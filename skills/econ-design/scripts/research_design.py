#!/usr/bin/env python3
"""Select research methods and evaluate adopted comparisons, sources and variables."""
import argparse
from copy import deepcopy
import importlib.util
import inspect
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import sys
import tempfile

for parent in Path(__file__).resolve().parents:
    if (parent / 'harness' / 'paragraph.py').is_file():
        sys.path.insert(0, str(parent / 'harness'))
        sys.path.insert(0, str(parent / 'skills/econ-literature/scripts'))
        sys.path.insert(0, str(parent / 'skills/econ-data/scripts'))
        break

FLAT_EXPORT = (Path(__file__).resolve().parent / 'RESOURCES.json').is_file()
ROOT = Path(__file__).resolve().parent if FLAT_EXPORT else Path(__file__).resolve().parents[3]

DIMENSIONS = ('mechanism', 'estimand', 'identifying_variation', 'measurement', 'population')
DESIGN_FIELDS = ('question', 'population', 'observation_unit', 'economic_model', 'mechanism', 'estimand', 'identification')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def file_bytes(root, name, digest):
    path = Path(name)
    path = path if path.is_absolute() else root / path
    raw = path.read_bytes()
    require(isinstance(digest, str) and hashlib.sha256(raw).hexdigest() == digest, 'File hash differs: ' + str(path))
    return raw


def load_sources(root, entries):
    import paragraph
    require(isinstance(entries, dict) and entries, 'Source texts are required')
    sources = {}
    for name, row in entries.items():
        require(isinstance(row, dict) and {'path', 'sha256'} <= row.keys(), 'Source path and hash required')
        raw = file_bytes(root, row['path'], row['sha256'])
        sources[name] = {'text': raw.decode('utf-8'), 'sha256': row['sha256'], 'path': row['path']}
    return paragraph.normalize_sources(sources)


def literature_input(contract, root, sources):
    """Resolve the selected paper knowledge through its existing source owner."""
    reference = contract.get('corpus')
    if reference is None:
        return sources, None
    import research_search
    require(isinstance(reference, dict) and {'path', 'sha256', 'proposition_ids'} <= reference.keys()
            and set(reference) <= {'path', 'sha256', 'proposition_ids', 'as_of'},
            'Corpus reference requires path, sha256 and selected proposition_ids; as_of is optional')
    path = Path(reference['path'])
    selected = research_search.load_corpus_record(path if path.is_absolute() else root / path,
        reference['sha256'], proposition_ids=reference['proposition_ids'], as_of=reference.get('as_of'))
    sources = dict(sources or {})
    for key, source in selected['design_sources'].items():
        require(key not in sources or sources[key] == source, 'Conflicting selected source identity: ' + key)
        sources[key] = source
    return sources, selected


def evidence(refs, sources, label):
    import paragraph
    require(isinstance(refs, list) and refs, label + ' requires source evidence')
    for ref in refs:
        require(isinstance(ref, dict) and ref.get('source_id') in sources, label + ' has unknown source')
        paragraph._span(ref, sources[ref['source_id']]['text'], label)
    return refs


def dimensions(row, label):
    require(isinstance(row, dict) and all(isinstance(row.get(k), str) and row[k].strip() for k in DIMENSIONS),
            label + ' requires all five economic dimensions')


def variable_design(spec):
    """Check adopted economic roles against the existing estimators' column inputs."""
    require(isinstance(spec, dict), 'Variable design requires an assembly specification')
    for key in DESIGN_FIELDS:
        value = spec.get(key)
        require((isinstance(value, str) and value.strip()) or (isinstance(value, dict) and value),
                'Variable design requires ' + key)
    definitions = spec.get('definitions')
    require(isinstance(definitions, dict) and definitions, 'Variable definitions are required')
    roles, causes = {}, {}
    role_names = {'outcome', 'primary_outcome', 'secondary_outcome', 'treatment', 'assignment',
                  'receipt', 'endogenous', 'control', 'covariate', 'instrument', 'fixed_effect',
                  'time_effect', 'trend', 'effect_modifier', 'mediator', 'collider', 'posttreatment',
                  'id', 'time', 'cohort', 'running', 'weight', 'cluster', 'exposure', 'auxiliary'}
    causal_names = {'confounder', 'baseline_outcome', 'baseline_attribute', 'pretreatment_time_varying',
                    'mediator', 'collider', 'posttreatment', 'instrument', 'fixed_effect',
                    'time_effect', 'trend', 'effect_modifier', 'assignment', 'receipt', 'exposure'}
    for name, definition in definitions.items():
        require(isinstance(name, str) and name and isinstance(definition, dict), 'Invalid variable definition')
        require(all(isinstance(definition.get(k), str) and definition[k].strip()
                    for k in ('unit', 'definition', 'version')), 'Define unit, definition and version: ' + name)
        for key, allowed, target in (('role', role_names, roles), ('causal_role', causal_names, causes)):
            labels = definition.get(key, [])
            labels = [labels] if isinstance(labels, str) else labels
            require(isinstance(labels, list) and all(isinstance(x, str) and x in allowed for x in labels)
                    and len(labels) == len(set(labels)), 'Invalid ' + key + ': ' + name)
            target[name] = set(labels)
        for key in ('source_fields', 'inputs'):
            if key in definition:
                values = definition[key]
                require(isinstance(values, list) and all(isinstance(x, str) and x for x in values),
                        key + ' must list field names: ' + name)
        if 'rationale' in definition:
            require(isinstance(definition['rationale'], str) and definition['rationale'].strip(),
                    'Variable rationale must be text: ' + name)
        for key in ('measurement', 'timing'):
            if key in definition:
                require(isinstance(definition[key], (str, dict)) and definition[key],
                        key + ' must be text or an object: ' + name)
    identification = spec['identification'] if isinstance(spec['identification'], dict) else {}
    adjustment = identification.get('adjustment_set')
    if adjustment is not None:
        require(isinstance(adjustment, list) and all(isinstance(x, str) and x in definitions for x in adjustment)
                and len(adjustment) == len(set(adjustment)), 'adjustment_set must name distinct defined variables')
    analyses = spec.get('analyses', [])
    require(isinstance(analyses, list), 'analyses must be a list')
    checked, ids = [], set()
    allowed_roles = {
        'outcome': {'outcome', 'primary_outcome', 'secondary_outcome'},
        'outcome_pre': {'outcome', 'primary_outcome', 'secondary_outcome', 'control', 'covariate'},
        'treatment': {'treatment', 'assignment', 'receipt', 'exposure'},
        'endogenous': {'endogenous', 'treatment', 'receipt', 'exposure'},
        'instrument': {'instrument'}, 'id': {'id'}, 'time': {'time', 'time_effect'},
        'cohort': {'cohort'}, 'running': {'running'}, 'weight': {'weight'},
        'cluster': {'cluster', 'id', 'fixed_effect', 'time'},
        'fixed_effect': {'fixed_effect', 'time_effect', 'id', 'time'},
        'control': {'control', 'covariate', 'effect_modifier', 'fixed_effect', 'time_effect', 'trend'},
        'regressor': {'control', 'covariate', 'effect_modifier', 'treatment', 'assignment', 'receipt',
                      'exposure', 'fixed_effect', 'time_effect', 'trend', 'mediator', 'collider', 'posttreatment'},
    }
    for analysis in analyses:
        require(isinstance(analysis, dict) and {'id', 'runner', 'specification'} <= set(analysis)
                <= {'id', 'runner', 'specification', 'sample'},
                'Each analysis requires id, runner, specification and an optional sample')
        name, runner, model = analysis['id'], analysis['runner'], analysis['specification']
        require(isinstance(name, str) and name and name not in ids, 'Analysis IDs must be distinct')
        ids.add(name)
        require(runner in ('research', 'causal') and isinstance(model, dict), 'Invalid analysis runner or specification')
        require('data' not in model and 'data_record' not in model, 'Assembly owns analysis data: ' + name)
        require(isinstance(model.get('method'), str) and model['method'], 'Analysis method is required: ' + name)
        fields, adjustments = {}, set()

        def bind(path, value, expected):
            columns = [value] if isinstance(value, str) else value
            require(isinstance(columns, list) and all(isinstance(x, str) and x in definitions for x in columns)
                    and len(columns) == len(set(columns)), name + ': undefined or repeated columns in ' + path)
            fields[path] = columns
            for column in columns:
                role, cause, definition = roles[column], causes[column], definitions[column]
                require(bool(definition.get('source_fields') or definition.get('inputs')),
                        name + ': bound variable requires source_fields or inputs: ' + column)
                if expected in allowed_roles:
                    require(bool(role & allowed_roles[expected]), name + ': ' + column + ' role does not match ' + path)
                if expected == 'instrument':
                    require(not cause or cause <= {'instrument', 'assignment'},
                            name + ': instrument has an incompatible causal role: ' + column)
                timing = definition.get('timing')
                relation = timing.get('relative_to_treatment') if isinstance(timing, dict) else timing
                if expected in {'outcome', 'outcome_pre', 'treatment', 'endogenous', 'instrument',
                                'regressor', 'control', 'fixed_effect', 'cohort', 'running'}:
                    require(bool(timing) and bool(definition.get('rationale')),
                            name + ': economic variable requires timing and rationale: ' + column)
                if expected == 'outcome_pre':
                    require(relation in ('pretreatment', 'baseline'), name + ': outcome_pre requires pretreatment timing')
                is_control = expected == 'control' or (expected == 'regressor' and bool(role &
                    {'control', 'covariate', 'effect_modifier', 'mediator', 'collider', 'posttreatment'}))
                if is_control:
                    adjustments.add(column)
                    require(bool(cause) and bool(definition.get('rationale')),
                            name + ': adjustment requires causal_role and rationale: ' + column)
                    require(not (cause & {'instrument'}), name + ': excluded instrument used as adjustment: ' + column)
                    effects_only = cause <= {'fixed_effect', 'time_effect', 'trend'}
                    if cause & {'mediator', 'collider', 'posttreatment'} or (relation == 'posttreatment' and not effects_only):
                        require(adjustment is not None and column in adjustment
                                and isinstance(identification.get('adjustment_rationale'), str)
                                and identification['adjustment_rationale'].strip(),
                                name + ': conditioned pathway requires adopted adjustment_set and adjustment_rationale: ' + column)
                    else:
                        require(cause <= {'confounder', 'baseline_outcome', 'baseline_attribute',
                            'pretreatment_time_varying', 'effect_modifier', 'fixed_effect', 'time_effect', 'trend'},
                            name + ': incompatible adjustment role: ' + column)
                        if not effects_only:
                            require(relation in ('pretreatment', 'baseline', 'time_invariant'),
                                    name + ': adjustment requires pretreatment measurement timing: ' + column)

        for key, expected in {'id': 'id', 'outcome': 'outcome', 'outcome_pre': 'outcome_pre',
                'outcome_post': 'outcome', 'treatment': 'treatment', 'exog': 'regressor',
                'regressors': 'regressor', 'covariates': 'control', 'endog': 'endogenous',
                'endogenous': 'endogenous', 'instruments': 'instrument', 'sample_columns': 'sample'}.items():
            if key in model:
                bind(key, model[key], expected)
        options = model.get('options', {})
        require(isinstance(options, dict), 'Analysis options must be an object: ' + name)
        for key, expected in {'treatment': 'treatment', 'treatments': 'treatment', 'outcome_pre': 'outcome_pre',
                'entity': 'id', 'time': 'time', 'cohort': 'cohort', 'running': 'running',
                'fixed_effects': 'fixed_effect', 'clustervars': 'cluster', 'cluster_var': 'cluster',
                'weightsname': 'weight', 'event_variable': 'auxiliary', 'status': 'auxiliary',
                'entry': 'auxiliary', 'strata': 'auxiliary', 'offset': 'auxiliary', 'group': 'auxiliary'}.items():
            if key in options:
                bind('options.' + key, options[key], expected)
        # Only these implemented methods interpret options.weights as a data column.
        if model['method'] in ('hdfe', 'dml_irm', 'dml_apo') and isinstance(options.get('weights'), str):
            bind('options.weights', options['weights'], 'weight')
        native_columns = options.get('columns', {})
        require(isinstance(native_columns, dict), 'options.columns must be an object: ' + name)
        for key, value in native_columns.items():
            bind('options.columns.' + key, value, 'auxiliary')
        for section in ('covariance', 'inference'):
            require(isinstance(model.get(section, {}), dict), section + ' must be an object: ' + name)
            for key in ('cluster', 'clusters'):
                if key in model.get(section, {}):
                    bind(section + '.' + key, model[section][key], 'cluster')
        if adjustment is not None:
            require(adjustments == set(adjustment), name + ': estimator adjustment columns differ from adjustment_set')
        if model['method'] == 'rct':
            assigned = options.get('treatment')
            require(assigned in definitions and 'assignment' in roles[assigned],
                    name + ': rct treatment must declare randomized assignment')
        checked.append({'id': name, 'runner': runner, 'method': model['method'], 'fields': fields})
    result = {key: spec[key] for key in DESIGN_FIELDS}
    result['analyses'] = checked
    if 'dag' in identification:
        result['dag_adjustment'] = _dag_adjustment(identification, definitions)
        treatment = identification['dag']['treatment']
        outcome = identification['dag']['outcome']
        for analysis in checked:
            fields = analysis['fields']
            actual_outcomes = {column for key in ('outcome', 'outcome_post') for column in fields.get(key, [])}
            actual_treatments = {column for key, columns in fields.items() for column in columns
                if key in ('treatment', 'endog', 'endogenous', 'options.treatment', 'options.treatments')
                or (key in ('exog', 'regressors', 'options.cohort') and
                    roles[column] & {'treatment', 'assignment', 'receipt', 'exposure'})}
            require(treatment in actual_treatments and outcome in actual_outcomes,
                    analysis['id'] + ': DAG endpoints differ from actual analysis treatment and outcome')
    return result


def _dag_adjustment(identification, definitions):
    """Check the supplied back-door set in the adopted directed acyclic graph."""
    dag, adjustment = identification['dag'], identification.get('adjustment_set')
    require(isinstance(dag, dict) and set(dag) == {'edges', 'treatment', 'outcome'}
            and isinstance(adjustment, list), 'DAG requires edges, treatment, outcome and an adopted adjustment_set')
    require(isinstance(identification.get('assumptions'), list) and identification['assumptions']
            and all(isinstance(x, str) and x.strip() for x in identification['assumptions']),
            'DAG identification requires its adopted causal assumptions')
    treatment, outcome = dag['treatment'], dag['outcome']
    require(isinstance(treatment, str) and isinstance(outcome, str)
            and treatment in definitions and outcome in definitions and treatment != outcome,
            'DAG endpoints must name distinct defined treatment and outcome columns')
    edges = dag['edges']
    require(isinstance(edges, list) and all(isinstance(edge, list) and len(edge) == 2
            and all(isinstance(x, str) and x for x in edge) and edge[0] != edge[1] for edge in edges),
            'DAG edges must be directed pairs of distinct node names')
    nodes = {treatment, outcome, *adjustment, *(x for edge in edges for x in edge)}
    parents, children = {x: set() for x in nodes}, {x: set() for x in nodes}
    for source, target in edges:
        parents[target].add(source)
        children[source].add(target)
    pending, removed = {x for x in nodes if not parents[x]}, set()
    while pending:
        node = pending.pop()
        removed.add(node)
        pending.update(x for x in children[node] if parents[x] <= removed)
    require(removed == nodes, 'Adopted causal graph contains a directed cycle')
    descendants, pending = set(), set(children[treatment])
    while pending:
        node = pending.pop()
        descendants.add(node)
        pending.update(children[node] - descendants)
    require(not set(adjustment) & (descendants | {treatment, outcome}),
            'Back-door adjustment contains an endpoint or treatment descendant')
    # Moralize the ancestral graph after deleting treatment's outgoing arrows.
    back_parents = {x: values - {treatment} for x, values in parents.items()}
    ancestors, pending = set(), {treatment, outcome, *adjustment}
    while pending:
        node = pending.pop()
        ancestors.add(node)
        pending.update(back_parents[node] - ancestors)
    neighbors = {x: set() for x in ancestors}
    for node in ancestors:
        family = {node} | (back_parents[node] & ancestors)
        for member in family:
            neighbors[member].update(family - {member})
    reached, pending = set(), {treatment}
    while pending:
        node = pending.pop()
        reached.add(node)
        pending.update(neighbors[node] - reached - set(adjustment))
    require(outcome not in reached, 'Adopted adjustment_set leaves an open back-door path')
    return {'criterion': 'backdoor', 'treatment': treatment, 'outcome': outcome,
            'adjustment_set': adjustment, 'assumptions': identification['assumptions']}


def dataset(root, name, spec, sources):
    require(isinstance(spec, dict) and all(k in spec for k in ('path', 'sha256', 'unit', 'population', 'period', 'documentation', 'grain', 'definition_versions')),
            'Dataset requires path, hash, unit, population, period, documentation, grain and definition versions: ' + name)
    require(all(isinstance(spec[k], str) and spec[k].strip() for k in ('unit', 'population')), 'Dataset unit and population required')
    require(isinstance(spec['period'], dict) and type(spec['period'].get('start')) is int and type(spec['period'].get('end')) is int and spec['period']['start'] <= spec['period']['end'], 'Invalid documented period')
    require(isinstance(spec['definition_versions'], dict) and spec['definition_versions'] and all(isinstance(k, str) and k and isinstance(v, str) and v for k, v in spec['definition_versions'].items()), 'Dataset definition versions required')
    evidence(spec['documentation'], sources, 'Dataset documentation')
    import research_data
    path = Path(spec['path'])
    path = path if path.is_absolute() else root / path
    with path.open('rb') as stream:
        actual_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
    require(actual_hash == spec['sha256'], 'File hash differs: ' + str(path))
    frame = research_data.read_frame(path, string_columns=True)
    fields = frame.columns.tolist()
    rows = frame.astype('string').where(frame.notna(), None).to_dict(orient='records')
    return {'id': name, 'path': spec['path'], 'sha256': spec['sha256'], 'definition_versions': spec['definition_versions'],
            'unit': spec['unit'], 'population': spec['population'], 'period': spec['period'],
            'documentation': spec['documentation'], 'grain': spec['grain'], 'fields': fields, 'rows': rows,
            'missing_tokens': spec.get('missing_tokens', ['', 'NA', 'NaN'])}


def fit(data, req, datasets):
    require(isinstance(req, dict), 'Dataset requirements must be an object')
    required = req.get('required_fields', [])
    grain = data['grain']
    require(isinstance(grain, list) and grain and all(isinstance(x, str) and x for x in grain) and len(set(grain)) == len(grain), 'Dataset grain must name unique fields')
    require(isinstance(required, list) and all(isinstance(x, str) and x for x in required), 'Invalid required fields')
    fields = set(data['fields'])
    missing_fields = sorted((set(required) | set(grain)) - fields)
    reasons = []
    if missing_fields:
        reasons.append('missing_fields')
    for key in ('unit', 'population'):
        require(isinstance(req.get(key), str) and req[key].strip(), 'Required ' + key + ' missing')
        if data[key] != req[key]:
            reasons.append(key + '_mismatch')
    period = req.get('period')
    require(isinstance(period, dict) and type(period.get('start')) is int and type(period.get('end')) is int and period['start'] <= period['end'], 'Required period invalid')
    if data['period']['start'] > period['start'] or data['period']['end'] < period['end']:
        reasons.append('documented_period_mismatch')
    all_rows, missing = data['rows'], set(data['missing_tokens'])
    sample = req.get('sample', {})
    require(isinstance(sample, dict) and all(isinstance(k, str) and isinstance(v, list) and v for k, v in sample.items()), 'Sample filters must map fields to accepted values')
    if set(sample) - fields:
        reasons.append('sample_fields')
    rows = [row for row in all_rows if all(row.get(k) in values for k, values in sample.items())]
    if not rows:
        reasons.append('empty_dataset')
    missing_counts = {k: sum(row.get(k) in missing or row.get(k) is None for row in rows) for k in sorted(fields)}
    duplicate_count = missing_key_count = 0
    if set(grain) <= fields:
        seen = set()
        for row in rows:
            key = tuple(row.get(k) for k in grain)
            if any(v is None or v in missing for v in key):
                missing_key_count += 1
            elif key in seen:
                duplicate_count += 1
            else:
                seen.add(key)
        if duplicate_count or missing_key_count:
            reasons.append('invalid_grain')
    maxima = req.get('max_missing_fraction', {})
    require(isinstance(maxima, dict), 'Missingness limits must be an object')
    for col, maximum in maxima.items():
        require(type(maximum) in (int, float) and 0 <= maximum <= 1, 'Invalid missingness threshold')
        if col not in fields or not rows or missing_counts[col] / len(rows) > maximum:
            reasons.append('missingness:' + col)
    variations = {}
    for col, definition in req.get('variation', {}).items():
        minimum = definition.get('minimum_distinct') if isinstance(definition, dict) else definition
        kind = definition.get('type', 'categorical') if isinstance(definition, dict) else 'categorical'
        require(type(minimum) is int and minimum >= 2, 'Variation requires at least two distinct values')
        require(kind in ('numeric', 'categorical'), 'Variation type must be numeric or categorical')
        values = sorted({row.get(col) for row in rows if row.get(col) is not None and row.get(col) not in missing}) if col in fields else []
        invalid = []
        if kind == 'numeric':
            numbers = set()
            for value in values:
                try:
                    number = Decimal(value)
                    if not number.is_finite():
                        invalid.append(value)
                    else:
                        numbers.add(number)
                except InvalidOperation:
                    invalid.append(value)
            values = [str(number) for number in sorted(numbers)]
        variations[col] = {'type': kind, 'distinct_values': values, 'count': len(values), 'required': minimum, 'invalid_values': invalid}
        if invalid:
            reasons.append('invalid_variation:' + col)
        if len(values) < minimum:
            reasons.append('variation:' + col)
    coverage = None
    if req.get('year_field'):
        col = req['year_field']
        invalid, years = 0, set()
        for row in rows:
            val = row.get(col)
            if val is None or val in missing or not val.isdigit():
                invalid += 1
            else:
                years.add(int(val))
        missing_years = sorted(set(range(period['start'], period['end'] + 1)) - years)
        coverage = {'field': col, 'observed_years': sorted(years), 'missing_years': missing_years, 'invalid_rows': invalid}
        if missing_years or invalid:
            reasons.append('observed_period_coverage')
    status = None
    if req.get('status_field'):
        col, accepted = req['status_field'], req.get('accepted_statuses')
        require(isinstance(accepted, list) and accepted, 'Accepted statuses required')
        counts = {}
        for row in rows:
            value = row.get(col)
            counts[str(value)] = counts.get(str(value), 0) + 1
        status = {'field': col, 'counts': counts, 'accepted': accepted}
        if col not in fields or any(row.get(col) not in accepted for row in rows):
            reasons.append('observation_status')
    links = []
    for link in req.get('links', []):
        target = datasets.get(link.get('dataset'))
        require(target is not None, 'Unknown linked dataset')
        left, right = link.get('left_fields'), link.get('right_fields')
        minimum = link.get('min_match_fraction')
        require(isinstance(left, list) and isinstance(right, list) and left and len(left) == len(right) and type(minimum) in (int, float) and 0 <= minimum <= 1, 'Invalid linkage contract')
        if not set(left) <= fields or not set(right) <= set(target['fields']):
            reasons.append('link_fields')
            links.append({'dataset': target['id'], 'valid_fields': False})
            continue
        target_missing = set(target['missing_tokens'])
        right_keys = [tuple(row[k] for k in right) for row in target['rows'] if all(row[k] is not None and row[k] not in target_missing for k in right)]
        right_set = set(right_keys)
        matched = sum(all(row[k] is not None and row[k] not in missing for k in left) and tuple(row[k] for k in left) in right_set for row in rows)
        unique = len(right_keys) == len(right_set)
        fraction = matched / len(rows) if rows else 0
        links.append({'dataset': target['id'], 'target_sha256': target['sha256'], 'matched': matched, 'rows': len(rows), 'match_fraction': fraction, 'right_unique': unique})
        if fraction < minimum or (link.get('right_unique', True) and not unique):
            reasons.append('linkage:' + target['id'])
    return {'feasible': not reasons, 'reasons': reasons, 'rows': len(rows), 'input_rows': len(all_rows), 'sample': sample, 'fields': data['fields'],
            'missing_fields': missing_fields, 'grain': grain, 'duplicate_keys': duplicate_count, 'missing_keys': missing_key_count,
            'missing_counts': missing_counts, 'variation': variations, 'coverage': coverage, 'status': status, 'links': links}


def formulation_record(item, sources, adopted=None):
    """Bind the lead's additional comparison to this candidate and source versions."""
    judgment = item['judgment']
    value = judgment.get('formulation')
    source_versions = {key: row['sha256'] for key, row in sources.items()}
    if value is None and adopted:
        previous = next((row for row in adopted.get('candidates', []) if row['id'] == item['id']), {})
        saved = previous.get('formulation')
        if (saved and saved['selected_dimensions'] == item['dimensions'] and
                saved['source_versions'] == source_versions):
            return {**saved, 'reused': True}
        if (not saved and adopted.get('selected_candidate') == item['id'] and not adopted.get('adoption_required')
                and previous.get('dimensions') == item['dimensions'] and
                {key: row['sha256'] for key, row in adopted.get('sources', {}).items()} == source_versions):
            return {'status': 'adopted_specification_reused', 'owner': judgment['owner'],
                    'selected_dimensions': deepcopy(item['dimensions']), 'source_versions': source_versions,
                    'reused': True}
    if value is None:
        return None
    require(isinstance(value, dict) and set(value) == {'initial', 'alternative', 'comparison', 'selected', 'rationale'},
            'Formulation requires initial, alternative, comparison, selected and rationale')
    for key in ('initial', 'alternative'):
        row = value[key]
        require(isinstance(row, dict) and set(row) == {'question', 'dimensions'} and
                isinstance(row['question'], str) and row['question'].strip(), 'Formulation needs each actual question')
        dimensions(row['dimensions'], 'Formulation '+key)
    require(value['initial']['question'] != value['alternative']['question'],
            'The additional reconsideration must name its consequential alternative question')
    require(value['selected'] in ('initial', 'alternative') and
            all(isinstance(value[key], str) and value[key].strip() for key in ('comparison', 'rationale')),
            'Formulation requires the lead comparison and adopted disposition')
    chosen = value[value['selected']]
    require(chosen['dimensions'] == item['dimensions'], 'Selected formulation must match the actual candidate dimensions')
    return {**deepcopy(value), 'owner': judgment['owner'], 'selected_question': chosen['question'],
            'selected_dimensions': deepcopy(item['dimensions']), 'source_versions': source_versions, 'reused': False}


def formulate_problem(contract, root):
    """Bind one additional formulation comparison to an existing research specification."""
    require(isinstance(contract, dict), 'Formulation contract must be an object')
    ref = contract.get('specification')
    require(isinstance(ref, dict) and set(ref) == {'path','sha256'}, 'Formulation needs the existing specification path and hash')
    specification = json.loads(file_bytes(root, ref['path'], ref['sha256']))
    judgment = contract.get('judgment', {})
    require(isinstance(specification, dict), 'Research specification must be an object')
    require(isinstance(judgment, dict) and isinstance(judgment.get('owner'), str) and judgment['owner'].strip(), 'Formulation needs its lead owner')
    value = judgment.get('formulation', {})
    require(isinstance(value, dict) and value.get('selected') in ('initial','alternative'), 'Formulation needs its adopted disposition')
    chosen = value[value['selected']]
    require(chosen['question'] == specification.get('question'), 'Formulation must resolve the actual specification question')
    for dimension, field in [('estimand','estimand'),('population','population'),('identifying_variation','identification'),('mechanism','mechanism')]:
        if isinstance(specification.get(field), str):
            require(chosen['dimensions'][dimension] == specification[field], 'Formulation differs from adopted '+field)
    item = {'dimensions':chosen['dimensions'], 'judgment':judgment}
    record = formulation_record(item, {'specification':dict(ref)})
    return {'status':'formulated', 'sources':{'specification':dict(ref)}, 'formulation':record,
            'definition':{k:specification[k] for k in DESIGN_FIELDS if k in specification},
            'scientific_specification_changed':False, 'executed':False}


def interpret_result(contract, root):
    """Save an economic judgment bound to the adopted specification and actual saved quantities."""
    require(isinstance(contract, dict), 'Interpretation contract must be an object')
    import research_evidence
    sources, documents = {}, {}
    for key in ('specification', 'result'):
        ref = contract.get(key)
        require(isinstance(ref, dict) and set(ref) == {'path', 'sha256'}, key+' needs its exact path and hash')
        raw = file_bytes(root, ref['path'], ref['sha256'])
        documents[key] = research_evidence.read_json(raw, ref['path'])
        sources[key] = dict(ref)
    judgment = contract.get('judgment')
    require(isinstance(judgment, dict) and all(isinstance(judgment.get(k), str) and judgment[k].strip()
            for k in ('owner', 'question', 'prediction', 'comparison', 'decision_criterion', 'conclusion')),
            'Interpretation requires the lead question, prediction, actual comparison, criterion and conclusion')
    require(judgment.get('decision') in ('retain', 'repair', 'authority_required'), 'Invalid interpretation decision')
    specification = documents['specification']
    require(isinstance(specification, dict) and all(k in specification for k in ('estimand','identification')),
            'Interpretation requires the adopted estimand and identification')
    if isinstance(specification, dict) and isinstance(specification.get('question'), str):
        require(judgment['question'] == specification['question'], 'Interpret the adopted question')
    observed = []
    paths = judgment.get('observations')
    require(isinstance(paths, list) and paths, 'Interpretation must consume actual result fields')
    for path in paths:
        require(isinstance(path, list) and path and all(isinstance(k, str) or type(k) is int for k in path),
                'Each observation names a result field path')
        value = documents['result']
        for key in path:
            require((isinstance(value, dict) and key in value) or
                    (isinstance(value, list) and type(key) is int and 0 <= key < len(value)), 'Missing observed result field')
            value = value[key]
        observed.append({'path': path, 'value': value})
    if judgment['decision'] != 'retain':
        require(isinstance(judgment.get('producing_owner'), str) and judgment['producing_owner'].strip(),
                'A consequential mismatch needs its actual producing owner')
    operation = judgment.get('next_operation')
    require(operation is None or isinstance(operation, dict) and set(operation) == {'argv', 'cwd'} and
            isinstance(operation['argv'], list) and operation['argv'] and
            all(isinstance(x, str) and x for x in operation['argv']) and isinstance(operation['cwd'], str),
            'Interpretation next operation must use the existing argv/cwd contract')
    return {'status': 'interpreted', 'sources': sources, 'result_interpretation': {
        **deepcopy(judgment), 'observations': observed,
        'adopted_definition': {k: specification[k] for k in ('question','estimand','identification','population','period','unit')
                               if isinstance(specification, dict) and k in specification},
        'specification_sha256': sources['specification']['sha256'], 'result_sha256': sources['result']['sha256'],
        'authority': 'The existing adopted specification and task authority remain binding.'},
        'next_operation': None if judgment['decision'] == 'authority_required' else operation,
        'scientific_specification_changed': False, 'executed': False}


def assess(contract, root):
    require(isinstance(contract, dict), 'Contract must be an object')
    source_entries, literature = literature_input(contract, root, contract.get('sources'))
    sources = load_sources(root, source_entries)
    datasets = {k: dataset(root, k, v, sources) for k, v in contract.get('datasets', {}).items()}
    candidates = contract.get('candidates')
    require(isinstance(candidates, list) and candidates, 'Candidates required')
    ids = [row.get('id') for row in candidates]
    require(all(isinstance(x, str) and x.strip() for x in ids) and len(ids) == len(set(ids)), 'Candidate IDs must be distinct')
    ranking = contract.get('selection', {})
    require(ranking.get('rule') == 'owner_order' and isinstance(ranking.get('order'), list) and len(ranking['order']) == len(ids) and set(ranking['order']) == set(ids), 'Selection must give each candidate exactly once in owner order')
    adopted = None
    if contract.get('adopted_design') is not None:
        ref = contract['adopted_design']
        require(isinstance(ref, dict) and set(ref) == {'path', 'sha256'}, 'Adopted design needs its path and hash')
        adopted = json.loads(file_bytes(root, ref['path'], ref['sha256']))
    results = {}
    for item in candidates:
        dimensions(item.get('dimensions'), 'Candidate')
        evidence(item.get('evidence'), sources, 'Candidate')
        closest = item.get('closest_answers')
        require(isinstance(closest, list) and closest, 'Closest-answer comparisons required')
        answer_ids = [answer.get('id') for answer in closest]
        require(all(isinstance(key, str) and key.strip() for key in answer_ids) and len(answer_ids) == len(set(answer_ids)), 'Closest answers require distinct IDs')
        for answer in closest:
            dimensions(answer.get('dimensions'), 'Closest answer')
            evidence(answer.get('evidence'), sources, 'Closest answer')
        judgment = item.get('judgment', {})
        require(judgment.get('classification') in ('replication', 'changed_contribution') and all(isinstance(judgment.get(k), str) and judgment[k].strip() for k in ('owner', 'rationale')), 'Owner classification and rationale required')
        evidence(judgment.get('evidence'), sources, 'Owner judgment')
        cited = {ref['source_id'] for ref in judgment['evidence']}
        require(all(cited & {ref['source_id'] for ref in answer['evidence']} for answer in closest),
                'Owner judgment must cite evidence from each closest answer')
        changes = judgment.get('changed_dimensions')
        require(isinstance(changes, list) and len(changes) == len(set(changes)) and set(changes) <= set(DIMENSIONS), 'Invalid changed dimensions')
        require((judgment['classification'] == 'replication' and not changes) or (judgment['classification'] == 'changed_contribution' and changes), 'Classification requires consistent owner-selected dimensions')
        opposing = judgment.get('contradictory_evidence', [])
        if opposing:
            evidence(opposing, sources, 'Contradictory evidence')
        data = datasets.get(item.get('dataset'))
        require(data is not None, 'Candidate dataset missing')
        assessment = fit(data, item.get('requirements'), datasets)
        if opposing:
            assessment['feasible'] = False
            assessment['reasons'].append('contradictory_evidence')
        operation = item.get('next_operation')
        require(isinstance(operation, dict) and set(operation) == {'argv', 'cwd'}
                and isinstance(operation['argv'], list) and operation['argv']
                and all(isinstance(arg, str) and arg for arg in operation['argv'])
                and isinstance(operation['cwd'], str) and operation['cwd'].strip(),
                'Candidate next operation requires argv and cwd')
        results[item['id']] = {'id': item['id'], 'dimensions': item['dimensions'], 'evidence': item['evidence'],
                               'closest_answers': closest, 'judgment': judgment, 'formulation': formulation_record(item, sources, adopted), 'dataset': data['id'],
                               'comparison': [{'closest_id': answer['id'], 'dimensions':
                                               {key: {'candidate': item['dimensions'][key], 'closest_answer': answer['dimensions'][key],
                                                      'owner_identified_change': key in changes} for key in DIMENSIONS}} for answer in closest],
                               'dataset_sha256': data['sha256'], 'definition_versions': data['definition_versions'],
                               'requirements': item['requirements'], 'fit': assessment, 'next_operation': item['next_operation']}
    pending = next((key for key in ranking['order'] if results[key]['fit']['feasible']), None)
    selected = pending if pending is not None and results[pending]['formulation'] is not None else None
    return {'status': 'selected' if selected else 'formulation_required' if pending else 'no_feasible_candidate',
            'pending_formulation': pending if pending and not selected else None, 'selection': ranking, 'selected_candidate': selected, 'next_operation': results[selected]['next_operation'] if selected else None,
            'sources': {k: {'path': v['path'], 'sha256': v['sha256']} for k, v in sources.items()},
            'datasets': {k: {key: value for key, value in v.items() if key != 'rows'} for k, v in datasets.items()},
            'candidates': [results[k] for k in ranking['order']],
            'corpus': contract.get('corpus'),
            'source_knowledge': literature['propositions'] if literature else []}


