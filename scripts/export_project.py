#!/usr/bin/env python3
"""Export a route-selected, content-addressed standalone instruction package."""
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
from route_registry import load_routes, resource_path, resolve_operation, native_index, relative, merge_selection, rule_selection, required_closure, generate_entries, validate_rule_bodies, markdown_sections, heading_id, transform_entry_references, inline_code_mask
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


def extract_sections(text, selection, resource):
    if selection.get('whole_resource'):
        return text
    lines, headings = markdown_sections(text)
    included = set()
    if selection.get('sections') and lines and lines[0].strip() == '---':
        closing = next((i for i in range(1, len(lines)) if lines[i].strip() in ('---', '...')), None)
        if closing is not None:
            included.update(range(closing + 1))
    for section in selection.get('sections', []):
        matches = [h for h in headings if section in (h['title'], h['id'], '#' + h['id'])]
        if len(matches) != 1:
            raise ValueError(f'Missing or ambiguous section: {resource} / {section}')
        included.update(range(matches[0]['start'], matches[0]['end']))
    return ''.join(line for i, line in enumerate(lines) if i in included)


def validate_required_bodies(routes, operations, selections, read_resource):
    """Check registered rule bodies against the exact selected package text."""
    resources = routes['resources']
    required_selections = {}
    # This invocation verifies one immutable package snapshot. Reuse its bytes
    # and completed rule checks across operations, never across snapshots.
    texts, verified, checked_scopes = {}, set(), set()
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
                    source_text = read_snapshot(rid)
                    scope = (rid, bool(rule_scope.get('whole_resource')), tuple(rule_scope.get('sections', [])))
                    if scope not in checked_scopes:
                        extract_sections(source_text, rule_scope, resources[rid]['source_path'])
                        checked_scopes.add(scope)
                    if rid not in selections or (rule_scope.get('whole_resource') and not selections[rid].get('whole_resource')):
                        raise ValueError('required body is absent from the selected snapshot')
                    if not selections[rid].get('whole_resource') and not set(rule_scope.get('sections', [])) <= set(selections[rid].get('sections', [])):
                        raise ValueError('required section is absent from the selected snapshot')
                except (OSError, ValueError) as error:
                    raise ValueError(f'Missing required rule {rule_id}; operation {operation["canonical_operation"]}; source {resources[rid]["source_path"]}: {error}') from error
    return required_selections


def validate_internal_links(contents, contexts=None):
    """Check local file and anchor targets without rewriting or optionalizing them."""
    contexts = contexts or {}
    for name, text in contents.items():
        if name == 'SOURCE.md' or name.endswith(('.py', '.sh', '.json', '.yaml')):
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


