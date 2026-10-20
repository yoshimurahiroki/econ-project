#!/usr/bin/env python3
"""Read-only checks of candidate bytes, requirements and structured review records."""
import argparse
import importlib.util
import json
import os
import re
import shlex
from pathlib import Path
import sys
import uuid
from urllib.parse import urlsplit


def _sibling(name, *filenames):
    """Load only shipped siblings, including the flat Project export alias."""
    for filename in filenames:
        path = Path(__file__).resolve().with_name(filename)
        if path.is_file():
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise ImportError('Missing sibling dependency: ' + ', '.join(filenames))


gate = _sibling('native_local_checks', 'local_checks.py', 'LOCAL_CHECKS.py')
requirements = _sibling('native_requirements_check', 'requirements_check.py')
def _registered_review_plans():
    base = Path(__file__).resolve().parent
    paths = (base.parent / 'registry/operations.json', base / 'OPERATIONS.json')
    for path in paths:
        if path.is_file():
            plans = gate.parse_json(gate.regular_bytes(path)).get('review_plans')
            gate.require(isinstance(plans, dict) and {'strict-reviewed', 'full', 'focused'} <= set(plans),
                         'registry review plans missing')
            return plans
    raise ValueError('registered review plan source missing')

REVIEW_PLANS = _registered_review_plans()
ROLES = tuple(REVIEW_PLANS['strict-reviewed']['roles'])
ROLE_CHECKS = {role: tuple(checks) for role, checks in REVIEW_PLANS['strict-reviewed']['checks'].items()}
PROSE_CHECK_IDS = tuple('B%02d' % number for number in range(25, 32)) + tuple(
    'C%02d' % number for number in range(1, 16))
PROSE_RECORD_FIELDS = frozenset(('check_id', 'verdict', 'candidate_sha256',
                                 'evidence', 'claim_refs'))
SURFACES = gate.SURFACES
MEANING_FIELDS = frozenset(('proposition_id', 'actor', 'predicate', 'object',
    'relation_type', 'modality', 'polarity', 'quantifiers', 'conditions',
    'quantities_and_units', 'source_relation'))
MAX_FILES = 10000
MAX_TOTAL_BYTES = 64 * 1024 * 1024
RETURN_BINDINGS = ('candidate_sha256', 'request_sha256', 'contract_sha256',
                   'events_sha256', 'dictionary_sha256', 'artifacts_sha256', 'text_views_sha256', 'sources_sha256')
RETURN_TRANSPORT = frozenset(('worker_id', 'launch_ref', 'return_ref', 'execution_status',
                             'review_kind', 'source_verification', 'return_text', 'return_sha256'))
LIMITATION = (
    'Checks cover exact bytes, explicit requirements, prose matches and structured '
    'review consistency. The coordinator matches worker and operation references '
    'to actual runtime returns and verifies original-request coverage. '
    'Authentication and release flags remain false.'
)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


# Match spelling in place: never normalize a result's value or source offsets.
# A comma is a thousands separator only in complete three-digit groups;
# the decimal point and exponent follow the existing dot-decimal input syntax.
_GROUP_SPACES = '\u00a0\u202f\u2009'
_SIGN = r'[+\-\u2212\ufe63\uff0d\uff0b]?'
_DIGITS = r'\d(?:_?\d)*'
_INTEGER = r'(?:\d{1,3}(?:[,\u00a0\u202f\u2009]\d{3})+|' + _DIGITS + ')'
_EXPONENT = '(?:[eE]' + _SIGN + _DIGITS + ')?'
_QUANTITY = re.compile(_SIGN + _INTEGER + r'(?:\.' + _DIGITS + r'|\.(?=[eE]' + _SIGN + r'\d))?' + _EXPONENT
                       + '|' + _SIGN + r'\.' + _DIGITS + _EXPONENT)


def _quantity_spans(text):
    """Whole numeric spellings and their unchanged character coordinates."""
    return [(match.start(), match.end()) for match in _QUANTITY.finditer(text)]


def _quantity_boundaries(text, start, end, context):
    if isinstance(text, gate.UTF8Text):
        # Numeric tokens are local. Inspect both selected boundaries with their
        # adjoining characters while retaining original character coordinates.
        for boundary in (start, end):
            left, right = max(0, boundary - 4096), min(len(text), boundary + 4096)
            window = text[left:right]
            gate.require(all(not a < boundary - left < b for a, b in _quantity_spans(window)),
                         context + ' splits a different quantity')
        return
    gate.require(all(not (left < start < right or left < end < right)
                     for left, right in _quantity_spans(text)),
                 context + ' splits a different quantity')


def _quantity_result(text, start, end, views=None):
    gate.require((start, end) in _quantity_spans(text),
                 'candidate result_span must cover a whole quantity')
    # The display view has source coordinates even across Markdown delimiters.
    # Do not use the whitespace-folded view: separate numbers stay separate.
    for view, mapping in (views or gate.text_views(text.encode()))[:2]:
        # NFKC maps grouping spaces to ordinary spaces. Restore only separators
        # actually present in the source; separate ASCII-space numbers stay apart.
        view = ''.join(text[left:right] if char == ' ' and right == left + 1
                       and text[left:right] in _GROUP_SPACES else char
                       for char, (left, right) in zip(view, mapping))
        ranges = [(mapping[left][0], mapping[right - 1][1])
                  for left, right in _quantity_spans(view)]
        gate.require((start, end) in ranges and all(
            not (left < start < right or left < end < right) for left, right in ranges),
            'candidate result_span splits a different displayed quantity')


def _issue(items, check, message):
    items.append({'check': check, 'message': message})


class ReleaseBlocked(ValueError):
    """Publication failed; retain the candidate without returning its contents."""

    def __init__(self, failures):
        self.failures = failures
        super().__init__('; '.join(row['message'] for row in failures))


def assert_release_predicates(context, check, *, host_verifier=None):
    return _assert_release_predicates(context, check, host_verifier=host_verifier)


def assert_surface_release_predicates(context, check, *, host_verifier=None):
    return _assert_release_predicates(context, check, host_verifier=host_verifier, surface_only=True)


def _assert_release_predicates(context, check, *, host_verifier=None, surface_only=False):
    """One publication gate for native, Site, verification and staged rechecks.

    ``context`` and ``check`` describe the exact saved snapshot, not authority.
    A trusted host integration may pass a callable in-process. No JSON field,
    command-line option, environment variable or source_verification label can
    install that integration. Its default is deliberately unavailable. A verifier
    must retrieve authoritative events independently of these caller records and
    bind its observation to this complete context. Hashes prove identity only.
    """
    failures = []
    def require(value, name, message, action='correct-and-resubmit'):
        if not value:
            failures.append({'check': name, 'message': message, 'action': action})
    require(isinstance(context, dict) and isinstance(check, dict), 'release-inputs',
            'release requires a saved context and computed check')
    if failures:
        raise ReleaseBlocked(failures)
    require(context.get('mode') == 'strict', 'strict-mode',
            'provisional candidates remain quarantined and cannot be published')
    require(context.get('status') in ('ready', 'blocked') if surface_only else context.get('status') == 'ready', 'release-status',
            'all candidate checks and fixed coverage must be ready')
    require(context.get('review_plan') == 'strict-reviewed', 'independent-review-plan',
            'only strict-reviewed can authorize publication; other plans are draft-only')
    surface = context.get('surface', 'final')
    surface_check = check.get('surface_check', {})
    require((surface in SURFACES and surface != 'final') if surface_only else surface == 'final', 'final-publication-surface',
            'nonfinal text review cannot authorize final-task publication')
    require(surface in SURFACES and surface_check.get('surface') == surface
            and surface_check.get('text_sha256') == context.get('candidate_sha256'),
            'surface-bindings', 'outgoing surface or exact text differs from its reviewed candidate')
    fulfillment = check.get('requirements', {})
    if surface_only:
        unmet = fulfillment.get('unmet', [])
        deferred = surface_check.get('deferred_completion_requirement_ids', [])
        completion_only = bool(unmet) and all(
            row.get('requirement_id') in deferred and row.get('code') in
            ('artifact_invalid', 'missing_action_event', 'action_unsuccessful', 'condition_unmet', 'condition_pending')
            for row in unmet)
        remaining = [row for key in ('failed_checks', 'missing_checks', 'unresolved')
                     for row in check.get(key, [])
                     if not (completion_only and row.get('check') == 'requirements')]
        require(surface_check.get('review_status') == 'consistent'
                and surface_check.get('scan_complete') is True
                and surface_check.get('parent_unmet') == unmet
                and not surface_check.get('unresolved') and not remaining,
                'complete-checks', 'every surface check must pass on the exact saved bytes')
        require((fulfillment.get('status') == 'pass' and not unmet) or completion_only,
                'requirements', 'only parent completion requirements may remain pending')
        capabilities = context.get('capability_statuses')
        require(isinstance(capabilities, dict) and all(
            status == 'available' or name in (*ROLES, 'independent-requirements-coverage')
            for name, status in capabilities.items()), 'capabilities',
            'required capability remains unavailable')
    else:
        require(check.get('status') == 'consistent' and check.get('recorded_checks_complete') is True
                and not any(check.get(key) for key in ('failed_checks', 'missing_checks', 'unresolved')),
                'complete-checks', 'every recorded requirement and review must pass')
        require(fulfillment.get('status') == 'pass' and not fulfillment.get('unmet'),
                'requirements', 'a required artifact, action, content or authority condition remains unmet')
    require({'input-bindings', 'requirements', 'prose-scan', 'review-records'}
            <= set(check.get('executed_checks', [])), 'executed-checks',
            'all required mechanical checks must have executed')
    require(context.get('dictionary_rule_count') == 142, 'dictionary',
            'publication requires the complete pinned 142-rule dictionary')
    prose = check.get('prose_scan', {})
    require(prose.get('status') == 'scanned' and not prose.get('unresolved_hits')
            and all(hit.get('resolution') == 'occurrence-reviewed' for hit in prose.get('hits', [])),
            'prose-occurrences', 'every dictionary occurrence must be resolved on the exact candidate')
    bindings = check.get('bindings', {})
    for field in ('run_id', *RETURN_BINDINGS):
        require(context.get(field) == bindings.get(field) and _text(context.get(field)),
                'snapshot-bindings', 'release snapshot differs from checked ' + field)
    for field in ('policy_manifest_sha256', 'submission_sha256', 'coverage_sha256'):
        require(gate.hexhash(context.get(field)), 'snapshot-bindings', 'missing exact ' + field)
    artifacts = context.get('artifact_hashes', [])
    require(isinstance(artifacts, list) and all(isinstance(row, dict)
            and set(row) == {'path', 'sha256', 'size_bytes'} and gate.hexhash(row.get('sha256'))
            and type(row.get('size_bytes')) is int and row['size_bytes'] >= 0 for row in artifacts),
            'artifact-bindings', 'publication requires exact artifact paths, hashes and sizes')
    if isinstance(artifacts, list) and all(isinstance(row, dict) for row in artifacts):
        require([{'path': row.get('path'), 'sha256': row.get('sha256')} for row in artifacts]
                == check.get('artifacts'), 'artifact-bindings',
                'release artifact set differs from the complete checked snapshot')
    coverage = context.get('coverage_review', {})
    try:
        coverage_body = gate.parse_json(coverage['return_text'].encode('utf-8'))
        require(coverage_body.get('schema_version') == 3, 'independent-coverage',
                'publication requires bidirectional, pre-candidate independent request coverage')
    except (KeyError, TypeError, AttributeError, ValueError):
        require(False, 'independent-coverage', 'independent coverage original is missing')
    records = context.get('review_records', [])
    by_role = {row.get('role'): row for row in records if isinstance(row, dict)
               and isinstance(row.get('role'), str)} if isinstance(records, list) else {}
    require(isinstance(records, list) and len(by_role) == len(records) == 3
            and set(by_role) == set(ROLES), 'independent-roles',
            'distinct quality-a, quality-b and compliance originals are required')
    for role in ROLES:
        review = check.get('reviews', {}).get(role, {})
        require(review.get('status') == 'consistent', role, 'required role has no valid complete return: ' + role)
        if role.startswith('quality-'):
            require(review.get('normalized_return', {}).get('schema_version') == 3,
                    role + '-meaning-schema',
                    'strict publication requires current typed meaning/source identity records; legacy returns remain readable only')
            verdicts = review.get('prose_review', {}).get('prose_verdicts', {})
            require(set(verdicts) == set(PROSE_CHECK_IDS) and all(value == 'absent' for value in verdicts.values()),
                    role + '-semantics', 'all 22 full-candidate semantic verdicts must pass for ' + role)
    require(callable(host_verifier), 'host-provenance',
            'authenticated host worker/operation verifier is unavailable; retain blocked-unapproved',
            'obtain-authenticated-host-verifier')
    adopted_assurance = context.get('adopted_assurance_class', 'host-authenticated')
    require(adopted_assurance in ('host-authenticated', 'host-observed'),
            'host-assurance-adoption', 'run has no supported fixed host assurance class')
    if failures:
        raise ReleaseBlocked(failures)
    # This call is an integration boundary, never a deserialized pass flag.
    try:
        observation = host_verifier(gate.parse_json(gate.canonical(context)))
    except Exception as exc:
        raise ReleaseBlocked([{'check': 'host-provenance',
            'message': 'authenticated host verification failed: ' + str(exc),
            'action': 'obtain-authenticated-host-verifier'}]) from exc
    require(isinstance(observation, dict), 'host-provenance', 'host returned no authenticated observation')
    if not isinstance(observation, dict):
        raise ReleaseBlocked(failures)
    host_observed = observation.get('assurance_class') == 'host-observed'
    require(observation.get('assurance_class', 'host-authenticated') == adopted_assurance,
            'host-assurance-adoption', 'host observation differs from the assurance class adopted by this run')
    require(observation.get('status') == ('observed' if host_observed else 'authenticated')
            and observation.get('context_sha256') == gate.sha(gate.canonical(context)),
            'host-provenance', 'host observation does not authenticate this exact release context')
    if host_observed:
        require(observation.get('coordinator_matched') is True
                and observation.get('worker_identity_authenticated') is False,
                'host-observed-boundary',
                'host-observed requires operational matching and must not claim authenticated worker identity')
    for field in ('trusted_request_observed', 'independent_coverage_verified',
                  'actual_operations_verified', 'compliance_started_first'):
        require(observation.get(field) is True, 'host-' + field,
                'host must independently verify ' + field)
    require(_text(observation.get('approved_at')) and _text(observation.get('tool_release_id')),
            'host-approval', 'host approval time and release identity are required')
    workers = observation.get('workers', [])
    observed = {row.get('role'): row for row in workers if isinstance(row, dict)
                and isinstance(row.get('role'), str)} if isinstance(workers, list) else {}
    require(isinstance(workers, list) and len(observed) == len(workers) == 3
            and set(observed) == set(ROLES), 'host-workers',
            'host must return all three distinct completed workers')
    identities, refs = {context.get('author_id')}, set()
    for role in ROLES:
        worker, record = observed.get(role, {}), by_role[role]
        require(worker.get('execution_status') == 'completed', role, 'actual terminal completion is missing: ' + role)
        if host_observed:
            require(worker.get('direct_submission_observed') is True
                    and worker.get('coordinator_matched') is True
                    and _text(worker.get('assignment_id'))
                    and _text(worker.get('receipt_id')),
                    role, 'host-observed requires a direct receipt matched by the coordinator: ' + role)
        for field in ('worker_id', 'launch_ref', 'return_ref', 'return_sha256'):
            require(_text(worker.get(field)) and worker.get(field) == record.get(field), role,
                    'actual host event differs from submitted ' + field + ': ' + role)
        require(worker.get('worker_id') not in identities, role, 'workers must differ from author and other roles')
        identities.add(worker.get('worker_id'))
        for field in ('launch_ref', 'completion_ref', 'return_ref'):
            require(_text(worker.get(field)) and worker.get(field) not in refs, role,
                    'actual launch, completion and return events must be distinct')
            refs.add(worker.get(field))
        if role.startswith('quality-'):
            require(worker.get('independent_before_merge') is True, role,
                    'quality judgments must be fixed before sharing the other judgment')
    if failures:
        raise ReleaseBlocked(failures)
    return {'release_authorized': not surface_only, 'independently_approved': not surface_only,
            **({'surface_release_authorized': True, 'surface_independently_approved': True,
                'final_task_release_authorized': False} if surface_only else {}),
            'provenance_authenticated': not host_observed,
            'assurance_class': 'host-observed' if host_observed else 'host-authenticated',
            'worker_identity_authenticated': not host_observed,
            'context_sha256': gate.sha(gate.canonical(context)),
            'approved_at': observation['approved_at'], 'tool_release_id': observation['tool_release_id'],
            'review_event_refs': {role: {key: observed[role][key] for key in
                ('worker_id', 'launch_ref', 'completion_ref', 'return_ref', 'return_sha256')} for role in ROLES}}


