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
TOKEN=re.compile(r'\{\{stat:([A-Za-z][A-Za-z0-9_-]*)\}\}|\{\{(table|figure)\}\}|\{\{definition:([A-Za-z][A-Za-z0-9_-]*)\}\}')
GALLERY_KINDS = ('descriptive', 'sample_composition', 'distribution', 'time_series',
                 'group_comparison', 'coefficient', 'event_study', 'robustness',
                 'alternative_specification', 'table', 'figure', 'att_gt', 'cohort_event',
                 'parallel_trends', 'rdd', 'iv_first_stage', 'iv_reduced_form', 'iv_confidence_set',
                 'scm', 'scm_gap', 'scm_placebo', 'binned_scatter', 'smd', 'structural', 'geo')
PLOT_TYPES = ('table', 'bar', 'line', 'scatter', 'step', 'area', 'coefficient', 'event_study', 'density', 'ecdf', 'box',
              'att_gt', 'cohort_event', 'parallel_trends', 'rdd', 'iv_first_stage', 'iv_reduced_form',
              'iv_confidence_set', 'scm', 'scm_gap', 'scm_placebo', 'binned_scatter', 'smd', 'structural', 'geo')
GALLERY_RENDER_VERSION = 12
DISPLAY_FIELDS = {'title', 'column_order', 'column_labels', 'formats', 'row_order',
                  'sort_by', 'ascending', 'notes', 'plot_type', 'x', 'y', 'lower', 'upper',
                  'series', 'visible_series', 'selected_result_ids', 'x_label', 'y_label',
                  'x_limits', 'y_limits', 'x_scale', 'y_scale', 'colors', 'legend',
                  'legend_location', 'width', 'height', 'orientation', 'style', 'font_size',
                  'series_order', 'series_labels', 'preset', 'table_number', 'latex_label',
                  'model_column', 'model_labels', 'model_order', 'outcome_column', 'column_groups',
                  'term_labels', 'term_order', 'panels', 'statistic_rows', 'show_se', 'show_ci',
                  'show_p', 'show_stars', 'digits', 'component', 'cohort', 'time', 'value',
                  'geometry', 'x_lower', 'x_upper', 'color_label', 'facet', 'note_fields',
                  'path_order', 'point_label'}
GALLERY_FILTERS = ('result_id', 'sample', 'comparison', 'outcome', 'specification', 'period', 'adoption')
RESULT_DEFINITION_FIELDS = (
    'run_id', 'specification_id', 'sample', 'population', 'observation_unit',
    'comparison', 'period', 'variables', 'measurement_units', 'estimand',
    'inference', 'weights', 'denominator', 'bin_edges', 'interval_closure',
    'quantile_convention', 'observations', 'outcome', 'specification', 'estimator',
    'n', 'n_clusters', 'fixed_effects', 'controls', 'sample_policy', 'unit',
    'ci_kind', 'interval_type', 'confidence_level', 'reference_time', 'reference_event_time',
    'reference_distribution', 'degrees_of_freedom', 'cluster', 'clustering',
    'treatment_group', 'control_group', 'comparison_group', 'assignment_unit',
    'inference_unit', 'treatment_history', 'time_structure', 'cohort',
    'aggregation', 'aggregation_weights', 'cohort_contributions', 'base_period',
    'anticipation', 'treatment_time', 'treatment_event_time', 'cutoff', 'bandwidth', 'weight_type',
    'weight_normalization', 'covariance_kind', 'official_function', 'effective_options',
    'result_format_version', 'scenario', 'parameter_definition', 'identification', 'reference_lines',
    'report_role', 'selection_status', 'method_selection',
    'model_contract', 'knowledge_ids', 'equations', 'notation', 'parameter_roles',
    'assumptions', 'normalization', 'equilibrium_selection', 'welfare_definition', 'horizon')
COMPARISON_FIELDS = (
    'estimand', 'population', 'sample', 'observation_unit', 'assignment_unit',
    'comparison', 'comparison_group', 'treatment_group', 'control_group', 'period',
    'outcome', 'unit', 'measurement_units', 'treatment_history', 'time_structure',
    'weights', 'weight_type', 'weight_normalization', 'aggregation',
    'aggregation_weights', 'cohort', 'cohort_contributions', 'base_period',
    'reference_time', 'reference_event_time', 'anticipation', 'inference_unit',
    'cluster', 'clustering', 'inference', 'interval_type', 'confidence_level')
GALLERY_LABELS = {'variable': '変数', 'term': '項目', 'group': '群', 'period': '期間',
                  'event_time': '導入からの期数', 'mean': '平均', 'sd': '標準偏差', 'median': '中央値',
                  'q25': '25%点', 'q50': '50%点', 'q75': '75%点', 'estimate': '推定値',
                  'se': '標準誤差', 'ci_low': '区間下端', 'ci_high': '区間上端', 'p_value': 'p 値',
                  'n': '観測数', 'unit': '単位', 'stage': '段階', 'n_missing': '欠損数', 'n_zero': 'ゼロの件数',
                  'value': '値', 'middle': '中央値', 'count': '件数', 'density': '密度', 'bin_mid': '階級の中央',
                  'min': '最小値', 'max': '最大値', 'difference': '平均差', 'standard_error': '標準誤差',
                  'conf_low': '区間下端', 'conf_high': '区間上端', 'smd': '標準化平均差', 'n_entities': '対象数'}


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
        metadata = {key: gallery_display_metadata(item) for key, item in value.items()
                    if not (key.endswith('_ids') and key not in ('result_ids', 'specification_ids', 'cohort_ids', 'knowledge_ids'))}
        # Official calls retain resolved column vectors in the source result.
        # Exhibits retain their column bindings and scalar options.
        if isinstance(value.get('columns'), dict):
            for field in ('args', 'inherited_args'):
                if isinstance(metadata.get(field), dict):
                    metadata[field] = {key: item for key, item in metadata[field].items()
                                       if key not in value['columns']}
        return metadata
    if isinstance(value, list):
        return [gallery_display_metadata(item) for item in value]
    return copy.deepcopy(value)


def gallery_metadata(registry, result_ids):
    """Capture economic definitions and producer identities from saved results once."""
    producers = {}
    definitions = []
    fields = RESULT_DEFINITION_FIELDS
    for result_id in result_ids:
        if result_id not in registry['records']:
            raise ValueError('unknown saved result: ' + result_id)
        record = registry['records'][result_id]
        saved = record.get('source_result') or {}
        adopted = record.get('adopted') or saved.get('adopted') or saved.get('definition') or {}
        if not isinstance(adopted, dict):
            adopted = {}
        metadata = {key: copy.deepcopy(saved.get(key, adopted.get(key))) for key in fields
                    if key in saved or key in adopted}
        # A structural result's scenario can contain the complete solved paths.
        # Display its adopted definition; keep calculated arrays in source_result.
        if isinstance(metadata.get('scenario'), dict):
            scenario = adopted.get('scenario') or {key: metadata['scenario'][key]
                for key in ('id', 'name', 'description') if key in metadata['scenario']}
            if scenario:
                metadata['scenario'] = copy.deepcopy(scenario)
            else:
                metadata.pop('scenario')
        metadata.update({key: copy.deepcopy(value) for key, value in record.get('metadata', {}).items()
                         if key in fields})
        if isinstance(saved.get('display'), dict):
            metadata.update(copy.deepcopy(saved['display'].get('metadata', {})))
        for key in ('interval_type', 'confidence_level', 'reference_distribution',
                    'degrees_of_freedom', 'inference_unit', 'cluster', 'n_clusters'):
            inference = saved.get('inference') or {}
            if key not in metadata and isinstance(inference, dict) and key in inference:
                metadata[key] = copy.deepcopy(inference[key])
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
            'official_function': copy.deepcopy(saved.get('official_function', saved.get('engine', record.get('engine')))),
            'effective_options': copy.deepcopy(saved.get('effective_options',
                (saved.get('diagnostics') or {}).get('effective_options', saved.get('options', record.get('options', {}))))),
            'versions': copy.deepcopy(saved.get('versions', record.get('versions', {}))),
            'result_format_version': saved.get('result_format_version', saved.get('schema_version', saved.get('schema'))),
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
    for field in ('x', 'y', 'lower', 'upper', 'series', 'sort_by', 'model_column', 'outcome_column',
                  'component', 'cohort', 'time', 'value', 'geometry', 'x_lower', 'x_upper', 'facet',
                  'path_order', 'point_label'):
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
    if display.get('preset', 'paper') not in ('paper', 'meeting'):
        raise ValueError('preset must be paper or meeting')
    if type(display.get('digits', 3)) is not int or not 0 <= display.get('digits', 3) <= 10:
        raise ValueError('digits must be an integer from 0 to 10')
    for field in ('show_se', 'show_ci', 'show_p', 'show_stars'):
        if field in display and type(display[field]) is not bool:
            raise ValueError(field + ' must be boolean')
    for field in ('model_labels', 'term_labels'):
        if not isinstance(display.get(field, {}), dict) or any(not isinstance(k, str) or not isinstance(v, str)
                                                              for k, v in display.get(field, {}).items()):
            raise ValueError(field + ' must map strings to labels')
    for field in ('model_order', 'term_order', 'note_fields'):
        values = display.get(field, [])
        if not isinstance(values, list) or any(not isinstance(value, str) for value in values) or len(set(values)) != len(values):
            raise ValueError(field + ' must contain distinct strings')
    for field, member in (('column_groups', 'models'), ('panels', 'terms')):
        groups = display.get(field, [])
        if not isinstance(groups, list):
            raise ValueError(field + ' must be a list')
        members = []
        for group in groups:
            if not isinstance(group, dict) or set(group) != {'label', member} or not isinstance(group['label'], str):
                raise ValueError(field + ' requires a label and ' + member)
            values = group[member]
            if not isinstance(values, list) or not values or any(not isinstance(value, str) for value in values):
                raise ValueError(member + ' must contain saved names')
            members.extend(values)
        if len(set(members)) != len(members):
            raise ValueError(field + ' cannot repeat a saved member')
    statistics = display.get('statistic_rows', [])
    if not isinstance(statistics, list) or any(not isinstance(row, dict) or set(row) != {'field', 'label'} or
                                              any(not isinstance(value, str) for value in row.values()) for row in statistics):
        raise ValueError('statistic_rows requires saved field and label pairs')
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
    for field in ('title', 'x_label', 'y_label', 'legend_location', 'table_number', 'latex_label', 'color_label'):
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
    rows = [(i, item['rows'][i]) for i in (display.get('row_order') or range(len(item['rows'])))]
    chosen = display.get('selected_result_ids', item['result_ids'])
    rows = [(i, row) for i, row in rows if row['result_id'] in chosen]
    series = display.get('series')
    if series and 'visible_series' in display:
        rows = [(i, row) for i, row in rows if str(row.get(series)) in display['visible_series']]
    if display.get('sort_by'):
        def sort_key(indexed_row):
            _, row = indexed_row
            value = row.get(display['sort_by'])
            return (value is None, type(value).__name__, value if value is not None else '')
        rows = sorted(rows, key=sort_key, reverse=not display.get('ascending', True))
    by_key = {col['key']: col for col in item['columns']}
    view['columns'] = [copy.deepcopy(by_key[key]) for key in display.get('column_order', by_key)]
    for column in view['columns']:
        column['label'] = display.get('column_labels', {}).get(column['key'], column['label'])
    view['rows'] = []
    for _, row in rows:
        selected = {key: row.get(key) for key in [*(col['key'] for col in view['columns']), 'result_id']}
        if 'unit' in row:
            selected['unit'] = row['unit']
        view['rows'].append(selected)
    view['row_indices'] = [i for i, _ in rows]
    view['title'] = display.get('title', item['title'])
    used = {row['result_id'] for _, row in rows}
    view['result_ids'] = [result_id for result_id in chosen if result_id in used]
    for field in ('producers', 'result_definitions'):
        if field in view['metadata']:
            view['metadata'][field] = {result_id: value for result_id, value in view['metadata'][field].items()
                                        if result_id in view['result_ids']}
    return view