def export(target, profile='standalone', skills=None, *, task=None, support=(), references=(), style_profile=None, mode=None, conditions=(), layout='source', output_format='flat'):
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
    if effective_profile and effective_profile != 'default-micro':
        custom = Path(effective_profile)
        custom = custom if custom.is_absolute() else root / relative(effective_profile)
        if not custom.is_file() or custom.is_symlink():
            raise ValueError('Custom profile must be a regular file')
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
            active, dependency_selection = required_closure(routes, [matches[0] + '.all'], conditions, 'reference:' + value)
            merge_selection(selections, dependency_selection)
            reference_required.append({'canonical_operation': 'reference:' + value, 'active_rules': active})
    while True:
        before = canonical(selections)
        for rid, selection in list(selections.items()):
            res = resources[rid]
            merge_selection(selections, {dep: {'whole_resource': True} for dep in res.get('required_resources', [])})
            merge_selection(selections, res.get('required_resource_sections', {}))
            for section in selection.get('sections', []):
                merge_selection(selections, res.get('section_dependencies', {}).get(section, {}))
        if before == canonical(selections):
            break
    # Catalog availability is distinct from each run's adopted dependency closure.
    if final_operations and 'policy-manifest' in selections and 'team-state-helper' in resources:
        merge_selection(selections, {'team-state-helper': {'whole_resource': True}})
    selected = set(selections)
    unsupported = sorted(rid for rid in selected if resources[rid].get('snapshot') == 'source_distribution_only')
    if unsupported:
        raise ValueError('Use complete source distribution for maintenance tools; cannot publish an executable flat/deployed snapshot for: ' + ', '.join(unsupported))
    output_paths = {rid: res['export_alias' if output_format == 'flat' else 'deployment_path'] for rid, res in resources.items()}
    if 'policy-manifest' in selected and final_operations:
        # A manifest is rooted at the common containing directory of all its
        # assets. Repository documents and policy pointers may sit above .agents.
        containing = Path(os.path.commonpath([str(Path(output_paths[rid]).parent)
                          for rid in selected if rid != 'policy-manifest']))
        previous = Path(output_paths['policy-manifest'])
        output_paths['policy-manifest'] = (containing / previous.parent.name / previous.name).as_posix()
    # Both physical layouts use the exact same resolved selections.
    # All logical paths resolve through this registry in either physical layout.
    path_ids = {}
    def register_path(path, rid):
        # Do not let a symlink in an unused bundle alias register an outside path.
        previous = path_ids.setdefault(path.absolute(), rid)
        if previous != rid:
            raise ValueError(f'Ambiguous registered resource path: {path}')

    for rid, res in resources.items():
        for key in ('source_path', 'deployment_path'):
            register_path(root / res[key], rid)
    # Public plugin entrypoints retain package-relative links when exported from
    # either a source distribution or an installed tree. Bind only exact aliases
    # of registered resources; never strip an arbitrary bundle prefix from links.
    entrypoints = [res for res in resources.values()
                   if re.fullmatch(r'skills/[^/]+/SKILL\.md', res['source_path'])]
    for entry in entrypoints:
        for key in ('source_path', 'deployment_path'):
            bundle = (root / entry[key]).parent / 'references/bundle'
            for rid, res in resources.items():
                bundled_path = Path(res['source_path'])
                if re.fullmatch(r'skills/[^/]+/SKILL\.md', res['source_path']):
                    bundled_path = bundled_path.with_name('REFERENCE.md')
                register_path(bundle / bundled_path, rid)
    generated = {'ECON_INDEX.md', 'SOURCE.md', 'OPTIONAL_INPUTS.md', 'PROJECT_INSTRUCTIONS.txt'}
    aliases = {output_paths[rid]: rid for rid in selected}
    if {name.casefold() for name in aliases} & {name.casefold() for name in generated}:
        # The instruction template is rendered below if declared as a resource.
        collisions = {name.casefold() for name in aliases} & {name.casefold() for name in generated - {'PROJECT_INSTRUCTIONS.txt'}}
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
        if '/' in name or name.casefold() in {n.casefold() for n in (*aliases, *generated, *project_aliases.values(), 'CUSTOM_STYLE.md')}:
            raise ValueError('Project file output collision or non-flat alias')
        project_aliases[(root / relative(entry['path'])).resolve()] = name
    omitted = set()
    generated_sources = {(root / name).absolute(): name for name in generated
                         if (root / name).is_file() and not (root / name).is_symlink()}
    optional_source = root / 'OPTIONAL_INPUTS.md'
    previous_optional = ({h['id']: h['title'] for h in markdown_sections(optional_source.read_text(encoding='utf-8'))[1]}
                         if optional_source.absolute() in generated_sources else {})
    def destination(source, link, output='ECON_INDEX.md'):
        def local(path):
            return os.path.relpath(path, str(Path(output).parent)).replace(os.sep, '/')
        parts = urlsplit(link)
        if parts.scheme or link.startswith('//'):
            return link
        clean = unquote(parts.path)
        suffix = '#' + parts.fragment if parts.fragment else ''
        if clean in generated or (custom and clean == 'CUSTOM_STYLE.md'):
            return local(clean) + suffix
        path = ((root / clean.lstrip('/') if clean.startswith('/') else source.parent / clean) if clean else source).resolve()
        if path in generated_sources:
            name = generated_sources[path]
            if name == 'OPTIONAL_INPUTS.md' and parts.fragment:
                title = previous_optional.get(unquote(parts.fragment))
                owners = [rid for rid in resources if title == rid or isinstance(title, str) and title.startswith(rid + '--')]
                if len(owners) != 1:
                    raise ValueError('Unregistered generated optional reference: ' + link)
                rid = owners[0]
                section = title[len(rid) + 2:] if title != rid else None
                if rid in selected and (section is None or section in active_anchors[rid]):
                    return local(output_paths[rid]) + ('#' + section if section else '')
                omitted.add(title)
            return local(name) + suffix
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
            return local('ECON_INDEX.md')
        if rid in selected:
            if parts.fragment and unquote(parts.fragment) not in active_anchors[rid]:
                if required_selections.get(rid, {}).get('whole_resource'):
                    raise ValueError(f'Missing section in required resource {rid}: {link}; source {source}')
                if unquote(parts.fragment) not in {h['id'] for h in markdown_sections(raw[rid].decode('utf-8'))[1]}:
                    raise ValueError(f'Missing source section in {source}: {link}; operations ' +
                                     ', '.join(op['canonical_operation'] for op in operations))
                optional_section = rid + '--' + unquote(parts.fragment)
                omitted.add(optional_section)
                return local('OPTIONAL_INPUTS.md') + '#' + heading_id(optional_section)
            return local(output_paths[rid]) + suffix
        if rid:
            omitted.add(rid)
            return local('OPTIONAL_INPUTS.md') + '#' + heading_id(rid)
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
    records = []
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
            records.append({'logical_id': rid, 'source': res['source_path'], 'resolved_path': res['source_path' if layout == 'source' else 'deployment_path'], 'output': output_paths[rid], 'selection': selections[rid], 'source_sha256': sha256(raw[rid]), 'export_sha256': sha256(raw[rid])})
            continue
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
        records.append({'logical_id': rid, 'source': res['source_path'], 'resolved_path': res['source_path' if layout == 'source' else 'deployment_path'], 'output': output_paths[rid], 'selection': selections[rid], 'source_sha256': sha256(raw[rid]), 'export_sha256': sha256(text.encode())})
    for entry in config['files']:
        if set(entry) != {'path', 'output'}:
            raise ValueError('Project file requires path and output')
        filename = relative(entry['output'])
        if '/' in filename or filename.casefold() in {name.casefold() for name in (*contents, *generated, 'CUSTOM_STYLE.md')}:
            raise ValueError('Project file output collision or non-flat alias')
        source = root / relative(entry['path'])
        if source.is_symlink() or not source.resolve().is_relative_to(root):
            raise ValueError('Project file escapes repository')
        data = source.read_bytes()
        text = rewrite_markdown(data.decode(), lambda link: destination(source, link))
        contents[filename] = text
        records.append({'logical_id': 'project:' + entry['path'], 'source': entry['path'], 'output': filename, 'source_sha256': sha256(data), 'export_sha256': sha256(text.encode())})
    custom_output = ('.agents/profiles/CUSTOM_STYLE.md'
                     if custom and 'policy-manifest' in selected and output_format == 'deployed'
                     else 'CUSTOM_STYLE.md')
    if custom:
        data = custom.read_bytes()
        text = rewrite_markdown(data.decode(), lambda link: destination(custom, link, custom_output))
        contents[custom_output] = text
        if custom_output != 'CUSTOM_STYLE.md':
            contents['CUSTOM_STYLE.md'] = '# Task writing profile\n\n[Use the adopted profile](' + custom_output + ').\n'
        records.append({'logical_id': 'profile.custom', 'source': 'external-profile', 'output': custom_output, 'source_sha256': sha256(data), 'export_sha256': sha256(text.encode())})
    lines = ['# Selected task operations', '', 'Read the included common rules once. Support inherits this task and returns to its owner. Run documentation command examples from this snapshot root.', '']
    if not final_operations:
        lines += ['Support input only: return these boundary or handoff resources to the existing result owner. Inherit the parent request, authority and progress. Do not start a new owner or native run; no execution policy manifest is generated.', '']
    lines += [f"- {op['skill_id']} / {op['mode']}: {op['operation']}" for op in operations]
    lines += ['', 'Included resources:', ''] + [f'- [{rid}]({output_paths[rid]})' for rid in sorted(selected)]
    if custom:
        lines += ['', 'Task writing profile: [custom](' + custom_output + '). Use --profile export-custom-profile with the native runner.']
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
    contents['ECON_INDEX.md'] = '\n'.join(lines) + '\n'
    contents['OPTIONAL_INPUTS.md'] = '# Optional inputs\n\nThese functions are inactive in this snapshot. If needed, request the named input or regenerate the snapshot with its condition/reference. Do not retrieve an external repository automatically.\n\n' + '\n'.join('## ' + rid + '\n\nRequired additional input: ' + rid + '.\n' for rid in sorted(omitted))
    if 'PROJECT_INSTRUCTIONS.txt' not in contents:
        contents['PROJECT_INSTRUCTIONS.txt'] = 'Read the included CORE and PROSE bodies, then follow ECON_INDEX.md for the selected operation and its required rules. Reuse same-version reads. Complete reasoning, execution, integrated review and applicable verification under CORE. SOURCE.md identifies this content snapshot. Request optional inputs when their function is needed.\n'
    if output_format == 'deployed':
        pointers = routes.get('placements', {}).get('policy_pointers', [])
        if 'repository-policy' in resources:
            pointers = pointers + [resources['repository-policy']]
        for pointer in pointers:
            filename = relative(pointer['deployment_path'])
            parent = str(Path(filename).parent)
            core_link = os.path.relpath(output_paths['core'], parent).replace(os.sep, '/')
            prose_entry = (', [PROSE](' + os.path.relpath(output_paths['prose'], parent).replace(os.sep, '/') + ')'
                           if 'prose' in selected else '')
            index_link = os.path.relpath('ECON_INDEX.md', parent).replace(os.sep, '/')
            contents[filename] = f'# Economics task entry\n\nRead [CORE]({core_link}){prose_entry} and the [selected operation]({index_link}) with its required rule bodies and activated dependencies. Reuse same-version reads. Complete reasoning, execution, integrated review and applicable verification under CORE.\n'
        instructions = resources.get('project-instructions', {}).get('deployment_path', 'docs/ai/project_instructions.txt')
        contents[instructions] = 'Follow ' + os.path.relpath('ECON_INDEX.md', str(Path(instructions).parent)).replace(os.sep, '/') + ' and read the included CORE, PROSE, selected skill/mode and required rule bodies. Complete CORE’s reasoning, execution, integrated review and applicable verification.\n'
    if len(contents['PROJECT_INSTRUCTIONS.txt'].replace('\n', '\r\n')) > 8000:
        raise ValueError('Project instructions exceed 8,000 characters')
    if 'policy-manifest' in selected and final_operations:
        helper = resource_path(root, resources['policy-assets'], layout)
        spec = importlib.util.spec_from_file_location('export_policy_assets', helper)
        policy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(policy)
        manifest_output = output_paths['policy-manifest']
        policy_root = (str(Path(manifest_output).parent.parent)
                       if Path(manifest_output).parent.name == 'quality' else '.')
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
    for record in records:
        record['export_sha256'] = sha256(contents[record['output']].encode())
    registry_paths = routes.get('registry_source_paths')
    if registry_paths:
        prefix = '' if layout == 'source' else '.agents/'
        route_hash = sha256(canonical({name: sha256((root / (prefix + name)).read_bytes()) for name in registry_paths}).encode())
    else:
        route_hash = sha256((root / ('runtime/ROUTES.yaml' if layout == 'source' else '.agents/runtime/ROUTES.yaml')).read_bytes())
    implementation_hashes = {name: sha256((Path(__file__).parent / name).read_bytes()) for name in ('export_project.py', 'route_registry.py')}
    identity = {'implementation_sha256': implementation_hashes, 'routes_sha256': route_hash, 'project_config_sha256': sha256(context_raw), 'operations': operations, 'conditions': sorted(set(conditions)), 'files': records}
    manifest = {'schema_version': 2, 'snapshot_id': sha256(canonical(identity).encode()), **identity, 'layout': layout, 'output_format': output_format, 'omitted_optional_resources': sorted(omitted)}
    manifest['generated_files'] = [{'output': name, 'export_sha256': sha256(text.encode())} for name, text in sorted(contents.items()) if name not in {r['output'] for r in records}]
    contents['SOURCE.md'] = '# Source snapshot\n\n```json\n' + json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + '\n```\n'
    contexts = {}
    for record in records:
        rid = record['logical_id']
        rule_ids = [rule for op in operations + reference_required
                    for rule in op.get('active_rules', [])
                    if routes.get('rules', {}).get(rule, {}).get('resource_id') == rid]
        contexts[record['output']] = (
            f"source {record['source']}; rules {', '.join(dict.fromkeys(rule_ids))}; "
            "operations " + ', '.join(op['canonical_operation'] for op in operations))
    validate_required_bodies(routes, operations + reference_required, selections,
                             lambda rid: contents[output_paths[rid]])
    validate_internal_links(contents, contexts)
    # Validate all content before publishing the directory. No Git or network needed.
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.econ-export-', dir=target.parent))
    try:
        for name, text in contents.items():
            (temporary / name).parent.mkdir(parents=True, exist_ok=True)
            (temporary / name).write_text(text, encoding='utf-8')
        if target.exists() or target.is_symlink():
            raise ValueError('Output appeared while preparing export')
        publish_directory(temporary, target)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return len(contents)


