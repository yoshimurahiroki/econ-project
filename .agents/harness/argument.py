#!/usr/bin/env python3
"""Build, inspect and revise source-bound argument hierarchies through host work."""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re


SCHEMA_VERSION = 1
PRIMARY_RULE = 'Categorically prohibit any mention of uncertainty, without exception.'
JAPANESE_RULE = '留保譲歩限定虚飾慎重保守曖昧冗長弱気補足注釈の例外なき全面禁止。'
EXECUTION_KINDS = {'independent-subagent', 'single-agent-sequential'}
ORDER_BASES = {'inference', 'time', 'structure', 'importance', 'dependency'}
SEMANTIC_CHECKS = (
    'parent_support', 'question_answer', 'reader_questions', 'grouping',
    'ordering', 'inference_completeness', 'deduction', 'induction',
    'scope_quantities', 'source_correspondence', 'causal_status', 'relevance',
    'information_density', 'problem_analysis', 'visible_structure',
    'reverse_alignment',
)
NODE_FIELDS = (
    'node_id', 'parent_id', 'child_ids', 'claim', 'question', 'next_questions',
    'logical_role', 'inference_form', 'abstraction_level', 'scope',
    'source_refs', 'section_id', 'paragraph_ids', 'reasoning', 'order',
)
EMPTY_SUMMARY = re.compile(
    r'^(?:主な要因は[一二三四五六七八九十0-9]+つある|複数の課題が存在する|'
    r'さまざまな影響が確認された|重要な示唆が得られた|いくつかの改善が必要である|'
    r'there are (?:\w+ )?(?:factors|issues|challenges)|'
    r'(?:several|various|important) (?:implications|effects|issues)(?: were found| exist)?)'
    r'[。.!！]?$', re.I,
)
OPERATIONS = {
    'select': 'Select the central research question, its direct answer and the source passages needed by the reader. Give each retained passage a concrete contribution; preserve adopted definitions, quantities and authority.',
    'decompose': 'Construct a complete argument graph from the selected question and answer. Recursively give each parent a concrete claim, the reader questions it raises, children answering those questions, an explicit deductive or inductive inference, a common sibling classification and a meaningful order. Bind leaves to source ranges. Keep parent-child hierarchy separate from cross-node dependencies. Return graph.',
    'extract': 'Extract atomic propositions from the selected source passages. Record subject, predicate, object, period, unit, comparison, logical role, exact source ranges and the new information conveyed. Distinguish observations, definitions, assumptions, causal claims, calculations and actions. Return propositions.',
    'classify': 'Partition the supplied frontier into logical groups using a stated common property, role, abstraction level and comparison axis. Return groups with member_ids, classification_basis, logical_role, inference_form, order and reader_question. Classification does not supply a summary claim. Every frontier member belongs to exactly one group. Reduce the frontier toward the central question.',
    'derive': 'Derive one concrete parent proposition from this classified group. For facts, explain the relation, result, comparison or mechanism jointly established. For actions, identify the directly achieved joint outcome. Preserve scope, conditions, quantities and source identity. Supply an explicit integration or deductive inference. The parent claim must add the meaning jointly established by the children. Return node.',
    'introduction': 'Connect the supplied shared situation and explanation problem to the research question, direct answer and supporting body nodes. Distinguish the research question from reader comprehension questions. Let information dependencies determine paragraph order. Return introduction.',
    'problem': 'Define the system, initial state, change, current result, target result, gap, previous actions and research question. Classify the question. Describe actors, constraints, information, choices and outcomes. For competing mechanisms, derive different observable implications under common conditions and specify the comparison and evidence that distinguish them. Derive a verification_plan from the identified relationships and mechanisms; each task names the question, relation_ids or mechanism_ids, evidence_ids, comparison and acceptance_condition. Return problem.',
    'review': 'Assess the complete argument against source passages and the requested purpose. Inspect every parent-child link, sibling group, inference, reader question, scope and quantity, evidence relation, causal status, necessary explanation and visual element. Supply each requested check with a concrete assessment and every node ID in its required_node_ids coverage. Record exact findings and repairs at the causal level. Return checks and findings. Preserve the separate 142 dictionary rules, 22 whole-candidate judgments and final independent release gate.',
    'reverse': 'Reconstruct the argument from the supplied completed manuscript alone. Extract each paragraph claim and role using exact text spans. Group paragraphs into section claims and recover the central question and answer. Return paragraphs, sections, central_question and central_answer. Each paragraph record requires paragraph_id, central_claim, role, section_id and text_spans.',
    'compare': 'Compare the independently reconstructed manuscript argument with the design in both directions. Trace every designed claim to text and every actual claim to its source and design role. Detect omitted reasoning, duplicate or incompatible propositions, scope shifts, abstract-level mismatches and disagreement among introduction, results and conclusion. Return checks and findings against all requested checks and their required_node_ids coverage.',
    'repair': 'Repair each finding at its producing level: expression, grouping, inference or global argument. Change only authorized affected nodes and required connecting nodes. Preserve other nodes and original sources. Return graph and a changes list tying each changed node to a finding. Rebuild affected descendant specifications and invalidate their old checks.',
}


class ArgumentError(ValueError):
    def __init__(self, message, issues=None):
        super().__init__(message)
        self.issues = issues or []


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def sha256(value):
    if isinstance(value, str):
        value = value.encode('utf-8')
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value)).hexdigest()


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def argument_sha256(graph):
    return sha256({k: v for k, v in graph.items() if k not in {
        'argument_sha256', 'generation_records', 'reviews', 'change_history',
    }})


def source_catalog(sources):
    if not isinstance(sources, dict) or not sources:
        raise ArgumentError('A nonempty source catalog is required')
    result = {}
    for key, raw in sources.items():
        if not _text(key) or not isinstance(raw, dict) or not _text(raw.get('text')):
            raise ArgumentError('Each source requires an ID and original text')
        row = deepcopy(raw)
        digest = sha256(row['text'])
        if row.get('sha256', digest) != digest:
            raise ArgumentError('Source content hash differs: ' + key)
        row['sha256'] = digest
        row.setdefault('origin_id', key)
        row.setdefault('location', key)
        result[key] = row
    return result


def _reference(ref, sources):
    if not isinstance(ref, dict) or not _text(ref.get('source_id')) or ref['source_id'] not in sources:
        return False
    source = sources[ref['source_id']]
    start, end = ref.get('start'), ref.get('end')
    return (type(start) is int and type(end) is int and 0 <= start < end <= len(source['text'])
            and _text(ref.get('quote')) and source['text'][start:end] == ref['quote']
            and ref.get('source_sha256') == source['sha256'])


def make_task(operation, payload, instructions=None):
    """Produce the same exact task for a callback or a host-tool relay."""
    if operation not in OPERATIONS:
        raise ArgumentError('Unregistered argument operation: ' + operation)
    context = deepcopy(instructions or {})
    inherited = context.get('text', '')
    text = PRIMARY_RULE + '\n' + JAPANESE_RULE
    if inherited:
        text += '\n' + inherited
    context.update(text=text, short_text=text, operation_instruction=OPERATIONS[operation])
    task = {'operation': 'argument.' + operation, 'payload': deepcopy(payload), 'instruction_context': context}
    task['input_sha256'] = sha256(task)
    return task