class UnstructuredReturn(ValueError):
    """A retained legacy report cannot supply a machine-usable approval."""


def normalize_report(report):
    """Derive substantive evidence only from the exact structured original return.

    Transport metadata remains caller-supplied. Optional compatibility mirrors
    must agree byte-for-byte after JSON normalization, including JSON types.
    """
    gate.require(isinstance(report, dict), 'review record must be an object')
    text = report.get('return_text')
    gate.require(_text(text) and report.get('return_sha256') == gate.sha(text.encode('utf-8')),
                 'return_text and exact return_sha256 are required')
    try:
        original = gate.parse_json(text.encode('utf-8'))
    except ValueError as exc:
        if text.lstrip().startswith(('{', '[')):
            raise ValueError('invalid structured original return: ' + str(exc)) from exc
        raise UnstructuredReturn('legacy unstructured return is retained but cannot establish approval') from exc
    if not isinstance(original, dict):
        raise UnstructuredReturn('legacy non-object return cannot establish approval')
    versions = (2, 3) if original.get('role') in ('quality-a', 'quality-b') else (1,)
    gate.require(type(original.get('schema_version')) is int and original['schema_version'] in versions,
                 'structured quality return requires schema_version 2 or 3; compliance requires version 1')
    gate.require(all(key in original for key in
                     ('role', 'decision', 'findings', 'unassessed', 'errors', 'checks', *RETURN_BINDINGS)),
                 'structured original lacks decision, findings, checks or candidate/context bindings')
    gate.require(not ({'return_text', 'return_sha256', 'normalized_return'} & set(original)),
                 'structured original cannot contain transport text/hash or a derived normalized return')
    gate.require(not ({'release_authorized', 'independently_approved', 'provenance_authenticated'}
                      & (set(original) | set(report))),
                 'review records cannot supply host authentication or publication authority')
    gate.require(not any(key in RETURN_TRANSPORT and key not in report for key in original),
                 'review transport metadata must be supplied in the evidence envelope')
    for key, value in report.items():
        if key not in RETURN_TRANSPORT or key in original:
            gate.require(key in original and gate.canonical(value) == gate.canonical(original[key]),
                         'review envelope differs from structured original: ' + key)
    normalized = {key: value for key, value in report.items() if key in RETURN_TRANSPORT}
    normalized.update(original)
    normalized['normalized_return'] = original
    return normalized


def _source_matched(source):
    return (isinstance(source, dict) and set(source) == {'status', 'reference', 'verifier_id'}
            and source.get('status') == 'matched-to-runtime'
            and _text(source.get('reference')) and _text(source.get('verifier_id')))

def _review_identity(report, original, kind, author_id):
    gate.require(report.get('execution_status') == 'completed' and report.get('review_kind') == kind
                 and _text(report.get('worker_id')) and _text(report.get('return_ref')),
                 'review requires its completed actor, method and original result reference')
    if kind == 'self-check':
        source = report.get('source_verification')
        gate.require(report['worker_id'] == author_id and original.get('worker_id') == author_id
                     and original.get('review_kind') == 'self-check' and not report.get('launch_ref')
                     and isinstance(source, dict) and set(source) == {'status', 'reference', 'verifier_id'}
                     and source['status'] == 'self-check' and _text(source['reference'])
                     and source['verifier_id'] == author_id,
                     'self-check must bind the author and local assessment without a worker launch')
    else:
        gate.require(kind == 'independent' and report['worker_id'] != author_id
                     and _text(report.get('launch_ref')) and report['launch_ref'] != report['return_ref']
                     and _source_matched(report.get('source_verification')),
                     'independent review requires another worker and matched launch/return records')


# Fixed saved-result schemas, not connector discovery or runtime authentication.
# Reviewers cannot select an adapter or redefine its operation/target semantics.
_OPERATION_ADAPTERS = {
    ('send_email', 'send_email'): ('json', ('target', 'to')),
    ('publish', 'publish'): ('json', ('target', 'document_id')),
    ('execute_command', 'execute_command'): ('command', ('cmd',)),
    ('exec_command', 'execute_command'): ('command', ('cmd',)),
    ('write_stdin', 'execute_command'): ('command', ('session_id',)),
    ('mcp__codex_apps__library_create_library_file',
     'save_file'): ('library', ('file',)),
    ('mcp__codex_apps__library_replace_library_file',
     'save_file'): ('library-replace', ('file',)),
    ('mcp__codex_apps__library_finalize_uploads',
     'save_file'): ('library', ('uploads',)),
}


def _operation_target(value, fields):
    supplied = [value[key] for key in fields if key in value]
    gate.require(supplied and all(_text(item) for item in supplied)
                 and all(item == supplied[0] for item in supplied),
                 'operation target is absent, unsupported or contradictory')
    return supplied[0]


def _operation_return(value, operation, target, adapter, depth=0):
    """Parse every registered result branch; reject uninterpreted containers."""
    gate.require(depth <= 8 and isinstance(value, dict),
                 'unsupported operation return: expected a JSON object')
    gate.require('isError' not in value or value['isError'] is False,
                 'operation return reports an error or invalid isError')
    gate.require(not value.get('error') and not value.get('errors'),
                 'operation return contains errors')
    if 'status' in value:
        gate.require(value['status'] in (('success', 'completed', 'running', 'pending')
                                        if adapter == 'command' else
                                        ('success', 'succeeded') if adapter in ('library', 'library-replace') else ('success',)),
                     'operation return is failed or has an unsupported status')
    session = None
    running = adapter == 'command' and value.get('status') in ('running', 'pending')
    for key in ('session_id', 'sessionId'):
        if value.get(key) is not None:
            gate.require(adapter == 'command' and
                         (type(value[key]) is int or _text(value[key])),
                         'unsupported operation session identifier')
            gate.require(session is None or session == value[key], 'contradictory operation sessions')
            session = value[key]
            running = True
    if 'operation' in value:
        expected_operation = ('replace_library_file' if adapter == 'library-replace' else
                              'create_library_file' if adapter == 'library' else operation)
        gate.require(value['operation'] == expected_operation, 'returned operation differs from call')
    for key in ('target', 'target_id'):
        if key in value:
            gate.require(value[key] == target, 'returned target differs from call')
    if 'cmd' in value:
        gate.require(adapter == 'command' and value['cmd'] == target, 'returned command differs from call')
    # Closed result vocabulary prevents an unparsed outcome/data/response branch
    # (including one containing an error) from being ignored beside success.
    allowed = {'status', 'operation', 'target', 'target_id', 'isError', 'error', 'errors',
               'result', 'structuredContent', 'content', 'metadata', 'message', 'id'}
    if adapter == 'command':
        allowed |= {'exit_code', 'output', 'cmd', 'session_id', 'sessionId',
                    'wall_time_seconds', 'chunk_id', 'original_token_count'}
    if adapter in ('library', 'library-replace'):
        allowed |= {'library_file_id', 'file_id', 'file_name', 'path', 'version',
                    'version_id', 'current_version_number', 'mime_type', 'size_bytes',
                    'file_size_bytes', 'xattrs', 'results', 'workspace_path',
                    'restored_from_version_number', 'directory_id', 'library_artifact_type',
                    'external_connectors_accessed'}
    gate.require(set(value) <= allowed, 'unsupported operation return fields')
    for key, item in value.items():
        if key not in ('result', 'structuredContent', 'content', 'metadata', 'errors', 'xattrs', 'results'):
            gate.require(not isinstance(item, (dict, list)), 'unsupported operation outcome container')
    returned_targets = [value[key] for key in ('target', 'target_id') if key in value]
    if 'metadata' in value:
        metadata = value['metadata']
        gate.require(isinstance(metadata, dict) and metadata
                     and set(metadata) <= {'operation', 'target', 'target_id', 'id'},
                     'unsupported operation return metadata')
        for key, item in metadata.items():
            gate.require(_text(item), 'unsupported operation return metadata value')
            if key == 'operation':
                gate.require(item == operation, 'metadata operation differs from call')
            if key in ('target', 'target_id'):
                gate.require(item == target, 'metadata target differs from call')
                returned_targets.append(item)
    identifiers = []
    file_ids = []
    versions = []
    if adapter in ('library', 'library-replace'):
        for key in ('current_version_number', 'file_size_bytes'):
            if key in value:
                gate.require(type(value[key]) is int and value[key] >= 0,
                             'invalid saved file version or size')
        if 'current_version_number' in value:
            versions.append(value['current_version_number'])
        if value.get('restored_from_version_number') is not None:
            gate.require(type(value['restored_from_version_number']) is int
                         and value['restored_from_version_number'] >= 0,
                         'invalid restored file version')
        if 'external_connectors_accessed' in value:
            gate.require(type(value['external_connectors_accessed']) is bool,
                         'invalid saved file connector indicator')
        if 'workspace_path' in value:
            gate.require(value['workspace_path'] == target, 'saved file source differs from call')
        if 'xattrs' in value:
            gate.require(isinstance(value['xattrs'], list) and all(
                isinstance(item, dict) and set(item) == {'name', 'value'}
                and _text(item['name']) and isinstance(item['value'], str)
                for item in value['xattrs']), 'unsupported saved file attributes')
        if 'file_id' in value:
            gate.require(_text(value['file_id']), 'invalid saved file identifier')
            file_ids.append(value['file_id'])
        if 'library_file_id' in value:
            gate.require(_text(value['library_file_id']), 'saved file lacks Library identifier')
            identifiers.append(value['library_file_id'])
    nested = [value[key] for key in ('result', 'structuredContent') if key in value]
    if 'results' in value:
        gate.require(adapter in ('library', 'library-replace') and isinstance(value['results'], list)
                     and len(value['results']) == 1, 'saved result must match one requested file')
        nested.extend(value['results'])
    if 'content' in value:
        content = value['content']
        gate.require(isinstance(content, list) and content, 'unsupported empty/non-array return content')
        for block in content:
            gate.require(isinstance(block, dict) and set(block) == {'type', 'text'}
                         and block.get('type') == 'text' and _text(block.get('text')),
                         'unsupported operation return content block')
            # The real Library transport supplies this fixed human-readable
            # acknowledgement beside its authoritative structured result.
            # Other text must still parse and agree; it cannot hide an error.
            if not (adapter in ('library', 'library-replace') and 'structuredContent' in value
                    and block['text'] == 'Action completed.'):
                nested.append(gate.parse_json(block['text'].encode('utf-8')))
    if 'exit_code' in value:
        gate.require(adapter == 'command' and ((running and value['exit_code'] is None)
                     or (type(value['exit_code']) is int and value['exit_code'] == 0)),
                     'command did not terminate successfully')
    if nested:
        for item in nested:
            outcome = _operation_return(item, operation, target, adapter, depth + 1)
            running = running or outcome['status'] == 'running'
            if outcome.get('session_id') is not None:
                gate.require(session is None or session == outcome['session_id'],
                             'nested operation session differs')
                session = outcome['session_id']
            if 'current_version_number' in outcome:
                versions.append(outcome['current_version_number'])
            if outcome.get('file_id'):
                file_ids.append(outcome['file_id'])
            if outcome.get('library_file_id'):
                identifiers.append(outcome['library_file_id'])
    elif adapter == 'command':
        gate.require(running or (type(value.get('exit_code')) is int and value['exit_code'] == 0),
                     'command completion requires terminal exit_code zero')
    elif adapter in ('library', 'library-replace'):
        gate.require(identifiers, 'saved result lacks created Library file identifier')
    else:
        gate.require(value.get('status') == 'success' and returned_targets,
                     'operation completion lacks explicit success and returned target metadata')
    result = {'operation': operation, 'target': target,
              'status': 'running' if running else 'success'}
    if session is not None:
        result['session_id'] = session
    if adapter in ('library', 'library-replace'):
        gate.require(identifiers and len(set(identifiers)) == 1,
                     'saved result contains contradictory Library file identifiers')
        result['library_file_id'] = identifiers[0]
        gate.require(len(set(file_ids)) <= 1, 'saved result contains contradictory file identifiers')
        if file_ids:
            result['file_id'] = file_ids[0]
        gate.require(len(set(versions)) <= 1, 'saved result contains contradictory versions')
        if versions:
            result['current_version_number'] = versions[0]
    return result


