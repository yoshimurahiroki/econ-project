"""Evaluate observed capability exposure without changing a host configuration."""


def _names(value, label):
    if not isinstance(value, list) or any(not isinstance(x, str) or not x for x in value):
        raise ValueError(f'{label} must be a list of capability IDs')
    if len(set(value)) != len(value):
        raise ValueError(f'{label} contains duplicates')
    return set(value)


def evaluate(inventory, observations, policy, required, protection_manifest=None):
    """Return candidate evidence; observations are actual per-prompt exposures and uses.

    inventory has host, host_version, source_kind, complete and tools (id, package, rare).
    Only a model-request-declarations inventory establishes model-visible exposure;
    callable-tool metadata alone cannot establish declaration-level candidates.
    Each observation has session_id, prompt_id, exposed, attempted, completed and indirect lists;
    a null list means unknown. IDs in required include task and operation dependencies.
    protection_manifest records the caller's verified required IDs or packages by category:
    mandatory_instruction, read, state, recovery, current_skill, current_external_write,
    delegation. The first four categories must be nonempty; conditional categories may
    be empty only when the current work has no such dependency. Every listed ID must
    also appear in required. Without this verified input no candidate is proposed.
    """
    if not isinstance(inventory, dict) or not isinstance(inventory.get('tools'), list):
        raise ValueError('Invalid inventory')
    rows = inventory['tools']
    if any(not isinstance(x, dict) or not isinstance(x.get('id'), str) or not x['id']
           or not isinstance(x.get('package'), str) or not x['package']
           or type(x.get('rare')) is not bool for x in rows):
        raise ValueError('Invalid capability record')
    ids = [x['id'] for x in rows]
    if len(ids) != len(set(ids)) or type(inventory.get('complete')) is not bool:
        raise ValueError('Invalid inventory identity or completeness')
    if (not isinstance(observations, list) or not isinstance(policy, dict)
            or set(policy) != {'enabled', 'protected'} or type(policy.get('enabled')) is not bool):
        raise ValueError('Invalid observations or policy')
    required_names = _names(required, 'required')
    protected = _names(policy.get('protected'), 'protected') | required_names
    if any(not isinstance(x, str) or not x for x in protected):
        raise ValueError('Invalid required capability')
    unmatched_required = set(required) - (set(ids) | {row['package'] for row in rows})
    unavailable_required = unmatched_required if inventory['complete'] else set()
    unknown_required = unmatched_required if not inventory['complete'] else set()
    categories = ('mandatory_instruction', 'read', 'state', 'recovery', 'current_skill',
                  'current_external_write', 'delegation')
    verified_protection = False
    if protection_manifest is not None:
        if not isinstance(protection_manifest, dict) or set(protection_manifest) != set(categories):
            raise ValueError('Invalid protection manifest')
        groups = {key: _names(protection_manifest[key], key) for key in categories}
        verified_protection = (all(groups[key] for key in categories[:4])
                               and set().union(*groups.values()).issubset(required_names))
    seen, usable, unknown, used = set(), [], False, set()
    for item in observations:
        if not isinstance(item, dict):
            raise ValueError('Invalid observation')
        values = [item.get(field) for field in ('exposed', 'attempted', 'completed', 'indirect')]
        for value in values[1:]:
            if value is not None:
                used |= _names(value, 'observation')
        sid, pid = item.get('session_id'), item.get('prompt_id')
        if not isinstance(sid, str) or not sid or not isinstance(pid, str) or not pid:
            unknown = True
            continue
        key = (sid, pid)
        if key in seen:
            raise ValueError('Duplicate prompt observation')
        seen.add(key)
        if any(x is None for x in values):
            unknown = True
            continue
        exposed, attempted, completed, indirect = (_names(value, 'observation') for value in values)
        usable.append((sid, exposed, attempted, completed, indirect))
    candidates = []
    tool_results = []
    for row in rows:
        name, package = row['id'], row['package']
        sessions = {sid for sid, exposed, *_ in usable if name in exposed}
        prompts = sum(name in exposed for _, exposed, *_ in usable)
        enough = (prompts >= 10 and len(sessions) >= 2) or len(sessions) >= 5
        if row['rare']:
            enough = len(sessions) >= 10
        reasons = []
        if not policy['enabled']: reasons.append('disabled')
        if not verified_protection: reasons.append('protection-unverified')
        if inventory.get('source_kind') != 'model-request-declarations': reasons.append('source-not-declarations')
        if not inventory['complete'] or unknown: reasons.append('incomplete-evidence')
        if unavailable_required: reasons.append('required-unavailable')
        if name in protected or package in protected: reasons.append('protected')
        if name in used or package in used: reasons.append('observed-use')
        if not enough: reasons.append('insufficient-exposure')
        record = {'id': name, 'package': package, 'prompts': prompts, 'sessions': len(sessions),
                  'attempted_prompts': sum(name in attempted for _, _, attempted, _, _ in usable),
                  'completed_prompts': sum(name in completed for _, _, _, completed, _ in usable),
                  'indirect_prompts': sum(name in indirect for _, _, _, _, indirect in usable),
                  'candidate': not reasons, 'reasons': reasons}
        tool_results.append(record)
        if not reasons: candidates.append(name)
    packages = []
    for package in sorted({row['package'] for row in rows}):
        members = [row for row in tool_results if row['package'] == package]
        packages.append({'id': package, 'members': [r['id'] for r in members],
                         'candidate': bool(members) and all(r['candidate'] for r in members)})
    return {'host': inventory.get('host'), 'host_version': inventory.get('host_version'),
            'inventory_source_kind': inventory.get('source_kind'),
            'declaration_reduction': 'unverified', 'enabled': policy['enabled'],
            'protection_verified': verified_protection,
            'protected': sorted(protected), 'unavailable_required': sorted(unavailable_required),
            'unknown_required': sorted(unknown_required),
            'tools': tool_results, 'packages': packages,
            'candidates': candidates}


def change(policy, action, capability=None):
    """Return a policy update or unsupported host action without mutating its input."""
    if not isinstance(policy, dict) or set(policy) != {'enabled', 'protected'} or type(policy.get('enabled')) is not bool:
        raise ValueError('Invalid policy')
    protected = _names(policy.get('protected'), 'protected')
    updated = {'enabled': policy['enabled'], 'protected': sorted(protected)}
    if action == 'protect':
        if not isinstance(capability, str) or not capability:
            raise ValueError('A capability ID is required')
        updated['protected'] = sorted(protected | {capability})
        result = 'updated'
    elif action in ('off', 'on'):
        updated['enabled'] = action == 'on'
        result = 'updated'
    elif action == 'dry-run':
        result = 'no-change'
    elif action == 'apply':
        result = 'unsupported-declaration-reduction-unverified'
    elif action == 'restore':
        result = 'not-applied'
    else:
        raise ValueError('Unknown action')
    return {'result': result, 'policy': updated}