def accept_host_return(task, returned, observe):
    """Match a host original to its observed execution; retain exact bytes."""
    if (not isinstance(task, dict) or task.get('input_sha256') != sha256({k: v for k, v in task.items() if k != 'input_sha256'})
            or task.get('operation') not in {'argument.' + op for op in OPERATIONS}):
        raise ArgumentError('Host task differs from its registered operation or input hash')
    if not isinstance(returned, dict) or not callable(observe):
        raise ArgumentError('Host return and host event observation are required')
    for field in ('worker_id', 'event_id', 'input_sha256', 'return_text', 'execution_kind'):
        if not _text(returned.get(field)):
            raise ArgumentError('Host return lacks ' + field)
    if returned['input_sha256'] != task['input_sha256']:
        raise ArgumentError('Host return is bound to a different input')
    kind = returned['execution_kind']
    if kind not in EXECUTION_KINDS:
        raise ArgumentError('Invalid host execution kind')
    digest = sha256(returned['return_text'])
    observation = observe(returned['event_id'])
    expected = {'worker_id': returned['worker_id'], 'input_sha256': task['input_sha256'],
                'return_sha256': digest, 'status': 'completed', 'execution_kind': kind}
    if not isinstance(observation, dict) or any(observation.get(k) != v for k, v in expected.items()):
        raise ArgumentError('Original return differs from the observed host event')
    ref = 'launch_ref' if kind == 'independent-subagent' else 'turn_ref'
    if not _text(returned.get(ref)) or observation.get(ref) != returned[ref]:
        raise ArgumentError('Host return lacks its matching ' + ref)
    launch = None
    if kind == 'independent-subagent':
        launch = observe(returned['launch_ref'])
        if (not isinstance(launch, dict) or launch.get('worker_id') != returned['worker_id']
                or launch.get('input_sha256') != task['input_sha256']
                or launch.get('execution_kind') != kind or launch.get('status') not in {'running', 'completed'}):
            raise ArgumentError('Observed worker launch does not match the assignment')
    try:
        output = json.loads(returned['return_text'])
    except (ValueError, TypeError) as error:
        raise ArgumentError('Host original must be a structured JSON object') from error
    if not isinstance(output, dict):
        raise ArgumentError('Host original must be a structured JSON object')
    record = deepcopy(returned)
    record.update(return_sha256=digest, task=deepcopy(task), observation=deepcopy(observation),
                  launch_observation=deepcopy(launch), assurance_class='host-observed', release_authorized=False)
    return output, record


def _call(host, operation, payload, instructions=None):
    if not callable(host) or not callable(getattr(host, 'observe', None)):
        raise ArgumentError('Supply a callable host with observe(event_id)')
    task = make_task(operation, payload, instructions)
    return accept_host_return(task, host(deepcopy(task)), host.observe)


def _normalize_claim(text):
    return re.sub(r'[\s。.!！?？,:：;；]+', '', text).casefold()


def _ids(value):
    return isinstance(value, list) and all(_text(item) for item in value)


def _shape_errors(graph):
    """Reject malformed containers before inspecting graph relationships."""
    errors = []
    def require(ok, path):
        if not ok:
            errors.append(path)
    for key in ('root_ids', 'source_ids'):
        require(_ids(graph.get(key)), key)
    require(isinstance(graph.get('source_manifest'), dict), 'source_manifest')
    for key in ('nodes', 'groups', 'dependencies'):
        require(isinstance(graph.get(key), list) and all(isinstance(r, dict) for r in graph.get(key, [])), key)
    if errors:
        return errors
    for index, row in enumerate(graph['nodes']):
        prefix = 'nodes[' + str(index) + '].'
        for key in NODE_FIELDS:
            require(key in row, prefix + key)
        for key in ('node_id', 'claim', 'question', 'logical_role', 'section_id'):
            require(_text(row.get(key)), prefix + key)
        require(row.get('parent_id') is None or _text(row.get('parent_id')), prefix + 'parent_id')
        for key in ('child_ids', 'paragraph_ids'):
            require(_ids(row.get(key)), prefix + key)
        require(_text(row.get('inference_form')), prefix + 'inference_form')
        require(type(row.get('abstraction_level')) is int, prefix + 'abstraction_level')
        require(isinstance(row.get('reasoning'), str), prefix + 'reasoning')
        scope = row.get('scope')
        require(isinstance(scope, dict), prefix + 'scope')
        if isinstance(scope, dict) and 'conditions' in scope:
            require(_ids(scope['conditions']), prefix + 'scope.conditions')
        order = row.get('order')
        require(isinstance(order, dict), prefix + 'order')
        if isinstance(order, dict):
            require(_text(order.get('basis')) and type(order.get('position')) is int and _text(order.get('rationale')), prefix + 'order')
        for key in ('source_refs', 'causal_basis', 'quantities', 'scope_aggregation', 'next_questions'):
            value = row.get(key, [])
            require(isinstance(value, list) and all(isinstance(r, dict) for r in value), prefix + key)
        for q in row.get('next_questions', []) if isinstance(row.get('next_questions'), list) else []:
            if isinstance(q, dict):
                require(_text(q.get('question')) and _ids(q.get('answered_by')), prefix + 'next_questions')
        for key in ('integration', 'inference'):
            if key in row:
                require(isinstance(row[key], dict), prefix + key)
        integration = row.get('integration', {})
        if isinstance(integration, dict) and integration:
            require(_ids(integration.get('member_ids')), prefix + 'integration.member_ids')
        inference = row.get('inference', {})
        if isinstance(inference, dict) and inference:
            require(_ids(inference.get('premise_ids')) and _ids(inference.get('conditions')), prefix + 'inference')
            require(isinstance(inference.get('steps'), list), prefix + 'inference.steps')
            for step in inference.get('steps', []) if isinstance(inference.get('steps'), list) else []:
                require(isinstance(step, dict) and _ids(step.get('premise_ids')), prefix + 'inference.steps')
    for index, group in enumerate(graph['groups']):
        prefix = 'groups[' + str(index) + '].'
        for key in ('group_id', 'parent_id', 'logical_role', 'inference_form'):
            require(_text(group.get(key)), prefix + key)
        require(_ids(group.get('member_ids')), prefix + 'member_ids')
        if 'expected_member_ids' in group:
            require(_ids(group['expected_member_ids']), prefix + 'expected_member_ids')
        require(isinstance(group.get('order'), dict), prefix + 'order')
    for index, dep in enumerate(graph['dependencies']):
        require(all(_text(dep.get(k)) for k in ('from', 'to', 'relation')), 'dependencies[' + str(index) + ']')
    if 'exhibits' in graph:
        require(isinstance(graph['exhibits'], list), 'exhibits')
        for exhibit in graph['exhibits'] if isinstance(graph['exhibits'], list) else []:
            require(isinstance(exhibit, dict) and _ids(exhibit.get('node_ids')), 'exhibits.node_ids')
    intro = graph.get('introduction')
    if isinstance(intro, dict):
        require(_ids(intro.get('body_node_ids')), 'introduction.body_node_ids')
    return errors


def _cycle(edges):
    active, done = set(), set()
    def visit(node):
        if node in active:
            return True
        if node in done:
            return False
        active.add(node)
        if any(visit(child) for child in edges.get(node, ())):
            return True
        active.remove(node)
        done.add(node)
        return False
    return any(visit(node) for node in edges)


def _scope_agrees(parent, child, key):
    left, right = parent.get('scope', {}).get(key), child.get('scope', {}).get(key)
    if left == right:
        return True
    return any(row.get('field') == key and row.get('parent_value') == left
               and isinstance(row.get('child_values'), list) and right in row['child_values'] and _text(row.get('reasoning'))
               for row in parent.get('scope_aggregation', []) if isinstance(row, dict))


