#!/usr/bin/env python3
"""Export a route-selected standalone instruction package."""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit
sys.path.insert(0, str(Path(__file__).resolve().parent))
from route_registry import load_routes, resource_path, resolve_operation, native_index, entry_contract, relative, merge_selection, rule_selection, required_closure, generate_entries, validate_rule_bodies, markdown_sections, heading_id, transform_entry_references, inline_code_mask, optional_reference, extract_sections
ROOT = Path(__file__).resolve().parents[1]


def validate_package_versions(root, *, required=False):
    """Reject mixed source releases before any generated file is changed."""
    root = Path(root)
    paths = [root / 'plugin.json', root / '.codex-plugin/plugin.json']
    if not required and not any(path.exists() for path in paths):
        return None  # Standalone deployed instruction trees have no plugin manifests.
    if not all(path.is_file() for path in paths):
        raise ValueError('Both root and Codex plugin manifests are required')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate plugin manifest field: ' + key)
            result[key] = value
        return result
    versions = [json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique).get('version') for path in paths]
    tree = ast.parse((root / 'harness/policy_assets.py').read_text(encoding='utf-8'))
    policies = [ast.literal_eval(node.value) for node in tree.body
                if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'POLICY_ID' for t in node.targets)]
    if (not all(isinstance(v, str) and re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', v) for v in versions)
            or len(set(versions)) != 1 or policies != ['economics-native-' + versions[0]]):
        raise ValueError('Root plugin, Codex plugin and policy versions must match')
    return versions[0]


def prose_resource(resource):
    """Executable modules and machine-readable assets are not Markdown."""
    return Path(resource['source_path']).suffix.lower() in ('', '.md', '.txt', '.mdc')


def runtime_prose(resource_id, text):
    """Omit the synchronization receipt from the generated integration guide."""
    if resource_id != 'integration':
        return text
    from sync_common_core import read_receipt
    _, _, start, end = read_receipt(text.encode('utf-8'))
    return text if start is None else text[:start] + text[end:]


def rewrite_code_paths(text, replacements):
    """Relocate registered paths in documentation examples, not program bytes.

    Code examples run from the exported package root. Markdown links elsewhere
    still use paths relative to the containing document.
    """
    mask = inline_code_mask(text)
    if not replacements:
        return text
    # Receipt paths and hashes describe the recorded source, not this layout.
    from sync_common_core import read_receipt
    _, _, start, end = read_receipt(text.encode('utf-8'))
    if start is not None:
        mask[start:end] = bytes(end - start)
    names = '|'.join(re.escape(name) for name in sorted(replacements, key=len, reverse=True))
    pattern = re.compile(r'(?<![\w./-])(' + names + r')(?![\w./-])')
    return pattern.sub(lambda match: replacements[match.group()]
                       if all(mask[match.start():match.end()]) else match.group(), text)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def publish_directory(staging, target):
    from sync_common_core import runtime_io
    runtime_io().atomic_publish(staging, target)



def destination_span(text, start):
    """Read an angle-bracket or balanced bare Markdown destination."""
    if start >= len(text):
        return None
    if text[start] == "<":
        end = start + 1
        while end < len(text):
            if text[end] == "\\":
                end += 2
            elif text[end] == ">":
                return start + 1, end, end + 1
            elif text[end] == "\n":
                return None
            else:
                end += 1
        return None
    end, depth = start, 0
    while end < len(text):
        char = text[end]
        if char == "\\":
            end += 2
            continue
        if char.isspace() and depth == 0:
            break
        if char == "(":
            depth += 1
        elif char == ")":
            if depth == 0:
                break
            depth -= 1
        end += 1
    if depth or end == start:
        return None
    return start, end, end


def rewrite_fragment(text, rewrite):
    mask = inline_code_mask(text)
    changes = []
    title_close = re.compile(
        r'''\s*(?:"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|\((?:[^)\\]|\\.)*\))?\s*\)'''
    )
    for match in re.finditer(r"(?<!\\)\]\([ \t\n]*", text):
        if mask[match.start()]:
            continue
        span = destination_span(text, match.end())
        if span is None:
            continue
        start, end, after = span
        closing = title_close.match(text, after)
        if closing is None or any(mask[match.start():closing.end()]):
            continue
        changes.append((start, end, rewrite(text[start:end])))
    for match in re.finditer(r"^ {0,3}\[(?!\^)[^\]\n]+\]:[ \t]*", text, re.MULTILINE):
        if mask[match.start()]:
            continue
        span = destination_span(text, match.end())
        if span:
            start, end, _ = span
            if not any(mask[start:end]):
                changes.append((start, end, rewrite(text[start:end])))
    for start, end, replacement in sorted(set(changes), reverse=True):
        text = text[:start] + replacement + text[end:]
    return text


def rewrite_markdown(text, rewrite):
    """Rewrite prose destinations, preserving fenced and inline code."""
    output, pending = [], []
    fence = None
    indented_code = False
    blank_before = True
    for line in text.splitlines(keepends=True):
        opening = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line.rstrip("\n"))
        indented = line.startswith(("    ", "\t"))
        if not fence and (indented_code or blank_before) and (indented or not line.strip()):
            output.append(rewrite_fragment("".join(pending), rewrite))
            pending = []
            output.append(line)
            indented_code = indented or indented_code
            blank_before = not line.strip()
            continue
        indented_code = False
        if fence:
            output.append(line)
            if re.match(r"^ {0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}[ \t]*$", line.rstrip("\n")):
                fence = None
        elif opening:
            output.append(rewrite_fragment("".join(pending), rewrite))
            pending = []
            fence = opening.group(1)
            output.append(line)
        else:
            pending.append(line)
        blank_before = not line.strip()
    output.append(rewrite_fragment("".join(pending), rewrite))
    return "".join(output)