def gallery_items(root, gallery_spec_path, query='', filters=None, *, item_ids=None):
    """List/search saved displays; no producer reads, checks or calculation runs."""
    path, registry = gallery_registry(root, gallery_spec_path)
    terms = query.casefold().split()
    if item_ids is not None:
        if not item_ids or len(set(item_ids)) != len(item_ids) or set(item_ids) - set(registry.get('items', {})):
            raise ValueError('selection requires distinct existing gallery item IDs')
        candidates = [registry['items'][item_id] for item_id in item_ids]
    else:
        candidates = registry.get('items', {}).values()
    items = []
    for item in candidates:
        searchable = json.dumps({key: item.get(key) for key in
                                ('id', 'title', 'kind', 'result_ids', 'metadata', 'interpretation', 'findings', 'issues', 'adoption_decision', 'status', 'links', 'display')},
                               ensure_ascii=False).casefold() if terms else ''
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
            view = gallery_projection(item)
            if view['metadata'].get('table_type') == 'regression':
                regression = gallery_projection({**item, 'display': {**item.get('display', {}),
                    'column_order': [column['key'] for column in item['columns']]}})
                presentation = gallery_regression_comparison([regression]).get('presentation')
                if presentation is not None:
                    view['presentation'] = presentation
            view['source_reference'] = {
                'kind': 'json', 'path': path.relative_to(Path(root).resolve()).as_posix(),
                'keys': ['items', item['id']], 'content_version': state.content_hash(item),
                'fields': ['rows', 'columns', 'metadata', 'display', 'interpretation', 'files']}
            items.append(view)
    return items


def composition_context(root, registry_path, *, result_ids, item_ids=(), gallery_path=None):
    """Select saved quantities and displays as sources for the existing writing host."""
    import argument

    root = Path(root).resolve(strict=True)
    path, registry = gallery_registry(root, registry_path)
    if (not isinstance(result_ids, (list, tuple)) or not result_ids
            or any(not isinstance(rid, str) or rid not in registry['records'] for rid in result_ids)
            or len(set(result_ids)) != len(result_ids)):
        raise ValueError('composition requires distinct existing result IDs')
    if (not isinstance(item_ids, (list, tuple)) or any(not isinstance(iid, str) or not iid for iid in item_ids)
            or len(set(item_ids)) != len(item_ids)):
        raise ValueError('composition requires distinct gallery item IDs')
    metadata = gallery_metadata(registry, result_ids)
    sources = {}
    for rid in result_ids:
        record = registry['records'][rid]
        definitions = gallery_display_metadata(record.get('adopted') or {})
        definitions.update(metadata['result_definitions'][rid])
        definitions.pop('effective_options', None)
        definitions.pop('options', None)
        statistics = {key: copy.deepcopy(value) for key, value in registry['statistics'].items()
                      if key.split('.', 1)[0] == rid}
        quantities = {key: {'source_key': copy.deepcopy(record.get('quantity_origins', {}).get(key[len(rid) + 1:])),
                            'registry_key': ['statistics', key]}
                      for key in statistics}
        producer = {key: copy.deepcopy(value) for key, value in metadata['producers'][rid].items()
                    if key != 'effective_options'}
        reference = {'kind': 'json', 'path': path.relative_to(root).as_posix(),
                     'keys': ['records', rid], 'content_version': state.content_hash(record)}
        result = {'result_id': rid, 'statistics': statistics, 'quantity_origins': quantities,
                  'definitions': definitions, 'producer': producer, 'source_reference': reference}
        sources['result:' + rid] = {'text': json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False),
                                   'origin_id': rid, 'location': reference['path'], 'research_result': result}
    selected = gallery_items(root, gallery_path or path, item_ids=list(item_ids)) if item_ids else []
    for item in selected:
        admitted = [rid for rid in result_ids if rid in item['result_ids']]
        if not admitted:
            raise ValueError('selected display has no selected result: ' + item['id'])
        for rid in admitted:
            producer = item['metadata'].get('producers', {}).get(rid, {})
            expected = sources['result:' + rid]['research_result']['producer']
            if any(producer.get(key) != expected.get(key) for key in ('identity', 'references', 'run_id')):
                raise ValueError('display and result producer differ: ' + item['id'] + '/' + rid)
        metadata = {key: copy.deepcopy(value) for key, value in item['metadata'].items()
                    if key not in ('producers', 'result_definitions', 'effective_options', 'options')}
        metadata['result_definitions'] = {
            rid: {key: copy.deepcopy(value) for key, value in item['metadata'].get('result_definitions', {}).get(rid, {}).items()
                  if key not in ('effective_options', 'options')}
            for rid in admitted}
        display = {key: copy.deepcopy(item[key]) for key in
                   ('id', 'title', 'kind', 'columns', 'display', 'interpretation', 'status', 'links', 'files', 'source_reference')}
        display['result_ids'] = admitted
        display['display']['selected_result_ids'] = admitted
        if 'model_labels' in display['display']:
            display['display']['model_labels'] = {rid: label for rid, label in display['display']['model_labels'].items()
                                                 if rid in admitted}
        display['metadata'] = metadata
        display['rows'] = []
        display['row_indices'] = []
        for index, row in zip(item['row_indices'], item['rows']):
            if row['result_id'] in admitted:
                display['rows'].append(copy.deepcopy(row))
                display['row_indices'].append(index)
        for key in ('findings', 'issues', 'adoption_decision'):
            if key in item:
                display[key] = copy.deepcopy(item[key])
        sources['display:' + item['id']] = {
            'text': json.dumps(display, ensure_ascii=False, indent=2, allow_nan=False),
            'origin_id': admitted[0] if len(admitted) == 1 else item['id'],
            'location': item['source_reference']['path'], 'display_item': display}
    return {'result_ids': list(result_ids), 'item_ids': list(item_ids),
            'sources': argument.source_catalog(sources)}


def gallery_compare(root, gallery_spec_path, item_ids):
    """Return explicitly selected saved displays and their defining differences."""
    selected = gallery_items(root, gallery_spec_path, item_ids=item_ids)
    fields = (*COMPARISON_FIELDS, 'variables', 'specification', 'sample_policy', 'estimator', 'ci_kind')
    differences = {key: {item['id']: item['metadata'].get(key) for item in selected}
                   for key in fields if any(item['metadata'].get(key) != selected[0]['metadata'].get(key)
                                             for item in selected[1:])}
    definitions = {}
    for item in selected:
        for result_id in item['result_ids']:
            definition = item['metadata'].get('result_definitions', {}).get(result_id, item['metadata'])
            definitions[item['id'] + '/' + result_id] = definition
    names = list(definitions)
    result_differences = {field: {key: definition.get(field) for key, definition in definitions.items()}
                          for field in fields if names and any(definitions[key].get(field) != definitions[names[0]].get(field)
                                                                for key in names[1:])}
    required = ('estimand', 'population', 'sample', 'period', 'weights')
    unrecorded = {key: [field for field in required if field not in definition or
                       (definition[field] is None and field != 'weights')]
                  for key, definition in definitions.items()}
    unrecorded = {key: value for key, value in unrecorded.items() if value}
    return {'items': selected, 'definition_differences': differences,
            'result_definition_differences': result_differences,
            'comparison_contract': {
                'status': 'different_definitions' if any(key in result_differences for key in COMPARISON_FIELDS)
                          else 'definition_fields_required' if unrecorded else 'aligned_saved_definitions',
                'fields': list(COMPARISON_FIELDS), 'unrecorded_fields': unrecorded,
                'automatic_reweighting': False, 'analysis_executed': False},
            'regression_table': gallery_regression_comparison(selected)}