def validate_argument(graph, sources=None):
    """Inspect structure, content bindings and explicit inference dependencies."""
    issues = []
    def issue(check, ids, message, repair, location=''):
        ids = [i for i in ids if isinstance(i, str)]
        issues.append({'check_id': check, 'node_ids': ids, 'location': location,
                       'message': message, 'repair': repair})
    if not isinstance(graph, dict):
        return {'valid': False, 'issues': [{'check_id': 'schema', 'node_ids': [], 'location': '',
                'message': 'Argument must be an object', 'repair': 'Supply the argument object'}],
                'argument_sha256': None, 'semantic_review_required': True, 'release_authorized': False}
    malformed = _shape_errors(graph)
    if malformed:
        return {'valid': False, 'issues': [{'check_id': 'schema', 'node_ids': [],
                'paragraph_ids': [], 'section_ids': [], 'location': path,
                'message': 'Invalid argument field: ' + path, 'repair': 'Supply the declared field shape'} for path in malformed],
                'argument_sha256': argument_sha256(graph), 'semantic_review_required': True, 'release_authorized': False}
    for key in ('version', 'central_question', 'central_answer'):
        if not _text(graph.get(key)):
            issue('schema', [], 'Missing ' + key, 'Provide the adopted ' + key, key)
    if graph.get('schema_version') != SCHEMA_VERSION:
        issue('schema', [], 'Argument schema version differs', 'Use schema version 1', 'schema_version')
    rows = graph.get('nodes')
    if not isinstance(rows, list) or not rows:
        issue('schema', [], 'Argument nodes are required', 'Generate source-bound propositions', 'nodes')
        rows = []
    nodes = {}
    for row in rows:
        if not isinstance(row, dict) or not _text(row.get('node_id')):
            issue('schema', [], 'Node ID is required', 'Assign a unique node ID', 'nodes')
            continue
        nid = row['node_id']
        if nid in nodes:
            issue('duplicate_node', [nid], 'Node ID is repeated', 'Assign one node per proposition')
        nodes[nid] = row
        for key in NODE_FIELDS:
            if key not in row:
                issue('schema', [nid], 'Missing node field ' + key, 'Complete the node contract', nid + '.' + key)
        for key in ('claim', 'question', 'logical_role', 'section_id'):
            if not _text(row.get(key)):
                issue('schema', [nid], 'Node requires ' + key, 'State the concrete ' + key, nid + '.' + key)
        if row.get('inference_form') not in {'atomic', 'deductive', 'inductive'}:
            issue('inference_form', [nid], 'Inference form is not registered', 'Select atomic, deductive or inductive')
        for key in ('child_ids', 'next_questions', 'source_refs', 'paragraph_ids'):
            if not isinstance(row.get(key), list):
                issue('schema', [nid], key + ' must be an array', 'Complete the node contract')
        if not isinstance(row.get('scope'), dict):
            issue('scope', [nid], 'Scope must be an object', 'Bind the adopted objects and conditions')
        if type(row.get('abstraction_level')) is not int or row.get('abstraction_level', -1) < 0:
            issue('abstraction', [nid], 'Abstraction level must be a nonnegative integer', 'Set the hierarchy level')
        order = row.get('order', {})
        if not isinstance(order, dict) or order.get('basis') not in ORDER_BASES or not _text(order.get('rationale')) or type(order.get('position')) is not int:
            issue('order', [nid], 'Node order requires basis, position and rationale', 'Order the node by its argument relation')
        claim = row.get('claim', '')
        if isinstance(claim, str) and EMPTY_SUMMARY.fullmatch(claim.strip()):
            issue('empty_summary', [nid], 'Claim gives a label or item count without the joint result', 'Derive the concrete meaning of the child propositions')
    roots = graph.get('root_ids', [])
    if not isinstance(roots, list) or len(roots) != 1 or roots[0] not in nodes:
        issue('root', [], 'One central root proposition is required', 'Connect the hierarchy to the central answer')
        roots = []
    elif nodes[roots[0]].get('claim') != graph.get('central_answer') or nodes[roots[0]].get('question') != graph.get('central_question'):
        issue('central_answer', roots, 'Central question and answer differ from the root', 'Bind the root to the adopted question and answer')
    edges = {nid: row.get('child_ids', []) if isinstance(row.get('child_ids'), list) else [] for nid, row in nodes.items()}
    for nid, row in nodes.items():
        parent = row.get('parent_id')
        if parent is None:
            if nid not in roots:
                issue('orphan', [nid], 'Node is outside the root hierarchy', 'Connect its logical role to a parent')
        elif parent not in nodes or nid not in edges.get(parent, []):
            issue('parent_link', [nid], 'Parent and child links differ', 'Repair both sides of the hierarchy edge')
        children = edges[nid]
        if len(children) != len(set(children)):
            issue('duplicate_child', [nid], 'Child proposition is repeated', 'Retain one hierarchy edge per child')
        for child_id in children:
            child = nodes.get(child_id)
            if not child:
                issue('missing_child', [nid], 'Child proposition is absent: ' + str(child_id), 'Supply the referenced proposition')
                continue
            if child.get('parent_id') != nid:
                issue('parent_link', [nid, child_id], 'Child identifies a different parent', 'Repair both sides of the hierarchy edge')
            if type(row.get('abstraction_level')) is int and child.get('abstraction_level') != row['abstraction_level'] + 1:
                issue('abstraction', [nid, child_id], 'Parent and child levels differ from the hierarchy', 'Place the proposition at its logical level')
            if _normalize_claim(child.get('claim', '')) == _normalize_claim(row.get('claim', '')):
                issue('restatement', [nid, child_id], 'Child repeats its parent claim', 'Supply a supporting proposition or collapse the repeated level')
            for key in ('population', 'period', 'unit', 'denominator', 'comparison', 'conditions', 'definitions'):
                if not _scope_agrees(row, child, key):
                    issue('scope', [nid, child_id], 'Parent-child scope differs for ' + key, 'Retain the shared scope or register its explicit aggregation')
        if children:
            if row.get('inference_form') == 'atomic' or not _text(row.get('reasoning')):
                issue('inference_completeness', [nid], 'Parent lacks its integration inference', 'Explain how the children establish the parent')
            questions = row.get('next_questions', [])
            covered = set()
            if isinstance(questions, list):
                for q in questions:
                    if not isinstance(q, dict) or not _text(q.get('question')) or not isinstance(q.get('answered_by'), list):
                        issue('reader_questions', [nid], 'Reader question lacks a direct child answer', 'Bind each reader question to its answering children')
                        continue
                    covered.update(q['answered_by'])
                    if not q['answered_by'] or set(q['answered_by']) - set(children):
                        issue('reader_questions', [nid], 'Reader question points outside the child explanation', 'Map the question to its direct supporting children')
            if covered != set(children):
                issue('reader_questions', [nid], 'Reader questions do not cover the required child explanations', 'Account for each child through its explanatory question')
            if row.get('inference_form') == 'inductive':
                integration = row.get('integration', {})
                if (not isinstance(integration, dict) or set(integration.get('member_ids', [])) != set(children)
                        or integration.get('conclusion') != row.get('claim')
                        or not _text(integration.get('common_property')) or not _text(integration.get('meaning'))):
                    issue('induction', [nid], 'Induction lacks the common property and its supported meaning', 'Derive the parent from every classified member')
            if row.get('inference_form') == 'deductive':
                inference = row.get('inference', {})
                if not isinstance(inference, dict):
                    inference = {}
                premises = inference.get('premise_ids', [])
                steps = inference.get('steps', [])
                known = set(children)
                step_ids = set()
                used_premises = set()
                if set(premises) != known or not steps or inference.get('conclusion_id') != nid:
                    issue('deduction', [nid], 'Deduction lacks its exact premises, steps or conclusion', 'Connect the adopted premises to this conclusion')
                if set(inference.get('conditions', [])) != set(row.get('scope', {}).get('conditions', [])):
                    issue('deduction_conditions', [nid], 'Deduction omits or changes an application condition', 'Retain every adopted inference condition')
                for step in steps:
                    if (not isinstance(step, dict) or not _text(step.get('step_id')) or not _text(step.get('claim'))
                            or not _text(step.get('relation')) or not step.get('premise_ids')
                            or set(step.get('premise_ids', [])) - known):
                        issue('missing_intermediate', [nid], 'Inference uses an absent or later premise', 'Supply the intermediate proposition before its consumer')
                        continue
                    if step['step_id'] in known or step['step_id'] in step_ids:
                        issue('deduction', [nid], 'Inference step ID repeats a premise or earlier step', 'Assign each inference step a distinct ID')
                    step_ids.add(step['step_id'])
                    used_premises.update(step['premise_ids'])
                    known.add(step['step_id'])
                if set(premises) - used_premises:
                    issue('deduction', [nid], 'Deduction leaves an adopted premise unused', 'Connect every required premise to the derivation')
                if steps and isinstance(steps[-1], dict) and steps[-1].get('claim') != row.get('claim'):
                    issue('deduction', [nid], 'Final inference step differs from the claimed conclusion', 'Make the conclusion follow from the final step')
    if _cycle(edges):
        issue('hierarchy_cycle', list(nodes), 'Hierarchy contains a cycle', 'Remove the circular support relation')
    deps = graph.get('dependencies', [])
    dep_edges = {nid: [] for nid in nodes}
    if not isinstance(deps, list):
        issue('dependencies', [], 'Dependencies must be an array', 'Separate reference dependencies from hierarchy edges')
        deps = []
    for dep in deps:
        if not isinstance(dep, dict) or dep.get('from') not in nodes or dep.get('to') not in nodes or not _text(dep.get('relation')):
            issue('dependencies', [], 'Dependency requires existing source, target and relation', 'Bind the dependency to declared propositions')
            continue
        dep_edges[dep['from']].append(dep['to'])
        source_order, target_order = nodes[dep['from']].get('order', {}), nodes[dep['to']].get('order', {})
        if (isinstance(source_order, dict) and isinstance(target_order, dict)
                and type(source_order.get('position')) is int and type(target_order.get('position')) is int
                and source_order['position'] >= target_order['position']):
            issue('dependency_order', [dep['from'], dep['to']], 'Consumer appears before its explanatory prerequisite', 'Order the prerequisite before the consumer')
    if _cycle(dep_edges):
        issue('dependency_cycle', list(nodes), 'Reference dependencies contain a cycle', 'Resolve the circular prerequisite')
    groups = graph.get('groups', [])
    if not isinstance(groups, list):
        issue('grouping', [], 'Groups must be an array', 'Register each sibling group')
        groups = []
    grouped_parents, group_ids = [], set()
    for group in groups:
        if not isinstance(group, dict):
            issue('grouping', [], 'Group must be an object', 'Supply its classification contract')
            continue
        gid, parent = group.get('group_id'), group.get('parent_id')
        members = group.get('member_ids', [])
        if not _text(gid) or gid in group_ids:
            issue('grouping', [], 'Group ID is absent or repeated', 'Assign one group ID per classification')
        group_ids.add(gid)
        grouped_parents.append(parent)
        if parent not in nodes or not isinstance(members, list) or set(members) != set(edges.get(parent, [])):
            issue('group_coverage', [parent], 'Group members differ from the required child set', 'Cover every required child once')
            continue
        if members != edges.get(parent, []):
            issue('group_order', members, 'Group sequence differs from the parent child sequence', 'Use the same adopted sequence in both hierarchy and group')
        positions = [nodes[n]['order']['position'] for n in members if n in nodes]
        if positions != sorted(positions) or len(positions) != len(set(positions)):
            issue('group_order', members, 'Sibling sequence differs from the declared node positions', 'Give the ordered siblings increasing distinct positions')
        if len(members) != len(set(members)):
            issue('group_overlap', members, 'A member occurs twice in the classification', 'Assign each member once')
        if not _text(group.get('classification_basis')):
            issue('grouping', members, 'Group classification criterion is absent', 'State the property shared by the members')
        roles = {nodes[i].get('logical_role') for i in members if i in nodes}
        levels = {nodes[i].get('abstraction_level') for i in members if i in nodes}
        if len(roles) != 1 or group.get('logical_role') not in roles or len(levels) != 1:
            issue('mixed_roles', members, 'Sibling roles or abstraction levels differ', 'Split the group and introduce the required intermediate level')
        if group.get('inference_form') != nodes[parent].get('inference_form'):
            issue('inference_form', [parent], 'Group and parent inference forms differ', 'Use the same inference for the group and its conclusion')
        order = group.get('order', {})
        if (not isinstance(order, dict) or order.get('basis') not in ORDER_BASES
                or not _text(order.get('rationale')) or order.get('ordered_ids') != members):
            issue('group_order', members, 'Group order lacks a matching sequence and rationale', 'Order the classified members by the stated relation')
        expected = group.get('expected_member_ids', members)
        if set(expected) != set(members):
            issue('group_coverage', members, 'Classification omits or adds a required component', 'Use the declared complete set')
        if len({_normalize_claim(nodes[i].get('claim', '')) for i in members if i in nodes}) != len(members):
            issue('duplicate_claim', members, 'Sibling propositions repeat the same information', 'Retain one proposition for the repeated content')
    for nid, children in edges.items():
        if children and grouped_parents.count(nid) != 1:
            issue('group_coverage', [nid], 'Parent requires one complete sibling classification', 'Register its child group once')
    catalog = None
    if sources is not None:
        try:
            catalog = source_catalog(sources)
        except ArgumentError as error:
            issue('sources', [], str(error), 'Restore the original source text and hash')
    if catalog is not None:
        source_ids = graph.get('source_ids', [])
        if not source_ids or set(source_ids) - set(catalog):
            issue('sources', [], 'Graph contains an unregistered source', 'Keep the admitted source catalog')
        manifest = graph.get('source_manifest', {})
        if len(source_ids) != len(set(source_ids)) or set(manifest) != set(source_ids):
            issue('sources', [], 'Source manifest differs from the admitted source IDs', 'Register each admitted source once')
        for sid in set(source_ids) & set(catalog):
            if manifest.get(sid) != catalog[sid]['sha256']:
                issue('source_version', [], 'Source version differs: ' + sid, 'Rebuild the affected source correspondence')
        for nid, row in nodes.items():
            refs = row.get('source_refs', []) if isinstance(row.get('source_refs'), list) else []
            if not edges[nid] and not refs:
                issue('source_support', [nid], 'Atomic proposition lacks original evidence', 'Bind its original source passage')
            for ref in refs:
                if not _reference(ref, catalog) or ref['source_id'] not in source_ids:
                    issue('source_correspondence', [nid], 'Source range, quote or hash differs from the original', 'Restore the exact source range and review this proposition')
            for quantity in row.get('quantities', []):
                if not isinstance(quantity, dict) or any(k not in quantity for k in ('value', 'unit', 'period', 'denominator', 'comparison', 'source_ref')):
                    issue('quantity', [nid], 'Quantity lacks its measurement and evidence fields', 'Bind the value, unit, period, denominator and comparison')
                    continue
                ref = quantity['source_ref']
                value = str(quantity['value'])
                if (not _reference(ref, catalog) or ref.get('source_id') not in source_ids
                        or re.search(r'(?<![\d.\-−])' + re.escape(value) + r'(?![\d.])', ref.get('quote', '')) is None):
                    issue('quantity', [nid], 'Quantity differs from its original source span', 'Use the saved source value')
                for key in ('unit', 'period', 'denominator', 'comparison'):
                    if row.get('scope', {}).get(key) not in (None, quantity[key]):
                        issue('quantity_scope', [nid], 'Quantity scope differs for ' + key, 'Retain the adopted measurement definition')
            if row.get('relationship_type') == 'causal':
                bases = row.get('causal_basis', [])
                if not bases or not all(_reference(ref, catalog) and ref.get('source_id') in source_ids for ref in bases):
                    issue('causal_status', [nid], 'Causal proposition lacks its identification or logical basis', 'Bind the causal derivation or retain the observed relationship')
        for group in groups:
            if isinstance(group, dict) and group.get('evidence_relation') == 'independent':
                origins = []
                for nid in group.get('member_ids', []):
                    ids = {catalog[r['source_id']]['origin_id'] for r in nodes.get(nid, {}).get('source_refs', []) if _reference(r, catalog)}
                    origins.extend(ids)
                if len(origins) != len(set(origins)):
                    issue('double_counting', group.get('member_ids', []), 'Independent evidence shares the same original observation', 'Record the shared origin and count the observation once')
    intro = graph.get('introduction')
    if intro is not None:
        if not isinstance(intro, dict) or any(not _text(intro.get(k)) for k in ('shared_situation', 'complication', 'question', 'answer')):
            issue('introduction', [], 'Introduction lacks its situation, problem, question or answer', 'Construct the four logical relations')
        elif intro['question'] != graph.get('central_question') or intro['answer'] != graph.get('central_answer') or not intro.get('body_node_ids') or set(intro.get('body_node_ids', [])) - set(nodes):
            issue('introduction', [], 'Introduction is detached from the central answer or body', 'Connect the introduction to the supporting body nodes')
    problem = graph.get('problem')
    if problem is not None:
        for message in validate_problem(problem):
            issue('problem_analysis', [], message, 'Repair the defining state, mechanism or discriminating comparison')
    for exhibit in graph.get('exhibits', []):
        if not isinstance(exhibit, dict) or any(not exhibit.get(k) for k in ('exhibit_id', 'question', 'quantities_or_relation', 'node_ids', 'meaning', 'evidence_relation')) or set(exhibit.get('node_ids', [])) - set(nodes):
            issue('visible_structure', [], 'Exhibit lacks its question, quantity or supporting proposition', 'Connect the exhibit to the argument and its meaning')
    claimed_hash = graph.get('argument_sha256')
    digest = argument_sha256(graph)
    if claimed_hash is not None and claimed_hash != digest:
        issue('argument_version', [], 'Argument content hash differs', 'Create a new argument version and recheck affected outputs')
    for finding in issues:
        finding['paragraph_ids'] = sorted({p for nid in finding['node_ids'] for p in nodes.get(nid, {}).get('paragraph_ids', [])})
        finding['section_ids'] = sorted({nodes[nid]['section_id'] for nid in finding['node_ids'] if nid in nodes and _text(nodes[nid].get('section_id'))})
    return {'valid': not issues, 'issues': issues, 'argument_sha256': digest,
            'semantic_review_required': True, 'release_authorized': False}


