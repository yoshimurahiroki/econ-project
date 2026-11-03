#!/usr/bin/env python3
"""Evaluate an owner-adopted research comparison against source spans and CSV data."""
import argparse
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

for parent in Path(__file__).resolve().parents:
    if (parent / 'harness' / 'paragraph.py').is_file():
        sys.path.insert(0, str(parent / 'harness'))
        sys.path.insert(0, str(parent / 'skills/econ-literature/scripts'))
        break
import paragraph

DIMENSIONS = ('mechanism', 'estimand', 'identifying_variation', 'measurement', 'population')


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
    require(isinstance(reference, dict) and set(reference) == {'path', 'sha256', 'proposition_ids'},
            'Corpus reference requires path, sha256 and selected proposition_ids')
    path = Path(reference['path'])
    selected = research_search.load_corpus_record(path if path.is_absolute() else root / path,
        reference['sha256'], proposition_ids=reference['proposition_ids'])
    sources = dict(sources or {})
    for key, source in selected['design_sources'].items():
        require(key not in sources or sources[key] == source, 'Conflicting selected source identity: ' + key)
        sources[key] = source
    return sources, selected


def evidence(refs, sources, label):
    require(isinstance(refs, list) and refs, label + ' requires source evidence')
    for ref in refs:
        require(isinstance(ref, dict) and ref.get('source_id') in sources, label + ' has unknown source')
        paragraph._span(ref, sources[ref['source_id']]['text'], label)
    return refs


def dimensions(row, label):
    require(isinstance(row, dict) and all(isinstance(row.get(k), str) and row[k].strip() for k in DIMENSIONS),
            label + ' requires all five economic dimensions')


def dataset(root, name, spec, sources):
    require(isinstance(spec, dict) and all(k in spec for k in ('path', 'sha256', 'unit', 'population', 'period', 'documentation', 'grain', 'definition_versions')),
            'Dataset requires path, hash, unit, population, period, documentation, grain and definition versions: ' + name)
    require(all(isinstance(spec[k], str) and spec[k].strip() for k in ('unit', 'population')), 'Dataset unit and population required')
    require(isinstance(spec['period'], dict) and type(spec['period'].get('start')) is int and type(spec['period'].get('end')) is int and spec['period']['start'] <= spec['period']['end'], 'Invalid documented period')
    require(isinstance(spec['definition_versions'], dict) and spec['definition_versions'] and all(isinstance(k, str) and k and isinstance(v, str) and v for k, v in spec['definition_versions'].items()), 'Dataset definition versions required')
    evidence(spec['documentation'], sources, 'Dataset documentation')
    raw = file_bytes(root, spec['path'], spec['sha256'])
    text = raw.decode('utf-8-sig').splitlines(keepends=True)
    reader = csv.DictReader(text)
    require(reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames)), 'CSV requires distinct named columns')
    rows = list(reader)
    require(all(None not in row for row in rows), 'CSV contains malformed rows')
    return {'id': name, 'path': spec['path'], 'sha256': spec['sha256'], 'definition_versions': spec['definition_versions'],
            'unit': spec['unit'], 'population': spec['population'], 'period': spec['period'],
            'documentation': spec['documentation'], 'grain': spec['grain'], 'fields': reader.fieldnames, 'rows': rows,
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
                               'closest_answers': closest, 'judgment': judgment, 'dataset': data['id'],
                               'comparison': [{'closest_id': answer['id'], 'dimensions':
                                               {key: {'candidate': item['dimensions'][key], 'closest_answer': answer['dimensions'][key],
                                                      'owner_identified_change': key in changes} for key in DIMENSIONS}} for answer in closest],
                               'dataset_sha256': data['sha256'], 'definition_versions': data['definition_versions'],
                               'requirements': item['requirements'], 'fit': assessment, 'next_operation': item['next_operation']}
    selected = next((key for key in ranking['order'] if results[key]['fit']['feasible']), None)
    return {'selection': ranking, 'selected_candidate': selected, 'next_operation': results[selected]['next_operation'] if selected else None,
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['assess', 'propose'])
    parser.add_argument('contract', type=Path)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raw = args.contract.read_bytes()
    contract = json.loads(raw)
    result = (assess if args.command == 'assess' else propose)(contract, args.root.resolve())
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
    print(json.dumps({'output': str(args.output.resolve()), 'selected_candidate': result['selected_candidate']}))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print('error: ' + str(exc), file=sys.stderr)
        sys.exit(1)