def propose(contract, root):
    """Create provisional comparisons from source claims and authorized transformations."""
    require(isinstance(contract, dict), 'Proposal contract must be an object')
    sources, literature = literature_input(contract, root, contract.get('design_sources'))
    normalized = load_sources(root, sources)
    require(literature is None or 'design_propositions' not in contract,
            'Selected corpus already owns the source propositions')
    propositions = literature['design_propositions'] if literature else contract.get('design_propositions')
    require(isinstance(propositions, list) and propositions, 'Source propositions are required')
    bases, skipped, seen = {}, [], set()
    for row in propositions:
        require(isinstance(row, dict) and isinstance(row.get('id'), str) and row['id'], 'Proposition needs an ID')
        require(row['id'] not in seen, 'Proposition IDs must be distinct')
        seen.add(row['id'])
        raw = row.get('dimensions', {})
        require(isinstance(raw, dict), 'Proposition dimensions must be an object')
        missing = [key for key in DIMENSIONS if key not in raw]
        if missing:
            skipped.append({'id':row['id'], 'missing_dimensions':missing})
            continue
        dimensions_out, references = {}, []
        for key in DIMENSIONS:
            field = raw.get(key)
            require(isinstance(field, dict) and isinstance(field.get('claim'), str) and field['claim'].strip(),
                    'Each source proposition needs five claims and their evidence')
            ref = field.get('evidence')
            evidence([ref], normalized, 'Proposition '+key)
            dimensions_out[key] = field['claim']
            if ref not in references: references.append(ref)
        bases[row['id']] = {'id':row['id'], 'dimensions':dimensions_out, 'evidence':references}
    alternatives = contract.get('transformations')
    require(isinstance(alternatives, list) and len(alternatives) >= 2, 'At least two transformations are required')
    permitted = contract.get('permitted_dimensions')
    require(isinstance(permitted, list) and permitted and len(set(permitted)) == len(permitted)
            and set(permitted) <= set(DIMENSIONS), 'Permitted dimensions must be specified')
    candidates = []
    for item in alternatives:
        require(isinstance(item, dict) and isinstance(item.get('id'), str) and item['id']
                and item.get('base') in bases, 'Each transformation needs an ID and source proposition')
        changes = item.get('changes')
        require(isinstance(changes, dict) and changes and set(changes) <= set(permitted)
                and all(isinstance(v, str) and v.strip() for v in changes.values()), 'Transformation exceeds permitted dimensions')
        base = bases[item['base']]
        changed = {**base['dimensions'], **changes}
        actual = [key for key in DIMENSIONS if changed[key] != base['dimensions'][key]]
        require(actual, 'Transformation must change at least one claim')
        refs = item.get('evidence', [])
        evidence(refs, normalized, 'Transformation')
        candidate = {'id':item['id'], 'dimensions':changed, 'evidence':refs,
                     'closest_answers':[base],
                     'judgment':{'owner':'unadopted mechanical proposal', 'classification':'changed_contribution',
                         'rationale':'Compare the specified transformed dimensions with the source proposition; adoption requires owner judgment.',
                         'changed_dimensions':actual, 'evidence':base['evidence']},
                     'dataset':item.get('dataset'), 'requirements':item.get('requirements'),
                     'next_operation':item.get('next_operation')}
        candidates.append(candidate)
    ids = [row['id'] for row in candidates]
    require(len(set(ids)) == len(ids), 'Transformation IDs must be distinct')
    order = contract.get('priority_order')
    require(isinstance(order, list) and len(order) == len(ids) and set(order) == set(ids),
            'Adopted candidate priority must order all transformations')
    assessed = assess({'sources':sources, 'datasets':contract.get('datasets', {}), 'candidates':candidates,
                       'selection':{'rule':'owner_order', 'order':order}}, root)
    assessed['selection']['rule'] = 'proposed_priority'
    assessed['skipped_propositions'] = skipped
    assessed['adoption_required'] = True
    assessed['status'] = 'proposed'
    assessed['target_stage'] = assessed['next_operation']
    assessed['corpus'] = contract.get('corpus')
    assessed['source_knowledge'] = literature['propositions'] if literature else []
    return assessed



R_METHODS = {
    'rct_design': ('randomizr', 'declare_ra'),
    'ols_r': ('stats', 'lm'),
    'fixest_ols': ('fixest', 'feols'),
    'fixest_ppml': ('fixest', 'fepois'),
    'negative_binomial_r': ('MASS', 'glm.nb'),
    'heckman': ('sampleSelection', 'heckit'),
    'sunab': ('fixest', 'feols'),
    'did2s': ('did2s', 'did2s'),
    'did_imputation': ('didimputation', 'did_imputation'),
    'fixes_event_study': ('fixes', 'event_study'),
    'nonabs_did': ('nonabsdid', 'nabs_event_study'),
    'synthdid': ('synthdid', 'synthdid_estimate'),
    'drdid_panel': ('DRDID', 'drdid_panel'),
    'drdid_rc': ('DRDID', 'drdid_rc'),
    'did_multiplegt_dyn': ('DIDmultiplegtDYN', 'did_multiplegt_dyn'),
    'honest_did': ('HonestDiD', 'createSensitivityResults_relativeMagnitudes'),
    'wild_cluster_bootstrap': ('fwildclusterboot', 'boottest'),
    'club_sandwich': ('clubSandwich', 'coef_test'),
    'rdrobust_r': ('rdrobust', 'rdrobust'),
    'rddensity': ('rddensity', 'rddensity'),
    'rdpower': ('rdpower', 'rdpower'),
    'grf': ('grf', 'causal_forest'),
    'grf_instrumental': ('grf', 'instrumental_forest'),
    'grf_multi_arm': ('grf', 'multi_arm_causal_forest'),
    'grf_survival': ('grf', 'causal_survival_forest'),
    'iv_ar_robust': ('ivDiag', 'AR_test'),
    'qte': ('qte', 'unc_qte'),
    'qtt': ('qte', 'unc_qte'),
    'quantile_did': ('qte', 'qdid'),
    'changes_in_changes': ('qte', 'cic'),
    'marginaleffects': ('marginaleffects', 'avg_slopes'),
    'bunching': ('bunching', 'bunchit'),
    'continuous_did': ('contdid', 'cont_did'),
}


GRF_METHODS = {name for name, (package, _) in R_METHODS.items() if package == 'grf'}


QTE_METHODS = {'qte', 'qtt', 'quantile_did', 'changes_in_changes'}


MARGINAL_FUNCTIONS = {'slopes', 'avg_slopes', 'predictions', 'avg_predictions',
                      'comparisons', 'avg_comparisons'}


RUN_FIELDS = {'method','data','id','outcome','regressors','endogenous','instruments',
              'population','period','unit','estimand','identification','assignment','inference','options'}


DML_METHODS = {'dml_plr':'DoubleMLPLR', 'dml_did':'DoubleMLDID',
               'dml_irm':'DoubleMLIRM', 'dml_pliv':'DoubleMLPLIV', 'dml_iivm':'DoubleMLIIVM',
               'dml_ssm':'DoubleMLSSM', 'dml_qte':'DoubleMLQTE', 'dml_pq':'DoubleMLPQ',
               'dml_cvar':'DoubleMLCVAR', 'dml_apo':'DoubleMLAPO'}


DML_TREATMENT_METHODS = set(DML_METHODS) - {'dml_pliv', 'dml_iivm'}


INFERENCE_METHODS = {
    name: {'engine':engine,'package':'statsmodels' if name=='holm' else 'StatsPAI',
        'version':'0.14.6' if name=='holm' else '1.43.1',
        'source_revision':None if name=='holm' else 'ddb3b45f2d3fc649ea794aa15f8989bb10f8e543',
        'required_options':required,'targets':targets,'inference':inference,'conditions':conditions}
    for name,engine,required,targets,inference,conditions in [
        ('shift_share_inference','statspai.ssaggregate; statspai.bartik',
         ['shares','shocks','identification_basis','definitions'],['structural_parameter','linear_projection'],
         'Shock identification: AKM/AKM0/BHJ; share identification: native location HC1 or cluster covariance and Rotemberg attribution',
         'Explicit shock or exposure-share exogeneity, independent shocks for AKM/BHJ, baseline share timing/population, valid linear IV moments and nonzero first stage.'),
        ('sensitivity_oster','statspai.oster_bounds',['r_max','delta'],['sensitivity'],
         'Exact Oster proportional-selection coefficient and identified interval',
         'Nested intercept OLS models on one sample, the adopted proportional-selection restriction and maximum R-squared.'),
        ('sensitivity_cinelli','statspai.sensemakr',['term'],['sensitivity'],
         'Cinelli-Hazlett partial R-squared and robustness values using classical OLS covariance',
         'The saved OLS coefficient, classical standard error and residual degrees of freedom describe the same fitted sample.'),
        ('sensitivity_evalue','statspai.evalue',['term','measure','coefficient_scale'],['sensitivity'],
         'E-values for the saved estimate and interval under the declared effect-scale conversion',
         'Correct RR/OR/HR/difference scale, specified contrast and outcome standard deviation where required.'),
        ('romano_wolf','statspai.romano_wolf',['treatment','outcomes','n_boot','seed','family'],['family_inference'],
         'Joint row or cluster bootstrap Romano-Wolf stepdown p-values',
         'The declared outcome family, full-rank treatment contrasts and adopted independent resampling unit.'),
        ('specification_curve','statspai.spec_curve; statsmodels.stats.multitest.multipletests',
         ['treatment','controls','se_types','family'],['specification_curve','family_inference'],
         'Holm adjusted p-values and Bonferroni simultaneous intervals for the complete declared family',
         'A finite declared specification family, estimable treatment in every member and valid member-specific covariance.'),
        ('holm','statsmodels.stats.multitest.multipletests',['p_values','family'],['family_inference'],
         'Holm stepdown family-wise error correction of saved p-values',
         'The declared family contains all relevant hypotheses and each saved p-value is valid under its null.'),
        ('spatial_conley','statspai.regress; statspai.conley',['lat','lon','dist_cutoff','kernel','distance'],
         ['linear_projection','structural_parameter'],'Official Conley HAC covariance and Student t intervals',
         'Exogenous linear regressors, degree coordinates, adopted distance/time kernels and bandwidths, and spatial dependence conditions.'),
    ]
}


CAUSAL_EXTENSIONS = {
    name: {'module':module, 'function':function, 'engine':module+'.'+function,
           'package':'StatsPAI', 'version':'1.43.1',
           'source_revision':'ddb3b45f2d3fc649ea794aa15f8989bb10f8e543',
           'required_options':required, 'targets':targets,
           'inference':inference, 'conditions':conditions}
    for name, module, function, required, targets, inference, conditions in [
        ('lp_did','statspai.did.lp_did','lp_did',['entity','time','treatment'],
         ['event_time_att'],'native entity-clustered horizon regressions and joint covariance',
         'Absorbing binary adoption, consecutive balanced panel, clean untreated comparisons and conditional parallel trends.'),
        ('bacon','statspai.did.bacon','bacon_decomposition',['entity','time','treatment'],
         ['twfe_decomposition'],'native decomposition; no sampling interval',
         'Balanced absorbing binary-treatment panel; sampling weights constant within entity.'),
        ('scm_diagnostics','statspai.synth.scm','synth',['entity','time','treated','treatment_time'],
         ['treated_trajectory','att'],'native in-space placebo ranks, interval and selected donor/time diagnostics',
         'One treated unit, balanced untreated donors, adopted pretreatment fit and treatment date.'),
        ('augmented_synthetic_control','statspai.synth.augsynth','augsynth',['entity','time','treated','treatment_time'],
         ['treated_trajectory','att'],'native placebo-ATT standard deviation, rank p value and normal interval',
         'Common treatment date, eligible untreated donors and the adopted ridge-augmented counterfactual model.'),
        ('mediation','statspai.mediation.mediate','mediate',['treatment','mediator'],
         ['mediation_effect'],'native bootstrap, stacked sandwich or linear delta method',
         'Sequential treatment/mediator exchangeability, consistency, overlap and the adopted mediator/outcome models.'),
        ('metalearner','statspai.metalearners.metalearners','metalearner',['treatment'],
         ['ate','cate'],'native cross-fitted AIPW average and influence-function covariance',
         'Binary treatment, conditional exchangeability and overlap; learner-specific CATEs retain their own target.'),
        ('tmle','statspai.tmle.tmle','tmle',['treatment'],
         ['ate','att','atc'],'native targeted influence function or complete-fit bootstrap',
         'Binary treatment, consistency, conditional exchangeability, overlap and adopted nuisance/fold/targeting choices.'),
        ('kitagawa','statspai.decomposition.kitagawa','kitagawa_decompose',['group','by'],
         ['rate_decomposition'],'exact symmetric rate/composition identity',
         'Groups coded 0 and 1, common observed cells, explicit individual or cell-population weights.'),
        ('dfl','statspai.decomposition.dfl','dfl_decompose',['group'],
         ['distribution_decomposition'],'native group-stratified row bootstrap or descriptive decomposition',
         'Groups coded 0 and 1, common covariate support, declared counterfactual direction/statistic/propensity clipping.'),
        ('gelbach','statspai.decomposition.oaxaca','gelbach',['added_regressors','var_of_interest'],
         ['coefficient_decomposition'],'native joint stacked-regression covariance',
         'Same sample, base regressors and added controls; full-rank short/long projections.'),
        ('survival_km','statspai.survival.models','kaplan_meier',['status'],
         ['survival_curve'],'native Greenwood, infinitesimal-jackknife or Xie-Liu covariance',
         'Observed durations/events and conditionally independent right censoring; declared delayed entry and weights.'),
        ('survival_aft','statspai.survival.models','survreg',['status'],
         ['log_time_ratio','time_ratio'],'native likelihood, sandwich or cluster covariance',
         'Positive durations, conditionally independent right censoring and adopted parametric AFT distribution.'),
    ]
}


CAUSAL_EXTENSIONS['bayesian_model'] = {
    'module':'pymc','function':'sample','engine':'pymc.sample + arviz.summary',
    'package':'pymc','version':'6.4.0',
    'packages_by_engine':{
        'pymc':{'pymc':'6.4.0','arviz':'1.3.0','arviz-stats':'1.3.3','xarray':'2026.9.0',
            'scipy':'1.18.1','h5netcdf':'1.8.2','h5py':'3.16.0'},
        'causalpy':{'causalpy':'0.9.0','pymc':'5.28.5','arviz':'0.23.4','numpy':'2.3.5',
            'pymc-extras':'0.10.0','pytensor':'2.38.3','preliz':'0.25.0',
            'better-optimize':'0.5.1','arviz-stats':'1.3.3','scikit-learn':'1.7.2',
            'xarray':'2026.9.0','scipy':'1.18.1','h5netcdf':'1.8.2','h5py':'3.16.0'}},
    'required_options':['engine','model_file','builder','posterior_output','var_names','sampling'],
    'targets':['posterior_parameter','posterior_effect','prediction'],
    'inference':'PyMC posterior draws; ArviZ posterior summaries, HDI, rank R-hat and effective sample sizes',
    'conditions':'Adopted likelihood, priors, economic model, sample and requested posterior quantities in an existing model file; PyMC 6/ArviZ 1 for engine=pymc, CausalPy 0.9 with PyMC 5/ArviZ 0 for engine=causalpy.'}


# Model-specific programs use the existing research argv stage. The selected
# package and its native calls stay here beside the existing engine selector.
OFFICIAL_PROJECT_IMPLEMENTATIONS = {
    'cmdstanpy': {
        'design':'bayesian_model', 'language':'python', 'packages':{'cmdstanpy':'1.3.2'},
        'function':'cmdstanpy.CmdStanModel.sample',
        'apis':[{'package':'cmdstanpy','symbol':'cmdstanpy.CmdStanModel.sample','positional':1,'keywords':['data','chains','iter_warmup','iter_sampling','seed']}],
        'targets':['posterior_parameter','posterior_effect','prediction','policy_value'],
        'inputs':['adopted Stan model and included files','Stan data mapping, parameter units and observation IDs','chains, warmup, retained draws, seed and generated quantities'],
        'outputs':['native chain CSV files','CmdStanMCMC.summary() and diagnose()','generated quantities, pointwise log likelihood and requested posterior decision'],
        'conditions':['adopted likelihood, priors, identifying restrictions and parameterization'],
        'inference':'native Stan chain diagnostics, functional MCSE and generated predictive quantities',
        'installation':'Install CmdStan 2.40.0 with its supported C++ toolchain; bind the CmdStan installation, compiled model and included sources in the project stage.',
        'source':'https://mc-stan.org/cmdstanpy/api.html#cmdstanpy.CmdStanModel.sample'},
    'cmdstanr': {
        'design':'bayesian_model', 'language':'r', 'packages':{'cmdstanr':'0.9.0'},
        'function':'cmdstanr::cmdstan_model',
        'apis':[{'package':'cmdstanr','symbol':'cmdstan_model','positional':0,'keywords':['stan_file']}],
        'targets':['posterior_parameter','posterior_effect','prediction','policy_value'],
        'inputs':['adopted Stan model and included files','Stan data mapping and observation IDs','sample(data, chains, iter_warmup, iter_sampling, seed) settings'],
        'outputs':['CmdStanMCMC draws and chain CSV files','summary(), diagnostic_summary() and sampler_diagnostics()','generated predictive quantities and requested posterior decision'],
        'conditions':['adopted likelihood, priors, identifying restrictions and parameterization'],
        'inference':'native Stan chain diagnostics and posterior package summaries',
        'installation':'Restore cmdstanr in the selected R project and CmdStan 2.40.0 with its supported C++ toolchain; track the installation and model sources.',
        'source':'https://mc-stan.org/cmdstanr/reference/model-method-sample.html'},
    'brms': {
        'design':'bayesian_model', 'language':'r', 'packages':{'brms':'2.23.0','cmdstanr':'0.9.0'},
        'function':'brms::brm',
        'apis':[{'package':'brms','symbol':'brm','positional':0,'keywords':['formula','data','family','prior','backend']}],
        'targets':['posterior_parameter','posterior_effect','prediction','policy_value'],
        'inputs':['multilevel formula, family, group IDs and explicit priors','canonical data and observation IDs','backend="cmdstanr", chains, warmup, iter and seed'],
        'outputs':['saved brmsfit and generated Stan code','posterior_epred(), posterior_predict(), pp_check() and loo()','draw-level economic contrasts and requested posterior decision'],
        'conditions':['adopted multilevel likelihood, grouping structure, priors and identifying restrictions'],
        'inference':'Stan diagnostics, posterior predictive checks and design-matched loo comparison',
        'installation':'Restore the R project, brms imports and cmdstanr; install CmdStan 2.40.0 and its supported toolchain.',
        'source':'https://paulbuerkner.com/brms/reference/brm.html'},
    'numpyro': {
        'design':'bayesian_model', 'language':'python', 'packages':{'numpyro':'0.22.0','jax':None,'jaxlib':None},
        'function':'numpyro.infer.MCMC.run',
        'apis':[{'package':'numpyro','symbol':'numpyro.infer.MCMC.run','positional':2,'keywords':['extra_fields']}],
        'targets':['posterior_parameter','posterior_effect','prediction','policy_value'],
        'inputs':['adopted NumPyro model and canonical model arguments','NUTS/MCMC chain and warmup settings, PRNG key and selected JAX dtype/device','extra_fields including adopted sampler diagnostics'],
        'outputs':['get_samples(group_by_chain=True) and get_extra_fields(group_by_chain=True)','numpyro.diagnostics.summary() and Predictive draws','draw-level economic contrasts and requested posterior decision'],
        'conditions':['adopted likelihood, priors and identifying restrictions','selected JAX precision, device and chain method support the calculation'],
        'inference':'native chain diagnostics and predictive draws with retained chain identity',
        'installation':'Install the selected CPU/GPU JAX build supported by NumPyro; retain actual jax/jaxlib versions, device and precision in the runtime.',
        'source':'https://num.pyro.ai/en/stable/mcmc.html#numpyro.infer.mcmc.MCMC.run'},
    'turing': {
        'design':'bayesian_model', 'language':'julia', 'packages':{'Turing':'0.49.0','FlexiChains':None},
        'function':'Turing.sample', 'apis':[],
        'targets':['posterior_parameter','posterior_effect','prediction','policy_value'],
        'inputs':['adopted @model and canonical model arguments','NUTS settings, seed, draws and multiple-chain executor','Project.toml and Manifest.toml'],
        'outputs':['native FlexiChains.VNChain multi-chain draws and summaries','Turing.predict() generated quantities','draw-level economic contrasts and requested posterior decision'],
        'conditions':['adopted likelihood, priors and identifying restrictions','selected automatic differentiation and sampler support the model'],
        'inference':'native Turing/FlexiChains diagnostics and generated predictive quantities',
        'installation':'Restore Turing and FlexiChains in the selected Julia >=1.10.8 project; bind its Project.toml, Manifest.toml and --project prefix. An adopted MCMCChains output explicitly loads its extension and chain_type.',
        'source':'https://turinglang.org/docs/core-functionality/'},
    'pymc_marketing_mmm': {
        'design':'marketing_mmm', 'implementation':'pymc_marketing', 'language':'python',
        'packages':{'pymc-marketing':'1.3.0','pymc':'6.3.1','arviz':'1.3.0'},
        'function':'pymc_marketing.mmm.MMM.fit',
        'apis':[{'package':'pymc-marketing','symbol':'pymc_marketing.mmm.MMM.fit','positional':1,'keywords':['X','y','draws','tune','chains','cores','random_seed']}],
        'targets':['posterior_parameter','posterior_effect','prediction','allocation','policy_value'],
        'inputs':['date/channel/control columns and outcome with units','adstock, saturation, channel priors, calibration experiments and adjustment set','adopted posterior sampling settings, contribution margins and budget constraints'],
        'outputs':['saved native posterior and posterior predictive draws','channel response and incremental contribution draws','BudgetOptimizer.allocate_budget() allocation and draw-level incremental profit'],
        'conditions':['adopted confounding adjustment and experimental calibration identify the channel response','carryover, saturation, time/geographic variation and outcome scale match the decision'],
        'inference':'native posterior/predictive diagnostics and experiment-calibrated channel contrasts',
        'installation':'Use its selected environment: pymc-marketing 1.3.0 requires PyMC >=6.3.1,<6.4.0 and ArviZ >=1.2,<2.',
        'source':'https://www.pymc-marketing.io/en/stable/api/generated/pymc_marketing.mmm.MMM.html'},
    'meridian': {
        'design':'marketing_mmm', 'implementation':'meridian', 'language':'python',
        'packages':{'google-meridian':'2.2.0'},
        'function':'meridian.model.model.Meridian.sample_posterior',
        'apis':[{'package':'google-meridian','symbol':'meridian.model.model.Meridian.sample_posterior','positional':1,'keywords':['n_chains','n_adapt','n_burnin','n_keep','seed']}],
        'targets':['posterior_parameter','posterior_effect','prediction','allocation','policy_value'],
        'inputs':['InputData from adopted geo/time KPI, media/spend, population, controls and revenue_per_kpi','ModelSpec, ROI/calibration priors and experiment periods','chain/adaptation/burnin/retained draws, seed and budget bounds'],
        'outputs':['native inference_data and saved model','Analyzer response, ROI/mROI and predictive quantities','BudgetOptimizer.optimize() allocation and incremental revenue/profit comparison'],
        'conditions':['adopted adjustment set, geographic/time variation and calibration identify the media response','media and KPI units and revenue conversion match the action'],
        'inference':'native posterior diagnostics, predictive fit and calibrated media contrasts',
        'installation':'Restore its separate compatible environment: google-meridian 2.2.0 requires arviz<0.20, pandas<3, numpy<2.4 and jax<1 with its TensorFlow/TFP closure.',
        'source':'https://developers.google.com/meridian/reference/api/meridian/model/model/Meridian'},
    'pymc_marketing_clv': {
        'design':'customer_lifetime_value', 'implementation':'pymc_marketing', 'language':'python',
        'packages':{'pymc-marketing':'1.3.0','pymc':'6.3.1','arviz':'1.3.0'},
        'function':'pymc_marketing.clv.BetaGeoModel.fit',
        'apis':[{'package':'pymc-marketing','symbol':'pymc_marketing.clv.BetaGeoModel.fit','positional':1,'keywords':['data','method','draws','tune','chains','cores','random_seed']}],
        'targets':['posterior_parameter','prediction','policy_value'],
        'inputs':['customer_id, repeat frequency, recency and T in one time unit','positive repeat-transaction monetary_value for GammaGammaModel','discount horizon, contribution margin, retention/acquisition costs and cohort population'],
        'outputs':['saved BetaGeoModel/GammaGammaModel posterior','expected_purchases() and expected_customer_lifetime_value() draws','cohort contribution CLV minus adopted acquisition/retention cost'],
        'conditions':['noncontractual repeat-purchase and dropout process fits the customer relationship','Gamma-Gamma spend model uses positive repeat amounts and its adopted frequency/spend independence restriction'],
        'inference':'native posterior predictive transaction/spend checks and cohort holdout performance',
        'installation':'Use the PyMC-Marketing environment with PyMC >=6.3.1,<6.4.0; preserve time-unit conversion and repeat-purchase definitions.',
        'source':'https://www.pymc-marketing.io/en/stable/guide/clv/quickstart.html'},
    'statsforecast': {
        'design':'demand_forecast', 'language':'python', 'packages':{'statsforecast':'2.1.1'},
        'function':'statsforecast.StatsForecast.forecast',
        'apis':[{'package':'statsforecast','symbol':'statsforecast.StatsForecast.forecast','positional':1,'keywords':['h','df','level']}],
        'targets':['prediction'],
        'inputs':['unique_id, ds and y with declared frequency and observation/censoring rule','selected AutoARIMA/AutoETS or CrostonOptimized/ADIDA/IMAPA model','horizon, future known covariates, rolling-origin windows and supported interval method'],
        'outputs':['native ID/time/model-labelled forecasts and available prediction intervals','cross_validation() origin/horizon losses','saved demand forecast inputs for the adopted inventory loss'],
        'conditions':['past information and genuinely known future covariates define each forecast origin','intermittent point forecasts and models providing prediction intervals retain their native output scope'],
        'inference':'native supported intervals or adopted time-series conformal intervals evaluated at matching rolling origins',
        'installation':'Restore StatsForecast in a pandas<3 environment; add only selected model/reader dependencies.',
        'source':'https://nixtlaverse.nixtla.io/statsforecast/src/core/core.html#statsforecast.forecast'},
    'hierarchicalforecast': {
        'design':'hierarchical_forecast', 'language':'python', 'packages':{'hierarchicalforecast':'1.5.3'},
        'function':'hierarchicalforecast.core.HierarchicalReconciliation.reconcile',
        'apis':[{'package':'hierarchicalforecast','symbol':'hierarchicalforecast.core.HierarchicalReconciliation.reconcile','positional':1,'keywords':['Y_hat_df','tags','S_df','Y_df','level','intervals_method']}],
        'targets':['prediction'],
        'inputs':['base forecast Y_hat_df and hierarchy summing matrix S_df with exact series ordering','tags, training Y_df and adopted BottomUp/MinTrace reconciliation','supported interval method, levels, sample count and seed'],
        'outputs':['native reconciled series-labelled point forecasts and intervals','coherent predictive samples when selected','rolling-origin hierarchy-level forecast and inventory loss'],
        'conditions':['hierarchy keys and summing matrix define the same complete population as base forecasts','reconciliation covariance and predictive dependence use information available at the forecast origin'],
        'inference':'native normality/bootstrap/PERMBU reconciliation with the selected method and covariance inputs',
        'installation':'Install only the reconciliation family; use the existing StatsForecast environment when base forecasts come from StatsForecast.',
        'source':'https://nixtlaverse.nixtla.io/hierarchicalforecast/src/core.html#hierarchicalreconciliation.reconcile'},
    'ortools': {
        'design':'operations_optimization', 'language':'python', 'packages':{'ortools':'9.15.6755'},
        'function':'ortools.sat.python.cp_model.CpSolver.solve',
        'apis':[{'package':'ortools','symbol':'ortools.sat.python.cp_model.CpSolver.solve','positional':2,'keywords':[]}],
        'targets':['allocation','policy_value'],
        'inputs':['CpModel integer/Boolean decisions, staffing/routing/inventory capacities and logical constraints','integer-scaled contribution/cost objective with original currency conversion','time limit, solver settings and adopted acceptable optimality gap'],
        'outputs':['native status, feasible allocation, objective_value and best_objective_bound','allocation restored to original units and binding resource quantities'],
        'conditions':['integer scaling preserves the adopted feasible set and economic objective','an accepted solver status and objective bound satisfy the adopted decision tolerance'],
        'inference':'solver status, primal feasibility and objective/bound gap in original economic units',
        'installation':'Install OR-Tools only for its selected CP-SAT/routing/flow model; continuous LP/MILP already supported by SciPy remains eligible.',
        'source':'https://developers.google.com/optimization/cp/cp_solver'},
    'pyomo': {
        'design':'operations_optimization', 'language':'python', 'packages':{'pyomo':'6.10.1','highspy':None},
        'function':'pyomo.contrib.solver.solvers.highs.Highs.solve',
        'apis':[{'package':'pyomo','symbol':'pyomo.contrib.solver.solvers.highs.Highs.solve','positional':2,'keywords':[]}],
        'targets':['allocation','policy_value'],
        'inputs':['ConcreteModel variables, objective and linear/mixed-integer constraints in declared units','adopted scenario weights, bounds and solver options','selected HiGHS installation and decision tolerance'],
        'outputs':['native solver termination and feasible primal allocation','objective, bound/gap and original constraint residuals','scenario-specific contribution, resource use and shadow values when supported'],
        'conditions':['selected solver supports the adopted mathematical model','accepted termination, feasibility and objective gap meet the adopted tolerance'],
        'inference':'native solver termination, primal feasibility and objective bound; nonlinear models select their matching solver explicitly',
        'installation':'Install Pyomo and its selected solver; this profile uses HiGHS through highspy for LP/MILP. Bind another supported solver for an adopted nonlinear model.',
        'source':'https://pyomo.readthedocs.io/en/stable/reference/topical/solvers/new-solver.html'},
    'arch': {
        'design':'financial_volatility', 'language':'python', 'packages':{'arch':'8.0.0'},
        'function':'arch.arch_model',
        'apis':[{'package':'arch','symbol':'arch.arch_model','positional':1,'keywords':['mean','vol','p','o','q','dist']}],
        'targets':['structural_parameter','prediction','policy_value'],
        'inputs':['dated return/loss series, rescaling and information set','adopted mean/volatility/innovation distribution and fitting window','forecast horizon, simulation seed and portfolio/loss conversion'],
        'outputs':['native fit, coefficient covariance and convergence_flag','forecast() conditional mean/variance and simulated paths when selected','adopted loss-tail and capital-allocation quantities'],
        'conditions':['return scale, conditional mean, volatility law and innovation tails match the risk horizon'],
        'inference':'native robust/classic fit covariance and forecast-origin loss evaluation',
        'installation':'Install arch in the selected financial time-series environment; retain its native fitted result.',
        'source':'https://bashtage.github.io/arch/univariate/introduction.html'},
    'lifelines': {
        'design':'customer_survival', 'language':'python', 'packages':{'lifelines':'0.30.3'},
        'function':'lifelines.CoxPHFitter.fit',
        'apis':[{'package':'lifelines','symbol':'lifelines.CoxPHFitter.fit','positional':2,'keywords':['duration_col','event_col','entry_col','strata','cluster_col','robust']}],
        'targets':['hazard_ratio','prediction','policy_value'],
        'inputs':['customer duration, event, entry, covariates and cohort IDs','adopted strata, weights and clustering','prediction horizon, future margin and retention action/cost'],
        'outputs':['saved native CoxPH fit and coefficient covariance','predict_survival_function() on the declared customer population','survival-weighted contribution value and adopted retention decision'],
        'conditions':['conditionally independent censoring/truncation and proportional hazards within adopted strata','a causal retention effect uses its separately adopted identifying design'],
        'inference':'native fit covariance, proportional-hazard diagnostics and censored holdout prediction',
        'installation':'Use lifelines in a pandas<3 environment for the survival-curve/CLV interface; existing PHReg hazard-coefficient fits retain their primary route.',
        'source':'https://lifelines.readthedocs.io/en/latest/fitters/regression/CoxPHFitter.html'},
    'pypsa': {
        'design':'energy_system', 'language':'python', 'packages':{'pypsa':'1.4.0'},
        'function':'pypsa.optimization.optimize.OptimizationAccessor.__call__',
        'apis':[{'package':'pypsa','symbol':'pypsa.optimization.optimize.OptimizationAccessor.__call__','positional':1,'keywords':['snapshots','solver_name','solver_options']}],
        'targets':['allocation','policy_value'],
        'inputs':['network buses, lines, generators, storage, loads and snapshot/investment weights','MW/MWh costs, availability, investment bounds and emissions constraints','selected solver, scenario and adopted feasibility/optimality tolerance'],
        'outputs':['Network.optimize() status and saved network','dispatch, capacity/storage investment, total cost and supported dual prices','baseline/scenario costs, emissions and allocation'],
        'conditions':['network and temporal constraints represent the adopted dispatch/investment problem','snapshot weights and capital-cost annualization use the same horizon'],
        'inference':'native solver termination, original energy-balance/capacity residuals and objective bound',
        'installation':'Restore PyPSA 1.4 in its pandas>=3 environment with the selected linopy/HiGHS closure.',
        'source':'https://docs.pypsa.org/latest/api/networks/optimize/'},
    'networkx': {
        'design':'network_allocation', 'language':'python', 'packages':{'networkx':'3.7'},
        'function':'networkx.maximum_flow',
        'apis':[{'package':'networkx','symbol':'networkx.maximum_flow','positional':3,'keywords':['capacity']}],
        'targets':['allocation'],
        'inputs':['directed graph with canonical node/edge IDs and nonnegative edge capacities','source, sink and capacity units','adopted network flow objective'],
        'outputs':['maximum flow value and edge flow dictionary','node conservation and edge-capacity quantities in original units'],
        'conditions':['capacities, feasible flow and the source/sink objective represent the economic allocation'],
        'inference':'native maximum-flow/minimum-cut equality and original conservation/capacity conditions',
        'installation':'Install NetworkX for the selected graph calculation; behavioural equilibrium and causal network exposure retain their separate model contracts.',
        'source':'https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.flow.maximum_flow.html'},
    'mesa': {
        'design':'agent_simulation', 'language':'python', 'packages':{'mesa':'3.5.2'},
        'function':'mesa.Model.run_model',
        'apis':[{'package':'mesa','symbol':'mesa.Model.run_model','positional':1,'keywords':[]}],
        'targets':['prediction','policy_value'],
        'inputs':['existing Mesa Model/Agent program with choices, information and transition rules','canonical calibration/initial states, seed and stopping rule','adopted scenario, collected economic outcomes and replications'],
        'outputs':['DataCollector agent/model observations and saved scenario outputs','prices, quantities, profits and welfare defined by the adopted model'],
        'conditions':['adopted agent rules, activation order and interaction graph define the model','fixed/calibrated/estimated parameter roles and convergence/stopping conditions remain explicit'],
        'inference':'model-defined simulation variation across adopted seeds/replications and original accounting conditions',
        'installation':'Install Mesa core for the selected project model; visualization extras and graph backends follow actual model imports.',
        'source':'https://mesa.readthedocs.io/stable/mesa.html#mesa.model.Model'}
}