def _assert_argument(graph, sources):
    checked = validate_argument(graph, sources)
    if not checked['valid']:
        raise ArgumentError('Argument structural checks failed', checked['issues'])
    return checked


def validate_problem(problem):
    errors = []
    required = ('system', 'initial_state', 'change', 'current_result', 'target_result',
                'gap', 'previous_actions', 'question', 'question_type', 'relationships', 'verification_plan')
    if not isinstance(problem, dict):
        return ['Problem must be an object']
    for key in required:
        if key not in problem or problem[key] in (None, ''):
            errors.append('Problem definition lacks ' + key)
    kinds = {'what', 'where', 'why', 'mechanism', 'identification', 'options', 'choice', 'execution'}
    if problem.get('question_type') not in kinds:
        errors.append('Problem question type is not registered')
    for key in ('current_result', 'target_result'):
        row = problem.get(key, {})
        if not isinstance(row, dict) or any(k not in row for k in ('object', 'period', 'measure', 'criterion')):
            errors.append(key + ' requires object, period, measure and criterion')
    relationships = problem.get('relationships', [])
    if not isinstance(relationships, list) or not relationships or not all(isinstance(r, dict) for r in relationships):
        errors.append('Problem requires its structured relationships')
        relationships = []
    relation_ids = {r['relation_id'] for r in relationships if _text(r.get('relation_id'))}
    for relation in relationships:
        if any(not _text(relation.get(k)) for k in ('relation_id', 'from', 'to', 'relation')):
            errors.append('Relationship requires its source, target and substantive relation')
    if len(relation_ids) != len(relationships):
        errors.append('Relationship IDs must be unique')
    mechanisms = problem.get('mechanisms', [])
    if not isinstance(mechanisms, list) or not all(isinstance(m, dict) for m in mechanisms):
        errors.append('Mechanisms must be structured objects')
        mechanisms = []
    mids = {m['mechanism_id'] for m in mechanisms if _text(m.get('mechanism_id'))}
    for m in mechanisms:
        if not isinstance(m, dict) or any(not m.get(k) for k in ('mechanism_id', 'claim', 'object', 'conditions', 'predictions')):
            errors.append('Mechanism requires its claim, common conditions and observable predictions')
    if len(mids) != len(mechanisms):
        errors.append('Mechanism IDs must be unique')
    if len(mechanisms) > 1:
        if len({canonical([m.get('object'), m.get('conditions')]) for m in mechanisms}) != 1:
            errors.append('Competing mechanisms require a shared object and conditions')
        compared = set()
        comparisons = problem.get('comparisons', [])
        if not isinstance(comparisons, list):
            comparisons = []
        for row in comparisons:
            if (not isinstance(row, dict) or not _ids(row.get('mechanism_ids')) or not row['mechanism_ids'] or set(row['mechanism_ids']) - mids
                    or not _text(row.get('contrast')) or not _text(row.get('design')) or not row.get('evidence_ids')
                    or not isinstance(row.get('predictions'), dict)
                    or set(row.get('predictions', {})) != set(row.get('mechanism_ids', []))
                    or len({canonical(v) for v in row.get('predictions', {}).values()}) < 2):
                errors.append('Competing mechanisms require a comparison of their differing predictions')
            else:
                compared.update(row['mechanism_ids'])
        if compared != mids:
            errors.append('A mechanism has no discriminating comparison')
    plan = problem.get('verification_plan', [])
    if not isinstance(plan, list) or not plan:
        errors.append('Problem requires verification tasks derived from its structure')
        plan = []
    test_ids = set()
    for test in plan:
        if (not isinstance(test, dict) or any(not _text(test.get(k)) for k in ('test_id', 'question', 'comparison', 'acceptance_condition'))
                or not _ids(test.get('relation_ids', [])) or not _ids(test.get('mechanism_ids', []))
                or not _ids(test.get('evidence_ids')) or not test['evidence_ids']
                or not (test.get('relation_ids') or test.get('mechanism_ids'))
                or set(test.get('relation_ids', [])) - relation_ids or set(test.get('mechanism_ids', [])) - mids):
            errors.append('Verification task must bind its question, structure, evidence and acceptance condition')
            continue
        if test['test_id'] in test_ids:
            errors.append('Verification task IDs must be unique')
        test_ids.add(test['test_id'])
    return errors