def _operation_results(report, events, outcomes=None):
    """Bind registered operation return schemas to exact supplied call bytes."""
    records = report.get('action_results_verified', [])
    gate.require(isinstance(records, list), 'action_results_verified must be an array')
    expected = {event['event_id']: event for event in events}
    seen = set()
    for record in records:
        gate.require(isinstance(record, dict), 'action result must be an object')
        event_id = record.get('event_id')
        gate.require(isinstance(event_id, str) and event_id in expected and event_id not in seen,
                     'unknown or duplicate verified action result')
        event = expected[event_id]
        gate.require(all(record.get(field) == event[field] for field in ('operation', 'target', 'status'))
                     and record.get('status') == 'success', 'verified action differs from final event')
        gate.require(all(_text(record.get(field)) for field in
                         ('tool_call_ref', 'tool_return_ref', 'tool_name', 'call_args_text', 'return_text')),
                     'action result lacks actual tool name, call arguments, references or return text')
        gate.require(record['tool_call_ref'] != record['tool_return_ref'],
                     'tool call and return references must be distinct')
        gate.require(record.get('return_sha256') == gate.sha(record['return_text'].encode('utf-8')),
                     'action returned text digest mismatch')
        gate.require(record.get('call_args_sha256') == gate.sha(record['call_args_text'].encode('utf-8')),
                     'action call arguments digest mismatch')
        gate.require(_source_matched(record.get('source_verification')),
                     'action source not recorded as matched to actual tool result')
        key = (record['tool_name'], event['operation'])
        gate.require(key in _OPERATION_ADAPTERS, 'unregistered tool/operation return adapter')
        adapter, fields = _OPERATION_ADAPTERS[key]
        args = gate.parse_json(record['call_args_text'].encode('utf-8'))
        gate.require(isinstance(args, dict), 'operation call arguments must be an object')
        if 'operation' in args:
            gate.require(args['operation'] == event['operation'], 'call operation differs from final event')
        gate.require(record['tool_name'] != 'write_stdin',
                     'command continuation requires its initiating exec_command')
        if adapter in ('library', 'library-replace'):
            if fields == ('file',):
                allowed_args = ({'file', 'library_file_id', 'expected_current_version', 'directory_id', 'version_reason'}
                                if adapter == 'library-replace' else
                                {'file', 'files', 'directory_id', 'library_artifact_type'})
                gate.require(set(args) <= allowed_args, 'unsupported Library save call fields')
                if adapter == 'library-replace':
                    gate.require(_text(args.get('library_file_id')), 'replacement lacks Library target ID')
                    if args.get('expected_current_version') is not None:
                        gate.require(type(args['expected_current_version']) is int
                                     and args['expected_current_version'] >= 0,
                                     'invalid expected replacement version')
                gate.require(('file' in args) != ('files' in args),
                             'save call requires exactly one file input')
                files = [args['file']] if 'file' in args else args['files']
                gate.require(isinstance(files, list) and len(files) == 1
                             and _text(files[0]) and files[0].startswith('/'),
                             'save action must identify one absolute local file')
                target = files[0]
            else:
                gate.require(set(args) == {'uploads'}, 'unsupported Library finalize call fields')
                uploads = args.get('uploads')
                gate.require(isinstance(uploads, list) and len(uploads) == 1
                             and isinstance(uploads[0], dict),
                             'save action must identify one finalized upload')
                upload = uploads[0]
                gate.require(set(upload) <= {'directory_id', 'expected_current_version', 'file_id',
                             'file_name', 'file_size_bytes', 'library_artifact_type', 'library_file_id',
                             'method', 'mime_type', 'pdf_c2pa_upload', 'purpose', 'required_headers',
                             'shared_library_upload', 'store_in_library', 'upload_session_id',
                             'upload_url', 'version_reason', 'workspace_path'},
                             'unsupported finalized upload fields')
                gate.require(upload.get('purpose') == 'create_library_file'
                             and upload.get('store_in_library') is True
                             and all(_text(upload.get(key)) for key in
                                     ('upload_session_id', 'file_id', 'file_name'))
                             and bool(upload.get('workspace_path')) != bool(upload.get('upload_url')),
                             'invalid finalized upload source or purpose')
                target = upload.get('workspace_path') or upload['file_name']
        else:
            target = _operation_target(args, fields)
        gate.require(target == event['target'], 'call target differs from final event')
        outcome = _operation_return(gate.parse_json(record['return_text'].encode('utf-8')),
                                    event['operation'], target, adapter)
        if adapter in ('library', 'library-replace') and fields == ('uploads',):
            gate.require(outcome.get('file_id') == upload['file_id'],
                         'finalized file identifier differs from prepared upload')
        if adapter == 'library-replace':
            gate.require(outcome.get('library_file_id') == args['library_file_id'],
                         'replacement returned a different Library target ID')
            if args.get('expected_current_version') is not None:
                gate.require(outcome.get('current_version_number') == args['expected_current_version'] + 1,
                             'replacement did not return the next expected version')
        continuations = record.get('continuations', [])
        gate.require(isinstance(continuations, list), 'operation continuations must be an array')
        references = {record['tool_call_ref'], record['tool_return_ref']}
        for step in continuations:
            gate.require(adapter == 'command' and record['tool_name'] == 'exec_command'
                         and outcome['status'] == 'running'
                         and type(outcome.get('session_id')) is int,
                         'continuation lacks an active command session')
            gate.require(isinstance(step, dict) and step.get('tool_name') == 'write_stdin'
                         and all(step.get(key) == event[key] for key in ('event_id', 'operation', 'target')),
                         'continuation belongs to a different operation or target')
            gate.require(all(_text(step.get(key)) for key in
                         ('tool_call_ref', 'tool_return_ref', 'call_args_text', 'return_text')),
                         'continuation lacks tool references or exact bytes')
            gate.require(step['tool_call_ref'] != step['tool_return_ref']
                         and not references.intersection((step['tool_call_ref'], step['tool_return_ref'])),
                         'continuation reuses call/return references')
            references.update((step['tool_call_ref'], step['tool_return_ref']))
            gate.require(_source_matched(step.get('source_verification')),
                         'continuation is not matched to actual tool result')
            gate.require(all(step.get(key + '_sha256') == gate.sha(step[key + '_text'].encode('utf-8'))
                             for key in ('call_args', 'return')), 'continuation bytes digest mismatch')
            follow_args = gate.parse_json(step['call_args_text'].encode('utf-8'))
            gate.require(isinstance(follow_args, dict)
                         and set(follow_args) <= {'session_id', 'chars', 'max_output_tokens', 'yield_time_ms'}
                         and type(follow_args.get('session_id')) is int
                         and follow_args['session_id'] == outcome['session_id']
                         and follow_args.get('chars', '') == '',
                         'continuation session differs or changes the running command')
            session = outcome['session_id']
            outcome = _operation_return(gate.parse_json(step['return_text'].encode('utf-8')),
                                        event['operation'], target, adapter)
            gate.require(outcome.get('session_id', session) == session,
                         'continuation return belongs to a different session')
        if outcomes is not None:
            outcomes.append({'event_id': event_id, 'tool_name': record['tool_name'],
                             **{key: value for key, value in outcome.items() if key != 'session_id'}})
        gate.require(outcome['status'] == 'success',
                     'operation remains running; claimed completion is unmet')
        seen.add(event_id)
    gate.require(seen == set(expected), 'required actions lack source-matched returned tool results')
    return seen


def _text_span(item, texts, path_field, hash_field):
    """Validate raw decoded-character coordinates against exact supplied bytes."""
    path = item.get(path_field)
    gate.require(isinstance(path, str) and path in texts, 'unknown prose text path')
    data = texts[path]
    text = (gate.UTF8Text(data) if isinstance(data, gate.FileSnapshot) and len(data) > gate.MAX_BYTES
            else data.decode('utf-8'))
    start, end = item.get('start'), item.get('end')
    gate.require(item.get(hash_field) == gate.sha(data), 'prose text digest mismatch: ' + path)
    gate.require(type(start) is int and type(end) is int and 0 <= start <= end <= len(text)
                 and (start < end or not text), 'invalid raw-character prose range: ' + path)
    return path, text, start, end


WEB_READ_TOOLS = {'web__run', 'mcp__codex_apps__search_service_web_run'}
LIBRARY_READ_TOOLS = {'mcp__codex_apps__library_read'}

def _checked_acquisition(record):
    gate.require(isinstance(record, dict) and record.get('status') == 'success'
                 and all(_text(record.get(key)) for key in
                         ('tool_name', 'tool_call_ref', 'tool_return_ref', 'call_args_text', 'return_text'))
                 and record['tool_call_ref'] != record['tool_return_ref']
                 and gate.sha(record['call_args_text'].encode()) == record.get('call_args_sha256')
                 and gate.sha(record['return_text'].encode()) == record.get('return_sha256')
                 and _source_matched(record.get('source_verification')),
                 'acquisition requires matched original call and return bytes')
    return gate.parse_json(record['call_args_text'].encode()), gate.parse_json(record['return_text'].encode())

def _json_value(value, path):
    gate.require(isinstance(path, str) and (not path or path.startswith('/')), 'invalid result pointer')
    for token in path.split('/')[1:] if path else ():
        token = token.replace('~1', '/').replace('~0', '~')
        if isinstance(value, list):
            gate.require(token.isdigit() and int(token) < len(value), 'result outside array')
            value = value[int(token)]
        else:
            gate.require(isinstance(value, dict) and token in value, 'unknown result field')
            value = value[token]
    return value

def _web_sections(text):
    """Read transport headers, keeping document body intervals separate."""
    blocks = []
    pattern = r'(?m)^[^\n]*Source: (open|click)\((\{[^\n]*\})\); Total lines:'
    for match in re.finditer(pattern, text):
        refs = re.findall('\ue200cite\ue202([^\ue201]+)\ue201', match.group())
        if not refs or re.match(r'L\d+:', match.group()):
            continue
        line_start = text.rfind('\n', 0, match.start()) + 1
        previous_start = text.rfind('\n', 0, max(0, line_start - 1)) + 1
        title = text[previous_start:line_start].strip()
        url = re.search(r'\((https?://[^\s]+)\)\s*$', title)
        if url:
            refs.append(url.group(1))
        body_start = text.find('\n', match.end())
        blocks.append({'start': previous_start, 'body_start': len(text) if body_start < 0 else body_start + 1,
                       'title': title, 'kind': match.group(1), 'args': gate.parse_json(match.group(2).encode()),
                       'refs': set(refs)})
    for index, block in enumerate(blocks):
        block['end'] = blocks[index + 1]['start'] if index + 1 < len(blocks) else len(text)
    return blocks

def _read_transport(value):
    if isinstance(value, dict):
        gate.require(value.get('isError', False) is False and not value.get('error')
                     and not value.get('errors') and value.get('status', 'success') in ('success', 'completed'),
                     'selected acquisition transport failed')


def _web_header_call(args, block):
    calls = args.get(block['kind'], [])
    gate.require(isinstance(calls, list) and any(isinstance(row, dict)
                 and {k: v for k, v in row.items() if v is not None} ==
                     {k: v for k, v in block['args'].items() if v is not None} for row in calls),
                 'web return header differs from original call item')
    return calls


def _web_success(text, block):
    gate.require(not block['title'].startswith('Internal Error')
                 and not re.search(r'(?m)^L0: Failed to fetch ', text[block['body_start']:block['end']]),
                 'selected web document failed to fetch')


def _web_body(record, args, returned, result):
    allowed = {'pointer', 'start', 'end', 'source_id'}
    gate.require(set(result) <= allowed and {'pointer', 'start', 'end'} <= set(result)
                 and isinstance(args, dict) and set(args) <= {
                     'open', 'click', 'find', 'search_query', 'image_query', 'screenshot',
                     'finance', 'weather', 'sports', 'time', 'response_length'}, 'invalid web read selection')
    _read_transport(returned)
    text = _json_value(returned, result['pointer'])
    gate.require(isinstance(text, str) and text.strip(), 'web selection requires returned body text')
    if isinstance(returned, dict):
        gate.require(returned.get('isError', False) is False
                     and re.fullmatch(r'/content/\d+/text', result['pointer']) is not None,
                     'web selection requires original content text block')
        block = _json_value(returned, result['pointer'].rsplit('/', 1)[0])
        gate.require(block.get('type') == 'text', 'web selected a nontext block')
    else:
        gate.require(isinstance(returned, str) and result['pointer'] == '', 'invalid web return transport')
    start, end = result['start'], result['end']
    gate.require(type(start) is int and type(end) is int and 0 <= start < end <= len(text), 'invalid web body span')
    sections = _web_sections(text)
    if sections:
        selected = [block for block in sections if block['body_start'] <= start < end <= block['end']
                    and result.get('source_id', next(iter(block['refs']))) in block['refs']]
        gate.require(len(selected) == 1, 'web span/source ID crosses or mismatches returned documents')
        selected = selected[0]
        calls = _web_header_call(args, selected)
        _web_success(text, selected)
        target = selected['args'].get('ref_id')
        gate.require(_text(target), 'web call requires a target reference')
        if selected['kind'] == 'click':
            gate.require(type(selected['args'].get('id')) is int and selected['args']['id'] >= 0,
                         'click requires a link ID')
            expected_target = target + '#' + str(selected['args']['id'])
        else:
            expected_target = target
        gate.require(record.get('target') == expected_target, 'web call target mismatch')
        if urlsplit(target).scheme not in ('https', 'http'):
            antecedents = record.get('antecedents', [])
            gate.require(isinstance(antecedents, list) and 0 < len(antecedents) <= 1000,
                         'reference acquisition requires its original producing returns')
            available, seen = set(), {record['tool_call_ref'], record['tool_return_ref']}
            for prior in antecedents:
                prior_args, prior_return = _checked_acquisition(prior)
                gate.require(prior['tool_name'] in WEB_READ_TOOLS and
                             not {prior['tool_call_ref'], prior['tool_return_ref']} & seen,
                             'invalid or repeated reference-producing event')
                seen.update((prior['tool_call_ref'], prior['tool_return_ref']))
                _read_transport(prior_return)
                bodies = [prior_return] if isinstance(prior_return, str) else [
                    block.get('text', '') for block in prior_return.get('content', []) if isinstance(block, dict)]
                for body in bodies:
                    for block in _web_sections(body):
                        _web_header_call(prior_args, block)
                        try:
                            _web_success(body, block)
                        except gate.GateError:
                            continue
                        source = block['args'].get('ref_id')
                        gate.require(urlsplit(source or '').scheme in ('https', 'http') or source in available,
                                     'reference chain omits its producing event')
                        available.update(block['refs'])
            gate.require(target in available, 'unknown or unrelated web reference ID')
        if len(calls) > 1 or selected['kind'] == 'click' or urlsplit(target).scheme not in ('https', 'http'):
            gate.require(_text(result.get('source_id')), 'batch/reference selection requires returned source ID')
    else:
        calls = args.get('open')
        gate.require(set(args) <= {'open', 'response_length'} and isinstance(calls, list) and len(calls) == 1
                     and isinstance(calls[0], dict) and set(calls[0]) <= {'ref_id', 'lineno'},
                     'unstructured web body requires one absolute-URL open')
        target = calls[0].get('ref_id');parsed = urlsplit(target if isinstance(target, str) else '')
        gate.require(parsed.scheme in ('http', 'https') and parsed.netloc
                     and record.get('operation') == 'read_url' and record.get('target') == target
                     and result.get('source_id', target) == target, 'web acquisition call target mismatch')
        for metadata in [returned, *([block] if isinstance(returned, dict) else [])]:
            if isinstance(metadata, dict):
                for field in ('url', 'source_url'):
                    gate.require(field not in metadata or metadata[field] == target, 'web acquisition return target mismatch')
        lines = text.splitlines()
        gate.require(not (len(lines) == 3 and lines[0] == 'Internal Error ()'
                          and lines[1].endswith('; Total lines: 1')
                          and lines[2].startswith('L0: Failed to fetch ' + target + ': ')),
                     'web acquisition return reports a fetch failure')
    return text[start:end]

def _library_body(record, args, returned, result):
    gate.require(set(result) <= {'pointer', 'start', 'end', 'source_id', 'file_id', 'version_id'}
                 and {'pointer', 'start', 'end', 'source_id', 'file_id'} <= set(result)
                 and isinstance(args, dict) and set(args) == {'read'} and isinstance(args['read'], list)
                 and 1 <= len(args['read']) <= 5 and isinstance(returned, dict)
                 and returned.get('isError', False) is False, 'invalid Library acquisition selection')
    _read_transport(returned)
    match = re.fullmatch(r'((?:/structuredContent)?/results/\d+)/(content/\d+(?:/text)?)', result['pointer'])
    gate.require(match is not None, 'Library acquisition must select original document content')
    document = _json_value(returned, match.group(1))
    index = document.get('read_index')
    gate.require(type(index) is int and 0 <= index < len(args['read'])
                 and document.get('api_tool_source') == 'files/read', 'invalid Library return document')
    requested = args['read'][index].get('ref_id')
    gate.require(_text(requested) and requested == document.get('requested_file_id')
                 and requested in {document.get('ref_id'), document.get('library_file_id'), document.get('file_id')}
                 and record.get('target') == requested
                 and result['source_id'] in {document.get('library_file_id'), document.get('file_id')}
                 and _text(document.get('file_id')) and result['file_id'] == document['file_id'],
                 'Library acquisition call/document identity mismatch')
    for version in [result.get('version_id'), args['read'][index].get('version_id')]:
        if version is not None:
            gate.require(type(version) is type(document.get('version_id')) and version == document['version_id'],
                         'Library acquisition version mismatch')
    gate.require(not document.get('error') and not document.get('errors')
                 and document.get('isError', False) is False, 'selected Library document failed')
    text = _json_value(returned, result['pointer'])
    gate.require(isinstance(text, str) and text.strip(), 'Library acquisition requires body text')
    start, end = result.get('start'), result.get('end')
    gate.require(type(start) is int and type(end) is int and 0 <= start < end <= len(text), 'invalid Library body span')
    return text[start:end]