def saved_display_definitions(result_id, saved):
    """Map a producer's display blocks into the existing registry.items contract."""
    definitions = []
    kinds = {'table1': 'descriptive', 'table': 'table', 'regression': 'table', 'balance': 'group_comparison',
             'sample-flow': 'sample_composition', 'trend': 'time_series', 'event-study': 'event_study',
             'iv': 'coefficient', 'heterogeneity': 'coefficient',
             'sensitivity': 'robustness', 'counterfactual': 'structural',
             'att-gt': 'att_gt', 'cohort-event': 'cohort_event', 'parallel-trends': 'parallel_trends',
             'iv-first-stage': 'iv_first_stage', 'iv-reduced-form': 'iv_reduced_form',
             'iv-confidence-set': 'iv_confidence_set', 'synthetic-control': 'scm',
             'scm-gap': 'scm_gap', 'scm-placebo': 'scm_placebo', 'binscatter': 'binned_scatter',
             'equilibrium': 'structural', 'geography': 'geo'}
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
            x = next((key for key in ('event_time', 'time', 'period', 'running', 'bin_mid', 'x', 'term', 'variable', 'scenario', 'group') if key in keys), None)
            y = next((key for key in ('estimate', 'value', 'mean', 'count', 'density', 'middle', 'n') if key in keys), None)
            if kind in ('descriptive', 'sample_composition', 'group_comparison', 'table'):
                plot_type = 'table'
            elif kind == 'distribution':
                plot_type = {'histogram': 'bar', 'density': 'density', 'ecdf': 'ecdf', 'box': 'box'}[distribution_type]
            else:
                plot_type = kind if kind in PLOT_TYPES else 'line'
            if kind == 'att_gt' and 'cohort' in keys:
                x = 'time' if 'time' in keys else x
                y = 'cohort'
            elif kind == 'smd' and 'smd' in keys:
                y = 'smd'
            elif kind == 'rdd':
                x = next((key for key in ('running', 'x', 'bin_mid', 'mean_x') if key in keys), None)
            if (x is None or y is None) and not (kind == 'geo' and 'geometry' in keys) and kind != 'iv_confidence_set':
                plot_type = 'table'
            display = {'plot_type': plot_type, 'style': 'paper',
                       'formats': {key: '.3g' for key in keys if any(type(row.get(key)) in (int, float) for row in rows)}}
            if kind == 'rdd' and plot_type == 'table':
                order = ('term', 'estimate', 'se', 'ci_low', 'ci_high', 'p_value')
                display['column_order'] = [key for key in order if key in keys] + [key for key in keys if key not in order]
                display['height'] = max(300, min(1600, 160 + len(rows) * 34))
            if source_kind == 'table1':
                display['column_order'] = [key for key in keys if key in ('variable', 'group', 'period', 'mean', 'sd', 'median', 'min', 'max', 'n', 'unit') or key.startswith('q')]
                display['height'] = max(300, min(1600, 160 + len(rows) * 34))
            if plot_type != 'table':
                value_key = next((key for key in ('estimate', 'value') if key in keys), None) if kind in ('att_gt', 'geo') else y
                for column in columns:
                    if column['key'] == value_key:
                        column['unit'] = metadata.get('unit', '')
                    if column['key'] == x and kind == 'distribution' and plot_type != 'box':
                        column['unit'] = metadata.get('outcome_unit', '')
                display.update(x=x, y=y, series='group' if 'group' in keys else 'series' if 'series' in keys else None,
                               lower=next((key for key in ('ci_low', 'conf_low', 'lower') if key in keys), None),
                               upper=next((key for key in ('ci_high', 'conf_high', 'upper') if key in keys), None))
                for field in ('component', 'cohort', 'time', 'geometry'):
                    if field in keys:
                        display[field] = field
                if kind in ('att_gt', 'geo'):
                    display['value'] = value_key
                if plot_type in ('coefficient', 'smd'):
                    display['orientation'] = 'horizontal'
            if 'columns' in block:
                columns = copy.deepcopy(block['columns'])
            if 'display' in block:
                if not isinstance(block['display'], dict):
                    raise ValueError('saved display settings must be an object')
                display.update(copy.deepcopy(block['display']))
            suffix = '-'.join(path[1:]) or source_kind
            identity_suffix = '-'.join(path) if path[0] == 'displays' else suffix
            identity = result_id + '-' + re.sub(r'[^A-Za-z0-9_-]', '_', identity_suffix)
            definitions.append({'id': identity, 'title': block.get('title', result_id + ' / ' + suffix),
                                'kind': kind, 'result_ids': [result_id], 'columns': columns,
                                'rows': rows, 'metadata': metadata, 'display': display})
        for key, value in block.items():
            if key not in ('rows', 'columns', 'metadata', 'kind', 'display') and isinstance(value, dict):
                visit(value, path + [key])
    visit(saved.get('display'), ['display'])
    visit(saved.get('displays'), ['displays'])
    group_time = saved.get('diagnostics', {}).get('group_time', {})
    if group_time.get('cells') and not any(item['kind'] == 'att_gt' for item in definitions):
        # These cells already contain official estimates and interval endpoints.
        # Retain row-level sample IDs and weights in the source result only.
        rows = [{key: cell[key] for key in ('time', 'event_time', 'base_period', 'role', 'estimate', 'se', 'ci_low', 'ci_high')
                 if key in cell} | {'cohort': cell['group']} for cell in group_time['cells']]
        options = saved.get('diagnostics', {}).get('effective_options', {}).get('att_gt', {})
        metadata = {**saved.get('display', {}).get('metadata', {}), 'estimand': 'ATT(g,t)',
                    'aggregation': 'unaggregated group-time cells', 'base_period': options.get('base_period'),
                    'control_group': options.get('control_group'), 'anticipation': options.get('anticipation'),
                    'interval_type': None, 'confidence_level': None}
        if 'cband' in options:
            metadata['interval_type'] = 'simultaneous' if options['cband'] else 'pointwise'
        if options.get('alp') is not None:
            metadata['confidence_level'] = 1 - options['alp']
        for key in ('cohort_contributions', 'aggregation_weights'):
            metadata[key] = None
        visit({'kind': 'att_gt', 'rows': rows, 'metadata': metadata}, ['diagnostics', 'group_time'])
        visit({'kind': 'cohort_event', 'rows': rows, 'metadata': metadata}, ['diagnostics', 'group_time'])
        definitions[-1]['id'] += '-cohort-event'
    gaps = saved.get('diagnostics', {}).get('period_gap')
    if gaps and not any(item['kind'] == 'scm_gap' for item in definitions):
        visit({'kind': 'scm_gap', 'rows': [{'time': row['time'], 'estimate': row['gap']} for row in gaps],
               'metadata': {**saved.get('adopted', {}),
                            'estimand': 'treated-minus-synthetic outcome gap'}}, ['diagnostics', 'period_gap'])
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
                                         'lower': quantities.get('confidence_lower.' + term, quantities.get('confidence_95_lower.' + term, {})).get('value'),
                                         'upper': quantities.get('confidence_upper.' + term, quantities.get('confidence_95_upper.' + term, {})).get('value'),
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
    if isinstance(value, list):
        return ', '.join(gallery_cell(part, key, display) for part in value)
    if isinstance(value, dict):
        return ', '.join(str(name) + ': ' + gallery_cell(part, key, display) for name, part in value.items())
    if type(value) in (int, float) and key in display.get('formats', {}):
        return format(value, display['formats'][key])
    return str(value)