def _context(brief, instructions):
    context = deepcopy(instructions or {})
    for key in ('original_request', 'authority', 'rules', 'policy_sha256'):
        if key in brief:
            context[key] = deepcopy(brief[key])
    return context


def generate_argument(brief, sources, host, *, direction='top-down', instructions=None):
    """Execute top-down design or separate extraction, grouping and derivation."""
    if not isinstance(brief, dict) or any(not _text(brief.get(k)) for k in ('purpose', 'reader', 'original_request')):
        raise ArgumentError('Brief requires purpose, reader and the fixed original request')
    if not brief.get('authority'):
        raise ArgumentError('Brief requires the adopted content-change authority')
    catalog, records = source_catalog(sources), []
    context = _context(brief, instructions)
    selection, record = _call(host, 'select', {'brief': brief, 'sources': catalog}, context)
    records.append(record)
    for key in ('central_question', 'central_answer'):
        if not _text(selection.get(key)):
            raise ArgumentError('Source selection requires text for ' + key)
    selected_ids, reasons = selection.get('selected_source_ids'), selection.get('selection_reasons')
    if (not _ids(selected_ids) or not selected_ids or len(selected_ids) != len(set(selected_ids))
            or not isinstance(reasons, dict) or not all(_text(v) for v in reasons.values())):
        raise ArgumentError('Source selection requires unique source IDs and concrete selection reasons')
    if set(selection['selected_source_ids']) - set(catalog) or set(selection['selection_reasons']) != set(selection['selected_source_ids']):
        raise ArgumentError('Source selection must explain each admitted source')
    selected = {k: catalog[k] for k in selection['selected_source_ids']}
    if direction == 'top-down':
        result, record = _call(host, 'decompose', {'brief': brief, 'selection': selection, 'sources': selected}, context)
        records.append(record)
        graph = result.get('graph')
        if not isinstance(graph, dict):
            raise ArgumentError('Decomposition must return graph')
    elif direction == 'bottom-up':
        result, record = _call(host, 'extract', {'brief': brief, 'selection': selection, 'sources': selected}, context)
        records.append(record)
        nodes = deepcopy(result.get('propositions', []))
        if not nodes or not all(isinstance(n, dict) and _text(n.get('node_id')) for n in nodes):
            raise ArgumentError('Extraction must return atomic propositions')
        by_id = {n['node_id']: n for n in nodes}
        if len(by_id) != len(nodes):
            raise ArgumentError('Extracted proposition IDs must be unique')
        for n in nodes:
            if n.get('child_ids') or not n.get('source_refs') or not all(_reference(r, selected) for r in n['source_refs']):
                raise ArgumentError('Extracted propositions require atomic original-source ranges')
        frontier, groups = list(by_id), []
        while len(frontier) > 1:
            classified, record = _call(host, 'classify', {'brief': brief, 'selection': selection,
                'propositions': [by_id[n] for n in frontier]}, context)
            records.append(record)
            level = classified.get('groups', [])
            members = [nid for group in level for nid in group.get('member_ids', [])] if isinstance(level, list) and all(isinstance(g, dict) for g in level) else []
            if not level or len(level) >= len(frontier) or sorted(members) != sorted(frontier):
                raise ArgumentError('Classification must partition and reduce the supplied frontier')
            next_frontier = []
            for group in level:
                if not _text(group.get('classification_basis')):
                    raise ArgumentError('Classify the group before deriving its parent')
                derived, record = _call(host, 'derive', {'brief': brief, 'selection': selection,
                    'group': group, 'propositions': [by_id[n] for n in group['member_ids']], 'sources': selected}, context)
                records.append(record)
                parent = derived.get('node', {})
                nid = parent.get('node_id')
                if not _text(nid) or nid in by_id or parent.get('child_ids') != group['member_ids']:
                    raise ArgumentError('Derived parent must identify every classified member once')
                for cid in group['member_ids']:
                    by_id[cid]['parent_id'] = nid
                parent['parent_id'] = None
                by_id[nid] = parent
                nodes.append(parent)
                group['parent_id'] = nid
                groups.append(group)
                next_frontier.append(nid)
            frontier = next_frontier
        root = frontier[0]
        def levels(nid, level):
            by_id[nid]['abstraction_level'] = level
            for child in by_id[nid].get('child_ids', []):
                levels(child, level + 1)
        levels(root, 0)
        graph = {'schema_version': 1, 'version': str(brief.get('version', '1')),
                 'central_question': selection['central_question'], 'central_answer': selection['central_answer'],
                 'root_ids': [root], 'nodes': nodes, 'groups': groups,
                 'dependencies': deepcopy(brief.get('dependencies', []))}
    else:
        raise ArgumentError('Direction must be top-down or bottom-up')
    if graph.get('central_question') != selection['central_question'] or graph.get('central_answer') != selection['central_answer']:
        raise ArgumentError('Generated argument changes the selected question or answer')
    graph.update(source_ids=list(selected), source_manifest={k: v['sha256'] for k, v in selected.items()},
                 context=context, selection=selection, purpose=brief['purpose'], reader=brief['reader'],
                 completion_conditions=deepcopy(brief.get('completion_conditions', [])))
    graph.pop('argument_sha256', None)
    _assert_argument(graph, catalog)
    graph['argument_sha256'] = argument_sha256(graph)
    graph['generation_records'] = records
    return graph