def _pdf_command(args, extraction, binding):
    command = shlex.split(args.get('cmd', ''))
    gate.require(command and (command[0] == 'pdftotext' or
                 os.path.isabs(command[0]) and os.path.normpath(command[0]) == command[0]
                 and os.path.basename(command[0]) == 'pdftotext'), 'PDF extraction requires pdftotext')
    options, paths, index = {}, [], 1
    while index < len(command):
        token = command[index]
        if token in {'-f', '-l', '-enc', '-layout', '-raw', '-nopgbrk'}:
            gate.require(token not in options, 'duplicate PDF extraction option')
            if token in {'-f', '-l', '-enc'}:
                index += 1
                gate.require(index < len(command), 'missing PDF extraction option value')
                options[token] = command[index]
            else:
                options[token] = True
        else:
            paths.append(token)
        index += 1
    gate.require(len(paths) == 2 and paths[1] == '-'
                 and not paths[0].startswith('-') and not ('-layout' in options and '-raw' in options)
                 and options.get('-enc', 'UTF-8').casefold() in {'utf-8', 'utf8'}
                 and options.get('-f', '1') == str(extraction['first_page'])
                 and options.get('-l') == (None if extraction['last_page'] is None else str(extraction['last_page']))
                 and os.path.normpath(os.path.join(args.get('workdir', ''), paths[0])) == binding.get('path'),
                 'PDF command differs from pinned input, encoding or page range')


def _claim_evidence(report, texts, sources, validated_events=(), request_sources=None, inspection=None):
    """Validate typed evidence, retained tool bindings and acyclic derivations.

    Runtime matching is recorded, not authenticated by this local checker.
    Quality reviewers still judge whether the premises imply the stated claim.
    """
    request_sources = request_sources or {}
    gate.require(not set(request_sources) & set(sources), 'request-source namespace overlaps original inputs')
    sources = {**sources, **request_sources}
    request_paths = {'request', *request_sources}
    evidence = report.get('evidence_sources')
    claims = report.get('claim_evidence')
    gate.require(isinstance(evidence, list) and isinstance(claims, list)
                 and (claims or report.get('schema_version') == 3),
                 'quality return requires evidence_sources and nonempty claim_evidence')
    added = {}
    if 'evidence/manifest.json' in sources:
        manifest = gate.parse_json(sources['evidence/manifest.json'])
        gate.require(isinstance(manifest, dict) and set(manifest) ==
                     {'schema_version', 'run_id', 'evidence_sources'}
                     and type(manifest['schema_version']) is int and manifest['schema_version'] == 1
                     and _text(manifest['run_id']) and isinstance(manifest['evidence_sources'], list),
                     'invalid submission evidence manifest')
        for item in manifest['evidence_sources']:
            gate.require(isinstance(item, dict) and _text(item.get('id')) and item['id'] not in added
                         and isinstance(item.get('source_path'), str)
                         and item['source_path'].startswith('evidence/')
                         and item['source_path'] != 'evidence/manifest.json'
                         and 'provenance' in item, 'invalid additional evidence registration')
            added[item['id']] = item
        gate.require({item['source_path'] for item in added.values()} ==
                     {path for path in sources if path.startswith('evidence/') and path != 'evidence/manifest.json'},
                     'unregistered or missing additional evidence body')
    else:
        gate.require(not any(path.startswith('evidence/') for path in sources),
                     'additional evidence requires its immutable manifest')

    def pointer(value, path):
        gate.require(isinstance(path, str) and (not path or path.startswith('/')), 'invalid JSON pointer')
        for token in path.split('/')[1:] if path else []:
            token = token.replace('~1', '/').replace('~0', '~')
            if isinstance(value, list):
                gate.require(token.isdigit() and int(token) < len(value), 'result pointer outside array')
                value = value[int(token)]
            else:
                gate.require(isinstance(value, dict) and token in value, 'unknown call/result pointer')
                value = value[token]
        gate.require(isinstance(value, str), 'call/result pointer must select exact text')
        return value

    def span(value, row):
        start, end = row.get('start'), row.get('end')
        gate.require(type(start) is int and type(end) is int and 0 <= start < end <= len(value),
                     'invalid provenance text span')
        return value[start:end]

    by_source = {}
    request_kinds = {'request-instruction', 'user-supplied-value', 'user-supplied-assumption'}
    original_kinds = {'source-proposition', 'calculation-result', 'adopted-premise'}
    for item in evidence:
        gate.require(isinstance(item, dict) and _text(item.get('id')) and item['id'] not in by_source,
                     'invalid or duplicate evidence source ID')
        kind = item.get('source_kind')
        if kind == 'operation-result':
            gate.require(set(item) == {'id', 'source_kind', 'event_id'}
                         and isinstance(item.get('event_id'), str)
                         and item['event_id'] in validated_events,
                         'operation evidence lacks an actual validated successful event')
        elif kind == 'input-file':
            gate.require(set(item) == {'id', 'source_kind', 'source_path', 'source_sha256', 'size_bytes'},
                         'invalid input-file evidence fields')
            path = item.get('source_path')
            gate.require(isinstance(path, str) and path in sources and path not in request_paths
                         and path not in texts and not path.startswith(('candidate/', 'artifacts/', 'evidence/', 'views/')),
                         'input-file requires a pinned original input path')
            data = sources[path]
            gate.require(type(item.get('size_bytes')) is int and item['size_bytes'] == len(data)
                         and item.get('source_sha256') == gate.sha(data),
                         'input-file size or digest mismatch: ' + path)
        else:
            fields = {'id', 'source_path', 'source_sha256', 'source_kind', 'start', 'end', 'quote'}
            if 'provenance' in item:
                fields.add('provenance')
            gate.require(set(item) == fields, 'invalid evidence source fields')
            path, text, start, end = _text_span(item, sources, 'source_path', 'source_sha256')
            gate.require(path not in texts and not path.startswith(('candidate/', 'artifacts/', 'views/'))
                         and path != 'evidence/manifest.json', 'generated text cannot serve as evidence')
            gate.require(kind in (request_kinds if path in request_paths else original_kinds),
                         'evidence source kind is incompatible with its source namespace')
            gate.require(_text(item.get('quote')) and item['quote'] == text[start:end],
                         'evidence source quote is missing or mismatched')
            _quantity_boundaries(text, start, end, 'evidence quote')
            if path.startswith('evidence/'):
                gate.require(item['id'] in added and gate.canonical(item) == gate.canonical(added[item['id']]),
                             'review evidence differs from immutable submission registration')
            gate.require(kind != 'calculation-result' or 'provenance' in item,
                         'calculation evidence requires input, processing and actual returned result bindings')
        by_source[item['id']] = item
    gate.require(set(added) <= set(by_source), 'review omits registered submission evidence')
    dependencies = {}
    premise_dependencies = {}
    for sid, item in by_source.items():
        provenance = item.get('provenance')
        dependencies[sid] = []
        premise_dependencies[sid] = []
        if provenance is None:
            continue
        gate.require(item['source_kind'] in original_kinds and isinstance(provenance, dict)
                     and set(provenance) in ({'tool_result', 'input_bindings', 'result'},
                         {'tool_result', 'input_bindings', 'result', 'extraction'}),
                     'invalid evidence provenance fields')
        record, inputs, result = provenance['tool_result'], provenance['input_bindings'], provenance['result']
        gate.require(isinstance(record, dict) and all(_text(record.get(k)) for k in
                     ('tool_name', 'tool_call_ref', 'tool_return_ref', 'call_args_text', 'return_text'))
                     and record['tool_call_ref'] != record['tool_return_ref']
                     and record.get('call_args_sha256') == gate.sha(record['call_args_text'].encode())
                     and record.get('return_sha256') == gate.sha(record['return_text'].encode())
                     and _source_matched(record.get('source_verification')),
                     'evidence lacks source-matched actual call and return bytes')
        args = gate.parse_json(record['call_args_text'].encode())
        returned_record = record
        extraction = provenance.get('extraction')
        is_pdf = extraction is not None
        if is_pdf:
            gate.require(item['source_kind'] == 'source-proposition' and isinstance(extraction, dict)
                         and set(extraction) == {'kind', 'input_source_id', 'first_page', 'last_page'}
                         and extraction['kind'] == 'pdf-text'
                         and type(extraction['first_page']) is int and extraction['first_page'] >= 1
                         and (extraction['last_page'] is None or type(extraction['last_page']) is int
                              and extraction['first_page'] <= extraction['last_page'])
                         and len(inputs) == 1 and inputs[0].get('source_id') == extraction['input_source_id']
                         and inputs[0].get('mode') == 'file' and inputs[0].get('processing') == [],
                         'PDF extraction requires one pinned original and an exact page range')
            original = by_source.get(extraction['input_source_id'], {})
            gate.require(original.get('source_kind') == 'input-file'
                         and sources[original['source_path']].startswith(b'%PDF-'), 'PDF extraction input is not its fixed PDF')
            _pdf_command(args, extraction, inputs[0])
        if item['source_kind'] == 'calculation-result' or is_pdf:
            gate.require(record.get('operation') == 'execute_command', 'calculation requires a command execution')
            event = {key: record.get(key) for key in ('event_id', 'operation', 'target', 'status')}
            _operation_results({'action_results_verified': [record]}, [event])
            if record.get('continuations'):
                returned_record = record['continuations'][-1]
            returns = [record] + record.get('continuations', [])
            return_refs = {row['tool_return_ref']: (index, row) for index, row in enumerate(returns)}
            fragments = result.get('fragments') if isinstance(result, dict) else None
            if fragments is not None:
                gate.require(set(result) == {'fragments'} and isinstance(fragments, list) and fragments,
                             'invalid returned-result fragments')
            else:
                fragments = [result]
            outputs = [pointer(gate.parse_json(row['return_text'].encode()), '/output')
                       for row in returns]
            offsets, total = [], 0
            for output in outputs:
                offsets.append(total)
                total += len(output)
            stdout = ''.join(outputs)
            pieces, previous, selected_start, selected_end = [], (-1, -1), None, None
            for fragment in fragments:
                gate.require(isinstance(fragment, dict) and set(fragment) in (
                    {'pointer', 'start', 'end'}, {'tool_return_ref', 'pointer', 'start', 'end'}),
                    'invalid returned-result binding')
                gate.require('tool_return_ref' in fragment or 'fragments' not in result,
                             'result fragments require explicit return references')
                ref = fragment.get('tool_return_ref', returned_record['tool_return_ref'])
                gate.require(isinstance(ref, str) and ref in return_refs,
                             'result references a return outside its validated command chain')
                index, selected_return = return_refs[ref]
                value = gate.parse_json(selected_return['return_text'].encode())
                gate.require(fragment['pointer'] == '/output', 'command result must select returned output')
                pieces.append(span(pointer(value, fragment['pointer']), fragment))
                absolute_start = offsets[index] + fragment['start']
                absolute_end = offsets[index] + fragment['end']
                gate.require(selected_end is None or absolute_start == selected_end,
                             'original return fragments omit intervening output')
                if selected_start is None:
                    selected_start = absolute_start
                selected_end = absolute_end
                gate.require(index > previous[0] or index == previous[0] and fragment['start'] >= previous[1],
                             'result fragments are reordered or overlapping')
                previous = (index, fragment['end'])
            if is_pdf:
                gate.require(selected_start == 0 and selected_end == len(stdout), 'PDF extraction must retain its complete returned page text')
            _quantity_boundaries(stdout, selected_start, selected_end, 'original return')
            calculation_body = ''.join(pieces)
        returned = gate.parse_json(returned_record['return_text'].encode())
        if item['source_kind'] != 'calculation-result' and not is_pdf:
            gate.require(isinstance(result, dict) and {'pointer', 'start', 'end'} <= set(result),
                         'invalid returned-result binding')
            acquisition_body = None
            # Fixed read operations bind the selected target within the original call.
            # call target and exact returned bytes, not document authority.
            gate.require(record.get('status') == 'success' and isinstance(args, dict),
                         'unsuccessful or invalid evidence acquisition call')
            if record['tool_name'] in WEB_READ_TOOLS:
                gate.require(record.get('operation') == 'read_url', 'web acquisition requires a read operation')
                acquisition_body = _web_body(record, args, returned, result)
            elif record['tool_name'] in LIBRARY_READ_TOOLS:
                gate.require(record.get('operation') == 'read_document', 'Library acquisition requires a read operation')
                acquisition_body = _library_body(record, args, returned, result)
            else:
                gate.require(record['tool_name'] == 'mcp__codex_apps__google_drive_get_document'
                             and record.get('operation') == 'read_document',
                             'unregistered or generative evidence acquisition tool')
                gate.require(set(result) == {'pointer', 'start', 'end'}, 'invalid document result selection')
                document_ids = []
                if args.get('document_id'):
                    document_ids.append(args['document_id'])
                if args.get('document_url'):
                    url = args['document_url']
                    gate.require(isinstance(url, str), 'invalid document acquisition URL')
                    prefix = 'https://docs.google.com/document/d/'
                    document_ids.append(url[len(prefix):].split('/')[0] if url.startswith(prefix) else url)
                gate.require(document_ids and all(_text(value) and '/' not in value and '?' not in value
                                                 and value == document_ids[0] for value in document_ids)
                             and record.get('target') == document_ids[0], 'acquisition call target mismatch')
                selected = returned
                document_id = None
                tokens = result['pointer'].split('/')[1:]
                gate.require(tokens[-2:] == ['textRun', 'content'], 'acquisition must select native document text')
                for token in tokens:
                    if isinstance(selected, dict) and 'documentId' in selected:
                        document_id = selected['documentId']
                    token = token.replace('~1', '/').replace('~0', '~')
                    if isinstance(selected, list):
                        gate.require(token.isdigit() and int(token) < len(selected), 'invalid document result path')
                        selected = selected[int(token)]
                    else:
                        gate.require(isinstance(selected, dict) and token in selected, 'invalid document result path')
                        selected = selected[token]
                gate.require(document_id == document_ids[0], 'acquisition return belongs to another document')
            pending_results = [returned] if acquisition_body is None else []
            while pending_results:
                branch = pending_results.pop()
                if isinstance(branch, dict):
                    gate.require(not branch.get('error') and not branch.get('errors')
                                 and branch.get('isError', False) is False
                                 and branch.get('status', 'success') in ('success', 'completed'),
                                 'acquisition return reports failure')
                    pending_results.extend(branch.values())
                elif isinstance(branch, list):
                    pending_results.extend(branch)
        body = sources[item['source_path']].decode('utf-8')
        gate.require((calculation_body if item['source_kind'] == 'calculation-result' or is_pdf else
                      acquisition_body if acquisition_body is not None else
                      span(pointer(returned, result['pointer']), result)) == body,
                     'evidence body differs from actual returned result')
        gate.require(isinstance(inputs, list) and (inputs or item['source_kind'] != 'calculation-result'),
                     'calculation requires explicit input bindings')
        for binding in inputs:
            gate.require(isinstance(binding, dict)
                         and isinstance(binding.get('source_id'), str) and binding['source_id'] in by_source,
                         'invalid or unknown evidence input reference')
            ref = binding['source_id']
            gate.require(by_source[ref]['source_kind'] in
                         {'user-supplied-value', 'user-supplied-assumption', 'adopted-premise',
                          'source-proposition', 'calculation-result', 'input-file'}, 'instruction/output is not a calculation input')
            if binding.get('mode', 'argument') == 'argument':
                gate.require(by_source[ref]['source_kind'] != 'input-file',
                             'input-file requires a file input binding')
                gate.require(set(binding) in ({'source_id', 'pointer', 'start', 'end'},
                             {'mode', 'source_id', 'pointer', 'start', 'end'}), 'invalid argument input binding')
                gate.require(span(pointer(args, binding['pointer']), binding) == by_source[ref].get('quote'),
                             'calculation/acquisition call uses a different input from the referenced premise')
            else:
                gate.require((item['source_kind'] == 'calculation-result' or is_pdf) and binding.get('mode') == 'file'
                             and set(binding) == {'mode', 'source_id', 'workdir', 'path', 'sha256',
                                                  'processing', 'reference'}, 'invalid file input binding')
                cwd = binding['workdir']
                gate.require(isinstance(cwd, str) and cwd.startswith('/') and os.path.normpath(cwd) == cwd
                             and args.get('workdir') == cwd, 'file input requires exact absolute execution workdir')
                chain = binding['processing']
                gate.require(isinstance(chain, list) and (chain or is_pdf), 'file input requires pinned processing code')
                previous_text = args['cmd']
                for index, link in enumerate(chain + [{key: binding[key] for key in ('source_id', 'path', 'sha256', 'reference')}]):
                    gate.require(isinstance(link, dict) and set(link) == {'source_id', 'path', 'sha256', 'reference'}
                                 and isinstance(link.get('source_id'), str) and link['source_id'] in by_source,
                                 'invalid processing dependency')
                    dependency = by_source[link['source_id']]
                    final_input = index == len(chain)
                    allowed = {'source-proposition', 'adopted-premise', 'calculation-result'}
                    if final_input:
                        allowed.add('input-file')
                    gate.require(dependency.get('source_kind') in allowed
                                 and dependency.get('source_path') in sources,
                                 'processing dependency requires pinned source bytes')
                    data = sources[dependency['source_path']]
                    gate.require(link['sha256'] == dependency['source_sha256'] == gate.sha(data),
                                 'input or processing file version mismatch')
                    path, reference = link['path'], link['reference']
                    gate.require(isinstance(path, str) and path.startswith('/') and os.path.normpath(path) == path
                                 and isinstance(reference, dict) and set(reference) == {'start', 'end'},
                                 'invalid resolved file path or reference')
                    named_path = span(previous_text, reference)
                    gate.require(os.path.normpath(os.path.join(cwd, named_path)) == path,
                                 'processing chain names a different file')
                    if not final_input:
                        previous_text = data.decode('utf-8')
                    if link['source_id'] != ref:
                        dependencies[sid].append(link['source_id'])
            dependencies[sid].append(ref)
            premise_dependencies[sid].append(ref)
        gate.require(len(premise_dependencies[sid]) == len(set(premise_dependencies[sid])),
                     'duplicate evidence input binding')
        dependencies[sid] = list(dict.fromkeys(dependencies[sid]))
    visiting, visited = set(), set()
    def visit(sid):
        gate.require(sid not in visiting, 'cyclic evidence dependency')
        if sid in visited:
            return
        visiting.add(sid)
        for ref in dependencies[sid]:
            visit(ref)
        visiting.remove(sid)
        visited.add(sid)
    for sid in by_source:
        visit(sid)
    requirements = {
        'request-adherence': ({'request-instruction'},),
        'user-supplied-value': ({'user-supplied-value'},),
        'source-observation': ({'source-proposition', 'calculation-result'},),
        'assumption': ({'user-supplied-assumption', 'adopted-premise'},),
        'derived-result': ({'user-supplied-assumption', 'adopted-premise', 'source-proposition',
                            'user-supplied-value', 'calculation-result'},),
        'operation-complete': ({'operation-result'},),
    }
    by_claim, ranges, used_sources = {}, {}, set()
    for claim in claims:
        fields = {'id', 'target', 'claim_kind', 'basis_refs'}
        if isinstance(claim, dict) and claim.get('claim_kind') == 'derived-result':
            fields.add('derivation')
        gate.require(isinstance(claim, dict) and set(claim) == fields
                     and _text(claim.get('id')) and claim['id'] not in by_claim,
                     'invalid or duplicate claim evidence ID/fields')
        target = claim['target']
        gate.require(isinstance(target, dict) and set(target) == {'path', 'sha256', 'start', 'end', 'quote'},
                     'invalid claim target fields')
        path, text, start, end = _text_span(target, texts, 'path', 'sha256')
        gate.require(target.get('quote') == text[start:end], 'claim target quote mismatch')
        kind, refs = claim['claim_kind'], claim['basis_refs']
        gate.require(isinstance(kind, str) and kind in requirements, 'unknown claim kind')
        gate.require(isinstance(refs, list) and refs and all(isinstance(ref, str) and ref in by_source for ref in refs)
                     and len(refs) == len(set(refs)), 'missing, unknown or duplicate claim basis reference')
        kinds = {by_source[ref]['source_kind'] for ref in refs}
        required = requirements[kind]
        if kind == 'derived-result' and isinstance(claim.get('derivation'), dict) and claim['derivation'].get('kind') == 'numeric':
            required = (required[0] | {'input-file'},)
        gate.require(all(kinds & allowed for allowed in required)
                     and kinds <= set().union(*required), 'claim kind lacks compatible required evidence')
        if kind == 'derived-result':
            derivation = claim['derivation']
            gate.require(isinstance(derivation, dict) and derivation.get('kind') in ('numeric', 'logical', 'comparison')
                         and _text(derivation.get('expression')), 'derived result requires concrete typed derivation')
            inputs = derivation.get('input_refs')
            gate.require(isinstance(inputs, list) and inputs and all(isinstance(ref, str) and ref in by_source for ref in inputs)
                         and len(inputs) == len(set(inputs)), 'derivation requires unique known premise references')
            if derivation['kind'] == 'numeric':
                gate.require(set(derivation) == {'kind', 'expression', 'input_refs', 'result_ref', 'result_span'}, 'invalid numeric derivation fields')
                result_ref = derivation['result_ref']
                gate.require(isinstance(result_ref, str) and result_ref in by_source
                             and by_source[result_ref]['source_kind'] == 'calculation-result'
                             and set(inputs) == set(premise_dependencies[result_ref])
                             and set(refs) == set(inputs) | {result_ref}
                             and derivation['expression'] == by_source[result_ref]['provenance']['tool_result']['target'],
                             'numeric derivation does not match its actual inputs, processing and result')
                result_span = derivation['result_span']
                gate.require(isinstance(result_span, dict) and set(result_span) == {'start', 'end'}
                             and type(result_span['start']) is int and type(result_span['end']) is int
                             and start <= result_span['start'] < result_span['end'] <= end
                             and span(text, result_span) == by_source[result_ref]['quote'].strip(),
                             'numeric claim result differs from the returned calculation')
                _quantity_result(text, result_span['start'], result_span['end'],
                                 inspection.views(path, texts[path]) if inspection else None)
            else:
                gate.require(set(derivation) == {'kind', 'expression', 'input_refs'} and set(inputs) == set(refs),
                             'logical/comparison derivation must bind all stated premises')
        ranges.setdefault(path, []).append((start, end))
        by_claim[claim['id']] = claim
        used_sources.update(refs)
    # Definitions may be evidence for terminology alone, rather than a premise
    # of the main claim. Reuse the same exact original-source ledger.
    for usage in report.get('technical_usages', []):
        gate.require(isinstance(usage, dict) and isinstance(usage.get('definition_refs'), list),
                     'term usage requires definition_refs')
        for ref in usage['definition_refs']:
            gate.require(isinstance(ref, str) and ref in by_source
                         and by_source[ref]['source_kind'] == 'source-proposition',
                         'term definition must reference original source-proposition evidence')
            used_sources.add(ref)
    for usage in report.get('occurrence_judgments', []):
        gate.require(isinstance(usage, dict) and isinstance(usage.get('source_refs'), list),
                     'occurrence judgment requires source_refs')
        for ref in usage['source_refs']:
            gate.require(isinstance(ref, str) and ref in by_source,
                         'occurrence references unknown original evidence')
            used_sources.add(ref)
    for reproduction in report.get('source_reproductions', []):
        gate.require(isinstance(reproduction, dict) and reproduction.get('source_id') in by_source,
                     'source reproduction references unknown original evidence')
        used_sources.add(reproduction['source_id'])
    pending = list(used_sources)
    while pending:
        for ref in dependencies[pending.pop()]:
            if ref not in used_sources:
                used_sources.add(ref)
                pending.append(ref)
    gate.require(used_sources == set(by_source), 'unreferenced evidence source')
    if report.get('schema_version') == 2:
        # Legacy records retain their stricter span contract before conversion.
        gate.require(set(ranges) == set(texts), 'claim ledger omits a final text, attachment or view')
    for path, data in texts.items():
        spans = ranges.get(path, [])
        text = data.decode('utf-8')
        gate.require(len(spans) == len(set(spans)), 'duplicate claim target range: ' + path)
        position = 0
        for start, end in sorted(spans):
            gate.require(start >= position, 'claim ledger has overlapping targets: ' + path)
            if report.get('schema_version') == 2:
                gate.require(not text[position:start].strip(),
                             'claim ledger has uncovered meaningful text: ' + path)
            position = end
        if report.get('schema_version') == 2:
            gate.require(not text[position:].strip(), 'claim ledger omits meaningful final text: ' + path)
        else:
            # Structure, connectives and punctuation are not propositions. The
            # whole-scope reviewer checks omitted conclusions and other claims;
            # numeric content has an additional mechanical omission guard.
            marker_spans = [match.span(1) for match in re.finditer(r'(?m)^[ \t]*(\d+)[.)][ \t]+', text)]
            regions = (inspection.regions(path, data) if inspection else gate.structure_regions(data))
            metadata_spans = [(row['start'], row['end']) for row in regions['regions']
                              if row['kind'] in ('link_destination', 'identifier')]
            for left, right in _quantity_spans(text):
                if any(a <= left and right <= b for a, b in marker_spans + metadata_spans):
                    continue
                gate.require(any(a <= left and right <= b for a, b in spans),
                             'claim ledger omits a quantity-bearing proposition: ' + path)
    return by_claim