def validate_required_bodies(routes, operations, selections, read_resource):
    """Check registered rule bodies against the exact selected package text."""
    resources = routes['resources']
    required_selections = {}
    # This invocation verifies one immutable package snapshot. Reuse its bytes
    # and completed rule checks across operations, never across snapshots.
    texts, verified = {}, set()
    def read_snapshot(rid):
        if rid not in texts:
            raw = read_resource(rid)
            texts[rid] = raw.decode('utf-8') if isinstance(raw, bytes) else raw
        return texts[rid]
    for operation in operations:
        pending = [rule for rule in operation.get('active_rules', []) if rule not in verified]
        validate_rule_bodies(routes, pending, read_snapshot,
                             origin=operation['canonical_operation'])
        verified.update(pending)
        for rule_id in operation.get('active_rules', []):
            for rid, rule_scope in rule_selection(routes, rule_id, operation['canonical_operation']).items():
                merge_selection(required_selections, {rid: rule_scope})
                try:
                    if rid not in selections or (rule_scope.get('whole_resource') and not selections[rid].get('whole_resource')):
                        raise ValueError('required body is absent from the selected snapshot')
                    if not selections[rid].get('whole_resource') and not set(rule_scope.get('sections', [])) <= set(selections[rid].get('sections', [])):
                        raise ValueError('required section is absent from the selected snapshot')
                except (OSError, ValueError) as error:
                    raise ValueError(f'Missing required rule {rule_id}; operation {operation["canonical_operation"]}; source {resources[rid]["source_path"]}: {error}') from error
    return required_selections


def validate_internal_links(contents, contexts=None, non_prose=()):
    """Check local file and anchor targets without rewriting or optionalizing them."""
    contexts = contexts or {}
    for name, text in contents.items():
        if name in non_prose or name.endswith(('.py', '.sh', '.json', '.yaml')):
            continue
        def validate_link(link):
            parts = urlsplit(link)
            if parts.scheme or link.startswith('//'):
                return link
            destination_name = os.path.normpath(str(Path(name).parent / unquote(parts.path))) if parts.path else name
            destination_name = destination_name.replace(os.sep, '/')
            if destination_name not in contents:
                raise ValueError(f'Missing packaged reference in {name}: {link}; {contexts.get(name, "generated package")}')
            if parts.fragment:
                anchors = {h['id'] for h in markdown_sections(contents[destination_name])[1]}
                if unquote(parts.fragment) not in anchors:
                    raise ValueError(f'Missing packaged section in {name}: {link}; {contexts.get(name, "generated package")}')
            return link
        rewrite_markdown(text, validate_link)


def knowledge_assets(root, layout, ids=(), *, source_assets=False):
    """Read the saved generation and its selected prerequisite closure."""
    prefix = Path('skills/econ-knowledge') if layout == 'source' else Path('.agents/skills/econ-knowledge')
    helper = root / prefix / 'scripts/knowledge.py'
    base = root / prefix / 'references'
    spec = importlib.util.spec_from_file_location('export_knowledge', helper)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if source_assets and ids:
        raise ValueError('Canonical source assets require the complete collection')
    reader = module.Reader(base)
    if source_assets and reader.projection:
        raise ValueError('Canonical source assets are unavailable from a runtime projection')
    manifest_raw = reader.contents['manifest.json']
    manifest = reader.manifest
    selected = list(dict.fromkeys(ids)) if ids else (
        reader.selection['selected_ids'] if reader.selection else list(manifest['units']))
    reader.domains()
    selection = reader.units(selected)
    if reader.spec_version == getattr(module, 'SEMANTIC_VERSION', 'knowledge-v2'):
        for name in module.SEMANTIC_FILES:
            reader.semantic(name)
    # Reader checks the consumed catalog, chapter, index and body hashes once.
    # Regeneration belongs to knowledge.py build after an authored input changes.
    names = set(reader.contents)
    if source_assets:
        for name, expected in manifest['chapters'].items():
            reader.read(name, expected)
            names.add(name)
    else:
        names = {name for name in names if name != 'catalog.json'
                 and not name.startswith('chapters/')}
    result = {name: reader.contents[name] for name in sorted(names)}
    if not source_assets:
        result['runtime.json'] = module.encoded({'projection_version': module.PROJECTION_VERSION,
                                                  'manifest_sha256': module.sha(manifest_raw)})
    if ids:
        result['selection.json'] = module.encoded({'spec_version': manifest['spec_version'],
            'manifest_sha256': selection['manifest_sha256'], 'selected_ids': selected,
            'closure_ids': selection['closure_ids']})
    return prefix / 'references', result


def knowledge_owner_ids(routes):
    return {rid for rid, record in routes['resources'].items()
            if record['source_path'] == 'skills/econ-knowledge/SKILL.md'}


def resource_closure(routes, selections, *, whole_resources=False):
    """Add each selected resource's declared executable and section dependencies."""
    while True:
        before = canonical(selections)
        for rid, selection in list(selections.items()):
            if whole_resources:
                selection = selections[rid] = {'whole_resource': True}
            resource = routes['resources'][rid]
            merge_selection(selections, {dep: {'whole_resource': True}
                                         for dep in resource.get('required_resources', [])})
            merge_selection(selections, resource.get('required_resource_sections', {}))
            sections = selection.get('sections', [])
            if selection.get('whole_resource'):
                sections = resource.get('section_dependencies', {})
            for section in sections:
                merge_selection(selections, resource.get('section_dependencies', {}).get(section, {}))
        if before == canonical(selections):
            return selections


def optional_inputs(omitted):
    return ('# Optional inputs\n\nThese functions are inactive in this snapshot. If needed, request the named input or regenerate the snapshot with its condition/reference. Do not retrieve an external repository automatically.\n\n' +
            '\n'.join('## ' + rid + '\n\nRequired additional input: ' + rid + '.\n'
                      for rid in sorted(omitted))).rstrip() + '\n'