def gallery_regression_comparison(items):
    """Present saved tidy/glance quantities; estimation and inference stay upstream.

    The numeric rows remain available to existing consumers. ``presentation`` is
    the shared, formatted table consumed by HTML, LaTeX, figures and meetings.
    """
    display = items[0].get('display', {}) if items else {}
    models, definitions, model_info, formats = {}, {}, {}, {}
    for item in items:
        item_display = item.get('display', {})
        for row in item['rows']:
            if 'term' in row and 'estimate' in row:
                definition = {**item.get('metadata', {}), **item.get('metadata', {}).get('result_definitions', {}).get(row['result_id'], {})}
                model = str(row.get(item_display.get('model_column'), row['result_id']))
                outcome = row.get(item_display.get('outcome_column') or 'outcome', definition.get('outcome'))
                stage = row.get('stage', definition.get('stage'))
                identity = (row['result_id'], model, gallery_cell(outcome, '', {}), gallery_cell(stage, '', {}))
                panel = row.get('panel', ' / '.join(str(row[key]) for key in ('subgroup', 'group', 'period') if row.get(key) is not None))
                term = (str(panel or ''), str(row['term']))
                previous = models.setdefault(identity, {}).get(term)
                if previous is not None and previous != row:
                    raise ValueError('saved regression rows repeat a model/term; select model_column or save distinct panel terms')
                models[identity][term] = row
                definitions[identity] = definition
                model_info[identity] = {'result_id': row['result_id'], 'model': model,
                                        'outcome': outcome, 'stage': stage}
                formats[identity] = item_display
    identities = list(models)
    def matches(identity, name):
        info = model_info[identity]
        return name in (info['model'], info['result_id'], info.get('key'))
    for identity in identities:
        info = model_info[identity]
        siblings = [key for key in identities if model_info[key]['model'] == info['model']]
        suffix = [str(info[field]) for field in ('outcome', 'stage') if info[field] is not None]
        info['key'] = info['model'] if len(siblings) == 1 else info['result_id'] + ' / ' + ' / '.join(suffix or [info['model']])
    ordered = [identity for name in display.get('model_order', []) for identity in identities if matches(identity, name)]
    identities = list(dict.fromkeys(ordered + identities))
    grouped = [identity for group in display.get('column_groups', []) for identity in identities
               if any(matches(identity, name) for name in group['models'])]
    identities = list(dict.fromkeys(grouped + identities))
    keys = [model_info[identity]['key'] for identity in identities]
    if len(set(keys)) != len(keys):
        raise ValueError('saved model columns require distinct identities')
    rows = []
    terms = list(dict.fromkeys(term for model in models.values() for term in model))
    terms = list(dict.fromkeys([term for name in display.get('term_order', []) for term in terms if term[1] == name] + terms))
    panels = display.get('panels', [])
    if panels:
        terms = list(dict.fromkeys([term for panel in panels for name in panel['terms'] for term in terms if term[1] == name] + terms))
    body = []
    current_panel = None
    def saved(row, names):
        return next((row[key] for key in names if key in row), None)
    def number(row, names, identity):
        key = next((key for key in names if key in row), names[0])
        value = row.get(key)
        settings = formats[identity]
        if value is None:
            return ''
        if type(value) in (int, float):
            return format(value, settings.get('formats', {}).get(key, '.' + str(settings.get('digits', 3)) + 'f'))
        return gallery_cell(value, key, settings)
    for term in terms:
        panel_label = next((panel['label'] for panel in panels if term[1] in panel['terms']), term[0])
        if panel_label and panel_label != current_panel:
            body.append({'kind': 'panel', 'label': panel_label, 'cells': [''] * len(identities)})
        current_panel = panel_label
        term_label = display.get('term_labels', {}).get(term[1], term[1])
        if term[0] and panel_label != term[0]:
            term_label += ' (' + term[0] + ')'
        estimates, errors, intervals, probabilities = [], [], [], []
        for identity in identities:
            row = models[identity].get(term, {})
            estimate = number(row, ('estimate',), identity)
            if display.get('show_stars', False) and estimate:
                symbol = saved(row, ('significance', 'stars'))
                p = saved(row, ('p_value', 'pvalue', 'p.value'))
                if symbol is None and type(p) in (int, float):
                    symbol = '***' if p < .01 else '**' if p < .05 else '*' if p < .1 else ''
                estimate += str(symbol or '')
            estimates.append(estimate)
            se = number(row, ('se', 'standard_error', 'std.error'), identity)
            errors.append('(' + se + ')' if se else '')
            low, high = saved(row, ('ci_low', 'lower', 'conf.low')), saved(row, ('ci_high', 'upper', 'conf.high'))
            intervals.append('[' + number(row, ('ci_low', 'lower', 'conf.low'), identity) + ', ' +
                             number(row, ('ci_high', 'upper', 'conf.high'), identity) + ']'
                             if low is not None and high is not None else '')
            p = number(row, ('p_value', 'pvalue', 'p.value'), identity)
            probabilities.append(p)
        body.append({'kind': 'coefficient', 'label': term_label, 'cells': estimates})
        if display.get('show_se', True) and any(errors):
            body.append({'kind': 'se', 'label': '', 'cells': errors})
        if display.get('show_ci', False) and any(intervals):
            body.append({'kind': 'ci', 'label': '区間', 'cells': intervals})
        if display.get('show_p', False) and any(probabilities):
            body.append({'kind': 'p', 'label': 'p 値', 'cells': probabilities})
        for names, label in [(('estimate',), '推定値'), (('se', 'standard_error', 'std.error'), '標準誤差'),
                             (('ci_low', 'lower', 'conf.low'), '区間下端'), (('ci_high', 'upper', 'conf.high'), '区間上端'),
                             (('p_value', 'pvalue', 'p.value'), 'p 値'), (('unit',), '単位')]:
            if any(any(key in model.get(term, {}) for key in names) for model in models.values()):
                label = ' / '.join(value for value in (*term, label) if value)
                rows.append({'quantity': label, **{model_info[identity]['key']: saved(models[identity].get(term, {}), names) for identity in identities}})
    fields = [('n', '観測数'), ('n_clusters', 'クラスタ数'), ('fixed_effects', '固定効果'),
              ('controls', '統制変数'), ('period', '期間'), ('sample', 'サンプル'),
              ('sample_policy', 'サンプル方式'), ('weights', '重み'), ('estimator', '推定法'),
              ('specification', '仕様'), ('stage', '推定段階'), ('first_stage_result_id', '第一段階の結果'),
              ('second_stage_result_id', '第二段階の結果'), ('instruments', '操作変数'),
              ('treatment_group', '処置群'), ('control_group', '対照群'), ('cohort', '導入群'),
              ('aggregation', '集計法'), ('ci_kind', '区間の種類'), ('interval_type', '保存区間'),
              ('confidence_level', '区間水準'), ('reference_distribution', '参照分布'),
              ('degrees_of_freedom', '自由度'), ('cluster', 'クラスタ単位'), ('unit', '単位')]
    if 'statistic_rows' in display:
        fields = [(entry['field'], entry['label']) for entry in display['statistic_rows']]
    footer = []
    for key, label in fields:
        values = {}
        for identity in identities:
            value = model_info[identity].get(key) if key == 'stage' else definitions[identity].get(key)
            if value is None:
                saved_values = [row[key] for row in models[identity].values() if key in row]
                if saved_values and all(value == saved_values[0] for value in saved_values):
                    value = saved_values[0]
            values[model_info[identity]['key']] = value
        saved_weight = key == 'weights' and any('weights' in definitions[identity] for identity in identities)
        if any(value is not None for value in values.values()) or saved_weight or 'statistic_rows' in display:
            rows.append({'quantity': label, **{key: gallery_cell(value, '', {}) if isinstance(value, (dict, list)) else value for key, value in values.items()}})
            footer.append({'label': label, 'cells': [gallery_cell(values[name], key, formats[identity]) if values[name] is not None else
                                                    'なし' if key == 'weights' and 'weights' in definitions[identity] else ''
                                                    for name, identity in zip(keys, identities)]})
    headers = []
    if display.get('column_groups'):
        groups = [{'text': '', 'colspan': 1}]
        for identity in identities:
            label = next((group['label'] for group in display['column_groups'] if any(matches(identity, name) for name in group['models'])), '')
            if len(groups) > 1 and groups[-1]['text'] == label:
                groups[-1]['colspan'] += 1
            else:
                groups.append({'text': label, 'colspan': 1})
        headers.append(groups)
    if any(model_info[identity]['outcome'] is not None for identity in identities):
        outcomes = [{'text': 'アウトカム', 'colspan': 1}]
        for identity in identities:
            label = gallery_cell(model_info[identity]['outcome'], '', {})
            if len(outcomes) > 1 and outcomes[-1]['text'] == label:
                outcomes[-1]['colspan'] += 1
            else:
                outcomes.append({'text': label, 'colspan': 1})
        headers.append(outcomes)
    labels = [display.get('model_labels', {}).get(key, display.get('model_labels', {}).get(model_info[identity]['model'], key)) for key, identity in zip(keys, identities)]
    headers.append([{'text': '項目', 'colspan': 1}, *[{'text': label, 'colspan': 1} for label in labels]])
    headers.append([{'text': '', 'colspan': 1}, *[{'text': '(' + str(index + 1) + ')', 'colspan': 1} for index in range(len(keys))]])
    notes = list(dict.fromkeys(note for item in items for note in gallery_notes(item)))
    if display.get('show_se', True) and any(row['kind'] == 'se' for row in body):
        notes.insert(0, '括弧内は保存された標準誤差。')
    if display.get('show_stars', False):
        notes.append('保存された有意記号を優先。保存 p 値の表示規則: * p < 0.10、** p < 0.05、*** p < 0.01。')
    presentation = {'headers': headers, 'body': body, 'footer': footer, 'notes': notes,
                    'caption': display.get('title', items[0].get('title', '') if items else ''),
                    'label': display.get('latex_label', ''), 'number': str(display.get('table_number', '')),
                    'preset': display.get('preset', 'meeting' if display.get('style') == 'presentation' else 'paper')}
    return {'rows': rows, 'columns': [{'key': 'quantity', 'label': '項目', 'unit': ''},
                                     *[{'key': key, 'label': label, 'unit': ''} for key, label in zip(keys, labels)]],
            'presentation': presentation}


def gallery_notes(item):
    notes = list(item.get('display', {}).get('notes', []))
    labels = {'estimand': '推定対象', 'sample': 'サンプル', 'sample_policy': 'サンプル方式',
              'population': '母集団', 'period': '期間', 'unit': '単位', 'weights': '重み',
              'ci_kind': '区間', 'interval_type': '保存区間', 'confidence_level': '区間水準',
              'reference_time': '基準期', 'reference_event_time': '基準イベント期',
              'base_period': '基準期の定義', 'treatment_time': '処置時点', 'treatment_event_time': '処置イベント期', 'cutoff': '閾値',
              'bandwidth': '帯域幅', 'treatment_group': '処置群', 'control_group': '対照群',
              'comparison_group': '比較群', 'aggregation': '集計法', 'aggregation_weights': '集計重み',
              'n': '観測数', 'n_clusters': 'クラスタ数', 'denominator': '分母',
              'quantile_method': '分位点', 'distribution_type': '分布表示'}
    requested = item.get('display', {}).get('note_fields')
    if requested is not None:
        labels = {key: labels.get(key, key) for key in requested}
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