OFFICIAL_PROJECT_DEFAULTS = {
    'marketing_mmm':'pymc_marketing_mmm', 'customer_lifetime_value':'pymc_marketing_clv',
    'demand_forecast':'statsforecast', 'hierarchical_forecast':'hierarchicalforecast',
    'operations_optimization':'ortools', 'financial_volatility':'arch',
    'customer_survival':'lifelines', 'energy_system':'pypsa',
    'network_allocation':'networkx', 'agent_simulation':'mesa'}


def _select_method(request, *, spec_path=None):
    """Select an estimator from economic objects and structured design conditions.

    Narrative identification is retained as evidence, never parsed as a package
    request. Existing flat specifications remain readable at this boundary.
    """
    required = {'question','estimand','identification','design','outcome_scale','data_structure','treatment_pattern','dependence'}
    contract_fields = ('population','comparison_group','observation_unit','assignment_unit','inference_unit',
                       'unit','period','assignment','weights','inference',
                       'economic_model','target','conditions','comparison','numerical','model_contract_id')
    optional = {'adopted_method','adopted_specification','options','score','structural_model','implementation','execution_context',
                'data','data_record','id','outcome','regressors','endogenous','instruments',*contract_fields}
    if not isinstance(request, dict) or not required <= request.keys() or set(request)-required-optional:
        raise ValueError(f'selection requires {sorted(required)} and accepts {sorted(optional)}')
    if any(not isinstance(request[k], str) or not request[k].strip() for k in required):
        raise ValueError('selection fields must be explicit nonempty strings')
    execution_context = request.get('execution_context', {})
    if not isinstance(execution_context, dict) or set(execution_context) - {
            'available_languages','data_engine','memory_budget_bytes','working_set_bytes','performance'}:
        raise ValueError('execution_context accepts available_languages, data_engine, memory_budget_bytes, working_set_bytes and observed performance')
    available_languages = execution_context.get('available_languages')
    if available_languages is not None and (not isinstance(available_languages, list) or
            any(language not in ('python','r','julia','sql') for language in available_languages)):
        raise ValueError('available_languages must list python, r, julia or sql')
    if execution_context.get('data_engine') not in (None,'pandas','duckdb','native'):
        raise ValueError('data_engine must be pandas, duckdb or native')
    for field in ('memory_budget_bytes','working_set_bytes'):
        value = execution_context.get(field)
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value <= 0):
            raise ValueError(f'execution_context.{field} must be a positive integer')
    adopted_spec = request.get('adopted_specification', {})
    if not isinstance(adopted_spec, dict):
        raise ValueError('adopted_specification must be an existing specification object')
    resources = json.loads((ROOT / ('RESOURCES.json' if FLAT_EXPORT else 'registry/resources.json')).read_text())['resources']
    placements = json.loads((ROOT / ('PLACEMENTS.json' if FLAT_EXPORT else 'registry/placements.json')).read_text())['resources']
    layout_path = 'export_alias' if FLAT_EXPORT else 'deployment_path' if ROOT.name == '.agents' else 'source_path'
    model_contract = None
    knowledge_plan = None
    contract_binding = None
    contract_id = request.get('model_contract_id', adopted_spec.get('model_contract_id'))
    if contract_id is not None:
        if not isinstance(contract_id, str) or not contract_id.startswith('MC-'):
            raise ValueError('model_contract_id must name a canonical MC- contract')
        rid = 'knowledge-retrieval'
        knowledge_relative = resources[rid]['source_path'] if layout_path == 'source_path' else placements[rid][layout_path]
        knowledge_path = (ROOT.parent if ROOT.name == '.agents' else ROOT) / knowledge_relative
        module_spec = importlib.util.spec_from_file_location('selected_model_knowledge', knowledge_path)
        knowledge = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(knowledge)
        reader = knowledge.Reader(knowledge.BASE)
        model_contract = reader.contract(contract_id)
        knowledge_plan = reader.plan([contract_id])
        knowledge_plan.pop('contracts')
        contract_binding = model_contract.get('selection_binding')
    for key in ('economic_model','target','conditions','comparison','numerical'):
        if not isinstance(request.get(key, adopted_spec.get(key,{})), dict):
            raise ValueError(f'{key} must be a structured object')
    facts = request.get('conditions', adopted_spec.get('conditions',{}))
    target = request.get('target', adopted_spec.get('target',{}))
    economic_model = request.get('economic_model', adopted_spec.get('economic_model',{}))
    comparison = request.get('comparison', adopted_spec.get('comparison',{}))
    numerical = request.get('numerical', adopted_spec.get('numerical',{}))
    for key in ('randomized','weak_instruments','homoskedastic_normal_errors',
                'conditional_exchangeability','overlap','parallel_trends',
                'exclusion','monotonicity','continuity','common_treatment_block',
                'equilibrium_counterfactual','independent_units','no_interference',
                'aggregate_shocks','stationary_equilibrium','nominal_rigidity',
                'complete_information','transferable_utility','coalition_externalities',
                'free_trading','all_states_possible','dose_time_invariant',
                'balanced_panel','strong_parallel_trends','covariate_adjustment','additive_effects',
                'dose_cohort_independence','joint_gaussian_errors','iid'):
        if key in facts and not isinstance(facts[key], bool):
            raise ValueError(f'conditions.{key} must be boolean')
    target_kind = target.get('kind')
    allowed_targets = {'ate','att','itt','late','cate','policy_value','linear_projection',
        'conditional_mean','count_distribution','group_time_att','event_time_att',
        'treatment_path_effect','dose_response','local_effect','confidence_set',
        'treated_trajectory','treated_block_att','structural_parameter','equilibrium',
        'welfare','allocation','price_bounds','sensitivity','density_discontinuity','power',
        'qte','qtt','local_qte','tail_effect','potential_quantile','tail_mean','potential_mean',
        'conditional_iv_effect','aclate','multi_arm_cate','multi_arm_ate','survival_effect',
        'counterfactual_distribution','conditional_quantile',
        'marginal_effect','average_marginal_effect','prediction','probability','prediction_contrast',
        'log_hazard_ratio','hazard_ratio','mean_decomposition','bunching_mass','elasticity',
        'att_d','acrt_d','acrt','event_time_acrt','identified_set','exposure_contrast','treatment_vector_effect'}
    extension_methods = {**INFERENCE_METHODS, **CAUSAL_EXTENSIONS}
    allowed_targets |= {target for entry in extension_methods.values() for target in entry['targets']}
    allowed_targets |= {target for entry in OFFICIAL_PROJECT_IMPLEMENTATIONS.values() for target in entry['targets']}
    if target_kind is not None and target_kind not in allowed_targets:
        raise ValueError(f'target.kind must be one of {sorted(allowed_targets)}')
    if any(not isinstance(s.get('options', {}), dict) for s in (request, adopted_spec)):
        raise ValueError('selection and adopted specification options must be objects')
    adopted = request.get('adopted_method', adopted_spec.get('method', adopted_spec.get('model')))
    if adopted is not None and (not isinstance(adopted, str) or not adopted.strip()):
        raise ValueError('adopted_method must be a nonempty string')
    stored_method = adopted_spec.get('method', adopted_spec.get('model'))
    if stored_method and adopted and stored_method != adopted:
        raise ValueError('adopted_method must match adopted_specification')
    def scientific_contract(s):
        fields = {k:s[k] for k in contract_fields if k in s}
        o = s.get('options', {})
        definitions = o.get('definitions', {})
        if not isinstance(definitions, dict):
            raise ValueError('options.definitions must be an object')
        for key in contract_fields:
            if key not in fields and key in definitions:
                fields[key] = definitions[key]
        for key in ('population','weights'):
            if key not in fields and key in s.get('target',{}):
                fields[key] = s['target'][key]
        for group in ('args','columns'):
            if not isinstance(o.get(group, {}), dict):
                raise ValueError('native args and columns must be objects')
        if 'comparison_group' not in fields:
            control_group = o.get('control_group', o.get('args', {}).get('control_group'))
            if control_group is not None:
                fields['comparison_group'] = control_group
        if 'weights' not in fields:
            weights = {k:o[k] for k in ('weightsname','fix_weights','weights','weights_type') if k in o}
            for group in ('args','columns'):
                selected = {k:v for k,v in o.get(group, {}).items() if k in ('weights','i.weights','sample.weights','weight','weightsname','wts')}
                if selected: weights[group] = selected
            if weights: fields['weights'] = weights
        return fields
    adopted_contract = scientific_contract(adopted_spec)
    proposed_contract = scientific_contract({**adopted_spec, **request})
    for key in ('population','weights'):
        if key not in request and key in request.get('target',{}):
            proposed_contract[key] = request['target'][key]
    forward_options = request.get('options', adopted_spec.get('options', {}))
    requested_inference = proposed_contract.get('inference', {})
    if not isinstance(requested_inference, dict):
        raise ValueError('inference must be a structured object')
    level = comparison.get('confidence_level', requested_inference.get('confidence_level'))
    requested_alpha = requested_inference.get('alpha')
    for key, value in (('confidence_level', level), ('alpha', requested_alpha)):
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value < 1):
            raise ValueError(f'inference {key} must lie strictly between zero and one')
    if level is not None and requested_alpha is not None and abs(level + requested_alpha - 1) > 1e-12:
        raise ValueError('confidence_level and inference.alpha must agree')
    if level is None and requested_alpha is not None:
        level = 1 - requested_alpha
    interval_type = comparison.get('interval_type', comparison.get('ci_kind',
        requested_inference.get('interval_type', requested_inference.get('ci_kind'))))
    cluster_columns = requested_inference.get('clusters', requested_inference.get('cluster'))
    if isinstance(cluster_columns, str):
        cluster_columns = [cluster_columns]
    if cluster_columns is not None and (not isinstance(cluster_columns, list) or not cluster_columns or
            any(not isinstance(column, str) or not column.strip() for column in cluster_columns) or
            len(set(cluster_columns)) != len(cluster_columns)):
        raise ValueError('inference.cluster/clusters must name distinct analysis columns')
    design = request['design']; structure = request['data_structure']; pattern = request['treatment_pattern']
    mechanism = facts.get('assignment_mechanism')
    if design == 'auto':
        mechanisms = {'randomized':'rct','parallel_trends':'did','threshold':'rdd',
            'instrument':'iv','selection_on_observables':'orthogonal_score',
            'conditional_mean':'conditional_mean','donor_panel':'synthetic_control',
            'structural_equilibrium':'structural','network_randomized':'network_interference',
            'partial_identification':'partial_identification',
            'shock_instrument':'shift_share_inference','spatial_dependence':'spatial_conley',
            'mediation':'mediation','specification_family':'specification_curve',
            'posterior_model':'bayesian_model'}
        if mechanism not in mechanisms:
            raise ValueError('design=auto requires conditions.assignment_mechanism: ' + ', '.join(mechanisms))
        design = mechanisms[mechanism]
        if mechanism in ('randomized','selection_on_observables'):
            if target_kind in ('cate','multi_arm_cate','multi_arm_ate','survival_effect'): design = 'heterogeneous_effect'
            if target_kind == 'policy_value': design = 'policy_learning'
            if target_kind in ('qte','qtt','counterfactual_distribution'): design = 'quantile_effect'
        if mechanism == 'instrument' and target_kind in ('conditional_iv_effect','aclate'):
            design = 'heterogeneous_effect'
        if mechanism == 'parallel_trends' and target_kind in ('qtt','counterfactual_distribution'):
            distribution_design = facts.get('distribution_identification')
            if distribution_design not in ('quantile_parallel_trends','changes_in_changes'):
                raise ValueError('distributional DID requires quantile_parallel_trends or changes_in_changes identification')
            design = 'quantile_did' if distribution_design == 'quantile_parallel_trends' else 'changes_in_changes'
    if design == 'did' and facts.get('estimator') == 'lp_did':
        design = 'lp_did'
    if design == 'synthetic_control' and facts.get('counterfactual_model') == 'ridge_augmented':
        design = 'augmented_synthetic_control'
    if design == 'synthetic_control' and comparison.get('diagnostics') in ('placebo','donor_sensitivity'):
        design = 'scm_diagnostics'
    if design == 'did' and (pattern in ('fixed_dose_staggered','fixed_dose_common') or
            facts.get('dose_time_invariant') is True and target_kind in
            ('att_d','acrt_d','att','acrt','event_time_att','event_time_acrt','dose_response')):
        design = 'continuous_did'
    if mechanism == 'selection_on_observables':
        if facts.get('conditional_exchangeability') is False or facts.get('overlap') is False:
            raise ValueError('selection on observables requires conditional exchangeability and overlap in the target population')
    for name, value in (('data_structure',structure),('treatment_pattern',pattern),
                        ('outcome_scale',request['outcome_scale'])):
        if name in facts and facts[name] != value:
            raise ValueError(f'conditions.{name} must match the explicit {name}')
    if model_contract is not None:
        if contract_binding is None:
            return {'result_format_version':1, 'status':'implementation_required',
                'question':request['question'], 'estimand':request['estimand'],
                'identification':request['identification'], 'method':None, 'engine':None, 'entry_point':None,
                'design_contract':proposed_contract, 'adopted_specification':adopted_spec,
                'method_selection':{'model_contract':model_contract, 'knowledge_plan':knowledge_plan,
                    'compatibility':{'status':model_contract['selection_status'],
                        'reason':'This contract has no binding to the existing method selector.',
                        'selected_method':None},
                    'official_implementation':{'execution_mode':'none', 'execution_specification':None}},
                'executed':False}
        if design != contract_binding['design']:
            raise ValueError(f'{contract_id} requires design={contract_binding["design"]}; received {design}')
    owner = 'skills/econ-data/scripts/research_causal.py run'
    conditions = []
    required_inputs = []
    alternatives = []
    required_native_options = {}
    external_implementation = None
    native_function = None
    computation = None
    numerical_kernel = None
    model = None
    algorithm = None
    respy_simulation = False
    balanced_rct = False
    method_quantity = request['estimand']
    score = facts.get('score', request.get('score'))
    if 'score' in facts and 'score' in request and facts['score'] != request['score']:
        raise ValueError('conditions.score must match score')
    if request.get('implementation') == 'doubleml' and design in ('sample_selection','quantile_effect'):
        selected_family = 'ssm' if design == 'sample_selection' else 'qte'
        if score not in (None, selected_family):
            raise ValueError('The selected DoubleML family must match the requested design')
        design, score = 'orthogonal_score', selected_family
    project_implementation = None
    selected_profile = None
    if design == 'bayesian_model' and forward_options.get('engine') in OFFICIAL_PROJECT_IMPLEMENTATIONS:
        selected_profile = forward_options['engine']
        project_implementation = OFFICIAL_PROJECT_IMPLEMENTATIONS[forward_options['engine']]
        if project_implementation['design'] != design:
            raise ValueError('options.engine must select a Bayesian implementation')
    elif design in OFFICIAL_PROJECT_DEFAULTS:
        default_profile = OFFICIAL_PROJECT_IMPLEMENTATIONS[OFFICIAL_PROJECT_DEFAULTS[design]]
        bound_profile = contract_binding.get('implementation') if contract_binding else None
        selected_profile = request.get('implementation', bound_profile or default_profile.get('implementation', OFFICIAL_PROJECT_DEFAULTS[design]))
        if bound_profile is not None and selected_profile != bound_profile:
            raise ValueError(f'{contract_id} requires implementation={bound_profile}')
        project_implementation = next((entry for key,entry in OFFICIAL_PROJECT_IMPLEMENTATIONS.items()
            if entry['design'] == design and entry.get('implementation',key) == selected_profile), None)
        if project_implementation is None:
            raise ValueError(f'No official project implementation {selected_profile} for design={design}')
    extension_contract = None if project_implementation else extension_methods.get(design)
    if project_implementation is not None:
        method = design
        native_function = project_implementation['function']
        owner = 'existing project script using ' + native_function
        conditions = project_implementation['conditions']
        required_inputs = project_implementation['inputs'] + ['options.stage: existing research argv stage with project script, inputs and outputs']
        external_implementation = deepcopy(project_implementation)
    elif extension_contract is not None:
        method = design
        native_function = extension_contract['engine']
        conditions = [extension_contract['conditions']]
        required_inputs = ['data and the adopted scientific/sample contract'] + [
            'options.'+field for field in extension_contract['required_options']]
        if method == 'sensitivity_cinelli' and forward_options.get('input','data') == 'data':
            required_inputs = ['data','options.treatment']
        if method == 'shift_share_inference' and facts.get('identification_basis') is not None:
            required_native_options['identification_basis'] = facts['identification_basis']
        if cluster_columns and method in INFERENCE_METHODS:
            if method not in ('romano_wolf','specification_curve','shift_share_inference') or len(cluster_columns) != 1:
                raise ValueError('this inference method requires its documented spatial, classical or single-cluster contract')
            required_native_options['cluster'] = cluster_columns[0]
        if isinstance(proposed_contract.get('weights'),str):
            required_native_options['weights'] = proposed_contract['weights']
        for condition in ('conditional_exchangeability','overlap'):
            if method in ('metalearner','tmle','mediation') and facts.get(condition) is False:
                raise ValueError(f'{method} requires {condition}')
        if method == 'lp_did' and facts.get('parallel_trends') is False:
            raise ValueError('LP-DiD requires its conditional parallel-trends restriction')
    elif design in ('survival','oaxaca','bunching'):
        method = design
        if proposed_contract.get('weights') is not None:
            raise ValueError(f'{method} native interface has no sampling-weight argument')
        if method == 'survival':
            conditions = ['proportional hazards within the adopted strata',
                'conditionally independent right censoring and left truncation',
                'the declared covariates and risk sets identify the log hazard ratios']
            required_inputs = ['duration outcome','binary event-status column','regressors without an intercept',
                'entry, strata and offset columns when adopted','Breslow or Efron tie handling']
            method_quantity = 'conditional hazard ratio exp(beta)' if target_kind == 'hazard_ratio' else 'log conditional hazard ratio beta'
            required_native_options['effect_scale'] = 'hazard_ratio' if target_kind == 'hazard_ratio' else 'log_hazard'
            if level is not None:
                required_native_options['confidence_level'] = level
            if interval_type not in (None,'pointwise'):
                raise ValueError('PHReg supplies pointwise coefficient intervals')
            if cluster_columns and len(cluster_columns) != 1:
                raise ValueError('PHReg.fit groups requires one independent cluster partition')
        elif method == 'oaxaca':
            conditions = ['two explicitly ordered groups and full-rank group-specific linear projections',
                'the selected two-fold reference coefficients or three-fold second-group reference',
                'independent observations for the native row bootstrap']
            required_inputs = ['outcome and regressors','group column and ordered labels',
                'two-fold or three-fold decomposition','native bootstrap repetitions, retained fraction and seed']
            method_quantity = 'first-group minus second-group outcome mean, decomposed using the adopted reference coefficients'
            if level is not None or interval_type not in (None,'none'):
                raise ValueError('OaxacaBlinder returns bootstrap component standard deviations; its conf argument trims bootstrap draws and is not an interval level')
        else:
            conditions = ['a kink in the declared marginal tax schedule',
                'a smooth polynomial counterfactual density over the adopted window and excluded bins',
                'residual-bootstrap inference conditional on binning, window and polynomial choices']
            required_inputs = ['unbinned outcome values','kink location, bin width and window',
                'polynomial and exclusion bins','tax rates below and above the kink','bootstrap seed']
            method_quantity = 'bunching-implied elasticity' if target_kind == 'elasticity' else 'excess mass divided by mean counterfactual bin count'
            required_native_options['quantity'] = 'e' if target_kind == 'elasticity' else 'b'
            if forward_options.get('args',{}).get('notch') is True:
                raise ValueError('bunching 0.8.6 runner adopts the kink contract; its notch bootstrap omits notch/alpha in marginal_buncher')
            if level is not None or interval_type not in (None,'none'):
                raise ValueError('bunchit supplies residual-bootstrap standard deviations; this route saves no constructed confidence interval')
        if method in ('oaxaca','bunching') and (request['dependence'] in ('cluster','clustered') or cluster_columns):
            raise ValueError(f'{method} native bootstrap has no cluster-resampling argument')
    elif design == 'post_estimation':
        method = 'marginaleffects'
        function = forward_options.get('function')
        if function is not None and function not in MARGINAL_FUNCTIONS:
            raise ValueError('marginaleffects function must be slopes, predictions, comparisons or their avg_ variants')
        conditions = ['saved native model and its original estimation data',
            'adopted evaluation population, scale, contrast and averaging weights',
            'the model covariance and requested delta-method reference']
        required_inputs = ['saved native fitted-result JSON','official post-estimation function',
            'evaluation data or saved estimation sample','variables, contrasts, weights and inference options']
        method_quantity = request['estimand']
        if level is not None:
            required_native_options['args.conf_level'] = level
        if cluster_columns:
            required_native_options['args.vcov'] = '~' + '+'.join(cluster_columns)
        evaluation_weights = proposed_contract.get('weights')
        if isinstance(evaluation_weights,str):
            required_native_options['args.wts'] = evaluation_weights
        if function is not None:
            target_functions = {'marginal_effect':{'slopes'},'average_marginal_effect':{'avg_slopes'},
                'prediction':{'predictions','avg_predictions'},'probability':{'predictions','avg_predictions'},
                'prediction_contrast':{'comparisons','avg_comparisons'}}
            if target_kind in target_functions and function not in target_functions[target_kind]:
                raise ValueError('the post-estimation function must calculate the requested target')
        if target_kind == 'probability':
            required_native_options['args.type'] = 'response'
        if interval_type not in (None,'pointwise'):
            raise ValueError('the saved marginaleffects route returns the official pointwise intervals')
    elif design in ('quantile_effect','quantile_did','changes_in_changes'):
        if design == 'quantile_effect':
            if target_kind == 'counterfactual_distribution':
                raise ValueError('unc_qte exposes a quantile-grid ECDF; a counterfactual_distribution target requires the distribution-identified qdid/cic route')
            if target_kind not in ('qte','qtt'):
                raise ValueError('quantile_effect requires a marginal QTE or QTT target')
            method = target_kind
            if facts.get('conditional_exchangeability') is False or facts.get('overlap') is False:
                raise ValueError('marginal QTE/QTT requires conditional exchangeability and overlap')
            conditions = ['binary treatment and marginal potential-outcome distributions',
                'conditional exchangeability and target-population overlap',
                'the selected IPW, outcome-regression or AIPW identifying nuisance conditions']
            required_inputs = ['outcome, treatment and pretreatment covariates','quantile grid','sampling weights and target population']
        else:
            method = design
            conditions = ['no anticipation','stable comparison-group composition and outcome support',
                'quantile parallel trends at the adopted ranks' if method == 'quantile_did' else
                'strictly increasing common outcome transformation and time-invariant latent rank distribution within groups']
            required_inputs = ['outcome, unit, time and first-treatment cohort columns',
                'eligible comparison group and anticipation','marginal-distribution aggregation population','quantile grid']
            required_native_options['args.panel'] = structure == 'panel'
        if request['dependence'] in ('cluster','clustered') or cluster_columns:
            raise ValueError('these qte calls bootstrap independent observations or panel units; they expose no higher-level cluster argument')
        method_quantity = ('Q_Y(1)(tau)-Q_Y(0)(tau)' if method == 'qte' else
            'Q_Y(1)|treated(tau)-Q_Y(0)|treated(tau)')
        if target_kind == 'counterfactual_distribution':
            method_quantity = 'marginal potential-outcome CDFs F_Y(0)(y) and F_Y(1)(y) in the adopted target population'
        if isinstance(proposed_contract.get('weights'),str):
            required_native_options['args.weightsname'] = proposed_contract['weights']
        if level is not None:
            required_native_options['args.alp'] = 1-level
        if interval_type not in (None,'pointwise','simultaneous','joint'):
            raise ValueError('quantile-effect intervals must be pointwise or simultaneous')
        simultaneous = interval_type in ('simultaneous','joint')
        if method in ('qte','qtt') and (simultaneous or forward_options.get('args',{}).get('cband') is True):
            raise ValueError('qte 2.0.0 unc_qte returns pointwise intervals; simultaneous bands are available from qdid/cic')
        if interval_type is not None or method in ('qte','qtt'):
            required_native_options['args.cband'] = simultaneous
        alternatives = [{'method':'quantile','difference':'conditional outcome quantile regression',
            'estimand':'Q_tau(Y|X)=X beta_tau',
            'conditions':['correct conditional quantile specification'],
            'data_fit':{'required':['outcome and conditional regressors']},
            'inference':{'procedure':'official robust kernel covariance'}}]
    elif design == 'conditional_quantile':
        method = 'quantile'
        method_quantity = 'conditional outcome quantile slope in Q_tau(Y|X)=X beta_tau'
        conditions = ['correct conditional quantile specification','independent observations for the robust kernel covariance']
        required_inputs = ['outcome, regressors and options.quantile']
        if request['dependence'] in ('cluster','clustered') or cluster_columns:
            raise ValueError('the conditional-quantile runner implements independent-observation robust kernel covariance')
        if level not in (None,.95) or interval_type not in (None,'pointwise'):
            raise ValueError('the conditional-quantile runner saves official 95% pointwise intervals')
    elif design in ('rct','randomized','rct_design'):
        if facts.get('randomized') is False:
            raise ValueError('RCT requires randomized assignment')
        method = 'rct_design'
        method_quantity = 'population-weighted assignment ITT under the declared randomization and cell contrast'
        if target_kind == 'late':
            method = 'iv_gmm'
            method_quantity = 'complier effect under assignment exclusion, relevance and monotonicity'
        elif target_kind not in (None,'ate','itt','power'):
            raise ValueError('RCT assignment comparison targets ate or itt; receipt late requires the IV branch')
        conditions = ['recorded randomization probabilities and assignment units',
            'consistency and the adopted interference mapping',
            'the same randomizr declaration in assignment, design-based inference and simulation']
        required_inputs = ['roster IDs and population weights','treatment assignment and outcome columns',
            'experimental_design: conditions or factorial, blocks, clusters and allocation probabilities/counts',
            'operation: assign, analyze or diagnose; seed; named assignment-effect contrasts']
        if method == 'iv_gmm':
            conditions = ['random assignment of the instrument','assignment exclusion','nonzero receipt first stage','monotonic receipt response']
            required_inputs += ['actual treatment receipt','assignment as excluded instrument']
        else:
            experimental = forward_options.get('experimental_design',{})
            if not isinstance(experimental,dict):
                raise ValueError('experimental_design must contain the adopted assignment specification')
            balanced_rct = experimental.get('ra_type')=='balanced' or 'formula' in experimental or 'prob_unit_each' in experimental
            if balanced_rct:
                conditions += ['pretreatment balancing variables and the native cube allocation',
                    'sharp-null inference draws complete assignment vectors from the same declaration']
                required_inputs += ['balanced declaration probabilities and optional covariate formula',
                    'Monte Carlo randomization inference for analyze or diagnose']
            allowed_intervals = (None,'none','randomization') if balanced_rct else (None,'pointwise')
            if interval_type not in allowed_intervals:
                raise ValueError('The adopted RCT declaration must support its requested inference family')
            if cluster_columns:
                if len(cluster_columns) != 1:
                    raise ValueError('RCT design uses one randomized cluster partition, optionally nested in blocks')
                existing_cluster = forward_options.get('experimental_design', {}).get('clusters')
                if existing_cluster is not None and existing_cluster != cluster_columns[0]:
                    raise ValueError('RCT randomization and inference must use the same cluster column')
                required_native_options['experimental_design.clusters'] = cluster_columns[0]
            if level is not None:
                required_native_options['confidence_level'] = level
            if isinstance(proposed_contract.get('weights'), str):
                required_native_options['weights'] = proposed_contract['weights']
        alternatives = [
            {'method':'fixest_ols','difference':'covariate-adjusted assignment contrast',
             'estimand':'average assignment effect under the adopted regression adjustment and population weights',
             'conditions':['random assignment','prespecified adjustment implementing the target contrast'],
             'data_fit':{'required':['assignment, outcome and pretreatment adjustment variables']},
             'inference':{'procedure':'official linear-model covariance at the independent assignment unit'}},
            {'method':'iv_gmm','difference':'assignment instruments actual treatment receipt',
             'estimand':'receipt LATE for assignment compliers under binary assignment and receipt',
             'conditions':['assignment exclusion','instrument independence','monotonic receipt response','nonzero first stage'],
             'data_fit':{'required':['assignment instrument, actual receipt, outcome and exogenous controls']},
             'inference':{'procedure':'robust or clustered GMM covariance; weak-IV inference requires test inversion'}}]
    elif design == 'sample_selection':
        method = 'heckman'
        saved_conditions = forward_options.get('definitions',{}).get('conditions',{})
        if not isinstance(saved_conditions,dict):
            raise ValueError('Heckman definitions.conditions must be an object')
        selection_conditions = {**saved_conditions, **facts}
        if selection_conditions.get('outcome_support') != 'continuous':
            raise ValueError('Heckman selection requires conditions.outcome_support=continuous')
        for restriction in ('joint_gaussian_errors','exclusion','iid'):
            if selection_conditions.get(restriction) is not True:
                raise ValueError(f'Heckman selection requires conditions.{restriction}=true')
        if request['dependence'] != 'independent' or cluster_columns or proposed_contract.get('weights') is not None:
            raise ValueError('Heckman selection uses the adopted unweighted iid covariance')
        if requested_inference.get('type') not in (None,'official','iid','homoskedastic'):
            raise ValueError('Heckman selection uses official iid inference')
        if interval_type not in (None,'pointwise'):
            raise ValueError('Heckman selection supplies pointwise Student-t Wald intervals')
        selection_regressors = forward_options.get('selection_regressors')
        outcome_regressors = request.get('regressors',adopted_spec.get('regressors',[]))
        if not isinstance(forward_options.get('selection'),str) or not forward_options['selection'].strip():
            raise ValueError('Heckman selection must name the binary selection column')
        if (not isinstance(selection_regressors,list) or not selection_regressors
                or any(not isinstance(column,str) or not column for column in selection_regressors)
                or len(set(selection_regressors)) != len(selection_regressors)):
            raise ValueError('selection_regressors must name distinct observed selection covariates')
        if not set(selection_regressors)-set(outcome_regressors):
            raise ValueError('Heckman selection requires an explicit selection regressor excluded from the outcome equation')
        estimation_method = forward_options.get('estimation_method','2step')
        if estimation_method not in ('2step','ml'):
            raise ValueError('Heckman estimation_method must be 2step or ml')
        if forward_options.get('args') or forward_options.get('columns'):
            raise ValueError('Heckman equations and iid inference are bound through their named options')
        conditions = ['continuous latent outcome observed only when selection equals one',
            'joint Gaussian selection and outcome errors with unit selection-error variance',
            'selection-equation covariates excluded from the outcome equation',
            'independent identically distributed unweighted observations']
        required_inputs = ['binary selection column','outcome and selection covariates',
            'explicit excluded selection covariates','observed outcomes for selected rows']
        method_quantity = 'continuous latent-outcome equation coefficients under the adopted selection model'
        required_native_options = {'estimation_method':estimation_method,
            'definitions.conditions':selection_conditions,
            'confidence_level':level if level is not None else forward_options.get('confidence_level',.95)}
    elif design == 'conditional_mean':
        if target_kind == 'count_distribution' or facts.get('conditional_distribution') == 'nb2':
            if facts.get('conditional_distribution') != 'nb2':
                raise ValueError('count-distribution selection requires conditions.conditional_distribution=nb2')
            method = 'negative_binomial_r'
            method_quantity = 'NB2 likelihood coefficient with E[Y|X]=exp(X beta) and Var(Y|X)=mu+alpha*mu^2'
        elif request['outcome_scale'] == 'level':
            implementation_choice = request.get('implementation')
            if implementation_choice is None and adopted is None:
                import shutil
                python_ready = importlib.util.find_spec('pyfixest') is not None
                r_ready = shutil.which('Rscript') is not None
                if available_languages is not None:
                    python_ready = 'python' in available_languages
                    r_ready = 'r' in available_languages
                python_options = {'fixed_effects','weights','weights_type','ssc','vcov','confidence_level'}
                if (python_ready and not r_ready and forward_options.get('fixed_effects') and
                        set(forward_options) <= python_options and len(cluster_columns or []) <= 1):
                    implementation_choice = 'pyfixest'
            performance = execution_context.get('performance', {})
            if implementation_choice is None and adopted is None and isinstance(performance,dict):
                if performance.get('preferred_implementation') == 'FixedEffectModels.jl':
                    if not all(performance.get(field) for field in ('data_sha256','specification_sha256','observed_seconds','precision')):
                        raise ValueError('Julia performance selection requires actual input/specification hashes, elapsed seconds and precision')
                    implementation_choice = 'FixedEffectModels.jl'
            method = ('fixed_effects_julia' if implementation_choice == 'FixedEffectModels.jl' or adopted == 'fixed_effects_julia'
                else 'hdfe' if implementation_choice == 'pyfixest' or adopted == 'hdfe' else 'fixest_ols')
            method_quantity = 'weighted additive conditional-mean or linear-projection coefficient in outcome units'
        elif request['outcome_scale'] == 'proportional_nonnegative': method = 'fixest_ppml'
        else: raise ValueError('conditional_mean requires level or proportional_nonnegative outcome_scale')
        conditions = ['adopted conditional mean', 'fixed effects and weights from the target population', 'covariance matched to dependence']
        if method == 'fixest_ppml':
            method_quantity = 'log-mean coefficient beta in E[Y|X,FE]=exp(X beta+FE+offset)'
        required_inputs = ['outcome scale and support','regressors and fixed effects','sampling or analytic weights','exposure/offset when a rate is targeted']
        alternatives = [
            {'method':'fixest_ols','difference':'additive outcome-unit contrast',
             'estimand':'weighted linear projection or additive conditional-mean coefficient',
             'conditions':['specified projection population or additive conditional mean','full-rank residual variation'],
             'data_fit':{'required':['numeric outcomes, regressors, fixed effects and adopted weights'], 'outcome_scales':['level']},
             'inference':{'procedure':'adopted fixest covariance and small-sample convention'}},
            {'method':'fixest_ppml','difference':'exponential conditional mean with observed zeros retained',
             'estimand':'beta in E[Y|X,FE]=exp(X beta+FE+offset)',
             'conditions':['exponential conditional mean','exogenous regressors','identified nonseparated coefficients'],
             'data_fit':{'required':['nonnegative outcomes and positive exposure for a log offset'], 'outcome_scales':['proportional_nonnegative']},
             'inference':{'procedure':'heteroskedastic or cluster covariance for the PPML score'}},
            {'method':'negative_binomial_r','difference':'NB2 count likelihood jointly estimates dispersion',
             'estimand':'log-mean coefficients and alpha in Var(Y|X)=mu+alpha*mu^2',
             'conditions':['adopted NB2 conditional distribution','specified unconditional group heterogeneity'],
             'data_fit':{'required':['nonnegative integer counts and an identified likelihood design'], 'conditional_distribution':'nb2'},
             'inference':{'procedure':'MASS likelihood coefficient covariance and official dispersion standard error'}}]
    elif design == 'continuous_did':
        method = 'continuous_did'
        native = forward_options.get('args', {})
        if structure != 'panel' or facts.get('balanced_panel') is False:
            raise ValueError('contdid 0.1.2 requires an adopted balanced panel')
        if request['dependence'] not in ('independent','cluster','clustered') or facts.get('independent_units') is False:
            raise ValueError('contdid 0.1.2 inference requires independent panel entities')
        if pattern not in ('fixed_dose_staggered','fixed_dose_common','absorbing_staggered','two_period'):
            raise ValueError('contdid requires fixed dose with common or staggered absorbing adoption; changing doses use their treatment-path estimator')
        if facts.get('dose_time_invariant') is False:
            raise ValueError('contdid requires the same unit dose in every period, including pretreatment periods')
        if facts.get('parallel_trends') is False:
            raise ValueError('continuous DID requires the adopted untreated parallel-trend restriction')
        if facts.get('covariate_adjustment') or request.get('regressors', adopted_spec.get('regressors', [])):
            raise ValueError('contdid 0.1.2 supports the unconditional design; covariate-adjusted continuous DID requires its adopted official estimator')
        if not isinstance(native.get('xformula', '~1'), str) or native.get('xformula', '~1').replace(' ', '') != '~1':
            raise ValueError('contdid 0.1.2 requires xformula=~1')
        if native.get('allow_unbalanced_panel', False) or native.get('panel', True) is False:
            raise ValueError('contdid 0.1.2 requires balanced panel observations')
        if native.get('treatment_type', 'continuous') != 'continuous':
            raise ValueError('contdid 0.1.2 implements continuous treatment')
        if native.get('est_method') is not None:
            raise ValueError('contdid 0.1.2 requires est_method=null')
        if native.get('control_group', 'notyettreated') != 'notyettreated' or proposed_contract.get('comparison_group', 'notyettreated') != 'notyettreated':
            raise ValueError('contdid 0.1.2 does not forward control_group; the executed comparison is notyettreated')
        if native.get('base_period', 'varying') != 'varying' or facts.get('base_period', 'varying') != 'varying':
            raise ValueError('contdid 0.1.2 executes the varying base period')
        if native.get('bstrap', True) is not True:
            raise ValueError('contdid 0.1.2 does not forward bstrap=false; inference uses the official multiplier calculation')
        if proposed_contract.get('weights') is not None or native.get('weightsname') is not None:
            raise ValueError('the contdid 0.1.2 execution contract requires unweighted observations')
        if facts.get('anticipation', 0) != 0 or native.get('anticipation', 0) != 0:
            raise ValueError('the contdid 0.1.2 execution contract requires zero anticipation')
        target_map = {'att_d':('level','dose'), 'acrt_d':('slope','dose'),
            'att':('level','dose'), 'acrt':('slope','dose'),
            'event_time_att':('level','eventstudy'), 'event_time_acrt':('slope','eventstudy')}
        if target_kind == 'dose_response':
            parameter = native.get('target_parameter')
            if parameter not in ('level','slope'):
                raise ValueError('dose_response requires target_parameter=level for ATT(d) or slope for ACRT(d)')
            aggregation = 'dose'
        elif target_kind in target_map:
            parameter, aggregation = target_map[target_kind]
        else:
            raise ValueError('continuous_did requires att_d, acrt_d, att, acrt, event_time_att, event_time_acrt or an explicit dose_response target')
        if native.get('aggregation', aggregation) not in ('dose','eventstudy'):
            raise ValueError('contdid 0.1.2 supports dose or eventstudy aggregation')
        if parameter == 'slope' and facts.get('strong_parallel_trends') is not True:
            raise ValueError('ACRT requires an explicitly adopted strong_parallel_trends restriction across doses')
        if aggregation == 'dose' and target_kind not in ('att','acrt') and pattern not in ('fixed_dose_common','two_period'):
            if facts.get('dose_cohort_independence') is not True and comparison.get('aggregation') != 'fixed_cohort_weights':
                raise ValueError('The contdid dose curve uses fixed ever-treated cohort weights; declare dose_cohort_independence=true for the natural dose population or adopt comparison.aggregation=fixed_cohort_weights')
        dose_method = native.get('dose_est_method', 'parametric')
        if dose_method not in ('parametric','cck'):
            raise ValueError('contdid dose_est_method must be parametric or cck')
        if native.get('boot_type', 'multiplier') != 'multiplier':
            raise ValueError('contdid 0.1.2 dose inference executes the multiplier bootstrap')
        if dose_method == 'cck' and (aggregation != 'dose' or pattern not in ('fixed_dose_common','two_period')
                or facts.get('num_time_periods') != 2):
            raise ValueError('contdid cck requires dose aggregation, two periods and common treatment timing')
        if dose_method == 'cck':
            if native.get('dvals') is not None or native.get('degree', 3) != 3 or native.get('num_knots', 0) != 0:
                raise ValueError('contdid 0.1.2 CCK evaluates observed treated doses with native degree 3 and automatic knots')
            if native.get('alp', .05) != .05 or level is not None and abs(level-.95) > 1e-12:
                raise ValueError('contdid 0.1.2 CCK calls npiv at its fixed 95% confidence level')
            if native.get('cband', True) is not True or interval_type not in (None,'simultaneous'):
                raise ValueError('contdid 0.1.2 CCK preserves its native simultaneous confidence bands')
            required_native_options['args.cband'] = True
        if cluster_columns and len(cluster_columns) != 1:
            raise ValueError('contdid 0.1.2 supports one independent cluster partition')
        native_clusters = native.get('clustervars')
        if native_clusters is not None and not isinstance(native_clusters, (str, list)):
            raise ValueError('clustervars must name one analysis column')
        if isinstance(native_clusters, list) and len(native_clusters) != 1:
            raise ValueError('contdid 0.1.2 supports one independent cluster partition')
        for declared in (cluster_columns, [native_clusters] if isinstance(native_clusters, str) else native_clusters):
            if declared and declared != [forward_options.get('entity')]:
                raise ValueError('contdid 0.1.2 does not forward external clustervars; inference uses independent panel entities')
        required_native_options.update({'args.target_parameter':parameter,
            'args.aggregation':aggregation, 'args.treatment_type':'continuous',
            'quantity':'overall' if target_kind in ('att','acrt') else 'curve',
            'definitions.parallel_trends_type':'strong' if facts.get('strong_parallel_trends') is True else 'standard',
            'definitions.dose_time_invariant':True,
            'definitions.dose_aggregation':'fixed_cohort_weights'})
        if facts.get('dose_cohort_independence') is True:
            required_native_options['definitions.dose_cohort_independence'] = True
        if cluster_columns:
            required_native_options['args.clustervars'] = cluster_columns
        if level is not None:
            required_native_options['args.alp'] = 1-level
        if interval_type is not None:
            if interval_type not in ('pointwise','simultaneous'):
                raise ValueError('contdid intervals must be pointwise or simultaneous')
            required_native_options['args.cband'] = interval_type == 'simultaneous'
            if interval_type == 'simultaneous':
                required_native_options['args.bstrap'] = True
        if proposed_contract.get('comparison_group') in ('nevertreated','notyettreated','eventuallytreated'):
            required_native_options['args.control_group'] = proposed_contract['comparison_group']
        if 'base_period' in facts:
            required_native_options['args.base_period'] = facts['base_period']
        method_quantity = ('ATT(d)=E[Y_t(d)-Y_t(0)|D=d]' if parameter == 'level' else
            'ACRT(d)=E[partial Y_t(d)/partial d|D=d] under strong parallel trends')
        if aggregation == 'dose' and target_kind not in ('att','acrt'):
            method_quantity += '; native curve weights: P(G=g|ever treated)/(number of post-treatment periods for g)'
        if aggregation == 'eventstudy':
            method_quantity = ('event-time ATT averaged across eligible cohorts and their doses' if parameter == 'level' else
                'event-time ACRT averaged across eligible cohorts and their doses')
        elif target_kind in ('att','acrt'):
            method_quantity = 'overall ' + target_kind.upper() + ' under the official treated-dose and cohort-period aggregation'
        conditions = ['balanced unit-period panel with absorbing treatment adoption',
            'fixed unit dose retained in every pretreatment and post-treatment period',
            'zero anticipation and adopted untreated comparison eligibility',
            'SPT-MP: within each cohort, potential-outcome changes at every fixed dose agree across dose groups, with untreated parallel trends' if parameter == 'slope' else
                'standard untreated parallel trends for dose-specific level effects',
            'correct adopted B-spline specification' if dose_method == 'parametric' else
                'official CCK nonparametric dose conditions in the two-period common-adoption design']
        required_inputs = ['entity, time, first-treatment cohort (never-treated=0), fixed dose and outcome',
            'outcome and dose units','eligible untreated comparisons and target population',
            'adopted dose grid or event-time aggregation','official inference settings and seed']
        alternatives = [{'method':'did_multiplegt_dyn',
            'difference':'effects of changing treatment histories relative to maintaining the baseline dose',
            'estimand':'switcher path effect or normalized current and lagged dose effects',
            'conditions':['baseline-dose-specific parallel trends','no anticipation','eligible not-yet-switching controls'],
            'data_fit':{'required':['complete observed treatment paths and their baseline-dose comparison support'],
                'data_structures':['panel'], 'treatment_patterns':['changing_dose','reversals','treatment_histories']},
            'inference':{'procedure':'official treatment-path inference with adopted switcher and cluster populations'}}]
    elif design == 'did' and pattern == 'multiple_two_period':
        if structure != 'panel' or facts.get('balanced_panel') is False or facts.get('additive_effects') is not True:
            raise ValueError('multiple two-period DID requires a balanced panel and explicitly adopted additive effects')
        if facts.get('parallel_trends') is False or facts.get('anticipation', 0) != 0:
            raise ValueError('multiple two-period DID requires conditional parallel trends and zero anticipation')
        if cluster_columns and len(cluster_columns) != 1:
            raise ValueError('multiple two-period DID supports one independent cluster partition')
        if request['dependence'] not in ('independent','cluster','clustered') or facts.get('independent_units') is False:
            raise ValueError('multiple two-period DID requires independent units or the declared independent clusters')
        if proposed_contract.get('weights') is not None:
            raise ValueError('multiple two-period DID uses the existing unweighted first-difference regression')
        if interval_type not in (None,'pointwise') or level is not None and abs(level-.95) > 1e-12:
            raise ValueError('multiple two-period DID uses its existing 95% pointwise covariance contract')
        method = 'multitreatment_did'
        method_quantity = 'additive first-difference effect of each simultaneous intervention, conditional on the other adopted interventions'
        conditions = ['two-period balanced panel','joint treatment support including untreated units',
            'conditional parallel trends for the intervention vector','no anticipation',
            'additive treatment responses and pretreatment controls']
        required_inputs = ['entity, time, pre and post periods','at least two post-period treatment columns with zero pretreatment exposure',
            'pretreatment covariates','independent units or one cluster partition']
    elif design == 'did':
        if facts.get('parallel_trends') is False:
            raise ValueError('DID requires the adopted parallel-trend restriction; use saved-event-study sensitivity for a bounded departure')
        estimator = facts.get('estimator', 'group_time')
        if pattern == 'absorbing_staggered':
            candidates = {'group_time':'staggered_did','cohort_interaction':'sunab',
                'imputation':'did_imputation','two_stage':'did2s','fixes':'fixes_event_study'}
            if estimator not in candidates:
                raise ValueError('absorbing DID estimator must be group_time, cohort_interaction, imputation, two_stage or fixes')
            method = candidates[estimator]
            if method == 'fixes_event_study':
                required_inputs.append('explicit fixes estimator and its supported nuisance/weight/cluster contract')
            method_quantity = 'ATT(g,t)=E[Y_t(g)-Y_t(0)|G=g], aggregated over the adopted cohorts and event times'
        elif pattern in ('reversals','changing_dose','treatment_histories','continuous'):
            if target_kind == 'dose_response' and facts.get('effect_normalization') != 'per_unit_dose':
                raise ValueError('dose_response requires the adopted per_unit_dose normalization and dose-response restrictions')
            method = 'nonabs_did' if estimator == 'nonabsdid' else 'did_multiplegt_dyn'
            if estimator not in ('group_time','switcher','nonabsdid'):
                raise ValueError('changing treatment histories require switcher or nonabsdid estimator conditions')
            method_quantity = ('weighted current and lagged per-unit dose effects' if facts.get('effect_normalization') == 'per_unit_dose'
                else 'switcher effect of the realized treatment path relative to maintaining the baseline dose')
            normalized = facts.get('effect_normalization') == 'per_unit_dose'
            if method == 'nonabs_did' and normalized:
                required_native_options['estimator'] = 'DCDH'
            if method == 'did_multiplegt_dyn' or normalized or forward_options.get('estimator') == 'DCDH':
                required_native_options['args.normalized'] = normalized
        elif pattern == 'two_period':
            if structure == 'panel': method = 'drdid_panel'
            elif structure == 'repeated_cross_section': method = 'drdid_rc'
            else: raise ValueError('two-period DID requires panel or repeated_cross_section data_structure')
            if score not in (None,'dr','doubly_robust'):
                raise ValueError('the two-period runner implements the doubly robust score; preserve an adopted OR/IPW score in its official implementation')
            method_quantity = 'E[Y_post(1)-Y_post(0)|D=1] under conditional parallel trends'
            if (request['dependence'] in ('cluster','clustered') or interval_type == 'simultaneous' or
                    (level is not None and abs(level - .95) > 1e-12)):
                method = 'staggered_did'
        else: raise ValueError('DID treatment_pattern must identify two_period, absorbing_staggered, reversals, changing_dose or treatment_histories')
        conditions = ['specified untreated-trend scale and comparison eligibility', 'adopted anticipation and reference period', 'cohort or switcher population and horizon weights', 'assignment-matched clustering and interval family']
        required_inputs = ['entity and time','cohort or complete treatment history','eligible control population',
            'anticipation periods','outcome and pretreatment covariates','event window and base period',
            'aggregation weights and population at each horizon']
        if pattern == 'two_period' and method == 'staggered_did':
            required_inputs.append('common adoption cohort and native inference settings for the adopted two-period score')
        alternatives = [
            {'method':'drdid_panel','difference':'one treated-group pre/post contrast using paired outcomes',
             'estimand':'two-period ATT with treated-population sampling weights',
             'conditions':['conditional parallel trends','no anticipation','overlap','correct propensity or untreated-outcome nuisance model'],
             'data_fit':{'required':['paired pre/post outcomes and pretreatment covariates'], 'data_structures':['panel'], 'treatment_patterns':['two_period'], 'dependence':['independent','iid','heteroskedastic','robust']},
             'inference':{'procedure':'official DRDID influence-function or bootstrap inference for independent sampled units'}},
            {'method':'drdid_rc','difference':'period-specific outcomes from stationary repeated cross sections',
             'estimand':'two-period ATT for the stable treated population',
             'conditions':['conditional parallel trends','no anticipation','overlap','stationary sampling composition','adopted doubly robust nuisance conditions'],
             'data_fit':{'required':['pre/post cross sections, treatment-group membership and period covariates'], 'data_structures':['repeated_cross_section'], 'treatment_patterns':['two_period'], 'dependence':['independent','iid','heteroskedastic','robust']},
             'inference':{'procedure':'official repeated-cross-section influence-function or bootstrap inference'}},
            {'method':'staggered_did','difference':'group-time comparisons and target-specific aggregation',
             'estimand':'ATT(g,t), aggregated using the adopted cohort/event/calendar weights',
             'conditions':['conditional parallel trends against eligible never-treated or not-yet-treated units','no anticipation beyond the adopted window','comparison overlap'],
             'data_fit':{'required':['cohort, time, unit and comparison eligibility'], 'data_structures':['panel','repeated_cross_section'], 'treatment_patterns':['absorbing_staggered','two_period']},
             'inference':{'procedure':'official influence functions or multiplier bootstrap with adopted clustering and simultaneous family'}},
            {'method':'sunab','difference':'cohort-interacted regression with designated reference cohorts',
             'estimand':'cohort-event ATT combined with the fitted sample cohort shares',
             'conditions':['parallel untreated trends for the designated reference cohorts','absorbing adoption','adopted anticipation and covariate restriction'],
             'data_fit':{'required':['cohort-period interactions, reference cohorts, fixed effects and horizon support'], 'data_structures':['panel'], 'treatment_patterns':['absorbing_staggered','two_period']},
             'inference':{'procedure':'fixest fitted covariance and covariance-aware cohort aggregation'}},
            {'method':'did_imputation','difference':'fit the untreated outcome model before imputing treated outcomes',
             'estimand':'weighted average of treated-minus-imputed outcomes at the adopted horizons',
             'conditions':['specified untreated conditional mean','no anticipation','untreated observations identify each imputed component'],
             'data_fit':{'required':['unit-period panel and untreated support for the first-stage design'], 'data_structures':['panel'], 'treatment_patterns':['absorbing_staggered','two_period']},
             'inference':{'procedure':'official imputation standard errors at the adopted cluster level; pretrend regression has a separate target'}},
            {'method':'did2s','difference':'untreated-sample residualization followed by the adopted treatment regression',
             'estimand':'second-stage treatment coefficients under the adopted residualization and weighting',
             'conditions':['specified untreated outcome model','no anticipation','identified first-stage fixed effects and covariates'],
             'data_fit':{'required':['unit-period panel, treatment status and explicit first/second-stage formulas'], 'data_structures':['panel'], 'treatment_patterns':['absorbing_staggered','two_period']},
             'inference':{'procedure':'official clustered variance correction for first-stage estimation'}},
            {'method':'did_multiplegt_dyn','difference':'switcher comparisons preserve the observed treatment history',
             'estimand':'effect of the realized path relative to its baseline dose, or normalized weighted current/lagged dose effects',
             'conditions':['baseline-dose-specific parallel trends','no anticipation','eligible not-yet-switching comparisons','adopted continuous-dose trend restriction'],
             'data_fit':{'required':['complete group treatment histories, shared baseline-dose support and horizon-specific switchers'], 'data_structures':['panel'], 'treatment_patterns':['absorbing_staggered','two_period','reversals','changing_dose','treatment_histories','continuous']},
             'inference':{'procedure':'official horizon-specific covariance or bootstrap with the adopted cluster and switcher population'}}]
        anticipation = facts.get('anticipation', forward_options.get('anticipation',0))
        if isinstance(anticipation,bool) or not isinstance(anticipation,int) or anticipation < 0:
            raise ValueError('anticipation must be a nonnegative number of periods')
        if anticipation and method in ('sunab','did_imputation','did2s'):
            required_inputs.append('explicit announcement/exposure coding implementing the adopted anticipation window')
        if pattern in ('continuous','changing_dose'):
            conditions.append('baseline-dose-specific trends and the adopted restriction across continuous baseline doses')
    elif design == 'rdd':
        if facts.get('continuity') is False:
            raise ValueError('local-polynomial RD requires the adopted continuity restrictions; a local-randomization design needs its own assignment conditions')
        method = 'rdrobust_r'; conditions = ['cutoff and running-variable support', 'sharp, fuzzy or derivative target', 'adopted bandwidth, bias correction and dependence']
        fuzzy = facts.get('discontinuity', 'sharp') == 'fuzzy'
        if facts.get('discontinuity','sharp') not in ('sharp','fuzzy'):
            raise ValueError('conditions.discontinuity must be sharp or fuzzy')
        method_quantity = ('local complier effect: outcome discontinuity divided by treatment-receipt discontinuity' if fuzzy
            else 'lim E[Y|X=c+] - lim E[Y|X=c-] at the assignment cutoff')
        if fuzzy: conditions += ['nonzero treatment jump','exclusion and local monotonicity']
        if fuzzy and 'fuzzy' in forward_options.get('columns', {}):
            required_native_options['columns.fuzzy'] = forward_options['columns']['fuzzy']
        required_inputs = ['running variable','cutoff','outcome','bandwidth and polynomial orders','treatment receipt for fuzzy RD']
        alternatives = [{'method':'rdd_localrand','difference':'assignment-based comparison within a fixed window',
            'estimand':'average assignment contrast in the adopted local-randomization window',
            'conditions':['complete randomization conditional on arm counts within the window','consistency and the adopted interference mapping'],
            'data_fit':{'required':['prespecified window, binary assignment and outcome observations']},
            'inference':{'procedure':'sharp-null permutation test and separate HC1 average-contrast interval'}}]
    elif design == 'density_at_cutoff':
        method = 'rddensity'; conditions = ['adopted cutoff', 'running-variable measurement and mass points']
    elif design == 'rd_power':
        method = 'rdpower'; conditions = ['adopted alternative effect, sample size and bandwidth', 'same RD estimator and dependence as the research design']
    elif design in ('iv','instrumental_variables'):
        method = 'iv_ar' if facts.get('weak_instruments') or target_kind == 'confidence_set' else 'iv_gmm'
        conditions = ['specified endogenous regressors and excluded instruments', 'instrument exclusion and rank identify the adopted moment coefficient', 'robust or adopted cluster covariance and the same moment weighting']
        method_quantity = 'linear IV moment coefficient estimated by two-step GMM'
        if method == 'iv_gmm' and (request.get('implementation') == 'FixedEffectModels.jl' or adopted == 'fixed_effects_julia'):
            method = 'fixed_effects_julia'
            method_quantity = 'linear IV coefficient estimated by official FixedEffectModels two-stage least squares'
            conditions = ['adopted linear IV model, instrument exclusion and rank',
                'same fixed effects, analytic weights and independent inference units',
                'official two-stage least squares in CPU Float64']
        if method == 'iv_ar':
            if facts.get('homoskedastic_normal_errors') is not True or request['dependence'] in ('cluster','clustered','heteroskedastic','robust'):
                method = 'iv_ar_robust'
            conditions = ['one endogenous regressor','instrument exclusion',
                'independent homoskedastic normal errors with fixed instruments' if method=='iv_ar' else 'independent observations or the adopted independent clusters',
                'inversion of the adopted Anderson-Rubin test']
            method_quantity = 'Anderson-Rubin confidence set for the endogenous-regressor coefficient'
        required_inputs = ['endogenous regressors','excluded instruments','exogenous controls','moment weighting','independent inference unit']
        alternatives = [
            {'method':'iv_gmm','difference':'point estimation and conventional GMM covariance',
             'estimand':'coefficient identified by the adopted linear IV moments',
             'conditions':['instrument exclusion and exogeneity','rank condition for conventional inference'],
             'data_fit':{'required':['endogenous regressors, excluded instruments and exogenous controls']},
             'inference':{'procedure':'two-step robust or cluster GMM covariance'}},
            {'method':'iv_ar','difference':'exact F-test inversion under the adopted disturbance model',
             'estimand':'Anderson-Rubin confidence set for one endogenous-regressor coefficient',
             'conditions':['valid excluded instruments','independent homoskedastic normal errors and fixed instruments'],
             'data_fit':{'required':['one endogenous regressor, excluded instruments and exogenous controls'], 'dependence':['independent','iid','homoskedastic']},
             'inference':{'procedure':'analytic F inversion retaining disconnected, empty and unbounded sets'}},
            {'method':'iv_ar_robust','difference':'robust or clustered Anderson-Rubin test inversion',
             'estimand':'Anderson-Rubin confidence set for one endogenous-regressor coefficient',
             'conditions':['valid excluded instruments','independent observations or independent clusters'],
             'data_fit':{'required':['one endogenous regressor, instruments, controls and any adopted cluster/weight columns']},
             'inference':{'procedure':'official ivDiag::AR_test confidence-set inversion'}}]
    elif design == 'weak_instrument_inference':
        method = ('iv_ar' if facts.get('homoskedastic_normal_errors') is True and request['dependence'] not in ('cluster','clustered','heteroskedastic','robust') else 'iv_ar_robust')
        conditions = ['one endogenous regressor and the adopted excluded instruments',
            'independent homoskedastic normal errors with fixed instruments' if method=='iv_ar' else 'independent observations or the adopted independent clusters',
            'adopted alpha and inversion of the Anderson-Rubin test']
        method_quantity = 'Anderson-Rubin confidence set for the specified endogenous-regressor coefficient'
    elif design == 'synthetic_control':
        method = 'synthdid' if facts.get('counterfactual_model') == 'synthetic_did' or target_kind == 'treated_block_att' else 'synthetic_control'
        if facts.get('counterfactual_model') == 'interactive_fixed_effects': method = 'generalized_synth'
        conditions = ['one treated unit and at least two balanced eligible donors', 'adopted training, untreated validation and post-treatment periods', 'nonnegative donor weights summing to one and held-out gap inference']
        method_quantity = 'post-treatment treated-minus-synthetic gap relative to its held-out untreated validation mean'
        if method == 'synthdid':
            if facts.get('common_treatment_block') is False:
                raise ValueError('synthdid requires a common treated block')
            method_quantity = 'average treatment effect over the common treated unit-time block'
            conditions = ['balanced outcome panel with a common treatment block','eligible untreated donor units','unit and time weights selected by synthdid','adopted bootstrap, jackknife or placebo inference']
        elif method == 'generalized_synth':
            method_quantity = 'treated-block average relative to the interactive fixed-effects counterfactual'
            conditions = ['stable factor counterfactual','identified factor rank and untreated support','adopted gsynth bootstrap']
        required_inputs = ['treated units','eligible donors','pre/post periods','balanced outcome panel','target aggregation and inference method']
        alternatives = [
            {'method':'synthetic_control','difference':'convex donor combination learned on pretreatment outcomes',
             'estimand':'post-treatment gap relative to its held-out untreated validation mean',
             'conditions':['eligible untreated donors','stable expected untreated gaps','independent held-out time errors for the implemented covariance'],
             'data_fit':{'required':['one treated unit, balanced donors and distinct training/validation/post periods'], 'data_structures':['panel']},
             'inference':{'procedure':'HC1 covariance across held-out time gaps conditional on trained donor weights'}},
            {'method':'synthdid','difference':'joint unit and time weighting for a common treatment block',
             'estimand':'average effect over the adopted treated unit-time block',
             'conditions':['common treatment block','eligible untreated donor panel','identified weighted counterfactual'],
             'data_fit':{'required':['balanced unit-period outcomes and common treatment timing'], 'data_structures':['panel']},
             'inference':{'procedure':'official bootstrap, jackknife or placebo variance chosen for the adopted assignment model'}},
            {'method':'generalized_synth','difference':'interactive fixed-effects untreated counterfactual',
             'estimand':'treated-block average and event-time effects relative to the fitted factor counterfactual',
             'conditions':['stable factor structure','identified rank and untreated support','adopted error model'],
             'data_fit':{'required':['balanced panel, never-treated units and at least five pretreatment periods'], 'data_structures':['panel']},
             'inference':{'procedure':'seeded official parametric bootstrap'}}]
    elif design == 'generalized_synth':
        method = 'generalized_synth'
        conditions = ['balanced panel with never-treated controls and one common absorbing adoption date', 'adopted factor rank and two-way interactive-effects specification', 'parametric bootstrap under the adopted error model']
        method_quantity = 'treated-block average and event-time effects relative to the interactive fixed-effects counterfactual'
    elif design == 'network_interference':
        if target_kind != 'exposure_contrast':
            raise ValueError('network_interference requires the adopted exposure_contrast target')
        if structure != 'cross_section':
            raise ValueError('network exposure requires one outcome observation per assignment unit')
        if facts.get('randomized') is False or facts.get('assignment_design', 'bernoulli') != 'bernoulli':
            raise ValueError('the implemented network exposure inference requires independent Bernoulli assignment')
        if cluster_columns or request['dependence'] not in ('network','local_interference'):
            raise ValueError('network exposure uses its adopted local-dependence HAC covariance')
        if proposed_contract.get('weights') is not None:
            raise ValueError('network exposure weighting is determined by the adopted exposure probabilities')
        if interval_type not in (None,'pointwise'):
            raise ValueError('StatsPAI network exposure returns pointwise normal-reference contrast intervals')
        method = 'network_exposure'
        method_quantity = 'finite-population average contrast between the adopted exposure states in the eligible population'
        conditions = ['known independent Bernoulli treatment probabilities',
            'adopted exposure mapping and adjacency determine potential-outcome exposure',
            'every target exposure has positive probability for each eligible unit',
            'local network dependence supports the official PSD HAC covariance']
        required_inputs = ['outcome and assignment by unit ID','directed adjacency in the outcome-to-neighbor orientation',
            'known assignment probability','exposure mapping and contrast pairs','adopted min_prob and eligible population']
    elif design == 'partial_identification':
        selected_bound = facts.get('estimator')
        bound_methods = {'manski':'manski_bounds','lee':'lee_bounds','balke_pearl':'balke_pearl'}
        if selected_bound not in bound_methods:
            raise ValueError('partial_identification requires conditions.estimator=manski, lee or balke_pearl')
        if target_kind != 'identified_set' or structure != 'cross_section':
            raise ValueError('partial identification requires an identified_set target and cross-sectional units')
        if (cluster_columns or request['dependence'] != 'independent' or facts.get('independent_units') is False
                or proposed_contract.get('weights') is not None):
            raise ValueError('the implemented bounds use independent unweighted observations')
        method = bound_methods[selected_bound]
        if method != 'balke_pearl' and interval_type not in (None,'pointwise'):
            raise ValueError('the implemented bounds preserve their native single-parameter confidence-region procedure')
        if method == 'manski_bounds':
            method_quantity = 'identified ATE interval under the adopted population outcome support and shape restrictions'
            conditions = ['declared population outcome support','consistency',
                'adopted MTR and/or MTS restrictions when selected']
            required_inputs = ['outcome and binary treatment','population y_lower and y_upper',
                'assumption, bootstrap repetitions and seed']
        elif method == 'lee_bounds':
            if facts.get('randomized') is False:
                raise ValueError('Lee bounds require the adopted randomized or conditionally independent treatment design')
            method_quantity = 'identified treatment-effect interval for the always-observed population'
            conditions = ['randomized treatment or conditional independence in adopted pretreatment cells',
                'selection monotonicity in the adopted common direction','exact fractional trimming at outcome ties']
            required_inputs = ['outcome, binary treatment and observation indicator',
                'all assigned units in the retention denominators','monotonicity direction, bootstrap repetitions and seed']
        else:
            if facts.get('exclusion') is False:
                raise ValueError('Balke-Pearl bounds require instrument exclusion')
            if level is not None or interval_type not in (None,'none'):
                raise ValueError('the official Balke-Pearl function returns identified-set endpoints without sampling intervals')
            method_quantity = 'identified binary-outcome ATE interval under instrument independence and exclusion'
            conditions = ['binary outcome, treatment and instrument','instrument independence and exclusion',
                'both instrument arms observed','explicit adopted treatment monotonicity direction when imposed']
            required_inputs = ['binary outcome, treatment and instrument','monotonicity=none, increasing or decreasing']
    elif design == 'orthogonal_score':
        if score is None:
            score = ({'ate':'irm','att':'irm','late':'iivm','qte':'qte','local_qte':'qte',
                'tail_effect':'qte','potential_quantile':'pq','tail_mean':'cvar',
                'potential_mean':'apo'}.get(target_kind, 'plr'))
        method = 'dml_' + score
        if method not in DML_METHODS:
            raise ValueError('score must select a registered DoubleML model: '+', '.join(k[4:] for k in DML_METHODS))
        if score in ('plr','irm','ssm','pq','cvar','apo') and facts.get('conditional_exchangeability') is False:
            raise ValueError('The selected treatment score requires conditional treatment exchangeability')
        if score in ('irm','ssm','qte','pq','cvar','apo') and facts.get('overlap') is False:
            raise ValueError('The selected score requires overlap in its target population')
        conditions = ['score identifies the stated target', 'folds preserve independent sampling units',
            'nuisance fitting and tuning use training folds']
        method_quantity = {'plr':'partially linear structural slope with residual-treatment weighting',
            'did':'two-period ATT under the adopted DoubleML DID score',
            'irm':'E[Y(1)-Y(0)|D=1]' if target_kind=='att' else 'E[Y(1)-Y(0)]',
            'pliv':'partially linear instrumental-variable moment coefficient',
            'iivm':'local average treatment effect among instrument compliers',
            'ssm':'population E[Y(1)-Y(0)] with outcomes observed under the adopted selection mechanism',
            'qte':'potential-outcome quantile or upper-tail contrast at the selected quantiles',
            'pq':'quantile of the potential-outcome distribution Y(d)',
            'cvar':'upper-tail expectation E[Y(d) | Y(d) >= Q_tau(Y(d))]',
            'apo':'average potential outcome E[Y(d)] at the declared treatment level'}[score]
        if score == 'plr' and (target_kind in ('att','late','cate','policy_value') or
                (target_kind == 'ate' and facts.get('effect_heterogeneity') != 'constant')):
            raise ValueError('PLR targets its partially linear slope; choose a score identifying the requested target')
        required_inputs = ['mathematical score','outcome/treatment/covariates',
            'fold assignment at independent units','nuisance learner and training-only tuning']
        default_score = {'irm':'ATTE' if target_kind=='att' else 'ATE','iivm':'LATE',
            'did':'observational','ssm':'missing-at-random',
            'qte':'LPQ' if target_kind=='local_qte' else 'CVaR' if target_kind=='tail_effect' else 'PQ',
            'pq':'PQ','cvar':'CVaR','apo':'APO'}.get(score,'partialling out')
        selected_score = (default_score if score in ('irm','iivm') else forward_options.get('score',default_score))
        allowed_scores = {'plr':('partialling out','IV-type'),'pliv':('partialling out','IV-type'),
            'did':('observational','experimental'),'ssm':('missing-at-random','nonignorable'),
            'qte':('PQ','LPQ','CVaR'),'pq':('PQ',),'cvar':('CVaR',),'apo':('APO',),
            'irm':('ATE','ATTE'),'iivm':('LATE',)}
        if selected_score not in allowed_scores[score]:
            raise ValueError(f'{method} requires score in {allowed_scores[score]}')
        if score=='qte' and selected_score!='LPQ' and facts.get('conditional_exchangeability') is False:
            raise ValueError('The potential-outcome contrast requires conditional treatment exchangeability')
        if score=='qte' and selected_score=='LPQ' and (facts.get('exclusion') is False or facts.get('monotonicity') is False):
            raise ValueError('Local quantile effects require instrument exclusion and monotonicity')
        if score == 'did':
            conditions += ['two-period panel with pretreatment covariates',
                'no anticipation and conditional parallel trends', 'treatment-group overlap']
            if selected_score == 'experimental':
                conditions += ['treatment independent of pretreatment covariates']
            required_inputs += ['pretreatment and post-treatment outcomes for each unit']
        if score == 'ssm':
            conditions += (['treatment exchangeability given pretreatment X',
                'selection exchangeability given treatment and X', 'treatment and selection positivity']
                if selected_score == 'missing-at-random' else
                ['excluded selection instrument Z with conditional independence from outcome and scalar latent selection rank',
                 'threshold selection, selection overlap and conditional effect homogeneity'])
            required_inputs += ['binary selection indicator; retain unselected rows with unobserved outcomes']
            if selected_score == 'nonignorable': required_inputs += ['excluded selection instruments','regression ml_g learner']
        if score in ('qte','pq','cvar'):
            conditions += ['continuous potential-outcome distribution with positive density at selected quantiles',
                'independent observations for the native nested sample splits']
            conditions += (['binary instrument independence, exclusion, monotonicity and complier overlap']
                if score=='qte' and selected_score=='LPQ' else
                ['conditional treatment exchangeability and treatment overlap'])
            if score=='cvar' or selected_score=='CVaR': conditions += ['integrable upper potential-outcome tail']
        if score == 'apo': conditions += ['conditional treatment exchangeability and overlap at the selected treatment level']
        required_native_options['score'] = selected_score
        for key in ('quantile','quantiles','treatment_level'):
            if key in target: required_native_options[key] = target[key]
        if score == 'irm' and target_kind == 'att' and forward_options.get('weights') is not None:
            raise ValueError('DoubleMLIRM weights implements a weighted ATE and is incompatible with score=ATTE')
        if score in ('pliv','iivm'):
            conditions += ['valid excluded instruments and the specified instrument score']
            required_inputs += ['instrument columns and instrument/treatment support']
        alternatives = [
            {'method':'dml_irm','difference':'interactive-regression score for the specified treatment population',
             'estimand':'ATE or ATT selected by the official ATE/ATTE score',
             'conditions':['conditional exchangeability','overlap','orthogonal-score nuisance rate conditions'],
             'data_fit':{'required':['binary treatment, outcome, covariates and independent scoring folds']},
             'inference':{'procedure':'official cross-fitted score inference with the adopted independent units'}},
            {'method':'dml_iivm','difference':'instrument score identifies the complier population',
             'estimand':'LATE for binary-instrument compliers',
             'conditions':['instrument independence and exclusion','monotonicity','nonzero first stage','instrument overlap'],
             'data_fit':{'required':['binary treatment and instrument, outcome, covariates and independent scoring folds']},
             'inference':{'procedure':'official cross-fitted instrumental score inference; weak-IV sets require their own procedure'}}]
    elif design == 'heterogeneous_effect':
        implementation = request.get('implementation', 'grf')
        if implementation not in GRF_METHODS | {'econml'}:
            raise ValueError('heterogeneous_effect implementation must name a registered GRF method or econml')
        method = 'causal_forest' if implementation == 'econml' else implementation
        target_method = {'conditional_iv_effect':'grf_instrumental','aclate':'grf_instrumental',
            'multi_arm_cate':'grf_multi_arm','multi_arm_ate':'grf_multi_arm',
            'survival_effect':'grf_survival'}.get(target_kind)
        if target_method:
            if implementation not in ('grf',target_method):
                raise ValueError('The forest implementation must identify the requested effect target')
            method = target_method
        conditional_target = target_kind in ('cate','conditional_iv_effect','multi_arm_cate')
        if method in GRF_METHODS:
            required_native_options['quantity'] = ('conditional' if conditional_target else 'average' if target_kind in ('ate','att','aclate','multi_arm_ate') else
                target.get('quantity',forward_options.get('quantity','average')))
            if required_native_options['quantity'] not in ('conditional','average'):
                raise ValueError('The forest target quantity must be conditional or average')
        method_quantity = 'conditional treatment effects and their adopted target-population aggregate'
        conditions = ['adopted effect covariates, independent sampling units and averaging population',
            'honest forest splitting and the selected native nuisance and covariance conditions']
        required_inputs = ['effect covariates','treatment support','outcome',
            'honesty and independent sampling units','target aggregation weights']
        if method == 'grf_instrumental':
            method_quantity = ('conditional instrument covariance ratio Cov(Y,Z|X)/Cov(W,Z|X)'
                if conditional_target else 'average conditional local treatment effect under the declared binary instrument')
            conditions += ['instrument relevance, conditional exclusion and independence',
                'binary treatment/instrument and monotonicity for the declared conditional LATE interpretation']
            required_inputs += ['options.instrument','definitions.iv_estimand: conditional_late or conditional_iv_ratio']
            if target_kind == 'aclate':
                required_native_options['definitions.iv_estimand'] = 'conditional_late'
            if facts.get('exclusion') is False:
                raise ValueError('The instrumental forest requires the adopted exclusion restriction')
        else:
            if facts.get('conditional_exchangeability') is False or facts.get('overlap') is False:
                raise ValueError('The selected treatment forest requires conditional exchangeability and overlap')
            conditions += ['conditional treatment exchangeability and overlap']
            if method == 'grf_multi_arm':
                method_quantity = 'arm-specific potential-outcome contrasts against the first declared baseline arm'
                required_inputs += ['ordered options.arms with baseline first']
            elif method == 'grf_survival':
                method_quantity = 'restricted-mean survival-time or survival-probability effect, or the native continuous-treatment slope, at the adopted horizon'
                conditions += ['conditionally independent censoring and censoring positivity through the horizon']
                required_inputs += ['declared treatment support','status: observed-event column','args.target','args.horizon',
                    'definitions.time_unit','definitions.censoring']
            else:
                conditions += ['binary CATE or continuous covariance-to-variance target']
        alternatives = [
            {'method':'dml_plr','difference':'partially linear slope weighted by residual treatment variation',
             'estimand':'partially linear coefficient; ATE under the explicit constant-effect restriction',
             'conditions':['partially linear conditional mean','exogenous residual treatment','cross-fitted nuisance rate conditions'],
             'data_fit':{'required':['outcome, treatment, covariates and independent scoring folds']},
             'inference':{'procedure':'official DoubleMLPLR orthogonal-score covariance'}},
            {'method':'policy_tree','difference':'learn an assignment rule and evaluate its held-out gain',
             'estimand':'policy value relative to assigning treatment zero to the evaluation population',
             'conditions':['known propensities','conditional exchangeability and overlap','independent policy training and evaluation'],
             'data_fit':{'required':['binary treatment, propensities and explicit train/evaluation partitions']},
             'inference':{'procedure':'HC1 holdout-value covariance conditional on the trained policy'}}]
    elif design == 'policy_learning':
        if facts.get('conditional_exchangeability') is False or facts.get('overlap') is False:
            raise ValueError('policy evaluation requires conditional exchangeability and overlap in its evaluation population')
        method = 'policy_tree'
        if 'policy' in forward_options:
            policy = forward_options['policy']
            if not isinstance(policy,dict):
                raise ValueError('options.policy must be an explicit policy specification')
            fixed_batch = policy.get('evaluation_target') == 'fixed_batch'
            if policy.get('constraints') and not fixed_batch:
                raise ValueError('exact allocation constraints require a fixed_batch policy target')
            if fixed_batch and (policy.get('propensity',{}).get('source')!='known'
                    or policy.get('propensity',{}).get('mechanism')!='independent_multinomial'):
                raise ValueError('fixed_batch policy inference requires known independent multinomial assignment')
            if policy.get('value_method')=='ipw' and policy.get('propensity',{}).get('source')=='estimated':
                raise ValueError('estimated-propensity policy inference requires AIPW; this IPW route uses known probabilities')
            conditions = ['declared treatment arms and baseline','conditional exchangeability, consistency and overlap',
                'training/evaluation separation at the independent unit; training-only nuisance cross-fitting',
                'correct propensity or outcome model for AIPW consistency; product-rate conditions for estimated-nuisance inference']
            conditions += (['fixed evaluation covariates and independent known randomized assignment; no interference',
                'many independent assignment units with no dominating contribution for the conditional normal reference'] if fixed_batch
                else ['independent holdout sampling and a training-fixed policy'])
            method_quantity = ('fixed-cohort policy value, baseline and net gain with a conservative conditional assignment-variance bound'
                if fixed_batch else 'holdout target-population policy value, baseline and gain with the adopted weights and clustering')
            required_inputs = ['ordered arms and baseline','known arm-probability columns or declared propensity learner',
                'separate training/evaluation partitions','effect covariates','cost unit and outcome valuation','explicit evaluation target']
        else:
            conditions = ['binary treatment and known assignment propensities', 'distinct training and evaluation samples', 'adopted effect covariates and the untreated-all baseline']
            method_quantity = 'held-out policy value gain relative to assigning treatment zero to every evaluation unit'
            required_inputs = ['known assignment propensities','separate training/evaluation partitions','effect covariates','treatment cost and capacity in the adopted objective']
        alternatives = [{'method':'grf','difference':'conditional effects preceding a separate allocation decision',
            'estimand':'binary-treatment CATE or the continuous-treatment covariance-to-variance slope',
            'conditions':['conditional exchangeability and overlap','honest estimation and the adopted nuisance restrictions'],
            'data_fit':{'required':['outcome, treatment, effect covariates and target-population weights']},
            'inference':{'procedure':'official forest prediction variance and target-population aggregation'}}]
    elif design == 'parallel_trend_sensitivity':
        method = 'honest_did'; conditions = ['saved coefficients and joint covariance', 'ordered pre/post terms with universal reference', 'adopted restriction, magnitude grid and post-treatment contrast']
    elif design == 'wild_cluster_inference':
        method = 'wild_cluster_bootstrap'; conditions = ['saved supported linear-model fit', 'adopted null, clusters, bootstrap weights and repetitions']
    elif design == 'small_cluster_inference':
        method = 'club_sandwich'; conditions = ['saved supported model fit', 'adopted CR correction, coefficient contrast and degrees-of-freedom approximation']
    elif design == 'structural' and (request.get('structural_model') == 'np_demand' or request.get('implementation') == 'NPDemand.jl'):
        method = 'np_demand'
        native_function = 'NPDemand.define_problem + NPDemand.estimate! + NPDemand.price_elasticities!'
        owner = 'external official Julia entry: NPDemand'
        method_quantity = 'shape-constrained inverse-demand sieve parameters and market-specific demand elasticities'
        conditions = ['adopted inverse-demand model, product exchangeability groups and normalization',
            'excluded price instruments identify the adopted sieve moments',
            'prices remain in index_vars; constraints and approximation order retain their economic meaning']
        required_inputs = ['canonical market/product observations and price instruments',
            'approximation_details with order, max_interaction and sieve_type',
            'exchange, index_vars, fixed effects, normalization and shape constraints',
            'adopted least-squares or quasi-Bayesian calculation and inference']
        external_implementation = {'language':'julia','function':native_function,'version':'0.1.0',
            'source':'https://github.com/jamesbrandecon/NPDemand.jl/tree/bdb124a6e29d87363ebb6eb5c2d19e613081d879',
            'inputs':required_inputs,'outputs':['native NPDProblem and fitted coefficients',
                'market_ids keyed all_elasticities and all_jacobians','adopted inference and original model diagnostics'],
            'execution':'Use the existing project Julia argv stage with Project.toml, Manifest.toml and the shared analysis path; retain the fitted NPDProblem and export named quantities from that object.'}
    elif design == 'structural':
        requested_operation = numerical.get('operation', adopted_spec.get('operation'))
        model = request.get('structural_model')
        if not model and adopted == 'finite_horizon_choice' and requested_operation in ('simulate','counterfactual'):
            model = adopted
        condition_model = {'differentiated_products':'blp','replacement':'replacement','dynamic_game':'dynamic_game',
            'quantity_competition':'cournot'}.get(facts.get('market_structure'))
        economic_object_model = {'representative_household_growth':'finite_horizon_growth',
                'household_consumption_saving':'consumption_saving',
                'stationary_incomplete_markets':'aiyagari', 'one_asset_hank':'hank_one_asset',
                'closed_city_commuting':'qse_commuting', 'open_city_commuting':'qse_open_city',
                'city_hinterland_mobility':'qse_imperfect_mobility',
                'stochastic_representative_growth':'stochastic_rbc',
                'finite_complete_information_game':'correlated_equilibrium',
                'transferable_utility_game':'tu_shapley_core',
                'interbank_liabilities':'interbank_clearing',
                'quantity_quality_effort':'multitask_incentives',
                'finite_state_claim':'state_price_bounds',
                'capacity_constrained_quantity_competition':'cournot',
                'binary_logit_moments':'binary_logit','finite_policy_sir':'finite_policy_sir',
                'queue_capacity':'queue_capacity','decision_rights':'decision_rights',
                'employment_retirement_regimes':'lifecycle_choice'}.get(facts.get('economic_object'))
        if facts.get('economic_object') == 'individual_dynamic_choice':
            # The adopted state/action domain governs estimation and welfare
            # simulation through the same model.
            economic_object_model = (model or
                (contract_binding['structural_model'] if contract_binding else None) or adopted)
            if economic_object_model not in ('finite_horizon_choice', 'lifecycle_choice', 'consumption_saving'):
                raise ValueError('individual_dynamic_choice requires the adopted structural_model or model_contract_id for its state/action domain')
        if condition_model and economic_object_model and condition_model != economic_object_model:
            raise ValueError('market_structure and economic_object identify different structural models')
        condition_model = condition_model or economic_object_model
        if model and condition_model and model != condition_model:
            raise ValueError('structural_model and declared economic conditions identify different models')
        if contract_binding:
            bound_model = contract_binding['structural_model']
            if any(value is not None and value != bound_model for value in (model, condition_model)):
                raise ValueError(f'{contract_id} binds structural_model={bound_model}; declared economic model differs')
            model = bound_model
        elif not model:
            model = condition_model
        if model in ('blp','auction','auction_fit','search','bargaining','platform','matching'):
            method = model; owner = 'skills/econ-data/scripts/research_markets.py run'
        elif model in ('replacement','latent_replacement','discrete_entry','dynamic_adoption_blp','continuous_time_entry','capacity_product_game'):
            method = model; owner = 'skills/econ-data/scripts/research_dynamic.py run'
        elif model == 'dynamic_game':
            method = model; owner = 'skills/econ-data/scripts/equity.py dynamic'
        elif model == 'cournot':
            method = model; owner = 'skills/econ-data/scripts/equity.py fit'
        elif model == 'finite_horizon_growth':
            method = model; owner = 'skills/econ-data/scripts/research_macro.py solve'
        elif model in ('aiyagari','qse_commuting','qse_open_city','qse_imperfect_mobility'):
            method = model; owner = 'skills/econ-data/scripts/research_macro_extended.py run'
        elif model == 'stochastic_rbc':
            method = model; owner = 'skills/econ-data/scripts/research_dsge.py run'
        elif model in ('correlated_equilibrium','tu_shapley_core','interbank_clearing','multitask_incentives','state_price_bounds',
                       'binary_logit','finite_policy_sir','queue_capacity','decision_rights'):
            method = model; owner = 'skills/econ-data/scripts/research_numerics.py run'
            numerical_kernel = {'interbank_clearing':'clearing_payments','binary_logit':'moment_map'}.get(model,model)
        elif model in ('finite_horizon_choice','lifecycle_choice','consumption_saving','hank_one_asset','dolo_yaml'):
            method = model
        else:
            raise ValueError('structural_model must name a documented market, dynamic, macro, finite-game, clearing, multitask, state-price or declared Dolo model')
        conditions = ['adopted primitives, timing, moments and excluded variation', 'normalizations and equilibrium selection', 'counterfactual re-solves affected endogenous choices']
        method_quantity = ('identified utility/cost parameters and scenario-specific equilibrium prices, choices and welfare' if model == 'blp'
            else 'identified payoff/transition parameters and the re-solved policy or equilibrium under the adopted intervention')
        respy_simulation = model == 'finite_horizon_choice' and requested_operation in ('simulate','counterfactual')
        ssj_operations = ('solve_steady_state','solve_jacobian','solve_impulse_linear','solve_impulse_nonlinear')
        ssj_operation = (requested_operation or 'solve_steady_state') if model == 'hank_one_asset' else None
        if ssj_operation is not None and ssj_operation not in ssj_operations:
            raise ValueError(f'hank_one_asset requires numerical.operation in {ssj_operations}')
        algorithms = {'blp':('gmm',), 'replacement':('nfxp','ccp','smm','mpec'),
            'latent_replacement':('em',),'discrete_entry':('moment_inequalities','npl','epl','slc'),
            'dynamic_adoption_blp':('share_inversion',),'continuous_time_entry':('nfxp',),
            'capacity_product_game':('nfxp',),'dynamic_game':('nfxp','mpec'),
            'auction_fit':('maximum_likelihood',),'auction':('equilibrium',),
            'search':('equilibrium',),'bargaining':('equilibrium',),
            'platform':('equilibrium',),'matching':('deferred_acceptance',),
            'finite_horizon_choice':('backward_induction',) if respy_simulation else ('smm','maximum_likelihood'),
            'lifecycle_choice':('backward_induction',),
            'finite_horizon_growth':('slsqp',),'consumption_saving':('backward_induction',),
            'aiyagari':('policy_iteration_brentq',),'hank_one_asset':(ssj_operation,),
            'qse_commuting':('trust_region_least_squares',),'qse_open_city':('trust_region_least_squares',),
            'qse_imperfect_mobility':('trust_region_least_squares',),
            'stochastic_rbc':('time_iteration','linearized_euler') if request.get('implementation') == 'dolo' else ('linearized_euler','time_iteration'),
            'dolo_yaml':('time_iteration',), 'correlated_equilibrium':('linear_program',),
            'tu_shapley_core':('exact_enumeration',), 'interbank_clearing':('greatest_fixed_point',),
            'multitask_incentives':('kkt',), 'state_price_bounds':('linear_program',),
            'binary_logit':('analytic_moments',),'finite_policy_sir':('solve_ivp',),
            'queue_capacity':('closed_form',),'decision_rights':('active_set',),'cournot':('equilibrium',)}
        solution_model = model in ('finite_horizon_growth','consumption_saving','lifecycle_choice',
            'aiyagari','qse_commuting','qse_open_city','qse_imperfect_mobility','hank_one_asset','stochastic_rbc','dolo_yaml','cournot') or respy_simulation or numerical_kernel is not None
        numerical_key = 'solution_method' if solution_model else 'estimation_method'
        default_algorithm = (adopted_spec.get('estimation', {}).get('method', algorithms[model][0])
            if model == 'finite_horizon_choice' and not respy_simulation else algorithms[model][0])
        if model == 'replacement':
            default_algorithm = adopted_spec.get('options', {}).get('estimation_method', default_algorithm)
        if model == 'stochastic_rbc' and adopted_spec.get('options', {}).get('algorithm') == 'dolo_time_iteration':
            default_algorithm = 'time_iteration'
        algorithm = numerical.get(numerical_key, numerical.get('estimation_method', default_algorithm))
        if solution_model and 'solution_method' in numerical and 'estimation_method' in numerical and numerical['solution_method'] != numerical['estimation_method']:
            raise ValueError('numerical.solution_method and the legacy estimation_method must agree')
        if algorithm not in algorithms[model]:
            raise ValueError(f'{model} implements numerical.{numerical_key} in {algorithms[model]}')
        required_native_options['solution_component' if solution_model else 'estimation_component'] = algorithm
        if solution_model or model == 'finite_horizon_choice':
            if numerical_kernel is not None:
                available_operations = ['solve']
            elif model == 'hank_one_asset':
                available_operations = list(ssj_operations)
            elif model == 'qse_commuting':
                available_operations = ['invert_baseline','counterfactual']
            elif model in ('qse_open_city','qse_imperfect_mobility'):
                available_operations = ['counterfactual']
            elif respy_simulation:
                available_operations = ['simulate','counterfactual']
            elif model == 'dolo_yaml' or model == 'stochastic_rbc' and algorithm == 'time_iteration':
                available_operations = ['time_iteration','reuse_solution']
            elif model in ('finite_horizon_growth','aiyagari','stochastic_rbc','cournot'):
                available_operations = ['solve','counterfactual']
            else:
                available_operations = ['solve','simulate','counterfactual'] if solution_model else ['estimate']
            operation = requested_operation or ssj_operation or (
                'time_iteration' if model == 'dolo_yaml' or model == 'stochastic_rbc' and algorithm == 'time_iteration'
                else 'invert_baseline' if model == 'qse_commuting' else 'counterfactual' if model in ('qse_open_city','qse_imperfect_mobility')
                else 'solve' if solution_model else 'estimate')
            if operation not in available_operations:
                raise ValueError(f'{model} supports numerical.operation in {available_operations}')
            if solution_model and facts.get('parameter_status') not in (None,'fixed','calibrated','estimated'):
                raise ValueError(f'{model} requires fixed, calibrated or previously estimated parameters')
            computation = {'requested_operation':operation,'available_operations':available_operations,
                'numerical_method':algorithm,'operations_executed':[],
                'parameter_operation':'reuse fixed, calibrated or previously estimated values' if solution_model else 'estimate identified free parameters',
                'identification_target':target or {'expression':request['estimand']},
                'observation_map':economic_model.get('observed_data'),
                'identified_parameters':economic_model.get('identified_parameters')}
        if model == 'dynamic_game':
            required_native_options['estimation_method'] = algorithm
        if model == 'replacement' and algorithm == 'smm':
            required_native_options['options.smm'] = 'adopted seed, replications, initial_costs, bounds and tolerance'
        if model == 'replacement' and algorithm == 'mpec':
            owner = 'skills/econ-data/scripts/research_dynamic.py run'
            required_native_options = {'estimation_method':'mpec'}
            native_function = 'ruspy.estimation.criterion_function.get_criterion_function'
        if contract_id == 'MC-replacement-ddc' and forward_options.get('replacement_timing', 'reset_to_zero') != 'reset_to_zero':
            raise ValueError('MC-replacement-ddc fixes reset-to-zero transitions; select the explicitly adopted native replacement model without that contract')
        required_inputs = ['actors/objectives/feasible actions/information and timing','states and transition law',
            'shock distribution and payoff normalization','moments or likelihood and excluded variation',
            'parameter order and fixed/calibrated values','equilibrium selection','intervention and welfare aggregation']
        if numerical_kernel is not None:
            if forward_options:
                raise ValueError('numerical model arguments belong in adopted_specification.inputs')
            rid = 'research-numerics'
            numerical_relative = resources[rid]['source_path'] if layout_path == 'source_path' else placements[rid][layout_path]
            numerical_path = (ROOT.parent if ROOT.name == '.agents' else ROOT) / numerical_relative
            numerical_spec = importlib.util.spec_from_file_location('selected_numerical_model', numerical_path)
            numerical_module = importlib.util.module_from_spec(numerical_spec)
            numerical_spec.loader.exec_module(numerical_module)
            numerical_signature = inspect.signature(getattr(numerical_module, numerical_kernel))
            required_inputs = ['inputs.'+name for name, parameter in numerical_signature.parameters.items()
                               if parameter.default is inspect.Parameter.empty] + ['unit']
            required_native_options = {}
            if model == 'correlated_equilibrium':
                if facts.get('recommendation_timing') not in (None,'private_before_action'):
                    raise ValueError('correlated equilibrium requires private recommendations before actions')
                if facts.get('complete_information') is False:
                    raise ValueError('correlated equilibrium requires complete-information payoffs')
                method_quantity = 'joint action probabilities maximizing the supplied weighted expected payoff subject to every conditional deviation inequality'
                conditions = ['finite complete-information game with one action axis per player',
                    'each player observes only its own recommendation before choosing',
                    'supplied weights define the common-unit payoff objective and equilibrium selection']
            elif model == 'tu_shapley_core':
                if facts.get('transferable_utility') is False or facts.get('coalition_externalities') is True:
                    raise ValueError('Shapley/core requires transferable coalition values with fixed outside terms')
                method_quantity = 'exact Shapley allocation and every coalition slack for that allocation'
                conditions = ['finite transferable-utility game with empty-coalition value zero',
                    'coalition values in bit-mask order with fixed outside transaction terms',
                    'core membership evaluates the returned Shapley allocation']
            elif model == 'interbank_clearing':
                if facts.get('repayment_priority') not in (None,'equal_pro_rata'):
                    raise ValueError('interbank clearing requires equal-priority pro-rata repayment')
                if facts.get('bankruptcy_costs') not in (None,False,0):
                    raise ValueError('interbank clearing implements zero bankruptcy resource costs')
                method_quantity = 'greatest clearing payments, outside-creditor recoveries and residual bank equity'
                conditions = ['nonnegative debtor-row liabilities, zero self-liabilities and nonnegative external assets',
                    'one simultaneous clearing period with equal-priority pro-rata repayment and limited liability',
                    'greatest fixed point selected by the equivalent maximal-payment linear program',
                    'outside payments plus equity equal external assets at the adopted residual tolerance']
            elif model == 'state_price_bounds':
                if facts.get('free_trading') is False or facts.get('all_states_possible') is False:
                    raise ValueError('state-price bounds require freely traded assets and every supplied state to be possible')
                method_quantity = 'no-arbitrage claim-price bounds, endpoint inclusion and the subhedge, superhedge or replicating portfolio'
                conditions = ['finite possible states and freely traded assets with unrestricted portfolio holdings',
                    'at least one traded asset pays strictly positively in every state',
                    'existing asset prices admit strictly positive state prices',
                    'an unspanned claim has an open price interval; a replicated claim has its unique replication price']
            elif model == 'binary_logit':
                method_quantity = 'mean logit probability and regressor-weighted probability, with their parameter Jacobian'
                conditions = ['supplied intercept and slope held fixed','finite observed covariate support',
                    'logistic response probability and its analytic derivatives']
            elif model == 'finite_policy_sir':
                method_quantity = 'SIR state trajectory and integrated loss under the supplied finite policy schedule'
                conditions = ['nonnegative susceptible, infected and recovered initial states',
                    'fixed transmission and recovery rates and finite dated controls',
                    'population conservation and the supplied infection, control and terminal loss weights']
            elif model == 'queue_capacity':
                method_quantity = 'stationary M/M/1 utilization, mean system/queue length and mean system/queue waiting time'
                conditions = ['Poisson arrivals and exponential single-server service',
                    'nonnegative arrival rate and positive service rate with arrival rate below service rate']
            elif model == 'decision_rights':
                method_quantity = 'principal and agent information effort and payoffs under the specified authority holder'
                conditions = ['supplied project payoffs, effort costs and preference alignment',
                    'principal or agent holds formal authority','efforts satisfy the original best-response bounds']
            else:
                method_quantity = 'quantity and quality effort and both principal and agent payoffs at the supplied contract'
                conditions = ['fixed nonnegative salary, quantity reward and private quality benefit',
                    'nonnegative efforts and quadratic cost with absolute interaction coefficient below one',
                    'agent best response satisfies both original KKT conditions',
                    'principal values quantity and quality at the supplied coefficients']
            computation.update(parameter_operation='hold supplied model inputs fixed; estimate no parameters',
                solution_object=method_quantity,
                outputs=[row['name'] for row in model_contract['outputs']] if model_contract else [method_quantity])
        elif model == 'cournot':
            required_native_options = {}
            method_quantity = 'capacity-constrained firm quantities, market prices and profits under baseline and changed market inputs'
            conditions = ['decreasing linear inverse demand and convex variable costs',
                'nonnegative quantities within firm capacities','Nash best responses at the adopted equilibrium tolerance',
                'supplied demand coefficients or excluded cost instruments identifying aggregate quantity']
            required_inputs = ['sources','identification','market','as_of','currency','price_unit','quantity_unit',
                'inverse_demand','markets']
            computation.update(solution_object=method_quantity,
                parameter_operation='estimate inverse demand by 2SLS when observations are supplied; otherwise reuse supplied coefficients',
                outputs=['baseline and counterfactual market and firm quantities, prices, costs, profits and capacity shadow prices'])
        elif model == 'finite_horizon_growth':
            method_quantity = 'optimal finite-horizon capital and consumption paths and discounted log-consumption welfare conditional on initial and terminal capital'
            conditions = ['representative household, log utility and Cobb-Douglas production',
                'positive consumption and capital; fixed initial and terminal capital with no continuation utility',
                'deterministic productivity and output-tax paths; tax revenue finances government absorption',
                'fixed or previously estimated alpha, beta and delta; original Euler/resource residuals within tolerance']
            required_inputs = ['alpha, beta, delta, initial_capital and terminal_capital',
                'baseline and scenario, each with equal-horizon productivity and output_tax paths',
                'population, period, unit, sources and tolerance']
            computation['outputs'] = ['baseline and scenario capital, consumption, output and government_absorption paths',
                'discounted log-consumption welfare and scenario-minus-baseline welfare_change',
                'original Euler/resource residuals and analytic-derivative comparisons']
            computation['solution_object'] = 'optimal trajectories at the supplied endpoints; a feedback policy function requires the corresponding state-space model'
        elif model in ('qse_commuting','qse_open_city','qse_imperfect_mobility'):
            open_city = model == 'qse_open_city'
            imperfect_mobility = model == 'qse_imperfect_mobility'
            variable_population = open_city or imperfect_mobility
            closure = 'open' if open_city else 'imperfect_mobility' if imperfect_mobility else 'closed'
            if (facts.get('city_closure') not in (None,closure) or facts.get('fixed_population') is variable_population
                    or adopted_spec.get('closure', closure) != closure):
                raise ValueError(f'{model} requires {closure}-city population closure')
            method_quantity = ('scenario-specific population, wages, rents, residence, employment, commuting and welfare from saved urban primitives'
                if variable_population else 'inverted urban primitives and scenario-specific wages, rents, residence, employment, commuting and welfare')
            conditions = [('open city with endogenous population and expected utility fixed to the saved baseline'
                    if open_city else 'fixed regional population and city-hinterland utility log-odds migration'
                    if imperfect_mobility else 'closed city with fixed population') + ', positive location residence/employment/rent and mixed floor use',
                'Cobb-Douglas production and goods/housing consumption; Frechet location-pair choices with epsilon>1',
                'baseline employment-weighted mean wage one; common goods price one in every scenario',
                'productivity and amenity externalities evaluated at each equilibrium allocation',
                'external floor owners consume rental income; original labor, floor, population and goods equations clear']
            required_inputs = ([f'model={model}, operation=counterfactual and hash-bound saved_solution',
                'scenario productivity_hat, amenity_hat, floor_space_hat or travel_time']
                if operation == 'counterfactual' else
                ['model=qse_commuting, operation=invert_baseline and calibration_source',
                 'parameters: alpha, beta, epsilon, kappa, productivity_spillover, productivity_decay, amenity_spillover, amenity_decay',
                 'baseline: location_ids, population, employment, rent, land_area, travel_time, wage_numeraire and source'])
            if imperfect_mobility:
                required_inputs += ['migration: positive zeta, baseline_urban_share in (0,1) and calibration source; reuse saved migration when present']
                conditions += ['fixed hinterland opportunity value and iid outer location shocks with scale 1/zeta']
            required_inputs.append('optional solver tolerance and max_iterations')
            computation.update(parameter_operation=('reuse saved inverted primitives' if operation == 'counterfactual'
                    else 'recover location primitives from observed margins at the supplied structural parameters'),
                solution_object=f'{closure}-city residence-workplace equilibrium with endogenous mixed floor allocation',
                outputs=['baseline/scenario wages, rents, population, employment, commuting flows, output and floor shares',
                    ('regional welfare-index ratio and log-value change; conditional city income equivalent, migration and external floor-owner income change'
                     if imperfect_mobility else 'fixed worker expected utility, baseline-population income equivalent and migration; external floor-owner income change' if open_city else
                     'worker expected utility and baseline-income equivalent; external floor-owner income change'),
                    'original market, population and resource residuals; saved primitive and equilibrium identity'])
            required_native_options = {}
        elif model == 'aiyagari':
            if facts.get('aggregate_shocks') is True or facts.get('stationary_equilibrium') is False:
                raise ValueError('aiyagari selects stationary equilibria with a fixed aggregate productivity in each scenario')
            method_quantity = 'scenario-specific stationary capital, competitive prices, household policies, invariant distributions and stationary population welfare'
            conditions = ['unit mass of infinitely lived households; CRRA utility and inelastic Markov labor efficiency',
                'finite increasing asset grid, positive consumption and irreducible income transition',
                'competitive Cobb-Douglas production with labor aggregated from the same income distribution',
                'one recurrent class in each evaluated household-policy transition',
                'Bellman, distribution, capital and resource residuals meet the adopted tolerances']
            required_inputs = ['model=aiyagari and calibration_source',
                'parameters: alpha, beta, delta, crra, asset_grid, income_states, income_transition',
                'baseline.productivity and scenario.productivity',
                'solver: capital_bracket, capital_tolerance, bellman_tolerance, distribution_tolerance, resource_tolerance, max_iterations']
            computation.update(parameter_operation='hold the supplied calibrated primitives; estimate no parameters',
                solution_object='two stationary equilibria, each with its own household policy and invariant distribution',
                outputs=['baseline/scenario capital, output, consumption, investment, net interest rate and wage',
                    'asset and consumption policies, value and stationary distribution by asset/income state',
                    'stationary mean value and stationary consumption equivalent',
                    'original Bellman, household-budget, distribution, capital and resource diagnostics'])
            required_native_options = {}
        elif model == 'hank_one_asset':
            if facts.get('nominal_rigidity') is False:
                raise ValueError('hank_one_asset requires the declared nominal-price and general-equilibrium conditions')
            if target_kind == 'welfare' and ssj_operation in ('solve_jacobian','solve_impulse_linear'):
                raise ValueError('HANK transition welfare requires solve_impulse_nonlinear with the saved household policies and distribution')
            function = 'sequence_jacobian.blocks.block.Block.' + ssj_operation
            owner = 'skills/econ-data/scripts/research_dsge.py run'
            method_quantity = ('calibrated one-asset HANK steady state satisfying the adopted targets' if ssj_operation == 'solve_steady_state'
                else 'one-asset HANK general-equilibrium Jacobian' if ssj_operation == 'solve_jacobian'
                else 'linear one-asset HANK equilibrium impulse paths' if ssj_operation == 'solve_impulse_linear'
                else 'nonlinear one-asset HANK equilibrium transition paths')
            conditions = ['the HET-03 household, monetary, fiscal and Rotemberg-price equations with common units and timing',
                'adopted income process, asset grid, borrowing limit and distribution weights',
                'steady-state calibration targets and transition unknowns/targets kept distinct',
                'fixed initial distribution and terminal steady state over the requested horizon',
                'original household, distribution, asset, labor, goods and pricing residuals retained']
            required_inputs = ['declared model blocks and calibration; constructing the model preserves the adopted equations',
                'steady-state model unknown initial values/brackets and target values, or the saved matching SteadyStateDict',
                'transition unknowns [w,Y,pi] and targets [asset_mkt,goods_mkt,nkpc_res]',
                'inputs: shock names for solve_jacobian, or adopted rstar/Z shock arrays for impulse operations',
                'horizon, requested outputs, original residuals and household internals needed by the target']
            native_function = function
            computation['parameter_operation'] = ('calibrate the declared steady-state unknowns to the adopted targets' if ssj_operation == 'solve_steady_state'
                else 'reuse the matching steady-state parameters, policy and distribution')
            required_native_options = {}
        elif model in ('stochastic_rbc','dolo_yaml'):
            if model == 'stochastic_rbc':
                restrictions = {'utility':'log','production':'cobb_douglas',
                    'labor_supply':'fixed_unit','productivity_process':'stationary_gaussian_ar1'}
                for field, expected in restrictions.items():
                    if field in facts and facts[field] != expected:
                        raise ValueError(f'stochastic_rbc requires conditions.{field}={expected}')
            dolo_entry = model == 'dolo_yaml' or algorithm == 'time_iteration'
            if request.get('implementation') == 'dolo' and not dolo_entry:
                raise ValueError('implementation=dolo requires numerical.solution_method=time_iteration')
            conditions = (['infinite-lived household with log utility, fixed unit labor and Cobb-Douglas production',
                'stationary zero-mean Gaussian AR(1) log productivity and calibrated alpha, beta and delta',
                'positive consumption, adopted capital timing and original Euler/resource equations']
                if model == 'stochastic_rbc' else ['declared YAML state, control, shock and parameter coordinates implement the adopted economic model',
                    'transition and arbitrage equations, shock timing, constraints and normalization match the requested equilibrium'])
            if dolo_entry:
                function = ('dolo.compiler.model_import.yaml_import + dolo.algos.steady_state.find_steady_state + '
                    'dolo.algos.steady_state.residuals + dolo.algos.time_iteration.time_iteration + dolo.numeric.residuals.F')
                owner = 'skills/econ-data/scripts/research_dsge.py run'
                method_quantity = 'decision rule for the adopted dynamic model, with steady-state equations and original final-policy arbitrage residuals'
                required_inputs = ['native Dolo YAML filename with the adopted equations, calibration, state/control/shock timing and bounds',
                    'same DiscretizedModel, grids and shock-process discretization throughout solution and residual evaluation',
                    'adopted interpolation, backend, initial decision rule and convergence tolerances',
                    'final decision rule evaluated on the same grid/regimes for original residuals.F']
                required_native_options = {}
                native_function = function
                computation.update(parameter_operation='reuse the adopted calibration; estimate no parameters',
                    solution_object='dynamic decision rule of the explicitly supplied model')
            else:
                method_quantity = 'AR(1) productivity estimates, local RBC policy, conditional impulse responses, stochastic allocations and finite-horizon welfare with terminal continuation'
                required_inputs = ['parameters.alpha, beta and delta',
                    'observations: type, source, path, sha256, period_column, value_column',
                    'horizon, simulation_paths, seed and technology_shock']
                required_native_options = {}
                computation.update(parameter_operation='estimate AR(1) persistence and innovation variance; hold preferences and technology coefficients fixed',
                    solution_object='local first-order capital policy with exact resource accounting',
                    outputs=['AR(1) estimates and covariance','linearized Euler/resource coefficients and residuals',
                        'conditional impulse responses, stochastic paths and forecast moments','finite-horizon welfare with terminal continuation'])
        elif model == 'consumption_saving':
            income_process = facts.get('income_process', adopted_spec.get('income_process'))
            classes = {'perfect_foresight':'PerfForesightConsumerType','idiosyncratic_shocks':'IndShockConsumerType'}
            if income_process not in classes:
                raise ValueError('consumption_saving requires conditions.income_process=perfect_foresight or idiosyncratic_shocks')
            function = 'HARK.ConsumptionSaving.ConsIndShockModel.' + classes[income_process]
            owner = 'skills/econ-data/scripts/research_macro_extended.py run'
            method_quantity = 'age-specific consumption policies, normalized value functions and simulated asset/income paths at adopted parameters'
            conditions = ['finite lifecycle with cycles=1 and T_cycle periods plus the terminal solution',
                'CRRA utility, adopted discounting, survival, income growth, returns and borrowing constraints',
                'terminal consumption equals cash on hand in these consumer classes',
                'initial population and income/shock timing match the adopted model',
                'prices are exogenous; welfare uses declared value units, population weights and scenario contrast']
            required_inputs = ['income_process','consumer_options with cycles, T_cycle, CRRA, DiscFac, Rfree, LivPrb, PermGroFac and BoroCnstArt',
                'evaluation.mNrm with adopted periods and optional population weights','calibration_source',
                'simulation for requested histories; scenario.consumer_options for a requested counterfactual']
            if income_process == 'idiosyncratic_shocks':
                required_inputs += ['PermShkStd, TranShkStd, shock distributions, integration counts and asset grid']
            required_native_options = {'consumer_options.cycles':1}
            if income_process == 'idiosyncratic_shocks':
                required_native_options['consumer_options.vFuncBool'] = True
            computation.update(solution_object=method_quantity,
                outputs=['solve() stores T_cycle+1 ConsumerSolution objects in consumer.solution',
                    'solution[t].cFunc(mNrm) and vFunc(mNrm), with permanent-income normalization',
                    'simulate() stores each track_vars history as a (T_sim, AgentCount) array',
                    'scenario-specific values and outcomes aggregated with the adopted population weights'])
        elif respy_simulation:
            simulation_method = numerical.get('simulation_method', adopted_spec.get('simulation', {}).get('method'))
            if simulation_method not in ('n_step_ahead_with_sampling','n_step_ahead_with_data','one_step_ahead'):
                raise ValueError('respy simulation requires numerical.simulation_method=n_step_ahead_with_sampling, n_step_ahead_with_data or one_step_ahead')
            if facts.get('parameter_status') not in ('fixed','calibrated','estimated'):
                raise ValueError('respy simulation requires explicit fixed, calibrated or estimated parameter_status')
            owner = 'skills/econ-data/scripts/research_dynamic.py run'
            method_quantity = ('scenario contrast of adopted discounted chosen-flow utility for the same initial population' if target_kind == 'welfare'
                else 'scenario-specific choices, rewards and state paths from the same respy structural primitives')
            if simulation_method == 'one_step_ahead':
                if target_kind == 'welfare':
                    raise ValueError('respy lifecycle welfare requires an n-step simulation of the counterfactual state path')
                method_quantity = 'one-period choices and rewards conditional on each observed state under the adopted respy scenario'
            conditions = ['reuse the fitted respy parameter ordering, normalizations, model options and invariant primitives',
                'declare sampled initial conditions, fixed observed initial states or observed one-step states',
                'hold the adopted population, scenario draws, choice ordering and horizon comparison fixed',
                'aggregate chosen flow utility with adopted discounting, present-bias interpretation and terminal evaluation']
            required_inputs = ['params: fixed or saved estimated parameter dataframe/series with provenance',
                'options: the same structural model, decision horizon, initial distributions, solution/simulation seeds and draws',
                'numerical.simulation_method and the adopted scenario changes',
                'target population, identifiers, weights, value units and welfare aggregation']
            if simulation_method != 'n_step_ahead_with_sampling':
                required_inputs += ['df with Identifier/Period MultiIndex and the adopted state columns; initial-data simulation uses zero-based consecutive IDs at Period=0']
            required_native_options = {}
            native_function = 'respy.get_simulate_func'
            computation['outputs'] = ['saved ordered parameters and native model options',
                'Identifier/Period-indexed simulated choices, states and rewards',
                'adopted discounted chosen-flow utility and scenario contrasts']
        elif model == 'finite_horizon_choice':
            smm = algorithm == 'smm'
            function = 'respy.get_moment_errors_func' if smm else 'respy.get_log_like_func'
            owner = 'skills/econ-data/scripts/research_dynamic.py run'
            method_quantity = ('structural parameters minimizing the adopted weighted finite-horizon simulated-moment distance' if smm
                else 'structural parameters maximizing the mean log likelihood of the adopted finite-horizon observed histories')
            conditions = ['finite decision horizon, adopted terminal values and feasible state/action support',
                'payoff and shock normalizations, information timing and transition law',
                'parameter-to-moment identification' if smm else 'identified choice/wage likelihood on the adopted observed sample',
                'fixed solution and simulation draws across parameter evaluations']
            required_inputs = ['params: ordered parameter dataframe/series with free and fixed parameters, normalizations and adopted bounds',
                'options: horizon, state/choice definitions, covariates, transitions, integration and simulation settings',
                'observed population, sample selection, measurement units and target weights',
                'solution, simulation and estimation seeds and draw counts',
                'adopted optimizer and structural-parameter inference at the independent sampling unit']
            required_inputs += (['calc_moments and ordered empirical_moments with matching labels',
                'replace_nans rule, weighting_matrix and n_simulation_periods'] if smm
                else ['df: observed choice/wage histories in the official estimation-data format'])
            required_native_options = {}
            native_function = function
            computation['outputs'] = ['fitted ordered structural parameters and optimizer return',
                'official weighted moment criterion and moment errors' if smm else 'official mean log likelihood and contributions',
                'adopted parameter-inference inputs and simulation design']
        elif model == 'lifecycle_choice':
            owner = 'skills/econ-data/scripts/research_macro_extended.py run'
            method_quantity = ('target-population aggregation of lifecycle values under the adopted welfare weights and utility or monetary conversion' if target_kind == 'welfare'
                else 'lifecycle policies, values and simulated outcomes at the adopted fixed or previously estimated parameters')
            conditions = ['fixed or previously estimated structural parameters and adopted utility/shock normalizations',
                'finite horizon and terminal regimes with feasible states, actions, constraints and transition laws',
                'declared information, perceived/realized regime transitions and initial-population distribution',
                'policy scenarios hold the adopted exogenous paths fixed and re-solve affected household choices',
                'welfare aggregation uses the adopted population weights and value units']
            required_inputs = ['lcm.Model: regimes, regime_id_class, initial_nodes and edges',
                'exactly one of ages and n_periods; states, actions, state_transitions, utility functions, constraints and shocks',
                'fixed_params and params matching get_params_template(), including discounting and normalizations',
                'regime-specific official solver, grids, integration and numerical precision',
                'initial_conditions, seed and adopted taste_shock_seed or shock_paths for scenario comparisons',
                'policy intervention, exogenous price paths, target population, weights and welfare aggregation/conversion']
            required_native_options = {}
            native_function = 'lcm.Model.solve + lcm.Model.simulate'
        alternatives = [
            {'method':'nfxp','difference':'solve the Bellman/equilibrium system within each parameter evaluation',
             'estimand':'parameters of the adopted dynamic likelihood and equilibrium selection',
             'conditions':['specified payoff/shock/transition law','identified likelihood and normalization'],
             'data_fit':{'required':['observed states, actions and transitions in the model support']},
             'inference':{'procedure':'adopted likelihood curvature or refitted sampling procedure'}},
            {'method':'mpec','difference':'jointly optimize parameters and values or policies under equilibrium constraints',
             'estimand':'the same structural likelihood parameters under the imposed equilibrium equations',
             'conditions':['the adopted likelihood and normalization','original Bellman or equilibrium constraints'],
             'data_fit':{'required':['the same state/action observations and an identified constrained system']},
             'inference':{'procedure':'structural parameter inference accounting for equilibrium constraints'}},
            {'method':'ccp','difference':'use first-stage choice probabilities and transition estimates',
             'estimand':'payoff parameters identified by the adopted CCP inversion and second-stage criterion',
             'conditions':['shock distribution giving the CCP inversion','choice support and transition identification'],
             'data_fit':{'required':['supported conditional choices and transitions for each evaluated state']},
             'inference':{'procedure':'sampling procedure carrying first-stage CCP and transition estimation'}},
            {'method':'smm','difference':'match observed and simulated moments under fixed simulation draws',
             'estimand':'structural parameters identified by the adopted moment vector and weighting matrix',
             'conditions':['parameter-to-moment identification','adopted initial-state and transition law'],
             'data_fit':{'required':['ordered empirical moments and observed histories in the adopted support']},
             'inference':{'procedure':'adopted moment covariance with the specified simulation contribution'}},
            {'method':'gmm','difference':'match economically identified moments using the adopted weighting matrix',
             'estimand':'parameters satisfying the adopted population moment restrictions',
             'conditions':['moment exclusion and rank','adopted integration and normalization'],
             'data_fit':{'required':['moment observations, instruments and adopted population weights']},
             'inference':{'procedure':'moment covariance matched to the independent market or sampling unit'}},
            {'method':'maximum_likelihood','difference':'maximize the mean log likelihood of the observed finite-horizon histories',
             'estimand':'structural parameters identified by the adopted choice/wage likelihood',
             'conditions':['identified likelihood and utility/shock normalizations','adopted information, state support and transition law'],
             'data_fit':{'required':['observed choice/wage histories and their adopted sampling population']},
             'inference':{'procedure':'adopted likelihood curvature or refitted sampling procedure with the recorded integration draws'}}]
        alternatives = [candidate for candidate in alternatives
                        if candidate['method'] in algorithms[model] and candidate['method'] != algorithm]
    else:
        raise ValueError('unsupported design; use the documented selection contracts')
    if method == 'iv_ar_robust':
        required_inputs = ['data','Y: outcome column','D: one endogenous treatment column',
            'Z: excluded instrument columns','controls: exogenous control columns',
            'FE: adopted fixed effects','cl: adopted cluster columns','weights: adopted weight column','alpha']
        alpha = requested_alpha
        if level is not None:
            if isinstance(level,bool) or not isinstance(level,(int,float)) or not 0<level<1:
                raise ValueError('comparison.confidence_level must be between zero and one')
            if alpha is not None and abs(alpha-(1-level))>1e-12:
                raise ValueError('inference.alpha and comparison.confidence_level must agree')
            alpha = 1-level
        if alpha is None: alpha = forward_options.get('args',{}).get('alpha',.05)
        if isinstance(alpha,bool) or not isinstance(alpha,(int,float)) or not 0<alpha<1:
            raise ValueError('the selected AR alpha must be between zero and one')
        native_alpha = forward_options.get('args',{}).get('alpha')
        if native_alpha is not None and abs(native_alpha-alpha)>1e-12:
            raise ValueError('options.args.alpha must agree with the selected inference level')
        required_native_options = {'args.CI':True,'args.alpha':alpha}
    if method == 'fixes_event_study' and target_kind == 'att':
        method = 'fixes_att'; owner = 'external official R entry: fixes::att'
        required_native_options = {'aggregation':'simple','estimator':'adopted cs or bjs'}
        external_implementation = {'language':'R','function':'fixes::att','version':'1.0.0',
            'source':'https://github.com/yo5uke/fixes/blob/0a1e1cbba31bd344b7599273f973f9c850247c92/R/att.R',
            'inputs':['formula','data','time','timing with never-treated coded NA','unit','estimator','aggregation','comparison and anticipation'],
            'outputs':['aggregate estimates','standard errors','confidence intervals','aggregation/sample attributes'],
            'execution':'invoke the official aggregate function in project analysis; the event-study runner retains dynamic effects'}
    compatible = {
        'rct':{'ate','itt'},'rct_design':{'ate','itt','power'},'fixest_ols':{'linear_projection','conditional_mean','ate','itt'},
        'hdfe':{'linear_projection','conditional_mean'},'fixed_effects_julia':{'linear_projection','conditional_mean','structural_parameter','late'},'fixest_ppml':{'conditional_mean'},
        'negative_binomial_r':{'count_distribution','conditional_mean'},
        'heckman':{'structural_parameter','conditional_mean'},
        'staggered_did':{'att','group_time_att','event_time_att'},
        'network_exposure':{'exposure_contrast'},
        'multitreatment_did':{'treatment_vector_effect'},
        'manski_bounds':{'identified_set'},'lee_bounds':{'identified_set'},'balke_pearl':{'identified_set'},
        'continuous_did':{'att_d','acrt_d','att','acrt','event_time_att','event_time_acrt','dose_response'},
        'drdid_panel':{'att'},'drdid_rc':{'att'},'sunab':{'att','event_time_att'},
        'did2s':{'att','event_time_att'},'did_imputation':{'att','event_time_att'},
        'fixes_event_study':{'event_time_att'},'fixes_att':{'att'},
        'did_multiplegt_dyn':{'treatment_path_effect','dose_response'},
        'nonabs_did':{'treatment_path_effect','dose_response'},
        'rdrobust_r':{'local_effect','late'} if facts.get('discontinuity')=='fuzzy' else {'local_effect'},
        'rdd_localrand':{'local_effect','ate','itt'},'rddensity':{'density_discontinuity'},'rdpower':{'power'},
        'iv_gmm':{'structural_parameter','late'},'iv_ar':{'confidence_set','structural_parameter','late'},'iv_ar_robust':{'confidence_set','structural_parameter','late'},
        'synthetic_control':{'treated_trajectory'},'synthdid':{'treated_block_att','att'},
        'generalized_synth':{'treated_trajectory','treated_block_att','att','event_time_att'},
        'dml_plr':{'linear_projection','conditional_mean','structural_parameter','ate'},'dml_did':{'att'},
        'dml_irm':{'ate','att'},'dml_pliv':{'structural_parameter'},'dml_iivm':{'late'},
        'dml_ssm':{'ate'},'dml_qte':{'qte','local_qte','tail_effect'},
        'dml_pq':{'potential_quantile'},'dml_cvar':{'tail_mean'},'dml_apo':{'potential_mean'},
        'grf':{'cate','ate','att'},'grf_instrumental':{'conditional_iv_effect','aclate'},
        'grf_multi_arm':{'multi_arm_cate','multi_arm_ate'},'grf_survival':{'survival_effect'},'causal_forest':{'cate','ate'},'policy_tree':{'policy_value'},
        'qte':{'qte'},'qtt':{'qtt'},
        'quantile_did':{'qtt','counterfactual_distribution'},'changes_in_changes':{'qtt','counterfactual_distribution'},
        'quantile':{'conditional_quantile'},
        'survival':{'log_hazard_ratio','hazard_ratio'},'oaxaca':{'mean_decomposition'},
        'bunching':{'bunching_mass','elasticity'},
        'marginaleffects':{'marginal_effect','average_marginal_effect','prediction','probability','prediction_contrast'},
        'honest_did':{'sensitivity','confidence_set'},
        'finite_horizon_choice':{'policy_value','welfare'} if respy_simulation else {'structural_parameter'},'lifecycle_choice':{'policy_value','welfare'},
        'finite_horizon_growth':{'policy_value','welfare'},'consumption_saving':{'policy_value','welfare'},
        'aiyagari':{'equilibrium','welfare'}, 'hank_one_asset':{'equilibrium','welfare'},
        'qse_commuting':{'equilibrium','welfare'},'qse_open_city':{'equilibrium','welfare'},
        'qse_imperfect_mobility':{'equilibrium','policy_value','welfare'},
        'stochastic_rbc':{'equilibrium'} if native_function else {'equilibrium','welfare','structural_parameter'},
        'dolo_yaml':{'equilibrium'},
        'correlated_equilibrium':{'equilibrium','welfare'}, 'tu_shapley_core':{'allocation'},
        'interbank_clearing':{'equilibrium'}, 'multitask_incentives':{'policy_value'},
        'state_price_bounds':{'price_bounds'},
        'binary_logit':{'conditional_mean'},'finite_policy_sir':{'policy_value','welfare'},
        'queue_capacity':{'equilibrium','policy_value'},'decision_rights':{'equilibrium','policy_value','welfare'},
        'cournot':{'equilibrium','welfare'},
        'smm':{'structural_parameter'},'maximum_likelihood':{'structural_parameter'}}
    if method == 'dml_qte':
        compatible[method] = {{'PQ':'qte','LPQ':'local_qte','CVaR':'tail_effect'}[selected_score]}
    compatible.update({name:set(entry['targets']) for name,entry in extension_methods.items()})
    if project_implementation is not None:
        compatible[method] = set(project_implementation['targets'])
    compatible['np_demand'] = {'structural_parameter','elasticity'}
    accepted_targets = compatible.get(method, {'structural_parameter','equilibrium','welfare'} if design=='structural' else None)
    if target_kind is not None and accepted_targets is not None and target_kind not in accepted_targets:
        raise ValueError(f'{method} implements target.kind in {sorted(accepted_targets)}; received {target_kind}')
    if design=='conditional_mean' and method=='fixest_ols' and target_kind in ('ate','itt'):
        raise ValueError('causal ATE/ITT selection requires the assignment branch and its identifying conditions')
    if (method in ('iv_gmm','iv_ar','iv_ar_robust','dml_pliv','dml_iivm') or
            method == 'fixed_effects_julia' and request.get('endogenous',adopted_spec.get('endogenous'))) and facts.get('exclusion') is False:
        raise ValueError('the selected IV moment and its test inversion require instrument exclusion')
    if method=='rdrobust_r' and facts.get('discontinuity')=='fuzzy':
        if facts.get('exclusion') is False or facts.get('monotonicity') is False:
            raise ValueError('the fuzzy RD complier effect requires exclusion and local monotonicity')
    if target_kind=='late':
        if facts.get('exclusion') is False or facts.get('monotonicity') is False:
            raise ValueError('LATE requires exclusion and monotonicity for the adopted instrument/receipt comparison')
        conditions += ['binary assignment/receipt compliance population','exclusion and monotonicity','nonzero first-stage receipt response']
    if target_kind=='att' and method=='sunab': required_native_options['aggregation'] = 'att'
    if method in DML_METHODS:
        if isinstance(proposed_contract.get('weights'), str):
            required_native_options['weights'] = proposed_contract['weights']
        if method == 'dml_ssm' and forward_options.get('normalize_ipw') is True:
            raise ValueError('DoubleMLSSM 0.11.4 requires normalize_ipw=false; the official correction changes arm normalization')
        if level is not None:
            required_native_options['confidence_level'] = level
        if interval_type is not None:
            if interval_type not in ('pointwise','simultaneous','joint'):
                raise ValueError('DoubleML intervals must be pointwise or simultaneous')
            required_native_options['joint'] = interval_type in ('simultaneous','joint')
    if target_kind=='event_time_att' and method=='sunab': required_native_options['aggregation'] = 'period'
    if method=='grf' and target_kind in ('ate','att'):
        required_native_options['aggregation.target.sample'] = 'treated' if target_kind=='att' else 'all'
    if method in GRF_METHODS:
        if interval_type not in (None, 'pointwise'):
            raise ValueError('GRF supplies pointwise normal intervals from official conditional variance or aggregate standard errors')
        if level is not None:
            required_native_options['confidence_level'] = level
        if cluster_columns is not None:
            if len(cluster_columns) != 1:
                raise ValueError('grf.clusters requires one adopted independent cluster partition')
            required_native_options['columns.clusters'] = cluster_columns[0]
        selected_weight = proposed_contract.get('weights')
        if isinstance(selected_weight, str):
            required_native_options['columns.sample.weights'] = selected_weight
    if method == 'fixed_effects_julia':
        if interval_type not in (None, 'pointwise'):
            raise ValueError('FixedEffectModels provides its adopted pointwise t intervals')
        if level is not None: required_native_options['confidence_level'] = level
        if isinstance(proposed_contract.get('weights'),str): required_native_options['weights'] = proposed_contract['weights']
    if method == 'causal_forest':
        if proposed_contract.get('weights') is not None:
            raise ValueError('the EconML causal_forest runner averages its unweighted fitted sample; weighted target aggregation uses the GRF contract')
        if (request['dependence'] not in ('independent','iid','heteroskedastic','robust') or cluster_columns or
                requested_inference.get('type') == 'cluster' or facts.get('independent_units') is False):
            raise ValueError('the EconML causal_forest runner uses independent-observation folds and inference; cluster designs use the GRF contract')
        if interval_type not in (None, 'pointwise') or level not in (None, .95):
            raise ValueError('the EconML causal_forest runner saves 95% pointwise intervals; select an implementation of the requested interval contract')
    if method == 'policy_tree':
        if interval_type not in (None,'pointwise'):
            raise ValueError('policy evaluation implements pointwise intervals for the declared target')
        if cluster_columns and len(cluster_columns)!=1:
            raise ValueError('policy evaluation requires one independent cluster partition')
        if 'policy' not in forward_options and (cluster_columns or request['dependence'] in ('cluster','clustered')
                or proposed_contract.get('weights') is not None
                or level not in (None,.95)):
            raise ValueError('weighted/clustered or non-95% policy inference requires the explicit options.policy specification')
        if isinstance(proposed_contract.get('weights'),str):
            required_native_options['weights'] = proposed_contract['weights']
    if method == 'staggered_did':
        if structure not in ('panel','repeated_cross_section'):
            raise ValueError('group-time DID requires panel or repeated_cross_section data_structure')
        required_native_options['panel'] = structure == 'panel'
        if target_kind in ('att','event_time_att'):
            required_native_options['aggregation.type'] = 'simple' if target_kind == 'att' else 'dynamic'
        if cluster_columns is not None:
            if len(set(cluster_columns) - {forward_options.get('entity')}) > 1:
                raise ValueError('did clustering accepts the entity column and one additional cluster column')
            required_native_options['clustervars'] = cluster_columns
            required_native_options['aggregation.clustervars'] = cluster_columns
        if level is not None:
            required_native_options['alp'] = 1 - level
            required_native_options['aggregation.alp'] = 1 - level
        if interval_type is not None:
            if interval_type not in ('pointwise', 'simultaneous'):
                raise ValueError('did interval_type must be pointwise or simultaneous')
            required_native_options['cband'] = interval_type == 'simultaneous'
            required_native_options['aggregation.cband'] = interval_type == 'simultaneous'
            if interval_type == 'simultaneous':
                required_native_options['bstrap'] = True
                required_native_options['aggregation.bstrap'] = True
        for field in ('anticipation', 'base_period'):
            if field in facts:
                required_native_options[field] = facts[field]
        if proposed_contract.get('comparison_group') in ('nevertreated', 'notyettreated'):
            required_native_options['control_group'] = proposed_contract['comparison_group']
    if method == 'iv_ar':
        required_native_options['alpha'] = 1 - level if level is not None else forward_options.get('alpha', .05)
    if method == 'iv_ar_robust' and cluster_columns is not None:
        required_native_options['args.cl'] = cluster_columns
    if method == 'rdrobust_r':
        if interval_type not in (None, 'pointwise'):
            raise ValueError('rdrobust supplies pointwise robust bias-corrected intervals for the adopted cutoff target')
        if level is not None:
            required_native_options['args.level'] = 100 * level
        if cluster_columns is not None:
            if len(cluster_columns) != 1:
                raise ValueError('rdrobust.cluster requires one adopted independent cluster partition')
            required_native_options['columns.cluster'] = cluster_columns[0]
    if method in ('fixest_ols', 'fixest_ppml', 'sunab') and cluster_columns is not None:
        quoted_columns = ['`' + name.replace('\\', '\\\\').replace('`', '\\`') + '`' for name in cluster_columns]
        required_native_options['args.vcov'] = '~' + '+'.join(quoted_columns)
    if method == 'hdfe':
        if interval_type not in (None, 'pointwise'):
            raise ValueError('the HDFE runner implements pointwise official confint intervals')
        if level is not None:
            required_native_options['confidence_level'] = level
        if cluster_columns is not None:
            if len(cluster_columns) != 1:
                raise ValueError('the HDFE runner requires one declared independent cluster column')
            native_vcov = forward_options.get('vcov', {})
            adjustment = 'CRV3' if isinstance(native_vcov, dict) and 'CRV3' in native_vcov else 'CRV1'
            required_native_options['vcov'] = {adjustment:cluster_columns[0]}
        selected_weight = proposed_contract.get('weights')
        if isinstance(selected_weight, str):
            required_native_options['weights'] = selected_weight
        elif selected_weight is not None and not forward_options.get('weights'):
            raise ValueError('HDFE weights require the actual column in options.weights or a string weights binding')
    if method in ('ols_r', 'fixest_ols', 'fixest_ppml', 'negative_binomial_r', 'sunab', 'did2s'):
        if interval_type not in (None, 'pointwise'):
            raise ValueError('the selected fitted-model confint interface supplies pointwise intervals')
        if level is not None:
            required_native_options['confidence_level'] = level
    # Keep the supplied options intact and expose target-implied changes as a
    # reviewable proposal. Selection never amends or executes the adopted fit.
    selected_options = deepcopy(forward_options)
    if method == 'consumption_saving':
        if 'consumer_options' in selected_options:
            if set(selected_options) != {'consumer_options'}:
                raise ValueError('HARK selection options must contain the native consumer_options object')
        else:
            selected_options = {'consumer_options':deepcopy(forward_options or adopted_spec.get('consumer_options',{}))}
        if not isinstance(selected_options['consumer_options'],dict):
            raise ValueError('consumer_options must be an object of native HARK arguments')
    option_changes = []
    if method in GRF_METHODS:
        for argument in ('clusters', 'sample.weights'):
            if 'columns.' + argument in required_native_options and argument in selected_options.get('args', {}):
                previous = selected_options['args'].pop(argument)
                option_changes.append({'field':'options.args.' + argument,'supplied':previous,'selected':None})
    if method in ('fixest_ols', 'fixest_ppml', 'sunab') and cluster_columns is not None:
        # fixest accepts one covariance specification. The vcov formula binds
        # the adopted clusters without also passing its legacy cluster option.
        for container in ('args', 'columns'):
            if 'cluster' in selected_options.get(container, {}):
                previous = selected_options[container].pop('cluster')
                option_changes.append({'field':f'options.{container}.cluster','supplied':previous,'selected':None})
    if extension_contract is not None or method in QTE_METHODS or method in DML_METHODS or method in GRF_METHODS or method in ('rct_design','policy_tree','continuous_did','survival','oaxaca','bunching','marginaleffects','ols_r','fixest_ols','fixest_ppml','negative_binomial_r','heckman','sunab','did2s','staggered_did','did_multiplegt_dyn','nonabs_did','iv_ar','iv_ar_robust','rdrobust_r','hdfe','fixed_effects_julia','finite_horizon_choice','consumption_saving','stochastic_rbc','dolo_yaml','replacement'):
        for field, value in required_native_options.items():
            cursor = selected_options
            path = field.split('.', 1)
            if len(path) == 2:
                if not isinstance(cursor.get(path[0], {}), dict):
                    raise ValueError(f'options.{path[0]} must be an object')
                cursor = cursor.setdefault(path[0], {})
            key = path[-1]
            defaults = {'panel':True,'args.panel':True,'aggregation.type':'dynamic','aggregation':'period',
                        'aggregation.target.sample':'all','args.normalized':False,
                        'args.CI':True,'args.alpha':.05,'args.level':95,'alpha':.05,'confidence_level':.95,
                        'alp':.05,'aggregation.alp':forward_options.get('alp',.05),
                        'cband':False,'aggregation.cband':forward_options.get('cband',False),
                        'bstrap':False,'aggregation.bstrap':forward_options.get('bstrap',False),
                        'score':'ATE' if method == 'dml_irm' else 'LATE' if method == 'dml_iivm' else 'observational' if method == 'dml_did' else 'partialling out',
                        'return_scalar':True,'vFuncBool':False,'details':True,
                        'quantity':'average' if method in GRF_METHODS else None,
                        'effect_scale':'log_hazard' if method == 'survival' else None,
                        'vcov':{'CRV1':cluster_columns[0]} if method == 'hdfe' and cluster_columns else 'hetero'}
            supplied = cursor.get(key, defaults.get(field))
            if supplied != value:
                option_changes.append({'field':('' if method=='consumption_saving' else 'options.')+field,
                    'supplied':supplied,'selected':value})
            cursor[key] = value
    if method in GRF_METHODS and selected_options.get('quantity')=='conditional' and selected_options.get('aggregation'):
        option_changes.append({'field':'options.aggregation','supplied':selected_options.pop('aggregation'),'selected':None})
    unbound_inputs = []
    if extension_contract is not None:
        required_extension_options = extension_contract['required_options']
        if method == 'sensitivity_cinelli' and selected_options.get('input','data') == 'data':
            required_extension_options = ['treatment']
        unbound_inputs.extend('options.'+field for field in required_extension_options if field not in selected_options)
    if method == 'rct_design':
        unbound_inputs.extend('options.' + field for field in
            ('operation','treatment','seed','experimental_design') if field not in selected_options)
        experimental = selected_options.get('experimental_design', {})
        if not isinstance(experimental, dict):
            raise ValueError('experimental_design must contain the adopted assignment specification')
        if not experimental.get('conditions') and not experimental.get('factorial'):
            unbound_inputs.append('options.experimental_design.conditions or factorial')
        if 'interference' not in experimental:
            unbound_inputs.append('options.experimental_design.interference: none or within_cluster')
        if request['dependence'] in ('cluster','clustered') and not experimental.get('clusters'):
            unbound_inputs.append('options.experimental_design.clusters: assignment cluster column')
        if target_kind == 'power' and selected_options.get('operation') != 'diagnose':
            unbound_inputs.append('options.operation=diagnose for the requested power target')
        if selected_options.get('operation') == 'diagnose' and 'simulation' not in selected_options:
            unbound_inputs.append('options.simulation: effect grid, outcome variance, adherence/attrition and repeated design diagnosis')
        if balanced_rct and selected_options.get('operation') in ('analyze','diagnose'):
            ri = selected_options.get('ri',{})
            if not isinstance(ri,dict): raise ValueError('options.ri must bind the adopted randomization procedure')
            if ri.get('method') not in (None,'monte_carlo'):
                raise ValueError('Balanced allocation requires Monte Carlo draws from the same declaration')
            for field in ('method','seed','draws'):
                if field not in ri: unbound_inputs.append('options.ri.'+field)
            if selected_options.get('simulation',{}).get('test') not in (None,'randomization'):
                raise ValueError('Balanced design diagnosis uses the adopted randomization test')
    if method == 'multitreatment_did':
        unbound_inputs.extend('options.'+field for field in ('entity','time','pre','post','treatments') if field not in selected_options)
        if request['dependence'] in ('cluster','clustered') and not cluster_columns:
            unbound_inputs.append('inference.cluster: independent cluster column')
        treatments = selected_options.get('treatments')
        if treatments is not None and (not isinstance(treatments, list) or len(treatments) < 2):
            raise ValueError('multiple_two_period requires at least two intervention columns')
    if method in ('network_exposure','manski_bounds','lee_bounds','balke_pearl'):
        fields = {'network_exposure':('treatment','adjacency','mapping','p_treat','estimator','contrasts','min_prob','eligible_population'),
            'manski_bounds':('treatment','y_lower','y_upper','assumption','n_bootstrap','seed'),
            'lee_bounds':('treatment','selection','monotonicity','n_bootstrap','seed'),
            'balke_pearl':('treatment','instrument','monotonicity')}[method]
        unbound_inputs.extend('options.'+field for field in fields if field not in selected_options)
        if method == 'network_exposure' and selected_options.get('mapping') == 'fraction' and 'thresholds' not in selected_options:
            unbound_inputs.append('options.thresholds')
    if method == 'continuous_did':
        for field in ('entity','time','cohort','dose','seed'):
            if field not in selected_options:
                unbound_inputs.append('options.'+field)
        for field in ('outcome_unit','dose_unit'):
            if not selected_options.get('definitions', {}).get(field):
                unbound_inputs.append('options.definitions.'+field)
    if method in ('survival','oaxaca','bunching'):
        fields = {'survival':('status','ties'), 'oaxaca':('group','group_order','decomposition','bootstrap'),
                  'bunching':('seed','definitions')}[method]
        for field in fields:
            if field not in selected_options:
                unbound_inputs.append('options.'+field)
        if method == 'bunching':
            for field in ('zstar','binwidth','bins_l','bins_r','poly','t0','t1'):
                if field not in selected_options.get('args',{}):
                    unbound_inputs.append('options.args.'+field)
        if method == 'survival' and request['dependence'] in ('cluster','clustered') and not cluster_columns:
            unbound_inputs.append('inference.cluster: independent cluster column')
    if method == 'marginaleffects' and not selected_options.get('function'):
        unbound_inputs.append('options.function: official slopes, predictions, comparisons or avg_ variant')
    if method in QTE_METHODS:
        for field in (('treatment','seed') if method in ('qte','qtt') else ('entity','time','cohort','seed')):
            if field not in selected_options:
                unbound_inputs.append('options.'+field)
        if proposed_contract.get('weights') is not None and not selected_options.get('args',{}).get('weightsname'):
            unbound_inputs.append('options.args.weightsname: sampling-weight column')
    if method in GRF_METHODS:
        for field in {'grf':('treatment',),'grf_instrumental':('treatment','instrument','definitions'),
                'grf_multi_arm':('treatment','arms'),'grf_survival':('treatment','status','definitions')}[method]:
            if field not in selected_options: unbound_inputs.append('options.'+field)
        if method == 'grf_instrumental':
            definitions = selected_options.get('definitions',{})
            if 'iv_estimand' not in definitions: unbound_inputs.append('options.definitions.iv_estimand')
            if definitions.get('iv_estimand') == 'conditional_late' and not definitions.get('compliance_population'):
                unbound_inputs.append('options.definitions.compliance_population')
        if method == 'grf_survival':
            for field in ('target','horizon'):
                if field not in selected_options.get('args',{}): unbound_inputs.append('options.args.'+field)
            for field in ('time_unit','censoring'):
                if not selected_options.get('definitions',{}).get(field): unbound_inputs.append('options.definitions.'+field)
        has_weights = (selected_options.get('columns', {}).get('sample.weights') is not None or
            selected_options.get('args', {}).get('sample.weights') is not None)
        if proposed_contract.get('weights') is not None and not has_weights:
            unbound_inputs.append('weights: analysis column, options.columns.sample.weights or options.args.sample.weights')
        if has_weights and selected_options.get('args', {}).get('equalize.cluster.weights') is True:
            raise ValueError('GRF sample.weights requires equalize.cluster.weights=false')
    if method == 'policy_tree':
        for field in ('treatment','partition','seed'):
            if field not in selected_options: unbound_inputs.append('options.'+field)
        if 'policy' in selected_options:
            for field in ('arms','baseline','value_method','propensity','evaluation_target'):
                if field not in selected_options['policy']: unbound_inputs.append('options.policy.'+field)
            if request['dependence'] in ('cluster','clustered') and not cluster_columns:
                unbound_inputs.append('inference.cluster: independent cluster column')
            if proposed_contract.get('weights') is not None and not selected_options.get('weights'):
                unbound_inputs.append('weights: positive pretreatment target-weight column')
        elif 'propensity' not in selected_options:
            unbound_inputs.append('options.propensity: known binary assignment probability')
    if method in DML_METHODS:
        for field in ('n_folds','seed','learners'):
            if field not in selected_options:
                unbound_inputs.append('options.'+field)
        if method in DML_TREATMENT_METHODS and not selected_options.get('treatment'):
            unbound_inputs.append('options.treatment: treatment column')
        if method == 'dml_did' and not selected_options.get('outcome_pre'):
            unbound_inputs.append('options.outcome_pre: pretreatment outcome column; outcome is post-treatment')
        if method not in ('dml_irm','dml_apo') and (selected_options.get('weights') is not None
                or proposed_contract.get('weights') is not None):
            raise ValueError('The selected official DoubleML constructor has no sampling-weight argument')
        for field in {'dml_ssm':('selection',),'dml_qte':('quantiles',),
                'dml_pq':('quantile','treatment_level'),'dml_cvar':('quantile','treatment_level'),
                'dml_apo':('treatment_level',)}.get(method,()):
            if field not in selected_options: unbound_inputs.append('options.'+field)
        independent_only = method in ('dml_qte','dml_pq','dml_cvar') or (
            method=='dml_ssm' and selected_options.get('score')=='nonignorable')
        if independent_only and (cluster_columns or request['dependence'] in ('cluster','clustered')):
            raise ValueError('The selected native nested score splits require independent observations')
        instrument_score = (method=='dml_ssm' and selected_options.get('score')=='nonignorable' or
            method=='dml_qte' and selected_options.get('score')=='LPQ')
        instruments = request.get('instruments',adopted_spec.get('instruments',[]))
        if instrument_score and not instruments:
            unbound_inputs.append('instruments: excluded selection instrument or binary LPQ instrument')
        if method in DML_TREATMENT_METHODS and request.get('endogenous',adopted_spec.get('endogenous')):
            raise ValueError('The selected DoubleML treatment is bound through options.treatment')
        if method in DML_TREATMENT_METHODS and not instrument_score and instruments:
            raise ValueError('The selected DoubleML score requires instruments=[]')
        if method=='dml_qte' and instrument_score and instruments and len(instruments)!=1:
            raise ValueError('Local quantile effects require exactly one binary instrument')
        if selected_options.get('joint') and not selected_options.get('bootstrap'):
            unbound_inputs.append('options.bootstrap: method and n_rep_boot for joint intervals')
    if request['dependence'] in ('cluster', 'clustered'):
        if method in DML_METHODS and not cluster_columns:
            unbound_inputs.append('inference.cluster/clusters: independent cluster columns')
        elif method == 'hdfe' and not cluster_columns:
            unbound_inputs.append('inference.cluster: one independent cluster column')
        elif method == 'staggered_did' and not selected_options.get('clustervars'):
            unbound_inputs.append('inference.cluster/clusters or options.clustervars')
        elif method == 'continuous_did' and not selected_options.get('args', {}).get('clustervars'):
            unbound_inputs.append('inference.cluster or options.args.clustervars')
        elif method == 'iv_ar_robust' and not selected_options.get('args', {}).get('cl'):
            unbound_inputs.append('inference.cluster/clusters or options.args.cl')
        elif method == 'rdrobust_r' and not (selected_options.get('columns', {}).get('cluster') or
                selected_options.get('args', {}).get('cluster') is not None):
            unbound_inputs.append('inference.cluster or options.columns.cluster')
        elif method in GRF_METHODS and not (selected_options.get('columns', {}).get('clusters') or
                selected_options.get('args', {}).get('clusters') is not None):
            unbound_inputs.append('inference.cluster, options.columns.clusters or options.args.clusters')
        elif method in ('fixest_ols', 'fixest_ppml', 'sunab') and cluster_columns is None:
            native = selected_options.get('args', {})
            vcov = native.get('vcov')
            if not (native.get('cluster') or selected_options.get('columns', {}).get('cluster') or
                    isinstance(vcov, str) and '~' in vcov):
                unbound_inputs.append('inference.cluster/clusters or an explicit native cluster binding')
    if method == 'rdrobust_r' and facts.get('discontinuity') == 'fuzzy' and not (
            selected_options.get('columns', {}).get('fuzzy') or selected_options.get('args', {}).get('fuzzy') is not None):
        unbound_inputs.append('options.columns.fuzzy: actual treatment-receipt column')
    if external_implementation:
        engine = external_implementation['function']
    elif native_function:
        engine = native_function
    elif method == 'consumption_saving':
        engine = function
    elif method in DML_METHODS:
        engine = ('doubleml.did.' if method == 'dml_did' else 'doubleml.') + DML_METHODS[method]
    elif method in R_METHODS:
        package, function = R_METHODS[method]; engine = f'{package}::{function}'
        if method == 'rct_design':
            engine += ' + randomizr::conduct_ra + estimatr + DeclareDesign::diagnose_design'
        if method == 'marginaleffects':
            function = selected_options.get('function','avg_slopes')
            engine = f'marginaleffects::{function}'
    else:
        engine = {'staggered_did':'did::att_gt + did::aggte','blp':'pyblp.Problem.solve',
                  'iv_gmm':'linearmodels.iv.IVGMM',
                  'iv_ar_robust':'ivDiag::AR_test',
                  'fixes_att':'fixes::att',
                  'iv_ar':'linearmodels.iv.IV2SLS + statsmodels.OLS + scipy.stats.f',
                  'synthetic_control':'pysyncon.Synth + statsmodels.OLS',
                  'generalized_synth':'gsynth::gsynth',
                  'causal_forest':'econml.dml.CausalForestDML',
                  'policy_tree':'econml.policy.DRPolicyTree + statsmodels.OLS',
                  'network_exposure':'statspai.interference.network_exposure.network_exposure',
                  'multitreatment_did':'statsmodels.OLS',
                  'manski_bounds':'statspai.bounds.lee_manski.manski_bounds',
                  'lee_bounds':'statspai.bounds.lee_manski.lee_bounds',
                  'balke_pearl':'statspai.bounds.balke_pearl.balke_pearl',
                  'rct':'scipy.stats.permutation_test + statsmodels.OLS',
                  'quantile':'statsmodels.QuantReg',
                  'survival':'statsmodels.duration.hazard_regression.PHReg',
                  'oaxaca':'statsmodels.stats.oaxaca.OaxacaBlinder',
                  'hdfe':'pyfixest.feols','fixed_effects_julia':'FixedEffectModels.reg',
                  'finite_horizon_growth':'scipy.optimize.minimize/SLSQP',
                  'aiyagari':'quantecon.markov.DiscreteDP.solve + scipy.optimize.brentq',
                  'qse_commuting':'scipy.optimize.least_squares','qse_open_city':'scipy.optimize.least_squares',
                  'qse_imperfect_mobility':'scipy.optimize.least_squares',
                  'stochastic_rbc':'statsmodels.tsa.arima.model.ARIMA + research_dsge.solve',
                  'correlated_equilibrium':'research_numerics.correlated_equilibrium + scipy.optimize.linprog',
                  'tu_shapley_core':'research_numerics.tu_shapley_core',
                  'interbank_clearing':'scipy.optimize.linprog(method=highs)',
                  'multitask_incentives':'research_numerics.multitask_incentives',
                  'state_price_bounds':'research_numerics.state_price_bounds + scipy.optimize.linprog',
                  'binary_logit':'research_numerics.moment_map + research_numerics.moment_jacobian',
                  'finite_policy_sir':'research_numerics.finite_policy_sir + scipy.integrate.solve_ivp',
                  'queue_capacity':'research_numerics.queue_capacity','decision_rights':'research_numerics.decision_rights',
                  'cournot':'equity_io.cournot',
                  'matching':'matching.games.StableMarriage.create_from_dictionaries + matching.games.StableMarriage.solve',
                  'bargaining':'research_markets.bargain','dynamic_game':'equity_io.dynamic_game'}.get(method)
        if engine is None:
            engine = 'research_dynamic.observed_run' if owner.startswith('skills/econ-data/scripts/research_dynamic.py') else 'research_markets.'+method
    if method == 'policy_tree' and 'policy' in selected_options:
        engine = 'econml.policy.PolicyTree + '+('scipy.optimize.milp + ' if selected_options['policy'].get('constraints') else '')+(
            'statsmodels.stats.sandwich_covariance.S_white_simple' if selected_options['policy'].get('evaluation_target')=='fixed_batch'
            else 'statspai.policy_learning.ope + statsmodels.WLS')
    changes = []
    if adopted and adopted != method:
        changes.append({'field':'method','adopted':adopted,'selected':method})
    for key in ('estimand','identification','data','id','outcome','regressors','endogenous','instruments'):
        if key == 'identification' and method == 'cournot' and isinstance(adopted_spec.get(key),dict):
            # The equity owner consumes its structured identification object;
            # the selector's required prose describes that unchanged object.
            continue
        if key in adopted_spec and key in request and adopted_spec[key] != request[key]:
            changes.append({'field':key,'adopted':adopted_spec[key],'selected':request[key]})
    for key in contract_fields:
        if key in adopted_contract and proposed_contract.get(key) != adopted_contract[key]:
            changes.append({'field':key,'adopted':adopted_contract[key],'selected':proposed_contract.get(key)})
    if method == 'consumption_saving' and adopted_spec:
        if selected_options['consumer_options'] != adopted_spec.get('consumer_options',{}):
            changes.append({'field':'consumer_options','adopted':adopted_spec.get('consumer_options',{}),
                'selected':selected_options['consumer_options']})
        if 'income_process' in adopted_spec and adopted_spec['income_process'] != income_process:
            changes.append({'field':'income_process','adopted':adopted_spec['income_process'],'selected':income_process})
    elif adopted_spec and (forward_options != adopted_spec.get('options', {}) or option_changes):
        changes.append({'field':'options','adopted':adopted_spec.get('options', {}),'selected':selected_options})
    relation = {'adopted_estimand':adopted_spec.get('estimand'),
                'requested_estimand':request['estimand'],'selected_method_quantity':method_quantity}
    if 'target' in adopted_spec and target and adopted_spec['target'] != target:
        relation['target_change'] = {'adopted':adopted_spec['target'],'selected':target}
    inherited_inference = proposed_contract.get('inference', {})
    if not isinstance(inherited_inference, dict):
        inherited_inference = {}
    inference_contract = {'dependence':request['dependence'],
        'unit':proposed_contract.get('inference_unit',proposed_contract.get('assignment_unit',proposed_contract.get('observation_unit'))),
        'assignment_unit':proposed_contract.get('assignment_unit'),
        'specification':proposed_contract.get('inference'),
        'interval_type':comparison.get('interval_type',comparison.get('ci_kind',
            inherited_inference.get('interval_type',inherited_inference.get('ci_kind','pointwise')))),
        'confidence_level':level,
        'family':comparison.get('inference_family',comparison.get('family',
            inherited_inference.get('inference_family',inherited_inference.get('family')))),
        'official_output_required':True}
    if project_implementation is not None:
        inference_contract.update(procedure=project_implementation['inference'],
            interval_type=requested_inference.get('interval_type'), confidence_level=level)
        if design in ('bayesian_model','marketing_mmm','customer_lifetime_value'):
            inference_contract.update(confidence_level=None,
                credible_level=requested_inference.get('credible_level',.95))
    elif extension_contract is not None:
        inference_contract['procedure'] = extension_contract['inference']
        inference_contract['confidence_level'] = None if method in ('bacon','kitagawa') else level or .95
        if method in ('bacon','kitagawa'):
            inference_contract['interval_type'] = 'none'
        elif method == 'specification_curve':
            inference_contract['interval_type'] = 'simultaneous'
        inference_contract['family'] = selected_options.get('family',inference_contract['family'])
        if method == 'bayesian_model':
            inference_contract.update(interval_type='posterior HDI',confidence_level=None,
                credible_level=requested_inference.get('credible_level',.95))
    elif method == 'np_demand':
        inference_contract.update(procedure='adopted native quasi-Bayesian draws or project sampling procedure for the fitted sieve',
            interval_type=requested_inference.get('interval_type'),confidence_level=None)
    elif method == 'rct_design':
        inference_contract['procedure'] = 'official declaration-based HT or block-standardized HC2/CR2; RI resamples the same declaration'
        inference_contract['experimental_design'] = selected_options.get('experimental_design')
        inference_contract['confidence_level'] = selected_options.get('confidence_level', .95)
        if balanced_rct:
            inference_contract.update(procedure='official HT point contrast; Monte Carlo sharp-null p value from complete declared assignment draws',
                interval_type='none',confidence_level=None,
                significance_level=1-selected_options.get('confidence_level',.95),
                independent_draw_unit='complete declared assignment vector')
    elif method == 'heckman':
        inference_contract.update(procedure='sampleSelection native iid covariance and Student-t coefficient inference',
            interval_type='pointwise',confidence_level=selected_options['confidence_level'],
            estimation_method=selected_options['estimation_method'])
    elif method == 'iv_ar_robust':
        inference_contract['confidence_level'] = 1-alpha
    elif method == 'policy_tree':
        policy = selected_options.get('policy',{})
        inference_contract.update(confidence_level=level or .95,
            target=policy.get('evaluation_target','population'),
            official_output_required=policy.get('evaluation_target')!='fixed_batch',
            procedure=('conservative conditional assignment residual second moment; normal asymptotic reference'
                if policy.get('evaluation_target')=='fixed_batch' else 'independent holdout score mean with HC1 or cluster covariance'))
    elif method in GRF_METHODS:
        inference_contract.update(confidence_level=selected_options.get('confidence_level',.95),
            interval_type='pointwise',procedure='official honest-forest conditional variance or AIPW aggregate covariance',
            target=selected_options.get('quantity','average'))
    elif method in DML_METHODS:
        inference_contract.update(confidence_level=selected_options.get('confidence_level',.95),
            interval_type='joint' if selected_options.get('joint') else 'pointwise',
            procedure='official cross-fitted orthogonal-score inference and declared multiplier bootstrap',
            score=selected_options.get('score'),split_unit='cluster' if cluster_columns else 'observation')
    elif method == 'causal_forest':
        inference_contract.update(confidence_level=.95, interval_type='pointwise',
            procedure='official EconML individual-effect variance and unweighted sample-average standard-error bound')
    elif method == 'continuous_did':
        native = selected_options.get('args', {})
        inference_contract['confidence_level'] = 1-native.get('alp', .05)
        inference_contract['interval_type'] = 'simultaneous' if native.get('cband', False) else 'pointwise'
        inference_contract['procedure'] = 'official contdid returned standard errors and critical values'
    elif method in ('network_exposure','manski_bounds','lee_bounds','balke_pearl'):
        inference_contract['confidence_level'] = None if method == 'balke_pearl' else level or .95
        inference_contract['interval_type'] = 'none' if method == 'balke_pearl' else 'pointwise'
        inference_contract['procedure'] = {'network_exposure':'official PSD HAC covariance for local network dependence',
            'manski_bounds':'official endpoint bootstrap and identified-set covering interval',
            'lee_bounds':'official exact trimming, endpoint bootstrap and Imbens-Manski parameter interval',
            'balke_pearl':'identified-set endpoints; no sampling interval'}[method]
        inference_contract['target'] = {'network_exposure':'exposure contrast','manski_bounds':'identified_set',
            'lee_bounds':'parameter','balke_pearl':'identified_set'}[method]
    elif method in ('survival','oaxaca','bunching'):
        inference_contract['procedure'] = {'survival':'official PHReg likelihood or group sandwich covariance',
            'oaxaca':'official OaxacaBlinder row-bootstrap component standard deviations after native conf trimming',
            'bunching':'official bunchit residual-bootstrap standard deviations'}[method]
        if method != 'survival':
            inference_contract['interval_type'] = 'none'
            inference_contract['confidence_level'] = None
    elif method == 'finite_horizon_choice' and not respy_simulation:
        inference_contract['procedure'] = ('adopted moment covariance with simulation contribution' if algorithm == 'smm'
            else 'adopted likelihood curvature or refitted sampling procedure')
        inference_contract['parameter_operation'] = 'estimate structural parameters'
    elif method in ('lifecycle_choice','consumption_saving','finite_horizon_growth','aiyagari','qse_commuting','qse_open_city','qse_imperfect_mobility','hank_one_asset','stochastic_rbc','dolo_yaml','cournot') or respy_simulation or numerical_kernel is not None:
        inference_contract['procedure'] = ('original Euler/resource residuals at the adopted deterministic numerical tolerance' if method == 'finite_horizon_growth'
            else 'adopted simulation precision and parameter-draw propagation when requested')
        inference_contract['parameter_operation'] = 'hold fixed or previously estimated parameters'
        inference_contract['interval_type'] = comparison.get('interval_type',comparison.get('ci_kind',
            inherited_inference.get('interval_type',inherited_inference.get('ci_kind'))))
        inference_contract['official_output_required'] = False
        if numerical_kernel is not None:
            inference_contract['procedure'] = 'original feasibility, obedience, allocation, clearing or KKT residuals'
            inference_contract['parameter_operation'] = computation['parameter_operation']
            if method == 'state_price_bounds':
                inference_contract['procedure'] = 'original state-price equations, hedge inequalities, primal-dual gaps and replication residual'
            elif method == 'binary_logit':
                inference_contract['procedure'] = 'analytic model quantities and derivatives at the supplied fixed parameters'
            elif method == 'queue_capacity':
                inference_contract['procedure'] = 'stationary M/M/1 utilization, system and queue identities at the supplied rates'
            elif method == 'finite_policy_sir':
                inference_contract['procedure'] = 'population conservation and the adopted integration tolerance'
        if method == 'cournot':
            inference_contract['procedure'] = 'firm best-response residuals and capacity complementarity at the adopted equilibrium tolerance'
            inference_contract['parameter_operation'] = computation['parameter_operation']
        if method in ('aiyagari','qse_commuting','qse_open_city','qse_imperfect_mobility','hank_one_asset','stochastic_rbc','dolo_yaml'):
            inference_contract['procedure'] = 'original economic-equation residuals and the adopted grid, horizon and integration comparisons'
            inference_contract['parameter_operation'] = computation['parameter_operation']
        if method == 'qse_commuting':
            inference_contract['procedure'] = 'original labor, floor, goods and population residuals at the adopted numerical tolerance'
        if method in ('qse_open_city','qse_imperfect_mobility'):
            inference_contract['procedure'] = ('original labor, floor, goods, population and migration log-odds residuals at the adopted numerical tolerance'
                if method=='qse_imperfect_mobility' else 'original labor, floor, goods, population and migration-utility residuals at the adopted numerical tolerance')
        if method == 'stochastic_rbc' and native_function is None:
            inference_contract['procedure'] = 'Gaussian AR(1) maximum-likelihood covariance and original RBC equation residuals'
            inference_contract['official_output_required'] = True
    if request['dependence'] in ('cluster', 'clustered'):
        cluster_count = facts.get('cluster_count')
        treated_cluster_count = facts.get('treated_cluster_count')
        for name, count, minimum in (('cluster_count', cluster_count, 2),
                ('treated_cluster_count', treated_cluster_count, 0)):
            if count is not None and (isinstance(count, bool) or not isinstance(count, int) or count < minimum):
                raise ValueError(f'conditions.{name} must be an integer >= {minimum}')
        if cluster_count is not None and treated_cluster_count is not None and treated_cluster_count > cluster_count:
            raise ValueError('treated_cluster_count cannot exceed cluster_count')
        inference_contract['cluster_design'] = {
            'columns':cluster_columns, 'independent_unit':inference_contract['unit'],
            'declared_cluster_count':cluster_count, 'declared_treated_cluster_count':treated_cluster_count,
            'common_shocks':facts.get('common_shocks'), 'counts_basis':'declared design; confirm on the fitted sample',
            'required_conditions':['independence across the specified clusters',
                'assignment and common shocks represented by the adopted clustering',
                'cluster size, leverage and treated/control cluster support for the chosen reference distribution']}
        inference_contract['comparisons'] = []
        for candidate, supported, model_class, native, source in (
            ('wild_cluster_bootstrap', method in ('ols_r','fixest_ols','sunab','did2s'),
             'saved lm or linear fixest fit', {'conf_int':True},
             'https://s3alfisc.github.io/fwildclusterboot/reference/boottest.fixest.html'),
            ('club_sandwich', method == 'ols_r', 'saved lm fit with vcovCR.lm support',
             {'vcov':'CR2','test':'Satterthwaite'},
             'https://jepusto.github.io/clubSandwich/reference/coef_test.html')):
            package, function = R_METHODS[candidate]
            inference_contract['comparisons'].append({
                'method':candidate,'function':f'{package}::{function}',
                'entry_point':'skills/econ-data/scripts/research_causal.py run',
                'model_contract':model_class,'compatible_saved_fit':supported,
                'excluded_by':[] if supported else ['the selected result does not provide this supported native linear-model fit'],
                'native_options':native,'source':source,
                'required_inputs':['saved fit and exact analysis-sample cluster vector','coefficient contrast and null',
                    'adopted cluster reference model and bootstrap weights/repetitions when used'],
                'adoption_status':'comparison_preserving_current_inference','executed':False})
    candidate_comparisons = []
    for candidate in alternatives:
        if candidate['method'] == method:
            continue
        fit = candidate['data_fit']
        dimensions = {'data_structures':('data_structure',structure),
                      'treatment_patterns':('treatment_pattern',pattern),
                      'outcome_scales':('outcome_scale',request['outcome_scale']),
                      'dependence':('dependence',request['dependence'])}
        fit['declared'] = {name:value for name,value in dimensions.values()}
        fit['matches_declared_dimensions'] = {
            name:value in fit[allowed] for allowed,(name,value) in dimensions.items() if allowed in fit}
        if 'conditional_distribution' in fit:
            fit['matches_declared_dimensions']['conditional_distribution'] = (
                facts['conditional_distribution'] == fit['conditional_distribution'] if 'conditional_distribution' in facts else None)
        fit['basis'] = 'declared specification'
        fit['data_inspected'] = False
        candidate_targets = compatible.get(candidate['method'])
        candidate['target_comparison'] = {'requested':target or {'expression':request['estimand']},
            'candidate_estimand':candidate['estimand'],
            'supported_kinds':sorted(candidate_targets) if candidate_targets is not None else None,
            'matches_requested_kind':target_kind in candidate_targets if target_kind and candidate_targets is not None else None}
        if candidate['method'] == 'dml_plr' and target_kind == 'ate':
            candidate['target_comparison']['matches_requested_kind'] = (
                facts['effect_heterogeneity'] == 'constant' if 'effect_heterogeneity' in facts else None)
        exclusions = [f'{dimension}={fit["declared"].get(dimension, facts.get(dimension))}'
            for dimension, matches in fit['matches_declared_dimensions'].items() if matches is False]
        if candidate['target_comparison']['matches_requested_kind'] is False:
            exclusions.append(f'target.kind={target_kind} is outside the candidate estimand')
        if candidate['method'] == 'iv_ar' and facts.get('homoskedastic_normal_errors') is False:
            exclusions.append('exact F inversion requires explicit independent homoskedastic normal errors')
        if candidate['method'] == 'synthdid' and facts.get('common_treatment_block') is False:
            exclusions.append('the observed treatment histories do not form a common treated block')
        candidate['eligibility'] = {'status':'incompatible' if exclusions else 'requires_identifying_conditions',
            'excluded_by':exclusions, 'conditions_to_establish':candidate['conditions']}
        candidate['inference']['adopted_dependence'] = request['dependence']
        candidate['inference']['adopted_unit'] = inference_contract['unit']
        candidate['adopted_specification_changes'] = {
            'method':{'adopted':adopted,'candidate':candidate['method'],
                      'change_required':adopted is not None and adopted != candidate['method']},
            'estimand':{'adopted':adopted_spec.get('estimand'),'candidate':candidate['estimand']},
            'identification':{'adopted':adopted_spec.get('identification'),'candidate_conditions':candidate['conditions']},
            'sample_weights_aggregation':{'adopted':{k:adopted_contract[k] for k in ('population','comparison_group','weights','comparison') if k in adopted_contract},
                                          'candidate_requirements':fit['required']},
            'inference':{'adopted':adopted_contract.get('inference'),'candidate_procedure':candidate['inference']['procedure']}}
        if design == 'structural':
            candidate['adopted_specification_changes']['method'] = {
                'adopted':adopted,'candidate':model,'change_required':adopted is not None and adopted != model}
            candidate['adopted_specification_changes']['numerical.estimation_method'] = {
                'adopted':adopted_contract.get('numerical',{}).get('estimation_method'),
                'selected':algorithm,'candidate':candidate['method']}
        candidate_comparisons.append(candidate)
    economic_fields = ('actors','objectives','choices','constraints','information','interactions','equilibrium','welfare')
    if computation is not None and numerical_kernel is None:
        economic_fields = ('actors','objectives','states','choices','constraints','information',
            'transitions','shocks','discount','horizon','terminal_conditions','observed_data',
            'identified_parameters','computation_target','equilibrium','welfare')
        if external_implementation:
            computation['outputs'] = external_implementation['outputs']
    if not required_inputs:
        required_inputs = ['adopted target/population/period','model-specific columns or saved fitted object','matching inference unit and contrast']
    selection = {'selected_method':method,'estimand':method_quantity,'target':target,
        'economic_model':economic_model,'structured_conditions':facts,
        'required_inputs':required_inputs,'assumptions':conditions,'inference':inference_contract,
        'official_implementation':{'function':engine,'entry_point':owner,'options':selected_options,
            'implementation':selected_profile,
            'required_options':required_native_options,'execution_mode':'external_official_entry' if external_implementation else 'existing_runner',
            'unbound_inputs':unbound_inputs,
            'external_contract':external_implementation},
        'option_changes':option_changes,
        'reason':{'target':method_quantity,'design':design,'assignment_mechanism':mechanism,
            'data_structure':structure,'treatment_pattern':pattern,'outcome_scale':request['outcome_scale']},
        'alternatives':candidate_comparisons,
        'economic_chain':{'decision':economic_model,'target':target or {'expression':request['estimand']},
            'population_and_observations':proposed_contract,'identification':{'statement':request['identification'],'conditions':facts,'comparison':comparison},
            'estimator':{'method':method,'weights':proposed_contract.get('weights'),'numerical':numerical,'inference':inference_contract},
            'implementation':{'function':engine,'options':selected_options}},
        'model_inputs_to_supply':[k for k in economic_fields if (economic_model or computation is not None) and k not in economic_model],
        'adoption_status':'proposal_retaining_adopted_specification' if changes else 'selected_for_requested_target'}
    if computation is not None:
        selection['computation'] = computation
    if model_contract is not None:
        selection['model_contract'] = model_contract
        selection['knowledge_plan'] = knowledge_plan
        selection['compatibility'] = {'status':'compatible_declared_specification',
            'basis':'existing selector restrictions on the declared model, target, conditions and numerical method',
            'selected_method':method, 'structural_model':model,
            'supported_targets':sorted(accepted_targets), 'requested_target':target_kind,
            'numerical_method':algorithm, 'conditions_to_establish':conditions,
            'data_inspected':False, 'executed':False}
    native_language = (external_implementation.get('language','python').lower() if external_implementation else
        'r' if '::' in engine else 'julia' if engine.startswith(('FixedEffectModels.','NPDemand.')) else 'python')
    data_path = request.get('data', adopted_spec.get('data'))
    selected_record = request.get('data_record',adopted_spec.get('data_record'))
    if data_path is None and selected_record is not None:
        import research_data
        base = Path(spec_path).resolve().parent if spec_path is not None else Path.cwd()
        bound, _, _ = research_data.bind_data_record({'data_record':selected_record},base)
        data_path = bound['data']
    table_path = data_path.get('path') if isinstance(data_path, dict) else data_path
    data_format = Path(table_path).suffix.lower().lstrip('.') if isinstance(table_path,str) else None
    if data_format in ('feather','ipc'): data_format = 'arrow'
    data_engine = execution_context.get('data_engine')
    budget, working_set = (execution_context.get(field) for field in ('memory_budget_bytes','working_set_bytes'))
    if data_engine is None:
        data_engine = 'duckdb' if budget is not None and working_set is not None and working_set > budget else 'pandas'
    selection['execution_plan'] = {
        'estimation_language':native_language, 'orchestration_language':'python',
        'data_engine':data_engine, 'data':data_path,
        'data_record':deepcopy(request.get('data_record',adopted_spec.get('data_record'))),
        'data_format':data_format, 'canonical_data_policy':'one shared analysis table referenced by every executor',
        'materialization':'project, filter, join and aggregate before collection' if data_engine=='duckdb' else 'reuse the adopted in-memory or saved analysis table',
        'handoff':'direct file reference' if native_language in ('r','julia') else 'native dataframe',
        'native_result':'retain the fitted object and export named coefficients, covariance, sample and inference',
        'environment_status':'available' if available_languages is not None and native_language in available_languages else 'resolve selected runtime and package closure',
        'selection_basis':{'official_function':engine,'preserved_contract':proposed_contract,
            'working_set_bytes':working_set,'memory_budget_bytes':budget,
            'observed_performance':execution_context.get('performance')},
        'executed':False}
    implementation = selection['official_implementation']
    # Reuse the registered dependency owners; requirements remain their sole
    # version authority and can be passed to the research harness runtime.
    dependency_path = owner.split(' ', 1)[0]
    resource = next((r for rid, r in resources.items() if dependency_path in
        (r['source_path'], placements[rid]['deployment_path'], placements[rid]['export_alias'])), None)
    is_causal_runner = owner == 'skills/econ-data/scripts/research_causal.py run'
    if model_contract is not None:
        if external_implementation:
            called_functions = set(engine.split(' + '))
            native_separator = '::' if external_implementation['language'].lower() == 'r' else '.'
            matched_bindings = [entry for entry in model_contract['implementation']
                if entry.get('module') and entry['module']+native_separator+entry['symbol'] in called_functions]
            matched_functions = {entry['module']+native_separator+entry['symbol'] for entry in matched_bindings}
            if matched_functions != called_functions:
                raise ValueError(f'{contract_id} does not bind the selected official functions: {engine}')
        else:
            matched_bindings = [entry for entry in model_contract['implementation']
                if resource and entry.get('resource_id') == resource['resource_id']
                and entry.get('command') == owner.split(' ',1)[1]]
            if not matched_bindings:
                raise ValueError(f'{contract_id} does not bind the selected execution owner: {owner}')
        implementation['model_contract_id'] = contract_id
        implementation['contract_bindings'] = matched_bindings
    if resource and not external_implementation:
        resource_id = resource['resource_id']
        script_path = resource['source_path'] if layout_path == 'source_path' else placements[resource_id][layout_path]
        owner = script_path + ' ' + owner.split(' ', 1)[1]
        implementation['entry_point'] = owner
    for candidate in inference_contract.get('comparisons', []):
        causal_path = resources['research-causal']['source_path'] if layout_path == 'source_path' else placements['research-causal'][layout_path]
        candidate['entry_point'] = causal_path + ' run'
    implementation['dependencies'] = []
    if resource:
        dependency_ids = resource.get('required_resources', [])
        if method == 'finite_horizon_choice':
            dependency_ids = ['research-respy-dependencies']
        elif method == 'lifecycle_choice':
            dependency_ids = ['research-lifecycle-dependencies']
        elif method == 'dolo_yaml' or method == 'stochastic_rbc' and native_function:
            dependency_ids = ['research-dolo-dependencies']
        elif method in ('hank_one_asset','stochastic_rbc','aiyagari','qse_commuting','qse_open_city','qse_imperfect_mobility','consumption_saving'):
            dependency_ids = ['research-macro-dependencies']
        for resource_id in dependency_ids:
            dependency = resources[resource_id]
            path = dependency['source_path']
            if Path(path).name.startswith('requirements-'):
                if path.endswith('-r.json') and method not in R_METHODS and method not in ('staggered_did','generalized_synth'):
                    continue
                implementation['dependencies'].append({'resource_id':resource_id,
                    'path':path if layout_path == 'source_path' else placements[resource_id][layout_path]})
    evaluation_data = selected_options.get('evaluation_data')
    evaluation_format = Path(evaluation_data).suffix.lower() if isinstance(evaluation_data,str) else None
    typed_r_input = is_causal_runner and native_language == 'r' and (
        data_format in ('parquet','arrow') or evaluation_format in ('.parquet','.arrow','.feather','.ipc'))
    if extension_contract is not None or method in ('fixed_effects_julia','np_demand','heckman') or typed_r_input:
        # The existing requirements own shared pins; select the package closure
        # for this operation instead of installing the entire causal family.
        rid = 'research-causal-dependencies'
        dependency_file = resources[rid]['source_path'] if layout_path == 'source_path' else placements[rid][layout_path]
        dependency_root = ROOT.parent if ROOT.name == '.agents' else ROOT
        requirements = (dependency_root/dependency_file).read_text().splitlines()
        pins = {line.split('==',1)[0]:line.split('==',1)[1] for line in requirements if '==' in line}
        packages = {name:pins[name] for name in ('numpy','pandas','scipy','statsmodels')}
        install = [name+'=='+value for name,value in packages.items()]
        if method == 'bayesian_model':
            bayesian_engine = selected_options.get('engine', 'pymc')
            if bayesian_engine not in CAUSAL_EXTENSIONS[method]['packages_by_engine']:
                raise ValueError('Bayesian engine must be pymc or causalpy')
            packages.update(CAUSAL_EXTENSIONS[method]['packages_by_engine'][bayesian_engine])
            install = [name+'=='+value for name,value in packages.items()]
        elif extension_contract is not None and method != 'holm':
            packages['StatsPAI'] = extension_contract['version']
            install.extend(line for line in requirements if line.startswith('StatsPAI @ '))
            if method == 'shift_share_inference' and selected_options.get('cluster'):
                packages['linearmodels'] = pins['linearmodels']; install.append('linearmodels=='+pins['linearmodels'])
        if data_format in ('parquet','arrow') or typed_r_input:
            packages['pyarrow'] = '26.0.1'; install.append('pyarrow==26.0.1')
        implementation['dependencies'] = []
        implementation['dependency_sources'] = [{'resource_id':rid,'path':dependency_file}]
        implementation['install_requirements'] = install
        implementation['runtime'] = {'language':'python','packages':packages,'files':[dependency_file]}
        if method in ('fixed_effects_julia','np_demand'):
            julia_packages = {'FixedEffectModels':'2.2.0','DataFrames':None,'StatsModels':None,'Tables':None,'JSON3':None} if method=='fixed_effects_julia' else {'NPDemand':'0.1.0','DataFrames':None,'Tables':None}
            julia_packages[{'parquet':'Parquet2','arrow':'Arrow'}.get(data_format,'CSV')] = None
            native_runtime = {'language':'julia','packages':julia_packages,
                'files':['adopted Project.toml','adopted Manifest.toml']}
            if method == 'fixed_effects_julia': implementation['runtime']['companions'] = [native_runtime]
            else:
                implementation['runtime'] = native_runtime
                implementation['install_requirements'] = []
        if typed_r_input or method == 'heckman':
            r_id = 'research-causal-r-dependencies'
            r_file = resources[r_id]['source_path'] if layout_path == 'source_path' else placements[r_id][layout_path]
            r_pins = json.loads((dependency_root/r_file).read_text())['packages']
            package = R_METHODS[method][0] if method in R_METHODS else {
                'staggered_did':'did','generalized_synth':'gsynth'}[method]
            r_packages = ['jsonlite',package]
            if typed_r_input:
                r_packages.append('arrow')
            r_packages.extend({
                'staggered_did':['DRDID'],
                'did2s':['fixest'],
                'iv_ar_robust':['lfe'],
                'wild_cluster_bootstrap':['dqrng'],
                'heckman':['miscTools','systemfit','Formula','VGAM','mvtnorm','maxLik'],
                'rct_design':['estimatr'],
                'bunching':['BB','dplyr','tidyr','ggplot2'],
                'continuous_did':['ptetools','npiv','BMisc','splines2','sandwich','ggplot2','checkmate','MASS','Matrix'],
            }.get(method,[]))
            if method in QTE_METHODS:
                r_packages.append('ptetools')
            if method == 'rct_design' and selected_options.get('operation') == 'diagnose':
                r_packages.extend(['DeclareDesign','fabricatr','broom'])
            if method == 'nonabs_did':
                underlying = {'DCDH':'DIDmultiplegtDYN','PanelMatch':'PanelMatch','IFE':'fect','FE':'fect','MC':'fect'}
                if selected_options.get('estimator') in underlying:
                    r_packages.append(underlying[selected_options['estimator']])
            if method == 'did_multiplegt_dyn' or method == 'nonabs_did' and selected_options.get('estimator') == 'DCDH':
                r_packages.append('polars')
            if method == 'marginaleffects' and isinstance(data_path,str):
                saved_path = Path(data_path)
                if not saved_path.is_absolute():
                    saved_path = (Path(spec_path).resolve().parent if spec_path is not None else Path.cwd())/saved_path
                if saved_path.is_file():
                    from research_evidence import read_json
                    saved_result = read_json(saved_path.read_bytes(), f'saved causal result {saved_path}')
                    model_engine = (saved_result.get('source_model') or saved_result).get('engine','')
                    if isinstance(model_engine,str) and '::' in model_engine:
                        r_packages.append(model_engine.split('::',1)[0])
            implementation['dependency_sources'].append({'resource_id':r_id,'path':r_file})
            implementation['runtime']['companions'] = [{
                'language':'r','packages':{name:r_pins.get(name) for name in r_packages},'files':[r_file]}]
    if data_format in ('parquet', 'arrow') and native_language == 'python' and project_implementation is None:
        arrow_version = '17.0.0' if method == 'finite_horizon_choice' else '26.0.1'
        runtime = implementation.setdefault('runtime', {'language': 'python', 'packages': {}})
        runtime['packages'].setdefault('pyarrow', arrow_version)
        requirements = [entry['path'] for entry in implementation['dependencies']
                        if entry['path'].endswith('.txt')]
        if requirements:
            runtime.setdefault('requirements', requirements)
            runtime.setdefault('files', requirements)
        install = implementation.setdefault('install_requirements', [])
        requirement = 'pyarrow==' + arrow_version
        if requirement not in install:
            install.append(requirement)
    if data_engine == 'duckdb':
        selection['execution_plan']['data_runtime'] = {
            'language': 'python', 'packages': {'duckdb': '2.0.0', 'pyarrow': '26.0.1'}}
    if project_implementation is not None:
        packages = deepcopy(project_implementation['packages'])
        native_language = project_implementation['language']
        if native_language == 'python':
            packages.setdefault('packaging', '26.3')
        runtime = {'language':native_language,'packages':packages}
        if project_implementation['apis']:
            runtime['apis'] = deepcopy(project_implementation['apis'])
        implementation['runtime'] = runtime
        implementation['install_requirements'] = ([name+'=='+version for name,version in packages.items()
            if version is not None] if native_language == 'python' else [])
        implementation['installation'] = project_implementation['installation']
        implementation['dependency_sources'] = [{'resource_id':'research-design',
            'path':resources['research-design']['source_path'] if layout_path == 'source_path' else placements['research-design'][layout_path]}]
        stage = deepcopy(selected_options.get('stage'))
        missing = []
        if stage is None:
            missing.append('options.stage with the existing project argv, inputs, outputs and runtime.probe_argv')
        else:
            if not isinstance(stage,dict):
                raise ValueError('options.stage must be an existing research argv stage')
            for field in ('id','argv','inputs','depends','outputs','runtime'):
                if field not in stage:
                    missing.append('options.stage.'+field)
            if 'argv' in stage and (not isinstance(stage['argv'],list) or not stage['argv'] or
                    any(not isinstance(value,str) or not value for value in stage['argv'])):
                raise ValueError('options.stage.argv must list the actual command and arguments')
            if 'inputs' in stage and (not isinstance(stage['inputs'],list) or
                    any(not isinstance(value,str) or not value for value in stage['inputs'])):
                raise ValueError('options.stage.inputs must list the project input paths')
            if 'outputs' in stage and (not isinstance(stage['outputs'],dict) or not stage['outputs']):
                raise ValueError('options.stage.outputs must name the native result files')
            stage_runtime = stage.get('runtime',{})
            if not isinstance(stage_runtime,dict) or stage_runtime.get('language',native_language) != native_language:
                raise ValueError('options.stage.runtime must use the selected native language')
            stage_runtime.setdefault('language',native_language)
            stage_packages = stage_runtime.setdefault('packages',{})
            if not isinstance(stage_packages,dict):
                raise ValueError('options.stage.runtime.packages must be an object')
            for name,version in packages.items():
                if version is not None and name in stage_packages and stage_packages[name] != version:
                    raise ValueError(f'options.stage runtime conflicts with selected {name}=={version}')
                stage_packages.setdefault(name,version)
            if 'probe_argv' not in stage_runtime:
                missing.append('options.stage.runtime.probe_argv')
            if project_implementation['apis']:
                existing_apis = stage_runtime.setdefault('apis',[])
                if not isinstance(existing_apis,list):
                    raise ValueError('options.stage.runtime.apis must list selected native API bindings')
                for api in project_implementation['apis']:
                    if api not in existing_apis:
                        existing_apis.append(deepcopy(api))
            stage['runtime'] = stage_runtime
            if native_language == 'julia' and not stage_runtime.get('files'):
                missing.append('options.stage.runtime.files with the adopted Project.toml and Manifest.toml')
            for source in implementation['dependency_sources']:
                if source['path'] not in stage.get('inputs',[]):
                    stage.setdefault('inputs',[]).append(source['path'])
                if source['path'] not in stage_runtime.get('files',[]):
                    stage_runtime.setdefault('files',[]).append(source['path'])
        implementation['execution_specification'] = {
            'status':'inputs_required' if missing else 'specified', 'stage':stage,
            'missing_fields':missing, 'unbound_inputs':missing, 'adoption_required':bool(changes),
            'schema_owner':'harness/research.md: argv stage and selected runtime',
            'result_contract':{'native_outputs':project_implementation['outputs'],
                'identity':['adopted specification','canonical data and observation IDs','package/runtime versions','actual native call and options','units and scenario'],
                'consumer':'existing saved-result dependencies and artifact renderer'}}
        implementation['unbound_inputs'] = missing
    elif is_causal_runner and external_implementation is None:
        inputs = {**adopted_spec, **request}
        execution_spec = {key:deepcopy(inputs[key]) for key in RUN_FIELDS | {'data_record'} if key in inputs}
        execution_spec.update(method=method, options=deepcopy(selected_options))
        if 'data_record' in execution_spec and 'data' not in execution_spec:
            execution_spec['data'] = data_path
        if extension_contract is not None:
            for field in ('regressors','endogenous','instruments'):
                execution_spec.setdefault(field, [])
            if method == 'bayesian_model':
                execution_spec['inference'] = {'type':'posterior',
                    'credible_level':requested_inference.get('credible_level',level or .95)}
            elif method in INFERENCE_METHODS:
                execution_spec['inference'] = {'type':'official','confidence_level':level or .95}
            elif method in ('bacon','kitagawa') or requested_inference.get('type') == 'none':
                execution_spec['inference'] = {'type':'none'}
            elif cluster_columns:
                if len(cluster_columns) != 1:
                    raise ValueError('this official extension requires one independent cluster partition')
                execution_spec['inference'] = {'type':'cluster','cluster':cluster_columns[0],'confidence_level':level or .95}
            else:
                execution_spec['inference'] = {'type':'official','confidence_level':level or .95}
        elif method in DML_METHODS:
            execution_spec['inference'] = ({'type':'cluster','clusters':cluster_columns} if cluster_columns
                else {'type':'official'})
            for field in ('endogenous','instruments'):
                if method in DML_TREATMENT_METHODS:
                    execution_spec.setdefault(field, [])
                elif not execution_spec.get(field):
                    unbound_inputs.append(field+': adopted treatment/instrument columns')
        elif method in ('network_exposure','manski_bounds','lee_bounds','balke_pearl'):
            execution_spec['inference'] = ({'type':'none'} if method == 'balke_pearl' else
                {'type':'official','confidence_level':level or .95})
        elif method == 'multitreatment_did':
            execution_spec['inference'] = ({'type':'cluster','cluster':cluster_columns[0]} if cluster_columns else {'type':'robust'})
        elif method == 'policy_tree':
            execution_spec['inference'] = {'type':'policy'}
            if 'policy' in selected_options:
                if cluster_columns: execution_spec['inference']['cluster'] = cluster_columns[0]
                if level is not None: execution_spec['inference']['confidence_level'] = level
        elif method == 'causal_forest':
            execution_spec['inference'] = {'type':'forest'}
        elif method in R_METHODS:
            execution_spec['inference'] = {'type':'official'}
        elif method == 'staggered_did':
            execution_spec['inference'] = {'type':'did'}
        elif method == 'iv_ar':
            execution_spec['inference'] = {'type':'homoskedastic'}
        elif method == 'quantile':
            execution_spec['inference'] = {'type':'robust'}
        elif method == 'survival':
            execution_spec['inference'] = ({'type':'cluster','cluster':cluster_columns[0]} if cluster_columns else {'type':'official'})
        elif method == 'oaxaca':
            execution_spec['inference'] = {'type':'official'}
        elif method == 'fixed_effects_julia':
            execution_spec['inference'] = ({'type':'cluster','clusters':cluster_columns} if cluster_columns
                else {'type':'homoskedastic'} if requested_inference.get('type') == 'homoskedastic' else {'type':'robust'})
            if request['dependence'] in ('cluster','clustered') and not cluster_columns:
                unbound_inputs.append('inference.cluster/clusters')
        elif method == 'hdfe':
            if cluster_columns:
                execution_spec['inference'] = {'type':'cluster','cluster':cluster_columns[0]}
            else:
                execution_spec['inference'] = {'type':'cluster' if request['dependence'] in ('cluster','clustered') else 'robust'}
        missing_fields = sorted(RUN_FIELDS - execution_spec.keys())
        implementation['execution_specification'] = {
            'status':'inputs_required' if missing_fields or unbound_inputs else 'specified',
            'specification':execution_spec, 'missing_fields':missing_fields,
            'unbound_inputs':unbound_inputs, 'adoption_required':bool(changes),
            'command':['python',*owner.split(' '),'SPEC.json','--output','RESULT.json']}
    elif resource and external_implementation is None and (resource['resource_id'] in (
            'research-macro', 'research-markets', 'research-dynamic', 'research-macro-extended', 'research-dsge', 'research-numerics')
            or resource['resource_id'] == 'equity-calculator' and method == 'cournot'):
        # Project a matching adopted specification into its existing owner's
        # public input. Numerical validation stays in that owner.
        resource_id = resource['resource_id']
        if resource_id == 'research-numerics':
            owner_fields = required_fields = {'model','inputs','unit'}
        elif resource_id == 'equity-calculator' and method == 'cournot':
            required_fields = {'model','sources','identification','market','as_of','currency','price_unit','quantity_unit',
                'inverse_demand','markets'}
            owner_fields = required_fields | {'observations','counterfactual','equilibrium_tolerance'}
        elif resource_id == 'research-macro':
            owner_fields = {'alpha','beta','delta','initial_capital','terminal_capital','baseline','scenario',
                'population','period','unit','sources','tolerance'}
            required_fields = owner_fields
        elif resource_id == 'research-macro-extended' and method == 'aiyagari':
            owner_fields = required_fields = {'model','calibration_source','parameters','baseline','scenario','solver'}
        elif resource_id == 'research-macro-extended' and method in ('qse_commuting','qse_open_city','qse_imperfect_mobility'):
            required_fields = {'model','operation'}
            owner_fields = required_fields | {'calibration_source','parameters','baseline','scenario','saved_solution','solver','closure','migration'}
            required_fields |= ({'saved_solution','scenario'} if computation['requested_operation'] == 'counterfactual'
                else {'calibration_source','parameters','baseline'})
        elif resource_id == 'research-macro-extended' and method == 'consumption_saving':
            required_fields = {'model','income_process','consumer_options','evaluation','calibration_source'}
            owner_fields = required_fields | {'scenario','simulation'}
        elif resource_id == 'research-macro-extended' and method == 'lifecycle_choice':
            required_fields = {'model','operation','model_definition','parameters','calibration_source'}
            owner_fields = required_fields | {'n_periods','solver','solution_path','saved_solution',
                'simulation','scenario','outcomes','welfare','evaluation','definitions','parameter_status'}
            if computation['requested_operation'] in ('simulate','counterfactual'):
                required_fields |= {'saved_solution','simulation'}
            else:
                required_fields.add('solution_path')
            if computation['requested_operation'] == 'counterfactual':
                required_fields.add('scenario')
        elif resource_id == 'research-dynamic' and method == 'finite_horizon_choice':
            required_fields = {'model', 'operation'}
            owner_fields = required_fields | {'params', 'options', 'adopted', 'data', 'estimation',
                'moments', 'fit_path', 'simulation', 'scenario', 'welfare', 'inference', 'parameter_status'}
            if 'fit_path' not in adopted_spec:
                required_fields |= {'params', 'options', 'adopted'}
            if not respy_simulation:
                required_fields |= {'data', 'estimation'}
                if algorithm == 'smm':
                    required_fields.add('moments')
            elif computation['requested_operation'] == 'counterfactual':
                required_fields.add('scenario')
        elif resource_id == 'research-dsge' and method == 'hank_one_asset':
            required_fields = {'model','operation'}
            owner_fields = required_fields | {'calibration_source','parameters','steady_state','saved_solution',
                'transition','horizon','inputs','shocks','outputs','solver_options','scenario','equilibrium_tolerance'}
            if 'saved_solution' not in adopted_spec:
                required_fields |= {'calibration_source','parameters','steady_state'}
            if computation['requested_operation'] != 'solve_steady_state':
                required_fields.add('horizon')
                required_fields.add('inputs' if ssj_operation == 'solve_jacobian' else 'shocks')
        elif resource_id == 'research-dsge' and native_function:
            required_fields = {'model','operation'}
            owner_fields = required_fields | {'yaml_model','calibration_source','calibration','discretization',
                'solver','validation','saved_solution','options','units','normalization'}
            if 'saved_solution' not in adopted_spec:
                required_fields |= {'yaml_model','calibration_source'}
            if computation['requested_operation'] == 'reuse_solution':
                required_fields.add('saved_solution')
        elif resource_id == 'research-dsge':
            owner_fields = required_fields = {'parameters','observations','horizon','simulation_paths','seed','technology_shock'}
        elif resource_id == 'research-markets':
            owner_fields = required_fields = {'model','baseline','scenario','unit','sources'}
        else:
            required_fields = {'model','options'}
            owner_fields = required_fields | {'data','adopted','scenario'}
            if method in ('replacement','latent_replacement','discrete_entry','dynamic_adoption_blp'):
                required_fields = required_fields | {'data'}
        execution_spec = {key:deepcopy(adopted_spec[key]) for key in owner_fields if key in adopted_spec}
        if resource_id != 'research-macro' and (resource_id != 'research-dsge' or native_function):
            execution_spec['model'] = model
        if method in ('lifecycle_choice','qse_commuting','qse_open_city','qse_imperfect_mobility','hank_one_asset','dolo_yaml') or method == 'stochastic_rbc' and native_function:
            execution_spec['operation'] = computation['requested_operation']
        if method == 'stochastic_rbc' and native_function:
            execution_spec.setdefault('options', {})['algorithm'] = 'dolo_time_iteration'
        if method == 'lifecycle_choice' and 'parameter_status' in facts:
            if execution_spec.get('parameter_status', facts['parameter_status']) != facts['parameter_status']:
                raise ValueError('lifecycle parameter_status must agree with the adopted specification')
            execution_spec['parameter_status'] = facts['parameter_status']
        if method == 'consumption_saving':
            execution_spec['income_process'] = income_process
            execution_spec['consumer_options'] = deepcopy(selected_options['consumer_options'])
            if computation['requested_operation'] == 'simulate' and 'simulation' not in execution_spec:
                unbound_inputs.append('simulation: adopted AgentCount, T_sim, seed and track_vars')
            if computation['requested_operation'] == 'counterfactual' and 'scenario' not in execution_spec:
                unbound_inputs.append('scenario.consumer_options: adopted changed parameters')
        if method == 'finite_horizon_choice':
            execution_spec['operation'] = computation['requested_operation']
            if respy_simulation:
                execution_spec.setdefault('simulation', {})['method'] = simulation_method
                execution_spec['parameter_status'] = facts['parameter_status']
            else:
                execution_spec.setdefault('estimation', {})['method'] = algorithm
        if resource_id == 'research-dynamic' and method != 'finite_horizon_choice' and 'options' in adopted_spec:
            execution_spec['options'] = deepcopy(selected_options)
            if method == 'replacement' and algorithm == 'smm' and 'smm' not in execution_spec['options']:
                unbound_inputs.append('options.smm: adopted seed, replications, initial_costs, bounds and tolerance')
        missing_fields = sorted(required_fields - execution_spec.keys())
        if method == 'consumption_saving':
            missing_fields.extend('consumer_options.'+key for key in
                ('T_cycle','CRRA','DiscFac','Rfree','LivPrb','PermGroFac','BoroCnstArt')
                if key not in execution_spec['consumer_options'])
            if isinstance(execution_spec.get('evaluation'),dict) and 'mNrm' not in execution_spec['evaluation']:
                missing_fields.append('evaluation.mNrm')
        if resource_id == 'research-numerics' and 'inputs' in execution_spec:
            if not isinstance(execution_spec['inputs'], dict):
                raise ValueError('adopted_specification.inputs must be an object')
            numerical_signature.bind_partial(**execution_spec['inputs'])
            missing_fields.extend('inputs.'+name for name, parameter in numerical_signature.parameters.items()
                if parameter.default is inspect.Parameter.empty and name not in execution_spec['inputs'])
        implementation['execution_specification'] = {
            'status':'inputs_required' if missing_fields or unbound_inputs else 'specified',
            'specification':execution_spec, 'missing_fields':missing_fields,
            'unbound_inputs':unbound_inputs, 'adoption_required':bool(changes),
            'schema_owner':{'resource_id':resource_id, 'entry_point':implementation['entry_point']},
            'validation':'The selected owner validates numerical inputs when its command executes.',
            'command':['python',*owner.split(' '),'SPEC.json','--output','RESULT.json']}
        if method == 'replacement':
            replacement_options = execution_spec.get('options', {})
            implementation['execution_components'] = [replacement_options.get('estimation_method', 'nfxp'),
                'baseline and scenario policy solution']
            if replacement_options.get('replacement_timing', 'reset_to_zero') == 'reset_to_zero':
                implementation['execution_components'] += ['ccp','finite-horizon solution']
            if 'smm' in execution_spec.get('options', {}):
                implementation['execution_components'].append('smm')
    return {'result_format_version':1,'status':'design_change' if changes else 'selected','question':request['question'],
        'estimand':request['estimand'],'identification':request['identification'],
        'method':method,'engine':engine,'entry_point':owner,'determining_conditions':conditions,
        'forward_options':forward_options,'design_contract':proposed_contract,
        'adopted_specification':adopted_spec,'estimand_relation':relation,
        'design_change':{'adopted_method':adopted,'selected_method':method,'changes':changes,'estimand_relation':relation} if changes else None,
        'requested_design':{k:request[k] for k in ('outcome_scale','data_structure','treatment_pattern','dependence')},
        'method_selection':selection,'executed':False}


