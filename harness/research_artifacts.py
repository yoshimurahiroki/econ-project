#!/usr/bin/env python3
"""Normalize saved scientific results and generate existing research DAG stages."""
from __future__ import annotations
import argparse
import copy
import html
import io
import json
import math
import os
import re
import sys
import shutil
import subprocess
import random
import csv
import tempfile
from pathlib import Path

import state
import research_evidence as evidence

NAME=re.compile(r'^[A-Za-z][A-Za-z0-9_-]*$')
FMT=re.compile(r'^(?:\.[0-9]{1,2})?[fge]$')
TOKEN=re.compile(r'\{\{stat:([A-Za-z][A-Za-z0-9_-]*)\}\}|\{\{(table|figure)\}\}')
GALLERY_KINDS = ('descriptive', 'sample_composition', 'distribution', 'time_series',
                 'group_comparison', 'coefficient', 'event_study', 'robustness',
                 'alternative_specification', 'table', 'figure')
PLOT_TYPES = ('table', 'bar', 'line', 'scatter', 'step', 'area', 'coefficient', 'event_study', 'density', 'ecdf', 'box')
GALLERY_RENDER_VERSION = 4
DISPLAY_FIELDS = {'title', 'column_order', 'column_labels', 'formats', 'row_order',
                  'sort_by', 'ascending', 'notes', 'plot_type', 'x', 'y', 'lower', 'upper',
                  'series', 'visible_series', 'selected_result_ids', 'x_label', 'y_label',
                  'x_limits', 'y_limits', 'x_scale', 'y_scale', 'colors', 'legend',
                  'legend_location', 'width', 'height', 'orientation', 'style', 'font_size',
                  'series_order', 'series_labels'}
GALLERY_FILTERS = ('result_id', 'sample', 'comparison', 'outcome', 'specification', 'period', 'adoption')
GALLERY_LABELS = {'variable': '変数', 'term': '項目', 'group': '群', 'period': '期間',
                  'event_time': '導入からの期数', 'mean': '平均', 'sd': '標準偏差', 'median': '中央値',
                  'q25': '25%点', 'q50': '50%点', 'q75': '75%点', 'estimate': '推定値',
                  'se': '標準誤差', 'ci_low': '区間下端', 'ci_high': '区間上端', 'p_value': 'p 値',
                  'n': '観測数', 'unit': '単位', 'stage': '段階', 'n_missing': '欠損数', 'n_zero': 'ゼロの件数',
                  'value': '値', 'middle': '中央値', 'count': '件数', 'density': '密度', 'bin_mid': '階級の中央'}


def gallery_registry(root, path):
    """Read the saved catalogue; producer paths are provenance, not read inputs."""
    root = Path(root).resolve(strict=True)
    path = Path(path)
    if path.is_absolute():
        path = path.relative_to(root)
    path = root / state.relative(root, path.as_posix())
    registry = load(path)
    if not isinstance(registry, dict) or registry.get('schema') != 'research-artifact-registry-v1':
        raise ValueError('gallery requires a saved research-artifact-registry-v1 registry')
    if not isinstance(registry.get('records'), dict) or not isinstance(registry.get('items', {}), dict):
        raise ValueError('registry records and items must be objects')
    return path, registry


def gallery_display_metadata(value):
    """Keep sample membership in the scientific record, outside display metadata."""
    if isinstance(value, dict):
        return {key: gallery_display_metadata(item) for key, item in value.items()
                if not (key.endswith('_ids') and key not in ('result_ids', 'specification_ids', 'cohort_ids'))}
    if isinstance(value, list):
        return [gallery_display_metadata(item) for item in value]
    return copy.deepcopy(value)


def gallery_metadata(registry, result_ids):
    """Capture economic definitions and producer identities from saved results once."""
    producers = {}
    definitions = []
    fields = ('run_id', 'specification_id', 'sample', 'population', 'observation_unit',
              'comparison', 'period', 'variables', 'measurement_units', 'estimand',
              'inference', 'weights', 'denominator', 'bin_edges', 'interval_closure',
              'quantile_convention', 'observations', 'outcome', 'specification', 'estimator',
              'n', 'n_clusters', 'fixed_effects', 'controls', 'sample_policy', 'unit',
              'ci_kind', 'interval_type', 'confidence_level', 'reference_time', 'reference_event_time',
              'reference_distribution', 'degrees_of_freedom', 'cluster')
    for result_id in result_ids:
        if result_id not in registry['records']:
            raise ValueError('unknown saved result: ' + result_id)
        record = registry['records'][result_id]
        saved = record.get('source_result') or {}
        adopted = record.get('adopted') or saved.get('definition') or {}
        if not isinstance(adopted, dict):
            adopted = {}
        metadata = {key: copy.deepcopy(saved.get(key, adopted.get(key))) for key in fields
                    if key in saved or key in adopted}
        metadata.update({key: copy.deepcopy(value) for key, value in record.get('metadata', {}).items()
                         if key in fields})
        if isinstance(saved.get('display'), dict):
            metadata.update(copy.deepcopy(saved['display'].get('metadata', {})))
        metadata.setdefault('specification', metadata.get('specification_id', record.get('identity', {}).get('specification', saved.get('specification'))))
        if 'outcome' not in metadata and 'variables' in metadata:
            metadata['outcome'] = copy.deepcopy(metadata['variables'])
        for old, new in (('observations', 'n'), ('method', 'estimator')):
            if new not in metadata and old in saved:
                metadata[new] = copy.deepcopy(saved[old])
        metadata = gallery_display_metadata(metadata)
        definitions.append(metadata)
        producers[result_id] = {
            'identity': copy.deepcopy(record.get('identity', {})),
            'run_id': metadata.get('run_id', saved.get('run_id', (record.get('provenance') or {}).get('run_id'))),
            'references': copy.deepcopy(record.get('references', {})),
            'environment': copy.deepcopy(record.get('metadata', {}).get('environment',
                                          record.get('environment', record.get('versions', saved.get('environment', {}))))),
            'engine': copy.deepcopy(record.get('engine')),
            'method': record.get('method'),
        }
    common = {key: value for key, value in definitions[0].items()
              if all(other.get(key) == value for other in definitions[1:])} if definitions else {}
    return {**common, 'producers': producers,
            'result_definitions': dict(zip(result_ids, definitions))}


def validate_gallery_item(item):
    """Validate one display-ready record without opening any producing input."""
    if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not NAME.fullmatch(item['id']):
        raise ValueError('gallery item needs a simple stable id')
    if item.get('kind') not in GALLERY_KINDS or not isinstance(item.get('title'), str) or not item['title'].strip():
        raise ValueError('gallery item requires a title and supported kind')
    result_ids = item.get('result_ids')
    if not isinstance(result_ids, list) or not result_ids or any(not isinstance(x, str) or not x for x in result_ids) or len(set(result_ids)) != len(result_ids):
        raise ValueError('gallery item requires distinct saved result_ids')
    columns = item.get('columns')
    if not isinstance(columns, list) or not columns:
        raise ValueError('gallery columns must contain key, label and unit')
    keys = []
    for column in columns:
        if not isinstance(column, dict) or set(column) != {'key', 'label', 'unit'} or any(not isinstance(v, str) for v in column.values()) or not column['key'] or not column['label']:
            raise ValueError('gallery columns require string key, label and unit')
        keys.append(column['key'])
    if len(set(keys)) != len(keys):
        raise ValueError('gallery column keys must be distinct')
    if not isinstance(item.get('rows'), list):
        raise ValueError('gallery rows must be a saved list')
    for row in item['rows']:
        if not isinstance(row, dict) or set(row) - set(keys) - {'result_id'}:
            raise ValueError('saved display rows must use declared columns')
        if row.get('result_id') not in result_ids:
            raise ValueError('each display row must name its saved result_id')
        if any(value is not None and type(value) not in (str, int, float, bool) for value in row.values()):
            raise ValueError('saved display cells must be scalar values or null')
        if any(type(value) is float and not math.isfinite(value) for value in row.values()):
            raise ValueError('saved display cells must be finite or null')
    display = item.get('display', {})
    if not isinstance(display, dict) or set(display) - DISPLAY_FIELDS:
        raise ValueError('unsupported display setting; scientific definitions belong to a new registered result')
    if display.get('plot_type', 'table') not in PLOT_TYPES:
        raise ValueError('unsupported saved-data plot type')
    for field in ('x', 'y', 'lower', 'upper', 'series', 'sort_by'):
        if display.get(field) is not None and display[field] not in keys:
            raise ValueError(field + ' must name a saved column')
    for field in ('column_order', 'selected_result_ids', 'visible_series'):
        values = display.get(field)
        if values is not None and (not isinstance(values, list) or any(not isinstance(v, str) for v in values) or len(set(values)) != len(values)):
            raise ValueError(field + ' must contain distinct strings')
    if set(display.get('column_order', keys)) - set(keys) or not display.get('column_order', keys):
        raise ValueError('column_order must select saved columns')
    if set(display.get('selected_result_ids', result_ids)) - set(result_ids):
        raise ValueError('display specification selection must use saved result_ids')
    if 'visible_series' in display and display.get('series'):
        series = {str(row.get(display['series'])) for row in item['rows']}
        if set(display['visible_series']) - series:
            raise ValueError('visible_series must select saved series')
    order = display.get('row_order')
    if order is not None and (not isinstance(order, list) or any(type(i) is not int for i in order) or sorted(order) != list(range(len(item['rows'])))):
        raise ValueError('row_order must order every saved row index once')
    for field in ('column_labels', 'formats', 'colors'):
        if not isinstance(display.get(field, {}), dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in display.get(field, {}).items()):
            raise ValueError(field + ' must map strings to strings')
    if display.get('style', 'paper') not in ('paper', 'presentation'):
        raise ValueError('style must be paper or presentation')
    if type(display.get('font_size', 10)) not in (int, float) or not 6 <= display.get('font_size', 10) <= 40:
        raise ValueError('font_size must be 6–40')
    if not isinstance(display.get('series_order', []), list) or any(not isinstance(value, str) for value in display.get('series_order', [])):
        raise ValueError('series_order must contain saved series names')
    if display.get('series'):
        series = {str(row.get(display['series'])) for row in item['rows']}
        order = display.get('series_order', [])
        if set(order) - series or len(set(order)) != len(order):
            raise ValueError('series_order must select distinct saved series')
    if not isinstance(display.get('series_labels', {}), dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in display.get('series_labels', {}).items()):
        raise ValueError('series_labels must map saved names to labels')
    if set(display.get('column_labels', {})) - set(keys) or set(display.get('formats', {})) - set(keys):
        raise ValueError('column labels and formats must use saved column keys')
    if any(not FMT.fullmatch(fmt) for fmt in display.get('formats', {}).values()):
        raise ValueError('numeric formats must use f, g or e precision')
    for field in ('title', 'x_label', 'y_label', 'legend_location'):
        if field in display and not isinstance(display[field], str):
            raise ValueError(field + ' must be text')
    for field in ('ascending', 'legend'):
        if field in display and type(display[field]) is not bool:
            raise ValueError(field + ' must be boolean')
    for field in ('width', 'height'):
        if type(display.get(field, 720)) is not int or not 240 <= display.get(field, 720) <= 4000:
            raise ValueError(field + ' must be 240–4000 pixels')
    for axis in ('x', 'y'):
        limits = display.get(axis + '_limits')
        if limits is not None and (not isinstance(limits, list) or len(limits) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in limits) or limits[0] >= limits[1]):
            raise ValueError(axis + '_limits requires increasing finite endpoints')
        if display.get(axis + '_scale', 'linear') not in ('linear', 'log', 'symlog'):
            raise ValueError(axis + '_scale must be linear, log or symlog')
    if display.get('orientation', 'vertical') not in ('vertical', 'horizontal'):
        raise ValueError('orientation must be vertical or horizontal')
    if not isinstance(display.get('notes', []), list) or any(not isinstance(v, str) for v in display.get('notes', [])):
        raise ValueError('notes must be a list of text')
    if not isinstance(item.get('metadata'), dict) or not isinstance(item.get('links'), dict):
        raise ValueError('metadata and links must be objects')
    if not isinstance(item.get('interpretation'), str) or not isinstance(item.get('status'), str) or not item['status']:
        raise ValueError('interpretation and status must be text')
    for field in ('findings', 'issues', 'adoption_decision'):
        if not isinstance(item.get(field, ''), str):
            raise ValueError(field + ' must be text')
    if any(not isinstance(v, list) or any(not isinstance(link, str) for link in v) for v in item['links'].values()):
        raise ValueError('links must map names to lists of references')
    if not isinstance(item.get('files'), list) or any(not isinstance(v, str) for v in item['files']):
        raise ValueError('files must be project-relative display paths')
    json.dumps(item, allow_nan=False)
    return item