def export(target, profile='standalone', skills=None, *, task=None, support=(), references=(), style_profile=None, mode=None, conditions=(), layout='source', output_format='flat', knowledge_ids=()):
    root = ROOT.resolve()
    validate_package_versions(root)
    target = Path(target).absolute()
    if any(parent.is_symlink() for parent in target.parents):
        raise ValueError('Refuse symlink output ancestor')
    if target.exists() or target.is_symlink() or target.resolve().is_relative_to(root):
        raise ValueError('Choose a fresh output directory outside the source tree')
    if profile != 'standalone' or (task and skills):
        raise ValueError('Use standalone and either --task or --skills')
    routes = load_routes(root, layout)
    resources = routes['resources']
    config = {"version": 1, "writing_profile": "default-micro", "files": []}
    context = root / 'docs/ai/repo_context.md'
    context_raw = context.read_bytes() if context.is_file() else b''
    marker = '<!-- export-project:v1 -->'
    if marker.encode() in context_raw:
        context_text = context_raw.decode()
        if context_text.count(marker) != 1:
            raise ValueError('Duplicate project configuration')
        match = re.search(r'<!-- export-project:v1 -->\s*(```|~~~)json\s*\n(.*?)\n\1', context_text, re.S)
        if not match:
            raise ValueError('Malformed project configuration')
        config.update(json.loads(match.group(2)))
        if set(config) != {'version', 'writing_profile', 'files'} or config['version'] != 1:
            raise ValueError('Unsupported project configuration')
    effective_profile = style_profile or config['writing_profile']
    custom = None
    if output_format not in ('flat', 'deployed'):
        raise ValueError('Unknown output format')
    selectors = [(task, mode)] if task else [(r.get('id', r['skill_id']), r['mode']) for r in routes['operations'] if not skills or r['skill_id'] in skills]
    if skills and set(skills) - {r['skill_id'] for r in routes['operations']}:
        raise ValueError('Unknown specialist in --skills')
    for item in support:
        selector, separator, support_mode = item.partition(':')
        selectors.append((selector, support_mode if separator else None))
    operations = [resolve_operation(routes, selector, selected_mode, user_profile=style_profile, project_profile=config['writing_profile'], conditions=conditions) for selector, selected_mode in selectors]
    final_operations = [op for op in operations if not op.get('runtime_action')]
    if (effective_profile and effective_profile != 'default-micro'
            and any(op.get('selected_profile') == effective_profile for op in operations)):
        custom = Path(effective_profile)
        custom = custom if custom.is_absolute() else root / relative(effective_profile)
        if not custom.is_file() or custom.is_symlink():
            raise ValueError('Custom profile must be a regular file')
    selections = {}
    for op in operations:
        merge_selection(selections, op['resource_sections'])
    reference_required = []
    for value in references:
        matches = [rid for rid, res in resources.items() if value in (rid, res['source_path'], res['deployment_path'])]
        if len(matches) != 1:
            raise ValueError(f'Select a registered reference ID or path: {value}')
        merge_selection(selections, {matches[0]: {'whole_resource': True}})
        if routes.get('schema_version') == 2:
            rid = matches[0]
            rule_ids = ([rid + '.all'] if rid + '.all' in routes['rules'] else
                        [rule_id for rule_id, rule in routes['rules'].items() if rule['resource_id'] == rid])
            if not rule_ids:
                raise ValueError('Selected reference has no registered rule: ' + rid)
            active, dependency_selection = required_closure(routes, rule_ids, conditions, 'reference:' + value)
            merge_selection(selections, dependency_selection)
            reference_required.append({'canonical_operation': 'reference:' + value, 'active_rules': active})
    # Include the automatically required state helper before resolving its
    # declared dependencies, just like explicitly selected resources.
    if final_operations and 'policy-manifest' in selections and 'team-state-helper' in resources:
        merge_selection(selections, {'team-state-helper': {'whole_resource': True}})
    if output_format == 'deployed':
        # Installed reading and re-export use the complete registry metadata;
        # the selected rule and knowledge bodies retain their bounded closure.
        merge_selection(selections, {rid: {'whole_resource': True} for rid in (
            'registry-operations', 'registry-resources', 'registry-placements',
            'tool-route-registry-py')})
    resource_closure(routes, selections)
    selected = set(selections)
    knowledge_selected = bool(knowledge_owner_ids(routes) & selected) or any(op.get('skill_id') == 'econ-knowledge' for op in operations)
    if knowledge_ids and not knowledge_selected:
        raise ValueError('Select the econ-knowledge reference before choosing knowledge IDs')
    unsupported = sorted(rid for rid in selected if resources[rid].get('snapshot') == 'source_distribution_only')
    if unsupported:
        raise ValueError('Use complete source distribution for maintenance tools; cannot publish an executable flat/deployed snapshot for: ' + ', '.join(unsupported))
    output_paths = {rid: res['export_alias' if output_format == 'flat' else 'deployment_path'] for rid, res in resources.items()}
    # Both physical layouts use the exact same resolved selections.
    # All logical paths resolve through this registry in either physical layout.
    path_ids = {}
    def register_path(path, rid):
        previous = path_ids.setdefault(path.absolute(), rid)
        if previous != rid:
            raise ValueError(f'Ambiguous registered resource path: {path}')

    for rid, res in resources.items():
        for key in ('source_path', 'deployment_path'):
            register_path(root / res[key], rid)
    generated_names = ('ECON_INDEX.md', 'OPTIONAL_INPUTS.md', 'PROJECT_INSTRUCTIONS.txt')
    declared_root = (routes.get('placements', {}).get('deployed', {}).get('policy_root', '.')
                     if output_format == 'deployed' else '.')
    if declared_root != '.':
        relative(declared_root)
    generated = {name: (Path(declared_root) / name).as_posix() for name in generated_names}
    aliases = {output_paths[rid]: rid for rid in selected}
    if {name.casefold() for name in aliases} & {name.casefold() for name in generated.values()}:
        # The instruction template is rendered below if declared as a resource.
        collisions = {name.casefold() for name in aliases} & {name.casefold() for name in set(generated.values()) - {generated['PROJECT_INSTRUCTIONS.txt']}}
        if collisions:
            raise ValueError('Reserved generated aliases: ' + ', '.join(collisions))
    if custom and 'CUSTOM_STYLE.md' in aliases:
        raise ValueError('Custom profile alias collision')
    required_selections = validate_required_bodies(
        routes, operations + reference_required, selections,
        lambda rid: resource_path(root, resources[rid], layout).read_text(encoding='utf-8'))
    raw = {rid: resource_path(root, resources[rid], layout).read_bytes() for rid in sorted(selected)}
    active_anchors = {rid: {h['id'] for h in markdown_sections(extract_sections(raw[rid].decode('utf-8'), selections[rid], rid))[1]} for rid in selected}
    project_aliases = {}
    for entry in config['files']:
        if not isinstance(entry, dict) or set(entry) != {'path', 'output'}:
            raise ValueError('Project file requires path and output')
        name = relative(entry['output'])
        if '/' in name or name.casefold() in {n.casefold() for n in (*aliases, *generated.values(), *project_aliases.values(), 'CUSTOM_STYLE.md')}:
            raise ValueError('Project file output collision or non-flat alias')
        project_aliases[(root / relative(entry['path'])).resolve()] = name
    omitted = set()
    generated_sources, previous_optional = {}, {}
    if layout == 'installed':
        input_root = root / routes.get('placements', {}).get('deployed', {}).get('policy_root', '.')
        for name in generated_names:
            candidate = input_root / name
            if candidate.is_file() and not candidate.is_symlink():
                generated_sources[candidate.absolute()] = name
        optional_source = input_root / 'OPTIONAL_INPUTS.md'
        if optional_source.absolute() in generated_sources:
            previous_optional = {h['id']: h['title'] for h in markdown_sections(optional_source.read_text(encoding='utf-8'))[1]}
    def destination(source, link, output=None):
        if output is None: output = generated['ECON_INDEX.md']
        def local(path):
            return os.path.relpath(path, str(Path(output).parent)).replace(os.sep, '/')
        parts = urlsplit(link)
        if parts.scheme or link.startswith('//'):
            return link
        clean = unquote(parts.path)
        suffix = '#' + parts.fragment if parts.fragment else ''
        if clean in generated:
            return local(generated[clean]) + suffix
        if custom and clean == 'CUSTOM_STYLE.md':
            return local(clean) + suffix
        path = ((root / clean.lstrip('/') if clean.startswith('/') else source.parent / clean) if clean else source).resolve()
        if path in generated_sources:
            name = generated_sources[path]
            if name == 'OPTIONAL_INPUTS.md' and parts.fragment:
                title = previous_optional.get(unquote(parts.fragment))
                rid, section = optional_reference(resources, title or unquote(parts.fragment))
                if rid in selected and (section is None or section in active_anchors[rid]):
                    return local(output_paths[rid]) + ('#' + section if section else '')
                title = rid + ('--' + section if section else '')
                omitted.add(title)
                return local(generated[name]) + '#' + heading_id(title)
            return local(generated[name]) + suffix
        if path in project_aliases:
            return local(project_aliases[path]) + suffix
        rid = aliases.get(clean, path_ids.get(path))
        if rid is None and layout == 'installed':
            source_id = path_ids.get(source.resolve())
            if source_id is not None:
                logical_source = root / resources[source_id]['source_path']
                legacy_path = (logical_source.parent / clean if clean else logical_source).resolve()
                rid = path_ids.get(legacy_path)
        if routes.get('schema_version') == 2 and rid in ('registry-operations', 'native-index'):
            return local(generated['ECON_INDEX.md'])
        if rid in selected:
            if parts.fragment and unquote(parts.fragment) not in active_anchors[rid]:
                if required_selections.get(rid, {}).get('whole_resource'):
                    raise ValueError(f'Missing section in required resource {rid}: {link}; source {source}')
                if unquote(parts.fragment) not in {h['id'] for h in markdown_sections(raw[rid].decode('utf-8'))[1]}:
                    raise ValueError(f'Missing source section in {source}: {link}; operations ' +
                                     ', '.join(op['canonical_operation'] for op in operations))
                optional_section = rid + '--' + unquote(parts.fragment)
                omitted.add(optional_section)
                return local(generated['OPTIONAL_INPUTS.md']) + '#' + heading_id(optional_section)
            return local(output_paths[rid]) + suffix
        if rid:
            omitted.add(rid)
            return local(generated['OPTIONAL_INPUTS.md']) + '#' + heading_id(rid)
        raise ValueError(f'Unregistered local reference in {source.name}: {link}')
    # Commands in documentation use package-root paths. Include unambiguous
    # basenames because guides often name a sibling executable or dictionary.
    code_paths = {}
    basenames = {}
    for other, item in resources.items():
        basenames.setdefault(Path(item['source_path']).name, set()).add(other)
        if other in selected:
            for key in ('source_path', 'deployment_path'):
                code_paths[item[key]] = output_paths[other]
    for name, ids in basenames.items():
        if len(ids) == 1:
            other = next(iter(ids))
            if other in selected:
                code_paths.setdefault(name, output_paths[other])
    contents = {}
    for rid in sorted(selected):
        res = resources[rid]
        source = resource_path(root, res, layout)
        text = raw[rid].decode('utf-8')
        if not prose_resource(res):
            if not selections[rid].get('whole_resource'):
                raise ValueError(f'Executable/data resource must be selected whole: {rid}')
            # Do not rewrite regexes, code comments, JSON strings or import
            # names as if they were prose links or instruction templates.
            contents[output_paths[rid]] = text
            continue
        text = runtime_prose(rid, text)
        text = extract_sections(text.replace('\r\n', '\n'), selections[rid], rid)
        if res['source_path'] == 'docs/ai/compiled_ai_skills.md':
            text = '# Selected operations\n\n' + '\n'.join(f"- {op['canonical_operation']}" for op in operations) + '\n'
        text = rewrite_markdown(text, lambda link: destination(source, link, output_paths[rid]))
        text = rewrite_code_paths(text, code_paths)
        # Inactive inline physical references remain explicit optional inputs.
        # Selected paths were relocated above, including multiword commands.
        for other, item in sorted(resources.items(), key=lambda pair: -len(pair[1]['source_path'])):
            if other in selected:
                continue
            for key in ('source_path', 'deployment_path'):
                token = '`' + item[key] + '`'
                if token in text:
                    text = text.replace(token, '`optional input: ' + other + '`')
                    omitted.add(other)
        text = text.replace('{{METHOD_PROVIDER}}', ', '.join(op['skill_id'] + ':' + op['mode'] for op in operations))
        text = text.replace('{{STUDY_ENTRY_POINT_LINE}}', '')
        if re.search(r'\{\{[^{}]+\}\}', text):
            raise ValueError(f'Unresolved template in {rid}')
        contents[output_paths[rid]] = text
    knowledge_outputs = set()
    if knowledge_selected:
        _, asset_files = knowledge_assets(root, layout, knowledge_ids)
        asset_target = (Path('knowledge/references') if output_format == 'flat'
                        else Path('.agents/skills/econ-knowledge/references'))
        for name, data in asset_files.items():
            output = (asset_target / name).as_posix()
            if output in contents:
                raise ValueError('Knowledge asset output collision: ' + output)
            contents[output] = data.decode('utf-8')
            knowledge_outputs.add(output)
    for entry in config['files']:
        if set(entry) != {'path', 'output'}:
            raise ValueError('Project file requires path and output')
        filename = relative(entry['output'])
        if '/' in filename or filename.casefold() in {name.casefold() for name in (*contents, *generated.values(), 'CUSTOM_STYLE.md')}:
            raise ValueError('Project file output collision or non-flat alias')
        source = root / relative(entry['path'])
        if source.is_symlink() or not source.resolve().is_relative_to(root):
            raise ValueError('Project file escapes repository')
        data = source.read_bytes()
        text = rewrite_markdown(data.decode(), lambda link: destination(source, link, filename))
        contents[filename] = text
    custom_output = ('.agents/profiles/CUSTOM_STYLE.md'
                     if custom and 'policy-manifest' in selected and output_format == 'deployed'
                     else 'CUSTOM_STYLE.md')
    if custom:
        data = custom.read_bytes()
        text = rewrite_markdown(data.decode(), lambda link: destination(custom, link, custom_output))
        contents[custom_output] = text
        custom_pointer = (Path(declared_root) / 'CUSTOM_STYLE.md').as_posix()
        if custom_output != custom_pointer:
            profile_link = os.path.relpath(custom_output, Path(custom_pointer).parent).replace(os.sep, '/')
            contents[custom_pointer] = '# Task writing profile\n\n[Use the adopted profile](' + profile_link + ').\n'
    lines = ['# Selected task operations', '', 'Use the selected contracts below, then read their complete common and specialist rule bodies. Run documentation command examples from this snapshot root.', '']
    if not final_operations:
        lines += ['Support input only: return these boundary or handoff resources to the existing result owner. Inherit the parent request, authority and progress. Do not start a new owner or native run; no execution policy manifest is generated.', '']
    lines += [f"- {op['skill_id']} / {op['mode']}: {op['operation']}" for op in operations]
    lines += ['', 'Included resources:', ''] + [f'- [{rid}]({os.path.relpath(output_paths[rid], Path(generated["ECON_INDEX.md"]).parent).replace(os.sep, "/")})' for rid in sorted(selected)]
    if custom:
        lines += ['', 'Task writing profile: [custom](' + os.path.relpath(custom_output, Path(generated['ECON_INDEX.md']).parent).replace(os.sep, '/') + '). Use --profile export-custom-profile with the native runner.']
    lines += ['', 'Optional resources are requested only when their function becomes necessary. See [optional inputs](OPTIONAL_INPUTS.md).']
    lines += ['', 'Operation contract:', '']
    for op in operations:
        lines += [f"- Selector: {op['requested_selector']}; owner: {op['owner_skill']}; canonical operation: {op['canonical_operation']}."]
        if op['default_input']:
            lines += [f"- Default input: {op['default_input']}."]
        if op['requested_section']:
            lines += [f"- Requested section: {op['requested_section']}."]
        if op.get('result_contract'):
            lines += ['- Inputs: ' + op['input_contract'], '- Result: ' + canonical(op['result_contract']), '- Finish: ' + op['finish']]
        else:
            lines += ['- Required outputs: ' + canonical(op['required_outputs']), '- Required actions: ' + canonical(op['required_actions'])]
    contents[generated['ECON_INDEX.md']] = '\n'.join(lines) + '\n'
    contents[generated['OPTIONAL_INPUTS.md']] = optional_inputs(omitted)
    def entry_at(filename):
        parent = Path(filename).parent
        links = [os.path.relpath(path, parent).replace(os.sep, '/')
                 for path in (output_paths['core'], output_paths['prose'], generated['ECON_INDEX.md'])]
        return entry_contract(routes, *links) + '\n'
    if generated['PROJECT_INSTRUCTIONS.txt'] not in contents:
        contents[generated['PROJECT_INSTRUCTIONS.txt']] = entry_at(generated['PROJECT_INSTRUCTIONS.txt'])
    if output_format == 'deployed':
        pointers = routes.get('placements', {}).get('policy_pointers', [])
        if 'repository-policy' in resources:
            pointers = pointers + [resources['repository-policy']]
        for pointer in pointers:
            filename = relative(pointer['deployment_path'])
            contents[filename] = '# Economics task entry\n\n' + entry_at(filename)
        instructions = resources.get('project-instructions', {}).get('deployment_path',
            (Path(declared_root) / 'docs/ai/project_instructions.txt').as_posix())
        contents[instructions] = entry_at(instructions)
    if len(contents[generated['PROJECT_INSTRUCTIONS.txt']].replace('\n', '\r\n')) > 8000:
        raise ValueError('Project instructions exceed 8,000 characters')
    if 'policy-manifest' in selected and final_operations:
        helper = resource_path(root, resources['policy-assets'], layout)
        spec = importlib.util.spec_from_file_location('export_policy_assets', helper)
        policy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(policy)
        manifest_output = output_paths['policy-manifest']
        # Registered deployment paths are relative to the exported project root,
        # even when the manifest itself is under .agents/quality.
        policy_root = '.'
        if output_format == 'deployed':
            catalog_path = output_paths['registry-placements']
            placement_catalog = json.loads(contents[catalog_path])
            for rid in selected:
                placement_catalog['resources'][rid]['deployment_path'] = output_paths[rid]
            contents[catalog_path] = json.dumps(placement_catalog, ensure_ascii=False, indent=2) + '\n'
        if custom:
            resource_catalog_path = output_paths['registry-resources']
            placement_catalog_path = output_paths['registry-placements']
            resource_catalog = json.loads(contents[resource_catalog_path])
            placement_catalog = json.loads(contents[placement_catalog_path])
            rid = 'export-custom-profile'
            if rid in resource_catalog['resources'] or rid in placement_catalog['resources']:
                raise ValueError('Reserved custom profile registry ID exists')
            resource_catalog['resources'][rid] = {
                'resource_id': rid, 'source_path': 'profiles/CUSTOM_STYLE.md',
                'resource_kind': 'profile', 'content_version': sha256(contents[custom_output].encode())}
            resource_catalog['sections'][rid] = {'all': {'whole_resource': True}}
            resource_catalog['rules'][rid + '.all'] = {
                'rule_id': rid + '.all', 'resource_id': rid, 'section_id': 'all',
                'requires': [], 'conditional_requires': [], 'optional_examples': []}
            placement_catalog['resources'][rid] = {
                'resource_id': rid, 'deployment_path': '.agents/profiles/CUSTOM_STYLE.md',
                'export_alias': 'CUSTOM_STYLE.md'}
            contents[resource_catalog_path] = json.dumps(resource_catalog, ensure_ascii=False, indent=2) + '\n'
            contents[placement_catalog_path] = json.dumps(placement_catalog, ensure_ascii=False, indent=2) + '\n'
        paths, assets = {}, {}
        if custom:
            paths['resource:export-custom-profile'] = os.path.relpath(custom_output, policy_root).replace(os.sep, '/')
            assets['resource:export-custom-profile'] = contents[custom_output].encode('utf-8')
        for rid in sorted(selected):
            destination = output_paths[rid]
            if rid == 'policy-manifest':
                continue
            logical = policy.resource_key(rid)
            paths[logical] = os.path.relpath(destination, policy_root).replace(os.sep, '/')
            assets[logical] = contents[destination].encode('utf-8')
        catalog = policy.build_manifest(assets, paths=paths)
        for operation in final_operations:
            policy.select_manifest(catalog, assets, operation['canonical_operation'],
                                   conditions=conditions, profile=('export-custom-profile' if custom and operation.get('selected_profile') else operation.get('selected_profile')))
        contents[manifest_output] = json.dumps(catalog, ensure_ascii=False, indent=2) + '\n'
    contexts = {}
    for rid in selected:
        rule_ids = [rule for op in operations + reference_required
                    for rule in op.get('active_rules', [])
                    if routes.get('rules', {}).get(rule, {}).get('resource_id') == rid]
        contexts[output_paths[rid]] = (
            f"source {resources[rid]['source_path']}; rules {', '.join(dict.fromkeys(rule_ids))}; "
            'operations ' + ', '.join(op['canonical_operation'] for op in operations))
    for entry in config['files']:
        contexts[entry['output']] = f"source {entry['path']}; operations " + ', '.join(op['canonical_operation'] for op in operations)
    if custom:
        contexts[custom_output] = 'source external-profile; operations ' + ', '.join(op['canonical_operation'] for op in operations)
    validate_required_bodies(routes, operations + reference_required, selections,
                             lambda rid: contents[output_paths[rid]])
    data_outputs = {output_paths[rid] for rid in selected if not prose_resource(resources[rid])}
    validate_internal_links({k: v for k, v in contents.items() if k not in knowledge_outputs},
                            contexts, data_outputs)
    # Validate all content before publishing the directory. No Git or network needed.
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.econ-export-', dir=target.parent))
    try:
        for name, text in contents.items():
            (temporary / name).parent.mkdir(parents=True, exist_ok=True)
            (temporary / name).write_bytes(text.encode('utf-8'))
        if target.exists() or target.is_symlink():
            raise ValueError('Output appeared while preparing export')
        publish_directory(temporary, target)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return len(contents)