def select_method(request, *, spec_path=None, stage='contract', task=None, root=None, store='.agents/state/team.json', restore=False):
    """Select through the existing scientific owner and attach current-stage knowledge."""
    require(isinstance(request, dict), 'Method selection request must be an object')
    decisions = request.get('research_decisions', request.get('adopted_specification', {}).get('research_decisions', {}))
    require(isinstance(decisions, dict) and not set(decisions)-{'formulation','interpretation'}, 'Invalid research decision references')
    scientific_request = {k:v for k,v in request.items() if k not in ('research_decisions','knowledge_ids')}
    result = _select_method(scientific_request, spec_path=spec_path)
    resources = json.loads((ROOT / ('RESOURCES.json' if FLAT_EXPORT else 'registry/resources.json')).read_text())['resources']
    placements = json.loads((ROOT / ('PLACEMENTS.json' if FLAT_EXPORT else 'registry/placements.json')).read_text())['resources']
    layout = 'export_alias' if FLAT_EXPORT else 'deployment_path' if ROOT.name == '.agents' else 'source_path'
    rid = 'knowledge-retrieval'
    relative = resources[rid]['source_path'] if layout == 'source_path' else placements[rid][layout]
    path = (ROOT.parent if ROOT.name == '.agents' else ROOT) / relative
    module_spec = importlib.util.spec_from_file_location('method_knowledge', path)
    knowledge = importlib.util.module_from_spec(module_spec); module_spec.loader.exec_module(knowledge)
    reader = knowledge.Reader(knowledge.BASE)
    selection = result['method_selection']
    retained = {}
    base = Path(root or (Path(spec_path).resolve().parent if spec_path else Path.cwd()))
    for kind, ref in decisions.items():
        require(isinstance(ref, dict) and {'path','sha256'} <= set(ref) and
                not set(ref)-{'path','sha256','candidate_id'}, 'Decision reference needs its path and hash')
        record = json.loads(file_bytes(base, ref['path'], ref['sha256']))
        for source in record.get('sources', {}).values():
            file_bytes(base, source['path'], source['sha256'])
        if kind == 'formulation':
            value = record.get('formulation')
            definition = record.get('definition', {})
            if ref.get('candidate_id'):
                candidate = next((x for x in record.get('candidates', []) if x['id']==ref['candidate_id']), {})
                value = candidate.get('formulation')
                if value:
                    definition = {'estimand':value['selected_dimensions']['estimand'],
                                  'population':value['selected_dimensions']['population'],
                                  'identification':value['selected_dimensions']['identifying_variation']}
                    if 'selected_question' in value:
                        definition['question'] = value['selected_question']
            require(value is not None, 'The referenced formulation has not been applied')
        else:
            value = record.get('result_interpretation')
            require(value is not None, 'The referenced result has no applied interpretation')
            definition = value['adopted_definition']
        for key, adopted in definition.items():
            require(scientific_request.get(key, scientific_request.get('adopted_specification', {}).get(key)) == adopted,
                    'Decision differs from the adopted '+key)
        retained[kind] = {'reference':dict(ref), 'decision':value}
    if retained:
        selection['research_decisions'] = retained
    design = selection.get('reason', {}).get('design', request.get('design'))
    contract_id = (selection.get('model_contract') or {}).get('id')
    model = request.get('structural_model', request.get('adopted_specification', {}).get('structural_model', result.get('method')))
    cache, call = {}, None
    if task:
        call = knowledge.state_command(Path(root or Path.cwd()), store)
        current = call('show', task)
        require(restore or current['status'] == 'running', 'Task-bound knowledge requires a running task; use --restore for saved work')
        cache, external = knowledge.task_knowledge(current)
        reader = knowledge.Reader(knowledge.BASE, external)
    delivered = reader.for_method(result.get('method'), design, stage, model=model, contract_id=contract_id,
                                  implementation=selection['official_implementation'].get('implementation'),
                                  target=selection.get('target', {}).get('kind'),
                                  context=request.get('conditions', request.get('adopted_specification', {}).get('conditions')),
                                  cached=None if restore else cache, additional_ids=request.get('knowledge_ids', ()))
    if call and not restore:
        for unit in delivered['units']:
            if not unit['reused'] and not unit['id'].startswith('external:'):
                call('output', task, 'knowledge:'+unit['id'], '--kind', 'object', '--value',
                     json.dumps({'version':unit['version'], 'body':unit['body']}, ensure_ascii=False), '--no-dependencies')
    selection['stage_knowledge'] = delivered
    if stage == 'entry' and result['status'] == 'selected':
        result['status'] = 'knowledge_deferred'
        selection['adoption_status'] = 'pending_contract_knowledge'
    if delivered['status'] in ('source_required','read_blocked') and result['status'] == 'selected':
        result['status'] = 'knowledge_required'
    if delivered.get('plan'):
        selection['knowledge_plan'] = {k:v for k,v in delivered['plan'].items() if k != 'contracts'}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['assess', 'propose', 'variables', 'select', 'interpret', 'formulate'])
    parser.add_argument('contract', type=Path)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stage', choices=['entry','contract','compose','review','finalize'], default='contract')
    parser.add_argument('--task')
    parser.add_argument('--restore', action='store_true', help='Restore current-stage knowledge after actual context loss')
    parser.add_argument('--store', default='.agents/state/team.json')
    args = parser.parse_args()
    require(args.output.resolve() != args.contract.resolve(), 'Output must differ from its input contract')
    raw = args.contract.read_bytes()
    contract = json.loads(raw)
    require(isinstance(contract, dict), 'Contract must be an object')
    result = (select_method(contract, spec_path=args.contract, stage=args.stage, task=args.task, root=args.root, store=args.store, restore=args.restore) if args.command == 'select' else
              formulate_problem(contract, args.root.resolve()) if args.command == 'formulate' else
              interpret_result(contract, args.root.resolve()) if args.command == 'interpret' else
              variable_design(contract) if args.command == 'variables' else
              (assess if args.command == 'assess' else propose)(contract, args.root.resolve()))
    protected = set()
    if isinstance(contract.get('adopted_design'), dict):
        path = Path(contract['adopted_design']['path'])
        protected.add((path if path.is_absolute() else args.root / path).resolve())
    for group in ('sources', 'datasets'):
        for reference in result.get(group, {}).values():
            if isinstance(reference, dict) and isinstance(reference.get('path'), str):
                path = Path(reference['path'])
                protected.add((path if path.is_absolute() else args.root / path).resolve())
    if isinstance(contract.get('corpus'), dict) and isinstance(contract['corpus'].get('path'), str):
        path = Path(contract['corpus']['path'])
        protected.add((path if path.is_absolute() else args.root / path).resolve())
    require(args.output.resolve() not in protected, 'Output must differ from its source and dataset inputs')
    result['contract_sha256'] = hashlib.sha256(raw).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=args.output.parent, delete=False) as stream:
            temp = Path(stream.name)
            json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
        temp.replace(args.output)
    finally:
        if temp:
            temp.unlink(missing_ok=True)
    summary = {'output': str(args.output.resolve())}
    summary.update({'method': result['method']} if args.command == 'select' else
                   {'analyses': len(result['analyses'])} if args.command == 'variables' else
                   {'status': result['status']} if args.command in ('interpret','formulate') else
                   {'selected_candidate': result['selected_candidate']})
    print(json.dumps(summary))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print('error: ' + str(exc), file=sys.stderr)
        sys.exit(1)