def gallery_projection(item):
    """Apply display selection while retaining unrounded saved cells and units."""
    view = copy.deepcopy(item)
    display = item.get('display', {})
    rows = [item['rows'][i] for i in (display.get('row_order') or range(len(item['rows'])))]
    chosen = display.get('selected_result_ids', item['result_ids'])
    rows = [row for row in rows if row['result_id'] in chosen]
    series = display.get('series')
    if series and 'visible_series' in display:
        rows = [row for row in rows if str(row.get(series)) in display['visible_series']]
    if display.get('sort_by'):
        def sort_key(row):
            value = row.get(display['sort_by'])
            return (value is None, type(value).__name__, value if value is not None else '')
        rows = sorted(rows, key=sort_key, reverse=not display.get('ascending', True))
    by_key = {col['key']: col for col in item['columns']}
    view['columns'] = [copy.deepcopy(by_key[key]) for key in display.get('column_order', by_key)]
    for column in view['columns']:
        column['label'] = display.get('column_labels', {}).get(column['key'], column['label'])
    view['rows'] = [{key: row.get(key) for key in [*(col['key'] for col in view['columns']), 'result_id']}
                    for row in rows]
    view['title'] = display.get('title', item['title'])
    used = {row['result_id'] for row in rows}
    view['result_ids'] = [result_id for result_id in chosen if result_id in used]
    for field in ('producers', 'result_definitions'):
        if field in view['metadata']:
            view['metadata'][field] = {result_id: value for result_id, value in view['metadata'][field].items()
                                        if result_id in view['result_ids']}
    return view


def gallery_items(root, gallery_spec_path, query='', filters=None):
    """List/search saved displays; no producer reads, checks or calculation runs."""
    _, registry = gallery_registry(root, gallery_spec_path)
    terms = query.casefold().split()
    items = []
    for item in registry.get('items', {}).values():
        searchable = json.dumps({key: item.get(key) for key in
                                ('id', 'title', 'kind', 'result_ids', 'metadata', 'interpretation', 'findings', 'issues', 'adoption_decision', 'status', 'links', 'display')},
                               ensure_ascii=False).casefold()
        matched = True
        for key, value in (filters or {}).items():
            if not value:
                continue
            if key not in GALLERY_FILTERS:
                raise ValueError('Unknown gallery filter: ' + key)
            candidates = (item['result_ids'] if key == 'result_id' else [item['status']] if key == 'adoption'
                          else [item['metadata'].get(key), *[meta.get(key) for meta in item['metadata'].get('result_definitions', {}).values()]])
            if not any(str(value).casefold() in json.dumps(candidate, ensure_ascii=False).casefold() for candidate in candidates if candidate is not None):
                matched = False
                break
        if matched and all(term in searchable for term in terms):
            items.append(gallery_projection(item))
    return items


def gallery_compare(root, gallery_spec_path, item_ids):
    """Return explicitly selected saved displays and their defining differences."""
    items = {item['id']: item for item in gallery_items(root, gallery_spec_path)}
    if not item_ids or len(set(item_ids)) != len(item_ids) or set(item_ids) - set(items):
        raise ValueError('compare requires distinct existing gallery item IDs')
    selected = [items[item_id] for item_id in item_ids]
    fields = ('sample', 'population', 'observation_unit', 'comparison', 'period',
              'variables', 'measurement_units', 'estimand', 'inference', 'outcome', 'specification',
              'sample_policy', 'weights', 'estimator', 'ci_kind', 'interval_type', 'reference_event_time')
    differences = {key: {item['id']: item['metadata'].get(key) for item in selected}
                   for key in fields if any(item['metadata'].get(key) != selected[0]['metadata'].get(key)
                                             for item in selected[1:])}
    return {'items': selected, 'definition_differences': differences,
            'regression_table': gallery_regression_comparison(selected)}


def saved_display_definitions(result_id, saved):
    """Map a producer's display blocks into the existing registry.items contract."""
    definitions = []
    kinds = {'table1': 'descriptive', 'table': 'table', 'regression': 'table', 'balance': 'group_comparison',
             'sample-flow': 'sample_composition', 'trend': 'time_series', 'event-study': 'event_study',
             'iv': 'coefficient', 'rdd': 'figure', 'heterogeneity': 'coefficient',
             'sensitivity': 'robustness', 'counterfactual': 'figure'}
    def visit(block, path):
        if not isinstance(block, dict):
            return
        if isinstance(block.get('rows'), list) and block['rows']:
            rows = copy.deepcopy(block['rows'])
            source_kind = block.get('kind', 'table')
            kind = kinds.get(source_kind, source_kind)
            keys = list(dict.fromkeys(key for row in rows for key in row if key != 'result_id'))
            metadata = gallery_display_metadata(block.get('metadata', {}))
            metadata['display_source'] = {'result_id': result_id, 'key': path}
            if source_kind == 'regression':
                metadata['table_type'] = 'regression'
            columns = [{'key': key, 'label': GALLERY_LABELS.get(key, key), 'unit': ''} for key in keys]
            distribution_type = metadata.get('distribution_type', 'histogram')
            x = next((key for key in ('event_time', 'period', 'running', 'bin_mid', 'x', 'term', 'scenario', 'group') if key in keys), None)
            y = next((key for key in ('estimate', 'value', 'mean', 'count', 'density', 'middle', 'n') if key in keys), None)
            if kind in ('descriptive', 'sample_composition', 'group_comparison', 'table'):
                plot_type = 'table'
            elif kind == 'distribution':
                plot_type = {'histogram': 'bar', 'density': 'density', 'ecdf': 'ecdf', 'box': 'box'}[distribution_type]
            else:
                plot_type = {'coefficient': 'coefficient', 'event_study': 'event_study'}.get(kind, 'line')
            if x is None or y is None:
                plot_type = 'table'
            display = {'plot_type': plot_type, 'style': 'paper',
                       'formats': {key: '.3g' for key in keys if any(type(row.get(key)) in (int, float) for row in rows)}}
            if source_kind == 'table1':
                display['column_order'] = [key for key in keys if key in ('variable', 'group', 'mean', 'sd', 'median', 'n', 'unit') or key.startswith('q')]
                display['height'] = max(300, min(1600, 160 + len(rows) * 34))
            if plot_type != 'table':
                for column in columns:
                    if column['key'] == y:
                        column['unit'] = metadata.get('unit', '')
                    if column['key'] == x and kind == 'distribution' and plot_type != 'box':
                        column['unit'] = metadata.get('outcome_unit', '')
                display.update(x=x, y=y, series='group' if 'group' in keys else 'series' if 'series' in keys else None,
                               lower='ci_low' if 'ci_low' in keys else None, upper='ci_high' if 'ci_high' in keys else None)
                if plot_type == 'coefficient':
                    display['orientation'] = 'horizontal'
            suffix = '-'.join(path[1:]) or source_kind
            identity = result_id + '-' + re.sub(r'[^A-Za-z0-9_-]', '_', suffix)
            definitions.append({'id': identity, 'title': block.get('title', result_id + ' / ' + suffix),
                                'kind': kind, 'result_ids': [result_id], 'columns': columns,
                                'rows': rows, 'metadata': metadata, 'display': display})
        for key, value in block.items():
            if key not in ('rows', 'columns', 'metadata', 'kind') and isinstance(value, dict):
                visit(value, path + [key])
    visit(saved.get('display'), ['display'])
    return definitions


def prepare_gallery_items(registry, definitions=None):
    """Register authored display rows, or project named quantities from saved results."""
    if definitions is None:
        definitions = list(registry.get('items', {}).values())
        if not definitions:
            for result_id, record in registry['records'].items():
                saved = record.get('source_result') or {}
                saved_items = copy.deepcopy(saved.get('display_items', [])) or saved_display_definitions(result_id, saved)
                if saved_items:
                    definitions.extend(saved_items)
                else:
                    prefix = result_id + '.'
                    quantities = {key[len(prefix):]: value for key, value in registry.get('statistics', {}).items()
                                  if key.startswith(prefix)}
                    coefficients = [key.removeprefix('coefficient.') for key in quantities if key.startswith('coefficient.')]
                    if coefficients:
                        rows = []
                        for term in coefficients:
                            estimate = quantities['coefficient.' + term]
                            rows.append({'term': term, 'estimate': estimate['value'], 'unit': estimate['unit'],
                                         'standard_error': quantities.get('standard_error.' + term, {}).get('value'),
                                         'lower': quantities.get('confidence_95_lower.' + term, {}).get('value'),
                                         'upper': quantities.get('confidence_95_upper.' + term, {}).get('value'),
                                         'p_value': quantities.get('p_value.' + term, {}).get('value')})
                        definitions.append({'id': result_id + '-coefficients', 'title': result_id + ' coefficients',
                                            'kind': 'coefficient', 'result_ids': [result_id], 'rows': rows,
                                            'columns': [{'key': key, 'label': key.replace('_', ' '), 'unit': ''}
                                                        for key in ('term', 'estimate', 'standard_error', 'lower', 'upper', 'p_value', 'unit')],
                                            'metadata': {'table_type': 'regression'},
                                            'display': {'plot_type': 'table', 'x': 'term', 'y': 'estimate',
                                                        'lower': 'lower', 'upper': 'upper', 'series': 'term'}})
                    elif quantities:
                        definitions.append({'id': result_id + '-statistics', 'title': result_id + ' saved statistics',
                                            'kind': 'descriptive', 'result_ids': [result_id],
                                            'rows': [{'statistic': key, 'value': value['value'], 'unit': value['unit']}
                                                     for key, value in quantities.items()],
                                            'columns': [{'key': key, 'label': key.title(), 'unit': ''}
                                                        for key in ('statistic', 'value', 'unit')]})
    if not isinstance(definitions, list):
        raise ValueError('gallery registration requires a list of display items')
    items = {}
    for definition in definitions:
        item = copy.deepcopy(definition)
        ids = item.get('result_ids', [])
        if not isinstance(ids, list) or not ids:
            raise ValueError('each display must identify its producing saved results')
        metadata = gallery_metadata(registry, ids)
        supplied = gallery_display_metadata(item.get('metadata', {}))
        if not isinstance(supplied, dict):
            raise ValueError('display metadata must be an object')
        item['metadata'] = {**metadata, **supplied, 'producers': metadata['producers'],
                            'result_definitions': metadata['result_definitions']}
        if len(ids) == 1:
            item['metadata']['result_definitions'][ids[0]].update({key: copy.deepcopy(value) for key, value in supplied.items() if key not in ('producers', 'result_definitions')})
        item.setdefault('files', [])
        item.setdefault('interpretation', '')
        item.setdefault('status', 'candidate')
        item.setdefault('links', {'tasks': [], 'documents': []})
        display = item.setdefault('display', {})
        defaults = {'coefficient': 'coefficient', 'event_study': 'event_study',
                    'distribution': 'bar', 'time_series': 'line', 'group_comparison': 'bar'}
        display.setdefault('plot_type', defaults.get(item.get('kind'), 'table'))
        display.setdefault('width', 960)
        display.setdefault('height', 540)
        for row in item.get('rows', []):
            if isinstance(row, dict) and len(ids) == 1:
                row.setdefault('result_id', ids[0])
        validate_gallery_item(item)
        if item['id'] in items:
            raise ValueError('duplicate gallery item: ' + item['id'])
        items[item['id']] = item
    return items


def gallery_cell(value, key, display):
    if value is None:
        return '—'
    if type(value) in (int, float) and key in display.get('formats', {}):
        return format(value, display['formats'][key])
    return str(value)