def _prepare_distribution(root):
    """Build and verify a complete distribution in a disposable staging tree."""
    root = Path(root).resolve()
    validate_package_versions(root, required=True)
    routes = generate_entries(root)
    operations = [resolve_operation(routes, op['id'],
                  conditions=list(routes['condition_definitions']))
                  for op in routes['operations']]
    selections = {rid: {'whole_resource': True} for rid, record in routes['resources'].items()
                  if not record.get('source_distribution_only')}
    spec = importlib.util.spec_from_file_location('distribution_policy', root / 'harness/policy_assets.py')
    policy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(policy)
    manifest_path = root / 'quality/policy_manifest.json'
    manifest_path.write_text(json.dumps(policy.generate_manifest(root), ensure_ascii=False, indent=2) + '\n')
    validate_required_bodies(routes, operations, selections,
        lambda rid: resource_path(root, routes['resources'][rid], 'source').read_text(encoding='utf-8'))
    resources = routes['resources']
    runtime = {rid: record for rid, record in resources.items()
               if not record.get('source_distribution_only') and rid != 'policy-manifest'}
    placements = {record['source_path']: (record['source_path'][:-len('SKILL.md')] + 'REFERENCE.md'
                  if re.fullmatch(r'skills/[^/]+/SKILL\.md', record['source_path']) else record['source_path'])
                  for record in resources.values()}
    bundle_aliases = {}
    for owner in {operation['owner_skill'] for operation in routes['operations']}:
        prefix = str(Path(resources[owner]['source_path']).parent / 'references/bundle') + '/'
        for source_path, target_path in placements.items():
            bundle_aliases[prefix + source_path] = target_path
            bundle_aliases[prefix + target_path] = target_path
    for owner in sorted({operation['owner_skill'] for operation in routes['operations']}):
        bundle = (root / resources[owner]['source_path']).parent / 'references/bundle'
        if bundle.exists():
            shutil.rmtree(bundle)
        bundle.mkdir(parents=True)
        for rid, record in runtime.items():
            source = root / record['source_path']
            output = bundle / placements[record['source_path']]
            output.parent.mkdir(parents=True, exist_ok=True)
            data = source.read_bytes()
            if prose_resource(record):
                body = data.decode('utf-8')
                if re.fullmatch(r'skills/[^/]+/SKILL\.md', record['source_path']):
                    start = body.find('## Read packaged resources\n')
                    end = body.find('\n# ', start)
                    if start >= 0 and end >= 0:
                        body = body[:start] + body[end + 1:]
                    body = transform_entry_references(routes, rid, body, 'source')
                def destination(link):
                    parts = urlsplit(link)
                    if parts.scheme or link.startswith('//'):
                        return link
                    original = (source.parent / unquote(parts.path)).resolve() if parts.path else source
                    try:
                        key = original.relative_to(root).as_posix()
                    except ValueError:
                        raise ValueError('Bundle link escapes source: ' + link)
                    target = bundle_aliases.get(key, placements.get(key, key))
                    return os.path.relpath(bundle / target, output.parent).replace(os.sep, '/') + ('#' + parts.fragment if parts.fragment else '')
                body = rewrite_markdown(body, destination)
                body = rewrite_code_paths(body, placements)
                data = body.encode('utf-8')
            output.write_bytes(data)
        registry_path = bundle / 'registry/resources.json'
        registry = json.loads(registry_path.read_text())
        for record in registry['resources'].values():
            record['source_path'] = placements[record['source_path']]
            record['package_path'] = 'references/bundle/' + record['source_path']
        registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + '\n')
        manifest_path = bundle / 'quality/policy_manifest.json'
        manifest_path.write_text(json.dumps(policy.generate_manifest(bundle), ensure_ascii=False, indent=2) + '\n')
        # Validate the staged bytes, not the previously published bundles.
        bundled_routes = load_routes(bundle)
        validate_required_bodies(bundled_routes, operations, selections,
            lambda rid: (bundle / placements[resources[rid]['source_path']]).read_text(encoding='utf-8'))
        contents = {p.relative_to(bundle).as_posix(): p.read_text(encoding='utf-8')
                    for p in bundle.rglob('*') if p.is_file()}
        contexts = {}
        for rid, record in runtime.items():
            rules = [rule for rule, definition in routes['rules'].items()
                     if definition['resource_id'] == rid]
            origins = [op['canonical_operation'] for op in operations
                       if set(rules) & set(op['active_rules'])]
            contexts[placements[record['source_path']]] = (
                f"source {record['source_path']}; rules {', '.join(rules)}; "
                f"operations {', '.join(origins)}")
        validate_internal_links(contents, contexts)
        policy.verify_manifest(bundle)
    # Each advertised skill must read its own bundled rules through the host's
    # package-scoped reader. Repository synchronization restores source links.
    for owner in sorted({operation['owner_skill'] for operation in routes['operations']}):
        entry = root / resources[owner]['source_path']
        entry.write_text(transform_entry_references(routes, owner,
            entry.read_text(encoding='utf-8'), 'plugin'), encoding='utf-8')
    manifest_path = root / 'quality/policy_manifest.json'
    manifest_path.write_text(json.dumps(policy.generate_manifest(root), ensure_ascii=False, indent=2) + '\n')
    # This operation authored the source-layout manifest above. A repository can
    # also retain a deployed .agents tree with its own independently pinned map.
    policy.verify_manifest(root, policy.parse(policy.regular_bytes(root / 'quality/policy_manifest.json')))
    return routes