def _prose_record(record, claims, candidate_sha256):
    """Each whole-candidate judgment references the one typed evidence ledger."""
    gate.require(set(record) == PROSE_RECORD_FIELDS, 'invalid prose check fields')
    gate.require(record.get('verdict') in ('absent', 'violation', 'unassessed'),
                 'prose verdict must be absent, violation or unassessed')
    gate.require(record.get('candidate_sha256') == candidate_sha256,
                 'stale or absent prose check candidate binding')
    gate.require(_text(record.get('evidence')), 'prose check lacks assessment evidence')
    refs = record.get('claim_refs')
    gate.require(isinstance(refs, list) and all(isinstance(ref, str) for ref in refs)
                 and len(refs) == len(set(refs)) and set(refs) == set(claims),
                 'prose claim_refs must cover each claim exactly once')


def claim_ledger_sha256(claims, evidence):
    """Stable common binding, independent of per-check verdicts."""
    return gate.sha(gate.canonical({'claim_evidence': claims, 'evidence_sources': evidence}))


def quality_review_record(candidate_sha256, claims, evidence, text_paths, assessment,
                          verdicts, occurrence_judgments=()):
    """Generate the v3 common fields; never manufacture judgments or approval."""
    return {'schema_version': 3, 'candidate_sha256': candidate_sha256,
            'claim_evidence': claims, 'evidence_sources': evidence,
            'claim_ledger_sha256': claim_ledger_sha256(claims, evidence),
            'review_scope': sorted(text_paths), 'assessment': assessment,
            'prose_verdicts': dict(verdicts),
            'occurrence_judgments': list(occurrence_judgments)}


def _prose_records(report, role, texts, request_bytes, bindings, failed, missing, unresolved,
                   original_sources=None, validated_events=(), request_sources=None, inspection=None):
    """One full-candidate scope/ledger binding and all 22 functional verdicts.

    V2 is read and checked under its original contract, then normalized to the
    same common view. Original return bytes and transport hashes never change.
    """
    claims = _claim_evidence(report, texts, {**(original_sources or {}), 'request': request_bytes},
                             validated_events, request_sources, inspection)
    common = {'candidate_sha256': bindings['candidate_sha256'],
              'claim_ledger_sha256': claim_ledger_sha256(report['claim_evidence'], report['evidence_sources']),
              'review_scope': sorted(texts)}
    if report.get('schema_version') == 3:
        gate.require('prose_checks' not in report and 'technical_usages' not in report,
                     'version 3 uses common prose_verdicts and occurrence_judgments')
        gate.require(report.get('claim_ledger_sha256') == common['claim_ledger_sha256'],
                     'stale or absent common claim ledger hash')
        scope = report.get('review_scope')
        gate.require(isinstance(scope, list) and all(isinstance(path, str) for path in scope)
                     and len(scope) == len(set(scope)) and sorted(scope) == common['review_scope'],
                     'review_scope must include every complete final text, attachment and view once')
        gate.require(_text(report.get('assessment')), 'whole-candidate assessment is required')
        verdicts = report.get('prose_verdicts')
        gate.require(isinstance(verdicts, dict) and not set(verdicts) - set(PROSE_CHECK_IDS),
                     'unknown prose verdict ID')
        common['assessment'] = report['assessment']
    else:
        records = report.get('prose_checks')
        if records is None:
            _issue(missing, role, 'original return lacks all 22 individual prose_checks')
            return
        gate.require(isinstance(records, list), 'prose_checks must be an array')
        verdicts, assessments = {}, []
        for record in records:
            gate.require(isinstance(record, dict), 'individual prose check must be an object')
            check_id = record.get('check_id')
            gate.require(isinstance(check_id, str) and check_id in PROSE_CHECK_IDS and check_id not in verdicts,
                         'unknown or duplicate prose check ID')
            verdicts[check_id] = record.get('verdict')
            try:
                _prose_record(record, claims, bindings['candidate_sha256'])
            except (ValueError, TypeError, KeyError, AttributeError) as exc:
                _issue(failed, role + ':' + check_id, str(exc))
                continue
            assessments.append({'check_id': check_id, 'assessment': record['evidence']})
        common['legacy_assessments'] = assessments
    common['prose_verdicts'] = verdicts
    report['prose_review'] = common
    for check_id in PROSE_CHECK_IDS:
        label = role + ':' + check_id
        if check_id not in verdicts:
            _issue(missing, label, 'individual prose assessment is missing from original return')
            continue
        verdict = verdicts[check_id]
        gate.require(verdict in ('absent', 'violation', 'unassessed'),
                     'prose verdict must be absent, violation or unassessed')
        if verdict == 'absent':
            continue
        if report.get('schema_version') == 3:
            field = 'findings' if verdict == 'violation' else 'unassessed'
            details = [row for row in report.get(field, [])
                       if isinstance(row, dict) and row.get('check_id') == check_id]
            gate.require(details, 'non-absent prose verdict requires its concrete located finding')
            for finding in details:
                target = finding.get('target')
                gate.require(isinstance(target, dict) and set(target) == {'path', 'sha256', 'start', 'end', 'quote'},
                             'prose finding requires an exact target')
                path, text, left, right = _text_span(target, texts, 'path', 'sha256')
                gate.require(target['quote'] == text[left:right] and _text(finding.get('assessment')),
                             'prose finding target or assessment mismatch')
                refs = finding.get('claim_refs')
                gate.require(isinstance(refs, list) and len(refs) == len(set(refs))
                             and all(isinstance(ref, str) and ref in claims for ref in refs),
                             'prose finding references unknown or duplicate claims')
        (_issue(failed, label, 'returned prose assessment records a violation')
         if verdict == 'violation' else _issue(missing, label, 'returned prose assessment is unassessed'))
        unresolved.append({'check': label, 'finding': verdict})