def gallery_regression_comparison(items):
    models, definitions = {}, {}
    for item in items:
        for row in item['rows']:
            if 'term' in row and 'estimate' in row:
                models.setdefault(row['result_id'], {})[str(row['term'])] = row
                definitions[row['result_id']] = item['metadata'].get('result_definitions', {}).get(row['result_id'], {})
    rows = []
    terms = list(dict.fromkeys(term for model in models.values() for term in model))
    for term in terms:
        for keys, label in [(('estimate',), '推定値'), (('se', 'standard_error'), '標準誤差'),
                            (('ci_low', 'lower'), '区間下端'), (('ci_high', 'upper'), '区間上端'),
                            (('p_value',), 'p 値'), (('unit',), '単位')]:
            if any(any(key in model.get(term, {}) for key in keys) for model in models.values()):
                rows.append({'quantity': term + ' / ' + label, **{identity: next((model.get(term, {})[key] for key in keys if key in model.get(term, {})), None) for identity, model in models.items()}})
    fields = [('n', '観測数'), ('n_clusters', 'クラスタ数'), ('fixed_effects', '固定効果'),
              ('controls', '統制変数'), ('period', '期間'), ('sample', 'サンプル'),
              ('sample_policy', 'サンプル方式'), ('weights', '重み'), ('estimator', '推定法'),
              ('specification', '仕様'), ('ci_kind', '区間の種類'), ('interval_type', '保存区間'),
              ('confidence_level', '区間水準'), ('reference_distribution', '参照分布'),
              ('degrees_of_freedom', '自由度'), ('unit', '単位')]
    for key, label in fields:
        if any(key in metadata for metadata in definitions.values()):
            values = {identity: metadata.get(key) for identity, metadata in definitions.items()}
            rows.append({'quantity': label, **{identity: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value for identity, value in values.items()}})
    return {'rows': rows, 'columns': [{'key': 'quantity', 'label': '項目', 'unit': ''},
                                     *[{'key': identity, 'label': identity, 'unit': ''} for identity in models]]}


def gallery_notes(item):
    notes = list(item.get('display', {}).get('notes', []))
    labels = {'sample': 'サンプル', 'sample_policy': 'サンプル方式', 'period': '期間', 'unit': '単位',
              'ci_kind': '区間', 'interval_type': '保存区間', 'confidence_level': '区間水準',
              'reference_time': '基準期', 'reference_event_time': '基準イベント期',
              'n': '観測数', 'n_clusters': 'クラスタ数', 'denominator': '分母',
              'quantile_method': '分位点', 'distribution_type': '分布表示'}
    metadata = item['metadata']
    shared = [label + ': ' + (json.dumps(metadata[key], ensure_ascii=False) if isinstance(metadata[key], (dict, list)) else str(metadata[key]))
              for key, label in labels.items() if metadata.get(key) is not None]
    if shared:
        notes.append(' / '.join(shared))
    for result_id, definition in metadata.get('result_definitions', {}).items():
        differences = [label + ': ' + (json.dumps(definition[key], ensure_ascii=False) if isinstance(definition[key], (dict, list)) else str(definition[key]))
                       for key, label in labels.items() if key in definition and definition[key] != metadata.get(key)]
        if differences:
            notes.append(result_id + ': ' + ' / '.join(differences))
    return notes


def gallery_table(item, markdown=False):
    view = gallery_projection(item)
    display = item.get('display', {})
    if item['metadata'].get('table_type') == 'regression':
        view = gallery_regression_comparison([view])
        display = {**display, 'formats': {**{col['key']: '.3g' for col in view['columns'][1:]}, **display.get('formats', {})}}
    headings = [col['label'] + (' (' + col['unit'] + ')' if col['unit'] else '') for col in view['columns']]
    cells = [[gallery_cell(row.get(col['key']), col['key'], display) for col in view['columns']]
             for row in view['rows']]
    if markdown:
        def line(values):
            return '| ' + ' | '.join(value.replace('|', '\\|').replace('\n', '<br>') for value in values) + ' |'
        return '\n'.join([line(headings), line(['---'] * len(headings)), *(line(row) for row in cells)]) + '\n'
    return ('<table><thead><tr>' + ''.join('<th>' + html.escape(value) + '</th>' for value in headings)
            + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + html.escape(value) + '</td>' for value in row)
                                              + '</tr>' for row in cells) + '</tbody></table>')