def gallery_table_presentation(item):
    if item['metadata'].get('table_type') == 'regression':
        view = gallery_projection({**item, 'display': {**item.get('display', {}), 'column_order': [col['key'] for col in item['columns']]}})
        return gallery_regression_comparison([view])['presentation']
    view = gallery_projection(item)
    display = item.get('display', {})
    headings = [col['label'] + (' (' + col['unit'] + ')' if col['unit'] else '') for col in view['columns']]
    cells = [[gallery_cell(row.get(col['key']), col['key'], display) for col in view['columns']] for row in view['rows']]
    return {'headers': [[{'text': heading, 'colspan': 1} for heading in headings]],
            'body': [{'kind': 'row', 'label': row[0], 'cells': row[1:]} for row in cells],
            'footer': [], 'notes': gallery_notes(item), 'caption': view['title'],
            'label': display.get('latex_label', ''), 'number': str(display.get('table_number', '')),
            'preset': display.get('preset', 'meeting' if display.get('style') == 'presentation' else 'paper')}


def gallery_presentation(presentation, markdown=False):
    """Render the same header/body/footer contract used by meeting consumers."""
    count = sum(cell['colspan'] for cell in presentation['headers'][-1])
    if markdown:
        def line(values):
            return '| ' + ' | '.join(str(value).replace('|', '\\|').replace('\n', '<br>') for value in values) + ' |'
        headers = []
        for header in presentation['headers']:
            expanded = [cell['text'] for cell in header for _ in range(cell['colspan'])]
            headers.append(expanded)
        combined = ['<br>'.join(dict.fromkeys(row[index] for row in headers if row[index])) for index in range(count)]
        rows = [[row['label'], *row['cells']] for row in presentation['body'] + presentation['footer']]
        return '\n'.join([line(combined), line(['---'] * count), *(line(row) for row in rows)]) + '\n'
    headers = ''.join('<tr>' + ''.join('<th colspan="' + str(cell['colspan']) + '">' + html.escape(cell['text']) + '</th>' for cell in header) + '</tr>' for header in presentation['headers'])
    rows = []
    for row in presentation['body']:
        if row.get('kind') == 'panel':
            rows.append('<tr class="panel"><th colspan="' + str(count) + '">' + html.escape(row['label']) + '</th></tr>')
        else:
            rows.append('<tr class="' + row.get('kind', 'row') + '"><th scope="row">' + html.escape(row['label']) + '</th>'
                        + ''.join('<td>' + html.escape(str(value)) + '</td>' for value in row['cells']) + '</tr>')
    footer = ''.join('<tr><th scope="row">' + html.escape(row['label']) + '</th>' + ''.join('<td>' + html.escape(str(value)) + '</td>' for value in row['cells']) + '</tr>' for row in presentation['footer'])
    style = ('<style>.econ-table{border-collapse:collapse;width:100%;font-size:14px;color:#213547;'
             'border-top:2px solid #28323c;border-bottom:2px solid #28323c;font-family:system-ui,sans-serif;}'
             '.econ-table th,.econ-table td{padding:7px 12px;text-align:center;white-space:pre-line;}'
             '.econ-table th:first-child{text-align:left;}.econ-table tbody th,.econ-table tfoot th{font-weight:normal;}'
             '.econ-table thead{border-bottom:1px solid #65717e;}.econ-table tfoot{border-top:1px solid #65717e;}'
             '.econ-table .panel th{font-weight:600;padding-top:14px;border-top:1px solid #aab2ba;}'
             '.econ-table .se td,.econ-table .ci td,.econ-table .p td{padding-top:0;color:#46505c;}'
             '.econ-table .coefficient td{padding-bottom:2px;}.econ-table.meeting{font-size:18px;}</style>')
    return style + '<table class="econ-table ' + presentation.get('preset', 'paper') + '"><thead>' + headers + '</thead><tbody>' + ''.join(rows) + '</tbody><tfoot>' + footer + '</tfoot></table>'


def gallery_table(item, markdown=False):
    return gallery_presentation(gallery_table_presentation(item), markdown=markdown)


def gallery_plot_table(axis, presentation, family, font_size, width):
    """Draw booktabs-style horizontal rules and genuine spanning headers."""
    import textwrap
    count = sum(cell['colspan'] for cell in presentation['headers'][-1])
    label_width = .32 if count > 1 else 1
    widths = [label_width] + [(1 - label_width) / (count - 1)] * (count - 1)
    boundaries = [0]
    for value in widths:
        boundaries.append(boundaries[-1] + value)
    records = []
    for header in presentation['headers']:
        records.append(('header', header))
    records += [(row.get('kind', 'row'), [{'text': row['label'], 'colspan': count}] if row.get('kind') == 'panel'
                 else [{'text': row['label'], 'colspan': 1}, *[{'text': str(value), 'colspan': 1} for value in row['cells']]])
                for row in presentation['body']]
    footer_start = len(records)
    records += [('footer', [{'text': row['label'], 'colspan': 1}, *[{'text': str(value), 'colspan': 1} for value in row['cells']]]) for row in presentation['footer']]
    prepared = []
    for kind, cells in records:
        column, wrapped = 0, []
        for cell in cells:
            span = cell['colspan']
            usable = sum(widths[column:column + span]) * width
            text = '\n'.join(textwrap.fill(part, max(5, int(usable / (font_size * .85)))) for part in cell['text'].splitlines())
            wrapped.append((column, span, text))
            column += span
        height = max((text.count('\n') + 1 for _, _, text in wrapped), default=1)
        prepared.append((kind, wrapped, height + (.35 if kind == 'se' else .7)))
    total = sum(height for _, _, height in prepared) or 1
    y = 1
    axis.set_axis_off()
    axis.plot([0, 1], [y, y], transform=axis.transAxes, color='#20252b', linewidth=1.2)
    for index, (kind, cells, height) in enumerate(prepared):
        if index == len(presentation['headers']) or index == footer_start or kind == 'panel':
            axis.plot([0, 1], [y, y], transform=axis.transAxes, color='#6b7280', linewidth=.65)
        for column, span, text in cells:
            left = boundaries[column]
            right = boundaries[column + span]
            centered = column > 0 or (kind == 'header' and span > 1)
            axis.text((left + right) / 2 if centered else left + .006, y - height / total / 2,
                      text, transform=axis.transAxes, ha='center' if centered else 'left', va='center',
                      fontsize=font_size, fontfamily=family,
                      fontweight='bold' if kind in ('header', 'panel') else 'normal',
                      color='#46505c' if kind in ('se', 'ci', 'p') else '#17212b')
        y -= height / total
    axis.plot([0, 1], [y, y], transform=axis.transAxes, color='#20252b', linewidth=1.2)