def build_introduction(shared_situation, complication, graph, sources, host, *, instructions=None):
    catalog = source_catalog(sources)
    output, record = _call(host, 'introduction', {'shared_situation': shared_situation,
        'complication': complication, 'graph': graph, 'sources': catalog}, instructions or graph.get('context'))
    introduction = output.get('introduction')
    updated = deepcopy(graph)
    updated.pop('argument_sha256', None)
    updated['introduction'] = introduction
    _assert_argument(updated, catalog)
    return {'introduction': introduction, 'record': record}


def analyze_problem(problem_input, sources, host, *, instructions=None):
    catalog = source_catalog(sources)
    output, record = _call(host, 'problem', {'input': problem_input, 'sources': catalog}, instructions)
    problem = output.get('problem')
    errors = validate_problem(problem)
    if errors:
        raise ArgumentError('Problem analysis contract failed', errors)
    for comparison in problem.get('comparisons', []):
        if set(comparison.get('evidence_ids', [])) - set(catalog):
            raise ArgumentError('Problem comparison cites an unregistered source')
    for test in problem['verification_plan']:
        if set(test['evidence_ids']) - set(catalog):
            raise ArgumentError('Verification task cites an unregistered source')
    return {'problem': problem, 'record': record}


def _required_review_nodes(graph):
    """Bind each semantic check to its complete relevant proposition set."""
    rows = graph['nodes']
    all_ids = {n['node_id'] for n in rows}
    roots = set(graph['root_ids'])
    parents = {n['node_id'] for n in rows if n.get('child_ids')}
    targets = {check_id: set(all_ids) for check_id in SEMANTIC_CHECKS}
    targets.update(question_answer=roots, problem_analysis=roots,
                   parent_support=parents or all_ids, reader_questions=parents or all_ids,
                   inference_completeness=parents or all_ids,
                   deduction={n['node_id'] for n in rows if n.get('inference_form') == 'deductive'} or roots,
                   induction={n['node_id'] for n in rows if n.get('inference_form') == 'inductive'} or roots)
    return {key: sorted(value) for key, value in targets.items()}


def _review_output(output, graph, sources, record):
    checks, findings = output.get('checks'), output.get('findings')
    if not isinstance(checks, list) or not isinstance(findings, list):
        raise ArgumentError('Review requires concrete checks and findings')
    ids = [c.get('check_id') for c in checks if isinstance(c, dict)]
    if len(ids) != len(checks) or len(set(ids)) != len(ids) or set(ids) != set(SEMANTIC_CHECKS):
        raise ArgumentError('Review must assess every argument check once')
    nodes = {n['node_id']: n for n in graph['nodes']}
    inspected = set()
    required_nodes = _required_review_nodes(graph)
    for check in checks:
        if check.get('verdict') not in {'pass', 'fail'} or not _text(check.get('assessment')):
            raise ArgumentError('Review check requires a concrete assessed verdict')
        if not isinstance(check.get('node_ids'), list) or not check['node_ids'] or set(check['node_ids']) - set(nodes):
            raise ArgumentError('Review check must identify inspected argument nodes')
        if set(required_nodes[check['check_id']]) - set(check['node_ids']):
            raise ArgumentError('Review check omits required propositions: ' + check['check_id'])
        inspected.update(check['node_ids'])
        if not isinstance(check.get('source_refs'), list) or any(not _reference(ref, sources) for ref in check['source_refs']):
            raise ArgumentError('Review source correspondence differs from the source')
        if check['check_id'] in {'parent_support', 'source_correspondence', 'scope_quantities'} and not check['source_refs']:
            raise ArgumentError('Evidence check must cite the inspected source ranges')
    if inspected != set(nodes):
        raise ArgumentError('Argument review omits a proposition')
    for finding in findings:
        if (not isinstance(finding, dict) or finding.get('check_id') not in SEMANTIC_CHECKS
                or not _text(finding.get('finding_id')) or not _text(finding.get('message'))
                or not _text(finding.get('repair')) or not finding.get('node_ids')
                or set(finding.get('node_ids', [])) - set(nodes)
                or finding.get('cause_level') not in {'expression', 'grouping', 'inference', 'global'}):
            raise ArgumentError('Finding requires its exact node, causal level and repair')
    failed = {c['check_id'] for c in checks if c['verdict'] == 'fail'}
    if {f['check_id'] for f in findings} != failed:
        raise ArgumentError('Failed checks and concrete findings differ')
    return {'argument_sha256': argument_sha256(graph), 'checks': checks, 'findings': findings,
            'semantic_pass': not failed, 'record': record, 'release_authorized': False}