def _prepare_distribution(root, routes=None):
    """Generate canonical entries and one shared policy catalog."""
    root = Path(root).resolve()
    validate_package_versions(root, required=True)
    routes = generate_entries(root, routes)
    spec = importlib.util.spec_from_file_location('distribution_policy', root / 'harness/policy_assets.py')
    policy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(policy)
    paths = {policy.resource_key(rid): record['source_path']
             for rid, record in routes['resources'].items()
             if rid != 'policy-manifest' and not record.get('source_distribution_only')}
    assets = {key: (root / path).read_bytes() for key, path in paths.items()}
    encoded = (json.dumps(policy.build_manifest(assets, paths=paths),
                          ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    manifest = root / routes['resources']['policy-manifest']['source_path']
    if not manifest.is_file() or manifest.read_bytes() != encoded:
        manifest.write_bytes(encoded)
    return routes


def export_plugin(target):
    """Publish one runtime accessible through the existing project-work Skill."""
    root, target = ROOT.resolve(), Path(target).absolute()
    validate_package_versions(root, required=True)
    if any(parent.is_symlink() for parent in target.parents):
        raise ValueError('Refuse symlink output ancestor')
    if target.exists() or target.is_symlink() or target.resolve().is_relative_to(root):
        raise ValueError('Choose a fresh output directory outside the source tree')
    routes = load_routes(root)
    resources = routes['resources']
    selected = {rid for rid, item in resources.items()
                if not item.get('source_distribution_only') and rid != 'policy-manifest'}
    owners = sorted({op['owner_skill'] for op in routes['operations']} | knowledge_owner_ids(routes))
    # Hosts discover SKILL.md recursively. Shared bodies are ordinary resources;
    # only the seven public entrances below should register as Skills.
    output_paths = {rid: (Path(item['source_path']).with_name('instructions.md').as_posix()
                          if rid in owners else item['source_path'])
                    for rid, item in resources.items()}
    relocated = {resources[rid]['source_path']: output_paths[rid] for rid in owners}
    paths = {item['source_path']: rid for rid, item in resources.items()}
    raw = {rid: resource_path(root, resources[rid]).read_bytes() for rid in selected}
    contents, omitted = {}, set()
    for rid in sorted(selected):
        name = resources[rid]['source_path']
        text = raw[rid].decode('utf-8')
        if prose_resource(resources[rid]):
            text = runtime_prose(rid, text)
            if re.fullmatch(r'skills/[^/]+/SKILL\.md', name):
                text = transform_entry_references(routes, rid, text)
            def destination(link):
                parts = urlsplit(link)
                if parts.scheme or parts.netloc or not parts.path:
                    return link
                path = os.path.normpath(str(Path(name).parent / unquote(parts.path))).replace(os.sep, '/')
                target_id = paths.get(path)
                if target_id is None:
                    raise ValueError('Unregistered plugin reference in ' + name + ': ' + link)
                if target_id in selected:
                    destination_path = os.path.relpath(output_paths[target_id], Path(output_paths[rid]).parent).replace(os.sep, '/')
                    return parts._replace(path=destination_path).geturl()
                title = target_id + ('--' + unquote(parts.fragment) if parts.fragment else '')
                omitted.add(title)
                return os.path.relpath('OPTIONAL_INPUTS.md', Path(name).parent).replace(os.sep, '/') + '#' + heading_id(title)
            text = rewrite_markdown(text, destination)
            text = rewrite_code_paths(text, relocated)
        contents[output_paths[rid]] = text
    resource_catalog_path = output_paths['registry-resources']
    resource_catalog = json.loads(contents[resource_catalog_path])
    for owner in owners:
        resource_catalog['resources'][owner]['source_path'] = output_paths[owner]
    contents[resource_catalog_path] = json.dumps(resource_catalog, ensure_ascii=False, indent=2) + '\n'
    contents['OPTIONAL_INPUTS.md'] = optional_inputs(omitted)
    operations = [resolve_operation(routes, op['id'], conditions=op['conditions'])
                  for op in routes['operations']]
    selections = {rid: {'whole_resource': True} for rid in selected}
    validate_required_bodies(routes, operations, selections,
                            lambda rid: contents[output_paths[rid]])
    base, knowledge = knowledge_assets(root, 'source')
    files = {name: body.encode('utf-8') for name, body in contents.items()}
    files.update({(base / name).as_posix(): data for name, data in knowledge.items()})
    spec = importlib.util.spec_from_file_location('plugin_policy', root / 'harness/policy_assets.py')
    policy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(policy)
    policy_paths = {policy.resource_key(rid): output_paths[rid] for rid in selected}
    policy_assets = {key: files[name] for key, name in policy_paths.items()}
    files[resources['policy-manifest']['source_path']] = (json.dumps(
        policy.build_manifest(policy_assets, paths=policy_paths), ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    # Cloud readers expose one Skill directory at a time. Keep the complete
    # runtime in one existing Skill so its rule text and executable bundle are
    # available through that same host interface.
    shared = Path('skills/project-work/references/shared')
    canonical_files = files
    files = {(shared / name).as_posix(): body for name, body in canonical_files.items()}
    linked_contents = {(shared / name).as_posix(): body for name, body in contents.items()}
    for owner in owners:
        name = resources[owner]['source_path']
        source = canonical_files[output_paths[owner]].decode('utf-8')
        if not source.startswith('---\n') or '\n---\n' not in source[4:]:
            raise ValueError('Skill entrance requires its canonical YAML frontmatter: ' + name)
        frontmatter = source[:source.index('\n---\n', 4) + 5]
        relative_body = os.path.relpath(shared / output_paths[owner], Path(name).parent).replace(os.sep, '/')
        relative_index = os.path.relpath(shared / 'docs/ai/compiled_ai_skills.md', Path(name).parent).replace(os.sep, '/')
        body = (frontmatter + '\n# ' + owner + '\n\n'
                + 'Read the complete [canonical Skill instructions](' + relative_body + ') and the selected rule bodies with their prerequisites under CORE. Use the [compact index](' + relative_index + ') when the operation or conditions remain unresolved; go directly to a known operation and retrieve its current stage with `route_registry.py read OPERATION --stage STAGE`. '
                + 'Keep `' + owner + '` as the operation owner while reading the shared package.\n\n'
                + 'For a cloud Skill reader, select the `project-work` package from this same plugin. '
                + 'Replace the final `SKILL.md` in its `main_resource` URI with `references/shared/' + output_paths[owner] + '` to read this body. '
                + 'Resolve its relative references within `references/shared/`; read CORE, the selected PROSE rules, operation/mode and activated dependencies in full. '
                + 'Reuse complete same-version text already in context.\n\n'
                + 'For execution, read that package\'s `bundle` resource, download and extract it once, and use its `references/shared/` directory as the runtime root. '
                + 'It contains the canonical scripts, references, templates and knowledge collection for all seven Skills. '
                + 'A materialized plugin uses the linked directory directly.\n')
        files[name] = body.encode('utf-8')
        linked_contents[name] = body
    validate_internal_links(linked_contents, non_prose={
        (shared / output_paths[rid]).as_posix() for rid in selected
        if not prose_resource(resources[rid])})
    for name in ('plugin.json', '.codex-plugin/plugin.json'):
        files[name] = (root / name).read_bytes()
    for entry in sorted((root / 'skills').glob('*/agents/openai.yaml')):
        files[entry.relative_to(root).as_posix()] = entry.read_bytes()
    files['hooks/hooks.json'] = canonical_files['hooks/hooks.json']
    files['hooks/check.py'] = (
        '#!/usr/bin/env python3\n'
        '"""Run the canonical hook in the shared Skill runtime."""\n'
        'from pathlib import Path\n'
        'import runpy\n\n'
        'runpy.run_path(str(Path(__file__).resolve().parents[1] / '
        + repr((shared / 'hooks/check.py').as_posix()) + '), run_name="__main__")\n').encode('utf-8')
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.' + target.name + '-', dir=target.parent))
    try:
        for name, data in files.items():
            output = staging / name
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(data)
            source = root / (Path(name).relative_to(shared) if Path(name).is_relative_to(shared) else name)
            if source.is_file():
                shutil.copymode(source, output)
        publish_directory(staging, target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return len(files)


def generate_distribution(root):
    """Serialize regeneration of the canonical instruction outputs."""
    validate_package_versions(root, required=True)
    from sync_common_core import runtime_io
    root = Path(root).resolve()
    identity = hashlib.sha256(str(root).encode('utf-8')).hexdigest()
    path = root.parent / ('.econ-generation-lock-' + identity)
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        try:
            runtime_io().lock_fd(fd)
        except BlockingIOError as exc:
            raise ValueError('Distribution generation is already running: ' + str(root)) from exc
        return _generate_distribution(root)
    finally:
        os.close(fd)


def _generate_distribution(root):
    """Generate against fixed inputs; preserve concurrent edits during publication."""
    from sync_common_core import tree_records, same_tree
    root = Path(root).resolve()
    validate_package_versions(root, required=True)
    routes = load_routes(root)
    owners = sorted({op['owner_skill'] for op in routes['operations']} | knowledge_owner_ids(routes))
    targets = [Path(name) for name in (
        'docs/ai/compiled_ai_skills.md', 'docs/ai/resources.md',
        'docs/ai/project_instructions.txt', 'skills/econ-writing/agents/openai.yaml')]
    targets += [Path(pointer['source_path']) for pointer in routes['placements']['policy_pointers']]
    targets += [Path(routes['resources'][owner]['source_path']) for owner in owners]
    targets += [Path(resource['source_path']) for resource in routes['resources'].values()
                if resource.get('reading_index')]
    # Publish the catalog after every entry it identifies.
    targets.append(Path('quality/policy_manifest.json'))
    targets = list(dict.fromkeys(targets))
    source_paths = {Path(record['source_path']) for record in routes['resources'].values()
                    if not record.get('source_distribution_only')}
    source_paths.update(Path(name) for name in ('plugin.json', '.codex-plugin/plugin.json'))
    source_paths.update(targets)
    scope = sorted(source_paths | set(targets))
    def snapshot():
        records = {}
        for path in scope:
            prefix = path.as_posix()
            records.update({prefix + ('' if name == '.' else '/' + name): state
                            for name, state in tree_records(root / path).items()})
        return records
    initial = snapshot()
    temporary = Path(tempfile.mkdtemp(prefix='.econ-distribution-', dir=root.parent))
    staging, backup = temporary / 'staging', temporary / 'backup'
    retain_backup = False
    def remove(path):
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        elif path.exists() or path.is_symlink():
            path.unlink()
    def verify(expected):
        current = snapshot()
        if not same_tree(current, expected):
            changed = sorted(key for key in current.keys() | expected.keys()
                             if current.get(key) != expected.get(key))
            raise ValueError('Distribution inputs changed: ' + ', '.join(changed))
    try:
        staging.mkdir()
        for path in sorted(source_paths):
            source = root / path
            if source.is_symlink():
                raise ValueError('Distribution input must be a regular file: ' + path.as_posix())
            if source.is_file():
                destination = staging / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
        prepared = _prepare_distribution(staging, routes)
        expected = dict(initial)
        verify(expected)
        committed = []
        try:
            for relative_path in targets:
                destination, staged = root / relative_path, staging / relative_path
                saved = backup / relative_path
                before, desired = tree_records(destination), tree_records(staged)
                prefix = relative_path.as_posix()
                expected_target = {('.' if name == prefix else name[len(prefix) + 1:]): state
                                   for name, state in expected.items()
                                   if name == prefix or name.startswith(prefix + '/')}
                if not same_tree(before, expected_target):
                    raise ValueError('Distribution target changed: ' + prefix)
                if same_tree(before, desired):
                    continue
                existed = bool(before)
                saved.parent.mkdir(parents=True, exist_ok=True)
                destination.parent.mkdir(parents=True, exist_ok=True)
                row = {'destination': destination, 'saved': saved, 'existed': existed,
                       'desired': desired, 'published': False}
                committed.append(row)
                if existed:
                    shutil.copy2(destination, saved)
                    if not same_tree(tree_records(saved), before):
                        raise ValueError('Distribution target changed during backup: ' + str(relative_path))
                if not same_tree(tree_records(destination), before):
                    raise ValueError('Distribution target changed before replacement: ' + str(relative_path))
                os.replace(staged, destination)
                row['published'] = True
                expected = {name: state for name, state in expected.items()
                            if name != prefix and not name.startswith(prefix + '/')}
                expected.update({prefix + ('' if name == '.' else '/' + name): state
                                 for name, state in desired.items()})
                if existed and not same_tree(tree_records(saved), before):
                    raise ValueError('Saved distribution input changed: ' + str(relative_path))
            # One final input comparison covers the whole generation. Each
            # changed target was checked immediately before its replacement.
            verify(expected)
        except BaseException as error:
            conflicts = []
            for row in reversed(committed):
                destination, saved = row['destination'], row['saved']
                current = tree_records(destination)
                own = row['published'] and same_tree(current, row['desired'])
                if saved.exists() or saved.is_symlink():
                    if not current or own:
                        remove(destination)
                        os.replace(saved, destination)
                    else:
                        conflicts.append(str(destination.relative_to(root)))
                        retain_backup = True
                elif not row['existed'] and own:
                    remove(destination)
            if conflicts:
                raise ValueError('Concurrent distribution edits retained: ' + ', '.join(conflicts)
                                 + '; backup retained at ' + str(backup)) from error
            raise
        return prepared
    finally:
        if not retain_backup:
            shutil.rmtree(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=['standalone'], default='standalone')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--format', dest='output_format', choices=['flat', 'deployed', 'plugin'], default='flat')
    parser.add_argument('--layout', choices=['source', 'installed'], default='source')
    select = parser.add_mutually_exclusive_group()
    select.add_argument('--task')
    select.add_argument('--skills', nargs='+')
    parser.add_argument('--mode')
    parser.add_argument('--support', action='append', default=[])
    parser.add_argument('--condition', action='append', default=[])
    parser.add_argument('--references', action='append', default=[])
    parser.add_argument('--knowledge-id', action='append', default=[], help='Export the selected knowledge ID and its required prerequisites')
    parser.add_argument('--style-profile')
    parser.add_argument('--generate-index', type=Path)
    parser.add_argument('--generate-entries', action='store_true')
    args = parser.parse_args()
    try:
        if args.generate_entries:
            generate_distribution(ROOT)
            return
        if args.generate_index:
            args.generate_index.write_text(native_index(load_routes(ROOT), links=True), encoding='utf-8')
            return
        if not args.output:
            parser.error('--output is required')
        if args.output_format == 'plugin':
            if any((args.task, args.skills, args.support, args.references, args.style_profile,
                    args.mode, args.condition, args.knowledge_id)) or args.layout != 'source':
                parser.error('Plugin output uses the complete canonical source distribution')
            count = export_plugin(args.output)
        else:
            count = export(args.output, args.profile, args.skills, task=args.task, support=args.support, references=args.references, style_profile=args.style_profile, mode=args.mode, conditions=args.condition, layout=args.layout, output_format=args.output_format, knowledge_ids=args.knowledge_id)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, f'Export: {error}\n')
    print(f'Exported {count} files to {args.output}')


if __name__ == '__main__':
    main()
