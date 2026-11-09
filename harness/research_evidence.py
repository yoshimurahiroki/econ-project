#!/usr/bin/env python3
"""Bind a selected manuscript to its actual sources, results and model code.

The host supplies and retains the substantive judgments; this operation checks
the identities and exact correspondences on which those judgments depend.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/econ-literature/scripts'))
import paragraph
import state


class EvidenceError(ValueError):
    """A selected evidence binding cannot be verified."""


def require(condition, message):
    if not condition:
        raise EvidenceError(message)


def text(value, context):
    require(isinstance(value, str) and value.strip(), context + ' must contain text')
    return value


def obj(value, context):
    require(isinstance(value, dict), context + ' must be an object')
    return value


def rows(value, context):
    require(isinstance(value, list), context + ' must be a list')
    return value


def file_bytes(root, ref, context, *, cache=None):
    obj(ref, context)
    path = state.relative(root, text(ref.get('path'), context + '.path'))
    expected = text(ref.get('sha256'), context + '.sha256')
    files = cache.setdefault('files', {}) if cache is not None else {}
    if path not in files:
        raw = (root / path).read_bytes()
        files[path] = (raw, paragraph.sha(raw))
    raw, digest = files[path]
    require(digest == expected, context + ' hash differs: ' + path)
    if 'content_sha256' in ref:
        decoded_hashes = cache.setdefault('decoded_hashes', {}) if cache is not None else {}
        if digest not in decoded_hashes:
            try:
                content = gzip.decompress(raw) if raw.startswith(b'\x1f\x8b') else raw
            except (OSError, EOFError, zlib.error) as exc:
                raise EvidenceError(context + ': invalid gzip content') from exc
            decoded_hashes[digest] = paragraph.sha(content)
        require(decoded_hashes[digest] == ref['content_sha256'],
                context + ' decoded content hash differs: ' + path)
    return raw


def result_json(root, ref, context, *, cache):
    """Read each pinned result once during this binding operation."""
    raw = file_bytes(root, ref, context, cache=cache)
    results = cache.setdefault('results', {})
    key = ref['sha256']
    if key not in results:
        results[key] = read_json(raw, context)
    return results[key]


def utf8(raw, context):
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise EvidenceError(context + ' must be UTF-8') from exc


def read_json(raw, context):
    try:
        if raw.startswith(b'\x1f\x8b'):
            raw = gzip.decompress(raw)
        data = state.gate.parse_json(raw)
        if isinstance(data, dict) and data.get('schema') == 'research-artifact-registry-v1':
            from research_artifacts import expand_registry
            return expand_registry(data)
        return data
    except state.gate.GateError as exc:
        raise EvidenceError(context + ': ' + str(exc)) from exc
    except (OSError, EOFError, zlib.error) as exc:
        raise EvidenceError(context + ': invalid gzip JSON') from exc


def lookup(data, keys, context):
    """Resolve object keys and zero-based array indices in a saved result."""
    require(isinstance(keys, list) and keys and all(
        (isinstance(key, str) and key) or (type(key) is int and key >= 0) for key in keys),
        context + ' needs a nonempty JSON path of object keys and nonnegative array indices')
    for key in keys:
        if isinstance(key, str):
            require(isinstance(data, dict) and key in data, context + ' missing JSON key: ' + key)
        else:
            require(isinstance(data, list) and key < len(data),
                    context + ' missing JSON array index: ' + str(key))
        data = data[key]
    return data


def check_registered_inputs(result, root, key=None, *, cache=None):
    """Recheck the selected producing record, or the whole registry when required."""
    if not isinstance(result, dict) or result.get('schema') != 'research-artifact-registry-v1':
        return
    if key and key[0] == 'items':
        require(len(key) > 1 and key[1] in obj(result.get('items'), 'gallery items'),
                'selected saved gallery item is missing')
        return
    records = obj(result.get('records'), 'registry records')
    if key and len(key) > 1 and key[0] in {'statistics', 'records'}:
        name = key[1].split('.', 1)[0] if key[0] == 'statistics' else key[1]
        require(name in records, 'selected registry source is missing')
        records = {name: records[name]}
    for name, record in records.items():
        refs = obj(obj(record, 'registry record').get('references'), 'registry references')
        require('result' in refs and 'code' in refs, 'registry source needs result and code references')
        for kind, reference in refs.items():
            file_bytes(root, reference, f'registry {name} {kind}', cache=cache)


def check_identity(result, keys, adopted, context):
    obj(keys, context + '.identity_keys')
    require(set(keys) == set(adopted), context + ' must bind every adopted identity')
    for name, expected in adopted.items():
        actual = lookup(result, keys[name], context + '.' + name)
        require(type(actual) is type(expected) and actual == expected, context + ' identity differs: ' + name)


def check_judgment(value, context, *, require_support=False):
    obj(value, context)
    text(value.get('reviewer'), context + '.reviewer')
    text(value.get('rationale'), context + '.rationale')
    require(value.get('decision') in {'supported', 'revision-required', 'unresolved'},
            context + ' decision must name the actual assessment')
    if require_support:
        require(value['decision'] == 'supported', context + ' needs support for this coverage account')


def span(value, original, context):
    return paragraph._span(value, original, context)


def literature_bindings(contract, root):
    """Resolve selected literature once, using the original source-corpus owner."""
    contract = copy.deepcopy(contract)
    reference = contract.get('corpus')
    if reference is None:
        return contract, None
    import research_search
    require(isinstance(reference, dict) and {'path', 'sha256', 'proposition_ids'} <= reference.keys()
            and set(reference) <= {'path', 'sha256', 'proposition_ids', 'as_of'},
            'corpus requires path, sha256 and selected proposition_ids; as_of is optional')
    path = root / state.relative(root, reference['path'])
    selected = research_search.load_corpus_record(path, reference['sha256'],
                                                 proposition_ids=reference['proposition_ids'],
                                                 as_of=reference.get('as_of'))
    by_id = {row['document_id'] + ':' + row['id']: row for row in selected['propositions']}
    sources = contract.setdefault('sources', {})
    for key, source in selected['design_sources'].items():
        local = Path(source['path'])
        local = local.relative_to(root) if local.is_absolute() else local
        value = {**source, 'path': state.relative(root, local.as_posix()), 'metadata': {'identities': {}}}
        require(key not in sources or sources[key] == value, 'conflicting literature source identity: ' + key)
        sources[key] = value
    for claim in contract.get('claims', []):
        anchors = claim.setdefault('sources', [])
        for use in claim.get('literature', []):
            require(isinstance(use, dict) and set(use) == {'id', 'proposition_sha256'} and use['id'] in by_id,
                    'claim literature anchor must select a loaded proposition and its hash')
            source = by_id[use['id']]
            require(use['proposition_sha256'] == source['proposition_sha256'], 'claim literature proposition changed')
            for evidence in source['evidence']:
                anchor = {'id': evidence['source_id'],
                          'span': {key: evidence[key] for key in ('start', 'end', 'quote')}}
                if anchor not in anchors:
                    anchors.append(anchor)
    return contract, selected


def claim_coverage(manuscript, claims, coverage=None):
    """Locate review candidates; the owner judges materiality and unmarked claims."""
    coverage = coverage or {}
    scopes = coverage.get('spans', [{'start': 0, 'end': len(manuscript), 'quote': manuscript}])
    accounts = coverage.get('claim_accounts', [])
    for account in accounts:
        span(account['target'], manuscript, 'claim account')
        check_judgment(account['judgment'], 'claim account judgment', require_support=True)
    patterns = {
        'citation': r'\\cite\w*\{|\[@[^\]]+\]|\([^\n)]*\b(?:19|20)\d{2}[a-z]?[^\n)]*\)',
        'quantity': paragraph.QUANTITY.pattern,
        'inference': r'\b(?:confidence|significan\w*|estimat\w*|standard errors?|p[- ]values?)\b|信頼区間|推定|有意',
        'causal': r'\b(?:caus\w*|effect|impact|identif\w*)\b|因果|効果|識別',
        'theory': r'\b(?:equilibrium|welfare|optimal|theorem|proposition|implies)\b|均衡|厚生|最適|定理|命題',
    }
    candidates, seen = [], set()
    for scope in scopes:
        span(scope, manuscript, 'claim coverage scope')
        for match in re.finditer(r'.+?(?:[。！？]|[.!?](?=\s|$)|\n|$)', scope['quote'], re.S):
            quote = match.group().strip()
            if not quote:
                continue
            start = scope['start'] + match.start() + len(match.group()) - len(match.group().lstrip())
            end = start + len(quote)
            if (start, end) in seen:
                continue
            seen.add((start, end))
            signals = [key for key, pattern in patterns.items() if re.search(pattern, quote, re.I)]
            if not signals:
                continue
            target = {'start': start, 'end': end, 'quote': quote}
            registered = [claim['id'] for claim in claims
                          if claim['target']['start'] <= start and end <= claim['target']['end']]
            accounted = any(row['target']['start'] <= start and end <= row['target']['end'] for row in accounts)
            candidates.append({'target': target, 'signals': signals, 'claim_ids': registered, 'accounted': accounted})
    missing = [row for row in candidates if not row['claim_ids'] and not row['accounted']]
    return {'candidates': candidates, 'unregistered': missing, 'semantic_completeness': 'owner-judgment-required'}


def response_draft(settings, root, packet, *, writing=None):
    """Compose a response from the assessed revision through the existing writer."""
    obj(settings, 'response_draft')
    language = settings.get('language', 'en')
    require(language in {'ja', 'en'}, 'response_draft language must be ja or en')
    require(packet['status'] == 'reviewed', 'response draft requires a completed current assessment')
    findings = {row['id']: row for row in packet['review']['findings']}
    selected = settings.get('finding_ids', list(findings))
    require(isinstance(selected, list) and selected and all(isinstance(key, str) for key in selected)
            and len(selected) == len(set(selected)) and set(selected) <= set(findings),
            'response_draft must select distinct current finding IDs')
    claims = {row['id']: row for row in packet['claims']}
    manuscript = packet['manuscript_text']
    labels = ('査読コメント', '回答', '本文', '根拠') if language == 'ja' else (
        'Referee comment', 'Response', 'Manuscript', 'Evidence')
    entries = []
    for ident in selected:
        finding = findings[ident]
        require(finding['decision'] in {'supported', 'removed'},
                'response draft requires a resolved finding: ' + ident)
        origin = obj(finding.get('origin'), 'finding origin')
        original = utf8(file_bytes(root, origin['manuscript'], 'original manuscript'), 'original manuscript')
        span(origin['target'], original, 'original passage')
        comment = origin['rationale']
        if origin.get('comment'):
            ref = origin['comment']
            comment = span(ref['span'], utf8(file_bytes(root, ref, 'referee comment'), 'referee comment'),
                           'referee comment')
        current = claims.get(finding['claim_id'])
        require(current is not None or finding['decision'] == 'removed',
                'supported response finding requires its current claim: ' + ident)
        changes = copy.deepcopy(finding.get('changes', []))
        if current and current['target']['quote'] != origin['target']['quote']:
            require(changes and any(row['start'] < current['target']['end']
                                    and current['target']['start'] < row['end'] for row in changes),
                    'changed claim requires its current revised passage: ' + ident)
        passages = changes or ([copy.deepcopy(current['target'])] if current else [])
        for passage in passages:
            span(passage, manuscript, 'response manuscript passage')
        references = copy.deepcopy(finding['references'])
        for ref in references:
            raw = file_bytes(root, ref, 'response evidence')
            if 'span' in ref:
                span(ref['span'], utf8(raw, 'response evidence'), 'response evidence')
        entry = {'finding_id': ident, 'claim_id': finding['claim_id'],
                 'criterion': next(copy.deepcopy(row) for row in packet['review']['criteria']
                                   if row['id'] == finding['criterion_id']),
                 'decision': finding['decision'], 'comment': comment,
                 'origin': copy.deepcopy(origin), 'rationale': finding['rationale'],
                 'manuscript': copy.deepcopy(packet['manuscript']), 'passages': passages,
                 'changes': changes, 'references': references,
                 'bindings': {key: copy.deepcopy(packet['binding_context'][key])
                              for key in current['bindings']} if current else {}}
        entries.append(entry)
    execution = None
    if writing is not None:
        obj(writing, 'response writing')
        mode = writing.get('mode', 'compose')
        require(mode in {'compose', 'revise', 'translate'}, 'response writing uses compose, revise or translate')
        request = text(writing.get('request'), 'response writing request')
        source_ids = {anchor['id'] for entry in entries
                      for anchor in claims.get(entry['claim_id'], {}).get('sources', [])}
        payload = {'original_request': request, 'language': language,
                   'adopted': copy.deepcopy(packet['adopted']),
                   'manuscript': copy.deepcopy(packet['manuscript']),
                   'entries': copy.deepcopy(entries),
                   'source_context': {key: copy.deepcopy(packet['source_context'][key]) for key in sorted(source_ids)},
                   'output_contract': {'responses': 'Map each finding_id to its completed response text. '
                       'Answer the economic issue using the assessed decision, actual revised passages, '
                       'evidence and manuscript location. Preserve quantities, definitions and citations.'}}
        task = paragraph._task('econ-writing:' + mode, payload,
                              paragraph.instruction_packet(request, writing['rules']))
        result, execution = paragraph.invoke_host(
            writing['host'], task, writing['observe'],
            execution_kind=writing.get('execution_kind', 'single-agent-sequential'),
            author_id=writing.get('author_id'))
        responses = obj(result.get('responses'), 'written responses')
        require(set(responses) == set(selected), 'written responses must cover the selected findings exactly')
        for entry in entries:
            entry['response'] = text(responses[entry['finding_id']], 'written response')
    sections = []
    for entry in entries:
        body = [f"## {entry['finding_id']}", f'**{labels[0]}**', entry['comment'],
                f'**{labels[1]}**', entry.get('response', entry['rationale'])]
        if writing is None and entry['passages']:
            body.append(f'**{labels[2]}**')
            for passage in entry['passages']:
                body.append('\n'.join('> ' + line for line in passage['quote'].split('\n')))
        quoted_evidence = [ref for ref in entry['references'] if 'span' in ref]
        if writing is None and quoted_evidence:
            body.append(f'**{labels[3]}**')
            for ref in quoted_evidence:
                body.extend([ref['path'], '\n'.join('> ' + line for line in ref['span']['quote'].split('\n'))])
        sections.append('\n\n'.join(body))
    draft = {'language': language, 'manuscript': copy.deepcopy(packet['manuscript']),
             'evidence_sha256': packet['evidence_sha256'], 'entries': entries,
             'text': '\n\n'.join(sections) + '\n'}
    if execution is not None:
        draft['execution'] = execution
    return draft


def review_round(contract, root, packet, *, writing=None):
    """Bind requested review rounds to existing evidence results, never release authority."""
    settings = obj(contract.get('review', {}), 'review')
    if not settings:
        return packet
    previous_ref = settings.get('previous')
    previous = read_json(file_bytes(root, previous_ref, 'previous review'), 'previous review') if previous_ref else None
    if previous:
        require(previous.get('status') == 'reviewed', 'previous review must contain a completed evidence assessment')
        require(previous['adopted'] == packet['adopted'], 're-review cannot silently change the adopted research specification')
    criteria = settings.get('criteria', previous['review']['criteria'] if previous else None)
    require(isinstance(criteria, list) and criteria, 'review requires fixed initial criteria')
    criterion_ids = set()
    for item in criteria:
        text(item.get('id'), 'criterion id'); text(item.get('text'), 'criterion text')
        require(item['id'] not in criterion_ids, 'duplicate review criterion')
        criterion_ids.add(item['id'])
    if previous:
        require(criteria == previous['review']['criteria'], 're-review criteria changed')
    fingerprints = packet['claim_fingerprints']
    old_fingerprints = previous.get('claim_fingerprints', {}) if previous else {}
    reusable = {key for key in fingerprints if fingerprints[key] == old_fingerprints.get(key)}
    packet['changes'] = {'reusable_claims': sorted(reusable),
                         'claims_to_reassess': sorted(set(fingerprints) - reusable),
                         'removed_claims': sorted(set(old_fingerprints) - set(fingerprints))}
    response_after = settings.get('response_after')
    if response_after or 'author_response' in settings:
        require('response_draft' not in settings, 'draft a response from the current assessment before comparing an author response')
        require(response_after and 'author_response' in settings and 'assessment' not in settings,
                'author response requires a separately saved completed evidence assessment')
        assessed = read_json(file_bytes(root, response_after, 'evidence-first review'), 'evidence-first review')
        require(assessed.get('status') == 'reviewed' and assessed.get('evidence_sha256') == packet['evidence_sha256']
                and assessed['review']['criteria'] == criteria, 'author response requires the current evidence-first review')
        response = settings['author_response']
        body = utf8(file_bytes(root, response, 'author response'), 'author response')
        packet.update(status='response-comparison-required', review=assessed['review'],
                      evidence_first_review=response_after, author_response={**response, 'text': body})
        return packet
    assessment = settings.get('assessment')
    supplied = rows(obj(assessment, 'assessment').get('findings'), 'review findings') if assessment is not None else []
    replacement_ids = {row.get('id') for row in supplied}
    old_findings = {row['id']: row for row in previous['review']['findings']} if previous else {}
    findings = []
    for row in old_findings.values():
        if row['id'] in replacement_ids:
            continue
        if row['claim_id'] not in reusable:
            if (row['decision'] != 'removed' or row['claim_id'] in fingerprints or not row.get('origin')
                    or row['origin']['target']['quote'] in packet['manuscript_text']):
                continue
        reused = {**copy.deepcopy(row), 'reused_from': previous_ref}
        old_target = next((c['target'] for c in previous['claims'] if c['id'] == row['claim_id']), None)
        current_target = next((c['target'] for c in packet['claims'] if c['id'] == row['claim_id']), None)
        if old_target:
            reused.setdefault('origin', {'manuscript': copy.deepcopy(previous['manuscript']),
                                         'target': copy.deepcopy(old_target), 'rationale': row['rationale'],
                                         **({'comment': copy.deepcopy(row['comment'])} if row.get('comment') else {})})
        for changed in reused.get('changes', []):
            start, end = changed['start'], changed['end']
            overlaps = True
            if old_target and current_target:
                shift = current_target['start'] - old_target['start']
                start, end = start + shift, end + shift
                overlaps = old_target['start'] < changed['end'] and changed['start'] < old_target['end']
            if not (overlaps and start >= 0 and packet['manuscript_text'][start:end] == changed['quote']):
                start = packet['manuscript_text'].find(changed['quote'])
                require(start >= 0 and packet['manuscript_text'].find(changed['quote'], start + 1) < 0,
                        'reused revised passage requires its current span: ' + row['id'])
                end = start + len(changed['quote'])
            changed.update(start=start, end=end)
        findings.append(reused)
    if assessment is not None:
        reviewer = text(assessment.get('reviewer'), 'reviewer')
        supplied_ids = set()
        for row in supplied:
            ident = text(row.get('id'), 'finding id')
            require(ident not in supplied_ids, 'duplicate review finding')
            supplied_ids.add(ident)
            require(row.get('criterion_id') in criterion_ids, 'finding must use the fixed review criteria')
            claim_id = row.get('claim_id')
            require(claim_id in fingerprints or claim_id in old_fingerprints, 'finding must identify a reviewed claim')
            require(row.get('decision') in {'supported', 'revision-required', 'unresolved', 'removed'}, 'invalid review finding decision')
            text(row.get('rationale'), 'finding rationale')
            references = rows(row.get('references'), 'finding references')
            require(references, 'finding requires actual evidence references')
            for reference in references:
                raw = file_bytes(root, reference, 'finding reference')
                if 'span' in reference:
                    span(reference['span'], utf8(raw, 'finding reference'), 'finding reference')
            for changed in row.get('changes', []):
                span(changed, packet['manuscript_text'], 'revised passage')
            if ident in old_findings:
                require(all(row[key] == old_findings[ident][key] for key in ('claim_id', 'criterion_id')),
                        'a re-review finding cannot replace its initial target or criterion')
            old = old_findings.get(ident)
            origin = copy.deepcopy(old.get('origin')) if old else None
            if origin is None:
                source = previous if old or claim_id not in fingerprints else packet
                original_claim = next(c for c in source['claims'] if c['id'] == claim_id)
                origin = {'manuscript': copy.deepcopy(source['manuscript']),
                          'target': copy.deepcopy(original_claim['target']),
                          'rationale': (old or row)['rationale']}
                if (old or row).get('comment'):
                    origin['comment'] = copy.deepcopy((old or row)['comment'])
            if 'comment' in row:
                require(not old or row['comment'] == origin.get('comment'), 'initial referee comment changed')
                comment = row['comment']
                span(comment['span'], utf8(file_bytes(root, comment, 'referee comment'), 'referee comment'),
                     'referee comment')
            if row['decision'] == 'removed':
                require(claim_id not in fingerprints and previous is not None,
                        'removed finding requires an actually removed claim')
                old_claim = next(c for c in previous['claims'] if c['id'] == claim_id)
                require(old_claim['target']['quote'] not in packet['manuscript_text'], 'removed claim remains in manuscript')
            findings = [old for old in findings if old['id'] != ident]
            findings.append({**copy.deepcopy(row), 'reviewer': reviewer, 'origin': origin})
        if previous:
            require(set(old_findings) <= {row['id'] for row in findings}, 're-review omitted an initial finding')
    covered = {row['claim_id'] for row in findings}
    retained = set(old_findings) <= {row['id'] for row in findings}
    packet['review'] = {'criteria': copy.deepcopy(criteria), 'previous': previous_ref, 'findings': findings}
    packet['status'] = 'reviewed' if set(fingerprints) <= covered and findings and retained else 'review-required'
    if 'response_draft' in settings:
        packet['response_draft'] = response_draft(settings['response_draft'], root, packet, writing=writing)
    return packet


def review(contract, root, *, claim_ids=None, writing=None):
    """Supply the actual claim and source context for the selected specialist judgment."""
    root = Path(root).resolve(strict=True)
    cache = {}
    if writing is not None:
        require(claim_ids is None and 'response_draft' in contract.get('review', {}),
                'response writing requires the current complete review and response_draft selection')
    if claim_ids is not None:
        require(isinstance(claim_ids, list) and claim_ids and len(set(claim_ids)) == len(claim_ids)
                and set(claim_ids) <= {c['id'] for c in contract.get('claims', [])}, 'Select existing distinct claim IDs')
        contract = copy.deepcopy(contract)
        contract['claims'] = [c for c in contract['claims'] if c['id'] in claim_ids]
        if 'corpus' in contract:
            contract['corpus']['proposition_ids'] = list(dict.fromkeys(
                r['id'] for c in contract['claims'] for r in c.get('literature', [])))
            if not contract['corpus']['proposition_ids']:
                contract.pop('corpus')
    contract, selected = literature_bindings(contract, root)
    manuscript = utf8(file_bytes(root, contract['manuscript'], 'manuscript', cache=cache), 'manuscript')
    used_sources = {anchor['id'] for claim in contract.get('claims', []) for anchor in claim.get('sources', [])}
    sources = {key: utf8(file_bytes(root, ref, 'source ' + key, cache=cache), 'source ' + key)
               for key, ref in contract.get('sources', {}).items() if key in used_sources}
    claims, source_context, seen = [], {}, set()
    for claim in rows(contract.get('claims'), 'claims'):
        require(isinstance(claim.get('id'), str) and claim['id'] and claim['id'] not in seen,
                'review claim IDs must be distinct')
        seen.add(claim['id'])
        span(claim['target'], manuscript, 'review claim')
        original = []
        for anchor in claim.get('sources', []):
            require(anchor['id'] in sources, 'unknown review source')
            span(anchor['span'], sources[anchor['id']], 'review source')
            if 'role' in anchor:
                text(anchor['role'], 'source evidence role')
            original.append(copy.deepcopy(anchor))
            source_context[anchor['id']] = {**contract['sources'][anchor['id']], 'text': sources[anchor['id']]}
        binding_ids = claim.get('bindings', [])
        require(isinstance(binding_ids, list) and all(isinstance(key, str) for key in binding_ids), 'claim bindings must be IDs')
        require(original or binding_ids, 'review needs the actual source or result context')
        claims.append({'id': claim['id'], 'target': claim['target'], 'sources': original,
                       'bindings': binding_ids, 'literature': claim.get('literature', [])})
    binding_context = {}
    needed = {key for claim in claims for key in claim['bindings']}
    for kind in ('numbers', 'models', 'mappings'):
        for row in contract.get(kind, []):
            if row['id'] not in needed:
                continue
            require(row['id'] not in binding_context, 'duplicate result binding')
            ref = row['result']
            data = result_json(root, ref, 'review result', cache=cache)
            key = ref.get('key') or ref.get('residual_key') or (ref.get('quantity') or {}).get('key')
            check_registered_inputs(data, root, key, cache=cache)
            check_identity(data, ref.get('identity_keys', {}), contract.get('adopted', {}), 'review result')
            context = {'kind': kind, 'binding': copy.deepcopy(row), 'selected_result': lookup(data, key, 'review result') if key else None}
            context['producing_inputs'] = {name: data[name] for name in
                ('spec_sha256', 'data_sha256', 'script_sha256', 'provenance', 'engine') if name in data}
            if data.get('schema') == 'research-artifact-registry-v1' and key:
                source_id = key[1].split('.', 1)[0] if key[0] == 'statistics' else key[1]
                record = data['records'][source_id]
                context['producing_inputs'] = {name: value for name, value in record.items()
                    if name not in {'source_result', 'references', 'quantity_origins'}}
                context['producing_inputs']['references'] = {name: ref for name, ref in record['references'].items()
                                                            if name != 'result'}
            if 'code' in row:
                code = utf8(file_bytes(root, row['code'], 'review code', cache=cache), 'review code')
                context['code_quote'] = span(row['code']['span'], code, 'review code')
            binding_context[row['id']] = context
    require(needed <= set(binding_context), 'claim refers to an unknown result binding')
    fingerprints = {}
    for claim in claims:
        selected_bindings = copy.deepcopy({key: binding_context[key] for key in claim['bindings']})
        for context in selected_bindings.values():
            context['binding']['result'].pop('sha256', None)
            for field in ('target', 'equation', 'unit_target'):
                if field in context['binding']:
                    context['binding'][field] = context['binding'][field]['quote']
        identity = {'claim': claim['target']['quote'], 'adopted': contract.get('adopted', {}),
                    'sources': [{**anchor,
                                 'sha256': contract['sources'][anchor['id']]['sha256']} for anchor in claim['sources']],
                    'literature': claim['literature'], 'bindings': selected_bindings}
        fingerprints[claim['id']] = state.content_hash(identity)
    packet = {'status': 'review-required', 'manuscript': contract['manuscript'], 'adopted': contract.get('adopted', {}),
            'claims': claims, 'source_context': source_context,
            'binding_context': binding_context, 'claim_fingerprints': fingerprints,
            'evidence_sha256': state.content_hash({key: value for key, value in contract.items() if key != 'review'}),
            'source_knowledge': [{key: row[key] for key in ('document_id', 'paper_id', 'version', 'id',
                                   'kind', 'attribution', 'proposition_sha256')} for row in selected['propositions']] if selected else [],
            'comparison': 'Compare each actual claim with its original conditions, identified object, inference and scope. '
                          'Return the supported finding and its exact source; retain a correct claim when no defect follows.'}
    if contract.get('coverage', {}).get('claims') is True:
        packet['claim_coverage'] = claim_coverage(manuscript, claims, contract['coverage'])
    if claim_ids is None:
        packet['manuscript_text'] = manuscript
        packet = review_round(contract, root, packet, writing=writing)
        packet.pop('manuscript_text')
    else:
        # This is input identity, never a new review or a partial replacement
        # for the fixed initial criteria and full prior review history.
        packet['status'] = 'binding-only'
        packet.pop('claim_coverage', None)
    return packet


def bind(contract, root):
    """Bind exact source/result correspondences without pre-approving their claims."""
    root = Path(root).resolve(strict=True)
    cache = {}
    obj(contract, 'contract')
    contract, literature = literature_bindings(contract, root)
    manuscript_ref = obj(contract.get('manuscript'), 'manuscript')
    manuscript = utf8(file_bytes(root, manuscript_ref, 'manuscript', cache=cache), 'manuscript')
    adopted = obj(contract.get('adopted', {}), 'adopted')
    for name, value in adopted.items():
        text(name, 'adopted identity name')
        require(value is not None and not isinstance(value, (dict, list)), 'adopted identity must be scalar')
        require(not isinstance(value, float) or math.isfinite(value), 'adopted identity must be finite')

    source_refs = obj(contract.get('sources', {}), 'sources')
    source_texts = {}
    for name, ref in source_refs.items():
        text(name, 'source id')
        source_texts[name] = {'text': utf8(file_bytes(root, ref, 'source ' + name, cache=cache), 'source ' + name),
                              'sha256': ref['sha256']}
        metadata = obj(ref.get('metadata'), 'source ' + name + '.metadata')
        identities = obj(metadata.get('identities', {}), 'source ' + name + ' identities')
        for key, value in identities.items():
            require(key in adopted and type(value) is type(adopted[key]) and value == adopted[key],
                    'source identity differs: ' + key)
    if source_texts:
        source_texts = paragraph.normalize_sources(source_texts)

    claims = rows(contract.get('claims', []), 'claims')
    numbers = rows(contract.get('numbers', []), 'numbers')
    models = rows(contract.get('models', []), 'models')
    mappings = rows(contract.get('mappings', []), 'mappings')
    require(claims or numbers or models or mappings, 'at least one binding is required')
    if models or mappings:
        require({'model', 'specification'} <= set(adopted),
                'model bindings require adopted model and specification identities')
    ids = set()
    claim_ids = set()
    for claim in claims:
        obj(claim, 'claim')
        name = text(claim.get('id'), 'claim.id')
        require(name not in ids, 'duplicate binding id: ' + name)
        ids.add(name)
        claim_ids.add(name)
        span(claim.get('target'), manuscript, 'claim ' + name + ' target')
        anchors = rows(claim.get('sources'), 'claim ' + name + ' sources')
        selected_bindings = claim.get('bindings', [])
        binding_ids = {row['id'] for group in (numbers, models, mappings) for row in group}
        require(isinstance(selected_bindings, list) and set(selected_bindings) <= binding_ids, 'unknown claim result binding')
        require(anchors or selected_bindings, 'claim needs cited source anchors or result bindings: ' + name)
        for anchor in anchors:
            obj(anchor, 'source anchor')
            sid = anchor.get('id')
            require(isinstance(sid, str) and sid in source_texts, 'unknown source anchor')
            span(anchor.get('span'), source_texts[sid]['text'], 'source anchor ' + sid)
            if 'role' in anchor:
                text(anchor['role'], 'source evidence role')
        if 'judgment' in claim:
            check_judgment(claim['judgment'], 'claim ' + name + ' judgment')
        if claim.get('literature') and 'judgment' in claim:
            comparison = obj(claim['judgment'].get('comparison'), 'literature support comparison')
            for key in ('claim_meaning', 'source_meaning', 'inference'):
                text(comparison.get(key), 'literature support comparison.' + key)

    numeric_spans, statistic_checks = [], []
    for row in numbers:
        obj(row, 'number')
        name = text(row.get('id'), 'number.id')
        require(name not in ids, 'duplicate binding id: ' + name)
        ids.add(name)
        ref = obj(row.get('result'), 'number result')
        result = result_json(root, ref, 'number result', cache=cache)
        check_registered_inputs(result, root, ref.get('key'), cache=cache)
        check_identity(result, ref.get('identity_keys', {}), adopted, 'number result')
        statistic = obj(lookup(result, ref.get('key'), 'statistic'), 'statistic')
        unit = text(ref.get('unit'), 'number result.unit')
        require(statistic.get('unit') == unit, 'statistic unit differs: ' + name)
        value = statistic.get('value')
        require(type(value) in (int, float) and math.isfinite(value), 'statistic must be finite: ' + name)
        fmt = ref.get('format')
        require(isinstance(fmt, str) and re.fullmatch(r'(?:\.[0-9]{1,2})?[fge]', fmt), 'invalid numeric format')
        target = row.get('target')
        require(span(target, manuscript, 'number ' + name + ' target') == format(value, fmt),
                'formatted statistic differs: ' + name)
        display_unit = text(row.get('unit_display'), 'number unit_display')
        require(span(row.get('unit_target'), manuscript, 'number ' + name + ' unit') == display_unit,
                'display unit differs: ' + name)
        numeric_spans.append((target['start'], target['end']))
        statistic_checks.append({'id': name, 'value': value, 'formatted': format(value, fmt),
                                 'unit': unit, 'unit_display': display_unit,
                                 'result_path': ref['path'], 'result_sha256': ref['sha256'],
                                 'key': copy.deepcopy(ref['key'])})

    residuals = []
    for row in models:
        obj(row, 'model')
        name = text(row.get('id'), 'model.id')
        require(name not in ids, 'duplicate binding id: ' + name)
        ids.add(name)
        span(row.get('equation'), manuscript, 'model ' + name + ' equation')
        code = obj(row.get('code'), 'model code')
        code_text = utf8(file_bytes(root, code, 'model code', cache=cache), 'model code')
        span(code.get('span'), code_text, 'model ' + name + ' code')
        if 'judgment' in row:
            check_judgment(row['judgment'], 'model ' + name + ' judgment')
        ref = obj(row.get('result'), 'model result')
        result = result_json(root, ref, 'model result', cache=cache)
        check_registered_inputs(result, root, ref.get('residual_key'), cache=cache)
        check_identity(result, ref.get('identity_keys', {}), adopted, 'model result')
        residual = lookup(result, ref.get('residual_key'), 'model residual')
        tolerance = ref.get('tolerance')
        require(type(tolerance) in (int, float) and math.isfinite(tolerance) and tolerance >= 0,
                'invalid residual tolerance')
        require(type(residual) in (int, float) and math.isfinite(residual), 'residual must be finite')
        require(abs(residual) <= tolerance, 'residual exceeds tolerance: ' + name)
        residuals.append({'id': name, 'value': residual, 'absolute_value': abs(residual), 'tolerance': tolerance})

    mapping_checks = []
    for row in mappings:
        obj(row, 'mapping')
        name = text(row.get('id'), 'mapping.id')
        require(name not in ids, 'duplicate binding id: ' + name)
        ids.add(name)
        require(row.get('kind') in ('symbol', 'parameter'), 'invalid mapping kind')
        require(row.get('status') in ('derived', 'fixed', 'calibrated', 'estimated'), 'invalid mapping status')
        span(row.get('target'), manuscript, 'mapping ' + name + ' manuscript')
        code = obj(row.get('code'), 'mapping code')
        code_text = utf8(file_bytes(root, code, 'mapping code', cache=cache), 'mapping code')
        span(code.get('span'), code_text, 'mapping ' + name + ' code')
        if 'judgment' in row:
            check_judgment(row['judgment'], 'mapping ' + name + ' judgment')
        ref = obj(row.get('result'), 'mapping result')
        result = result_json(root, ref, 'mapping result', cache=cache)
        check_registered_inputs(result, root, (ref.get('quantity') or {}).get('key'), cache=cache)
        check_identity(result, ref.get('identity_keys', {}), adopted, 'mapping result')
        origin = obj(row.get('origin'), 'mapping origin')
        require(set(origin) in ({'source'}, {'specification'}), 'mapping needs one source or specification origin')
        if 'source' in origin:
            source = obj(origin['source'], 'mapping source')
            sid = source.get('id')
            require(isinstance(sid, str) and sid in source_texts, 'unknown mapping source')
            span(source.get('span'), source_texts[sid]['text'], 'mapping source ' + sid)
        else:
            spec = obj(origin['specification'], 'mapping specification')
            spec_data = result_json(root, spec, 'mapping specification', cache=cache)
            require(spec['sha256'] == adopted['specification'], 'mapping specification identity differs')
            actual = lookup(spec_data, spec.get('key'), 'mapping specification')
            expected = spec.get('value')
            require(type(actual) in (str, int, float, bool) and type(actual) is type(expected) and actual == expected,
                    'mapping specification value differs')
            require(not isinstance(actual, float) or math.isfinite(actual), 'mapping specification value must be finite')
            text(spec.get('unit'), 'mapping specification.unit')
        if row['status'] in ('fixed', 'calibrated'):
            require(row['kind'] == 'parameter' and 'specification' in origin,
                    'fixed or calibrated parameters need their specification key')
        quantity = ref.get('quantity')
        if row['status'] == 'estimated':
            require(quantity is not None, 'estimated mapping requires a named result quantity')
        if quantity is not None:
            obj(quantity, 'mapping quantity')
            statistic = obj(lookup(result, quantity.get('key'), 'mapping quantity'), 'mapping quantity')
            value = quantity.get('value')
            require(type(value) in (int, float) and math.isfinite(value), 'mapping quantity must be finite')
            require(type(statistic.get('value')) in (int, float) and math.isfinite(statistic['value'])
                    and statistic['value'] == value, 'mapping result value differs')
            unit = text(quantity.get('unit'), 'mapping quantity.unit')
            require(statistic.get('unit') == unit, 'mapping result unit differs')
        mapping_checks.append({'id': name, 'kind': row['kind'], 'status': row['status'],
                               'origin': copy.deepcopy(origin), 'result_path': ref['path'],
                               'result_sha256': ref['sha256'], 'quantity': copy.deepcopy(quantity)})

    coverage_result = None
    if 'coverage' in contract:
        coverage = obj(contract['coverage'], 'coverage')
        selections = rows(coverage.get('spans'), 'coverage.spans')
        require(selections, 'coverage needs selected spans')
        for selected in selections:
            span(selected, manuscript, 'coverage selection')
        accounted = rows(coverage.get('accounted', []), 'coverage.accounted')
        exceptions = []
        for item in accounted:
            obj(item, 'coverage account')
            target = item.get('target')
            token = span(target, manuscript, 'coverage account target')
            require(paragraph.QUANTITY.fullmatch(token) is not None, 'coverage account must select one numeric token')
            require(item.get('kind') in ('source', 'assumption', 'citation'), 'invalid coverage account kind')
            require(item.get('claim') in claim_ids, 'coverage account requires a source-bound claim')
            claim = next(c for c in claims if c['id'] == item['claim'])
            require(claim['target']['start'] <= target['start'] and target['end'] <= claim['target']['end'],
                    'coverage account must lie in its cited claim')
            exceptions.append((target['start'], target['end']))
        seen, unbound = set(), []
        for selected in selections:
            for match in paragraph.QUANTITY.finditer(selected['quote']):
                a, b = selected['start'] + match.start(), selected['start'] + match.end()
                if (a, b) not in seen:
                    seen.add((a, b))
                    if (a, b) not in numeric_spans and (a, b) not in exceptions:
                        unbound.append({'start': a, 'end': b, 'quote': match.group()})
        require(not unbound, 'unbound quantitative claims: ' + json.dumps(unbound, ensure_ascii=False))
        coverage_result = {'checked_tokens': len(seen), 'unbound': []}
        if coverage.get('claims') is True:
            checked_claims = claim_coverage(manuscript, claims, coverage)
            require(not checked_claims['unregistered'], 'unregistered important claim candidates')
            check_judgment(coverage.get('claim_judgment'), 'whole-scope claim coverage judgment', require_support=True)
            coverage_result['claims'] = checked_claims

    return {'version': 1, 'status': 'bound', 'bindings': copy.deepcopy(contract),
            'statistic_checks': statistic_checks, 'residual_checks': residuals,
            'mapping_checks': mapping_checks, 'coverage': coverage_result,
            'source_knowledge': literature['propositions'] if literature else []}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in {'artifacts', 'gallery'}:
        import research_artifacts
        return (research_artifacts.gallery_main if argv[0] == 'gallery' else research_artifacts.main)(argv[1:])
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('bind', 'review'):
        command = commands.add_parser(name)
        command.add_argument('contract')
        command.add_argument('--root', required=True)
        command.add_argument('--output', required=True)
        if name == 'review':
            command.add_argument('--host')
            command.add_argument('--rules')
            command.add_argument('--request')
            command.add_argument('--writing-mode', choices=('compose', 'revise', 'translate'), default='compose')
            command.add_argument('--execution-kind', choices=paragraph.EXECUTION_KINDS,
                                 default='single-agent-sequential')
            command.add_argument('--author-id')
            command.add_argument('--response-output')
    args = parser.parse_args(argv)
    try:
        root = Path(args.root).resolve(strict=True)
        contract_path = Path(args.contract)
        if contract_path.is_absolute():
            contract_path = contract_path.relative_to(root)
        contract_path = state.relative(root, contract_path.as_posix())
        raw = (root / contract_path).read_bytes()
        contract = read_json(raw, 'contract')
        writing, writing_inputs = None, []
        if args.command == 'review':
            require(bool(args.host) == bool(args.rules) == bool(args.request),
                    'response writing requires --host, --rules and --request together')
            if args.host:
                for value in (args.host, args.rules):
                    selected = Path(value)
                    if selected.is_absolute():
                        selected = selected.relative_to(root)
                    writing_inputs.append(state.relative(root, selected.as_posix()))
                host, observe = paragraph.load_host_adapter(root / writing_inputs[0])
                writing = {'host': host, 'observe': observe,
                           'rules': read_json((root / writing_inputs[1]).read_bytes(), 'writing rules'),
                           'request': args.request, 'mode': args.writing_mode,
                           'execution_kind': args.execution_kind, 'author_id': args.author_id}
        output = Path(args.output)
        if output.is_absolute():
            output = output.relative_to(root)
        output = state.relative(root, output.as_posix(), exists=False)
        result = bind(contract, root) if args.command == 'bind' else review(contract, root, writing=writing)
        refs = [contract_path, contract.get('manuscript', {}).get('path'), *writing_inputs]
        refs += [x.get('path') for x in contract.get('sources', {}).values()]
        refs += [x.get('result', {}).get('path') for x in contract.get('numbers', [])]
        refs += [x.get(k, {}).get('path') for x in contract.get('models', []) for k in ('result', 'code')]
        refs += [x.get(k, {}).get('path') for x in contract.get('mappings', []) for k in ('result', 'code')]
        refs += [x.get('origin', {}).get('specification', {}).get('path') for x in contract.get('mappings', [])]
        refs += [(contract.get('corpus') or {}).get('path')]
        review_settings = contract.get('review', {})
        refs += [(review_settings.get(key) or {}).get('path')
                 for key in ('previous', 'response_after', 'author_response')]
        for finding in result.get('review', {}).get('findings', []):
            refs += [ref.get('path') for ref in finding.get('references', [])]
            origin = finding.get('origin', {})
            refs += [(origin.get(key) or {}).get('path') for key in ('manuscript', 'comment')]
            refs.append((finding.get('comment') or {}).get('path'))
        actual_sources = result['bindings'].get('sources', {}) if args.command == 'bind' else result['source_context']
        refs += [source['path'] for source in actual_sources.values()]
        protected = {state.relative(root, ref) for ref in refs if isinstance(ref, str) and ref}
        require(output not in protected,
                'output cannot overwrite a binding input')
        result['contract'] = {'path': contract_path, 'sha256': paragraph.sha(raw)}
        response_output = getattr(args, 'response_output', None)
        if response_output:
            require('response_draft' in result, '--response-output requires response_draft')
            destination = Path(response_output)
            if destination.is_absolute():
                destination = destination.relative_to(root)
            response_output = state.relative(root, destination.as_posix(), exists=False)
            require(response_output not in protected | {output},
                    'response output cannot overwrite a binding input or review output')
            destination = root / response_output
            response_text = result['response_draft']['text']
            fd, temporary = tempfile.mkstemp(prefix='.' + destination.name + '-', dir=destination.parent)
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                    stream.write(response_text)
                    stream.flush()
                    os.fsync(stream.fileno())
                state.gate.replace_path(temporary, destination)
                state.gate.sync_directory(destination.parent)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            result['response_draft']['output'] = {'path': response_output, 'sha256': paragraph.sha(response_text)}
        state.save(root / output, result)
        return 0
    except (EvidenceError, paragraph.ParagraphError, ValueError, TypeError, OSError, KeyError) as exc:
        print('research_evidence: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