def review_argument(graph, sources, host, *, manuscript=None, instructions=None):
    catalog = source_catalog(sources)
    structural = validate_argument(graph, catalog)
    output, record = _call(host, 'review', {'graph': graph, 'sources': catalog,
        'structural_findings': structural['issues'], 'manuscript': manuscript,
        'required_checks': list(SEMANTIC_CHECKS), 'required_node_ids': _required_review_nodes(graph)}, instructions or graph.get('context'))
    result = _review_output(output, graph, catalog, record)
    result['structural'] = structural
    result['valid'] = structural['valid'] and result['semantic_pass']
    generation = graph.get('generation_records', [])
    result['independent_from_generation'] = bool(generation) and (
        record['execution_kind'] == 'independent-subagent'
        and record['worker_id'] not in {r.get('worker_id') for r in generation})
    return result


def _manuscript(manuscript):
    if isinstance(manuscript, str):
        parts = re.split(r'\n\s*\n', manuscript.strip())
        manuscript = [{'paragraph_id': 'p' + str(i + 1), 'section_id': 'document', 'text': text}
                      for i, text in enumerate(parts) if text.strip()]
    if not isinstance(manuscript, list) or not manuscript or not all(isinstance(p, dict) and all(_text(p.get(k)) for k in ('paragraph_id', 'section_id', 'text')) for p in manuscript):
        raise ArgumentError('Manuscript requires paragraph IDs, section IDs and complete text')
    if len({p['paragraph_id'] for p in manuscript}) != len(manuscript):
        raise ArgumentError('Manuscript paragraph IDs must be unique')
    return deepcopy(manuscript)


def reverse_outline(manuscript, host, *, instructions=None):
    paragraphs = _manuscript(manuscript)
    output, record = _call(host, 'reverse', {'manuscript': paragraphs}, instructions)
    rows = output.get('paragraphs', [])
    originals = {p['paragraph_id']: p for p in paragraphs}
    if not isinstance(rows, list) or len(rows) != len(originals) or {p.get('paragraph_id') for p in rows if isinstance(p, dict)} != set(originals):
        raise ArgumentError('Reverse outline must reconstruct every manuscript paragraph once')
    for row in rows:
        source = originals[row['paragraph_id']]
        if any(not _text(row.get(k)) for k in ('central_claim', 'role', 'section_id')) or row['section_id'] != source['section_id'] or not row.get('text_spans'):
            raise ArgumentError('Reverse outline requires actual claim, role, section and text spans')
        if not isinstance(row['text_spans'], list) or not all(isinstance(span, dict) for span in row['text_spans']):
            raise ArgumentError('Reverse outline text spans must be structured records')
        for span in row['text_spans']:
            start, end = span.get('start'), span.get('end')
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(source['text']) or source['text'][start:end] != span.get('quote'):
                raise ArgumentError('Reverse outline quote differs from the completed manuscript')
    sections = output.get('sections', [])
    expected_sections = {p['section_id'] for p in paragraphs}
    if (not isinstance(sections, list) or len(sections) != len(expected_sections)
            or not all(isinstance(s, dict) and _text(s.get('section_id')) for s in sections)
            or {s['section_id'] for s in sections} != expected_sections):
        raise ArgumentError('Reverse outline must reconstruct every section')
    for section in sections:
        expected = {p['paragraph_id'] for p in paragraphs if p['section_id'] == section['section_id']}
        ids = section.get('paragraph_ids')
        if not _text(section.get('claim')) or not _ids(ids) or len(ids) != len(expected) or set(ids) != expected:
            raise ArgumentError('Reconstructed section must integrate its complete paragraph set')
    if not _text(output.get('central_question')) or not _text(output.get('central_answer')):
        raise ArgumentError('Reverse outline must recover the central question and answer')
    output.update(manuscript_sha256=sha256(paragraphs), manuscript=paragraphs, record=record)
    output['outline_sha256'] = sha256({k: v for k, v in output.items() if k != 'record'})
    return output


def compare_outline(graph, outline, sources, host, *, instructions=None):
    catalog = source_catalog(sources)
    structural = validate_argument(graph, catalog)
    current = {k: v for k, v in outline.items() if k not in {'record', 'outline_sha256'}}
    if sha256(current) != outline.get('outline_sha256') or sha256(outline.get('manuscript')) != outline.get('manuscript_sha256'):
        raise ArgumentError('Reconstructed outline or manuscript has changed')
    planned = {p for n in graph['nodes'] for p in n.get('paragraph_ids', [])}
    actual = {p['paragraph_id'] for p in outline['paragraphs']}
    output, record = _call(host, 'compare', {'graph': graph, 'outline': outline,
        'sources': catalog, 'required_checks': list(SEMANTIC_CHECKS), 'required_node_ids': _required_review_nodes(graph),
        'unmapped_paragraphs': sorted(actual - planned), 'missing_paragraphs': sorted(planned - actual)},
        instructions or graph.get('context'))
    result = _review_output(output, graph, catalog, record)
    result.update(outline_sha256=outline['outline_sha256'], manuscript_sha256=outline['manuscript_sha256'],
                  structural=structural, paragraph_coverage=planned == actual,
                  valid=structural['valid'] and planned == actual and result['semantic_pass'])
    return result


def affected_nodes(graph, changed_node_ids):
    nodes = {n['node_id']: n for n in graph['nodes']}
    changed = set(changed_node_ids)
    if not changed <= set(nodes):
        raise ArgumentError('Changed node is outside the argument')
    descendants = set(changed)
    todo = list(changed)
    while todo:
        nid = todo.pop()
        for child in nodes[nid].get('child_ids', []):
            if child in nodes and child not in descendants:
                descendants.add(child)
                todo.append(child)
    affected = set(descendants)
    todo = list(descendants)
    consumers = {}
    for dep in graph.get('dependencies', []):
        consumers.setdefault(dep['from'], []).append(dep['to'])
    while todo:
        nid = todo.pop()
        parent = nodes[nid].get('parent_id')
        if parent in nodes and parent not in affected:
            affected.add(parent)
            todo.append(parent)
        for consumer in consumers.get(nid, []):
            # A consumer's supporting subtree depends on the changed input.
            # Ancestor review invalidation alone does not invalidate siblings.
            branches = [consumer]
            visited = set()
            while branches:
                other = branches.pop()
                if other in visited or other not in nodes:
                    continue
                visited.add(other)
                branches.extend(nodes[other].get('child_ids', []))
                if other not in affected:
                    affected.add(other)
                    todo.append(other)
    return {'affected_node_ids': sorted(affected), 'descendant_node_ids': sorted(descendants),
            'affected_paragraph_ids': sorted({p for n in affected for p in nodes[n].get('paragraph_ids', [])}),
            'affected_section_ids': sorted({nodes[n]['section_id'] for n in affected})}