def gallery_plot_panel(axis, rows, display, metadata, columns, family, font_size):
    """Draw one panel from saved points, endpoints, curves or polygon geometry."""
    import numpy as np
    from matplotlib import colors as mpl_colors
    plot_type = display.get('plot_type', 'line')
    xkey, ykey = display.get('x'), display.get('y')
    if plot_type == 'att_gt':
        xkey = display.get('time', xkey or 'time')
        cohort_key = display.get('cohort', 'cohort')
        ykey = display.get('value', ykey or 'estimate')
        times = list(dict.fromkeys(row[xkey] for row in rows if row.get(xkey) is not None))
        cohorts = list(dict.fromkeys(row[cohort_key] for row in rows if row.get(cohort_key) is not None))
        if not times or not cohorts:
            raise ValueError('ATT(g,t) requires saved time and cohort columns')
        matrix = np.full((len(cohorts), len(times)), np.nan)
        occupied = set()
        for row in rows:
            if row.get(xkey) is None or row.get(cohort_key) is None:
                continue
            cell = (cohorts.index(row[cohort_key]), times.index(row[xkey]))
            if cell in occupied:
                raise ValueError('ATT(g,t) repeats cohort/time; select a result or facet by saved model')
            occupied.add(cell)
            if row.get(ykey) is not None:
                matrix[cell] = row[ykey]
        finite = matrix[np.isfinite(matrix)]
        norm = mpl_colors.TwoSlopeNorm(vcenter=0) if len(finite) and finite.min() < 0 < finite.max() else None
        artist = axis.imshow(np.ma.masked_invalid(matrix), aspect='auto', origin='lower', cmap='RdBu_r' if norm else 'viridis', norm=norm)
        axis.set_xticks(range(len(times)), [str(value) for value in times])
        axis.set_yticks(range(len(cohorts)), [str(value) for value in cohorts])
        axis.set_xlabel(display.get('x_label') or columns.get(xkey, xkey))
        axis.set_ylabel(display.get('y_label') or columns.get(cohort_key, cohort_key))
        axis.figure.colorbar(artist, ax=axis, label=display.get('color_label') or columns.get(ykey, ykey))
        return
    if plot_type == 'geo':
        from matplotlib.path import Path as PlotPath
        from matplotlib.patches import PathPatch
        from matplotlib.collections import PatchCollection
        geometry_key = display.get('geometry', 'geometry')
        value_key = display.get('value', ykey or 'value')
        patches, values, points, point_values = [], [], [], []
        for row in rows:
            geometry = json.loads(row[geometry_key])
            if geometry.get('type') == 'Feature':
                geometry = geometry['geometry']
            kind, coordinates = geometry.get('type'), geometry.get('coordinates')
            if kind in ('Point', 'MultiPoint'):
                saved_points = [coordinates] if kind == 'Point' else coordinates
                points.extend([point[:2] for point in saved_points])
                point_values.extend([row.get(value_key)] * len(saved_points))
                continue
            polygons = [coordinates] if kind == 'Polygon' else coordinates if kind == 'MultiPolygon' else None
            if polygons is None:
                raise ValueError('geo requires saved Point, MultiPoint, Polygon or MultiPolygon GeoJSON geometry')
            for polygon in polygons:
                vertices, codes = [], []
                for ring in polygon:
                    if len(ring) < 4:
                        raise ValueError('saved polygon rings require at least four coordinates')
                    vertices.extend([point[:2] for point in ring])
                    codes.extend([PlotPath.MOVETO, *([PlotPath.LINETO] * (len(ring) - 2)), PlotPath.CLOSEPOLY])
                patches.append(PathPatch(PlotPath(vertices, codes)))
                values.append(row.get(value_key))
        finite = [value for value in values + point_values if value is not None]
        norm = mpl_colors.Normalize(min(finite), max(finite)) if finite else None
        artist = None
        if patches:
            artist = PatchCollection(patches, cmap='viridis', norm=norm, edgecolor='white', linewidth=.6, facecolor='#d7dce2')
            if finite:
                artist.set_array(np.ma.masked_invalid(np.array([float(value) if value is not None else np.nan for value in values])))
            axis.add_collection(artist)
        if points:
            x, y = zip(*points)
            artist = axis.scatter(x, y, c=[value if value is not None else np.nan for value in point_values] if finite else '#d7dce2',
                                  cmap='viridis' if finite else None, norm=norm, s=42, edgecolors='white', linewidths=.6, plotnonfinite=True)
        axis.autoscale_view()
        axis.set_aspect('equal')
        if finite and artist is not None:
            colorbar = axis.figure.colorbar(artist, ax=axis, label=display.get('color_label') or columns.get(value_key, value_key))
            if metadata.get('unit') in ('year', 'years') and len(set(finite)) <= 12:
                colorbar.set_ticks(sorted(set(finite)))
        axis.set_xlabel(display.get('x_label') or metadata.get('x_label', ''))
        axis.set_ylabel(display.get('y_label') or metadata.get('y_label', ''))
        return
    if plot_type == 'iv_confidence_set':
        low_key, high_key = display.get('lower') or 'lower', display.get('upper') or 'upper'
        series_key = display.get('series') or 'term'
        names = list(dict.fromkeys((row['result_id'], str(row.get(series_key, ''))) for row in rows))
        finite = [row[key] for row in rows for key in (low_key, high_key) if type(row.get(key)) in (int, float)]
        limits = display.get('x_limits') or ([min(finite) - max(1, max(finite) - min(finite)) * .1,
                                            max(finite) + max(1, max(finite) - min(finite)) * .1] if finite else None)
        for row in rows:
            name = (row['result_id'], str(row.get(series_key, '')))
            index = names.index(name)
            low, high = row.get(low_key), row.get(high_key)
            if row.get('set_type', metadata.get('set_type')) == 'empty':
                axis.text(.5, index, '空集合', transform=axis.get_yaxis_transform(), ha='center')
                continue
            left_open, right_open = row.get('lower_unbounded', False), row.get('upper_unbounded', False)
            if left_open and right_open and limits is None:
                axis.annotate('', xy=(.97, index), xytext=(.03, index), xycoords=axis.get_yaxis_transform(),
                              arrowprops={'arrowstyle': '<->', 'color': '#245b8a', 'linewidth': 2})
                axis.text(.5, index + .12, r'$\mathbb{R}$', transform=axis.get_yaxis_transform(), ha='center')
                continue
            if (left_open or right_open) and limits is None:
                raise ValueError('unbounded confidence sets require display x_limits or saved finite endpoints')
            left, right = limits[0] if left_open else low, limits[1] if right_open else high
            if left is None or right is None:
                continue
            if left > right:
                raise ValueError('saved confidence-set endpoints must be ordered')
            axis.hlines(index, left, right, color='#245b8a', linewidth=3)
            axis.scatter([left, right], [index, index], color='#245b8a', marker='|', s=90)
            for endpoint, unbounded, marker in ((left, left_open, '<'), (right, right_open, '>')):
                if unbounded:
                    axis.scatter([endpoint], [index], marker=marker, color='#245b8a', s=55)
        multiple_results = len({name[0] for name in names}) > 1
        labels = [display.get('series_labels', {}).get(series, series) or result_id for result_id, series in names]
        if multiple_results and series_key != 'result_id':
            labels = [result_id + (' / ' + label if series else '') for (result_id, series), label in zip(names, labels)]
        axis.set_yticks(range(len(names)), labels)
        axis.set_xlabel(display.get('x_label') or metadata.get('parameter_definition', '係数'))
        if limits:
            axis.set_xlim(*limits)
        else:
            axis.set_xticks([])
        axis.set_ylim(-.6, max(.6, len(names) - .4))
        return
    if not xkey or not ykey:
        raise ValueError('plot display requires x and y saved column keys')
    for name in ('x', 'y'):
        getattr(axis, 'set_' + name + 'scale')(display.get(name + '_scale', 'linear'))
    units = {row.get('unit') for row in rows if row.get(ykey) is not None and row.get('unit')}
    if len(units) > 1:
        raise ValueError('One plot axis requires one saved unit; select matching saved series or a facet')
    if any(row.get(ykey) is not None and type(row[ykey]) not in (int, float) for row in rows):
        raise ValueError('plot y column must contain numeric saved values or null')
    labels = list(dict.fromkeys(row[xkey] for row in rows if row.get(xkey) is not None))
    categorical = any(type(value) not in (int, float) for value in labels)
    if plot_type == 'rdd' and categorical:
        raise ValueError('RDD plots require numeric saved running-variable coordinates')
    horizontal = display.get('orientation') == 'horizontal'
    component_key = display.get('component', 'component')
    series_key = display.get('series')
    if not series_key:
        series_key = 'result_id' if len({row['result_id'] for row in rows}) > 1 else component_key
    multiple_results = len({row['result_id'] for row in rows}) > 1 and series_key != 'result_id'
    if plot_type == 'cohort_event' and not display.get('series'):
        series_key = display.get('cohort') or 'cohort'
        multiple_results = len({row['result_id'] for row in rows}) > 1
    def group_key(row):
        return (row['result_id'] if multiple_results else '', str(row.get(series_key, '')))
    groups = list(dict.fromkeys(group_key(row) for row in rows))
    order = display.get('series_order', [])
    groups = [group for name in order for group in groups if group[1] == name] + [group for group in groups if group[1] not in order]
    palette = ['#245b8a', '#b4513b', '#31836b', '#8a5b9e', '#b18324', '#427f8f']
    cutoff = metadata.get('cutoff')
    for index, group in enumerate(groups):
        selected = [row for row in rows if row.get(xkey) is not None and group_key(row) == group]
        components = list(dict.fromkeys((str(row.get(component_key, '')), str(row.get('role', ''))) for row in selected))
        for component, role in components:
            component_rows = [row for row in selected if (str(row.get(component_key, '')), str(row.get('role', ''))) == (component, role)]
            role = {'pretreatment_diagnostic': 'pre_diagnostic', 'post_treatment_att': 'att'}.get(role, role)
            if plot_type == 'rdd':
                sides = list(dict.fromkeys(row.get('side', row.get('group')) for row in component_rows))
                if sides != [None]:
                    if None in sides:
                        raise ValueError('saved RDD side/group must identify every row in a curve')
                    segments = [[row for row in component_rows if row.get('side', row.get('group')) == side] for side in sides]
                elif component in ('fit', 'fitted', 'line', 'curve', 'local_fit', 'band'):
                    raise ValueError('saved RDD curves require side/group to preserve both cutoff endpoints')
                elif type(cutoff) in (int, float):
                    segments = [[row for row in component_rows if row[xkey] < cutoff], [row for row in component_rows if row[xkey] >= cutoff]]
                else:
                    segments = [component_rows]
            else:
                segments = [component_rows]
            for segment_number, segment in enumerate(segments):
                if not segment:
                    continue
                path_order = display.get('path_order') if component == 'path' else None
                if path_order:
                    if any(type(row.get(path_order)) not in (int, float) for row in segment):
                        raise ValueError('a saved path requires numeric ordering coordinates')
                    segment = sorted(segment, key=lambda row: row[path_order])
                elif not categorical:
                    segment = sorted(segment, key=lambda row: row[xkey])
                xs = [labels.index(row[xkey]) if categorical else row[xkey] for row in segment]
                if plot_type in ('coefficient', 'smd') and len(groups) > 1:
                    xs = [value + (index - (len(groups) - 1) / 2) * .14 for value in xs]
                ys = [row[ykey] if row.get(ykey) is not None else float('nan') for row in segment]
                color = display.get('colors', {}).get(group[0] or group[1], display.get('colors', {}).get(group[1], palette[index % len(palette)]))
                label = display.get('series_labels', {}).get(group[1], group[1])
                if group[0]:
                    label = group[0] + (' / ' + label if label else '')
                if len({value[0] for value in components}) > 1 and component:
                    label += ' / ' + component
                if role:
                    role_label = {'pre_diagnostic': '処置前診断', 'reference': '基準期', 'att': 'ATT'}.get(role, role)
                    if series_key in ('term', 'role') and role in ('pre_diagnostic', 'reference', 'att'):
                        label = group[0] or segment[0]['result_id']
                    label += (' / ' if label else '') + role_label
                kwargs = {'label': label if segment_number == 0 else None, 'color': color}
                point = plot_type in ('scatter', 'coefficient', 'smd', 'binned_scatter') or component in ('points', 'bins', 'bin', 'binned_mean', 'observed', 'equilibrium')
                if plot_type in ('iv_first_stage', 'iv_reduced_form'):
                    point = component not in ('fit', 'fitted', 'line', 'curve', 'band')
                if plot_type == 'rdd' and component not in ('fit', 'fitted', 'line', 'curve', 'local_fit', 'band'):
                    point = True
                if component == 'region':
                    low_key, high_key = display.get('lower'), display.get('upper')
                    if not low_key or not high_key:
                        raise ValueError('a saved economic region requires lower and upper boundary columns')
                    bounds = [(row.get(low_key), row.get(high_key)) for row in segment]
                    if any(type(low) not in (int, float) or type(high) not in (int, float) or low > high
                           for low, high in bounds):
                        raise ValueError('saved economic region boundaries must be ordered numeric values')
                    low, high = zip(*bounds)
                    (axis.fill_betweenx if horizontal else axis.fill_between)(xs, low, high, alpha=.25, **kwargs)
                elif plot_type == 'box':
                    aliases = [('whislo', 'ymin'), ('q1', 'lower'), ('median', 'middle'), ('q3', 'upper'), ('whishi', 'ymax')]
                    for x, row in zip(xs, segment):
                        stats = [row.get(first, row.get(second)) for first, second in aliases]
                        if any(type(value) not in (int, float) for value in stats):
                            raise ValueError('Box plots require saved whiskers and quartiles')
                        axis.bxp([dict(zip(('whislo', 'q1', 'med', 'q3', 'whishi'), stats))], positions=[x + (index - (len(groups) - 1) / 2) * .2],
                                 widths=.5 / max(1, len(groups)), showfliers=False, vert=not horizontal, patch_artist=True,
                                 boxprops={'facecolor': color, 'alpha': .55}, medianprops={'color': '#172938'}, manage_ticks=False)
                elif plot_type == 'bar':
                    histogram = metadata.get('distribution_type') == 'histogram'
                    width = [row['bin_high'] - row['bin_low'] for row in segment] if histogram else .8 / max(1, len(groups))
                    positions = xs if histogram else [x + (index - (len(groups) - 1) / 2) * width for x in xs]
                    (axis.barh if horizontal else axis.bar)(positions, ys, **({'height': width} if horizontal else {'width': width}), alpha=.65 if histogram else 1, **kwargs)
                elif point:
                    axis.scatter(ys if horizontal else xs, xs if horizontal else ys, s=32, **kwargs)
                    label_key = display.get('point_label')
                    if label_key:
                        for x, y, row in zip(xs, ys, segment):
                            if row.get(label_key) and math.isfinite(y):
                                axis.annotate(str(row[label_key]), (y, x) if horizontal else (x, y),
                                              xytext=(5, 5), textcoords='offset points',
                                              fontfamily=family, fontsize=font_size)
                elif plot_type == 'area':
                    (axis.fill_betweenx if horizontal else axis.fill_between)(xs, ys, alpha=.3, **kwargs)
                else:
                    marker = 'o' if plot_type in ('event_study', 'cohort_event', 'parallel_trends') else None
                    if role == 'reference':
                        marker = '|'
                    linestyle = '--' if component == 'synthetic' or role == 'pre_diagnostic' else '-'
                    if role == 'reference':
                        linestyle = 'None'
                    axis.plot(ys if horizontal else xs, xs if horizontal else ys,
                              marker=marker, markerfacecolor='none' if role == 'pre_diagnostic' else color,
                              linestyle=linestyle,
                              alpha=.35 if component == 'placebo' else 1,
                              drawstyle='steps-post' if plot_type in ('step', 'ecdf') else 'default', **kwargs)
                lower_key, upper_key = display.get('lower'), display.get('upper')
                intervals = []
                if lower_key and upper_key and component != 'region':
                    for x, row in zip(xs, segment):
                        low, high = row.get(lower_key), row.get(upper_key)
                        if low is None or high is None:
                            continue
                        if type(low) not in (int, float) or type(high) not in (int, float) or low > high:
                            raise ValueError('saved interval endpoints must be ordered numeric values or null')
                        intervals.append((x, low, high))
                if intervals:
                    ix, low, high = zip(*intervals)
                    if component == 'band':
                        (axis.fill_betweenx if horizontal else axis.fill_between)(ix, low, high, color=color, alpha=.18)
                    else:
                        (axis.hlines if horizontal else axis.vlines)(ix, low, high, color=color, linewidth=1.3)
                if display.get('x_lower') and display.get('x_upper'):
                    for y, row in zip(ys, segment):
                        low, high = row.get(display['x_lower']), row.get(display['x_upper'])
                        if low is not None and high is not None:
                            if low > high:
                                raise ValueError('saved x interval endpoints must be ordered')
                            (axis.vlines if horizontal else axis.hlines)(y, low, high, color=color, linewidth=1)
    if categorical:
        (axis.set_yticks if horizontal else axis.set_xticks)(range(len(labels)), [str(value) for value in labels])
    axis.set_xlabel(display.get('x_label') or columns.get(ykey if horizontal else xkey, ykey if horizontal else xkey), fontfamily=family)
    axis.set_ylabel(display.get('y_label') or columns.get(xkey if horizontal else ykey, xkey if horizontal else ykey), fontfamily=family)
    if plot_type in ('coefficient', 'event_study', 'cohort_event', 'smd', 'scm_gap', 'scm_placebo'):
        (axis.axvline if horizontal else axis.axhline)(0, color='#73808c', linewidth=.8)
    definitions = [metadata, *metadata.get('result_definitions', {}).values()]
    markers = []
    if plot_type in ('event_study', 'cohort_event'):
        markers += [(definition.get('reference_event_time', definition.get('reference_time')), '--') for definition in definitions]
        markers += [(definition.get('treatment_event_time'), ':') for definition in definitions]
    if plot_type in ('parallel_trends', 'scm', 'scm_gap', 'scm_placebo'):
        markers += [(definition.get('treatment_time'), ':') for definition in definitions]
    if plot_type == 'rdd':
        markers.append((cutoff, '--'))
        bandwidth = metadata.get('bandwidth')
        if type(cutoff) in (int, float) and isinstance(bandwidth, (list, tuple)) and len(bandwidth) == 2:
            (axis.axhspan if horizontal else axis.axvspan)(cutoff - bandwidth[0], cutoff + bandwidth[1], color='#245b8a', alpha=.05)
    for value, style in dict.fromkeys((value, style) for value, style in markers if type(value) in (int, float)):
        (axis.axhline if horizontal else axis.axvline)(value, color='#73808c', linewidth=.8, linestyle=style)
    for reference in metadata.get('reference_lines', []):
        if reference.get('axis') in ('x', 'y') and type(reference.get('value')) in (int, float):
            (axis.axvline if reference['axis'] == 'x' else axis.axhline)(reference['value'], color='#73808c', linestyle=':', linewidth=.8, label=reference.get('label'))
    for name in ('x', 'y'):
        if display.get(name + '_limits') is not None:
            getattr(axis, 'set_' + name + 'lim')(*display[name + '_limits'])
    axis.spines[['top', 'right']].set_visible(False)
    axis.grid(axis='x' if horizontal else 'y', alpha=.18)
    handles, labels = axis.get_legend_handles_labels()
    if display.get('legend', True) and handles:
        unique = dict(zip(labels, handles))
        axis.legend(unique.values(), unique.keys(), loc=display.get('legend_location', 'best'), frameon=False,
                    prop={'family': family, 'size': font_size})


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
    meeting = display.get('preset') == 'meeting' or display.get('style') == 'presentation'
    font_size = display.get('font_size', 14 if meeting else 10)
    plot_type = display.get('plot_type', 'table')
    presentation = gallery_table_presentation(item) if plot_type == 'table' else None
    note_list = presentation['notes'] if presentation else gallery_notes(view)
    width = display.get('width', 960)
    notes = '\n'.join(textwrap.fill(note, max(35, width // 9)) for note in note_list)
    note_lines = len(notes.splitlines())
    height = display.get('height', 540)
    if presentation:
        row_count = len(presentation['headers']) + len(presentation['body']) + len(presentation['footer'])
        height = max(height, int(row_count * font_size * 2.6 + note_lines * 15 + 90))
    figure = Figure(figsize=(width / 100, height / 100), dpi=100)
    FigureCanvasAgg(figure)
    title = display.get('title', item['title'])
    if presentation and presentation['number']:
        title = 'Table ' + presentation['number'] + '. ' + title
    figure.suptitle(title, fontsize=font_size + 4, fontfamily=family, x=.06, ha='left')
    if presentation:
        axis = figure.subplots()
        gallery_plot_table(axis, presentation, family, font_size, width)
    else:
        facet = display.get('facet')
        facets = list(dict.fromkeys(row.get(facet) for row in view['rows'])) if facet else [None]
        facets = facets or [None]
        ncols = min(2, len(facets))
        axes = figure.subplots(math.ceil(len(facets) / ncols), ncols, squeeze=False).flat
        columns = {col['key']: col['label'] + (' (' + col['unit'] + ')' if col['unit'] else '') for col in view['columns']}
        for index, axis in enumerate(axes):
            if index >= len(facets):
                axis.set_visible(False)
                continue
            selected = [row for row in view['rows'] if not facet or row.get(facet) == facets[index]]
            metadata = view['metadata']
            result_ids = {row['result_id'] for row in selected}
            if len(result_ids) == 1:
                metadata = {**metadata, **metadata.get('result_definitions', {}).get(next(iter(result_ids)), {})}
            panel_columns = dict(columns)
            ykey = display.get('y')
            units = {row['unit'] for row in selected if row.get('unit') and row.get(ykey) is not None}
            if len(units) == 1 and not next((column['unit'] for column in view['columns'] if column['key'] == ykey), ''):
                panel_columns[ykey] = panel_columns.get(ykey, ykey) + ' (' + str(next(iter(units))) + ')'
            gallery_plot_panel(axis, selected, display, metadata, panel_columns, family, font_size)
            if not display.get('y_label'):
                axis.set_ylabel(textwrap.fill(axis.get_ylabel(), 24, break_long_words=False, break_on_hyphens=False))
            if facet:
                axis.set_title(str(facets[index]), fontfamily=family, fontsize=font_size + 1)
    # Color bars create additional axes; apply the same scientific-label font.
    for axis in figure.axes:
        axis.tick_params(labelsize=font_size)
        for label in [*axis.get_xticklabels(), *axis.get_yticklabels(), axis.xaxis.label, axis.yaxis.label]:
            label.set_fontfamily(family)
    bottom = min(.5, (note_lines * 15 + 20) / height) if notes else .03
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
        presentation = gallery_table_presentation(item)
        title = ('Table ' + presentation['number'] + '. ' if presentation['number'] else '') + presentation['caption']
        title = html.escape(title)
        notes = ''.join('<p>' + html.escape(note) + '</p>' for note in presentation['notes'])
        body = '<h3>' + title + '</h3>' + body + notes
    return ('<section class="research-display"><style>.research-display{font-family:system-ui,sans-serif;color:#213547;overflow-x:auto;}'
            '.research-display svg{max-width:100%;height:auto;}'
            '.research-display p{font-size:13px;color:#425466;}</style>'
            + body + '</section>')


def gallery_latex(item):
    escapes = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}
    def escape(value):
        return ''.join(escapes.get(char, char) for char in str(value)).replace('\n', ' ')
    is_table = item.get('display', {}).get('plot_type', 'table') == 'table'
    display = item.get('display', {})
    presentation = gallery_table_presentation(item) if is_table else None
    lines = [r'\begingroup', r'\begin{table}[htbp]' if is_table else r'\begin{figure}[htbp]', r'\centering']
    if presentation and presentation['number']:
        lines.append(r'\renewcommand{\thetable}{' + escape(presentation['number']) + '}')
    lines.append(r'\caption{' + escape(presentation['caption'] if presentation else display.get('title', item['title'])) + '}')
    label = display.get('latex_label') or ('tab:' if is_table else 'fig:') + item['id']
    if not re.fullmatch(r'[A-Za-z0-9:_.-]+', label):
        raise ValueError('latex_label must contain letters, digits, colon, underscore, dot or hyphen')
    lines.append(r'\label{' + label + '}')
    if is_table:
        count = sum(cell['colspan'] for cell in presentation['headers'][-1])
        lines += [r'\begin{tabular}{l' + 'c' * (count - 1) + '}', r'\toprule']
        for header in presentation['headers']:
            lines.append(' & '.join(r'\multicolumn{' + str(cell['colspan']) + '}{c}{' + escape(cell['text']) + '}'
                                    if cell['colspan'] > 1 else escape(cell['text']) for cell in header) + r' \\')
        lines.append(r'\midrule')
        for row in presentation['body']:
            if row.get('kind') == 'panel':
                lines += [r'\addlinespace', r'\multicolumn{' + str(count) + r'}{l}{\textit{' + escape(row['label']) + r'}} \\']
            else:
                lines.append(' & '.join(escape(value) for value in [row['label'], *row['cells']]) + r' \\')
        if presentation['footer']:
            lines.append(r'\midrule')
            lines += [' & '.join(escape(value) for value in [row['label'], *row['cells']]) + r' \\' for row in presentation['footer']]
        lines += [r'\bottomrule', r'\end{tabular}']
    else:
        lines.append(r'\includegraphics[width=\linewidth]{display.pdf}')
    notes = presentation['notes'] if presentation else gallery_notes(item)
    if notes:
        lines += [r'\par\medskip\begin{minipage}{\linewidth}\footnotesize',
                  r'\par '.join(escape(note) for note in notes), r'\end{minipage}']
    lines += [r'\end{table}' if is_table else r'\end{figure}', r'\endgroup']
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
            '$for(header-includes)$\n$header-includes$\n$endfor$\n')
    if kind=='paper':
        common += '\\AtBeginEnvironment{longtable}{\\def\\_{\\textunderscore\\allowbreak}}\n'
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
        # Pandoc's common preamble selects Babel's locale through the class option.
        source=replace_once(source,'\\documentclass[unicode, mathserif, m, 12pt, unknownkeysallowed]{beamer}', '\\documentclass[unicode, mathserif, m, $if(fontsize)$$fontsize$$else$12pt$endif$, unknownkeysallowed$if(babel-lang)$,$babel-lang$$endif$$if(aspectratio)$,aspectratio=$aspectratio$$endif$]{beamer}')
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
    if not isinstance(spec,dict) or set(spec)-{'pipeline','sources','bindings','definitions','article_template','slides_template','figure','models'} or not {'pipeline','sources','bindings','article_template','slides_template','figure'}<=set(spec): raise ValueError('artifact specification has invalid fields')
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
    definitions=spec.get('definitions',{})
    if not isinstance(definitions,dict): raise ValueError('definitions must be an object')
    for name,b in definitions.items():
        if (not isinstance(name,str) or not NAME.fullmatch(name) or not isinstance(b,dict)
                or set(b)!={'key'} or not isinstance(b['key'],list) or not b['key']
                or any(not isinstance(key,str) or not key for key in b['key'])):
            raise ValueError('definition requires a named nonempty JSON key path')
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
        names_definitions={m.group(3) for m in TOKEN.finditer(text) if m.group(3)}
        if names_definitions-set(definitions): raise ValueError('template has an unknown definition binding')
        rest=TOKEN.sub('',text)
        if any(token in rest for token in ('{{stat:', '{{definition:', '{{table', '{{figure')): raise ValueError('malformed artifact placeholder')
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
        for ref_name, hash_names in {'specification':('spec_sha256','specification_sha256'),'data':('data_sha256',),'code':('script_sha256','code_sha256','producer_sha256')}.items():
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
            if value is None: continue
            sname='coefficient.'+key
            unit=quantities.get(sname,{}).get('statistic',{}).get('unit',units.get(key))
            if unit is None: raise ValueError(f'{name}: coefficient unit required for {key}')
            add(sname,value,unit,['coefficients',key])
        for key,value in ses.items():
            if value is None: continue
            sname='standard_error.'+key
            unit=quantities.get(sname,{}).get('statistic',{}).get('unit',
                quantities.get('coefficient.'+key,{}).get('statistic',{}).get('unit',units.get(key)))
            if unit is None: raise ValueError(f'{name}: standard error unit required for {key}')
            add(sname,value,unit,['standard_errors',key])
        inference=result.get('inference',{}) or {}
        if isinstance(inference,dict):
            pvalues=inference.get('p_values',{})
            if not pvalues and 'pvalue' in inference and len(coef)==1: pvalues={next(iter(coef)):inference['pvalue']}
            if isinstance(pvalues,dict):
                for k,v in pvalues.items():
                    if v is not None: add('p_value.'+k,v,'probability',['inference','p_values',k] if 'p_values' in inference else ['inference','pvalue'])
            for field in ('confidence_intervals', 'confidence_interval', 'confidence_intervals_95', 'confidence_interval_95'):
                intervals=inference.get(field)
                if intervals is None: continue
                singular=field in ('confidence_interval', 'confidence_interval_95')
                if singular and len(coef)==1: intervals={next(iter(coef)):intervals}
                if not isinstance(intervals,dict): raise ValueError(field+' must map named terms to saved endpoints')
                prefix='confidence_95_' if field.endswith('_95') else 'confidence_'
                for k,ends in intervals.items():
                    if not isinstance(ends,list) or len(ends)!=2: raise ValueError('confidence interval must have two endpoints')
                    unit=quantities.get('coefficient.'+k,{}).get('statistic',{}).get('unit',units.get(k))
                    for index,(which,v) in enumerate(zip(('lower','upper'),ends)):
                        if v is None: continue
                        origin=['inference',field]+([] if singular else [k])+[index]
                        add(prefix+which+'.'+k,v,unit,origin)
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
        append(raw[cursor:m.start()]); alias=m.group(1); special=m.group(2); definition=m.group(3)
        if alias:
            b=spec['bindings'][alias]; item=registry['statistics'][b['key']]; value=format(item['value'],b['format']); start=length; append(value); stop=length; append(' '); ustart=length; append(b['display_unit']); uend=length
            captures.append({'id':alias+'-'+str(len(captures)+1),'alias':alias,'target':{'start':start,'end':stop,'quote':value},'unit_target':{'start':ustart,'end':uend,'quote':b['display_unit']}})
        elif definition:
            value=evidence.lookup(registry,spec['definitions'][definition]['key'],'definition '+definition)
            if not isinstance(value,str) or not value.strip(): raise ValueError('definition must select saved nonempty text: '+definition)
            append(value)
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
        elif args.command == 'compare':
            result = gallery_compare(root, path, args.item_ids)
        elif args.command == 'select':
            result = gallery_items(root, path, item_ids=args.item_ids)
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