def _coordinates(item):
    gate.require(isinstance(item, dict)
                 and isinstance(item.get('rule_id'), str)
                 and isinstance(item.get('path'), str)
                 and type(item.get('start')) is int
                 and type(item.get('end')) is int, 'invalid disposition coordinates')
    return tuple(item[k] for k in ('rule_id', 'path', 'start', 'end'))


def _source_reproductions(report, texts):
    """Verify literal source correspondence without changing prohibition results."""
    records = report.get('source_reproductions', [])
    gate.require(isinstance(records, list), 'source_reproductions must be an array')
    evidence = {row['id']: row for row in report.get('evidence_sources', [])}
    seen = set()
    for record in records:
        gate.require(isinstance(record, dict) and set(record) ==
                     {'kind', 'target_path', 'target_start', 'target_end', 'source_id'},
                     'invalid source reproduction fields')
        gate.require(record['kind'] in ('quotation', 'bibliography')
                     and record['target_path'] in texts and record['source_id'] in evidence,
                     'source reproduction requires a registered source and target')
        source = evidence[record['source_id']]
        gate.require(source.get('source_kind') != 'operation-result' and _text(source.get('quote')),
                     'literal reproduction requires exact source text')
        text = texts[record['target_path']].decode('utf-8')
        start, end = record['target_start'], record['target_end']
        gate.require(type(start) is int and type(end) is int and 0 <= start < end <= len(text)
                     and text[start:end] == source['quote'],
                     'verbatim target differs from the registered source quotation')
        key = (record['target_path'], start, end, record['source_id'])
        gate.require(key not in seen, 'duplicate source reproduction')
        seen.add(key)


def _legacy_technical_usages(report, hits, texts, inspection=None):
    """Bind narrow technical/lexical judgments.

    Every spelling match remains blocked until the existing quality reviewer
    establishes either genuine technical use or a different Japanese word.
    Definitions in the dictionary are hints; unlisted technical definitions use
    the already validated claim/evidence ledger rather than a new allowlist.
    """
    inspection = inspection or gate.TextInspection()
    items = report.get('technical_usages', [])
    gate.require(isinstance(items, list), 'technical_usages must be an array')
    lookup = {_coordinates(hit): hit for hit in hits}
    fields = {'rule_id', 'path', 'start', 'end', 'term_text', 'domain', 'definition',
              'term_start', 'term_end', 'character_spans', 'input_sha256',
              'decision', 'definition_relation', 'definition_id', 'definition_refs'}
    evidence = {item['id']: item for item in report.get('evidence_sources', [])}
    resolved = {}
    for item in items:
        key = _coordinates(item)
        gate.require(set(item) == fields and key in lookup and key not in resolved,
                     'invalid or duplicate technical/lexical usage')
        gate.require(item['decision'] in ('technical-use', 'different-word')
                     and all(_text(item[field]) for field in
                             ('term_text', 'domain', 'definition', 'definition_relation')),
                     'only defined technical terms or different lexical words are eligible')
        hit, path = lookup[key], item['path']
        gate.require(path in texts and item['input_sha256'] == gate.sha(texts[path]),
                     'usage input hash mismatch')
        term = gate.norm(item['term_text'])
        gate.require(term == item['term_text'] and term == term.strip(),
                     'term_text must use normalized source-view spelling')
        spans = item['character_spans']
        gate.require(isinstance(spans, list) and spans
                     and all(isinstance(pair, list) and len(pair) == 2
                             and all(type(x) is int for x in pair) and 0 <= pair[0] < pair[1] for pair in spans),
                     'invalid constituent character spans')
        expected = {'text': term, 'start': item['term_start'], 'end': item['term_end'],
                    'character_spans': spans}
        # Japanese has no whitespace word delimiter. Boundary identity is a
        # review judgment; English word fragments cannot become term candidates.
        boundaries = any('a' <= character <= 'z' for character in term)
        views = inspection.views(path, texts[path])
        gate.require(type(item['term_start']) is int and type(item['term_end']) is int
                     and any({**occurrence, 'text': gate.term_key(occurrence['text'])}
                             == {**expected, 'text': gate.term_key(term)}
                             for occurrence in inspection.occurrences(term, path, texts[path], boundaries))
                     and gate.covers(spans, hit['character_spans']),
                     'usage must match actual constituents and cover only its own hit')
        refs = item['definition_refs']
        gate.require(isinstance(refs, list) and all(isinstance(ref, str) and ref in evidence and evidence[ref]['source_kind'] == 'source-proposition' for ref in refs)
                     and len(refs) == len(set(refs)), 'invalid original definition references')
        basis = None
        if item['decision'] == 'different-word':
            # This is an eligibility constraint, never automatic segmentation:
            # reviewers must establish a whole different word, not a phrase,
            # quoted occurrence, approximation or surviving rhetorical function.
            gate.require(item['definition_id'] is None
                         and item['domain'] == 'lexical' and len(spans) > len(hit['character_spans'])
                         and all((0x3041 <= ord(c) <= 0x3096 or 0x30A1 <= ord(c) <= 0x30FA
                                  or 0x3400 <= ord(c) <= 0x4DBF or 0x4E00 <= ord(c) <= 0x9FFF
                                  or 0x20000 <= ord(c) <= 0x323AF or c in '々ー') for c in term),
                         'different-word requires a longer adjacent Japanese lexical word')
            if refs:
                basis = {'sources': [gate.parse_json(value) for value in sorted({
                    gate.canonical({field: evidence[ref][field] for field in
                                    ('source_path', 'source_sha256', 'start', 'end', 'quote')}) for ref in refs})]}
        else:
            if item['definition_id'] is not None:
                gate.require(_text(item['definition_id']) and not refs,
                             'registered definitions use one hint ID, not external proof references')
                hinted = [candidate for candidate in hit.get('technical_candidates', [])
                          if candidate['definition_id'] == item['definition_id']
                          and gate.term_key(candidate['text']) == gate.term_key(term)
                          and candidate['character_spans'] == spans]
                gate.require(hinted, 'definition ID must match this exact registered term occurrence')
                basis = {'registered': sorted((candidate['term_id'], candidate['definition_id'])
                                              for candidate in hinted)}
            else:
                gate.require(refs, 'unlisted technical definition requires original definition evidence')
                source_bindings = {gate.canonical({field: evidence[ref][field] for field in
                                   ('source_path', 'source_sha256', 'start', 'end', 'quote')}) for ref in refs}
                basis = {'sources': [gate.parse_json(value) for value in sorted(source_bindings)]}
        # Independent definition prose, explanations and local proof IDs can
        # differ. Consensus pins the actual definition source, not prose style.
        identity_fields = fields - {'definition_relation', 'definition_refs', 'domain', 'definition',
                                    'rule_id', 'start', 'end'}
        judgment = gate.canonical({**{field: item[field] for field in identity_fields},
                                   'term_text': gate.term_key(term), 'definition_basis': basis})
        for covered_key, covered in lookup.items():
            if covered['path'] == path and gate.covers(spans, covered['character_spans']):
                if covered['rule_id'] == 'ja-067':
                    quantity = gate.quantity_modifier_spans(covered, views)
                    gate.require(not quantity or quantity['kind'] != 'quantity'
                                 or not any(a < d and c < b for a, b in spans for c, d in quantity['character_spans']),
                                 'quantity modifier cannot be reclassified as a compound or technical divisor')
                    if quantity and item['decision'] == 'different-word':
                        gate.require(refs and any(term in gate.norm(evidence[ref]['quote']) for ref in refs),
                                     'a lexical word adjoining quantity or ambiguous formation requires its fixed original definition')
                gate.require(covered_key not in resolved or resolved[covered_key] == judgment,
                             'conflicting judgments for a contained match')
                resolved[covered_key] = judgment
    return resolved


def _occurrence_judgments(report, hits, texts, inspection=None):
    """Verify occurrence identity and recorded function.

    A quote/code/technical label is never an approval. The selected reviewer
    supplies a function/sense/syntax/proposition judgment for this exact span;
    prohibited or unassessed functions remain blocked. Original-source identity
    additionally requires literal equality against the validated source ledger.
    """
    inspection = inspection or gate.TextInspection()
    items = report.get('occurrence_judgments', [])
    gate.require(isinstance(items, list), 'occurrence_judgments must be an array')
    lookup, resolved, seen = {_coordinates(hit): hit for hit in hits}, {}, set()
    decisions, pending = {}, []

    def occurrence_key(hit):
        return (hit['path'], tuple(tuple(span) for span in hit['character_spans']))
    fields = {'rule_id', 'path', 'start', 'end', 'input_sha256', 'text', 'text_start', 'text_end',
              'character_spans', 'verdict', 'prohibited_function', 'function', 'sense', 'syntax_role',
              'target_proposition', 'assessment', 'claim_refs', 'source_refs', 'source_identity', 'meaning'}
    evidence = {row['id']: row for row in report.get('evidence_sources', [])}
    claims = {row['id']: row for row in report.get('claim_evidence', [])}
    for item in items:
        key = _coordinates(item)
        gate.require(set(item) == fields and key in lookup and key not in seen,
                     'invalid, unknown or duplicate occurrence judgment')
        seen.add(key)
        hit, path = lookup[key], item['path']
        gate.require(path in texts and item['input_sha256'] == gate.sha(texts[path]),
                     'occurrence input hash mismatch')
        gate.require(item['verdict'] in ('absent', 'violation', 'unassessed')
                     and type(item['prohibited_function']) is bool
                     and all(_text(item[name]) for name in ('text', 'function', 'sense', 'syntax_role',
                                                           'target_proposition', 'assessment')),
                     'occurrence requires function, sense, syntax and preserved proposition judgments')
        term, spans = item['text'], item['character_spans']
        gate.require(term == gate.norm(term) and term == term.strip()
                     and isinstance(spans, list) and spans
                     and all(isinstance(pair, list) and len(pair) == 2
                             and all(type(x) is int for x in pair) and 0 <= pair[0] < pair[1] for pair in spans),
                     'occurrence requires normalized text and actual constituent spans')
        expected = {'text': term, 'start': item['text_start'], 'end': item['text_end'], 'character_spans': spans}
        views = inspection.views(path, texts[path])
        gate.require(type(item['text_start']) is int and type(item['text_end']) is int
                     and any({**row, 'text': gate.term_key(row['text'])} ==
                             {**expected, 'text': gate.term_key(term)}
                             for row in inspection.occurrences(term, path, texts[path], any('a' <= c <= 'z' for c in term)))
                     and gate.covers(spans, hit['character_spans']),
                     'occurrence must match actual constituents and contain its exact anchor hit')
        for name, known in (('claim_refs', claims), ('source_refs', evidence)):
            refs = item[name]
            gate.require(isinstance(refs, list) and len(refs) == len(set(refs))
                         and all(isinstance(ref, str) and ref in known for ref in refs),
                         'unknown or duplicate occurrence ' + name)
        gate.require(item['claim_refs'] or item['source_refs'],
                     'occurrence needs its proposition or original-source correspondence')
        for ref in item['claim_refs']:
            target = claims[ref]['target']
            gate.require(target['path'] == path and target['start'] <= item['text_start']
                         and item['text_end'] <= target['end'],
                         'occurrence claim reference does not contain this occurrence')
        meaning = item['meaning']
        gate.require(isinstance(meaning, dict) and set(meaning) == MEANING_FIELDS
                     and all(_text(meaning[name]) for name in
                             ('proposition_id', 'actor', 'predicate', 'object', 'relation_type'))
                     and meaning['modality'] in ('permission', 'obligation', 'ability', 'feasibility',
                                                 'actuality', 'epistemic-uncertainty', 'none')
                     and meaning['polarity'] in ('positive', 'negative', 'not-applicable')
                     and meaning['source_relation'] in ('quotation', 'bibliography', 'identifier',
                                                        'paraphrase', 'generated-proposition')
                     and all(isinstance(meaning[name], list) and
                             all(_text(value) for value in meaning[name]) for name in ('quantifiers', 'conditions'))
                     and isinstance(meaning['quantities_and_units'], list)
                     and all(isinstance(value, dict) and set(value) == {'quantity', 'unit'}
                             and _text(value['quantity']) and _text(value['unit'])
                             for value in meaning['quantities_and_units']),
                     'occurrence needs its complete typed proposition meaning')
        gate.require(meaning['proposition_id'] in item['claim_refs']
                     or not item['claim_refs'] and meaning['proposition_id'] in item['source_refs'],
                     'occurrence proposition ID must bind its claim or original source')
        identity = item['source_identity']
        literal = meaning['source_relation'] in ('quotation', 'bibliography', 'identifier')
        reproductions = [row for row in report.get('source_reproductions', [])
                         if row.get('target_path') == path and
                         row.get('target_start', -1) <= item['text_start'] and
                         item['text_end'] <= row.get('target_end', -1)]
        gate.require(not (literal or reproductions) or identity is not None,
                     'literal quotation/bibliography/identifier requires original-source identity')
        source_binding = None
        if identity is not None:
            gate.require(isinstance(identity, dict) and set(identity) ==
                         {'kind', 'source_id', 'target_start', 'target_end'}
                         and identity['kind'] in ('quotation', 'bibliography', 'identifier')
                         and identity['kind'] == meaning['source_relation']
                         and identity['source_id'] in item['source_refs'],
                         'invalid literal original-source identity')
            source = evidence[identity['source_id']]
            left, right = identity['target_start'], identity['target_end']
            raw = texts[path].decode('utf-8')
            gate.require(type(left) is int and type(right) is int
                         and 0 <= left <= item['text_start'] < item['text_end'] <= right <= len(raw)
                         and raw[left:right] == source['quote']
                         and source['source_kind'] != 'operation-result',
                         'literal occurrence differs from its fixed original source')
            gate.require(not reproductions or any(row['kind'] == identity['kind']
                         and row['source_id'] == identity['source_id']
                         and row['target_start'] == left and row['target_end'] == right
                         for row in reproductions),
                         'occurrence identity differs from its source reproduction')
            source_binding = {name: source[name] for name in
                              ('source_path', 'source_sha256', 'start', 'end', 'quote')}
        # Validate every explicit verdict before sharing any absent judgment
        # across duplicate rule matches on these exact contributing characters.
        # Negative and unassessed records dominate, independent of input order.
        blocked = item['verdict'] != 'absent' or item['prohibited_function']
        decisions.setdefault(occurrence_key(hit), []).append(blocked)
        if blocked:
            continue
        claim_targets = [claims[ref]['target'] for ref in item['claim_refs']]
        sources = [{name: evidence[ref][name] for name in
                    ('source_path', 'source_sha256', 'start', 'end', 'quote')}
                   for ref in item['source_refs']]
        judgment = gate.canonical({'path': path, 'input_sha256': item['input_sha256'],
                                   'text': gate.term_key(term), 'text_start': item['text_start'],
                                   'text_end': item['text_end'], 'character_spans': spans,
                                   'claim_targets': sorted(claim_targets, key=gate.canonical),
                                   'sources': sorted(sources, key=gate.canonical),
                                   'meaning': meaning,
                                   'literal_identity': source_binding})
        pending.append((occurrence_key(hit), judgment))
    for values in decisions.values():
        gate.require(not (any(values) and not all(values)),
                     'conflicting verdicts for the same occurrence: explicit violation or unassessed cannot be cleared by absent')
    for occurrence, judgment in pending:
        if any(decisions[occurrence]):
            continue
        for covered_key, covered in lookup.items():
            if occurrence_key(covered) == occurrence:
                # Share only an uncontradicted judgment on this occurrence,
                # never every hit inside a quoted/code/paragraph envelope.
                gate.require(covered_key not in resolved or resolved[covered_key] == judgment,
                             'conflicting judgments for a contained match')
                resolved[covered_key] = judgment
    return resolved


