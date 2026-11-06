#!/usr/bin/env python3
"""Acquire official observations and build declared research tables."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
from html.parser import HTMLParser
import subprocess
import sys
import tempfile
import itertools
import json
import math
from pathlib import Path
import re
import random
import shutil
from urllib.parse import quote, urlencode


def source_module():
    for parent in Path(__file__).resolve().parents:
        for name in ('skills/econ-literature/scripts/research_sources.py',
                     '.agents/skills/econ-literature/scripts/research_sources.py',
                     'research_sources.py'):
            candidate = parent / name
            if candidate.is_file():
                spec = importlib.util.spec_from_file_location('data_research_sources', candidate)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module
    raise FileNotFoundError('Include the registered research source helper')


sources = source_module()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    sources.atomic_write(path, (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode())


def write_csv(path, fields, rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    raw = stream.getvalue().encode()
    sources.atomic_write(path, raw)
    return {'path': str(path.resolve()), 'sha256': digest(raw), 'rows': len(rows), 'fields': fields}


def numeric(value):
    if value is None or value in ('', '.', 'NA', ':'):
        return None
    require(not isinstance(value, bool), 'Observation must be numeric or missing')
    result = float(value)
    require(math.isfinite(result), 'Observation must be finite')
    return result


def acquire(spec, directory):
    """Normalize the selected official series, retaining original response bytes."""
    require(isinstance(spec, dict), 'Acquisition specification must be an object')
    provider = spec.get('provider')
    allowed = {'provider', 'series', 'start', 'end', 'unit', 'definition', 'countries', 'filters', 'year', 'geography'}
    require(not set(spec) - allowed, 'Unknown acquisition fields')
    require(provider in ('fred', 'worldbank', 'imf', 'eurostat', 'census'), 'Select a supported official provider')
    require(all(isinstance(spec.get(k), str) and spec[k].strip() for k in ('unit', 'definition')), 'Adopt the quantity unit and definition')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    responses, observations, definitions = [], [], {}
    if provider == 'worldbank':
        result = sources.series(spec['series'], spec['countries'], int(spec['start']), int(spec['end']), directory / 'original')
        observations = [{'entity': row['country_code'], 'period': str(row['year']), 'value': row['value'], 'status': row['obs_status'], 'unit': spec['unit']} for row in result['observations']]
        responses = result['responses'] + result['definition_responses']
        definitions = result['indicator_definition']
        conditions = 'https://data.worldbank.org/summary-terms-of-use'
    elif provider == 'fred':
        series = spec['series']
        require(isinstance(series, str) and re.fullmatch(r'[A-Za-z0-9_]+', series), 'Invalid FRED series ID')
        require(all(re.fullmatch(r'\d{4}-\d{2}-\d{2}', spec[k]) for k in ('start', 'end')) and spec['start'] <= spec['end'], 'FRED dates use ordered YYYY-MM-DD')
        url = 'https://fred.stlouisfed.org/graph/fredgraph.csv?' + urlencode({'id': series, 'cosd': spec['start'], 'coed': spec['end']})
        raw, response = sources.retrieve(url, directory / 'original', 'fred.csv')
        responses.append(response)
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
        require(reader.fieldnames == ['observation_date', series], 'FRED returned an unexpected series schema')
        for row in reader:
            require(spec['start'] <= row['observation_date'] <= spec['end'], 'FRED returned a date outside the adopted range')
            observations.append({'entity': series, 'period': row['observation_date'], 'value': numeric(row[series]), 'status': '', 'unit': spec['unit']})
        definitions = {'series': series, 'metadata': 'https://fred.stlouisfed.org/series/' + series}
        conditions = 'https://fred.stlouisfed.org/legal/'
    elif provider == 'imf':
        series, countries = spec['series'], spec['countries']
        require(re.fullmatch(r'[A-Za-z0-9_]+', series) and countries and all(re.fullmatch(r'[A-Z]{3}', c) for c in countries), 'Invalid IMF indicator or country IDs')
        begin, end = int(spec['start']), int(spec['end'])
        require(1 <= begin <= end <= 9999 and len(set(countries)) == len(countries), 'Invalid IMF years or repeated country IDs')
        url = 'https://www.imf.org/external/datamapper/api/v1/' + series + '/' + '/'.join(countries)
        payload, response = sources.get_json(url, directory / 'original', 'imf.json')
        responses.append(response)
        values = payload.get('values', {}).get(series)
        require(isinstance(values, dict) and set(countries) <= set(values), 'IMF response omitted requested country series')
        for country in countries:
            for year, value in values[country].items():
                if begin <= int(year) <= end:
                    observations.append({'entity': country, 'period': str(year), 'value': numeric(value), 'status': '', 'unit': spec['unit']})
        definitions = {'series': series, 'metadata': 'https://www.imf.org/external/datamapper/' + series}
        conditions = 'https://www.imf.org/external/terms.htm'
    elif provider == 'eurostat':
        series, filters = spec['series'], spec['filters']
        require(re.fullmatch(r'[a-zA-Z0-9_]+', series) and isinstance(filters, dict) and filters and all(isinstance(k, str) and isinstance(v, str) for k, v in filters.items()), 'Eurostat needs a dataset and explicit dimension filters')
        require(not {'lang', 'sinceTimePeriod', 'untilTimePeriod'} & set(filters), 'Use the declared period range and English metadata')
        url = 'https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/' + series + '?' + urlencode({'lang': 'EN', **filters, 'sinceTimePeriod': spec['start'], 'untilTimePeriod': spec['end']})
        payload, response = sources.get_json(url, directory / 'original', 'eurostat.json')
        responses.append(response)
        ids, sizes, dimensions = payload.get('id'), payload.get('size'), payload.get('dimension')
        require(isinstance(ids, list) and isinstance(sizes, list) and len(ids) == len(sizes) and 'time' in ids and isinstance(dimensions, dict), 'Eurostat JSON-stat dimensions are missing')
        categories = []
        for key, size in zip(ids, sizes):
            index = dimensions[key]['category']['index']
            index = {v: i for i, v in enumerate(index)} if isinstance(index, list) else index
            require(isinstance(index, dict) and sorted(index.values()) == list(range(size)), 'Eurostat category positions are invalid')
            categories.append([k for k, _ in sorted(index.items(), key=lambda pair: pair[1])])
        values, statuses = payload.get('value', {}), payload.get('status', {})
        for flat, cells in enumerate(itertools.product(*categories)):
            row = dict(zip(ids, cells))
            value = values[flat] if isinstance(values, list) else values.get(str(flat))
            status = statuses[flat] if isinstance(statuses, list) and flat < len(statuses) else statuses.get(str(flat), '') if isinstance(statuses, dict) else ''
            entity = row.get('geo') or '|'.join(row[k] for k in ids if k != 'time')
            observations.append({'entity': entity, 'period': row['time'], 'value': numeric(value), 'status': status, 'unit': spec['unit'], **{'dimension_' + k: v for k, v in row.items() if k != 'time'}})
        definitions = {'label': payload.get('label'), 'updated': payload.get('updated'), 'dimensions': dimensions}
        conditions = 'https://ec.europa.eu/eurostat/about-us/policies/copyright'
    elif provider == 'census' and spec.get('series') == 'POPESTIMATE':
        # Public Census Population Estimates CSV, 2024 vintage and state FIPS.
        year, geography = spec['year'], spec['geography']
        require(spec['unit'] == 'persons', 'Census population estimates are persons')
        require(year == 2024 and re.fullmatch(r'state:(?:\*|[0-9]{2}(?:,[0-9]{2})*)', geography),
                'Population Estimates use 2024 vintage and state FIPS codes')
        begin, end = int(spec['start']), int(spec['end'])
        require(2020 <= begin <= end <= year, 'Population Estimates years must be between 2020 and 2024')
        requested = geography.split(':',1)[1].split(',')
        require(requested == ['*'] or len(set(requested)) == len(requested), 'Repeated state FIPS')
        url = 'https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/state/totals/NST-EST2024-ALLDATA.csv'
        raw, response = sources.retrieve(url, directory/'original','census-population.csv')
        responses.append(response)
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
        require(set(['SUMLEV','STATE','NAME']+[f'POPESTIMATE{y}' for y in range(begin,end+1)]) <= set(reader.fieldnames or []), 'Census population columns missing')
        matched = set()
        for row in reader:
            if row['SUMLEV'] != '040' or (requested != ['*'] and row['STATE'] not in requested): continue
            matched.add(row['STATE'])
            for y in range(begin,end+1):
                observations.append({'entity':row['STATE'],'period':str(y),'value':numeric(row[f'POPESTIMATE{y}']),
                    'status':'','unit':spec['unit'],'name':row['NAME']})
        require(requested == ['*'] or set(requested) == matched, 'Census omitted requested state FIPS')
        definitions = {'series':'POPESTIMATE','vintage':2024,'geography':'state FIPS',
            'metadata':'https://www.census.gov/data/tables/time-series/demo/popest/2020s-state-total.html'}
        conditions = 'https://www.census.gov/about/policies/open-gov/open-data.html'
    else:
        year, series, geography = spec['year'], spec['series'], spec['geography']
        require(type(year) is int and 2009 <= year <= 9999 and re.fullmatch(r'[A-Z0-9_]+', series), 'Invalid Census year or variable')
        require(isinstance(geography, str) and re.fullmatch(r'[a-z ]+:(?:\*|[0-9,]+)', geography), 'Census geography must name an official geography and codes')
        url = f'https://api.census.gov/data/{year}/acs/acs5?' + urlencode({'get': 'NAME,' + series, 'for': geography})
        payload, response = sources.get_json(url, directory / 'original', 'census.json')
        responses.append(response)
        require(isinstance(payload, list) and len(payload) >= 2 and payload[0][:2] == ['NAME', series], 'Census returned an unexpected variable schema')
        keys = payload[0][2:]
        for values in payload[1:]:
            require(len(values) == len(payload[0]), 'Census row width differs')
            sentinel = values[1] in {'-222222222','-333333333','-555555555','-666666666','-777777777','-888888888','-999999999'}
            observations.append({'entity': '|'.join(values[2:]), 'period': str(year), 'value': None if sentinel else numeric(values[1]), 'status': 'census_sentinel:'+values[1] if sentinel else '', 'unit': spec['unit'], 'name': values[0], **{'geo_' + k: v for k, v in zip(keys, values[2:])}})
        definitions = {'variable': series, 'metadata': f'https://api.census.gov/data/{year}/acs/acs5/variables/{series}.json', 'geography_keys': keys}
        conditions = 'https://www.census.gov/about/policies/open-gov/open-data.html'
    require(observations, 'Official source returned no observations in the adopted range')
    observations.sort(key=lambda row: (row['entity'], row['period'], json.dumps(row, sort_keys=True)))
    fields = ['entity', 'period', 'value', 'status', 'unit'] + sorted(set().union(*(set(row) for row in observations)) - {'entity', 'period', 'value', 'status', 'unit'})
    keys = [(row['entity'], row['period'], *(row.get(k) for k in fields[5:])) for row in observations]
    require(len(keys) == len(set(keys)), 'Official observations contain duplicate declared cells')
    table = write_csv(directory / 'observations.csv', fields, observations)
    record = {'provider': provider, 'specification': spec, 'definition': definitions, 'conditions': conditions, 'responses': responses, 'table': table,
              'missing_values': sum(row['value'] is None for row in observations), 'producer_sha256': digest(Path(__file__).read_bytes())}
    write_json(directory / 'data-record.json', record)
    return record


def load_table(root, ref):
    require(isinstance(ref, dict) and set(ref) == {'path', 'sha256'}, 'Table reference requires path and hash')
    path = root / ref['path']
    raw = path.read_bytes()
    require(digest(raw) == ref['sha256'], 'Table input hash differs: ' + str(path))
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    require(reader.fieldnames and len(set(reader.fieldnames)) == len(reader.fieldnames), 'Table needs distinct columns')
    rows = list(reader)
    require(rows and all(None not in row and None not in row.values() for row in rows), 'Table is empty or malformed')
    return reader.fieldnames, rows


def validate_geometry(geometry):
    require(isinstance(geometry,dict) and geometry.get('type') in ('Point','Polygon','MultiPolygon'), 'GeoJSON requires point or region geometries')
    coordinates = geometry.get('coordinates')
    def point(p):
        require(isinstance(p,list) and 2 <= len(p) <= 3 and all(type(x) in (int,float) and math.isfinite(x) for x in p), 'GeoJSON position requires finite coordinates')
        require(-180 <= p[0] <= 180 and -90 <= p[1] <= 90, 'GeoJSON coordinates must be longitude and latitude')
    def polygon(p):
        require(isinstance(p,list) and bool(p), 'GeoJSON polygon requires rings')
        for ring in p:
            require(isinstance(ring,list) and len(ring)>=4 and ring[0]==ring[-1], 'GeoJSON polygon rings must be closed and have at least four positions')
            for value in ring: point(value)
    if geometry['type']=='Point': point(coordinates)
    elif geometry['type']=='Polygon': polygon(coordinates)
    else:
        require(isinstance(coordinates,list) and bool(coordinates), 'GeoJSON multipolygon requires polygons')
        for value in coordinates: polygon(value)


def assemble(spec, root, directory):
    """Join adopted keys and definitions, then validate panel/geographical grain."""
    root, directory = Path(root), Path(directory)
    require(set(spec) <= {'base', 'joins', 'definitions', 'grain', 'panel', 'geography', 'rename', 'numeric', 'scale'}, 'Unknown table construction fields')
    fields, rows = load_table(root, spec['base'])
    provenance = [spec['base']]
    for join in spec.get('joins', []):
        require(set(join) == {'table', 'left', 'right', 'columns', 'cardinality', 'unmatched'}, 'Join must declare keys, fields, cardinality and unmatched treatment')
        extra_fields, extra = load_table(root, join['table'])
        left, right, columns = join['left'], join['right'], join['columns']
        require(isinstance(left, list) and left and len(left) == len(right) and set(left) <= set(fields) and set(right) | set(columns) <= set(extra_fields), 'Join columns differ from source tables')
        require(not set(columns) & set(fields) and join['cardinality'] in ('one_to_one', 'many_to_one') and join['unmatched'] in ('error', 'keep'), 'Join cardinality or output columns invalid')
        mapping = {}
        for row in extra:
            key = tuple(row[k] for k in right)
            require(all(key) and key not in mapping, 'Right join keys must be complete and unique')
            mapping[key] = row
        if join['cardinality'] == 'one_to_one':
            left_keys = [tuple(row[k] for k in left) for row in rows]
            require(len(left_keys) == len(set(left_keys)), 'One-to-one left keys must be unique')
        for row in rows:
            key = tuple(row[k] for k in left)
            require(all(key), 'Left join keys must be complete')
            target = mapping.get(key)
            require(target is not None or join['unmatched'] == 'keep', 'Unmatched join key: ' + str(key))
            row.update({k: target[k] if target else '' for k in columns})
        fields += columns
        provenance.append(join['table'])
    rename = spec.get('rename', {})
    require(set(rename) <= set(fields) and all(isinstance(k, str) and k for k in rename.values()), 'Rename requires existing fields and nonempty names')
    fields = [rename.get(k, k) for k in fields]
    require(len(set(fields)) == len(fields), 'Renaming creates duplicate columns')
    rows = [{rename.get(k, k): value for k, value in row.items()} for row in rows]
    for name in spec.get('numeric', []):
        require(name in fields, 'Numeric column is absent')
        for row in rows:
            row[name] = numeric(row[name])
    for name, factor in spec.get('scale', {}).items():
        require(name in fields and type(factor) in (int, float) and math.isfinite(factor), 'Scaling requires a column and finite factor')
        for row in rows:
            value = numeric(row[name])
            row[name] = value * factor if value is not None else None
    definitions, grain = spec['definitions'], spec['grain']
    require(set(definitions) == set(fields) and all(isinstance(v, dict) and set(v) == {'unit', 'definition', 'version'} and all(isinstance(x, str) and x for x in v.values()) for v in definitions.values()), 'Define every generated variable, unit and version')
    require(isinstance(grain, list) and grain and set(grain) <= set(fields), 'Declare the generated observation grain')
    keys = [tuple(row[k] for k in grain) for row in rows]
    require(all(all(v is not None and v != '' for v in key) for key in keys) and len(set(keys)) == len(keys), 'Generated observation grain must be complete and unique')
    panel_result = None
    if spec.get('panel'):
        panel = spec['panel']
        require(set(panel) == {'entity', 'time', 'balanced'} and type(panel['balanced']) is bool and {panel['entity'], panel['time']} <= set(grain), 'Panel requires entity/time grain and balanced flag')
        panel_keys = [(row[panel['entity']],row[panel['time']]) for row in rows]
        require(len(panel_keys) == len(set(panel_keys)), 'Panel entity-time keys must be unique')
        times = {row[panel['time']] for row in rows}
        per_entity = {}
        for row in rows:
            per_entity.setdefault(row[panel['entity']], set()).add(row[panel['time']])
        balanced = all(values == times for values in per_entity.values())
        require(not panel['balanced'] or balanced, 'Panel is missing declared entity-time cells')
        panel_result = {'entities': len(per_entity), 'periods': sorted(times, key=str), 'balanced': balanced}
    geo_result = None
    if spec.get('geography'):
        geo = spec['geography']
        require(set(geo) == {'path', 'sha256', 'data_key', 'feature_key'}, 'Geography requires hashed GeoJSON and matching key fields')
        require(geo['data_key'] in fields, 'Geography data key is absent')
        raw = (root / geo['path']).read_bytes()
        require(digest(raw) == geo['sha256'], 'GeoJSON input hash differs')
        payload = json.loads(raw)
        require(payload.get('type') == 'FeatureCollection' and isinstance(payload.get('features'), list), 'Use a GeoJSON FeatureCollection')
        geometry = {}
        for feature in payload['features']:
            require(isinstance(feature,dict) and feature.get('type') == 'Feature' and isinstance(feature.get('properties'),dict) and geo['feature_key'] in feature['properties'], 'GeoJSON feature key is absent')
            key = str(feature['properties'][geo['feature_key']])
            require(key not in geometry, 'GeoJSON requires unique feature keys')
            validate_geometry(feature['geometry'])
            geometry[key] = feature
        require(all(str(row[geo['data_key']]) in geometry for row in rows), 'Geographical data keys lack geometry')
        selected = sorted({str(row[geo['data_key']]) for row in rows})
        geo_path = directory / 'geography.geojson'
        write_json(geo_path, {'type': 'FeatureCollection', 'features': [geometry[key] for key in selected]})
        geo_result = {'path': str(geo_path.resolve()), 'sha256': digest(geo_path.read_bytes()), 'features': len(selected), 'join': geo}
        provenance.append({'path': geo['path'], 'sha256': geo['sha256']})
    table = write_csv(directory / 'analysis.csv', fields, rows)
    record = {'specification': spec, 'inputs': provenance, 'table': table, 'definitions': definitions, 'grain': grain, 'panel': panel_result, 'geography': geo_result,
              'producer_sha256': digest(Path(__file__).read_bytes())}
    write_json(directory / 'data-record.json', record)
    return record


class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.tables = []
        self.current = []
        self.row = None
        self.cell = None
    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.depth += 1
            if self.depth == 1: self.current = []
        elif self.depth == 1 and tag == 'tr': self.row = []
        elif self.depth == 1 and self.row is not None and tag in ('td','th'): self.cell = []
    def handle_data(self, data):
        if self.cell is not None: self.cell.append(data)
    def handle_endtag(self, tag):
        if self.depth == 1 and tag in ('td','th') and self.cell is not None:
            self.row.append(' '.join(''.join(self.cell).split()))
            self.cell = None
        elif self.depth == 1 and tag == 'tr' and self.row is not None:
            if self.row: self.current.append(self.row)
            self.row = None
        elif tag == 'table' and self.depth:
            if self.depth == 1: self.tables.append(self.current)
            self.depth -= 1


def extract_table(spec, root, directory):
    """Extract an explicitly located HTML table or exact PDF row."""
    ref = spec['source']; path = Path(root)/ref['path']; raw = path.read_bytes()
    require(digest(raw)==ref['sha256'], 'Document input hash differs')
    unit = spec['unit']; definition = spec['definition']
    require(isinstance(unit,str) and unit and isinstance(definition,str) and definition, 'Document unit and definition required')
    if spec['format']=='html':
        parser = _TableParser(); parser.feed(raw.decode('utf-8-sig'))
        index = int(spec['table_index'])
        require(0 <= index < len(parser.tables), 'HTML table index is absent')
        table = parser.tables[index]
        require(len(table)>=2 and len(set(table[0]))==len(table[0]) and all(table[0]), 'HTML table requires distinct headers and data')
        require(all(len(row)==len(table[0]) for row in table[1:]), 'HTML table must be rectangular')
        rows = [dict(zip(table[0],row)) for row in table[1:]]
        if spec.get('row_regex'):
            rx = re.compile(spec['row_regex'])
            rows = [row for row in rows if rx.search(' | '.join(row.values()))]
        fields = table[0]; location = {'table_index':index}; engine = 'Python html.parser'
    elif spec['format']=='pdf':
        page = int(spec['page'])
        require(page>=1, 'PDF page is one-based')
        completed = subprocess.run(['pdftotext','-layout','-f',str(page),'-l',str(page),str(path),'-'],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        lines = completed.stdout.decode('utf-8').splitlines()
        matches = [(i+1,line,re.fullmatch(spec['row_regex'],line)) for i,line in enumerate(lines)]
        matches = [(i,line,m) for i,line,m in matches if m is not None and line == spec['exact_line']]
        require(len(matches)==1 and matches[0][2].groupdict(), 'PDF declared page, exact line and named row captures must select exactly one row')
        line_number, line, match = matches[0]; rows = [match.groupdict()]; fields = list(rows[0]); location = {'page':page,'line_number':line_number,'exact_line':line}
        version = subprocess.run(['pdftotext','-v'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,check=True).stdout.splitlines()[0]
        engine = {'name':'pdftotext','version':version,'executable':shutil.which('pdftotext')}
    else: raise ValueError('format must be html or pdf')
    require(bool(rows), 'Table selection returned no rows')
    for column in spec.get('numeric',[]):
        require(column in fields, 'Numeric extraction column is absent')
        for row in rows: row[column] = numeric(row[column])
    table = write_csv(Path(directory)/'observations.csv',fields,rows)
    result = {'source':ref,'format':spec['format'],'location':location,'engine':engine,'unit':unit,'definition':definition,
        'specification':spec,'table':table,'producer_sha256':digest(Path(__file__).read_bytes())}
    write_json(Path(directory)/'data-record.json',result)
    return result


def catalog(spec, directory):
    provider, query = spec['provider'], spec['query']
    limit = int(spec.get('limit',20))
    require(isinstance(query,str) and query.strip() and 1 <= limit <= 100, 'Catalog query and limit 1–100 required')
    if provider == 'imf':
        url='https://www.imf.org/external/datamapper/api/v1/indicators'
        payload,response=sources.get_json(url,Path(directory)/'original','imf-indicators.json')
        entries=payload['indicators']
    elif provider == 'census':
        year=int(spec['year']); require(2009<=year<=2024,'Select ACS year 2009–2024')
        url=f'https://api.census.gov/data/{year}/acs/acs5/variables.json'
        payload,response=sources.get_json(url,Path(directory)/'original','census-variables.json')
        entries=payload['variables']
    else: raise ValueError('catalog supports imf and census; World Bank uses research_sources indicators')
    words=query.casefold().split()
    matches=[]
    for name,data in entries.items():
        text=(name+' '+str(data.get('label',''))+' '+str(data.get('description',''))+' '+str(data.get('concept',''))).casefold()
        if all(word in text for word in words): matches.append({'id':name,'metadata':data})
    conditions = 'https://www.imf.org/external/terms.htm' if provider == 'imf' else 'https://www.census.gov/about/policies/open-gov/open-data.html'
    result={'provider':provider,'query':query,'conditions':conditions,'matching_total':len(matches),'returned':min(limit,len(matches)),
        'entries':matches[:limit],'response':response,'producer_sha256':digest(Path(__file__).read_bytes())}
    write_json(Path(directory)/'catalog.json',result)
    return result


def dataset_mentions(spec, root, directory):
    """Locate adopted dataset-name patterns in a selected paper's original PDF pages."""
    ref=spec['source']; path=Path(root)/ref['path']; raw=path.read_bytes()
    require(digest(raw)==ref['sha256'], 'Paper input hash differs')
    first,last=int(spec['first_page']),int(spec['last_page'])
    require(1<=first<=last and last-first<=50, 'Select at most 51 ordered PDF pages')
    patterns=spec['datasets']
    require(isinstance(patterns,list) and patterns and all(set(x)=={'id','regex'} and x['id'] and x['regex'] for x in patterns), 'Adopt dataset IDs and search expressions')
    require(len({x['id'] for x in patterns})==len(patterns), 'Dataset IDs must be unique')
    completed=subprocess.run(['pdftotext','-layout','-f',str(first),'-l',str(last),str(path),'-'],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    pages=completed.stdout.decode('utf-8').split('\f')
    matches=[]
    for page_index,page in enumerate(pages):
        if page_index>last-first: break
        normalized=' '.join(page.split())
        for entry in patterns:
            for match in re.finditer(entry['regex'],normalized,flags=re.IGNORECASE):
                left=max(0,match.start()-150); right=min(len(normalized),match.end()+150)
                matches.append({'dataset_id':entry['id'],'page':first+page_index,'matched_text':match.group(),
                    'normalized_start':match.start(),'normalized_end':match.end(),'context':normalized[left:right],
                    'normalized_page_sha256':digest(normalized.encode())})
    require(bool(matches), 'No adopted dataset pattern appears on the selected pages')
    version=subprocess.run(['pdftotext','-v'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,check=True).stdout.splitlines()[0]
    result={'source':ref,'paper':spec['paper'],'pages':[first,last],'patterns':patterns,'matches':matches,
        'meaning':'dataset-name mentions in selected source pages; inspect context for actual use',
        'engine':version,'producer_sha256':digest(Path(__file__).read_bytes())}
    write_json(Path(directory)/'dataset-mentions.json',result)
    return result


DESCRIBE_R = r'''
args <- commandArgs(trailingOnly=TRUE)
suppressPackageStartupMessages(library(jsonlite))
suppressPackageStartupMessages(library(modelsummary))
suppressPackageStartupMessages(library(ggplot2))
job <- fromJSON(args[1], simplifyVector=TRUE)
d <- as.data.frame(job$rows, stringsAsFactors=FALSE)
weighted <- job$weights$kind != "none"
if (weighted && !requireNamespace("Hmisc", quietly=TRUE)) stop("Weighted summaries require Hmisc")
qprobs <- as.numeric(job$quantiles$probabilities)
qnames <- paste0("q", gsub("[.]", "p", format(qprobs * 100, scientific=FALSE, trim=TRUE, digits=15)))
groups <- as.character(job$groups)
summary_rows <- list()
trends <- list()
distributions <- list()
balance_rows <- list()
summarize <- function(x, w) {
    usable <- !is.na(x) & !is.na(w) & w > 0
    x <- x[usable]; w <- w[usable]
    if (!length(x)) return(as.list(setNames(c(rep(NA_real_, 5 + length(qprobs)), 0), c("mean", "sd", "median", qnames, "min", "max", "n"))))
    e <- new.env(parent=environment())
    e$Mean <- if (weighted) function(x) stats::weighted.mean(x, w) else base::mean
    e$SD <- if (weighted) function(x) sqrt(Hmisc::wtd.var(x, w, normwt=job$weights$normalization == "sum_to_n", method=job$weights$variance)) else stats::sd
    quantile_at <- function(p) {
        force(p)
        if (weighted) function(x) as.numeric(Hmisc::wtd.quantile(x, w, probs=p, normwt=job$weights$normalization == "sum_to_n", type=job$quantiles$method))
        else function(x) as.numeric(stats::quantile(x, probs=p, type=job$quantiles$type, names=FALSE))
    }
    e$Median <- quantile_at(0.5)
    e$Min <- base::min
    e$Max <- base::max
    e$N <- length
    for (j in seq_along(qprobs)) e[[qnames[j]]] <- quantile_at(qprobs[j])
    formula <- stats::reformulate(c("Mean", "SD", "Median", qnames, "Min", "Max", "N"), response="value", env=e)
    tab <- modelsummary::datasummary(formula, data=data.frame(value=x), output="data.frame",
                                    fmt=function(x) if (is.numeric(x)) sprintf("%.17g", x) else x)
    values <- lapply(tab[1, -1, drop=FALSE], function(value) as.numeric(value[[1]]))
    names(values) <- c("mean", "sd", "median", qnames, "min", "max", "n")
    values
}
counts <- function(x, w, take) {
    usable <- !is.na(x) & !is.na(w) & w > 0
    list(n_observations=length(x), n_entities=if (isTRUE(job$has_entity)) length(unique(d$entity[take][usable])) else NA_integer_,
         n_observed=sum(!is.na(x)), n_missing=sum(is.na(x)), n_zero=sum(x == 0, na.rm=TRUE),
         n_missing_weight=sum(is.na(w)), n_zero_weight=sum(w == 0, na.rm=TRUE),
         weight_sum=sum(w[usable]), frequency_n=if (job$weights$kind == "frequency") sum(w[usable]) else NA_real_)
}
balance_inference <- function(xall, variable_key) {
    b <- job$balance
    valid <- !is.na(xall) & !is.na(d$weight) & d$weight > 0 & d$group %in% c(b$control, b$treated)
    bd <- d[valid, , drop=FALSE]
    bd$value <- xall[valid]
    bd$treated <- as.numeric(bd$group == b$treated)
    control <- summarize(bd$value[bd$treated == 0], bd$weight[bd$treated == 0])
    treated <- summarize(bd$value[bd$treated == 1], bd$weight[bd$treated == 1])
    difference <- treated$mean - control$mean
    scale <- if (b$smd$denominator == "control_sd") control$sd else sqrt((treated$sd^2 + control$sd^2) / 2)
    out <- list(control=b$control, treated=b$treated, mean_control=control$mean, mean_treated=treated$mean,
                mean_difference=difference, difference=difference, standard_error=NA_real_, statistic=NA_real_, df=NA_real_, p_value=NA_real_,
                conf_low=NA_real_, conf_high=NA_real_, smd=if (is.finite(scale) && scale > 0) difference / scale else NA_real_,
                smd_scale=scale, n_control=control$n, n_treated=treated$n,
                weight_sum_control=sum(bd$weight[bd$treated == 0]), weight_sum_treated=sum(bd$weight[bd$treated == 1]),
                inference_n=NA_real_, inference_method=b$inference$method)
    method <- b$inference$method
    if (method == "none") return(out)
    level <- b$inference$confidence_level
    if (method == "welch") {
        if (job$weights$kind == "frequency") bd <- bd[rep(seq_len(nrow(bd)), bd$weight), , drop=FALSE]
        fit <- stats::t.test(bd$value[bd$treated == 1], bd$value[bd$treated == 0], conf.level=level)
        out$difference <- unname(diff(rev(fit$estimate)))
        out$standard_error <- unname(fit$stderr)
        out$statistic <- unname(fit$statistic)
        out$df <- unname(fit$parameter)
        out$p_value <- fit$p.value
        out$conf_low <- fit$conf.int[1]
        out$conf_high <- fit$conf.int[2]
        out$inference_n <- nrow(bd)
    } else if (method == "estimatr") {
        if (!requireNamespace("estimatr", quietly=TRUE)) stop("Declared mean-difference inference requires estimatr")
        args <- list(formula=value ~ treated, data=bd, condition1=0, condition2=1, alpha=1-level)
        if (!is.null(b$inference$clusters)) args$clusters <- bd$clusters
        if (!is.null(b$inference$blocks)) args$blocks <- bd$blocks
        fit <- do.call(estimatr::difference_in_means, args)
        out$difference <- unname(fit$coefficients)
        out$standard_error <- unname(fit$std.error)
        out$statistic <- unname(fit$statistic)
        out$df <- unname(fit$df)
        out$p_value <- unname(fit$p.value)
        out$conf_low <- unname(fit$conf.low)
        out$conf_high <- unname(fit$conf.high)
        out$inference_n <- unname(fit$nobs)
        out$inference_design <- fit$design
    } else {
        if (method == "survey") {
            if (!requireNamespace("survey", quietly=TRUE)) stop("Probability-weight inference requires survey")
            survey_data <- as.data.frame(job$survey_rows, stringsAsFactors=FALSE)
            survey_data$value <- as.numeric(survey_data[[variable_key]])
            survey_data$treated <- as.numeric(survey_data$group == b$treated)
            args <- list(ids=if (length(b$inference$ids)) stats::reformulate(paste0("ids", seq_along(b$inference$ids))) else ~1,
                         weights=~weight, data=survey_data, nest=b$inference$nest)
            for (field in c("strata", "fpc")) if (length(b$inference[[field]])) args[[field]] <- stats::reformulate(paste0(field, seq_along(b$inference[[field]])))
            design <- do.call(survey::svydesign, args)
            design <- subset(design, in_domain & group %in% c(b$control, b$treated) & !is.na(value))
            fit <- survey::svyglm(value ~ treated, design=design, family=stats::gaussian())
            info <- summary(fit)
            interval <- stats::confint(fit, parm="treated", level=level, method="Wald")
        } else {
            fit <- stats::lm(value ~ treated, data=bd, weights=weight)
            info <- summary(fit)
            interval <- stats::confint(fit, parm="treated", level=level)
        }
        out$difference <- unname(stats::coef(fit)["treated"])
        out$standard_error <- unname(info$coefficients["treated", 2])
        out$statistic <- unname(info$coefficients["treated", 3])
        out$df <- fit$df.residual
        out$p_value <- unname(info$coefficients["treated", 4])
        out$conf_low <- unname(interval[1])
        out$conf_high <- unname(interval[2])
        out$inference_n <- stats::nobs(fit)
    }
    out
}
for (i in seq_len(nrow(job$variables))) {
    variable <- job$variables[i, ]
    xall <- as.numeric(d[[variable$key]])
    if (!is.null(job$balance)) balance_rows[[length(balance_rows) + 1]] <- c(list(variable=variable$name, unit=variable$unit), balance_inference(xall, variable$key))
    trend_rows <- list()
    plot_rows <- list(histogram=list(), density=list(), ecdf=list(), box=list())
    display_groups <- if (isTRUE(job$grouped)) c(NA_character_, groups) else NA_character_
    for (group in display_groups) {
        take <- if (is.na(group)) rep(TRUE, nrow(d)) else d$group == group
        group_label <- if (is.na(group)) "全体" else group
        group_role <- if (is.na(group)) "full" else if (!is.null(job$balance) && group == job$balance$treated) "treated" else if (!is.null(job$balance) && group == job$balance$control) "control" else "group"
        x <- xall[take]; w <- as.numeric(d$weight[take])
        stats <- summarize(x, w)
        row <- c(list(variable=variable$name, group=group_label, group_role=group_role), stats, counts(x, w, take), list(unit=variable$unit))
        summary_rows[[length(summary_rows) + 1]] <- row
        for (period in job$periods) {
            period_take <- take & d$period == period
            period_stats <- summarize(xall[period_take], as.numeric(d$weight[period_take]))
            trend_rows[[length(trend_rows) + 1]] <- c(list(variable=variable$name, group=group_label, group_role=group_role, period=period),
                period_stats, counts(xall[period_take], as.numeric(d$weight[period_take]), period_take), list(unit=variable$unit))
        }
        usable <- !is.na(x) & !is.na(w) & w > 0
        x <- x[usable]; w <- w[usable]
        if (!length(x)) next
        pd <- data.frame(value=x, weight=w)
        options <- job$distributions[[variable$name]]
        if (is.null(options)) next
        save_layer <- function(layer, type, unit) {
            for (j in seq_len(nrow(layer))) {
                one <- as.list(layer[j, , drop=FALSE])
                plot_rows[[type]][[length(plot_rows[[type]]) + 1]] <<- c(list(variable=variable$name, group=group_label, group_role=group_role), one, list(n=length(x), weight_sum=sum(w), unit=unit))
            }
        }
        if (!is.null(options$histogram)) {
            h <- options$histogram
            if (min(x) < min(h$breaks) || max(x) > max(h$breaks)) stop("Histogram breaks must cover the selected values")
            p <- ggplot(pd, aes(x=value, weight=weight)) + geom_histogram(breaks=h$breaks, closed=h$closed)
            layer <- ggplot2::layer_data(p)
            layer <- data.frame(bin_mid=layer$x, bin_low=layer$xmin, bin_high=layer$xmax, count=layer$count, density=layer$density)
            save_layer(layer, "histogram", if (weighted) "weight" else "observations")
        }
        if (!is.null(options$density) && length(x) >= 2) {
            de <- options$density
            p <- ggplot(pd, aes(x=value, weight=weight)) + geom_density(bw=de$bw, adjust=de$adjust, n=de$n, kernel="gaussian")
            layer <- ggplot2::layer_data(p)
            save_layer(data.frame(x=layer$x, value=layer$density), "density", paste0("1/(", variable$unit, ")"))
        }
        if (!is.null(options$ecdf)) {
            if (weighted) {
                ec <- Hmisc::wtd.Ecdf(x, w, normwt=FALSE, type="i/n")
                layer <- data.frame(x=ec$x, value=ec$ecdf)
            } else {
                p <- ggplot(pd, aes(x=value)) + stat_ecdf(pad=FALSE)
                built <- ggplot2::layer_data(p)
                layer <- data.frame(x=built$x, value=built$y)
            }
            layer <- layer[order(layer$x), , drop=FALSE]
            save_layer(layer, "ecdf", "share")
        }
        if (!is.null(options$box)) {
            if (weighted && !requireNamespace("quantreg", quietly=TRUE)) stop("Weighted ggplot2 box plots require quantreg")
            mapping <- if (weighted) aes(x=factor(1), y=value, weight=weight) else aes(x=factor(1), y=value)
            p <- ggplot(pd, mapping) + geom_boxplot(coef=options$box$coef, outlier.shape=NA)
            built <- ggplot2::layer_data(p)
            layer <- data.frame(ymin=built$ymin, lower=built$lower, middle=built$middle,
                                upper=built$upper, ymax=built$ymax,
                                n_outliers=vapply(built$outliers, length, integer(1)))
            save_layer(layer, "box", variable$unit)
        }
    }
    trends[[variable$name]] <- trend_rows
    distributions[[variable$name]] <- plot_rows
}
packages <- c("modelsummary", "ggplot2", "jsonlite", if (weighted) "Hmisc")
if (!is.null(job$balance) && job$balance$inference$method %in% c("estimatr", "survey")) packages <- c(packages, job$balance$inference$method)
if (weighted && any(vapply(job$distributions, function(x) !is.null(x$box), logical(1)))) packages <- c(packages, "quantreg")
versions <- setNames(lapply(packages, function(p) as.character(packageVersion(p))), packages)
write_json(list(rows=summary_rows, balance=balance_rows, trends=trends, distributions=distributions,
                engine=list(R=R.version.string, packages=versions)), args[2], auto_unbox=TRUE, digits=NA, na="null", dataframe="rows", pretty=TRUE)
'''


def describe(spec, root, directory, rscript='Rscript'):
    """Calculate adopted display aggregates through modelsummary and ggplot2."""
    allowed = {'result_id', 'specification', 'data', 'row_id', 'population', 'sample',
               'period', 'group', 'variables', 'weights', 'quantiles', 'denominator', 'distributions',
               'observation_unit', 'entity', 'balance'}
    require(isinstance(spec, dict) and not set(spec) - allowed, 'Unknown descriptive specification fields')
    for key in ('result_id', 'specification', 'row_id', 'population', 'denominator'):
        require(isinstance(spec.get(key), str) and spec[key], 'Adopt descriptive ' + key)
    root = Path(root).resolve()
    data_path = Path(spec['data']['path'])
    require(not data_path.is_absolute() and '..' not in data_path.parts, 'Data path must be project-relative')
    fields, rows = load_table(root, spec['data'])
    input_rows = rows
    require(spec['row_id'] in fields, 'Row identity column is absent')
    identities = [row[spec['row_id']] for row in rows]
    require(all(identities) and len(set(identities)) == len(rows), 'Row identities must be complete and unique')
    observation_unit = spec.get('observation_unit', 'records')
    require(isinstance(observation_unit, str) and observation_unit, 'Observation unit must be a nonempty label')
    entity = spec.get('entity')
    if entity is not None:
        require(isinstance(entity, str) and entity in fields and all(row[entity] for row in rows), 'Entity column must contain complete identities')

    def sample_count(stage, selected):
        return {'stage': stage, 'n': len(selected), 'n_observations': len(selected),
                'n_entities': len({row[entity] for row in selected}) if entity else None, 'unit': observation_unit}

    variables = spec.get('variables')
    require(isinstance(variables, list) and variables, 'Select descriptive variables')
    for variable in variables:
        require(isinstance(variable, dict) and set(variable) <= {'name', 'unit', 'label', 'status', 'observed_statuses'} and all(isinstance(variable.get(key), str) and variable[key] for key in ('name', 'unit')), 'Variable needs its saved name and unit')
        require(variable['name'] in fields, 'Descriptive variable is absent: ' + variable['name'])
        if 'status' in variable:
            require(variable['status'] in fields and isinstance(variable.get('observed_statuses'), list) and variable['observed_statuses'], 'Status fields require adopted observed_statuses')
    require(len({variable['name'] for variable in variables}) == len(variables), 'Descriptive variable names must be distinct')
    sample = spec.get('sample', {})
    require(isinstance(sample, dict) and sample.get('id') and sample.get('policy') in ('available-case', 'complete-case', 'fitted'), 'Adopt sample id and available-case, complete-case or fitted policy')
    require(not set(sample) - {'id', 'policy', 'filters', 'result', 'ids_key'} and isinstance(sample.get('filters', []), list), 'Sample uses explicit filters or a saved fitted-result identity list')
    flow = [sample_count('input', rows)]
    for condition in sample.get('filters', []):
        require(set(condition) == {'column', 'values'} and condition['column'] in fields and isinstance(condition['values'], list), 'Sample filters require a column and explicit values')
        values = {str(value) for value in condition['values']}
        rows = [row for row in rows if row[condition['column']] in values]
        flow.append(sample_count('filter:' + condition['column'], rows))
    if sample['policy'] == 'fitted':
        reference = sample['result']
        path = Path(reference['path'])
        require(not path.is_absolute() and '..' not in path.parts, 'Fitted result path must be project-relative')
        raw = (root / path).read_bytes()
        require(digest(raw) == reference['sha256'], 'Fitted sample result hash differs')
        selected = json.loads(raw)
        for key in sample['ids_key']:
            selected = selected[key]
        require(isinstance(selected, list), 'Fitted sample key must contain the recorded row IDs')
        selected_ids = {str(value) for value in selected}
        require(selected_ids <= set(identities), 'Fitted row identities are absent from the input snapshot')
        rows = [row for row in rows if row[spec['row_id']] in selected_ids]
        require({row[spec['row_id']] for row in rows} == selected_ids, 'Sample filters changed the adopted fitted sample')
        flow.append(sample_count('fitted sample', rows))
    period = spec.get('period')
    if isinstance(period, dict):
        require(set(period) == {'column', 'values', 'label'} and period['column'] in fields and isinstance(period['values'], list) and period['values'], 'Period requires column, values and label')
        periods = [str(value) for value in period['values']]
        rows = [row for row in rows if row[period['column']] in periods]
        period_label = period['label']
    else:
        require(isinstance(period, str) and period, 'Adopt the descriptive period')
        periods, period_label = [period], period
    flow.append(sample_count('period', rows))
    group = spec.get('group')
    if group:
        require(set(group) == {'column', 'levels', 'missing'} and group['column'] in fields and group['missing'] in ('include', 'exclude') and isinstance(group['levels'], list) and group['levels'], 'Group requires column, levels and missing policy')
        groups = [str(value) for value in group['levels']]
        require(len(groups) == len(set(groups)), 'Group levels must be distinct')
        if group['missing'] == 'include':
            groups.append('（群欠損）')
        rows = [row for row in rows if (row[group['column']] or '（群欠損）') in groups]
    else:
        groups = ['全体']
    flow.append(sample_count('groups', rows))
    weights = spec.get('weights')
    require(isinstance(weights, dict) and weights.get('kind') in ('none', 'frequency', 'population', 'reliability', 'probability', 'analytic'), 'Adopt the weight meaning')
    weighted = weights['kind'] != 'none'
    if weighted:
        require(set(weights) == {'kind', 'column', 'normalization', 'variance'} and weights['column'] in fields and weights['normalization'] in ('none', 'sum_to_n') and weights['variance'] in ('unbiased', 'ML'), 'Weights require column, normalization and variance convention')
        require(weights['kind'] != 'frequency' or weights['normalization'] == 'none', 'Frequency weights retain their original counts')
        require(weights['kind'] != 'reliability' or weights['normalization'] == 'sum_to_n', 'Reliability weights normalize to the usable observation count')
        require(weights['kind'] != 'analytic' or weights['normalization'] == 'sum_to_n', 'Analytic-weight descriptive dispersion uses normalized relative weights')
        require(weights['kind'] != 'population' or weights['variance'] == 'ML', 'Population-weight dispersion uses the adopted population variance')
        require(weights['kind'] != 'probability' or weights['normalization'] == 'none' and weights['variance'] == 'ML', 'Probability-weight summaries retain sampling weights and use population dispersion')
    else:
        require(set(weights) == {'kind'}, 'Unweighted summaries require weights.kind=none')
    balance = spec.get('balance')
    design_columns = {}
    if balance is not None:
        require(isinstance(balance, dict) and set(balance) <= {'treated', 'control', 'inference', 'smd', 'plot_smd'} and group, 'Balance requires named treated/control groups and an adopted group definition')
        require(balance.get('treated') in groups and balance.get('control') in groups and balance['treated'] != balance['control'], 'Balance treated and control must be distinct adopted levels')
        require('observation_unit' in spec, 'Balance requires the observation unit')
        require(isinstance(balance.get('smd'), dict) and set(balance['smd']) == {'denominator'} and balance['smd']['denominator'] in ('pooled_sd', 'control_sd'), 'Adopt pooled_sd or control_sd for SMD')
        require(type(balance.get('plot_smd', False)) is bool, 'plot_smd must be a boolean')
        inference = balance.get('inference')
        require(isinstance(inference, dict) and inference.get('method') in ('none', 'welch', 'estimatr', 'survey', 'analytic_wls'), 'Adopt the mean-difference inference method')
        method = inference['method']
        allowed_inference = {'method'} if method == 'none' else {'method', 'confidence_level'}
        if method == 'estimatr':
            allowed_inference |= {'clusters', 'blocks'}
        if method == 'survey':
            allowed_inference |= {'ids', 'strata', 'fpc', 'nest'}
        require(not set(inference) - allowed_inference, 'Unknown mean-difference inference fields')
        if method != 'none':
            require(type(inference.get('confidence_level')) in (int, float) and 0 < inference['confidence_level'] < 1, 'Adopt the mean-difference confidence level')
        compatible = {'none': {'none', 'welch', 'estimatr'}, 'frequency': {'none', 'welch'},
                      'probability': {'none', 'survey'}, 'analytic': {'none', 'analytic_wls'},
                      'reliability': {'none', 'analytic_wls'}, 'population': {'none'}}
        require(method in compatible[weights['kind']], 'Inference method does not match the declared weight type')
        for field in ('clusters', 'blocks'):
            if field in inference:
                require(isinstance(inference[field], str) and inference[field] in fields, field + ' must name a data column')
                design_columns[field] = inference[field]
        if method == 'survey':
            require('ids' in inference and type(inference.get('nest')) is bool, 'Survey inference requires ids and an explicit nest flag; ids=[] declares independent sampling')
            for field in ('ids', 'strata', 'fpc'):
                columns = inference.get(field, [])
                require(isinstance(columns, list) and all(isinstance(column, str) and column in fields for column in columns), 'Survey ' + field + ' must list existing columns')
                design_columns.update({field + str(i + 1): column for i, column in enumerate(columns)})
    quantiles = spec.get('quantiles')
    require(isinstance(quantiles, dict) and isinstance(quantiles.get('probabilities'), list) and quantiles['probabilities'] and all(type(p) in (int, float) and 0 <= p <= 1 for p in quantiles['probabilities']), 'Adopt quantile probabilities')
    require(len(set(quantiles['probabilities'])) == len(quantiles['probabilities']), 'Quantile probabilities must be distinct')
    if weighted:
        require(quantiles.get('method') in ('quantile', '(i-1)/(n-1)', 'i/(n+1)', 'i/n'), 'Adopt the Hmisc weighted quantile convention')
        require(weights['kind'] != 'probability' or quantiles['method'] == 'i/n', 'Probability-weight quantiles use the scale-invariant weighted ECDF i/n convention')
    else:
        require(type(quantiles.get('type')) is int and 1 <= quantiles['type'] <= 9, 'Adopt an R quantile type from 1 to 9')

    def design_values(row):
        values = {}
        for key, column in design_columns.items():
            value = numeric(row[column]) if key.startswith('fpc') else row[column]
            require(value is not None and value != '', 'Inference design column has missing values: ' + column)
            values[key] = value
        return values

    prepared, row_ids, selected_rows = [], [], []
    status_counts = {}
    for row in rows:
        weight = numeric(row[weights['column']]) if weighted else 1.0
        require(weight is None or weight >= 0, 'Weights must be nonnegative')
        require(weights['kind'] != 'frequency' or weight is None or weight.is_integer(), 'Frequency weights must be integer counts')
        prepared_row = {'group': row[group['column']] or '（群欠損）' if group else '全体',
                        'period': row[period['column']] if isinstance(period, dict) else period,
                        'weight': weight, 'entity': row[entity] if entity else None}
        prepared_row.update(design_values(row))
        for index, variable in enumerate(variables):
            status = row[variable['status']] if 'status' in variable else 'observed'
            observed = 'status' not in variable or status in variable['observed_statuses']
            value = numeric(row[variable['name']]) if observed else None
            if 'status' not in variable and value is None:
                status = 'missing'
            status_counts.setdefault(variable['name'], {}).setdefault(status, 0)
            status_counts[variable['name']][status] += 1
            prepared_row['v' + str(index)] = value
        if sample['policy'] == 'complete-case' and (weight is None or weight == 0 or any(prepared_row['v' + str(index)] is None for index in range(len(variables)))):
            continue
        prepared.append(prepared_row)
        row_ids.append(row[spec['row_id']])
        selected_rows.append(row)
    flow.append(sample_count(sample['policy'], selected_rows))
    if sample['policy'] == 'fitted':
        require(set(row_ids) == selected_ids, 'Period or group selection changed the adopted fitted sample')
    require(prepared, 'The adopted sample has no rows')
    survey_rows = None
    if balance is not None and balance['inference']['method'] == 'survey':
        adopted_rows = dict(zip(row_ids, prepared))
        survey_rows = []
        for row in input_rows:
            weight = numeric(row[weights['column']])
            require(weight is None or weight >= 0, 'Survey weights must be nonnegative')
            if weight is None or weight == 0:
                continue
            adopted = adopted_rows.get(row[spec['row_id']])
            design_row = {'weight': weight, 'group': row[group['column']] or '（群欠損）',
                          'in_domain': adopted is not None, **design_values(row)}
            for index in range(len(variables)):
                key = 'v' + str(index)
                design_row[key] = adopted[key] if adopted is not None else None
            survey_rows.append(design_row)
    distributions = spec.get('distributions', {})
    require(isinstance(distributions, dict) and not set(distributions) - {v['name'] for v in variables}, 'Distribution variables must be selected summaries')
    for name, options in distributions.items():
        require(isinstance(options, dict) and not set(options) - {'histogram', 'density', 'ecdf', 'box'}, 'Unknown distribution type')
        if 'histogram' in options:
            h = options['histogram']; breaks = h.get('breaks', [])
            require(set(h) == {'breaks', 'closed'} and len(breaks) >= 2 and all(type(x) in (int, float) and math.isfinite(x) for x in breaks) and all(a < b for a, b in zip(breaks, breaks[1:])) and h['closed'] in ('left', 'right'), 'Histogram requires increasing breaks and closed side')
        if 'density' in options:
            d = options['density']
            require(set(d) == {'bw', 'adjust', 'n'} and (d['bw'] == 'nrd0' or type(d['bw']) in (int, float) and d['bw'] > 0) and type(d['adjust']) in (int, float) and d['adjust'] > 0 and type(d['n']) is int and d['n'] >= 2, 'Density requires adopted bw, adjust and n')
        if 'box' in options:
            require(set(options['box']) == {'coef'} and type(options['box']['coef']) in (int, float) and options['box']['coef'] >= 0, 'Box plot requires its adopted whisker coefficient')
        if 'ecdf' in options:
            require(options['ecdf'] == {}, 'ECDF uses the saved empirical distribution without padding')
    job = {'rows': prepared, 'groups': groups, 'periods': periods, 'weights': weights, 'quantiles': quantiles,
           'variables': [{'key': 'v' + str(i), **v} for i, v in enumerate(variables)], 'distributions': distributions,
           'balance': balance, 'grouped': bool(group), 'has_entity': entity is not None, 'survey_rows': survey_rows}
    binary = shutil.which(rscript)
    require(binary is not None, 'Rscript is required for descriptive summaries')
    with tempfile.TemporaryDirectory(prefix='.describe-', dir=directory) as temporary:
        temporary = Path(temporary)
        write_json(temporary / 'input.json', job)
        (temporary / 'describe.R').write_text(DESCRIBE_R, encoding='utf8')
        subprocess.run([binary, '--vanilla', str(temporary / 'describe.R'), str(temporary / 'input.json'), str(temporary / 'output.json')], check=True)
        computed = json.loads((temporary / 'output.json').read_text())
    require(digest((root / data_path).read_bytes()) == spec['data']['sha256'], 'Input snapshot changed during descriptive calculation')
    metadata = {'population': spec['population'], 'sample': sample['id'], 'sample_policy': sample['policy'],
                'period': period_label, 'weights': weights, 'denominator': spec['denominator'],
                'specification': spec['specification'], 'outcome': [v['name'] for v in variables],
                'quantile_method': quantiles, 'group': group or 'all', 'observation_unit': observation_unit,
                'entity': entity, 'time': period, 'weight_type': weights['kind'],
                'n_definition': 'usable source records with positive observed weight',
                'summary_engine': 'modelsummary::datasummary',
                'units': {v['name']: v['unit'] for v in variables}}
    units = {variable['unit'] for variable in variables}
    if len(units) == 1:
        metadata['unit'] = next(iter(units))
    display = {'kind': 'table1', 'rows': computed['rows'], 'metadata': metadata,
               'sample_flow': {'kind': 'sample-flow', 'rows': flow, 'metadata': metadata},
               'trends': {}, 'distributions': {}}
    if balance is not None:
        balance_metadata = {**metadata, 'treated': balance['treated'], 'control': balance['control'],
                            'treatment_group': balance['treated'], 'control_group': balance['control'],
                            'contrast': 'treated minus control', 'inference': balance['inference'],
                            'smd_definition': {'numerator': 'unadjusted treated minus control mean',
                                               'denominator': balance['smd']['denominator'],
                                               'pooled_sd': 'sqrt((treated_variance + control_variance) / 2)'},
                            'difference_in_means': True}
        if balance['inference']['method'] != 'none':
            balance_metadata['confidence_level'] = balance['inference']['confidence_level']
            balance_metadata.update(official_function={'welch': 'stats::t.test', 'estimatr': 'estimatr::difference_in_means',
                'survey': 'survey::svyglm', 'analytic_wls': 'stats::lm'}[balance['inference']['method']],
                interval_type='two-sided pointwise t', reference_distribution='t',
                inference_unit=balance['inference'].get('clusters') or balance['inference'].get('ids') or observation_unit)
            if survey_rows is not None:
                balance_metadata['survey_design_scope'] = 'all positive-weight input records; adopted sample is a survey domain'
                balance_metadata['survey_design_observations'] = len(survey_rows)
        display['balance'] = {'kind': 'balance', 'rows': computed['balance'], 'metadata': balance_metadata}
        if balance.get('plot_smd'):
            display['smd'] = {'kind': 'smd', 'rows': [{key: row[key] for key in ('variable', 'control', 'treated', 'smd', 'smd_scale', 'n_control', 'n_treated')} for row in computed['balance']],
                              'metadata': {**balance_metadata, 'unit': 'standard deviations', 'smd_scale': balance['smd']['denominator']}}
    else:
        display['balance'] = {'kind': 'balance',
                              'rows': [row for row in computed['rows'] if not group or row['group_role'] != 'full'],
                              'metadata': {**metadata, 'table_type': 'group_summary', 'difference_in_means': False}}
    if isinstance(period, dict):
        display['by_year'] = {'kind': 'table1', 'rows': [row for rows_for_variable in computed['trends'].values() for row in rows_for_variable],
                              'metadata': metadata}
    for variable in variables:
        name = variable['name']
        shared = {**metadata, 'outcome': name, 'unit': variable['unit']}
        display['trends'][name] = {'kind': 'trend', 'rows': computed['trends'][name], 'metadata': shared}
        display['distributions'][name] = {}
        for kind, saved_rows in computed['distributions'][name].items():
            if saved_rows:
                unit = saved_rows[0]['unit']
                display['distributions'][name][kind] = {'kind': 'distribution', 'rows': saved_rows,
                    'metadata': {**shared, 'unit': unit, 'outcome_unit': variable['unit'],
                                 'distribution_type': kind, 'distribution_definition': distributions[name][kind],
                                 **({'outliers': 'count_only'} if kind == 'box' else {})}}
    return {'result_id': spec['result_id'], 'specification': spec['specification'], 'status': 'completed',
            'method': 'modelsummary descriptive statistics and ggplot2 saved display data',
            'adopted': spec, 'sample': {'id': sample['id'], 'row_ids': row_ids, 'status_counts': status_counts,
                'n_observations': len(selected_rows), 'n_entities': len({row[entity] for row in selected_rows}) if entity else None,
                'variable_row_ids': {variable['name']: [identity for identity, row in zip(row_ids, prepared)
                    if row['v' + str(i)] is not None and row['weight'] is not None and row['weight'] > 0]
                    for i, variable in enumerate(variables)}},
            'display': display, 'statistics': {}, 'engine': computed['engine'],
            'provenance': {'data_sha256': spec['data']['sha256'], 'script_sha256': digest(Path(__file__).read_bytes()),
                           'r_script_sha256': digest(DESCRIBE_R.encode()), 'rscript': str(Path(binary).resolve()),
                           'rscript_options': ['--vanilla']}}


def create_case(root, python):
    """Prepare one finite synthetic pipeline for the existing research DAG."""
    root = Path(root).resolve()
    require(not root.exists(), 'Case directory already exists')
    python = str(Path(python).absolute())
    require(Path(python).is_file(), 'Analysis Python is absent')
    probe = subprocess.check_output([python,'-c',
        'import sys,json,importlib.metadata as m; print(json.dumps({"version":sys.version.split()[0],"packages":{x:m.version(x) for x in ["numpy","scipy","pandas","statsmodels"]}}))'],text=True)
    versions=json.loads(probe)
    root.mkdir(); (root/'code').mkdir(); (root/'data').mkdir()
    shutil.copyfile(Path(__file__).resolve(),root/'code/research_data.py')
    shutil.copyfile(Path(sources.__file__).resolve(),root/'code/research_sources.py')
    base = Path(__file__).resolve().parent
    estimator = base/'research_estimator.py' if (base/'research_estimator.py').is_file() else base/'research.py'
    require(estimator.is_file(), 'Existing research estimator is required')
    shutil.copyfile(estimator,root/'code/research.py')
    rng=random.Random(59020)
    observations=[]
    for person in range(1,21):
        for year in range(2020,2024):
            exposure=rng.gauss(0,1)
            outcome=1+1.4*exposure+.03*person+.05*(year-2020)+rng.gauss(0,.15)
            observations.append({'record_id':f'P{person:02}-{year}','person_id':f'P{person:02}',
                'firm_local':f'L{(person-1)%4+1}', 'year':str(year), 'exposure':exposure,'outcome':outcome})
    base=write_csv(root/'data/raw.csv',list(observations[0]),observations)
    crosswalk=write_csv(root/'data/crosswalk.csv',['firm_local','firm_id','region_id'],
        [{'firm_local':f'L{i}','firm_id':f'F{i}','region_id':f'R{i}'} for i in range(1,5)])
    geo={'type':'FeatureCollection','features':[{'type':'Feature','properties':{'region_id':f'R{i}'},
         'geometry':{'type':'Point','coordinates':[-100.+i,35.+i]}} for i in range(1,5)]}
    write_json(root/'data/regions.geojson',geo)
    definitions={key:{'unit':unit,'definition':definition,'version':'synthetic-v1'} for key,unit,definition in [
        ('record_id','identifier','unique person-year identifier'),('person_id','identifier','person identifier'),
        ('firm_local','identifier','local firm identifier'),('year','calendar year','observation year'),
        ('exposure','synthetic treatment units','seeded exposure'),('outcome','synthetic outcome units','seeded outcome'),
        ('firm_id','identifier','crosswalked firm identifier'),('region_id','identifier','firm region identifier')]}
    specification={'base':{'path':'data/raw.csv','sha256':base['sha256']},
        'joins':[{'table':{'path':'data/crosswalk.csv','sha256':crosswalk['sha256']},'left':['firm_local'],'right':['firm_local'],
            'columns':['firm_id','region_id'],'cardinality':'many_to_one','unmatched':'error'}],
        'definitions':definitions,'grain':['person_id','year'],'panel':{'entity':'person_id','time':'year','balanced':True},
        'numeric':['exposure','outcome'],'geography':{'path':'data/regions.geojson',
            'sha256':digest((root/'data/regions.geojson').read_bytes()),'data_key':'region_id','feature_key':'region_id'}}
    write_json(root/'data/assembly.json',specification)
    write_json(root/'data/source.json',{'kind':'seeded synthetic','seed':59020,'population':'20 persons linked to four firms across four years',
        'equation':'outcome = 1 + 1.4 exposure + .03 person_id + .05(year-2020) + Normal(0,.15)',
        'inputs':{'raw':base,'crosswalk':crosswalk,'geo_sha256':digest((root/'data/regions.geojson').read_bytes())}})
    runtime={'language':'python','probe_argv':[python],'version':versions['version'],'packages':versions['packages'],'files':[]}
    env={x:'1' for x in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')}
    def stage(id,inputs,depends,outputs,argv):
        return {'id':id,'inputs':inputs,'depends':depends,'outputs':outputs,'argv':argv,'runtime':runtime,'env':env}
    helper='{root}/code/research_data.py'
    stages=[stage('assemble',['code/research_data.py','code/research_sources.py','data/raw.csv','data/crosswalk.csv','data/regions.geojson','data/assembly.json','data/source.json'],{},
        {'table':'analysis.csv','record':'data-record.json','geography':'geography.geojson'},
        [python,helper,'assemble','{root}/data/assembly.json','--root','{root}','--output','{out:record}','--output-record']),
      stage('fit_spec',['code/research_data.py','code/research_sources.py','data/source.json'],{'assemble':['table','record']},{'spec':'fit.json'},
        [python,helper,'case-fit-spec','{dep:assemble:table}','--output','{out:spec}']),
      stage('fit',['code/research.py','data/source.json'],{'fit_spec':['spec'],'assemble':['table','record']},{'result':'fit-result.json'},
        [python,'{root}/code/research.py','estimate','{dep:fit_spec:spec}','--output','{out:result}']),
      stage('table',['code/research_data.py','code/research_sources.py'],{'fit':['result']},{'table':'summary.csv'},
        [python,helper,'case-table','{dep:fit:result}','--output','{out:table}'])]
    write_json(root/'manifest.json',{'pipeline':'synthetic-data-assembly','stages':stages})
    return {'root':str(root),'manifest':str(root/'manifest.json'),'source':str(root/'data/source.json')}


def case_fit_spec(data, output):
    write_json(Path(output),{'data':str(Path(data).resolve()),'id':'record_id','outcome':'outcome','exog':['exposure'],
        'population':'20 synthetic people over four years','period':'2020–2023','unit':'synthetic outcome per exposure unit',
        'method':'ols','covariance':{'type':'HC1'},'sources':[{'description':'seed 59020 data and crosswalk in declared DAG inputs'}],
        'question':'Estimate the synthetic exposure–outcome relation',
        'identification':'seeded exposure is independent of the generated disturbance'})


def case_table(result_path, output):
    result=json.loads(Path(result_path).read_text())
    write_csv(Path(output),['parameter','estimate','standard_error','observations','unit'],[{
        'parameter':'exposure','estimate':result['coefficients']['exposure'],
        'standard_error':result['standard_errors']['exposure'],'observations':result['observations'],
        'unit':'synthetic outcome per exposure unit'}])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('acquire', 'assemble', 'extract', 'catalog', 'case', 'case-fit-spec', 'case-table', 'dataset-use', 'describe'))
    parser.add_argument('specification', type=Path, nargs='?')
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--output-record', action='store_true')
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--rscript', default='Rscript')
    args = parser.parse_args(argv)
    if args.command == 'case':
        print(json.dumps(create_case(args.output,args.python))); return
    if args.specification is None: parser.error('specification is required')
    if args.command == 'case-fit-spec':
        case_fit_spec(args.specification,args.output); return
    if args.command == 'case-table':
        case_table(args.specification,args.output); return
    if args.output_record:
        if args.command != 'assemble' or args.output.name != 'data-record.json': parser.error('--output-record requires assemble output named data-record.json')
        args.output = args.output.parent
    raw = args.specification.read_bytes()
    spec = json.loads(raw)
    args.output.mkdir(parents=True, exist_ok=True)
    if args.command == 'describe':
        require(not (args.output / 'result.json').exists(), 'Result already exists; choose a new descriptive generation')
        result = describe(spec, args.root, args.output, args.rscript)
        result['provenance']['spec_sha256'] = digest(raw)
        write_json(args.output / 'result.json', result)
        print(json.dumps({'result': str((args.output / 'result.json').resolve()), 'result_id': result['result_id']}))
        return
    record_name = 'catalog.json' if args.command == 'catalog' else 'dataset-mentions.json' if args.command == 'dataset-use' else 'data-record.json'
    require(not (args.output/record_name).exists(), 'Output record already exists; select a new directory')
    if args.command == 'acquire': result = acquire(spec,args.output)
    elif args.command == 'assemble': result = assemble(spec,args.root,args.output)
    elif args.command == 'extract': result = extract_table(spec,args.root,args.output)
    elif args.command == 'dataset-use': result = dataset_mentions(spec,args.root,args.output)
    else: result = catalog(spec,args.output)
    result['specification_sha256'] = digest(raw)
    record_name = 'catalog.json' if args.command == 'catalog' else 'dataset-mentions.json' if args.command == 'dataset-use' else 'data-record.json'
    write_json(args.output/record_name,result)
    print(json.dumps({'record':str((args.output/record_name).resolve()),'table':result.get('table'),'returned':result.get('returned')}))


if __name__ == '__main__':
    main()