def _distribution_record(temporary, record):
    """Persist the pending ownership record before retiring any target."""
    path = temporary / 'journal.json'
    fd, name = tempfile.mkstemp(prefix='.journal-', dir=temporary)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(record, handle, sort_keys=True, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        from sync_common_core import runtime_io
        runtime_io().replace_path(name, path)
        runtime_io().sync_directory(temporary)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _recover_distribution(root):
    from sync_common_core import tree_records, same_tree, checked_path
    recovered = []
    for temporary in sorted(root.parent.glob('.econ-distribution-*')):
        journal = temporary / 'journal.json'
        if temporary.is_symlink() or not journal.is_file() or journal.is_symlink():
            continue
        record = json.loads(journal.read_text(encoding='utf-8'))
        if record.get('root') != str(root):
            continue
        if (set(record) != {'schema_version', 'root', 'status', 'entries'}
                or type(record['schema_version']) is not int or record['schema_version'] != 1
                or record['status'] not in ('preparing', 'publishing', 'complete')
                or not isinstance(record['entries'], list)):
            raise ValueError('Invalid pending distribution journal: ' + str(journal))
        conflicts = []
        for entry in reversed(record['entries'] if record['status'] != 'complete' else []):
            if (not isinstance(entry, dict) or set(entry) != {'path', 'existed', 'before', 'desired'}
                    or type(entry['existed']) is not bool or not isinstance(entry['before'], dict)
                    or not isinstance(entry['desired'], dict)):
                raise ValueError('Invalid pending distribution target: ' + str(journal))
            relative = checked_path(entry['path'])
            destination, saved = root / relative, temporary / 'backup' / relative
            if any(parent.is_symlink() for parent in (*destination.parents, *saved.parents)):
                raise ValueError('Pending distribution symlink parent: ' + relative)
            current = tree_records(destination)
            if saved.exists() or saved.is_symlink():
                if current and not same_tree(current, entry['desired']):
                    conflicts.append(relative)
                    continue
                if destination.is_dir() and not destination.is_symlink():
                    shutil.rmtree(destination)
                elif destination.exists() or destination.is_symlink():
                    destination.unlink()
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(saved, destination)
                recovered.append(relative)
            elif entry['existed']:
                if not same_tree(current, entry['before']):
                    conflicts.append(relative)
            elif current:
                if same_tree(current, entry['desired']):
                    if destination.is_dir() and not destination.is_symlink():
                        shutil.rmtree(destination)
                    else:
                        destination.unlink()
                else:
                    conflicts.append(relative)
        if conflicts:
            raise ValueError('Concurrent distribution edits retained: ' + ', '.join(conflicts)
                             + '; pending backup: ' + str(temporary / 'backup'))
        shutil.rmtree(temporary)
    return recovered


def generate_distribution(root):
    """Serialize publication and recover the same interrupted generation first."""
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
        _recover_distribution(root)
        return _generate_distribution(root)
    finally:
        os.close(fd)


def _generate_distribution(root):
    """Generate against fixed inputs; preserve concurrent edits during publication."""
    from sync_common_core import tree_records, same_tree
    root = Path(root).resolve()
    validate_package_versions(root, required=True)
    initial = tree_records(root)
    routes = load_routes(root)
    owners = sorted({op['owner_skill'] for op in routes['operations']})
    targets = [Path(name) for name in (
        'runtime/CORE.md', 'runtime/CONTROL.md', 'runtime/TEAM.md',
        'runtime/EXECUTION.md', 'runtime/PROSE.md', 'README.md',
        'docs/ai/compiled_ai_skills.md', 'docs/ai/resources.md',
        'docs/ai/project_instructions.txt', 'skills/econ-writing/agents/openai.yaml',
        'quality/policy_manifest.json', 'harness/local_checks.py')]
    targets += [Path(pointer['source_path']) for pointer in routes['placements']['policy_pointers']]
    targets += [Path(routes['resources'][owner]['source_path']) for owner in owners]
    targets += [Path(routes['resources'][owner]['source_path']).parent / 'references/bundle'
                for owner in owners]
    targets = list(dict.fromkeys(targets))
    temporary = Path(tempfile.mkdtemp(prefix='.econ-distribution-', dir=root.parent))
    staging, backup = temporary / 'staging', temporary / 'backup'
    retain_backup = False
    journal = {'schema_version': 1, 'root': str(root), 'status': 'preparing', 'entries': []}
    _distribution_record(temporary, journal)
    def remove(path):
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        elif path.exists() or path.is_symlink():
            path.unlink()
    def verify(expected):
        current = tree_records(root)
        if not same_tree(current, expected):
            changed = sorted(key for key in current.keys() | expected.keys()
                             if current.get(key) != expected.get(key))
            raise ValueError('Distribution inputs changed: ' + ', '.join(changed))
    try:
        shutil.copytree(root, staging, symlinks=True,
                        ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc'))
        prepared = _prepare_distribution(staging)
        expected = dict(initial)
        verify(expected)
        committed = []
        journal['status'] = 'publishing'
        _distribution_record(temporary, journal)
        try:
            for relative_path in targets:
                verify(expected)
                destination, staged = root / relative_path, staging / relative_path
                saved = backup / relative_path
                before, desired = tree_records(destination), tree_records(staged)
                existed = bool(before)
                saved.parent.mkdir(parents=True, exist_ok=True)
                # Adopt only directories created here, retaining every other
                # expected input so concurrent changes still fail verification.
                for parent in reversed(relative_path.parents):
                    name = parent.as_posix()
                    if name not in expected:
                        created = root / parent
                        created.mkdir()
                        expected[name] = tree_records(created)['.']
                row = {'destination': destination, 'saved': saved, 'existed': existed,
                       'desired': desired, 'published': False}
                committed.append(row)
                journal['entries'].append({'path': relative_path.as_posix(), 'existed': existed,
                                           'before': before, 'desired': desired})
                _distribution_record(temporary, journal)
                if existed:
                    os.replace(destination, saved)
                    if not same_tree(tree_records(saved), before):
                        raise ValueError('Distribution target changed while retiring: ' + str(relative_path))
                if staged.is_dir():
                    publish_directory(staged, destination)
                else:
                    os.link(staged, destination, follow_symlinks=False)
                    staged.unlink()
                row['published'] = True
                prefix = relative_path.as_posix()
                expected = {name: state for name, state in expected.items()
                            if name != prefix and not name.startswith(prefix + '/')}
                expected.update({prefix + ('' if name == '.' else '/' + name): state
                                 for name, state in desired.items()})
                verify(expected)
                if existed and not same_tree(tree_records(saved), before):
                    raise ValueError('Retired distribution input changed: ' + str(relative_path))
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
        journal['status'] = 'complete'
        _distribution_record(temporary, journal)
        return prepared
    finally:
        if not retain_backup:
            shutil.rmtree(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=['standalone'], default='standalone')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--format', dest='output_format', choices=['flat', 'deployed'], default='flat')
    parser.add_argument('--layout', choices=['source', 'installed'], default='source')
    select = parser.add_mutually_exclusive_group()
    select.add_argument('--task')
    select.add_argument('--skills', nargs='+')
    parser.add_argument('--mode')
    parser.add_argument('--support', action='append', default=[])
    parser.add_argument('--condition', action='append', default=[])
    parser.add_argument('--references', action='append', default=[])
    parser.add_argument('--style-profile')
    parser.add_argument('--generate-index', type=Path)
    parser.add_argument('--generate-entries', action='store_true')
    args = parser.parse_args()
    try:
        if args.generate_entries:
            generate_distribution(ROOT)
            return
        if args.generate_index:
            args.generate_index.write_text(native_index(load_routes(ROOT)), encoding='utf-8')
            return
        if not args.output:
            parser.error('--output is required')
        count = export(args.output, args.profile, args.skills, task=args.task, support=args.support, references=args.references, style_profile=args.style_profile, mode=args.mode, conditions=args.condition, layout=args.layout, output_format=args.output_format)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, f'Export: {error}\n')
    print(f'Exported {count} files to {args.output}')


if __name__ == '__main__':
    main()