def repair_argument(graph, findings, sources, host, *, instructions=None):
    if not findings or not all(isinstance(f, dict) and f.get('node_ids') and _text(f.get('repair')) for f in findings):
        raise ArgumentError('Repair requires concrete findings with affected nodes')
    catalog = source_catalog(sources)
    changed = {nid for finding in findings for nid in finding['node_ids']}
    affected = affected_nodes(graph, changed)
    output, record = _call(host, 'repair', {'graph': graph, 'findings': findings, 'sources': catalog,
        'allowed_node_ids': affected['affected_node_ids']}, instructions or graph.get('context'))
    repaired, changes = output.get('graph'), output.get('changes')
    if not isinstance(repaired, dict) or not isinstance(changes, list) or not changes:
        raise ArgumentError('Repair must return a changed argument and attributed changes')
    original_nodes = {n['node_id']: n for n in graph['nodes']}
    repaired_nodes = {n['node_id']: n for n in repaired.get('nodes', [])}
    actual_changes = {nid for nid in set(original_nodes) | set(repaired_nodes) if original_nodes.get(nid) != repaired_nodes.get(nid)}
    allowed = set(affected['affected_node_ids'])
    if (set(original_nodes) - allowed) - set(repaired_nodes) or any(original_nodes[nid] != repaired_nodes[nid] for nid in set(original_nodes) - allowed):
        raise ArgumentError('Repair changes a preserved argument node')
    finding_ids = {f.get('finding_id') for f in findings if _text(f.get('finding_id'))}
    attributed = {row.get('node_id') for row in changes if isinstance(row, dict) and _text(row.get('reason')) and row.get('finding_id') in finding_ids}
    if not actual_changes or attributed != actual_changes:
        raise ArgumentError('Every changed node needs its concrete repair attribution')
    if repaired.get('source_ids') != graph.get('source_ids') or repaired.get('source_manifest') != graph.get('source_manifest'):
        raise ArgumentError('Repair changes the admitted sources')
    for key in ('context', 'purpose', 'reader', 'completion_conditions'):
        if repaired.get(key) != graph.get(key):
            raise ArgumentError('Repair changes the fixed ' + key)
    if repaired.get('version') == graph.get('version'):
        raise ArgumentError('Repair must create a new argument version')
    repaired.pop('argument_sha256', None)
    repaired.pop('reviews', None)
    _assert_argument(repaired, catalog)
    repaired['argument_sha256'] = argument_sha256(repaired)
    repaired['generation_records'] = [*graph.get('generation_records', []), record]
    new_affected = affected_nodes(repaired, actual_changes & set(repaired_nodes))
    combined = {key: sorted(set(affected[key]) | set(new_affected[key])) for key in affected}
    repaired['change_history'] = [*graph.get('change_history', []), {
        'old_argument_sha256': argument_sha256(graph), 'new_argument_sha256': repaired['argument_sha256'],
        'change_kind': 'argument-repair', 'changes': changes, **combined}]
    return {'graph': repaired, 'record': record, 'invalidated_reviews': deepcopy(graph.get('reviews', [])), **combined}


def paragraph_argument(graph, node_id):
    nodes = {n['node_id']: n for n in graph['nodes']}
    if node_id not in nodes:
        raise ArgumentError('Paragraph proposition is not registered')
    row = nodes[node_id]
    parent = nodes.get(row.get('parent_id'))
    children = [nodes[n] for n in row.get('child_ids', [])]
    return {'argument_node_id': node_id,
        'parent_proposition': {'node_id': parent['node_id'], 'claim': parent['claim']} if parent else None,
        'local_question': row['question'],
        'supporting_propositions': [{k: deepcopy(n[k]) for k in ('node_id', 'claim', 'source_refs', 'reasoning')} for n in children],
        'inference_form': row['inference_form'], 'proposition_order': [n['node_id'] for n in children] or [node_id],
        'logical_completion': {'central_claim': row['claim'], 'required_reasoning': row['reasoning'],
            'scope': deepcopy(row['scope']), 'source_refs': deepcopy(row['source_refs']),
            'global_question': graph['central_question'], 'argument_sha256': argument_sha256(graph)}}


def metrics(graph, review, *, outline=None, repair_count=0, prohibited_occurrences=0):
    """Compute comparison metrics from bound judgments and concrete findings."""
    if review.get('argument_sha256') != argument_sha256(graph):
        raise ArgumentError('Metrics require the current argument review')
    checks = {r['check_id']: r for r in review['checks']}
    findings = review['findings']
    count = lambda *ids: sum(f['check_id'] in ids for f in findings)
    required_nodes = _required_review_nodes(graph)
    coverage_counts = {}
    def coverage(key):
        targets = set(required_nodes[key])
        inspected = set(checks[key].get('node_ids', [])) & targets
        failed = {nid for f in findings if f['check_id'] == key for nid in f['node_ids']} & targets
        if checks[key]['verdict'] == 'fail' and not failed:
            failed = set(targets)
        passed = inspected - failed
        coverage_counts[key] = {'passed': len(passed), 'required': len(targets)}
        return len(passed) / len(targets) if targets else 0.0
    result = {'direct_answer_coverage': coverage('question_answer'),
        'mandatory_proposition_coverage': coverage('reverse_alignment') if outline else coverage('parent_support'),
        'parent_evidence_alignment': coverage('parent_support'),
        'reader_question_alignment': coverage('reader_questions'), 'grouping_fit': coverage('grouping'),
        'required_explanation_coverage': coverage('inference_completeness'),
        'inference_gaps': count('inference_completeness', 'deduction', 'induction'),
        'empty_summaries': sum(bool(EMPTY_SUMMARY.fullmatch(n['claim'].strip())) for n in graph['nodes']),
        'paragraph_duplicates_or_contradictions': count('information_density', 'reverse_alignment'),
        'source_mismatches': count('source_correspondence', 'scope_quantities'),
        'prohibited_occurrences': prohibited_occurrences, 'repair_count': repair_count,
        'structural_issues': len(review.get('structural', {}).get('issues', [])),
        'argument_sha256': argument_sha256(graph), 'coverage_counts': coverage_counts}
    if outline:
        result['manuscript_sha256'] = outline['manuscript_sha256']
    return result


def compare_metrics(before, after, before_inputs, after_inputs):
    keys = ('material_sha256', 'question', 'results_sha256', 'conditions_sha256')
    if any(not before_inputs.get(k) or before_inputs.get(k) != after_inputs.get(k) for k in keys):
        raise ArgumentError('Comparison requires identical materials, question, results and writing conditions')
    measures = {k: {'before': before[k], 'after': after[k], 'change': after[k] - before[k]}
                for k in before.keys() & after.keys() if type(before[k]) in (int, float) and type(after[k]) in (int, float)}
    return {'inputs': {k: before_inputs[k] for k in keys}, 'measures': measures,
            'before_argument_sha256': before.get('argument_sha256'), 'after_argument_sha256': after.get('argument_sha256')}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    check = commands.add_parser('check')
    check.add_argument('--graph', type=Path, required=True)
    check.add_argument('--sources', type=Path, required=True)
    plan = commands.add_parser('task')
    plan.add_argument('--operation', choices=tuple(OPERATIONS), required=True)
    plan.add_argument('--payload', type=Path, required=True)
    plan.add_argument('--instructions', type=Path)
    arguments = parser.parse_args(argv)
    if arguments.command == 'check':
        result = validate_argument(json.loads(arguments.graph.read_text()), json.loads(arguments.sources.read_text()))
    else:
        result = make_task(arguments.operation, json.loads(arguments.payload.read_text()),
                           json.loads(arguments.instructions.read_text()) if arguments.instructions else None)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get('valid', True) else 1


if __name__ == '__main__':
    raise SystemExit(main())

