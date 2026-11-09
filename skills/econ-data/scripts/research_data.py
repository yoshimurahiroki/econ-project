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
import tempfile
import itertools
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import unicodedata
from urllib.parse import quote, urlencode, urljoin, urlsplit

MISSING_VALUES = ('', '.', 'NA', ':')


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


def companion_command(language, executable=None, *, default_options=()):
    """Use the same R or Julia prefix as the research runner's runtime capture."""
    variable = 'ERS_' + language.upper() + '_ARGV'
    bound = os.environ.get(variable)
    if bound is None:
        prefix = [executable or {'r': 'Rscript', 'julia': 'julia'}[language], *default_options]
    else:
        prefix = json.loads(bound)
        require(isinstance(prefix, list) and prefix
                and all(isinstance(arg, str) and arg for arg in prefix),
                variable + ' must contain the bound command prefix')
        if executable is not None:
            requested, selected = shutil.which(executable), shutil.which(prefix[0])
            require(requested is not None and selected is not None
                    and Path(requested).resolve() == Path(selected).resolve(),
                    'Explicit executable must match the declared ' + language + ' companion')
    binary = shutil.which(prefix[0])
    require(binary is not None, 'Selected runtime executable is unavailable: ' + prefix[0])
    return [binary, *prefix[1:]]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    saved = sources.record_paths(value, path.parent, relative=True)
    sources.atomic_write(path, (json.dumps(saved, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode())


def csv_header(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        header = next(csv.reader(stream), [])
    require(header and all(header) and len(header) == len(set(header)), 'Table needs distinct nonempty columns')
    return header


def read_frame(path, *, columns=None, string_columns=None):
    """Read the canonical table once, preserving typed inputs and semantic IDs."""
    import pandas as pd
    path = Path(path)
    selected = None if columns is None else list(columns)
    text_columns = [] if string_columns is True else list(string_columns or [])
    require(selected is None or len(selected) == len(set(selected)), 'Requested columns must be distinct')
    suffix = path.suffix.lower()
    if suffix == '.csv':
        csv_header(path)
        frame = pd.read_csv(path, usecols=selected,
                            dtype='string' if string_columns is True else {name: 'string' for name in text_columns},
                            keep_default_na=string_columns is not True, float_precision='round_trip')
        require(isinstance(frame.index, pd.RangeIndex), 'CSV rows differ from the declared header')
    else:
        import pyarrow as pa
        if suffix == '.parquet':
            import pyarrow.parquet as pq
            table = pq.read_table(path, columns=selected)
        elif suffix in ('.arrow', '.feather', '.ipc'):
            import pyarrow.feather as feather
            table = feather.read_table(path, columns=selected, memory_map=True)
        else:
            raise ValueError('Use a CSV, Parquet or Arrow IPC table: ' + str(path))

        def nullable_dtype(dtype):
            if pa.types.is_integer(dtype):
                prefix = 'UInt' if pa.types.is_unsigned_integer(dtype) else 'Int'
                return getattr(pd, prefix + str(dtype.bit_width) + 'Dtype')()
            if pa.types.is_boolean(dtype):
                return pd.BooleanDtype()
            return None

        frame = table.to_pandas(types_mapper=nullable_dtype)
    require(frame.columns.is_unique, 'Table needs distinct columns')
    if selected is not None:
        frame = frame.loc[:, selected]
    for name in frame.columns if string_columns is True else text_columns:
        if name in frame:
            frame[name] = frame[name].astype('string')
    return frame


R_READ_TABLE = r'''
ers_read_table <- function(path, text_columns=character(), columns=NULL) {
  ext <- tolower(tools::file_ext(path))
  if (ext == 'csv') {
    header <- names(read.csv(path, nrows=0, check.names=FALSE))
    classes <- setNames(rep(NA_character_, length(header)), header)
    classes[if (isTRUE(text_columns)) header else intersect(header, text_columns)] <- 'character'
    if (!is.null(columns)) {
      if (anyDuplicated(columns) || !all(columns %in% header)) stop('Invalid table columns')
      classes[setdiff(header, columns)] <- 'NULL'
    }
    result <- read.csv(path, check.names=FALSE, colClasses=classes,
                       na.strings=if (isTRUE(text_columns)) character() else "NA")
  } else if (ext == 'parquet') {
    result <- do.call(arrow::read_parquet, list(file=path, col_select=columns, as_data_frame=FALSE))
  } else if (ext %in% c('arrow','feather','ipc')) {
    result <- do.call(arrow::read_ipc_file, list(file=path, col_select=columns, as_data_frame=FALSE))
  } else stop('Use a CSV, Parquet or Arrow IPC table')
  if (ext != 'csv') {
    native <- result
    result <- as.data.frame(native)
    for (field in native$schema$fields) {
      if (grepl('^timestamp\\[', field$type$ToString())) {
        original <- native[[field$name]]$cast(arrow::int64())$as_vector()
        restored <- arrow::Array$create(result[[field$name]], type=field$type)$cast(arrow::int64())$as_vector()
        if (!identical(as.character(original), as.character(restored))) {
          stop(paste('Timestamp loses R POSIXct precision; construct an explicit string/integer clock:', field$name))
        }
      }
    }
  }
  if (!is.null(columns)) result <- result[,columns,drop=FALSE]
  for (name in if (isTRUE(text_columns)) names(result) else intersect(text_columns, names(result))) {
    result[[name]] <- as.character(result[[name]])
  }
  result
}
'''


JULIA_READ_TABLE = r'''
import Tables
using DataFrames
function ers_read_table(path; string_columns=String[], columns=nothing)
    ext = lowercase(splitext(path)[2])
    if ext == ".csv"
        @eval import CSV
        types = Dict(Symbol(name) => String for name in string_columns)
        result = Base.invokelatest() do
            columns === nothing ? CSV.read(path, DataFrame; types=types) :
                CSV.read(path, DataFrame; types=types, select=String.(columns))
        end
    elseif ext == ".parquet"
        @eval import Parquet2
        result = Base.invokelatest() do
            source = Parquet2.Dataset(path)
            for name in (columns === nothing ? Tables.columnnames(source) : columns)
                physical = Parquet2.parqtype(Parquet2.SchemaNode(source, String(name)))
                if physical isa Parquet2.ParqDateTime &&
                        (physical.exponent === nothing || physical.exponent < -3)
                    error("Parquet timestamp precision exceeds Julia DateTime; use the canonical Arrow table or an explicit string/integer clock: " * String(name))
                end
            end
            columns === nothing ? DataFrame(source; copycols=true) :
                DataFrame([Symbol(name) => Tables.getcolumn(source, Symbol(name)) for name in columns])
        end
    elseif ext in (".arrow", ".feather", ".ipc")
        @eval import Arrow
        result = Base.invokelatest() do
            source = Arrow.Table(path)
            physical = Arrow.Table(path; convert=false)
            selected = columns === nothing ? Tables.columnnames(source) : columns
            DataFrame([Symbol(name) => begin
                raw = Tables.getcolumn(physical, Symbol(name))
                kind = Base.nonmissingtype(eltype(raw))
                exact = kind <: Arrow.Timestamp && kind.parameters[1] in
                    (Arrow.Meta.TimeUnit.MICROSECOND, Arrow.Meta.TimeUnit.NANOSECOND)
                Vector(exact ? raw : Tables.getcolumn(source, Symbol(name)))
            end for name in selected])
        end
    else
        error("Use a CSV, Parquet or Arrow IPC table")
    end
    if columns !== nothing
        result = result[:, Symbol.(columns)]
    end
    for name in intersect(String.(string_columns), names(result))
        result[!, name] = Base.invokelatest(map,
            value -> ismissing(value) ? missing : string(value), result[!, name])
    end
    result
end
'''


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            if isinstance(rows, list):
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            else:
                rows.to_csv(stream, columns=fields, index=False, na_rep='', lineterminator='\r\n')
        with temporary.open('rb') as stream:
            sha256 = hashlib.file_digest(stream, 'sha256').hexdigest()
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {'path': path.name, 'sha256': sha256, 'rows': len(rows), 'fields': fields}


def write_frame(path, fields, rows):
    """Write one canonical table and retain its ordered physical schema."""
    import pandas as pd
    path = Path(path)
    frame = pd.DataFrame(rows, columns=fields)
    output_format = path.suffix.lower().lstrip('.')
    require(output_format in ('csv', 'parquet', 'arrow'), 'output_format must be csv, parquet or arrow')
    schema = [{'name': name, 'pandas_dtype': str(frame[name].dtype),
               'nullable': bool(frame[name].isna().any())} for name in fields]
    for field in schema:
        column = frame[field['name']]
        if isinstance(column.dtype, pd.CategoricalDtype):
            field['categories'] = [value if isinstance(value, (str, int, float, bool)) else str(value)
                                   for value in column.cat.categories.tolist()]
            field['category_dtype'] = str(column.cat.categories.dtype)
            field['ordered'] = column.cat.ordered
    if output_format == 'csv':
        return {**write_csv(path, fields, frame), 'format': output_format, 'schema': schema}
    import pyarrow as pa
    table = pa.Table.from_pandas(frame, preserve_index=False)
    for field, native in zip(schema, table.schema):
        field.update(type=str(native.type), nullable=native.nullable)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='wb', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            if output_format == 'parquet':
                import pyarrow.parquet as pq
                pq.write_table(table, stream, version='2.6')
            else:
                import pyarrow.feather as feather
                feather.write_feather(table, stream, version=2)
        with temporary.open('rb') as stream:
            sha256 = hashlib.file_digest(stream, 'sha256').hexdigest()
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {'path': path.name, 'sha256': sha256, 'rows': len(frame), 'fields': fields,
            'format': output_format, 'schema': schema}


def numeric(value):
    if value is None or value in MISSING_VALUES:
        return None
    require(not isinstance(value, bool), 'Observation must be numeric or missing')
    result = float(value)
    require(math.isfinite(result), 'Observation must be finite')
    return result


def census_acs_metadata(year, directory):
    """Select a published ACS five-year release without changing a pinned year."""
    require(year == 'latest' or type(year) is int, 'Census year must be an integer or latest')
    url = 'https://api.census.gov/data.json'
    payload, response = sources.get_json(url, Path(directory) / 'original', 'census-datasets.json')
    require(isinstance(payload, dict) and isinstance(payload.get('dataset'), list), 'Census dataset catalogue is missing')
    releases = [item for item in payload['dataset'] if item.get('c_dataset') == ['acs', 'acs5']
                and item.get('c_isAvailable') is True and type(item.get('c_vintage')) is int]
    require(releases, 'Census catalogue contains no published ACS five-year release')
    selected_year = max(item['c_vintage'] for item in releases) if year == 'latest' else year
    selected = [item for item in releases if item['c_vintage'] == selected_year]
    require(len(selected) == 1, f'Census catalogue does not identify one ACS five-year release for {selected_year}')
    dataset = selected[0]
    variables = dataset.get('c_variablesLink', '').replace('http://', 'https://', 1)
    require(variables == f'https://api.census.gov/data/{selected_year}/acs/acs5/variables.json',
            'Census ACS variable metadata does not match the selected release')
    return {'year': selected_year, 'selection': 'latest-published' if year == 'latest' else 'explicit',
            'period': {'start': selected_year - 4, 'end': selected_year},
            'metadata': url, 'dataset': dataset, 'variables_url': variables}, response


def census_directory_links(url, directory, name):
    """Read file identities published in the official Population Estimates index."""
    raw, response = sources.retrieve(url, Path(directory) / 'original', name)
    parser = sources.DiscoveryHTML()
    parser.feed(raw.decode('utf-8'))
    parser.close()
    links = {urljoin(url, item['href']) for item in parser.links}
    return sorted(link for link in links if link.startswith(url) and link != url), response


def census_population_source(year, directory):
    """Resolve a state population CSV from published vintage and file listings."""
    require(year == 'latest' or type(year) is int, 'Census year must be an integer or latest')
    index = 'https://www2.census.gov/programs-surveys/popest/datasets/'
    links, response = census_directory_links(index, directory, 'census-population-vintages.html')
    responses = [response]
    releases = []
    for url in links:
        match = re.fullmatch(r'(\d{4})-(\d{4})/', url[len(index):])
        if match and int(match[1]) <= int(match[2]) and (year == 'latest' or int(match[2]) == year):
            releases.append((int(match[2]), int(match[1]), url))
    require(releases, f'Census Population Estimates index has no published vintage for {year}')
    for vintage, start, url in sorted(releases, reverse=True):
        # Follow published directories so an incomplete new vintage cannot displace a released file.
        for suffix in ('state/', 'totals/'):
            links, response = census_directory_links(url, directory, f'census-population-{vintage}-{suffix[:-1]}.html')
            responses.append(response)
            target = url + suffix
            if target not in links:
                break
            url = target
        else:
            links, response = census_directory_links(url, directory, f'census-population-{vintage}-files.html')
            responses.append(response)
            files = [link for link in links if re.fullmatch(f'NST-EST{vintage}-ALLDATA\\.csv',
                     urlsplit(link).path.rsplit('/', 1)[-1], re.IGNORECASE)]
            require(len(files) <= 1, f'Census published multiple state population files for vintage {vintage}')
            if files:
                return {'vintage': vintage, 'selection': 'latest-published' if year == 'latest' else 'explicit',
                        'published_period': {'start': start, 'end': vintage},
                        'metadata': index, 'file_listing': url, 'source_url': files[0]}, responses
    raise ValueError(f'Census Population Estimates index has no state totals CSV for {year}')


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
        geography = spec['geography']
        require(spec['unit'] == 'persons', 'Census population estimates are persons')
        require(isinstance(geography, str) and re.fullmatch(r'state:(?:\*|[0-9]{2}(?:,[0-9]{2})*)', geography),
                'Population Estimates require state FIPS codes')
        begin, end = int(spec['start']), int(spec['end'])
        require(1 <= begin <= end <= 9999, 'Population Estimates require ordered calendar years')
        requested = geography.split(':',1)[1].split(',')
        require(requested == ['*'] or len(set(requested)) == len(requested), 'Repeated state FIPS')
        release, responses = census_population_source(spec.get('year', 'latest'), directory)
        raw, response = sources.retrieve(release['source_url'], directory/'original','census-population.csv')
        responses.append(response)
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
        require(set(['SUMLEV','STATE','NAME']+[f'POPESTIMATE{y}' for y in range(begin,end+1)]) <= set(reader.fieldnames or []), 'Census population columns missing')
        available_years = sorted(int(field.removeprefix('POPESTIMATE')) for field in reader.fieldnames
                                 if re.fullmatch(r'POPESTIMATE\d{4}', field))
        matched = set()
        for row in reader:
            if row['SUMLEV'] != '040' or (requested != ['*'] and row['STATE'] not in requested): continue
            matched.add(row['STATE'])
            for y in range(begin,end+1):
                observations.append({'entity':row['STATE'],'period':str(y),'value':numeric(row[f'POPESTIMATE{y}']),
                    'status':'','unit':spec['unit'],'name':row['NAME']})
        require(requested == ['*'] or set(requested) == matched, 'Census omitted requested state FIPS')
        definitions = {'series':'POPESTIMATE', **release, 'geography':'state FIPS',
            'period': {'start': begin, 'end': end}, 'available_years': available_years,
            'source_fields': {str(y): f'POPESTIMATE{y}' for y in range(begin, end + 1)},
            'measurement': 'July 1 resident population estimate'}
        conditions = 'https://www.census.gov/about/policies/open-gov/open-data.html'
    else:
        series, geography = spec['series'], spec['geography']
        require(isinstance(series, str) and re.fullmatch(r'[A-Z0-9_]+', series), 'Invalid Census variable')
        require(isinstance(geography, str) and re.fullmatch(r'[a-z ]+:(?:\*|[0-9,]+)', geography), 'Census geography must name an official geography and codes')
        release, response = census_acs_metadata(spec.get('year', 'latest'), directory)
        responses.append(response)
        year = release['year']
        metadata_url = release['variables_url'].removesuffix('.json') + '/' + series + '.json'
        variable, response = sources.get_json(metadata_url, directory / 'original', 'census-variable.json')
        responses.append(response)
        require(isinstance(variable, dict) and variable.get('name') == series, 'Census variable metadata does not match the requested series')
        url = f'https://api.census.gov/data/{year}/acs/acs5?' + urlencode({'get': 'NAME,' + series, 'for': geography})
        key = os.environ.get('CENSUS_API_KEY', '').strip()
        payload, response = (sources.get_json(url, directory / 'original', 'census.json', census_api_key=key)
                             if key else sources.get_json(url, directory / 'original', 'census.json'))
        responses.append(response)
        require(isinstance(payload, list) and len(payload) >= 2 and payload[0][:2] == ['NAME', series], 'Census returned an unexpected variable schema')
        keys = payload[0][2:]
        for values in payload[1:]:
            require(len(values) == len(payload[0]), 'Census row width differs')
            sentinel = values[1] in {'-222222222','-333333333','-555555555','-666666666','-777777777','-888888888','-999999999'}
            observations.append({'entity': '|'.join(values[2:]), 'period': str(year), 'value': None if sentinel else numeric(values[1]), 'status': 'census_sentinel:'+values[1] if sentinel else '', 'unit': spec['unit'], 'name': values[0], **{'geo_' + k: v for k, v in zip(keys, values[2:])}})
        definitions = {**release, 'variable': series, 'variable_metadata': variable,
                       'variable_metadata_url': metadata_url, 'source_url': url, 'geography_keys': keys}
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


def load_table(root, ref, *, columns=None):
    """Retain the text-row interface used by the existing descriptive consumer."""
    frame = load_frame(root, ref, columns=columns).astype('string').fillna('')
    return list(frame.columns), frame.to_dict('records')


def load_frame(root, ref, *, columns=None):
    """Validate a source snapshot without materializing its bytes or row dictionaries."""
    require(isinstance(ref, dict) and set(ref) == {'path', 'sha256'}, 'Table reference requires path and hash')
    path = (Path(root) / ref['path']).resolve()
    with path.open('rb') as stream:
        require(hashlib.file_digest(stream, 'sha256').hexdigest() == ref['sha256'], 'Table input hash differs: ' + str(path))
    frame = read_frame(path, columns=columns, string_columns=True if path.suffix.lower() == '.csv' else None)
    require(len(frame) > 0 and frame.columns.is_unique, 'Table is empty or malformed')
    return frame


def sql_frame(root, specification):
    """Reduce hashed source scans in DuckDB before collecting the analysis table."""
    import duckdb
    import pyarrow.dataset as ds
    require(isinstance(specification, dict) and {'query', 'tables'} <= set(specification)
            <= {'query', 'tables', 'joins'}, 'sql requires query, tables and declared joins')
    tables = specification['tables']
    require(isinstance(tables, dict) and tables and all(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name)
            for name in tables), 'SQL source aliases must be distinct identifiers')
    require(len({name.lower() for name in tables}) == len(tables),
            'SQL source aliases must be distinct under DuckDB identifier matching')
    paths = {}
    for name, reference in tables.items():
        require(isinstance(reference, dict) and set(reference) == {'path', 'sha256'}, 'SQL tables require path and hash')
        path = (Path(root) / reference['path']).resolve()
        with path.open('rb') as stream:
            require(hashlib.file_digest(stream, 'sha256').hexdigest() == reference['sha256'],
                    'SQL input hash differs: ' + str(path))
        require(path.suffix.lower() in ('.csv', '.parquet', '.arrow', '.feather', '.ipc'),
                'SQL inputs must be CSV, Parquet or Arrow IPC')
        paths[name] = path

    def identifier(name):
        return '"' + name.replace('"', '""') + '"'

    with duckdb.connect(config={'autoinstall_known_extensions': False,
                                'autoload_known_extensions': False}) as connection:
        connection.execute('LOAD json')
        connection.execute('SET allowed_paths = ?', [[str(path) for path in paths.values()]])
        connection.execute('SET enable_external_access = false')
        query = specification['query']
        require(isinstance(query, str) and query.strip(), 'SQL query must be nonempty')
        statements = connection.extract_statements(query)
        require(len(statements) == 1 and statements[0].type == duckdb.StatementType.SELECT,
                'SQL assembly accepts exactly one SELECT statement')
        declared_names = {name.lower(): name for name in tables}
        source_tables = {}
        for name, path in paths.items():
            if path.suffix.lower() == '.csv':
                fields = csv_header(path)
                connection.read_csv(str(path), header=True, all_varchar=True,
                                    force_not_null=fields).create_view(name)
            else:
                source = ds.dataset(str(path), format='parquet' if path.suffix.lower() == '.parquet' else 'ipc')
                fields = source.schema.names
                connection.register(name, source)
            require(len({field.lower() for field in fields}) == len(fields),
                    'SQL source columns must be distinct under identifier matching: ' + name)
            relation = connection.table(name)
            source_tables[name] = {'reference': tables[name], 'fields': relation.columns,
                                  'types': [str(value) for value in relation.types]}
        joins = specification.get('joins', [])
        require(isinstance(joins, list), 'sql.joins must be a list')
        for join in joins:
            require(isinstance(join, dict) and {'left_table', 'right_table', 'left', 'right', 'cardinality', 'unmatched'} <= set(join)
                    <= {'left_table', 'right_table', 'left', 'right', 'cardinality', 'unmatched', 'join_type'},
                    'SQL joins declare table aliases, keys, cardinality and unmatched treatment')
            left_name, right_name = join['left_table'], join['right_table']
            require(left_name in tables and right_name in tables and left_name != right_name,
                    'SQL joins must name distinct declared source aliases')
            for side, name in (('left', left_name), ('right', right_name)):
                keys = join[side]
                require(isinstance(keys, list) and keys and all(isinstance(key, str) for key in keys)
                        and len(keys) == len(set(keys)) and set(keys) <= set(source_tables[name]['fields']),
                        'SQL join keys must be distinct source fields')
            require(len(join['left']) == len(join['right']), 'SQL join key counts differ')
            require(join['cardinality'] in ('one_to_one', 'many_to_one') and join['unmatched'] in ('error', 'keep'),
                    'SQL join requires one_to_one or many_to_one and error or keep')
            require('join_type' not in join or join['join_type'] in ('LEFT', 'INNER'),
                    'SQL join_type must be LEFT or INNER')
            for left, right in zip(join['left'], join['right']):
                left_type = source_tables[left_name]['types'][source_tables[left_name]['fields'].index(left)]
                right_type = source_tables[right_name]['types'][source_tables[right_name]['fields'].index(right)]
                require(left_type == right_type,
                        'SQL join key types differ; normalize the declared source keys before joining')

        # Inspect DuckDB's own parsed query, so the checked keys are the executed keys.
        parsed = json.loads(connection.execute('SELECT json_serialize_sql(?)', [query]).fetchall()[0][0])
        require(not parsed.get('error') and len(parsed.get('statements', [])) == 1,
                'DuckDB could not serialize the adopted SQL query')
        remaining = set(range(len(joins)))
        used = set()
        executed_joins = {}
        join_inputs = {}
        table_names = {name.lower(): name for name in tables}

        def aliases(reference):
            if reference.get('type') == 'JOIN':
                left = aliases(reference['left'])
                right = aliases(reference['right'])
                require(not set(left) & set(right), 'SQL join aliases must be distinct')
                return {**left, **right}
            require(reference.get('type') == 'BASE_TABLE'
                    and reference.get('table_name', '').lower() in table_names
                    and not reference.get('column_name_alias') and not reference.get('sample'),
                    'Join declared source tables directly; construct derived join inputs in an earlier assembly')
            name = table_names[reference['table_name'].lower()]
            return {(reference.get('alias') or name).lower(): name}

        def column(expression, scope):
            require(expression.get('class') == 'COLUMN_REF', 'SQL join keys must be direct column references')
            names = expression['column_names']
            require(len(names) in (1, 2), 'SQL join keys must use a column or table-qualified column')
            candidates = [name for alias, name in scope.items()
                          if (len(names) == 1 or alias == names[0].lower())
                          and names[-1].lower() in {field.lower() for field in source_tables[name]['fields']}]
            require(len(candidates) == 1, 'SQL join key must identify one declared source column')
            name = candidates[0]
            field = next(field for field in source_tables[name]['fields'] if field.lower() == names[-1].lower())
            return name, field

        def equalities(expression):
            require(isinstance(expression, dict), 'SQL join needs its declared equality condition')
            if expression.get('type') == 'CONJUNCTION_AND':
                return [pair for child in expression['children'] for pair in equalities(child)]
            require(expression.get('type') == 'COMPARE_EQUAL', 'SQL join must use exactly the declared key equalities')
            return [(expression['left'], expression['right'])]

        def join_keys(value):
            require(value.get('ref_type') == 'REGULAR' and value.get('join_type') in ('LEFT', 'INNER'),
                    'SQL joins must preserve the declared left population with LEFT or matched INNER joins')
            left_scope, right_scope = aliases(value['left']), aliases(value['right'])
            require(value['right'].get('type') == 'BASE_TABLE' and not set(left_scope) & set(right_scope)
                    and not set(left_scope.values()) & set(right_scope.values()),
                    'SQL lookup joins require a distinct declared right source table')
            using = value.get('using_columns', [])
            if using:
                require(len(left_scope) == 1 and not value.get('condition'),
                        'Use qualified ON keys for a SQL join chain')
                pairs = [(column({'class': 'COLUMN_REF', 'column_names': [key]}, left_scope),
                          column({'class': 'COLUMN_REF', 'column_names': [key]}, right_scope)) for key in using]
            else:
                scope = {**left_scope, **right_scope}
                pairs = []
                for first, second in equalities(value.get('condition')):
                    a, b = column(first, scope), column(second, scope)
                    if a[0] in right_scope.values() and b[0] in left_scope.values():
                        a, b = b, a
                    require(a[0] in left_scope.values() and b[0] in right_scope.values(),
                            'SQL equality must connect its declared left and right sources')
                    pairs.append((a, b))
            return left_scope, right_scope, pairs

        def qualified(key, scope):
            alias = next(alias for alias, name in scope.items() if name == key[0])
            return identifier(alias) + '.' + identifier(key[1])

        def source_sql(reference):
            if reference.get('type') == 'BASE_TABLE':
                alias, name = next(iter(aliases(reference).items()))
                return identifier(name) + ' AS ' + identifier(alias)
            left_scope, right_scope, pairs = join_keys(reference)
            condition = ' AND '.join(qualified(a, left_scope) + ' = ' + qualified(b, right_scope) for a, b in pairs)
            return (source_sql(reference['left']) + ' ' + reference['join_type'] + ' JOIN '
                    + source_sql(reference['right']) + ' ON ' + condition)

        def inspect(value, ctes=frozenset()):
            if isinstance(value, list):
                for child in value:
                    inspect(child, ctes)
                return
            if not isinstance(value, dict):
                return
            local_ctes = {entry['key'].lower() for entry in value.get('cte_map', {}).get('map', [])}
            require(not local_ctes & set(declared_names), 'SQL CTE names must not shadow declared source aliases')
            ctes = ctes | local_ctes
            if value.get('type') == 'BASE_TABLE':
                name = value['table_name'].lower()
                require(name in declared_names or name in ctes,
                        'SQL query must use exactly its declared source aliases')
                if name not in ctes:
                    used.add(declared_names[name])
            if value.get('type') == 'JOIN':
                left_scope, right_scope, pairs = join_keys(value)
                matches = [index for index in remaining if len(pairs) == len(joins[index]['left'])
                           and set(pairs) == {((joins[index]['left_table'], a), (joins[index]['right_table'], b))
                                             for a, b in zip(joins[index]['left'], joins[index]['right'])}]
                require(len(matches) == 1, 'Executed SQL join differs from its declared keys or multiplicity')
                index = matches[0]
                require(joins[index].get('join_type', value['join_type']) == value['join_type'],
                        'Executed SQL join type differs from its declaration')
                require(joins[index]['unmatched'] != 'keep' or value['join_type'] == 'LEFT',
                        'SQL unmatched=keep requires a LEFT JOIN')
                remaining.remove(index)
                executed_joins[index] = value['join_type']
                join_inputs[index] = (source_sql(value['left']), left_scope,
                                      source_sql(value['right']), right_scope)
            for child in value.values():
                inspect(child, ctes)

        inspect(parsed['statements'][0])
        require(used == set(tables), 'SQL query must use exactly its declared source aliases')
        require(not remaining, 'SQL join declarations must each match one executed join')
        joined = set()
        join_records = []
        for index, join in enumerate(joins):
            left_name, right_name = join['left_table'], join['right_table']
            left, right = join['left'], join['right']
            left_sql, left_scope, right_sql, right_scope = join_inputs[index]
            for name, keys, unique, table_sql, scope in (
                    (left_name, left, join['cardinality'] == 'one_to_one', left_sql, left_scope),
                    (right_name, right, True, right_sql, right_scope)):
                columns = [qualified((name, key), scope) for key in keys]
                missing = ' OR '.join(key + " IS NULL OR CAST(" + key + " AS VARCHAR) = ''" for key in columns)
                require(connection.sql('SELECT count(*) FROM ' + table_sql + ' WHERE ' + missing).fetchall()[0][0] == 0,
                        'SQL join keys must be complete: ' + name)
                if unique:
                    grouped = ', '.join(columns)
                    duplicates = connection.sql('SELECT count(*) FROM (SELECT ' + grouped + ' FROM ' + table_sql
                                                + ' GROUP BY ' + grouped + ' HAVING count(*) > 1)').fetchall()[0][0]
                    require(duplicates == 0, 'SQL join keys must be unique: ' + name)
            condition = ' AND '.join(qualified((left_name, a), left_scope) + ' = '
                                     + qualified((right_name, b), right_scope) for a, b in zip(left, right))
            unmatched = connection.sql('SELECT count(*) FROM ' + left_sql
                + ' WHERE NOT EXISTS (SELECT 1 FROM ' + right_sql + ' WHERE ' + condition + ')').fetchall()[0][0]
            require(join['unmatched'] == 'keep' or unmatched == 0, 'SQL join has unmatched left keys: ' + left_name)
            joined.update((left_name, right_name))
            join_records.append({**join, 'join_type': executed_joins[index], 'unmatched_rows': unmatched})
        require(len(used) == 1 or joined == used, 'Every joined SQL source requires its key/cardinality declaration')
        for name in tables:
            source_tables[name]['rows'] = connection.sql('SELECT count(*) FROM ' + identifier(name)).fetchall()[0][0]
        relation = connection.sql(query)
        require(len(relation.columns) == len(set(relation.columns)), 'SQL output columns must be distinct')
        table = relation.to_arrow_table()
        require(table.num_rows > 0, 'SQL construction returned no rows')
        frame = table.to_pandas(integer_object_nulls=True)
    execution = {'operation': {'op': 'sql', **specification}, 'source_tables': source_tables,
                 'rows_after': len(frame), 'output_columns': list(frame.columns), 'joins': join_records,
                 'source_dependencies': list(tables.values()), 'engine': {'name': 'duckdb', 'version': duckdb.__version__}}
    return frame, list(tables.values()), execution


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


def construction_mask(frame, rule):
    """Evaluate a declared column comparison without executing expressions."""
    require(isinstance(rule, dict) and set(rule) <= {'column', 'op', 'value', 'values', 'reason'},
            'A filter needs a column and an explicit comparison')
    name = rule.get('column')
    require(name in frame.columns, 'Filter column is absent: ' + str(name))
    values = frame[name]
    missing = values.isna() | values.eq('')
    op = rule.get('op', 'in' if 'values' in rule else None)
    if op == 'missing':
        return missing
    if op == 'nonmissing':
        return ~missing
    if op in ('in', 'not_in'):
        require(isinstance(rule.get('values'), list), 'Membership filters require values')
        selected = values.isin(rule['values'])
        return ~missing & (~selected if op == 'not_in' else selected)
    require(op in ('eq', 'ne', 'lt', 'le', 'gt', 'ge') and 'value' in rule,
            'Filter op must be eq/ne/lt/le/gt/ge/in/not_in/missing/nonmissing')
    return ~missing & getattr(values, op)(rule['value'])


def construction_columns(frame, names, *, empty=False):
    require(isinstance(names, list) and (empty or names) and len(set(names)) == len(names)
            and all(isinstance(name, str) and name in frame.columns for name in names),
            'Declare distinct existing input columns')
    return names


def construction_numeric(frame, name):
    import pandas as pd
    require(name in frame.columns, 'Numeric input column is absent: ' + str(name))
    return frame[name].map(lambda value: None if pd.isna(value) else numeric(value)).astype(float)


def calendar_label(value):
    """Preserve integer year labels after an explicitly requested numeric conversion."""
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value == int(value):
        return str(int(value))
    return str(value)


def construction_clock(frame, step):
    """Give every observed entity-period cell its calendar position."""
    import pandas as pd
    by = construction_columns(frame, step.get('by', []), empty=True)
    time = step.get('time')
    require(time in frame.columns and isinstance(step.get('frequency'), str),
            'Calendar operations require time and frequency')
    require(not frame[by + [time]].isna().any().any()
            and not frame[by + [time]].eq('').any().any(), 'Calendar keys must be complete')
    periods = pd.PeriodIndex(frame[time].map(calendar_label), freq=step['frequency'])
    require(periods.freq.n == 1, 'Use a base calendar frequency; set periods/window for multiples')
    groups = list(frame[by].itertuples(index=False, name=None)) if by else [()] * len(frame)
    keys = [(group, period.ordinal) for group, period in zip(groups, periods)]
    require(len(set(keys)) == len(keys), 'Calendar operations require unique entity-period keys')
    return groups, periods, keys


def transform_table(fields, rows, transformations, definitions, column_sources):
    """Apply the adopted operations in order and retain their actual dependencies."""
    import pandas as pd
    require(isinstance(transformations, list), 'transformations must be a list')
    frame = pd.DataFrame(rows, columns=fields)
    records, known_fields = [], set(fields)
    for index, step in enumerate(transformations, 1):
        require(isinstance(step, dict) and isinstance(step.get('op'), str), 'Each transformation needs op')
        op = step['op']
        before = len(frame)
        inputs, outputs, detail = [], [], {}
        clock = None
        common = {'op', 'id', 'replace', 'on_invalid'}
        options = {
            'date': {'input', 'output', 'format', 'output_format', 'timezone'},
            'period': {'input', 'output', 'frequency'},
            'string': {'input', 'output', 'strip', 'case', 'unicode', 'width', 'pad'},
            'category': {'input', 'output', 'mapping', 'unknown', 'breaks', 'labels', 'right', 'include_lowest'},
            'indicator': {'input', 'output', 'values'},
            'arithmetic': {'inputs', 'output', 'function'},
            'ratio': {'numerator', 'denominator', 'output', 'scale'},
            'log': {'input', 'output'}, 'log1p': {'input', 'output'}, 'exp': {'input', 'output'}, 'ihs': {'input', 'output'},
            'polynomial': {'input', 'output', 'power'},
            'interaction': {'inputs', 'output'},
            'standardize': {'input', 'output', 'by', 'reference', 'ddof'},
            'lag': {'input', 'output', 'by', 'time', 'frequency', 'periods'},
            'lead': {'input', 'output', 'by', 'time', 'frequency', 'periods'},
            'diff': {'input', 'output', 'by', 'time', 'frequency', 'periods'},
            'growth': {'input', 'output', 'by', 'time', 'frequency', 'periods', 'scale'},
            'cumulative': {'input', 'output', 'by', 'time', 'frequency', 'stat', 'missing', 'start'},
            'rolling': {'input', 'output', 'by', 'time', 'frequency', 'stat', 'missing', 'window', 'min_periods'},
            'baseline': {'input', 'output', 'by', 'time', 'frequency', 'period', 'mode', 'scale'},
            'duplicates': {'keys', 'policy', 'order_by', 'keep'},
            'aggregate': {'by', 'metrics'},
            'wide_to_long': {'id', 'columns', 'names_to', 'values_to'},
            'long_to_wide': {'id', 'names_from', 'values_from', 'columns'},
            'index': {'inputs', 'output', 'weights', 'missing', 'normalize'},
            'real': {'input', 'deflator', 'base', 'output'},
            'treatment': {'input', 'by', 'time', 'frequency', 'active_values', 'outputs', 'anticipation', 'history', 'initial_state', 'history_start', 'history_end'},
            'exposure': {'input', 'weight', 'output', 'by', 'time', 'frequency', 'window', 'missing'},
            'row_id': {'columns', 'output'},
        }
        require(op in options and not set(step) - common - options[op], 'Unsupported transformation or option: ' + op)
        require(type(step.get('replace', False)) is bool, 'replace must be Boolean')
        invalid = step.get('on_invalid', 'error')
        require(invalid in ('error', 'missing'), 'on_invalid must be error or missing')

        def put(name, values):
            require(isinstance(name, str) and name and (name not in frame.columns or step.get('replace', False)),
                    'Output already exists; declare replace: true: ' + str(name))
            frame[name] = pd.Series(values, index=frame.index)
            outputs.append(name)

        def domain(values, valid, name):
            bad = values.notna() & ~valid
            require(not bad.any() or invalid == 'missing', name + ' outside declared domain at rows ' + str(frame.index[bad].tolist()))
            return values.mask(bad)

        if op in ('date', 'period', 'string', 'category', 'indicator'):
            inputs = construction_columns(frame, [step.get('input')])
            values = frame[inputs[0]].astype('string').replace('', pd.NA)
            if op == 'date':
                require(isinstance(step.get('format'), str), 'date requires the source format')
                dates = pd.to_datetime(values, format=step['format'], errors='raise')
                if step.get('timezone'):
                    dates = (dates.dt.tz_localize(step['timezone'], ambiguous='raise', nonexistent='raise')
                             if dates.dt.tz is None else dates.dt.tz_convert(step['timezone']))
                values = dates.dt.strftime(step.get('output_format', '%Y-%m-%d'))
                clock = {key: step[key] for key in ('format', 'timezone') if key in step}
            elif op == 'period':
                require(isinstance(step.get('frequency'), str), 'period requires frequency')
                values = frame[inputs[0]].map(lambda value: pd.NA if pd.isna(value) or value == ''
                    else str(pd.Period(calendar_label(value), freq=step['frequency'])))
                clock = {'frequency': step['frequency']}
            elif op == 'string':
                if step.get('unicode'):
                    require(step['unicode'] in ('NFC', 'NFD', 'NFKC', 'NFKD'), 'Unknown Unicode normalization')
                    values = values.map(lambda value: pd.NA if pd.isna(value) else unicodedata.normalize(step['unicode'], value)).astype('string')
                if step.get('strip', False):
                    values = values.str.strip().replace('', pd.NA)
                case = step.get('case')
                require(case in (None, 'lower', 'upper', 'casefold'), 'String case must be lower/upper/casefold')
                if case:
                    values = getattr(values.str, case)()
                if 'width' in step:
                    require(type(step['width']) is int and step['width'] > 0 and len(step.get('pad', '0')) == 1,
                            'Code padding needs positive width and one pad character')
                    values = values.str.pad(step['width'], side='left', fillchar=step.get('pad', '0'))
                pairs = pd.DataFrame({'original': frame[inputs[0]], 'normalized': values}).dropna()
                detail['merged_labels'] = {str(key): list(group['original'].unique())
                                           for key, group in pairs.groupby('normalized', sort=False)
                                           if group['original'].nunique() > 1}
            elif op == 'category':
                require(('mapping' in step) != ('breaks' in step), 'category requires mapping or breaks')
                if 'mapping' in step:
                    mapping = step['mapping']
                    require(isinstance(mapping, dict) and mapping, 'category mapping must be a nonempty object')
                    unknown = values.notna() & ~values.isin(mapping)
                    policy = step.get('unknown', 'error')
                    require(policy in ('error', 'missing', 'keep'), 'Unknown category policy')
                    require(not unknown.any() or policy != 'error', 'Unmapped category values: ' + str(values[unknown].unique().tolist()))
                    mapped = values.map(mapping)
                    values = mapped.where(~unknown, values) if policy == 'keep' else mapped
                else:
                    require(isinstance(step.get('labels'), list), 'Category bins require labels')
                    source = construction_numeric(frame, inputs[0])
                    values = pd.cut(source, bins=step['breaks'], labels=step['labels'],
                                    right=step.get('right', True), include_lowest=step.get('include_lowest', False)).astype(object)
                    require(not (source.notna() & values.isna()).any() or invalid == 'missing', 'Category value lies outside declared bins')
            else:
                require(isinstance(step.get('values'), list), 'indicator requires values')
                values = frame[inputs[0]].isin(step['values']).astype(float).mask(values.isna())
            put(step.get('output'), values)
        elif op in ('arithmetic', 'interaction', 'ratio', 'log', 'log1p', 'exp', 'ihs', 'polynomial', 'real', 'index'):
            if op in ('arithmetic', 'interaction', 'index'):
                operands = step.get('inputs')
                require(isinstance(operands, list) and operands, 'Declare input columns or numeric constants')
            elif op == 'ratio':
                operands = [step.get('numerator'), step.get('denominator')]
            elif op == 'real':
                operands = [step.get('input'), step.get('deflator')]
            else:
                operands = [step.get('input')]
            inputs = list(dict.fromkeys(value for value in operands if isinstance(value, str)))
            construction_columns(frame, inputs, empty=True)
            require(all(isinstance(value, str) or type(value) in (int, float) and math.isfinite(value) for value in operands),
                    'Arithmetic operands must be columns or finite constants')
            values = [construction_numeric(frame, value) if isinstance(value, str)
                      else pd.Series(float(value), index=frame.index) for value in operands]
            result = values[0]
            if op in ('arithmetic', 'interaction'):
                function = 'multiply' if op == 'interaction' else step.get('function')
                require(function in ('add', 'subtract', 'multiply', 'divide', 'min', 'max'), 'Unknown arithmetic function')
                for value in values[1:]:
                    if function == 'divide':
                        value = domain(value, value.ne(0), 'Division denominator')
                    if function == 'min':
                        result = pd.concat([result, value], axis=1).min(axis=1, skipna=False)
                    elif function == 'max':
                        result = pd.concat([result, value], axis=1).max(axis=1, skipna=False)
                    else:
                        result = getattr(result, {'subtract': 'sub', 'multiply': 'mul', 'divide': 'div'}.get(function, function))(value)
            elif op in ('ratio', 'real'):
                denominator = domain(values[1], values[1].gt(0) if op == 'real' else values[1].ne(0), 'Denominator')
                factor = step.get('base') if op == 'real' else step.get('scale', 1)
                require(type(factor) in (int, float) and math.isfinite(factor), 'Declare finite ratio scale or deflator base')
                result = result / denominator * factor
            elif op in ('log', 'log1p'):
                result = domain(result, result.gt(0 if op == 'log' else -1), op)
                fn = math.log if op == 'log' else math.log1p
                result = result.map(lambda value: fn(value) if pd.notna(value) else None)
            elif op == 'ihs':
                result = result.map(lambda value: math.asinh(value) if pd.notna(value) else None)
            elif op == 'exp':
                result = domain(result, result.le(math.log(sys.float_info.max)), 'Exponential representable range')
                result = result.map(lambda value: math.exp(value) if pd.notna(value) else None)
            elif op == 'polynomial':
                require(type(step.get('power')) is int and step['power'] >= 0, 'Polynomial power must be a nonnegative integer')
                result = result.pow(step['power']).mask(result.isna())
            elif op == 'index':
                weights = step.get('weights')
                require(isinstance(weights, list) and len(weights) == len(values)
                        and all(type(weight) in (int, float) and math.isfinite(weight) for weight in weights),
                        'Index requires one finite weight per input')
                missing = step.get('missing', 'propagate')
                require(missing in ('propagate', 'available') and type(step.get('normalize', False)) is bool, 'Declare index missing policy and normalization')
                matrix = pd.concat(values, axis=1)
                result = matrix.mul(weights).sum(axis=1, min_count=len(values) if missing == 'propagate' else 1)
                if step.get('normalize', False):
                    denominator = matrix.notna().mul(weights).sum(axis=1)
                    denominator = domain(denominator, denominator.ne(0), 'Index weight denominator')
                    result = result / denominator
                detail['weights'] = weights
            put(step.get('output'), result)
        elif op == 'standardize':
            inputs = construction_columns(frame, [step.get('input')] + step.get('by', []))
            by = step.get('by', [])
            ddof = step.get('ddof')
            require(ddof in (0, 1) and type(ddof) is int, 'standardize requires ddof 0 or 1')
            reference = pd.Series(True, index=frame.index)
            for rule in step.get('reference', []):
                reference &= construction_mask(frame, rule)
                if rule['column'] not in inputs:
                    inputs.append(rule['column'])
            values = construction_numeric(frame, step['input'])
            result = pd.Series(float('nan'), index=frame.index)
            detail['reference_groups'] = []
            groups = frame.groupby(by, sort=False, dropna=False).groups.items() if by else [((), frame.index)]
            for key, positions in groups:
                selected = values.loc[positions][reference.loc[positions]].dropna()
                mean, sd = selected.mean(), selected.std(ddof=ddof)
                valid = len(selected) > ddof and pd.notna(sd) and sd > 0
                require(valid or invalid == 'missing', 'Standardization reference has no positive defined scale')
                if valid:
                    result.loc[positions] = (values.loc[positions] - mean) / sd
                detail['reference_groups'].append({'group': [str(value) for value in key] if isinstance(key, tuple) else [str(key)],
                                                   'n': len(selected), 'mean': None if pd.isna(mean) else float(mean),
                                                   'sd': None if pd.isna(sd) else float(sd)})
            put(step.get('output'), result)
        elif op in ('lag', 'lead', 'diff', 'growth', 'cumulative', 'rolling', 'baseline', 'treatment', 'exposure'):
            groups, periods, keys = construction_clock(frame, step)
            time, by = step['time'], step.get('by', [])
            stride = periods.freq.n
            inputs = construction_columns(frame, list(dict.fromkeys([step.get('input'), *by, time]
                                        + ([step['weight']] if op == 'exposure' and step.get('weight') else []))))
            clock = {'time': time, 'frequency': step['frequency'], 'by': by, 'alignment': 'calendar_key'}
            values = construction_numeric(frame, step['input']) if op != 'treatment' else frame[step['input']]
            lookup = dict(zip(keys, values))
            if op in ('lag', 'lead', 'diff', 'growth'):
                horizon = step.get('periods', 1)
                require(type(horizon) is int and horizon > 0, 'Calendar horizon must be a positive integer')
                shift = stride * horizon * (1 if op == 'lead' else -1)
                previous = pd.Series([lookup.get((group, period + shift), float('nan')) for group, period in keys], index=frame.index)
                result = previous if op in ('lag', 'lead') else values - previous
                if op == 'growth':
                    require(type(step.get('scale', 1)) in (int, float) and math.isfinite(step.get('scale', 1)), 'Growth scale must be finite')
                    previous = domain(previous, previous.ne(0), 'Growth base')
                    result = (values / previous - 1) * step.get('scale', 1)
                put(step.get('output'), result)
            elif op == 'baseline':
                require('period' in step and step.get('mode', 'value') in ('value', 'difference', 'ratio', 'index'), 'Declare baseline period and mode')
                base_period = pd.Period(str(step['period']), freq=step['frequency']).ordinal
                base = pd.Series([lookup.get((group, base_period), float('nan')) for group in groups], index=frame.index)
                mode = step.get('mode', 'value')
                result = base if mode == 'value' else values - base
                if mode in ('ratio', 'index'):
                    require(type(step.get('scale', 100)) in (int, float) and math.isfinite(step.get('scale', 100)), 'Baseline scale must be finite')
                    base = domain(base, base.ne(0), 'Baseline denominator')
                    result = values / base * (step.get('scale', 100) if mode == 'index' else 1)
                clock['baseline'] = str(step['period'])
                put(step.get('output'), result)
            elif op in ('cumulative', 'rolling', 'exposure'):
                missing = step.get('missing', 'propagate')
                require(missing in ('propagate', 'available'), 'Window missing policy must be propagate or available')
                stat = step.get('stat', 'sum')
                require(stat in ('sum', 'mean', 'min', 'max'), 'Window statistic must be sum/mean/min/max')
                if op == 'exposure' and step.get('weight'):
                    values = values * construction_numeric(frame, step['weight'])
                    lookup = dict(zip(keys, values))
                window = step.get('window')
                require(op != 'rolling' or type(window) is int and window > 0, 'rolling requires a positive calendar window')
                require(window is None or type(window) is int and window > 0, 'window must be positive')
                min_periods = step.get('min_periods', window or 1)
                require(type(min_periods) is int and 1 <= min_periods <= (window or min_periods), 'Invalid min_periods')
                starts = {}
                for group, period in keys:
                    starts[group] = min(starts.get(group, period), period)
                declared_start = pd.Period(str(step['start']), freq=step['frequency']).ordinal if 'start' in step else None
                result = []
                for group, period in keys:
                    start = period - (window - 1) * stride if window else (declared_start if declared_start is not None else starts[group])
                    require(start <= period, 'Cumulative start is after an observation')
                    cells = pd.Series([lookup.get((group, target), float('nan')) for target in range(start, period + 1, stride)], dtype=float)
                    usable = cells.dropna()
                    valid = len(usable) >= min_periods and (missing == 'available' or len(usable) == len(cells))
                    result.append(float(getattr(usable, stat)()) if valid else None)
                clock['start'] = step.get('start', 'first_observed_period_per_entity') if not window else None
                put(step.get('output'), result)
            else:
                require(isinstance(step.get('active_values'), list) and step['active_values'], 'Treatment needs declared active_values')
                named = step.get('outputs')
                supported = {'active', 'first_treated', 'event_time', 'ever_observed', 'never_treated', 'not_yet_treated', 'cumulative', 'switch_on', 'switch_off', 'anticipation'}
                require(isinstance(named, dict) and named and set(named) <= supported and len(set(named.values())) == len(named), 'Declare distinct treatment output columns')
                require(step.get('history', 'propagate') in ('propagate', 'observed'), 'Treatment history must be propagate or observed')
                anticipation = step.get('anticipation', 0)
                require(type(anticipation) is int and anticipation >= 0, 'Anticipation periods must be nonnegative')
                initial = step.get('initial_state')
                require(initial in (None, 0, 1), 'initial_state must be 0 or 1 when declared')
                active = values.isin(step['active_values']).astype(float).mask(values.isna() | values.eq(''))
                active_lookup = dict(zip(keys, active))
                first, starts, ends = {}, {}, {}
                for (group, period), value in zip(keys, active):
                    starts[group] = min(starts.get(group, period), period)
                    ends[group] = max(ends.get(group, period), period)
                    if value == 1:
                        first[group] = min(first.get(group, period), period)
                ever_observed = set(first)
                if 'history_start' in step:
                    start = pd.Period(str(step['history_start']), freq=step['frequency']).ordinal
                    require(all(start <= value for value in starts.values()), 'history_start follows an input observation')
                    starts = {group: start for group in starts}
                if 'history_end' in step:
                    end = pd.Period(str(step['history_end']), freq=step['frequency']).ordinal
                    require(all(end >= value for value in ends.values()), 'history_end precedes an input observation')
                    ends = {group: end for group in ends}
                never = {}
                for group in starts:
                    history = [active_lookup.get((group, target), float('nan')) for target in range(starts[group], ends[group] + 1, stride)]
                    never[group] = int(not any(value == 1 for value in history)) if all(pd.notna(value) for value in history) else None
                clock['history_bounds'] = [{'group': [str(value) for value in group],
                    'start': str(pd.Period(ordinal=starts[group], freq=step['frequency'])),
                    'end': str(pd.Period(ordinal=ends[group], freq=step['frequency']))} for group in starts]
                if step.get('history', 'propagate') == 'propagate':
                    first = {group: onset for group, onset in first.items()
                             if (onset != starts[group] or initial == 0)
                             and all(pd.notna(active_lookup.get((group, target), float('nan')))
                                     for target in range(starts[group], onset + 1, stride))}
                derived = {name: [] for name in named}
                for position, (group, period) in enumerate(keys):
                    onset = first.get(group)
                    past = [active_lookup.get((group, target), float('nan')) for target in range(starts[group], period + 1, stride)]
                    complete = all(pd.notna(value) for value in past)
                    previous = active_lookup.get((group, period - stride), initial if period == starts[group] else float('nan'))
                    now = active.iloc[position]
                    event_time = (period - onset) // stride if onset is not None else None
                    row = {'active': now, 'first_treated': str(pd.Period(ordinal=onset, freq=step['frequency'])) if onset is not None else None,
                           'event_time': event_time, 'ever_observed': int(group in ever_observed),
                           'never_treated': never[group],
                           'not_yet_treated': int(period < onset) if onset is not None else (int(not any(value == 1 for value in past)) if complete else None),
                           'cumulative': sum(value for value in past if pd.notna(value)) if complete or step.get('history') == 'observed' else None,
                           'switch_on': int(previous == 0 and now == 1) if pd.notna(previous) and pd.notna(now) else None,
                           'switch_off': int(previous == 1 and now == 0) if pd.notna(previous) and pd.notna(now) else None,
                           'anticipation': int(-anticipation <= event_time < 0) if event_time is not None else None}
                    for name in named:
                        derived[name].append(row[name])
                detail['history_scope'] = 'observed input coverage'
                detail['adoption_clock'] = ('first observed active period' if step.get('history') == 'observed'
                                            else 'first active period with complete observed prior history; initial_state=0 for adoption at coverage start')
                for name, output in named.items():
                    put(output, derived[name])
        elif op == 'duplicates':
            inputs = construction_columns(frame, step.get('keys'))
            policy = step.get('policy')
            require(policy in ('error', 'identical', 'select'), 'duplicates policy must be error/identical/select')
            repeated = frame.duplicated(inputs, keep=False)
            detail['duplicate_rows'] = int(repeated.sum())
            require(policy != 'error' or not repeated.any(), 'Duplicate keys under the error policy')
            if policy == 'identical':
                for _, group in frame.loc[repeated].groupby(inputs, sort=False, dropna=False):
                    require(len(group.drop_duplicates()) == 1, 'Conflicting rows cannot be removed as identical ingestion')
                frame = frame.drop_duplicates().reset_index(drop=True)
            elif policy == 'select':
                order = construction_columns(frame, step.get('order_by'))
                require(not frame[inputs + order].isna().any().any() and not frame[inputs + order].eq('').any().any()
                        and step.get('keep') in ('first', 'last') and not frame.duplicated(inputs + order).any(),
                        'Version selection needs first/last and untied explicit order keys')
                frame = frame.sort_values(order, kind='stable').drop_duplicates(inputs, keep=step['keep']).reset_index(drop=True)
                inputs = list(dict.fromkeys(inputs + order))
            detail['grain_change'] = True
        elif op == 'aggregate':
            by = construction_columns(frame, step.get('by', []), empty=True)
            metrics = step.get('metrics')
            require(isinstance(metrics, dict) and metrics and not set(metrics) & set(by), 'aggregate requires named metrics')
            declared_outputs = list(metrics)
            for metric in metrics.values():
                require(isinstance(metric, dict), 'Aggregate metrics must be objects')
                if metric.get('stat') in ('weighted_mean', 'rate'):
                    declared_outputs.extend([metric.get('numerator_output'), metric.get('denominator_output')])
            require(all(isinstance(name, str) and name for name in declared_outputs)
                    and len(declared_outputs) == len(set(declared_outputs)) and not set(declared_outputs) & set(by),
                    'All aggregate outputs must be distinct from grouping keys and other outputs')
            result_rows, inputs = [], list(by)
            grouped = frame.groupby(by, sort=False, dropna=False) if by else [((), frame)]
            detail['support'] = []
            for key, group in grouped:
                key = key if isinstance(key, tuple) else (key,)
                row = dict(zip(by, key))
                for output, metric in metrics.items():
                    require(isinstance(metric, dict) and set(metric) <= {'stat', 'input', 'weight', 'numerator', 'denominator', 'missing', 'numerator_output', 'denominator_output', 'scale'}, 'Unknown aggregate metric fields')
                    stat, missing = metric.get('stat'), metric.get('missing', 'propagate')
                    require(stat in ('sum', 'mean', 'min', 'max', 'count', 'rows', 'weighted_mean', 'rate') and missing in ('propagate', 'complete'), 'Declare aggregate statistic and missing policy')
                    if stat == 'rows':
                        row[output] = len(group)
                        continue
                    names = [metric.get('numerator'), metric.get('denominator')] if stat == 'rate' else [metric.get('input')]
                    if stat == 'weighted_mean':
                        names.append(metric.get('weight'))
                    construction_columns(frame, names)
                    inputs.extend(name for name in names if name not in inputs)
                    if stat == 'count':
                        values = group[names[0]]
                        usable = values.notna() & ~values.isin(MISSING_VALUES)
                    else:
                        series = [construction_numeric(group, name) for name in names]
                        usable = pd.concat(series, axis=1).notna().all(axis=1)
                    valid = bool(usable.any()) and (missing == 'complete' or bool(usable.all()))
                    if stat in ('rate', 'weighted_mean'):
                        numerator_output, denominator_output = metric.get('numerator_output'), metric.get('denominator_output')
                        require(isinstance(numerator_output, str) and isinstance(denominator_output, str)
                                and len({output, numerator_output, denominator_output}) == 3, 'Rate/weighted mean require distinct numerator_output and denominator_output')
                        require((series[1].dropna() >= 0).all(), 'Exposure and aggregation weights must be nonnegative')
                        require(type(metric.get('scale', 1)) in (int, float) and math.isfinite(metric.get('scale', 1)), 'Aggregate rate scale must be finite')
                        denominator = series[1][usable].sum() if valid else None
                        numerator = ((series[0] * series[1]) if stat == 'weighted_mean' else series[0])[usable].sum() if valid else None
                        row[numerator_output], row[denominator_output] = numerator, denominator
                        row[output] = numerator / denominator * metric.get('scale', 1) if valid and denominator > 0 else None
                    elif stat == 'count':
                        row[output] = int(usable.sum())
                    else:
                        row[output] = float(getattr(series[0][usable], stat)()) if valid else None
                    detail['support'].append({'group': [str(value) for value in key], 'output': output, 'source_rows': len(group), 'usable_rows': int(usable.sum())})
                result_rows.append(row)
            frame = pd.DataFrame(result_rows)
            outputs = [name for name in frame.columns if name not in by]
            detail['grain_change'] = True
        elif op == 'wide_to_long':
            identities = construction_columns(frame, step.get('id'))
            columns = step.get('columns')
            require(isinstance(columns, dict) and columns, 'wide_to_long requires a declared column mapping')
            names_to = step.get('names_to')
            require(isinstance(names_to, str) and names_to and names_to not in identities, 'Declare a distinct long dimension column')
            if all(isinstance(mapping, dict) for mapping in columns.values()):
                value_names = list(next(iter(columns.values())))
                require(value_names and all(set(mapping) == set(value_names) for mapping in columns.values())
                        and not set(value_names) & set(identities + [names_to]), 'Paired long values/statuses require the same distinct output fields in every period')
                source_names = [source for mapping in columns.values() for source in mapping.values()]
                inputs = construction_columns(frame, identities + source_names)
                pieces = []
                for label, mapping in columns.items():
                    piece = frame[identities].copy()
                    piece[names_to] = label
                    for output, source in mapping.items():
                        piece[output] = frame[source]
                    pieces.append(piece)
                frame = pd.concat(pieces, ignore_index=True)
                outputs = [names_to, *value_names]
            else:
                require(all(isinstance(label, str) for label in columns.values()) and len(set(columns.values())) == len(columns), 'Single-value long mapping needs distinct dimension labels')
                inputs = construction_columns(frame, identities + list(columns))
                values_to = step.get('values_to')
                require(isinstance(values_to, str) and values_to and values_to not in identities + [names_to], 'Declare a distinct long value column')
                frame = frame.melt(id_vars=identities, value_vars=list(columns), var_name=names_to, value_name=values_to)
                frame[names_to] = frame[names_to].map(columns)
                outputs = [names_to, values_to]
            detail['grain_change'] = True
        elif op == 'long_to_wide':
            identities = construction_columns(frame, step.get('id'))
            name, value, columns = step.get('names_from'), step.get('values_from'), step.get('columns')
            values = value if isinstance(value, list) else [value]
            inputs = construction_columns(frame, identities + [name] + values)
            require(isinstance(columns, dict) and columns, 'long_to_wide requires a declared column mapping')
            paired = all(isinstance(mapping, dict) for mapping in columns.values())
            if paired:
                require(all(set(mapping) == set(values) for mapping in columns.values()), 'Wide mapping must carry every declared value/status field')
                outputs = [output for mapping in columns.values() for output in mapping.values()]
            else:
                require(len(values) == 1, 'Multiple value/status fields require paired wide mappings')
                outputs = list(columns.values())
            require(all(isinstance(output, str) and output for output in outputs) and len(set(outputs)) == len(outputs)
                    and not set(outputs) & set(identities), 'Wide output columns must be distinct')
            require(not frame[identities + [name]].isna().any().any() and not frame.duplicated(identities + [name]).any(), 'Wide cell keys must be complete and unique')
            require(set(frame[name].unique()) <= set(columns), 'Wide mapping omits observed dimension values')
            require(all(set(group[name]) == set(columns) for _, group in frame.groupby(identities, sort=False, dropna=False)),
                    'Wide reshape requires declared cell support for every ID; retain explicit missing/status rows')
            if paired:
                wide = frame.pivot(index=identities, columns=name, values=values)
                reshaped = pd.DataFrame(index=wide.index)
                for label, mapping in columns.items():
                    for source, output in mapping.items():
                        reshaped[output] = wide[(source, label)]
                frame = reshaped.reset_index()
            else:
                frame = frame.pivot(index=identities, columns=name, values=values[0]).reindex(columns=list(columns)).rename(columns=columns).reset_index()
                frame.columns.name = None
            detail['grain_change'] = True
        elif op == 'row_id':
            inputs = construction_columns(frame, step.get('columns'))
            require(not frame[inputs].isna().any().any() and not frame[inputs].eq('').any().any(), 'row_id inputs must be complete')
            values = [json.dumps([str(value) for value in row], ensure_ascii=False, separators=(',', ':'))
                      for row in frame[inputs].itertuples(index=False, name=None)]
            require(len(values) == len(set(values)), 'row_id inputs must identify rows uniquely')
            put(step.get('output'), values)
        for name in outputs:
            nonfinite = frame[name].map(lambda value: isinstance(value, (int, float)) and not pd.isna(value) and not math.isfinite(value))
            require(not nonfinite.any() or invalid == 'missing', 'Transformation produced a nonfinite output: ' + name)
            frame[name] = frame[name].mask(nonfinite)
        require(set(inputs + outputs) <= set(definitions), 'Define units and versions for transformation inputs and outputs: ' + ', '.join(sorted(set(inputs + outputs) - set(definitions))))
        dependencies = []
        for name in inputs:
            for source in column_sources.get(name, []):
                if source not in dependencies:
                    dependencies.append(source)
        for name in outputs:
            column_sources[name] = list(dependencies)
        known_fields.update(frame.columns)
        records.append({'step': index, 'operation': step, 'input_columns': inputs, 'output_columns': outputs,
                        'rows_before': before, 'rows_after': len(frame), 'units': {name: definitions[name]['unit'] for name in dict.fromkeys(inputs + outputs)},
                        'reference_clock': clock, 'source_dependencies': dependencies,
                        'missing_outputs': {name: int((frame[name].isna() | frame[name].eq('')).sum()) for name in outputs}, **detail})
    return list(frame.columns), frame, records, known_fields


def construction_sample(fields, frame, sample, grain):
    import pandas as pd
    require(isinstance(sample, dict) and set(sample) <= {'id', 'row_id', 'filters', 'complete_cases', 'require_common'}, 'Unknown construction sample fields')
    if sample:
        require(isinstance(sample.get('id'), str) and sample['id'] and sample.get('row_id') in fields,
                'A declared sample requires id and an existing row_id column')
    require(type(sample.get('require_common', False)) is bool, 'require_common must be Boolean')
    row_id = sample.get('row_id')
    if row_id:
        require(not frame[row_id].isna().any() and not frame[row_id].eq('').any(), 'Sample IDs must be complete')
        ids = frame[row_id].map(str)
    else:
        ids = pd.Series([json.dumps([str(value) for value in row], ensure_ascii=False, separators=(',', ':'))
                         for row in frame[grain].itertuples(index=False, name=None)], index=frame.index, dtype=object)
    require(ids.is_unique, 'Sample IDs must be unique')
    selected = pd.Series(True, index=frame.index)
    flow = [{'step': 'constructed', 'rows_before': len(frame), 'rows_after': len(frame),
             'newly_excluded_rows': 0, 'cumulative_excluded_rows': 0}]
    exclusions = []
    rules = sample.get('filters', [])
    require(isinstance(rules, list), 'sample.filters must be a list')
    complete = construction_columns(frame, sample.get('complete_cases', []), empty=True)
    rules = rules + [{'column': name, 'op': 'nonmissing', 'reason': 'complete_case:' + name} for name in complete]
    for index, rule in enumerate(rules, 1):
        keep = construction_mask(frame, rule)
        reason = rule.get('reason', 'filter:' + str(index))
        before = int(selected.sum())
        selected &= keep
        after = int(selected.sum())
        flow.append({'step': reason, 'rule': rule, 'rows_before': before, 'rows_after': after,
                     'newly_excluded_rows': before - after, 'cumulative_excluded_rows': len(frame) - after})
        exclusions.append({'reason': reason, 'excluded_ids': ids[~keep].tolist()})
    return frame.loc[selected], {
        'id': sample.get('id', 'all_constructed_rows'), 'row_id': row_id, 'row_ids': ids[selected].tolist(),
        'policy': 'explicit', 'require_common': sample.get('require_common', False), 'flow': flow, 'exclusions': exclusions}


def assemble(spec, root, directory, *, specification_sha256=None):
    """Construct the declared variables and sample, then validate their grain."""
    import pandas as pd
    root, directory = Path(root), Path(directory)
    design_fields = {'question', 'population', 'observation_unit', 'economic_model', 'mechanism', 'estimand', 'identification'}
    require(set(spec) <= {'base', 'joins', 'definitions', 'grain', 'panel', 'geography', 'rename', 'numeric', 'scale',
                          'transformations', 'sample', 'analyses', 'output_format', 'clusters', 'weights', 'sql'} | design_fields,
            'Unknown table construction fields')
    definitions = spec['definitions']
    definition_fields = {'unit', 'definition', 'version', 'source_fields', 'role', 'causal_role', 'timing', 'rationale', 'measurement', 'inputs'}
    require(isinstance(definitions, dict) and all(isinstance(value, dict) and set(value) <= definition_fields
            and all(isinstance(value.get(key), str) and value[key] for key in ('unit', 'definition', 'version'))
            for value in definitions.values()), 'Define every variable unit, meaning and version')
    require(('base' in spec) != ('sql' in spec), 'Assembly requires exactly one of base or sql')
    if 'sql' in spec:
        rows, provenance, execution = sql_frame(root, spec['sql'])
        column_sources = {name: list(provenance) for name in rows.columns}
        transformations = [execution]
    else:
        rows = load_frame(root, spec['base'])
        provenance = [spec['base']]
        column_sources = {name: [{**spec['base'], 'field': name}] for name in rows.columns}
        transformations = []
    fields = list(rows.columns)
    for join in spec.get('joins', []):
        require(set(join) == {'table', 'left', 'right', 'columns', 'cardinality', 'unmatched'}, 'Join must declare keys, fields, cardinality and unmatched treatment')
        left, right, columns = join['left'], join['right'], join['columns']
        require(isinstance(left, list) and left and len(left) == len(right) and set(left) <= set(fields), 'Join columns differ from source tables')
        require(not set(columns) & set(fields) and join['cardinality'] in ('one_to_one', 'many_to_one') and join['unmatched'] in ('error', 'keep'), 'Join cardinality or output columns invalid')
        extra = load_frame(root, join['table'], columns=list(dict.fromkeys(right + columns)))
        require(not extra[right].isna().any().any() and not extra[right].eq('').any().any()
                and not extra.duplicated(right).any(), 'Right join keys must be complete and unique')
        require(not rows[left].isna().any().any() and not rows[left].eq('').any().any(), 'Left join keys must be complete')
        if join['cardinality'] == 'one_to_one':
            require(not rows.duplicated(left).any(), 'One-to-one left keys must be unique')
        left_index = pd.MultiIndex.from_frame(rows[left])
        right_index = pd.MultiIndex.from_frame(extra[right])
        unmatched = ~left_index.isin(right_index)
        require(join['unmatched'] == 'keep' or not unmatched.any(),
                'Unmatched join keys: ' + str(left_index[unmatched].tolist()[:10]))
        extra.index = right_index
        attached = extra[columns].reindex(left_index)
        attached.index = rows.index
        rows = pd.concat([rows, attached], axis=1)
        fields += columns
        provenance.append(join['table'])
        for name in columns:
            column_sources[name] = [{**join['table'], 'field': name}]
        transformations.append({'operation': {'op': 'join', **join}, 'rows_before': len(rows), 'rows_after': len(rows),
                                'input_columns': left + right, 'output_columns': columns,
                                'source_dependencies': list(provenance), 'reference_clock': None,
                                'unmatched_rows': int(unmatched.sum()),
                                'units': {name: definitions.get(spec.get('rename', {}).get(name, name), {}).get('unit') for name in columns}})
    rename = spec.get('rename', {})
    require(set(rename) <= set(fields) and all(isinstance(k, str) and k for k in rename.values()), 'Rename requires existing fields and nonempty names')
    fields = [rename.get(k, k) for k in fields]
    require(len(set(fields)) == len(fields), 'Renaming creates duplicate columns')
    if rename:
        rows = rows.rename(columns=rename)
    column_sources = {rename.get(name, name): value for name, value in column_sources.items()}
    if rename:
        transformations.append({'operation': {'op': 'rename', 'columns': rename}, 'rows_before': len(rows), 'rows_after': len(rows),
                                'input_columns': list(rename), 'output_columns': list(rename.values()), 'reference_clock': None,
                                'units': {name: definitions.get(name, {}).get('unit') for name in rename.values()},
                                'source_dependencies': list(provenance)})
    for name in spec.get('numeric', []):
        require(name in fields, 'Numeric column is absent')
        rows[name] = rows[name].map(lambda value: None if pd.isna(value) else numeric(value))
        transformations.append({'operation': {'op': 'numeric', 'column': name}, 'rows_before': len(rows), 'rows_after': len(rows),
                                'input_columns': [name], 'output_columns': [name], 'reference_clock': None,
                                'units': {name: definitions.get(name, {}).get('unit')}, 'source_dependencies': column_sources[name]})
    for name, factor in spec.get('scale', {}).items():
        require(name in fields and type(factor) in (int, float) and math.isfinite(factor), 'Scaling requires a column and finite factor')
        values = rows[name].map(lambda value: None if pd.isna(value) else numeric(value))
        rows[name] = values * factor
        require(rows[name].dropna().map(math.isfinite).all(), 'Scale produced a nonfinite value: ' + name)
        transformations.append({'operation': {'op': 'scale', 'column': name, 'factor': factor}, 'rows_before': len(rows), 'rows_after': len(rows),
                                'input_columns': [name], 'output_columns': [name], 'reference_clock': None,
                                'units': {name: definitions.get(name, {}).get('unit')}, 'source_dependencies': column_sources[name]})
    if spec.get('transformations'):
        fields, rows, executed, known_fields = transform_table(fields, rows, spec['transformations'], definitions, column_sources)
        transformations.extend(executed)
    else:
        known_fields = set(fields)
        rows = pd.DataFrame(rows, columns=fields)
    require(set(fields) <= set(definitions) <= known_fields, 'Define every output column; extra definitions must belong to constructed intermediate columns')
    if 'clusters' in spec:
        require(isinstance(spec['clusters'], list) and set(spec['clusters']) <= set(fields),
                'clusters must name final-table columns')
    if 'weights' in spec:
        weights = spec['weights']
        require(isinstance(weights, dict) and (weights.get('kind') == 'none' or weights.get('column') in fields),
                'weights must declare kind none or an existing column with its adopted meaning')
    grain = spec['grain']
    require(isinstance(grain, list) and grain and set(grain) <= set(fields), 'Declare the generated observation grain')
    require(not rows[grain].isna().any().any() and not rows[grain].eq('').any().any()
            and not rows.duplicated(grain).any(), 'Generated observation grain must be complete and unique')
    rows, sample = construction_sample(fields, rows, spec.get('sample', {}), grain)
    variable_design = None
    if spec.get('analyses'):
        require(design_fields <= set(spec), 'Prepared analyses require all seven adopted research design fields')
    if (design_fields - {'observation_unit'}) & set(spec):
        paths = [parent / name for parent in Path(__file__).resolve().parents
                 for name in ('skills/econ-design/scripts/research_design.py',
                              '.agents/skills/econ-design/scripts/research_design.py', 'research_design.py')]
        path = next((candidate for candidate in paths if candidate.is_file()), None)
        require(path is not None, 'Include the registered research design helper')
        module_spec = importlib.util.spec_from_file_location('assembly_research_design', path)
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        variable_design = module.variable_design(spec)
        for analysis in variable_design['analyses']:
            for name, columns in analysis['fields'].items():
                require(set(columns) <= set(fields), 'Analysis ' + analysis['id'] + ' uses a removed intermediate column in ' + name)
    if 'analyses' in spec:
        require(isinstance(spec['analyses'], list), 'analyses must be a list')
    panel_result = None
    if spec.get('panel'):
        panel = spec['panel']
        require(set(panel) == {'entity', 'time', 'balanced'} and type(panel['balanced']) is bool and {panel['entity'], panel['time']} <= set(grain), 'Panel requires entity/time grain and balanced flag')
        require(not rows.duplicated([panel['entity'],panel['time']]).any(), 'Panel entity-time keys must be unique')
        times = rows[panel['time']].unique().tolist()
        per_entity = rows.groupby(panel['entity'], sort=False)[panel['time']].nunique()
        balanced = bool(per_entity.eq(len(times)).all())
        require(not panel['balanced'] or balanced, 'Panel is missing declared entity-time cells')
        panel_result = {'entities': len(per_entity),
                        'periods': [value if isinstance(value, (str, int, float, bool)) else str(value)
                                    for value in sorted(times, key=str)], 'balanced': balanced}
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
        require(rows[geo['data_key']].astype(str).isin(geometry).all(), 'Geographical data keys lack geometry')
        selected = sorted(rows[geo['data_key']].astype(str).unique())
        geo_path = directory / 'geography.geojson'
        write_json(geo_path, {'type': 'FeatureCollection', 'features': [geometry[key] for key in selected]})
        geo_result = {'path': geo_path.name, 'sha256': digest(geo_path.read_bytes()), 'features': len(selected), 'join': geo}
        provenance.append({'path': geo['path'], 'sha256': geo['sha256']})
    output_format = spec.get('output_format', 'csv')
    require(output_format in ('csv', 'parquet', 'arrow'), 'output_format must be csv, parquet or arrow')
    table = write_frame(directory / ('analysis.' + output_format), fields, rows)
    record = {'specification': spec, 'inputs': provenance, 'table': table, 'definitions': {name: definitions[name] for name in fields},
              'grain': grain, 'panel': panel_result, 'geography': geo_result, 'sample': sample, 'transformations': transformations,
              'variable_design': {key: value for key, value in (variable_design or {}).items() if key not in design_fields},
              'producer_sha256': digest(Path(__file__).read_bytes())}
    for name in ('observation_unit', 'clusters', 'weights'):
        if name in spec:
            record[name] = spec[name]
    if specification_sha256 is not None:
        record['specification_sha256'] = specification_sha256
    write_json(directory / 'data-record.json', record)
    write_analysis_inputs(record, directory, rows)
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
        release, metadata_response = census_acs_metadata(spec.get('year', 'latest'), directory)
        payload,response=sources.get_json(release['variables_url'],Path(directory)/'original','census-variables.json')
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
    if provider == 'census':
        result.update(specification=spec, definition=release, responses=[metadata_response, response])
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


DESCRIBE_R = R_READ_TABLE + r'''
args <- commandArgs(trailingOnly=TRUE)
suppressPackageStartupMessages(library(jsonlite))
suppressPackageStartupMessages(library(modelsummary))
suppressPackageStartupMessages(library(ggplot2))
job <- fromJSON(args[1], simplifyVector=TRUE)
weighted <- job$weights$kind != "none"
source <- ers_read_table(job$data_path,
    text_columns=if (tolower(tools::file_ext(job$data_path)) == "csv") TRUE else character(),
    columns=job$columns)
match_labels <- function(values, labels) {
    if (is.double(values) && !inherits(values, c("integer64", "Date", "POSIXt"))) {
        match(values, suppressWarnings(as.numeric(labels)))
    } else match(as.character(values), labels)
}
selected <- match(seq_along(job$row_ids), match_labels(source[[job$row_id]], job$row_ids))
if (anyNA(selected)) stop("Descriptive sample identities differ from the canonical table")
numeric_values <- function(x) {
    if (is.numeric(x)) return(as.numeric(x))
    x <- as.character(x)
    x[x %in% c("", ".", "NA", ":")] <- NA_character_
    as.numeric(x)
}
prepare_rows <- function(raw) {
    group <- if (is.null(job$group_column)) rep("全体", nrow(raw)) else job$groups[match_labels(raw[[job$group_column]], job$groups)]
    group[is.na(group) | group == ""] <- "（群欠損）"
    result <- data.frame(group=group,
        period=if (is.null(job$period_column)) rep(job$periods[[1]], nrow(raw)) else job$periods[match_labels(raw[[job$period_column]], job$periods)],
        weight=if (weighted) numeric_values(raw[[job$weights$column]]) else rep(1, nrow(raw)),
        stringsAsFactors=FALSE)
    if (!is.null(job$entity_column)) result$entity <- as.character(raw[[job$entity_column]])
    for (key in names(job$design_columns)) {
        value <- raw[[job$design_columns[[key]]]]
        result[[key]] <- if (startsWith(key, "fpc")) numeric_values(value) else as.character(value)
    }
    for (i in seq_len(nrow(job$variables))) {
        variable <- job$variables[i, ]
        value <- numeric_values(raw[[variable$name]])
        if (!is.null(variable$status) && !is.na(variable$status)) {
            value[is.na(match_labels(raw[[variable$status]], unlist(variable$observed_statuses)))] <- NA_real_
        }
        result[[variable$key]] <- value
    }
    result
}
d <- prepare_rows(source[selected, , drop=FALSE])
survey_source <- NULL
if (!is.null(job$balance) && job$balance$inference$method == "survey") {
    survey_source <- prepare_rows(source)
    survey_source$in_domain <- !is.na(match_labels(source[[job$row_id]], job$row_ids))
    survey_source <- survey_source[!is.na(survey_source$weight) & survey_source$weight > 0, , drop=FALSE]
    for (key in job$variables$key) survey_source[[key]][!survey_source$in_domain] <- NA_real_
}
rm(source)
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
            survey_data <- survey_source
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
if (tolower(tools::file_ext(job$data_path)) != "csv") packages <- c(packages, "arrow")
if (!is.null(job$balance) && job$balance$inference$method %in% c("estimatr", "survey")) packages <- c(packages, job$balance$inference$method)
if (weighted && any(vapply(job$distributions, function(x) !is.null(x$box), logical(1)))) packages <- c(packages, "quantreg")
versions <- setNames(lapply(packages, function(p) as.character(packageVersion(p))), packages)
write_json(list(rows=summary_rows, balance=balance_rows, trends=trends, distributions=distributions,
                engine=list(R=R.version.string, packages=versions)), args[2], auto_unbox=TRUE, digits=NA, na="null", dataframe="rows", pretty=TRUE)
'''


def bind_data_record(spec, root):
    """Resolve one saved construction contract before its existing consumer runs."""
    reference = spec['data_record']
    require(isinstance(reference, dict) and set(reference) == {'path', 'sha256'},
            'data_record requires its path and sha256')
    root = Path(root).resolve()
    path = (root / reference['path']).resolve()
    raw = path.read_bytes()
    require(digest(raw) == reference['sha256'], 'Data construction record hash differs')
    record = sources.read_record(path, raw)
    require(isinstance(record.get('sample'), dict) and record['sample'].get('row_id'),
            'data_record consumers require an explicit sample.row_id in the assembly specification')
    table = record['table']
    data_path = Path(table['path'])
    data_path = (data_path if data_path.is_absolute() else path.parent / data_path).resolve()
    with data_path.open('rb') as stream:
        require(hashlib.file_digest(stream, 'sha256').hexdigest() == table['sha256'],
                'Constructed analysis table hash differs')
    clean = {key: value for key, value in spec.items() if key != 'data_record'}
    if 'data' in clean:
        supplied = clean['data']['path'] if isinstance(clean['data'], dict) else clean['data']
        require((root / supplied).resolve() == data_path, 'Analysis data differs from the construction record')
        if isinstance(clean['data'], dict):
            require(clean['data'].get('sha256') == table['sha256'], 'Analysis data hash differs from the construction record')
    clean['data'] = str(data_path)
    construction = {'record': {'path': str(path), 'sha256': reference['sha256']},
                    'table': dict(table),
                    'grain': record['grain']}
    for key in ('sample', 'sample_flow', 'transformations', 'design', 'variable_design',
                'parent_record', 'analysis_id', 'analysis_specification', 'observation_unit', 'clusters', 'weights'):
        if key in record:
            construction[key] = record[key]
    adopted = {**record.get('specification', {}), **record.get('analysis_specification', {})}
    for key in ('question', 'population', 'observation_unit', 'economic_model', 'mechanism', 'estimand', 'identification'):
        if key in adopted:
            construction[key] = adopted[key]
    return clean, record, construction


def attach_data_record(result, record, construction):
    """Preserve construction definitions beside the official fitted sample."""
    result['variables'] = record['definitions']
    result['data_construction'] = construction
    sample = record.get('sample') or {}
    fitted = result.get('sample') or {}
    expected = sample.get('row_ids')
    actual = fitted.get('included_ids', fitted.get('row_ids'))
    if expected is not None and actual is not None and fitted.get('included_ids_available', True):
        expected, actual = [str(value) for value in expected], [str(value) for value in actual]
        require(len(actual) == len(set(actual)) and set(actual) <= set(expected),
                'Official fitted identities differ from the constructed sample')
        actual_set = set(actual)
        same_membership = actual_set == set(expected)
        require(not sample.get('require_common', False) or same_membership,
                'The official estimator changed the required common sample')
        construction['fitted_sample'] = {'observations': len(actual),
            'shared_observations': len(expected), 'same_membership': same_membership,
            'additional_excluded_ids': [value for value in expected if value not in actual_set]}
    else:
        require(not sample.get('require_common', False),
                'A required common sample needs official fitted row identities')
        construction['fitted_sample'] = {'included_ids_available': False,
            'observations': fitted.get('observations', result.get('observations'))}
    return result


def execute_with_data_record(operation, spec, spec_path):
    """Bind the shared input, call the existing estimator, and attach its definitions."""
    clean, record, construction = bind_data_record(spec, Path(spec_path).resolve().parent)
    analyses = record.get('specification', {}).get('analyses', [])
    if analyses:
        supplied = {key: value for key, value in clean.items() if key != 'data'}
        adopted = [analysis for analysis in analyses if analysis['specification'] == supplied
                   and (record.get('analysis_id') is None or analysis['id'] == record['analysis_id'])]
        require(len(adopted) == 1, 'Estimation input must match one declared analysis in the construction specification')
        construction['analysis_id'] = adopted[0]['id']
    sample = record.get('sample') or {}
    if sample.get('row_id'):
        require(clean.get('id') == sample['row_id'], 'Estimator ID differs from the shared sample identity')
    result = operation(clean, spec_path=Path(spec_path))
    return attach_data_record(result, record, construction)


def write_analysis_inputs(record, directory, frame):
    """Materialize declared existing-runner inputs against the final saved record."""
    analyses = record.get('specification', {}).get('analyses', [])
    if not analyses:
        return []
    require(record.get('sample', {}).get('row_id'), 'Prepared analyses require sample.row_id')
    directory = Path(directory).resolve()
    record_path = directory / 'data-record.json'
    reference_hash = digest(record_path.read_bytes())
    outputs, names = [], set()
    for analysis in analyses:
        require(isinstance(analysis, dict) and {'id', 'runner', 'specification'} <= set(analysis)
                <= {'id', 'runner', 'specification', 'sample'},
                'Each analysis declares id, runner, specification and an optional sample')
        name = analysis['id']
        require(isinstance(name, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name)
                and name not in names, 'Analysis IDs must be distinct file-safe names')
        names.add(name)
        require(analysis['runner'] in ('research', 'causal'), 'Select an existing research or causal runner')
        specification = analysis['specification']
        require(isinstance(specification, dict) and not {'data', 'data_record'} & set(specification),
                'Assembly owns the analysis data and construction reference')
        require(specification.get('id') == record['sample']['row_id'],
                'Analysis ID column differs from sample.row_id')
        table, selected_record_path, table_directory = record['table'], record_path, directory
        selected_hash = reference_hash
        if 'sample' in analysis:
            require(not record['sample'].get('require_common'),
                    'A required common sample applies to every analysis; declare its selection at assembly level')
            sample = analysis['sample']
            require(isinstance(sample, dict), 'Analysis sample must be an object')
            sample = {'row_id': record['sample']['row_id'], **sample}
            require(sample['row_id'] == record['sample']['row_id'],
                    'Analysis sample must preserve the constructed row identity')
            selected, sample_record = construction_sample(table['fields'], frame, sample, record['grain'])
            analysis_directory = directory / 'analyses' / name
            table = write_frame(analysis_directory / ('analysis.' + table.get('format', 'csv')), table['fields'], selected)
            selected_record = {key: record[key] for key in (
                'specification', 'specification_sha256', 'inputs', 'definitions', 'grain',
                'transformations', 'variable_design', 'producer_sha256', 'observation_unit', 'clusters', 'weights') if key in record}
            selected_record.update(parent_record={'path': os.path.relpath(record_path, analysis_directory),
                                                  'sha256': reference_hash}, analysis_id=name,
                analysis_specification=specification, table=table, sample=sample_record)
            selected_record_path = analysis_directory / 'data-record.json'
            write_json(selected_record_path, selected_record)
            selected_hash = digest(selected_record_path.read_bytes())
            table_directory = analysis_directory
        path = directory / 'analyses' / (name + '.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        selected_reference = {'path': os.path.relpath(selected_record_path, path.parent), 'sha256': selected_hash}
        write_json(path, {**specification, 'data': os.path.relpath(table_directory / table['path'], path.parent),
                          'data_record': selected_reference})
        outputs.append({'id': name, 'runner': analysis['runner'], 'path': path.relative_to(directory).as_posix(),
                        'sha256': digest(path.read_bytes())})
    return outputs


def describe(spec, root, directory, rscript=None):
    """Calculate adopted display aggregates through modelsummary and ggplot2."""
    if isinstance(spec, dict) and 'data_record' in spec:
        clean, record, construction = bind_data_record(spec, root)
        clean['data'] = {'path': clean['data'],
                         'sha256': record['table']['sha256']}
        shared = record.get('sample') or {}
        adopted = {**record.get('specification', {}), **record.get('analysis_specification', {})}
        for key in ('population', 'observation_unit'):
            if key in adopted:
                require(key not in clean or clean[key] == adopted[key],
                        'Descriptive ' + key + ' differs from the constructed definition')
                clean[key] = adopted[key]
        if shared.get('row_id'):
            require('row_id' not in clean or clean['row_id'] == shared['row_id'],
                    'Descriptive row identity differs from the shared sample')
            clean['row_id'] = shared['row_id']
        if 'sample' not in clean and shared.get('id'):
            clean['sample'] = {'id': shared['id'], 'policy': 'available-case'}
        variables = []
        for variable in clean.get('variables', []):
            item = {'name': variable} if isinstance(variable, str) else dict(variable)
            definition = record['definitions'].get(item['name'])
            require(definition is not None, 'Descriptive variable lacks a constructed definition')
            require('unit' not in item or item['unit'] == definition['unit'],
                    'Descriptive unit differs from the constructed variable')
            item['unit'] = definition['unit']
            variables.append(item)
        clean['variables'] = variables
        result = describe(clean, root, directory, rscript)
        return attach_data_record(result, record, construction)
    allowed = {'result_id', 'specification', 'data', 'row_id', 'population', 'sample',
               'period', 'group', 'variables', 'weights', 'quantiles', 'denominator', 'distributions',
               'observation_unit', 'entity', 'balance'}
    require(isinstance(spec, dict) and not set(spec) - allowed, 'Unknown descriptive specification fields')
    for key in ('result_id', 'specification', 'row_id', 'population', 'denominator'):
        require(isinstance(spec.get(key), str) and spec[key], 'Adopt descriptive ' + key)
    root = Path(root).resolve()
    data_path = Path(spec['data']['path'])
    variables = spec.get('variables')
    require(isinstance(variables, list) and variables, 'Select descriptive variables')
    for variable in variables:
        require(isinstance(variable, dict) and set(variable) <= {'name', 'unit', 'label', 'status', 'observed_statuses'} and all(isinstance(variable.get(key), str) and variable[key] for key in ('name', 'unit')), 'Variable needs its saved name and unit')
    sample = spec.get('sample', {})
    require(isinstance(sample, dict) and sample.get('id') and sample.get('policy') in ('available-case', 'complete-case', 'fitted'), 'Adopt sample id and available-case, complete-case or fitted policy')
    require(not set(sample) - {'id', 'policy', 'filters', 'result', 'ids_key'} and isinstance(sample.get('filters', []), list), 'Sample uses explicit filters or a saved fitted-result identity list')
    read_columns = [spec['row_id'], *[v['name'] for v in variables], *[v['status'] for v in variables if 'status' in v]]
    for field in ('period', 'group', 'weights'):
        value = spec.get(field)
        if isinstance(value, dict) and value.get('column'):
            read_columns.append(value['column'])
    if spec.get('entity'):
        read_columns.append(spec['entity'])
    for condition in sample.get('filters', []):
        require(isinstance(condition, dict) and set(condition) == {'column', 'values'} and isinstance(condition['column'], str) and isinstance(condition['values'], list), 'Sample filters require a column and explicit values')
        read_columns.append(condition['column'])
    balance = spec.get('balance')
    require(balance is None or isinstance(balance, dict), 'Balance must be an object')
    inference = (balance or {}).get('inference', {})
    require(isinstance(inference, dict), 'Balance inference must be an object')
    for key in ('clusters', 'blocks', 'ids', 'strata', 'fpc'):
        names = inference.get(key, [])
        names = [names] if isinstance(names, str) else names
        require(isinstance(names, list) and all(isinstance(name, str) for name in names), 'Inference design must name data columns')
        read_columns.extend(names)
    read_columns = list(dict.fromkeys(read_columns))
    fields, rows = load_table(root, spec['data'], columns=read_columns)
    input_rows = rows
    require(spec['row_id'] in fields, 'Row identity column is absent')
    identities = [row[spec['row_id']] for row in rows]
    require(all(identities) and len(set(identities)) == len(rows), 'Row identities must be complete and unique')
    observation_unit = spec.get('observation_unit', 'records')
    require(isinstance(observation_unit, str) and observation_unit, 'Observation unit must be a nonempty label')
    entity = spec.get('entity')
    if entity is not None:
        require(isinstance(entity, str) and entity in fields and all(row[entity] for row in rows), 'Entity column must contain complete identities')

    previous_count = len(rows)

    def sample_count(stage, selected):
        nonlocal previous_count
        count = len(selected)
        result = {'stage': stage, 'n': count, 'n_observations': count,
                  'newly_excluded_rows': previous_count - count,
                  'cumulative_excluded_rows': len(identities) - count,
                  'n_entities': len({row[entity] for row in selected}) if entity else None, 'unit': observation_unit}
        previous_count = count
        return result

    for variable in variables:
        require(variable['name'] in fields, 'Descriptive variable is absent: ' + variable['name'])
        if 'status' in variable:
            require(variable['status'] in fields and isinstance(variable.get('observed_statuses'), list) and variable['observed_statuses'], 'Status fields require adopted observed_statuses')
    require(len({variable['name'] for variable in variables}) == len(variables), 'Descriptive variable names must be distinct')
    flow = [sample_count('input', rows)]
    for condition in sample.get('filters', []):
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

    def validate_design_row(row):
        for key, column in design_columns.items():
            value = numeric(row[column]) if key.startswith('fpc') else row[column]
            require(value is not None and value != '', 'Inference design column has missing values: ' + column)

    row_ids, selected_rows = [], []
    variable_row_ids = {variable['name']: [] for variable in variables}
    status_counts = {}
    for row in rows:
        weight = numeric(row[weights['column']]) if weighted else 1.0
        require(weight is None or weight >= 0, 'Weights must be nonnegative')
        require(weights['kind'] != 'frequency' or weight is None or weight.is_integer(), 'Frequency weights must be integer counts')
        validate_design_row(row)
        values = []
        for variable in variables:
            status = row[variable['status']] if 'status' in variable else 'observed'
            observed = 'status' not in variable or status in variable['observed_statuses']
            value = numeric(row[variable['name']]) if observed else None
            if 'status' not in variable and value is None:
                status = 'missing'
            status_counts.setdefault(variable['name'], {}).setdefault(status, 0)
            status_counts[variable['name']][status] += 1
            values.append(value)
        if sample['policy'] == 'complete-case' and (weight is None or weight == 0 or any(value is None for value in values)):
            continue
        identity = row[spec['row_id']]
        row_ids.append(identity)
        selected_rows.append(row)
        if weight is not None and weight > 0:
            for variable, value in zip(variables, values):
                if value is not None:
                    variable_row_ids[variable['name']].append(identity)
    flow.append(sample_count(sample['policy'], selected_rows))
    if sample['policy'] == 'fitted':
        require(set(row_ids) == selected_ids, 'Period or group selection changed the adopted fitted sample')
    require(row_ids, 'The adopted sample has no rows')
    survey_count = None
    if balance is not None and balance['inference']['method'] == 'survey':
        survey_count = 0
        for row in input_rows:
            weight = numeric(row[weights['column']])
            require(weight is None or weight >= 0, 'Survey weights must be nonnegative')
            if weight is None or weight == 0:
                continue
            validate_design_row(row)
            survey_count += 1
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
    job = {'data_path': str((root / data_path).resolve()), 'columns': read_columns,
           'row_id': spec['row_id'], 'row_ids': row_ids, 'design_columns': design_columns,
           'group_column': group['column'] if group else None,
           'period_column': period['column'] if isinstance(period, dict) else None, 'entity_column': entity,
           'groups': groups, 'periods': periods, 'weights': weights, 'quantiles': quantiles,
           'variables': [{'key': 'v' + str(i), **v} for i, v in enumerate(variables)], 'distributions': distributions,
           'balance': balance, 'grouped': bool(group), 'has_entity': entity is not None}
    r_argv = companion_command('r', rscript, default_options=('--vanilla',))
    with tempfile.TemporaryDirectory(prefix='.describe-', dir=directory) as temporary:
        temporary = Path(temporary)
        write_json(temporary / 'input.json', job)
        (temporary / 'describe.R').write_text(DESCRIBE_R, encoding='utf8')
        subprocess.run([*r_argv, str(temporary / 'describe.R'), str(temporary / 'input.json'), str(temporary / 'output.json')], check=True)
        computed = json.loads((temporary / 'output.json').read_text())
    with (root / data_path).open('rb') as stream:
        require(hashlib.file_digest(stream, 'sha256').hexdigest() == spec['data']['sha256'], 'Input snapshot changed during descriptive calculation')
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
            if survey_count is not None:
                balance_metadata['survey_design_scope'] = 'all positive-weight input records; adopted sample is a survey domain'
                balance_metadata['survey_design_observations'] = survey_count
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
                'variable_row_ids': variable_row_ids},
            'display': display, 'statistics': {}, 'engine': computed['engine'],
            'provenance': {'data_sha256': spec['data']['sha256'], 'script_sha256': digest(Path(__file__).read_bytes()),
                           'r_script_sha256': digest(DESCRIBE_R.encode()), 'rscript': str(Path(r_argv[0]).resolve()),
                           'rscript_options': r_argv[1:]}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('acquire', 'assemble', 'extract', 'catalog', 'dataset-use', 'describe'))
    parser.add_argument('specification', type=Path)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--output-record', action='store_true')
    parser.add_argument('--rscript')
    args = parser.parse_args(argv)
    if args.output_record:
        if args.command != 'assemble' or args.output.name != 'data-record.json': parser.error('--output-record requires assemble output named data-record.json')
        args.output = args.output.parent
    raw = args.specification.read_bytes()
    spec = json.loads(raw)
    args.output.mkdir(parents=True, exist_ok=True)
    require(not any(path.is_file() or path.is_symlink() for path in args.output.rglob('*')),
            'Output directory must be fresh; existing files are preserved')
    if args.command == 'describe':
        result = describe(spec, args.root, args.output, args.rscript)
        result['provenance']['spec_sha256'] = digest(raw)
        write_json(args.output / 'result.json', result)
        print(json.dumps({'result': str((args.output / 'result.json').resolve()), 'result_id': result['result_id']}))
        return
    record_name = 'catalog.json' if args.command == 'catalog' else 'dataset-mentions.json' if args.command == 'dataset-use' else 'data-record.json'
    if args.command == 'acquire': result = acquire(spec,args.output)
    elif args.command == 'assemble': result = assemble(spec,args.root,args.output,specification_sha256=digest(raw))
    elif args.command == 'extract': result = extract_table(spec,args.root,args.output)
    elif args.command == 'dataset-use': result = dataset_mentions(spec,args.root,args.output)
    else: result = catalog(spec,args.output)
    if args.command != 'assemble':
        result['specification_sha256'] = digest(raw)
        write_json(args.output/record_name,result)
    analyses = [{'id': item['id'], 'runner': item['runner'],
                 'path': str((args.output / 'analyses' / (item['id'] + '.json')).resolve())}
                for item in spec.get('analyses', [])] if args.command == 'assemble' else []
    print(json.dumps({'record':str((args.output/record_name).resolve()),'table':result.get('table'),
                      'returned':result.get('returned'), 'analyses': analyses}))


if __name__ == '__main__':
    main()