def _technical_usages(report, hits, texts, inspection=None):
    """Read v2 under its original constraints; v3 uses general occurrences."""
    if report.get('schema_version') == 3:
        return _occurrence_judgments(report, hits, texts, inspection)
    resolved = _legacy_technical_usages(report, hits, texts, inspection)
    # A derived compatibility view; never rewrite the signed original return.
    converted = []
    evidence = {row['id']: row for row in report.get('evidence_sources', [])}
    for usage in report.get('technical_usages', []):
        claims = [row['id'] for row in report.get('claim_evidence', [])
                  if row['target']['path'] == usage['path']
                  and row['target']['start'] <= usage['term_start']
                  and usage['term_end'] <= row['target']['end']]
        converted.append({**{name: usage[name] for name in
                             ('rule_id', 'path', 'start', 'end', 'input_sha256', 'character_spans')},
                          'text': usage['term_text'], 'text_start': usage['term_start'],
                          'text_end': usage['term_end'], 'verdict': 'absent',
                          'prohibited_function': False, 'function': usage['decision'],
                          'sense': usage['definition'], 'syntax_role': usage['domain'],
                          'target_proposition': usage['definition_relation'],
                          'assessment': usage['definition_relation'], 'claim_refs': claims,
                          'source_refs': list(usage['definition_refs']), 'source_identity': None,
                          'legacy_definition': {name: usage[name] for name in
                                                ('decision', 'definition_id', 'definition_refs')}})
    # Literal correspondence alone was never an absent-function judgment. Its
    # converted view stays unassessed and cannot add a resolved coordinate.
    for reproduction in report.get('source_reproductions', []):
        source = evidence[reproduction['source_id']]
        converted.append({'verdict': 'unassessed', 'source_identity': {
            'kind': reproduction['kind'], 'source_id': reproduction['source_id'],
            'path': reproduction['target_path'], 'target_start': reproduction['target_start'],
            'target_end': reproduction['target_end']},
            'original_source': {name: source[name] for name in
                                ('source_path', 'source_sha256', 'start', 'end', 'quote')}})
    report['occurrence_review'] = {'migration': 'v2-to-occurrence-view',
                                   'occurrence_judgments': converted}
    return resolved


def _surface_result(result, surface, candidate_bytes, contract=None):
    """Expose lexical, semantic and authorization states without conflating them."""
    completion = set()
    if surface != 'final' and isinstance(contract, dict):
        completion = {row['id'] for row in contract.get('requirements', [])
                      if row.get('kind') in ('artifact', 'action', 'content', 'evidence')}
    parent_unmet = result.get('requirements', {}).get('unmet', [])
    deferred = [row for row in parent_unmet if row.get('requirement_id') in completion
                and row.get('code') in ('artifact_invalid', 'missing_action_event', 'action_unsuccessful',
                                        'condition_unmet', 'condition_pending')]
    # A progress surface can be fully reviewed while its parent task's final
    # artifact/action/content remains unfinished. Never defer an invalid input,
    # prohibited operation or other preserved prohibition. Parent state remains
    # unchanged and cannot authorize the final deliverable.
    completion_only = bool(parent_unmet) and len(deferred) == len(parent_unmet)
    unresolved = [row for row in [*result['failed_checks'], *result['missing_checks'], *result['unresolved']]
                  if not (completion_only and row.get('check') == 'requirements')]
    verdicts = {role: result.get('reviews', {}).get(role, {}).get('prose_review', {}).get('prose_verdicts', {})
                for role in ('quality-a', 'quality-b')}
    complete = (result.get('prose_scan', {}).get('dictionary_rule_count') == 142
                and all(result.get('reviews', {}).get(role, {}).get('status') == 'consistent'
                        and result['reviews'][role].get('normalized_return', {}).get('schema_version') == 3
                        and set(verdicts[role]) == set(PROSE_CHECK_IDS)
                        and all(value == 'absent' for value in verdicts[role].values()) for role in verdicts)
                and not unresolved)
    result['surface_check'] = {
        'surface': surface, 'text_sha256': gate.sha(candidate_bytes) if isinstance(candidate_bytes, bytes) else None,
        'evidence_event_ids': [row['event_id'] for row in result.get('operation_results', []) if row.get('event_id')],
        'scan_complete': result.get('prose_scan', {}).get('status') == 'scanned',
        'lexical_hits': result.get('prose_scan', {}).get('hits', []),
        'quality_a_prose_verdicts': verdicts['quality-a'],
        'quality_b_prose_verdicts': verdicts['quality-b'],
        'unresolved': unresolved,
        'deferred_completion_requirement_ids': sorted({row['requirement_id'] for row in deferred}),
        'parent_unmet': parent_unmet,
        'review_status': 'consistent' if complete else 'incomplete',
        'release_authorized': False,
    }
    return result