def gallery_plot(item):
    """Render saved aggregates or estimates; no statistic is computed here."""
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib import font_manager
    import textwrap
    display = item.get('display', {})
    view = gallery_projection({**item, 'display': {**display, 'column_order': [col['key'] for col in item['columns']]}})
    font_names = {font.name for font in font_manager.fontManager.ttflist}
    if 'Noto Sans CJK JP' not in font_names:
        for path in font_manager.findSystemFonts():
            if Path(path).name == 'NotoSansCJK-Regular.ttc':
                font_manager.fontManager.addfont(path)
        font_names = {font.name for font in font_manager.fontManager.ttflist}
    family = next((name for name in ('Noto Sans CJK JP', 'Noto Sans JP', 'IPAexGothic') if name in font_names), 'DejaVu Sans')
    font_size = display.get('font_size', 14 if display.get('style') == 'presentation' else 10)
    figure = Figure(figsize=(display.get('width', 960) / 100, display.get('height', 540) / 100), dpi=100)
    FigureCanvasAgg(figure)
    axis = figure.subplots()
    title = display.get('title', item['title'])
    figure.suptitle(title, fontsize=font_size + 4, fontfamily=family, x=0.06, ha='left')
    axis.tick_params(labelsize=font_size)
    plot_type = display.get('plot_type', 'table')
    if plot_type == 'table':
        table_view = gallery_projection(item)
        if item['metadata'].get('table_type') == 'regression':
            table_view = gallery_regression_comparison([table_view])
            display = {**display, 'formats': {**{col['key']: '.3g' for col in table_view['columns'][1:]}, **display.get('formats', {})}}
        headings = [col['label'] + ('\n' + col['unit'] if col['unit'] else '') for col in table_view['columns']]
        cells = [[gallery_cell(row.get(col['key']), col['key'], display) for col in table_view['columns']]
                 for row in table_view['rows']]
        axis.set_axis_off()
        if cells:
            table_artist = axis.table(cellText=cells, colLabels=headings, loc='center', cellLoc='left')
            table_artist.auto_set_font_size(False)
            table_artist.set_fontsize(max(8, font_size - max(0, len(headings) - 8)))
            table_artist.scale(1, 1.6)
            for (row, _), cell in table_artist.get_celld().items():
                cell.set_edgecolor('#d9e2ec')
                cell.get_text().set_fontfamily(family)
                if row == 0:
                    cell.set_facecolor('#eaf1f7')
                    cell.get_text().set_weight('bold')
                    if any('\n' in heading for heading in headings):
                        cell.set_height(cell.get_height() * 1.7)
    else:
        xkey, ykey = display.get('x'), display.get('y')
        if not xkey or not ykey:
            raise ValueError('plot display requires x and y saved column keys')
        rows = view['rows']
        units = {row.get('unit') for row in rows if row.get(ykey) is not None and row.get('unit')}
        if len(units) > 1:
            raise ValueError('One plot axis requires one saved unit; select matching saved series')
        if any(row.get(ykey) is not None and type(row[ykey]) not in (int, float) for row in rows):
            raise ValueError('plot y column must contain numeric saved values or null')
        labels = list(dict.fromkeys(row.get(xkey) for row in rows if row.get(xkey) is not None))
        categorical = any(type(value) not in (int, float) for value in labels)
        groups = list(dict.fromkeys(str(row.get(display['series'])) for row in rows)) if display.get('series') else ['']
        groups = [group for group in display.get('series_order', []) if group in groups] + [group for group in groups if group not in display.get('series_order', [])]
        horizontal = display.get('orientation') == 'horizontal'
        for index, group in enumerate(groups):
            selected = [row for row in rows if row.get(xkey) is not None and
                        (not display.get('series') or str(row.get(display['series'])) == group)]
            xs = [labels.index(row[xkey]) if categorical else row[xkey] for row in selected]
            ys = [row[ykey] if row.get(ykey) is not None else float('nan') for row in selected]
            color = display.get('colors', {}).get(group, ['#245b8a', '#b4513b', '#31836b', '#8a5b9e'][index % 4])
            kwargs = {'label': display.get('series_labels', {}).get(group, group) or None, 'color': color}
            if plot_type == 'box':
                for offset, row in enumerate(selected):
                    if any(type(row.get(key)) not in (int, float) for key in ('ymin', 'lower', 'middle', 'upper', 'ymax')):
                        raise ValueError('Box plots require saved ymin/lower/middle/upper/ymax statistics')
                    axis.bxp([{'label': kwargs['label'] or str(row[xkey]), 'whislo': row['ymin'], 'q1': row['lower'],
                               'med': row['middle'], 'q3': row['upper'], 'whishi': row['ymax']}],
                             positions=[index + offset * .15], widths=.5, showfliers=False,
                             vert=not horizontal, patch_artist=True,
                             boxprops={'facecolor': color, 'alpha': .55}, medianprops={'color': '#172938'})
                continue
            if plot_type == 'bar':
                histogram = item['metadata'].get('distribution_type') == 'histogram'
                width = [row['bin_high'] - row['bin_low'] for row in selected] if histogram else .8 / max(1, len(groups))
                positions = xs if histogram else [x + (index - (len(groups) - 1) / 2) * width for x in xs]
                if horizontal:
                    axis.barh(positions, ys, height=width, **kwargs)
                else:
                    axis.bar(positions, ys, width=width, alpha=.6 if histogram else 1, **kwargs)
            elif plot_type in ('scatter', 'coefficient'):
                axis.scatter(ys if horizontal else xs, xs if horizontal else ys, s=35, **kwargs)
            elif plot_type == 'area':
                if horizontal:
                    axis.fill_betweenx(xs, ys, alpha=.3, **kwargs)
                else:
                    axis.fill_between(xs, ys, alpha=.3, **kwargs)
            else:
                axis.plot(ys if horizontal else xs, xs if horizontal else ys,
                          marker=None if plot_type in ('density', 'ecdf') else 'o',
                          drawstyle='steps-post' if plot_type in ('step', 'ecdf') else 'default', **kwargs)
            if display.get('lower') and display.get('upper'):
                for x, row in zip(xs, selected):
                    lower, upper = row.get(display['lower']), row.get(display['upper'])
                    if lower is None or upper is None:
                        continue
                    if type(lower) not in (int, float) or type(upper) not in (int, float) or lower > upper:
                        raise ValueError('saved interval endpoints must be ordered numeric values or null')
                    if horizontal:
                        axis.hlines(x, lower, upper, color=color, linewidth=1.5)
                    else:
                        axis.vlines(x, lower, upper, color=color, linewidth=1.5)
        if categorical and plot_type != 'box':
            if horizontal:
                axis.set_yticks(range(len(labels)), [str(value) for value in labels])
            else:
                axis.set_xticks(range(len(labels)), [str(value) for value in labels])
        column_labels = {col['key']: col['label'] + (' (' + col['unit'] + ')' if col['unit'] else '')
                         for col in view['columns']}
        axis.set_xlabel(display.get('x_label', column_labels[ykey if horizontal else xkey]), fontfamily=family)
        axis.set_ylabel(display.get('y_label', column_labels[xkey if horizontal else ykey]), fontfamily=family)
        if plot_type in ('coefficient', 'event_study'):
            (axis.axvline if horizontal else axis.axhline)(0, color='#73808c', linewidth=.8)
        if plot_type == 'event_study':
            references = [item['metadata'], *item['metadata'].get('result_definitions', {}).values()]
            times = {meta.get('reference_event_time', meta.get('reference_time')) for meta in references}
            for reference in times:
                if type(reference) in (int, float):
                    (axis.axhline if horizontal else axis.axvline)(reference, color='#73808c', linewidth=.8, linestyle='--')
        for axis_name in ('x', 'y'):
            if display.get(axis_name + '_scale', 'linear') != 'linear':
                getattr(axis, 'set_' + axis_name + 'scale')(display[axis_name + '_scale'])
            if display.get(axis_name + '_limits') is not None:
                getattr(axis, 'set_' + axis_name + 'lim')(*display[axis_name + '_limits'])
        if plot_type == 'box':
            tick_labels = [display.get('series_labels', {}).get(group, group) for group in groups]
            (axis.set_yticks if horizontal else axis.set_xticks)(range(len(groups)), tick_labels)
        axis.spines[['top', 'right']].set_visible(False)
        axis.grid(axis='x' if horizontal else 'y', alpha=.18)
        if display.get('legend', True) and groups != [''] and axis.get_legend_handles_labels()[0]:
            axis.legend(loc=display.get('legend_location', 'best'), frameon=False, prop={'family': family})
        for label in [*axis.get_xticklabels(), *axis.get_yticklabels()]:
            label.set_fontfamily(family)
    notes = '\n'.join(textwrap.fill(note, max(35, display.get('width', 960) // 9)) for note in gallery_notes(item))
    bottom = min(.4, .06 + .035 * len(notes.splitlines())) if notes else .03
    if notes:
        figure.text(.06, .02, notes, fontsize=9, color='#425466', va='bottom', fontfamily=family)
    figure.tight_layout(rect=(.02, bottom, .99, .94))
    return figure


def gallery_preview(item, svg=None):
    """Build an in-memory preview from saved rows and a candidate display config."""
    validate_gallery_item(item)
    if item.get('display', {}).get('plot_type', 'table') == 'table':
        body = gallery_table(item)
    elif svg is not None:
        body = svg
    else:
        stream = io.StringIO()
        gallery_plot(item).savefig(stream, format='svg')
        body = stream.getvalue()
    if item.get('display', {}).get('plot_type', 'table') == 'table':
        title = html.escape(item.get('display', {}).get('title', item['title']))
        notes = ''.join('<p>' + html.escape(note) + '</p>' for note in gallery_notes(item))
        body = '<h3>' + title + '</h3>' + body + notes
    return ('<section class="research-display"><style>.research-display{font-family:system-ui,sans-serif;color:#213547;}'
            '.research-display table{border-collapse:collapse;width:100%;font-size:14px;}'
            '.research-display th,.research-display td{padding:9px 12px;border-bottom:1px solid #d9e2ec;text-align:left;}'
            '.research-display th{background:#eaf1f7;}.research-display svg{max-width:100%;height:auto;}'
            '.research-display p{font-size:13px;color:#425466;}</style>'
            + body + '</section>')


def gallery_latex(item):
    escapes = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}
    def escape(value):
        return ''.join(escapes.get(char, char) for char in str(value))
    is_table = item.get('display', {}).get('plot_type', 'table') == 'table'
    lines = [r'\begin{table}[htbp]' if is_table else r'\begin{figure}[htbp]', r'\centering']
    if is_table:
        view = gallery_projection(item)
        if item['metadata'].get('table_type') == 'regression':
            view = gallery_regression_comparison([view])
        columns = view['columns']
        lines += [r'\begin{tabular}{' + 'l' + 'r' * (len(columns) - 1) + '}', r'\hline',
                  ' & '.join(escape(column['label']) for column in columns) + r' \\', r'\hline']
        lines += [' & '.join(escape(gallery_cell(row.get(column['key']), column['key'], item.get('display', {}))) for column in columns) + r' \\' for row in view['rows']]
        lines += [r'\hline', r'\end{tabular}']
    else:
        lines.append(r'\includegraphics[width=\linewidth]{display.pdf}')
    lines += [r'\caption{' + escape(item.get('display', {}).get('title', item['title'])) + '}',
              r'\par\small ' + escape(' / '.join(gallery_notes(item))),
              r'\end{table}' if is_table else r'\end{figure}']
    return '\n'.join(lines) + '\n'


def render_gallery_item(root, item, assets):
    """Publish one complete display generation and return its relative paths."""
    root = Path(root).resolve(strict=True)
    validate_gallery_item(item)
    assets = Path(assets)
    if assets.is_absolute():
        assets = assets.relative_to(root)
    assets = root / state.relative(root, assets.as_posix(), exists=False)
    import matplotlib
    version = state.content_hash({'renderer': GALLERY_RENDER_VERSION, 'matplotlib': matplotlib.__version__,
                                  'item': {key: item[key] for key in ('id', 'title', 'rows', 'columns', 'display', 'metadata')}})[:20]
    destination = assets / (item['id'] + '-' + version)
    filenames = ['display.svg', 'display.png', 'display.html', 'display.pdf', 'display.tex']
    if not destination.exists():
        assets.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.display-', dir=assets) as temporary:
            temporary = Path(temporary)
            figure = gallery_plot(item)
            for extension in ('svg', 'png', 'pdf'):
                figure.savefig(temporary / ('display.' + extension), format=extension)
            (temporary / 'display.html').write_text(gallery_preview(item, (temporary / 'display.svg').read_text(encoding='utf8')), encoding='utf8')
            (temporary / 'display.tex').write_text(gallery_latex(item), encoding='utf8')
            os.replace(temporary, destination)
    return [(destination / filename).relative_to(root).as_posix() for filename in filenames]


def register_gallery(root, gallery_spec_path, definitions=None, output=None, assets=None):
    """Add saved display rows/provenance to the existing registry and render them."""
    root = Path(root).resolve(strict=True)
    source, registry = gallery_registry(root, gallery_spec_path)
    target = Path(output) if output is not None else source
    if target.is_absolute():
        target = target.relative_to(root)
    target = root / state.relative(root, target.as_posix(), exists=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    with state.locked(target):
        if target == source:
            _, registry = gallery_registry(root, source)
        prepared = prepare_gallery_items(registry, definitions)
        for item in prepared.values():
            item['files'] = render_gallery_item(root, item, assets or target.parent / 'gallery-assets')
        registry.setdefault('items', {}).update(prepared)
        state.save(target, registry)
    return {'registry': target.relative_to(root).as_posix(), 'item_ids': list(prepared)}


def gallery_edit_kind(changes):
    if not isinstance(changes, dict) or not changes:
        raise ValueError('provide the selected item fields to change')
    if set(changes) <= {'title', 'display'}:
        return 'display'
    if set(changes) <= {'interpretation', 'status', 'links', 'findings', 'issues', 'adoption_decision'}:
        return 'interpretation'
    if set(changes) <= {'title', 'display', 'interpretation', 'status', 'links', 'findings', 'issues', 'adoption_decision'}:
        raise ValueError('save display and interpretation edits separately')
    return 'scientific'


def edit_gallery_item(root, gallery_spec_path, item_id, changes, expected_revision=None):
    """Save an explicit display or interpretation edit; preserve scientific rows."""
    root = Path(root).resolve(strict=True)
    path, _ = gallery_registry(root, gallery_spec_path)
    kind = gallery_edit_kind(changes)
    if kind == 'scientific':
        raise ValueError('scientific edits require an adopted specification and separately registered result')
    with state.locked(path):
        _, registry = gallery_registry(root, path)
        if item_id not in registry.get('items', {}):
            raise ValueError('unknown gallery item: ' + item_id)
        previous = registry['items'][item_id]
        if expected_revision is not None and state.content_hash(previous) != expected_revision:
            raise ValueError('gallery item changed; reload its saved version before editing')
        item = copy.deepcopy(previous)
        for key, value in changes.items():
            if key == 'display':
                if not isinstance(value, dict):
                    raise ValueError('display changes must be an object')
                item['display'].update(copy.deepcopy(value))
            else:
                item[key] = copy.deepcopy(value)
        validate_gallery_item(item)
        changed = [key for key in changes if item[key] != previous.get(key)]
        if kind == 'display' and changed:
            item['files'] = render_gallery_item(root, item, path.parent / 'gallery-assets')
            changed.append('files')
        if changed:
            registry['items'][item_id] = item
            state.save(path, registry)
    return {'item': gallery_projection(item), 'edit_kind': kind,
            'changed_references': [{'kind': 'json', 'path': path.relative_to(root).as_posix(),
                                    'keys': ['items', item_id, key]} for key in changed]}


def latex_assets(root, require_adapters=True):
    """Resolve canonical templates and generated adapters in each supported layout."""
    roots=[root/'tex',root/'.agents'/'tex']
    names={'paper_source':('paper','ecta_template.tex','ecta_template.tex'),
           'paper_class':('paper','econsocart.cls','econsocart.cls'),
           'paper_config':('paper','econsocart.cfg','econsocart.cfg'),
           'paper_style':('paper','ecta-fullname.bst','ecta-fullname.bst'),
           'slides_source':('slides','main.tex','main.tex'),
           'paper_adapter':('paper','pandoc_template.latex','paper_pandoc_template.latex'),
           'slides_adapter':('slides','pandoc_template.latex','slides_pandoc_template.latex')}
    assets={}
    for key,(folder,name,flat) in names.items():
        options=[p/folder/name for p in roots]+[root/flat,Path(__file__).resolve().parent.parent/'tex'/folder/name,Path(__file__).resolve().parent/flat]
        assets[key]=next((p.resolve() for p in options if p.is_file()),None)
        if assets[key] is None and (require_adapters or not key.endswith('_adapter')): raise ValueError('Missing LaTeX asset: '+key)
    builders=[root/'scripts/build_latex.py',root/'.agents'/'scripts/build_latex.py',root/'build_latex.py',Path(__file__).resolve().parent/'build_latex.py']
    assets['builder']=next((p.resolve() for p in builders if p.is_file()),None)
    if assets['builder'] is None: raise ValueError('Missing LaTeX build helper')
    return assets


def latex_adapter(source, kind):
    """Replace only content slots in the user-supplied template."""
    def replace_once(body, old, new):
        if body.count(old)!=1: raise ValueError('LaTeX template slot changed: '+kind)
        return body.replace(old,new,1)
    common=('$if(bibliography)$$else$\\let\\econbibstyle\\bibliographystyle\n'
            '\\renewcommand{\\bibliographystyle}[1]{}\n$endif$'
            '$common.latex()$\n$if(bibliography)$$else$\\let\\bibliographystyle\\econbibstyle\n$endif$'
            '$if(standalone-renderer)$\n$for(header-includes)$\n$header-includes$\n$endfor$\n$endif$\n')
    if kind=='paper':
        common += '\\usepackage{needspace}\n\\BeforeBeginEnvironment{longtable}{\\Needspace{12\\baselineskip}}\n'
        source=replace_once(source,'\\documentclass[ecta,nameyear,draft]{econsocart}', '\\RequirePackage{fontspec}\n\\def\\econselectedclass{$documentclass$}\n\\def\\econjournalclass{econsocart}\n\\ifx\\econselectedclass\\econjournalclass\n\\documentclass[ecta,nameyear,draft]{econsocart}\n\\else\n\\documentclass[$for(classoption)$$classoption$$sep$,$endfor$]{$documentclass$}\n\\fi')
        source=replace_once(source,'\\startlocaldefs',common+'\\newcounter{pandocauthor}\n\\newcommand{\\pandocauthor}[1]{\\stepcounter{pandocauthor}\\author[id=au\\arabic{pandocauthor},addressref={add1}]{\\fnms{}~\\snm{#1}\\ead[label=e\\arabic{pandocauthor}]{}}}\n\\ifx\\econselectedclass\\econjournalclass\n\\startlocaldefs')
        source=replace_once(source,'\\endlocaldefs','\\endlocaldefs\n\\fi')
        source=replace_once(source,'\\begin{frontmatter}','\\ifx\\econselectedclass\\econjournalclass\n\\begin{frontmatter}')
        source=replace_once(source,'\\end{frontmatter}', '\\end{frontmatter}\n\\else\n$if(title)$\\title{$title$}$endif$\n\\author{$for(author)$$author$$sep$ \\and $endfor$}\n$if(date)$\\date{$date$}$endif$\n$if(title)$\\maketitle$endif$\n$if(abstract)$\\begin{abstract}$abstract$\\end{abstract}$endif$\n$if(keywords)$\\noindent\\textbf{Keywords:} $for(keywords)$$keywords$$sep$, $endfor$$endif$\n\\fi')
        source=replace_once(source,'\\title{???}\n\\runtitle{???}', '$if(title)$\\title{$title$}\n\\runtitle{$title$}$endif$')
        source=replace_once(source,'\\author[id=au1,addressref={add1}]{\\fnms{}~\\snm{}\\ead[label=e1]{}}', '$for(author)$\\pandocauthor{$author$}\n$endfor$')
        source=replace_once(source,'\\begin{abstract}\n???\n\\end{abstract}', '$if(abstract)$\\begin{abstract}\n$abstract$\n\\end{abstract}$endif$')
        source=replace_once(source,'\\begin{keyword}\n\\kwd{???}\n\\kwd{???}\n\\end{keyword}', '$if(keywords)$\\begin{keyword}\n$for(keywords)$\\kwd{$keywords$}\n$endfor$\\end{keyword}$endif$')
        source=replace_once(source,'\\section{???}\n???', '$body$')
        source=replace_once(source,'\\bibliographystyle{ecta-fullname} % Style BST file', '% Bibliography style is set to ecta-fullname by the renderer.')
        source=replace_once(source,'\\bibliography{../bibliography}  % Bibliography file (usually \'*.bib\')', '$if(bibliography)$\\bibliography{$for(bibliography)$$bibliography$$sep$,$endfor$}$endif$')
    elif kind=='slides':
        source=replace_once(source,'\\documentclass[unicode, mathserif, m, 12pt, unknownkeysallowed]{beamer}', '\\documentclass[unicode, mathserif, m, $if(fontsize)$$fontsize$$else$12pt$endif$, unknownkeysallowed$if(aspectratio)$,aspectratio=$aspectratio$$endif$]{beamer}')
        source=replace_once(source,'\\usetheme[numbering=fraction]{metropolis}', '$if(theme)$\\usetheme{$theme$}$else$\\usetheme[numbering=fraction]{metropolis}$endif$')
        source=replace_once(source,'\\title[Footer title]{TITLE}\n\\subtitle{SUBTITLE}\n\\author{Author}\n\\institute{}\n\\date{\\today}', '$if(title)$\\title{$title$}$endif$\n$if(subtitle)$\\subtitle{$subtitle$}$endif$\n\\author{$for(author)$$author$$sep$ \\and $endfor$}\n$if(institute)$\\institute{$institute$}$endif$\n\\date{$if(date)$$date$$else$\\today$endif$}')
        source=replace_once(source,'\\usepackage{amsmath}\n\\begin{document}', '\\usepackage{amsmath}\n'+common+'\\setbeamerfont{caption}{size=\\scriptsize}\n\\AtBeginEnvironment{longtable}{\\footnotesize\\setlength{\\tabcolsep}{2pt}}\n\\begin{document}')
        start=source.index('\\begin{frame}{}'); end=source.index('\\appendix',start)
        source=source[:start]+'$body$\n\n'+source[end:]
        source=replace_once(source,'\\begin{frame}{References}', '$if(bibliography)$\\begin{frame}{References}')
        source=replace_once(source,'\\bibliography{../bibliography}  % Bibliography file (usually \'*.bib\')', '\\bibliography{$for(bibliography)$$bibliography$$sep$,$endfor$}')
        source=replace_once(source,'\\end{frame}\n\n\\end{document}', '\\end{frame}$endif$\n\n\\end{document}')
        source=replace_once(source,'\\bibliographystyle{../paper/ecta-fullname} % Style BST file', '% Bibliography style is set to ecta-fullname by the renderer.')
    else: raise ValueError('Unknown LaTeX template kind')
    return source


def explicit_latex_options(source,pandoc,target):
    """Read the document's own Pandoc/Quarto choices before selecting a default."""
    result=subprocess.run([pandoc,'-f','markdown','-t','json',str(source)],check=True,capture_output=True,text=True)
    meta=json.loads(result.stdout).get('meta',{})
    def unpack(value):
        if not isinstance(value,dict): return None
        kind,content=value.get('t'),value.get('c')
        if kind=='MetaString': return content
        if kind=='MetaBool': return content
        if kind=='MetaMap': return {k:unpack(v) for k,v in content.items()}
        if kind=='MetaList': return [unpack(v) for v in content]
        if kind=='MetaInlines':
            return ''.join(' ' if v.get('t') in ('Space','SoftBreak','LineBreak') else v.get('c','')
                           for v in content if isinstance(v,dict) and isinstance(v.get('c',''),str))
        return None
    values={k:unpack(v) for k,v in meta.items()}
    options={k:values[k] for k in ('documentclass','theme','template','classoption') if values.get(k)}
    if values.get('bibliography'): options['_bibliography']=values['bibliography']
    formats=values.get('format')
    if isinstance(formats,dict):
        selected=formats.get('beamer' if target=='slides' else 'pdf')
        if isinstance(selected,dict):
            options.update({k:selected[k] for k in ('documentclass','theme','template','classoption') if selected.get(k)})
    return options


def chosen_template(root, origin, value):
    candidate=Path(value)
    if candidate.is_absolute(): return candidate.resolve(strict=True)
    for base in (Path(origin).resolve().parent,root):
        found=base/candidate
        if found.is_file(): return found.resolve()
    raise ValueError('Missing document template: '+str(value))


def render_latex(root, source, figure_svg, figure_pdf, target, output, pandoc, python, pdf=False, origin=None):
    assets=latex_assets(root); adapter=assets[target+'_adapter']
    choices=explicit_latex_options(source,pandoc,target)
    choices.pop('_bibliography',None)
    if 'template' in choices:
        selected=chosen_template(root,origin or source,choices['template'])
        if selected==adapter: choices.pop('template')
        else: choices['template']=str(selected)
    if not choices and adapter.read_text(encoding='utf8')!=latex_adapter(assets[target+'_source'].read_text(encoding='utf8'),target):
        raise ValueError('Generated LaTeX adapter is stale')
    output=Path(output).resolve()
    with tempfile.TemporaryDirectory(prefix='research-latex-') as tmp:
        tmp=Path(tmp); manuscript=tmp/'input.qmd'; tex=tmp/'document.tex'
        manuscript.write_text(Path(source).read_text(encoding='utf8').replace(str(Path(figure_svg).resolve()),str(Path(figure_pdf).resolve())),encoding='utf8')
        env=os.environ.copy()
        directories=list(dict.fromkeys(str(assets[k].parent) for k in ('paper_class','paper_config','paper_style')))
        for key in ('TEXINPUTS','BSTINPUTS'):
            env[key]=os.pathsep.join(directories+[env.get(key,'')])
        env['BIBINPUTS']=os.pathsep.join([str(Path(origin or source).resolve().parent),str(root),env.get('BIBINPUTS','')])
        if choices:
            command=[pandoc,'-f','markdown',str(manuscript),'-s','-t','beamer' if target=='slides' else 'latex','-o',str(output if pdf else tex)]
            if pdf: command+=['--pdf-engine=lualatex']
            for key in ('documentclass','theme','classoption'):
                if key in choices:
                    values=choices[key] if isinstance(choices[key],list) else [choices[key]]
                    for value in values: command+=['-V',key+'='+str(value)]
            if 'template' in choices:
                command+=['--template',choices['template']]
            if target=='slides': command+=['--slide-level=1']
            subprocess.run(command,cwd=root,env=env,check=True)
            if not pdf: shutil.copyfile(tex,output)
            return
        command=[pandoc,'-f','markdown',str(manuscript),'-s','--natbib','-M','biblio-style=ecta-fullname','-V','standalone-renderer=true','--template',str(adapter),'-t','beamer' if target=='slides' else 'latex','-o',str(tex)]
        if target=='paper': command+=['-V','documentclass=econsocart']
        if target=='slides': command+=['--slide-level=1']
        subprocess.run(command,cwd=root,env=env,check=True)
        if pdf:
            subprocess.run([python,str(assets['builder']),str(tex)],cwd=root,env=env,check=True)
            shutil.copyfile(tex.with_suffix('.pdf'),output)
        else: shutil.copyfile(tex,output)


def load(path):
    return evidence.read_json(Path(path).read_bytes(),str(path))


def checked(root, path):
    return root / state.relative(root,path)


def ref(root,path):
    p=checked(root,path)
    return {'path':path,'sha256':state.digest(p)}


def validate_spec(root, spec):
    if not isinstance(spec,dict) or set(spec)-{'pipeline','sources','bindings','article_template','slides_template','figure','models'} or not {'pipeline','sources','bindings','article_template','slides_template','figure'}<=set(spec): raise ValueError('artifact specification has invalid fields')
    if not isinstance(spec['pipeline'],str) or not NAME.fullmatch(spec['pipeline']): raise ValueError('pipeline must be a simple name')
    if not isinstance(spec['sources'],list) or not spec['sources']: raise ValueError('at least one source is required')
    seen=set()
    for row in spec['sources']:
        if not isinstance(row,dict) or set(row)-{'id','result','specification','code','data','coefficient_units','expected_hashes','quantities','metadata'} or not {'id','result','code'}<=set(row): raise ValueError('source requires id, result and code; specification, data and coefficient_units are optional')
        name=row['id']
        if not isinstance(name,str) or not NAME.fullmatch(name) or name in seen: raise ValueError('source IDs must be distinct simple names')
        seen.add(name)
        for field in ('result','specification','code','data'):
            if field in row: checked(root,row[field])
        if any(not isinstance(row.get(key,{}),dict) for key in ('coefficient_units','expected_hashes','quantities','metadata')): raise ValueError('source units, hashes, quantities and metadata must be objects')
        if any(k not in ('code','data','specification') or k not in row or not isinstance(v,str) or not re.fullmatch(r'[0-9a-f]{64}',v) for k,v in row.get('expected_hashes',{}).items()): raise ValueError('expected hashes must identify selected input files')
    if not isinstance(spec['bindings'],dict) or not spec['bindings']: raise ValueError('bindings must be nonempty')
    for name,b in spec['bindings'].items():
        if not NAME.fullmatch(name) or not isinstance(b,dict) or set(b)!={'key','unit','format','display_unit','label'} or any(not isinstance(v,str) or not v for v in b.values()) or not FMT.fullmatch(b['format']): raise ValueError('binding requires key, unit, format, display_unit and label')
    for path in (spec['article_template'],spec['slides_template']): checked(root,path)
    if any('.' not in b['key'] or b['key'].split('.',1)[0] not in seen for b in spec['bindings'].values()): raise ValueError('each binding must name a selected source and statistic')
    if not isinstance(spec['figure'],list) or not spec['figure'] or len(set(spec['figure']))!=len(spec['figure']) or set(spec['figure'])-set(spec['bindings']): raise ValueError('figure must select distinct binding names')
    if len({spec['bindings'][key]['unit'] for key in spec['figure']})!=1 or len({spec['bindings'][key]['display_unit'] for key in spec['figure']})!=1: raise ValueError('a figure must use a single common unit and display unit')
    models=spec.get('models',[])
    if not isinstance(models,list): raise ValueError('models must be a list')
    for model in models:
        if not isinstance(model,dict) or set(model)-{'id','source','equation','code_quote','residual_key','tolerance','judgment','parameters'} or not {'id','source','equation','code_quote','residual_key','tolerance','judgment'}<=set(model) or not NAME.fullmatch(model['id']) or model['source'] not in seen or not isinstance(model['equation'],str) or not model['equation'] or not isinstance(model['code_quote'],str) or not model['code_quote'] or not isinstance(model['residual_key'],list) or not model['residual_key'] or any(not isinstance(v,str) or not v for v in model['residual_key']) or type(model['tolerance']) not in (int,float) or not math.isfinite(model['tolerance']) or model['tolerance']<0: raise ValueError('invalid adopted model mapping')
        evidence.check_judgment(model['judgment'],'model judgment')
    for path in (spec['article_template'],spec['slides_template']):
        text=checked(root,path).read_text(encoding='utf-8')
        names={m.group(1) for m in TOKEN.finditer(text) if m.group(1)}
        if names-set(spec['bindings']): raise ValueError('template has an unknown statistic binding')
        rest=TOKEN.sub('',text)
        if any(token in rest for token in ('{{stat:', '{{table', '{{figure')): raise ValueError('malformed artifact placeholder')
        if not names: raise ValueError('each template must use at least one statistic')
    return spec


def normalize(root,spec,selected=None):
    if selected is not None and not selected <= {source['id'] for source in spec['sources']}: raise ValueError('unknown selected source')
    stats={}; records={}
    for source in spec['sources']:
        name=source['id']
        if selected is not None and name not in selected: continue
        result=load(checked(root,source['result']))
        if not isinstance(result,dict): raise ValueError('source result must be an object')
        refs={key:ref(root,source[key]) for key in ('result','specification','code','data') if key in source}
        provenance=result.get('provenance',result.get('inputs',{}))
        if not isinstance(provenance,dict): raise ValueError('result provenance must be an object')
        checks={}
        for ref_name, hash_names in {'specification':('spec_sha256','specification_sha256'),'data':('data_sha256',),'code':('script_sha256','code_sha256')}.items():
            claimed=next((provenance[k] for k in hash_names if k in provenance),None)
            if claimed is not None:
                if ref_name not in refs or refs[ref_name]['sha256']!=claimed: raise ValueError(f'{name}: {ref_name} does not match declared producer hash')
                checks[ref_name]='verified'
            elif ref_name in refs:
                expected=source.get('expected_hashes',{}).get(ref_name)
                if expected is None or refs[ref_name]['sha256']!=expected: raise ValueError(f'{name}: {ref_name} needs a matching owner-adopted hash')
                checks[ref_name]='owner-adopted hash; producer did not record a hash'
        own=result.get('statistics',{})
        if not isinstance(own,dict): raise ValueError('statistics must be an object')
        quantities={}
        def add(key,value,unit,source_key):
            if not isinstance(key,str) or not key or not isinstance(unit,str) or not unit or type(value) not in (int,float) or not math.isfinite(value): raise ValueError(f'{name}: invalid statistic {key}')
            item={'value':value,'unit':unit}
            if key in quantities and quantities[key]['statistic']!=item: raise ValueError(f'{name}: inconsistent statistic {key}')
            quantities[key]={'statistic':item,'source_key':source_key}
        for key,value in own.items():
            if not isinstance(value,dict) or set(value)!={'value','unit'}: raise ValueError(f'{name}: statistics must contain value and unit')
            add(key,value['value'],value['unit'],['statistics',key])
        for key,requested in source.get('quantities',{}).items():
            if not isinstance(requested,dict) or set(requested)!={'key','unit'}: raise ValueError('selected quantity requires source key and unit')
            add(key,evidence.lookup(result,requested['key'],'selected quantity'),requested['unit'],requested['key'])
        coef=result.get('coefficients',{}); ses=result.get('standard_errors',{}); units=source.get('coefficient_units',{})
        if not isinstance(coef,dict) or not isinstance(ses,dict): raise ValueError('coefficients and standard_errors must be objects')
        for key,value in coef.items():
            sname='coefficient.'+key
            unit=quantities.get(sname,{}).get('statistic',{}).get('unit',units.get(key))
            if unit is None: raise ValueError(f'{name}: coefficient unit required for {key}')
            add(sname,value,unit,['coefficients',key])
        for key,value in ses.items():
            sname='standard_error.'+key
            unit=quantities.get(sname,{}).get('statistic',{}).get('unit',units.get(key))
            if unit is None: raise ValueError(f'{name}: standard error unit required for {key}')
            add(sname,value,unit,['standard_errors',key])
        inference=result.get('inference',{}) or {}
        if isinstance(inference,dict):
            pvalues=inference.get('p_values',{})
            if not pvalues and 'pvalue' in inference and len(coef)==1: pvalues={next(iter(coef)):inference['pvalue']}
            if isinstance(pvalues,dict):
                for k,v in pvalues.items(): add('p_value.'+k,v,'probability',['inference','p_values',k] if 'p_values' in inference else ['inference','pvalue'])
            intervals=inference.get('confidence_intervals_95',{})
            if not intervals and 'confidence_interval_95' in inference and len(coef)==1: intervals={next(iter(coef)):inference['confidence_interval_95']}
            if isinstance(intervals,dict):
                for k,ends in intervals.items():
                    if not isinstance(ends,list) or len(ends)!=2: raise ValueError('confidence interval must have two endpoints')
                    unit=quantities.get('coefficient.'+k,{}).get('statistic',{}).get('unit')
                    for index,(which,v) in enumerate(zip(('lower','upper'),ends)):
                        if v is None: continue
                        add('confidence_95_'+which+'.'+k,v,unit,['inference','confidence_intervals_95',k,index] if 'confidence_intervals_95' in inference else ['inference','confidence_interval_95',index])
        reference=inference.get('reference') if isinstance(inference,dict) else None
        df=inference.get('degrees_of_freedom') if isinstance(inference,dict) else None
        need_wald=any(k in ses and ses[k]>0 and any(prefix+k not in quantities for prefix in ('p_value.','confidence_95_lower.','confidence_95_upper.')) for k in coef)
        if need_wald and reference in ('normal','Student t') and (reference=='normal' or type(df) in (int,float) and math.isfinite(df) and df>0):
            from scipy.stats import norm, t
            distribution=norm if reference=='normal' else t(df)
            critical=float(distribution.ppf(0.975))
            for k,value in coef.items():
                if k not in ses or ses[k]<=0: continue
                unit=quantities['coefficient.'+k]['statistic']['unit']; se=ses[k]
                if 'p_value.'+k not in quantities: add('p_value.'+k,float(2*distribution.sf(abs(value/se))),'probability',{'calculation':'two-sided Wald p-value','reference':reference,'degrees_of_freedom':df,'inputs':[['coefficients',k],['standard_errors',k]]})
                for which,sign in (('lower',-1),('upper',1)):
                    if 'confidence_95_'+which+'.'+k not in quantities: add('confidence_95_'+which+'.'+k,float(value+sign*critical*se),unit,{'calculation':'95% Wald confidence limit','reference':reference,'degrees_of_freedom':df,'inputs':[['coefficients',k],['standard_errors',k]]})
        observations=result.get('observations')
        if observations is not None and 'observations' not in quantities: add('observations',observations,'observations',['observations'])
        for key,value in quantities.items(): stats[name+'.'+key]=value['statistic']
        records[name]={'identity':{'model':result.get('model',result.get('method')),'specification':refs.get('specification',{}).get('sha256')},'references':refs,'hash_checks':checks,'method':result.get('method'),'model':result.get('model'),'engine':result.get('engine'),'versions':result.get('versions'),'adopted':result.get('adopted',result.get('definition')),'options':result.get('options',result.get('design')),'provenance':provenance,'quantity_origins':{k:v['source_key'] for k,v in quantities.items()},'source_result':result,'metadata':copy.deepcopy(source.get('metadata',{}))}
    for alias,b in spec['bindings'].items():
        if selected is not None and b['key'].split('.',1)[0] not in selected: continue
        if b['key'] not in stats or stats[b['key']]['unit']!=b['unit']: raise ValueError(f'binding {alias} does not match a registered statistic and unit')
    registry = {'schema':'research-artifact-registry-v1','statistics':stats,'records':records}
    registry['items'] = prepare_gallery_items(registry)
    return registry


def merge_registries(paths):
    combined={'schema':'research-artifact-registry-v1','statistics':{},'records':{},'items':{}}
    for path in paths:
        fragment=load(path)
        if fragment.get('schema')!='research-artifact-registry-v1': raise ValueError('invalid registry fragment')
        for key in ('statistics','records','items'):
            if set(combined[key]) & set(fragment.get(key,{})): raise ValueError('duplicate registry fragment identity')
            combined[key].update(fragment.get(key,{}))
    return combined


def table(spec, registry):
    rows=['| Quantity | Estimate | Unit |','|---|---:|---|']
    for b in spec['bindings'].values():
        value=registry['statistics'][b['key']]['value']
        rows.append('| '+b['label'].replace('|','\\|')+' | '+format(value,b['format'])+' | '+b['display_unit'].replace('|','\\|')+' |')
    return '\n'.join(rows)+'\n'


def figure(spec, registry):
    selected=[spec['bindings'][k] for k in spec['figure']]
    values=[registry['statistics'][b['key']]['value'] for b in selected]
    lo=min(0,*values); hi=max(0,*values)
    if hi==lo: hi=lo+1
    width=720; height=90+55*len(values); scale=460/(hi-lo); zero=200+(0-lo)*scale
    rows=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">', '<rect width="100%" height="100%" fill="white"/>',f'<text x="200" y="25" font-family="sans-serif" font-size="15">{html.escape(selected[0]["display_unit"])}</text>',f'<line x1="{zero:.2f}" y1="35" x2="{zero:.2f}" y2="{height-20}" stroke="#555"/>']
    for i,(b,value) in enumerate(zip(selected,values)):
        y=55+i*55; end=200+(value-lo)*scale; left=min(zero,end); bar=abs(end-zero)
        rows += [f'<text x="190" y="{y+5}" text-anchor="end" font-family="sans-serif" font-size="14">{html.escape(b["label"])}</text>',f'<rect x="{left:.2f}" y="{y-14}" width="{bar:.2f}" height="20" fill="#247887"/>',f'<text x="{end+5:.2f}" y="{y+2}" font-family="sans-serif" font-size="13">{format(value,b["format"])}</text>']
    rows.append('</svg>')
    return '\n'.join(rows)+'\n'


def render(root,spec,registry,template,table_path,figure_path):
    raw=checked(root,template).read_text(encoding='utf-8'); parts=[]; captures=[]; length=0; cursor=0
    def append(x):
        nonlocal length
        parts.append(x); length+=len(x)
    for m in TOKEN.finditer(raw):
        append(raw[cursor:m.start()]); alias=m.group(1); special=m.group(2)
        if alias:
            b=spec['bindings'][alias]; item=registry['statistics'][b['key']]; value=format(item['value'],b['format']); start=length; append(value); stop=length; append(' '); ustart=length; append(b['display_unit']); uend=length
            captures.append({'id':alias+'-'+str(len(captures)+1),'alias':alias,'target':{'start':start,'end':stop,'quote':value},'unit_target':{'start':ustart,'end':uend,'quote':b['display_unit']}})
        elif special=='table': append(Path(table_path).read_text(encoding='utf-8'))
        else: append('![Selected quantities]('+str(Path(figure_path).resolve())+')')
        cursor=m.end()
    append(raw[cursor:]); return ''.join(parts),captures


def make_contract(root,spec,registry_path,manuscript_path,trace):
    registry_path=Path(registry_path).resolve().relative_to(root).as_posix(); manuscript_path=Path(manuscript_path).resolve().relative_to(root).as_posix()
    rows=[]
    for capture in trace:
        b=spec['bindings'][capture['alias']]
        rows.append({'id':capture['id'],'target':capture['target'],'unit_target':capture['unit_target'],'unit_display':b['display_unit'],'result':{**ref(root,registry_path),'identity_keys':{},'key':['statistics',b['key']],'unit':b['unit'],'format':b['format']}})
    return {'manuscript':ref(root,manuscript_path),'adopted':{},'numbers':rows}


def make_model_contracts(root,spec,registry_path,article_path):
    registry_file=Path(registry_path).resolve().relative_to(root).as_posix()
    article_file=Path(article_path).resolve().relative_to(root).as_posix()
    registry=load(root/registry_file); article=(root/article_file).read_text(encoding='utf8'); contracts=[]
    for model in spec.get('models',[]):
        name=model['source']; record=registry['records'][name]; identity=record['identity']
        if not all(isinstance(identity.get(k),str) and identity[k] for k in ('model','specification')): raise ValueError('model mapping needs a recorded model and selected specification')
        code_path=record['references']['code']['path']; code=(root/code_path).read_text(encoding='utf8')
        def span(body,quote):
            if body.count(quote)!=1: raise ValueError('model quote must occur exactly once')
            start=body.index(quote); return {'start':start,'end':start+len(quote),'quote':quote}
        mapping={'id':model['id'],'equation':span(article,model['equation']),'code':{**ref(root,code_path),'span':span(code,model['code_quote'])},'judgment':model['judgment'],'result':{**ref(root,registry_file),'identity_keys':{'model':['records',name,'identity','model'],'specification':['records',name,'identity','specification']},'residual_key':['records',name,'source_result',*model['residual_key']],'tolerance':model['tolerance']}}
        contract={'manuscript':ref(root,article_file),'adopted':identity,'models':[mapping]}
        parameter_rows=[]
        for param in model.get('parameters',[]):
            if not isinstance(param,dict) or set(param)!={'id','target','code_quote','spec_key','spec_unit','statistic'}: raise ValueError('invalid adopted parameter mapping')
            spec_ref=record['references'].get('specification');
            if not spec_ref: raise ValueError('parameter mapping needs a specification')
            spec_data=load(root/spec_ref['path']); fixed=evidence.lookup(spec_data,param['spec_key'],'parameter specification'); stat=registry['statistics'][param['statistic']]
            parameter_rows.append({'id':param['id'],'kind':'parameter','status':'derived','target':span(article,param['target']),'code':{**ref(root,code_path),'span':span(code,param['code_quote'])},'judgment':model['judgment'],'origin':{'specification':{**spec_ref,'key':param['spec_key'],'value':fixed,'unit':param['spec_unit']}},'result':{**ref(root,registry_file),'identity_keys':{'model':['records',name,'identity','model'],'specification':['records',name,'identity','specification']},'quantity':{'key':['statistics',param['statistic']],'value':stat['value'],'unit':stat['unit']}}})
        if parameter_rows: contract['mappings']=parameter_rows
        contracts.append({'contract':contract,'check':evidence.bind(contract,root)})
    return contracts


def manifest(root,spec_path,spec,python,pandoc,quarto):
    helper=Path(__file__).resolve().relative_to(root).as_posix()
    core=list(dict.fromkeys(Path(p).resolve().relative_to(root).as_posix() for p in (__file__,evidence.__file__,state.__file__,evidence.paragraph.__file__,state.gate.__file__)))
    H='{root}/'+helper; S='{root}/'+spec_path
    stages=[]; source_dependencies={}
    for source in spec['sources']:
        sid='source-'+source['id']; source_dependencies[sid]=['registry']
        inputs=list(dict.fromkeys([spec_path,*core,*[source[k] for k in ('result','specification','code','data') if k in source]]))
        stages.append({'id':sid,'inputs':inputs,'depends':{},'outputs':{'registry':'registry.json'},'argv':[python,H,'normalize','--root','{root}','--spec',S,'--source',source['id'],'--output','{out:registry}']})
    merge_args=sum((['--registry','{dep:'+sid+':registry}'] for sid in source_dependencies),[])
    stages.append({'id':'registry','inputs':[spec_path,*core],'depends':source_dependencies,'outputs':{'registry':'registry.json'},'argv':[python,H,'merge','--root','{root}','--spec',S,*merge_args,'--output','{out:registry}']})
    stages.append({'id':'table','inputs':[spec_path,*core],'depends':{'registry':['registry']},'outputs':{'table':'table.md'},'argv':[python,H,'table','--root','{root}','--spec',S,'--registry','{dep:registry:registry}','--output','{out:table}']})
    figure_names={spec['bindings'][name]['key'].split('.',1)[0] for name in spec['figure']}
    figure_deps={'source-'+name:['registry'] for name in sorted(figure_names)}
    figure_args=sum((['--registry','{dep:'+sid+':registry}'] for sid in figure_deps),[])
    stages.append({'id':'figure','inputs':[spec_path,*core],'depends':figure_deps,'outputs':{'figure':'figure.svg'},'argv':[python,H,'figure','--root','{root}','--spec',S,*figure_args,'--output','{out:figure}']})
    stages.append({'id':'figure-pdf','inputs':[],'depends':{'figure':['figure']},'outputs':{'figure':'figure.pdf'},'argv':['rsvg-convert','-f','pdf','-o','{out:figure}','{dep:figure:figure}'],'inherit_env':['PATH']})
    for stage,key,extension in [('article','article_template','qmd'),('slides','slides_template','qmd')]:
        stages.append({'id':stage,'inputs':[spec_path,spec[key],*core],'depends':{'registry':['registry'],'table':['table'],'figure':['figure']},'outputs':{'text':stage+'.'+extension,'trace':'trace.json'},'argv':[python,H,'render','--root','{root}','--spec',S,'--registry','{dep:registry:registry}','--template','{root}/'+spec[key],'--table','{dep:table:table}','--figure','{dep:figure:figure}','--output','{out:text}','--trace','{out:trace}']})
    stages.append({'id':'bindings','inputs':[spec_path,*core],'depends':{'registry':['registry'],'article':['text','trace'],'slides':['text','trace']},'outputs':{'article_contract':'article-contract.json','article_check':'article-check.json','slides_contract':'slides-contract.json','slides_check':'slides-check.json','model_contracts':'model-contracts.json'},'argv':[python,H,'bind-generated','--root','{root}','--spec',S,'--registry','{dep:registry:registry}','--article','{dep:article:text}','--article-trace','{dep:article:trace}','--slides','{dep:slides:text}','--slides-trace','{dep:slides:trace}','--article-contract','{out:article_contract}','--article-check','{out:article_check}','--slides-contract','{out:slides_contract}','--slides-check','{out:slides_check}','--model-contracts','{out:model_contracts}']})
    for sid,fmt,source in [('html','html','article'),('latex','latex','article'),('pdf','pdf','article'),('slides-pdf','pdf','slides')]:
        out={'html':'article.html','latex':'article.tex','pdf':'article.pdf','slides-pdf':'slides.pdf'}[sid]
        argv=[pandoc,'{dep:'+source+':text}','-s','-o','{out:artifact}']
        dependencies={source:['text'],'bindings':[source+'_check']+(['model_contracts'] if source=='article' else []),'figure':['figure']}
        inputs=[]
        if fmt=='html': argv+=['--embed-resources']
        elif fmt in ('pdf','latex'):
            target='slides' if source=='slides' else 'paper'
            assets=latex_assets(root)
            inputs=[assets[k].relative_to(root).as_posix() for k in (target+'_source',target+'_adapter','paper_class','paper_config','paper_style','builder')]
            content=checked(root,spec[source+'_template']).read_text(encoding='utf8')
            if content.startswith('---') and any(key in content.split('---',2)[1] for key in ('template','bibliography')):
                options=explicit_latex_options(checked(root,spec[source+'_template']),pandoc,target)
                custom=options.get('template')
                if custom:
                    chosen=chosen_template(root,checked(root,spec[source+'_template']),custom)
                    item=chosen.relative_to(root).as_posix()
                    if item not in inputs: inputs.append(item)
                refs=options.get('_bibliography',[])
                for bibliography in refs if isinstance(refs,list) else [refs]:
                    chosen=chosen_template(root,checked(root,spec[source+'_template']),bibliography)
                    item=chosen.relative_to(root).as_posix()
                    if item not in inputs: inputs.append(item)
            dependencies['figure-pdf']=['figure']
            argv=[python,H,'render-latex','--root','{root}','--spec',S,'--article','{dep:'+source+':text}','--template','{root}/'+spec[source+'_template'],'--figure','{dep:figure:figure}','--figure-pdf','{dep:figure-pdf:figure}','--target',target,'--pandoc',pandoc,'--python',python,'--output','{out:artifact}']
            if fmt=='pdf': argv+=['--pdf']
        tex_cache=root/'.agents'/'cache'/'research-artifacts-tex'
        env={'TEXMFCACHE':str(tex_cache),'TEXMFVAR':str(tex_cache)} if fmt=='pdf' else {}
        stages.append({'id':sid,'inputs':inputs,'depends':dependencies,'outputs':{'artifact':out},'argv':argv,'env':env,'inherit_env':[k for k in ('PATH','HOME','TEXMFHOME','TEXMFCONFIG','TEXMFOUTPUT') if k in os.environ]})
    for sid,source,qformat in [('quarto','article','html')]:
        stages.append({'id':sid,'inputs':[spec_path,*core],'depends':{source:['text'],'bindings':[source+'_check']+(['model_contracts'] if source=='article' else []),'figure':['figure']},'outputs':{'artifact':sid+'.html','runtime':'quarto-runtime.json'},'argv':[python,H,'quarto-render','--root','{root}','--spec',S,'--article','{dep:'+source+':text}','--quarto',quarto,'--quarto-format',qformat,'--output','{out:artifact}','--engine','{out:runtime}'],'inherit_env':[k for k in ('PATH','HOME','XDG_CACHE_HOME','XDG_CONFIG_HOME','XDG_DATA_HOME','QUARTO_CONDA_PREFIX','QUARTO_SHARE_PATH','QUARTO_DENO','QUARTO_DART_SASS','QUARTO_PANDOC','QUARTO_TYPST','QUARTO_DENO_DOM','QUARTO_ESBUILD','QUARTO_PYTHON') if k in os.environ]})
    return {'pipeline':spec['pipeline'],'stages':stages}


def example(root,output,python,pandoc,quarto):
    """Execute a seeded IV and search example and prepare its real DAG."""
    if any(not x or not Path(x).is_absolute() for x in (python,pandoc,quarto)): raise ValueError('example requires absolute Python, Pandoc and Quarto paths')
    out=Path(output); out=(out if out.is_absolute() else root/out).resolve()
    rel=out.relative_to(root).as_posix()
    causal=next((p for p in (root/'skills/econ-data/scripts/research_causal.py',root/'research_causal.py') if p.is_file()),None)
    markets=next((p for p in (root/'skills/econ-data/scripts/research_markets.py',root/'research_markets.py') if p.is_file()),None)
    if causal is None or markets is None: raise ValueError('example needs the installed causal and market model scripts')
    out.mkdir(parents=True,exist_ok=False)
    rng=random.Random(20261101)
    with (out/'sample.csv').open('w',newline='',encoding='utf8') as stream:
        writer=csv.writer(stream); writer.writerow(['id','x','d','z','z2','y'])
        for i in range(1200):
            x,z,z2,error,noise=(rng.gauss(0,1) for _ in range(5)); d=.8*z+.7*z2+.6*error+noise; writer.writerow([str(i),x,d,z,z2,1+1.5*d+.5*x+error])
    iv={'method':'iv_gmm','data':'sample.csv','id':'id','outcome':'y','regressors':['x'],'endogenous':['d'],'instruments':['z','z2'],'population':'seeded simulated units','period':'simulation','unit':'outcome units','estimand':'effect of endogenous treatment','identification':'independent excluded instruments and independent units','assignment':'independent simulated units','inference':{'type':'robust'},'options':{}}
    search={'model':'search','baseline':{'offers':3,'search_cost':.08,'outside_option':0.0},'scenario':{'offers':3,'search_cost':.02,'outside_option':0.0},'unit':'model units','sources':[{'kind':'synthetic','description':'Uniform offers and full recall'}]}
    state.save(out/'iv-spec.json',iv); state.save(out/'search-spec.json',search)
    env=os.environ.copy(); env.update({'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
    for script,sp,res in ((causal,'iv-spec.json','iv-result.json'),(markets,'search-spec.json','search-result.json')):
        proc=subprocess.run([python,str(script),'run',str(out/sp),'--output',str(out/res)],env=env,text=True,capture_output=True)
        if proc.returncode: raise ValueError('example producer failed: '+proc.stderr[-2000:])
    article="""---
title: "Independent synthetic comparisons"
---

The IV treatment effect is {{stat:effect}}; its standard error is {{stat:se}}.

With independent uniform offers on [0,1], full recall and search cost c in [0,1/2], the reservation threshold z satisfies `c = (1-z)^2 / 2`. Its value is {{stat:threshold}}. Expected net surplus is {{stat:surplus}}.

{{table}}

{{figure}}
"""
    slides="""% Independent synthetic comparisons

# IV treatment effect

The estimate is {{stat:effect}}; its standard error is {{stat:se}}.

{{figure}}

# Consumer search

The reservation threshold is {{stat:threshold}} and expected net surplus is {{stat:surplus}}.

{{table}}
"""
    (out/'article.qmd').write_text(article,encoding='utf8'); (out/'slides.qmd').write_text(slides,encoding='utf8')
    def binding(key,unit,label): return {'key':key,'unit':unit,'display_unit':unit,'format':'.3f','label':label}
    ivunit='outcome units per one unit of d'; zunit='dimensionless utility normalized to [0,1]'
    config={'pipeline':'artifact-example','sources':[{'id':'iv','result':rel+'/iv-result.json','specification':rel+'/iv-spec.json','data':rel+'/sample.csv','code':causal.relative_to(root).as_posix(),'expected_hashes':{'code':state.digest(causal)}},{'id':'search','result':rel+'/search-result.json','specification':rel+'/search-spec.json','code':markets.relative_to(root).as_posix(),'expected_hashes':{'code':state.digest(markets)},'quantities':{'reservation_value':{'key':['baseline','reservation_value'],'unit':zunit}}}], 'bindings':{'effect':binding('iv.coefficient.d',ivunit,'IV effect'),'se':binding('iv.standard_error.d',ivunit,'Standard error'),'lower':binding('iv.confidence_95_lower.d',ivunit,'Lower 95% limit'),'upper':binding('iv.confidence_95_upper.d',ivunit,'Upper 95% limit'),'threshold':binding('search.reservation_value',zunit,'Search threshold'),'surplus':binding('search.expected_net_surplus','model units','Search surplus')},'figure':['effect','lower','upper'],'article_template':rel+'/article.qmd','slides_template':rel+'/slides.qmd','models':[{'id':'search-reservation','source':'search','equation':'c = (1-z)^2 / 2','code_quote':'abs((1-z)**2/2-c)','residual_key':['baseline','reservation_equation_error'],'tolerance':1e-10,'judgment':{'reviewer':'example-author','decision':'supported','rationale':'The saved reservation equation, code and residual agree.'},'parameters':[{'id':'search-threshold','target':'reservation threshold z','code_quote':'z = 1-math.sqrt(2*c)','spec_key':['baseline','search_cost'],'spec_unit':zunit,'statistic':'search.reservation_value'}]}]}
    state.save(out/'artifact-spec.json',config); validate_spec(root,config)
    (root/'.agents'/'cache'/'research-artifacts-tex').mkdir(parents=True,exist_ok=True)
    state.save(out/'manifest.json',manifest(root,rel+'/artifact-spec.json',config,python,pandoc,quarto))
    print(json.dumps({'specification':rel+'/artifact-spec.json','manifest':rel+'/manifest.json','results':[rel+'/iv-result.json',rel+'/search-result.json']}))


def gallery_main(argv=None):
    parser = argparse.ArgumentParser(description='Browse and edit saved research displays')
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('register', 'list', 'show', 'compare', 'select', 'preview', 'render', 'edit', 'ui'):
        command = commands.add_parser(name)
        command.add_argument('--root', required=True, type=Path)
        command.add_argument('--registry', required=True, type=Path)
        if name in ('register', 'list', 'show', 'compare', 'select', 'preview'):
            command.add_argument('--output', type=Path)
        if name == 'register':
            command.add_argument('--items', type=Path, help='JSON array of saved display-ready rows and definitions')
            command.add_argument('--assets', type=Path)
        if name == 'list':
            command.add_argument('--query', default='')
            command.add_argument('--kind', choices=GALLERY_KINDS)
            command.add_argument('--status')
            for key in GALLERY_FILTERS:
                command.add_argument('--' + key.replace('_', '-'))
        if name == 'ui':
            command.add_argument('--port', type=int, default=2718)
            command.add_argument('--host', default='127.0.0.1')
            command.add_argument('--headless', action='store_true')
            command.add_argument('--project-summary')
            command.add_argument('--project')
            command.add_argument('--store')
            command.add_argument('--github', action='append', default=[])
            command.add_argument('--meeting')
            command.add_argument('--quarto')
        if name in ('show', 'preview', 'edit'):
            command.add_argument('item_id')
        if name in ('compare', 'select'):
            command.add_argument('item_ids', nargs='+')
        if name == 'render':
            command.add_argument('--item', action='append')
            command.add_argument('--assets', type=Path)
        if name == 'edit':
            command.add_argument('--changes', required=True, type=Path)
            command.add_argument('--expected-revision', required=True)
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve(strict=True)
        path, registry = gallery_registry(root, args.registry)
        def local(value, exists=True):
            value = value.relative_to(root) if value.is_absolute() else value
            return root / state.relative(root, value.as_posix(), exists=exists)
        if args.command == 'ui':
            command = [sys.executable, '-m', 'marimo', 'run', str(Path(__file__).with_name('research_gallery.py')),
                       '--host', args.host, '--port', str(args.port)]
            if args.headless:
                command.append('--headless')
            command += ['--', '--root', str(root), '--registry', path.relative_to(root).as_posix()]
            for key in ('project_summary', 'project', 'store', 'meeting', 'quarto'):
                if getattr(args, key):
                    command += ['--' + key.replace('_', '-'), getattr(args, key)]
            for source in args.github:
                command += ['--github', source]
            return subprocess.run(command, check=False).returncode
        if args.command == 'register':
            definitions = load(local(args.items)) if args.items else None
            result = register_gallery(root, path, definitions, args.output, args.assets)
        elif args.command == 'edit':
            result = edit_gallery_item(root, path, args.item_id, load(local(args.changes)), args.expected_revision)
        elif args.command == 'render':
            selected = args.item if args.item is not None else list(registry.get('items', {}))
            if not selected or len(set(selected)) != len(selected) or set(selected) - set(registry.get('items', {})):
                raise ValueError('render requires distinct existing gallery item IDs')
            with state.locked(path):
                _, registry = gallery_registry(root, path)
                for item_id in selected:
                    item = registry['items'][item_id]
                    item['files'] = render_gallery_item(root, item, args.assets or path.parent / 'gallery-assets')
                state.save(path, registry)
            result = {'registry': path.relative_to(root).as_posix(), 'item_ids': selected}
        elif args.command == 'list':
            filters = {key: getattr(args, key) for key in GALLERY_FILTERS}
            result = [item for item in gallery_items(root, path, args.query, filters)
                      if (not args.kind or item['kind'] == args.kind) and (not args.status or item['status'] == args.status)]
        elif args.command in ('compare', 'select'):
            result = gallery_compare(root, path, args.item_ids)
            if args.command == 'select':
                result = result['items']
        else:
            if args.item_id not in registry.get('items', {}):
                raise ValueError('unknown gallery item: ' + args.item_id)
            item = registry['items'][args.item_id]
            result = gallery_preview(item) if args.command == 'preview' else {'revision': state.content_hash(item), **gallery_projection(item)}
        output = getattr(args, 'output', None)
        if output is not None and args.command != 'register':
            target = local(output, exists=False)
            if target == path:
                raise ValueError('a selection or preview cannot replace its registry')
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(result, str):
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf8', dir=target.parent, delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(result)
                try:
                    os.replace(temporary, target)
                finally:
                    temporary.unlink(missing_ok=True)
            else:
                state.save(target, result)
            print(json.dumps({'output': target.relative_to(root).as_posix()}, ensure_ascii=False))
        else:
            print(result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, TypeError, KeyError, OSError, ImportError, evidence.EvidenceError) as exc:
        print('research gallery: ' + str(exc), file=sys.stderr)
        return 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == 'gallery':
        return gallery_main(argv[1:])
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('command',choices=['example','materialize','normalize','merge','table','figure','render','render-latex','generate-adapters','bind-generated','quarto-render']); p.add_argument('--root',required=True,type=Path); p.add_argument('--spec',type=Path); p.add_argument('--output',type=Path); p.add_argument('--registry',type=Path,action='append'); p.add_argument('--source'); p.add_argument('--template',type=Path); p.add_argument('--table',type=Path); p.add_argument('--figure',type=Path); p.add_argument('--figure-pdf',type=Path); p.add_argument('--target',choices=['paper','slides']); p.add_argument('--pdf',action='store_true'); p.add_argument('--trace',type=Path); p.add_argument('--python'); p.add_argument('--pandoc'); p.add_argument('--quarto'); p.add_argument('--quarto-format',choices=['html','revealjs'],default='html'); p.add_argument('--engine',type=Path);
    for k in ('article','article-trace','slides','slides-trace','article-contract','article-check','slides-contract','slides-check','model-contracts'): p.add_argument('--'+k,type=Path)
    a=p.parse_args(argv)
    try:
        root=a.root.resolve(strict=True)
        if a.command=='example':
            if not a.output: raise ValueError('example requires a new output directory')
            example(root,a.output,a.python,a.pandoc,a.quarto); return 0
        if a.command=='generate-adapters':
            assets=latex_assets(root,require_adapters=False)
            for kind in ('paper','slides'):
                source=assets[kind+'_source']
                destination=source.parent/('pandoc_template.latex' if source.parent.name==kind else kind+'_pandoc_template.latex')
                destination.write_text(latex_adapter(assets[kind+'_source'].read_text(encoding='utf8'),kind),encoding='utf8')
            return 0
        if not a.spec: raise ValueError('specification is required')
        sp=a.spec.resolve(strict=True); rel=sp.relative_to(root).as_posix(); spec=validate_spec(root,load(sp))
        if a.command=='materialize':
            if not a.output or not a.python or not a.pandoc or not a.quarto or any(not Path(x).is_absolute() for x in (a.python,a.pandoc,a.quarto)): raise ValueError('materialize requires output and absolute python, pandoc and quarto paths')
            (root/'.agents'/'cache'/'research-artifacts-tex').mkdir(parents=True,exist_ok=True)
            state.save(a.output,manifest(root,rel,spec,a.python,a.pandoc,a.quarto))
        elif a.command=='normalize': state.save(a.output,normalize(root,spec,{a.source} if a.source else None))
        elif a.command=='merge':
            registry=merge_registries(a.registry)
            for alias,b in spec['bindings'].items():
                if b['key'] not in registry['statistics'] or registry['statistics'][b['key']]['unit']!=b['unit']: raise ValueError(f'binding {alias} does not match registry')
            state.save(a.output,registry)
        elif a.command in ('table','figure'):
            registry=merge_registries(a.registry); a.output.write_text(table(spec,registry) if a.command=='table' else figure(spec,registry),encoding='utf8')
        elif a.command=='render-latex':
            if not all((a.article,a.figure,a.figure_pdf,a.target,a.output,a.python,a.pandoc)): raise ValueError('render-latex requires source, figure files, target and executables')
            render_latex(root,a.article,a.figure,a.figure_pdf,a.target,a.output,a.pandoc,a.python,a.pdf,a.template)
        elif a.command=='render':
            registry=merge_registries(a.registry); template=a.template.resolve().relative_to(root).as_posix(); text,trace=render(root,spec,registry,template,a.table,a.figure); a.output.write_text(text,encoding='utf8'); state.save(a.trace,trace)
        elif a.command=='quarto-render':
            if not a.quarto or not Path(a.quarto).is_absolute(): raise ValueError('quarto executable must be absolute')
            binary=Path(a.quarto).resolve(strict=True); digest=state.digest(binary)
            version=subprocess.run([str(binary),'--version'],capture_output=True,text=True,check=True).stdout.strip()
            with tempfile.TemporaryDirectory(prefix='artifact-quarto-') as tmp:
                source=Path(tmp)/'article.qmd'; shutil.copyfile(a.article,source)
                subprocess.run([str(binary),'render','article.qmd','--to',a.quarto_format,'--output','quarto.html','-M','embed-resources:true','--no-execute','--quiet'],cwd=tmp,check=True)
                if state.digest(binary)!=digest: raise ValueError('Quarto changed during rendering')
                shutil.copyfile(Path(tmp)/'quarto.html',a.output)
            state.save(a.engine,{'executable':str(binary),'sha256':digest,'version':version})
        else:
            for manuscript,trace,contract_out,check_out in ((a.article,a.article_trace,a.article_contract,a.article_check),(a.slides,a.slides_trace,a.slides_contract,a.slides_check)):
                contract=make_contract(root,spec,a.registry[0],manuscript,load(trace)); result=evidence.bind(contract,root); state.save(contract_out,contract); state.save(check_out,result)
            state.save(a.model_contracts,make_model_contracts(root,spec,a.registry[0],a.article))
        return 0
    except (ValueError,TypeError,KeyError,OSError,AttributeError,ImportError,subprocess.CalledProcessError,evidence.EvidenceError) as exc:
        print('research_artifacts: '+str(exc),file=sys.stderr); return 1

if __name__=='__main__': sys.exit(main())