def check_native(candidate_name, candidate_bytes, request_bytes, contract_bytes,
                 artifacts, events_bytes, dictionary_bytes, author_id,
                 expected_request_sha256, expected_contract_sha256,
                 expected_candidate_sha256, reports=None, text_views=None, run_id=None, sources=None, review_plan='strict-reviewed', review_definition=None, view_files=None, surface='final'):
    """Check one immutable in-memory snapshot. Artifacts map safe paths to bytes.

    Filesystem/host callers own collection and external provenance verification.
    The optional reports envelope is schema_version=1, reports=[], unresolved_flags=[].
    No supplied status or provenance label is treated as authentication.
    """
    result = {
        'schema_version': 1, 'status': 'incomplete',
        'recorded_checks_complete': False, 'full_pass': False,
        'release_authorized': False, 'executed_checks': [],
        'failed_checks': [], 'missing_checks': [], 'unresolved': [],
        'bindings': {}, 'reviews': {}, 'operation_results': [],
        'provenance': {'classification': 'caller-supplied', 'authenticated': False,
                       'host_verification': 'not-performed-by-this-tool'},
        'limitations': LIMITATION,
    }
    failed, missing, unresolved = (result[k] for k in ('failed_checks', 'missing_checks', 'unresolved'))
    try:
        gate.require(all(isinstance(x, bytes) for x in
                         (candidate_bytes, request_bytes, contract_bytes, events_bytes, dictionary_bytes)),
                     'candidate, request, contract, events and dictionary must be exact bytes')
        gate.require(all(len(x) <= gate.MAX_BYTES for x in
                         (candidate_bytes, request_bytes, contract_bytes, events_bytes, dictionary_bytes)),
                     'managed text or JSON exceeds byte budget')
        gate.require(_text(author_id), 'actual executor author_id is required')
        gate.require(surface in SURFACES, 'unknown outgoing text surface')
        gate.require(surface == 'final' or review_plan == 'strict-reviewed',
                     'progress/status/error free text requires both complete independent quality reviews')
        gate.require(review_plan in REVIEW_PLANS, 'invalid review plan')
        selected_definition = REVIEW_PLANS[review_plan]
        gate.require(review_definition is None or review_definition == selected_definition,
                     'supplied review definition differs from registered plan')
        roles = tuple(selected_definition['roles'])
        quality_roles = tuple(selected_definition.get('quality_roles', [role for role in roles if role.startswith('quality-')]))
        review_kind = selected_definition.get('review_kind', 'independent')
        gate.require(_text(candidate_name) and Path(candidate_name).suffix.lower() in gate.TEXT_SUFFIXES,
                     'candidate must have a supported UTF-8 text suffix')
        gate.require(candidate_bytes.strip(), 'candidate must be nonempty')
        candidate_text = candidate_bytes.decode('utf-8')
        gate.require(not any(ord(c) < 32 and c not in '\t\n\r\f' for c in candidate_text),
                     'candidate contains unsupported binary controls')
        gate.require(isinstance(artifacts, dict), 'artifacts must map safe paths to bytes')
        gate.require(len(artifacts) <= MAX_FILES, 'too many artifacts')
        total = 0
        for path, data in artifacts.items():
            gate.safe_relative(path)
            gate.require(gate.is_content(data), 'artifact requires bytes or a fixed file version')
        sources = {} if sources is None else sources
        gate.require(isinstance(sources, dict) and len(sources) <= MAX_FILES,
                     'sources must map original source paths to bytes')
        source_total = 0
        for path, data in sources.items():
            gate.safe_relative(path)
            gate.require(not path.startswith(('candidate/', 'artifacts/', 'views/')) and path != 'request',
                         'original sources cannot use generated-output or request namespaces')
            gate.require(gate.is_content(data), 'source requires bytes or a fixed file version')
        if 'evidence/manifest.json' in sources:
            evidence_manifest = gate.parse_json(sources['evidence/manifest.json'])
            gate.require(isinstance(evidence_manifest, dict) and run_id is not None
                         and evidence_manifest.get('run_id') == run_id,
                         'submission evidence must belong to the current canonical run ID')
        source_entries = [{'path': path, 'sha256': gate.sha(data)} for path, data in sorted(sources.items())]
        text_views = {} if text_views is None else text_views
        gate.require(isinstance(text_views, dict), 'text_views must be an object')
        view_files = {} if view_files is None else view_files
        gate.require(isinstance(view_files, dict) and len(view_files) <= MAX_FILES
                     and all(gate.is_content(data) for data in view_files.values()),
                     'internal views must map safe paths to fixed content')
        entries = [{'path': path, 'sha256': gate.sha(data)} for path, data in sorted(artifacts.items())]
        bindings = {
            'candidate_sha256': gate.sha(candidate_bytes),
            'request_sha256': gate.sha(request_bytes), 'contract_sha256': gate.sha(contract_bytes),
            'events_sha256': gate.sha(events_bytes), 'dictionary_sha256': gate.sha(dictionary_bytes),
            'artifacts_sha256': gate.sha(gate.canonical(entries)),
            'text_views_sha256': gate.sha(gate.canonical(text_views)),
            'sources_sha256': gate.sha(gate.canonical(source_entries)),
        }
        if run_id is not None:
            parsed_run = uuid.UUID(run_id)
            gate.require(parsed_run.version == 4 and str(parsed_run) == run_id,
                         'run_id must be a canonical UUIDv4')
            bindings['run_id'] = run_id
        if review_plan != 'full':
            bindings['review_plan'] = review_plan
        if surface != 'final':
            bindings['surface'] = surface
        result.update(bindings=bindings, artifacts=entries, sources=source_entries, review_plan=review_plan)
        result['executed_checks'].append('input-bindings')
        for field, expected in [('request_sha256', expected_request_sha256),
                                ('contract_sha256', expected_contract_sha256),
                                ('candidate_sha256', expected_candidate_sha256)]:
            if not gate.hexhash(expected) or expected != bindings[field]:
                _issue(failed, 'input-bindings', 'missing or mismatched independently retained ' + field)
        contract = gate.parse_json(contract_bytes)
        events = gate.parse_json(events_bytes)
        if review_plan in ('focused', 'direct'):
            gate.require(not events and not any(row.get('kind') == 'action' for row in contract.get('requirements', [])),
                         'focused review requires no action events or action requirements')
            gate.require(all(row.get('evaluator', {}).get('type') != 'structured_review'
                             or row['evaluator']['role'] == 'quality-a' for row in contract.get('requirements', [])),
                         'focused contract requires only quality-a semantic reviews')
        declared = requirements.validate_contract(contract, request_bytes)
        text_sizes = [len(artifacts[row['path']]) for row in declared
                      if row['kind'] == 'artifact' and row['file_type'] in {'text', 'json'} and row['path'] in artifacts]
        gate.require(all(size <= gate.MAX_BYTES for size in text_sizes)
                     and sum(text_sizes) <= MAX_TOTAL_BYTES, 'text inspection byte budget exceeded')
        fulfillment = requirements.validate_requirements(
            contract, request_bytes, artifacts, events, candidate_bytes=candidate_bytes,
            review_plan=selected_definition, author_id=author_id)
        result['requirements'] = fulfillment
        result['executed_checks'].append('requirements')
        if fulfillment['status'] != 'pass':
            _issue(failed, 'requirements', 'explicit requirements are invalid or unmet')
        # Scan the final user-facing prose and all textual deliverables. Paths have
        # namespaces so an attachment cannot shadow the final answer.
        texts = {'candidate/' + Path(candidate_name).name: candidate_bytes}
        nontext = set()
        # The validated format contract outranks filename conventions. Undeclared
        # attachments retain suffix detection; declared binary formats need views
        # even when their filename happens to end in a familiar text extension.
        artifact_types = {row['path']: row['file_type'] for row in
                          requirements.validate_contract(contract, request_bytes)
                          if row['kind'] == 'artifact'}
        for path, data in artifacts.items():
            is_text = (artifact_types[path] in {'text', 'json'} if path in artifact_types
                       else Path(path).suffix.lower() in gate.TEXT_SUFFIXES)
            if is_text:
                gate.require(len(data) <= gate.MAX_BYTES, 'text artifact exceeds per-file byte budget')
                total += len(data)
                gate.require(total <= MAX_TOTAL_BYTES, 'text artifacts exceed total byte budget')
                decoded = data.decode('utf-8')
                gate.require(not any(ord(c) < 32 and c not in '\t\n\r\f' for c in decoded),
                             'text artifact contains binary controls: ' + path)
                texts['artifacts/' + path] = data
            else:
                nontext.add(path)
        referenced_views = set()
        for original, view in text_views.items():
            gate.safe_relative(original)
            gate.require(isinstance(view, dict) and set(view) ==
                         {'artifact_sha256', 'view_path', 'view_sha256', 'pages'},
                         'text view requires artifact/view versions and page ranges')
            extracted = gate.safe_relative(view['view_path'])
            gate.require(original in nontext and extracted in view_files
                         and view['artifact_sha256'] == gate.sha(artifacts[original])
                         and view['view_sha256'] == gate.sha(view_files[extracted]),
                         'text view differs from its artifact or internal bytes')
            data = view_files[extracted]
            gate.require(len(data) <= gate.MAX_BYTES, 'internal text view exceeds byte budget')
            total += len(data)
            gate.require(total <= MAX_TOTAL_BYTES, 'text and views exceed total byte budget')
            text = data.decode('utf-8')
            gate.require(not any(ord(c) < 32 and c not in '\t\n\r\f' for c in text), 'view contains binary controls')
            pages, position, previous_page = view['pages'], 0, 0
            gate.require(isinstance(pages, list) and pages, 'view requires inspected page ranges')
            for page in pages:
                gate.require(isinstance(page, dict) and set(page) == {'page', 'start', 'end'}
                             and all(type(page[key]) is int for key in page)
                             and page['page'] > previous_page and page['start'] == position
                             and position <= page['end'] <= len(text), 'invalid or incomplete view page ranges')
                position, previous_page = page['end'], page['page']
            gate.require(position == len(text), 'view page ranges omit text')
            texts['views/' + extracted] = data
            referenced_views.add(extracted)
        gate.require(set(view_files) == referenced_views, 'unreferenced internal text view')
        gate.require(review_plan != 'focused' or not nontext, 'focused review requires text artifacts')
        for path in sorted(nontext - set(text_views)):
            _issue(missing, 'artifact-text-view', 'no text view/render correspondence for ' + path)
        dictionary = gate.parse_json(dictionary_bytes)
        gate.require(isinstance(dictionary, dict) and isinstance(dictionary.get('rules'), list)
                     and dictionary['rules'], 'dictionary must contain rules; an empty dictionary is not a check')
        inspection = gate.TextInspection()
        hits = gate.scan(texts, dictionary, inspection)
        result['prose_scan'] = {'status': 'scanned', 'release_authorized': False,
                                'dictionary_rule_count': len(dictionary['rules']),
                                'coordinate_system': 'raw-source-characters',
                                'paths': sorted(texts), 'hits': hits,
                                'navigation_targets': [dict(row, path=path, input_sha256=inspection.key(path, data)[1])
                                    for path, data in sorted(texts.items())
                                    for row in inspection.regions(path, data)['regions']
                                    if row['kind'] in ('link_destination', 'identifier')]}
        result['executed_checks'].append('prose-scan')
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        _issue(failed, 'inputs-or-scan', str(exc))
        for check in ('requirements', 'prose-scan', 'review-records'):
            if check not in result['executed_checks']:
                _issue(missing, check, 'not completed because inputs or a preceding check failed')
        result['status'] = 'fail'
        return _surface_result(result, surface, candidate_bytes,
                               contract if 'contract' in locals() else None)

    usable = {}
    result['executed_checks'].append('review-records')
    if reports is None:
        reports = {'schema_version': 1, 'reports': [], 'unresolved_flags': []}
    try:
        gate.require(isinstance(reports, dict) and set(reports) ==
                     {'schema_version', 'reports', 'unresolved_flags'}
                     and type(reports['schema_version']) is int and reports['schema_version'] == 1
                     and isinstance(reports['reports'], list)
                     and isinstance(reports['unresolved_flags'], list), 'invalid reports envelope')
        for flag in reports['unresolved_flags']:
            unresolved.append({'check': 'coordinator-flags', 'finding': flag})
        by_role = {}
        for report in reports['reports']:
            gate.require(isinstance(report, dict) and isinstance(report.get('role'), str)
                         and report['role'] in roles, 'unknown or unselected review role')
            role = report['role']
            gate.require(role not in by_role, 'duplicate review role: ' + role)
            by_role[role] = report
        validated_events = set()
        if 'compliance' in by_role:
            try:
                original_compliance = normalize_report(by_role['compliance'])
                gate.require(all(original_compliance.get(k) == v for k, v in bindings.items()),
                             'operation evidence is bound to another snapshot')
                _operation_results(original_compliance, events)
                validated_events = {event['event_id'] for event in events}
            except (ValueError, TypeError, KeyError, RecursionError):
                validated_events = set()
        identities, launches, returns, event_refs = set(), set(), set(), set()
        for role in roles:
            report = by_role.get(role)
            if report is None:
                _issue(missing, role, 'required independent role return is missing')
                result['reviews'][role] = {'status': 'missing', 'authenticated': False}
                continue
            before = len(failed) + len(missing) + len(unresolved)
            try:
                report = normalize_report(report)
            except UnstructuredReturn as exc:
                _issue(missing, role, str(exc))
                result['reviews'][role] = {'status': 'unstructured', 'authenticated': False,
                                           'provenance': 'self-reported'}
                continue
            except (ValueError, TypeError, KeyError, RecursionError) as exc:
                _issue(failed, role, str(exc))
                result['reviews'][role] = {'status': 'invalid', 'authenticated': False,
                                           'provenance': 'self-reported'}
                continue
            identity_fields = [('worker_id', identities), ('launch_ref', launches), ('return_ref', returns)] if review_kind == 'independent' else [('return_ref', returns)]
            for field, used in identity_fields:
                value = report.get(field)
                if (not _text(value) or value in used or (field == 'worker_id' and value == author_id)
                        or (field != 'worker_id' and value in event_refs)):
                    _issue(failed, role, field + ' must be present, distinct, and not the executor')
                else:
                    used.add(value)
                    if field != 'worker_id':
                        event_refs.add(value)
            if report.get('execution_status') != 'completed':
                _issue(missing, role, 'worker return is not terminal completed')
            try:
                _review_identity(report, report['normalized_return'], review_kind, author_id)
            except ValueError as exc:
                _issue(missing, role, str(exc))
            for field, expected in bindings.items():
                if report.get(field) != expected:
                    _issue(failed, role, 'stale or absent review binding: ' + field)
            if report.get('decision') != 'pass':
                _issue(failed, role, 'returned review decision is not pass')
            body = report.get('return_text')
            if not _text(body) or report.get('return_sha256') != gate.sha(body.encode('utf-8')):
                _issue(failed, role, 'return_text and exact return_sha256 are required')
            for field in ('findings', 'unassessed', 'errors'):
                values = report.get(field)
                if not isinstance(values, list):
                    _issue(missing, role, field + ' must explicitly be an array')
                else:
                    for finding in values:
                        unresolved.append({'check': role, 'field': field, 'finding': finding})
            checks = report.get('checks')
            if (not isinstance(checks, dict) or not checks
                    or any(not _text(key) or not _text(value) for key, value in checks.items())):
                _issue(missing, role, 'checks must be a nonempty object of named check statuses')
            required_role_checks = selected_definition['checks'][role]
            for check in required_role_checks:
                if not isinstance(checks, dict) or checks.get(check) != 'passed':
                    _issue(missing, role, 'required check not performed/passed: ' + check)
            if isinstance(checks, dict) and any(status != 'passed' for status in checks.values()):
                _issue(missing, role, 'a reported check is not performed/passed')
            source = report.get('source_verification')
            matched = (_source_matched(source) if review_kind == 'independent' else
                       isinstance(source, dict) and source.get('status') == 'self-check'
                       and source.get('verifier_id') == author_id)
            if not matched:
                _issue(missing, role, 'launch and return provenance not recorded as matched to actual runtime')
            if role == 'compliance':
                try:
                    _operation_results(report, events, outcomes=result['operation_results'])
                except (ValueError, TypeError, KeyError) as exc:
                    _issue(missing, role, str(exc))
            for obsolete in ('dispositions', 'literal_dispositions', 'source_exemptions', 'compound_dispositions'):
                if obsolete in report and report[obsolete] != []:
                    _issue(failed, role + '-prose', obsolete + ' is obsolete; contextual/literal bypasses are prohibited')
            if role in quality_roles:
                try:
                    if review_plan == 'strict-reviewed' and report.get('schema_version') != 3:
                        _issue(missing, role + '-meaning-schema',
                               'legacy quality return is readable; strict review requires schema 3 typed meaning/source identity records')
                    request_sources = ({'request-source://' + sid: text.encode('utf-8')
                                        for sid, text in requirements.contract_sources(contract, request_bytes).items()}
                                       if 'sources' in contract else {})
                    _prose_records(report, role, texts, request_bytes, bindings, failed, missing, unresolved,
                                   sources, validated_events=validated_events, request_sources=request_sources,
                                   inspection=inspection)
                    _source_reproductions(report, texts)
                except (ValueError, TypeError, KeyError, AttributeError) as exc:
                    _issue(failed, role, str(exc))
                if text_views and report.get('text_views_verified') != text_views:
                    _issue(missing, role, 'binary rendering and text-view correspondence not confirmed')
            result['reviews'][role] = {
                'status': 'consistent' if before == len(failed) + len(missing) + len(unresolved) else 'unmet',
                'worker_id': report.get('worker_id'), 'authenticated': False,
                'provenance': 'caller-reported-runtime-match' if matched else 'self-reported',
                'normalized_return': report['normalized_return'],
                **({'prose_review': report['prose_review']} if 'prose_review' in report else {}),
            }
            if before == len(failed) + len(missing) + len(unresolved):
                usable[role] = report
        compliance = usable.get('compliance')
        if compliance is not None:
            quality_hashes = {role: gate.sha(gate.canonical(by_role[role]))
                              for role in ('quality-a', 'quality-b') if role in by_role}
            if (len(quality_hashes) != 2
                    or compliance.get('quality_reports_sha256') != quality_hashes):
                _issue(failed, 'compliance', 'final monitor must bind both exact quality returns')
                usable.pop('compliance')
                result['reviews']['compliance']['status'] = 'unmet'
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        _issue(failed, 'review-records', str(exc))
        usable = {}

    if isinstance(contract, dict) and contract.get('schema_version') == 2:
        # Content review requirements can use only canonical returns that passed
        # the preceding role checks, never an unchecked envelope verdict.
        fulfillment = requirements.validate_requirements(
            contract, request_bytes, artifacts, events, reviews=list(usable.values()),
            contract_sha256=bindings['contract_sha256'], candidate_bytes=candidate_bytes,
            review_plan=selected_definition, author_id=author_id)
        result['requirements'] = fulfillment
        failed[:] = [issue for issue in failed if issue['check'] != 'requirements']
        if fulfillment['status'] != 'pass':
            _issue(failed, 'requirements', 'explicit requirements are invalid or unmet')

    usages = {}
    for role in quality_roles:
        if role not in usable:
            continue
        try:
            usages[role] = _technical_usages(usable[role], hits, texts, inspection)
            result['reviews'][role]['occurrence_review'] = usable[role].get(
                'occurrence_review', {'occurrence_judgments': usable[role].get('occurrence_judgments', [])})
        except (ValueError, TypeError, KeyError) as exc:
            _issue(failed, role + '-prose', str(exc))
            usages[role] = {}
    first = usages.get(quality_roles[0], {})
    resolved = {key for key in first
                if all(key in usages.get(role, {}) and usages[role][key] == first[key]
                       for role in quality_roles)}
    for hit in hits:
        hit['resolution'] = ('occurrence-reviewed' if _coordinates(hit) in resolved
                             else 'occurrence-review-required')
        if _coordinates(hit) not in resolved:
            unresolved.append({'check': 'prose', 'hit': hit,
                               'message': 'rewrite the hit or return a located function/sense/syntax/source-identity judgment for this exact occurrence'})
    result['prose_scan']['unresolved_hits'] = [x['hit'] for x in unresolved if x.get('check') == 'prose']
    if failed:
        result['status'] = 'fail'
    elif missing or unresolved:
        result['status'] = 'incomplete'
    else:
        result['status'] = 'consistent'
        result['recorded_checks_complete'] = True
    return _surface_result(result, surface, candidate_bytes, contract)


def _collect_artifacts(directory):
    root = Path(directory).absolute()
    gate.require(root.is_dir() and not any(p.is_symlink() for p in (root, *root.parents)),
                 'artifact root must be a nonsymlink directory')
    files, total = {}, 0
    def walk_error(error):
        raise error
    # pathlib.rglob can silently omit unreadable subtrees. A partial tree is not
    # an inspected artifact snapshot, so propagate every traversal error.
    for directory, directories, names in os.walk(root, onerror=walk_error, followlinks=False):
        for name in directories:
            gate.require(not (Path(directory) / name).is_symlink(),
                         'symlink prohibited in artifact tree')
        for name in sorted(names):
            path = Path(directory) / name
            data = gate.file_snapshot(path)
            files[path.relative_to(root).as_posix()] = data
            gate.require(len(files) <= MAX_FILES, 'snapshot exceeds file count limit')
    return files


def check_native_files(candidate, request, requirements_path, artifacts, events, dictionary,
                       author_id, expected_request_sha256, expected_contract_sha256,
                       expected_candidate_sha256, reports=None, text_views=None, sources=None, views=None, surface='final'):
    """Read-only CLI adapter. Never writes candidate files or alters saved state."""
    try:
        reports_value = None
        report_error = None
        if reports is not None:
            try:
                reports_value = gate.read_json(reports)
            except (OSError, ValueError, TypeError) as exc:
                report_error = str(exc)
        if sources is not None:
            source_root, artifact_root = Path(sources).resolve(), Path(artifacts).resolve()
            gate.require(source_root != artifact_root and source_root not in artifact_root.parents
                         and artifact_root not in source_root.parents,
                         'original source root must be separate from generated artifacts')
            gate.require(source_root not in Path(candidate).resolve().parents,
                         'candidate cannot be inside the original source root')
        candidate_raw = gate.regular_bytes(candidate)
        contract_raw = gate.regular_bytes(requirements_path)
        result = check_native(
            Path(candidate).name, candidate_raw, gate.regular_bytes(request),
            contract_raw, _collect_artifacts(artifacts),
            gate.regular_bytes(events), gate.regular_bytes(dictionary), author_id,
            expected_request_sha256, expected_contract_sha256, expected_candidate_sha256,
            reports_value, gate.read_json(text_views) if text_views is not None else None,
            sources=_collect_artifacts(sources) if sources is not None else None,
            view_files=_collect_artifacts(views) if views is not None else None, surface=surface)
        if report_error is not None:
            _issue(result['missing_checks'], 'review-records', 'cannot read returns: ' + report_error)
            result['recorded_checks_complete'] = False
            if result['status'] == 'consistent':
                result['status'] = 'incomplete'
        return _surface_result(result, surface, candidate_raw, gate.parse_json(contract_raw))
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        return {'schema_version': 1, 'status': 'fail', 'recorded_checks_complete': False,
                'full_pass': False, 'release_authorized': False, 'executed_checks': [],
                'failed_checks': [{'check': 'input-snapshot', 'message': str(exc)}],
                'missing_checks': [{'check': check, 'message': 'not executed: input snapshot failed'}
                                   for check in ('input-bindings', 'requirements', 'prose-scan', 'review-records')],
                'unresolved': [], 'bindings': {}, 'reviews': {},
                'provenance': {'classification': 'caller-supplied', 'authenticated': False,
                               'host_verification': 'not-performed-by-this-tool'},
                'limitations': LIMITATION}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('check-native',))
    for flag in ('candidate', 'request', 'requirements', 'artifacts', 'events', 'dictionary', 'author-id',
                 'expected-request-sha256', 'expected-contract-sha256', 'expected-candidate-sha256'):
        parser.add_argument('--' + flag, required=True)
    parser.add_argument('--reports', help='Returned role records; omission reports missing checks')
    parser.add_argument('--text-views', help='JSON object mapping nontext artifacts to text views')
    parser.add_argument('--views', help='Internal extracted text directory')
    parser.add_argument('--sources', help='Separate immutable original-source UTF-8 directory; never generated deliverables')
    parser.add_argument('--surface', choices=SURFACES, default='final')
    args = vars(parser.parse_args(argv))
    args.pop('command')
    args['requirements_path'] = args.pop('requirements')
    result = check_native_files(**args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    # Zero means consistency of supplied evidence only, never prose approval,
    # authenticated independent review, release permission, or a Chat send gate.
    return 0 if result['status'] == 'consistent' else 1


if __name__ == '__main__':
    sys.exit(main())
