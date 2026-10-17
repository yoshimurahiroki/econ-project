#!/usr/bin/env python3
"""Export a route-selected, content-addressed standalone instruction package."""
import argparse
import hashlib
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
from route_registry import load_routes, resource_path, resolve_operation, native_index, relative, merge_selection, rule_selection, required_closure, generate_entries
ROOT = Path(__file__).resolve().parents[1]


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def inline_code_mask(text):
    """Mark matched backtick spans without changing their bytes or offsets."""
    mask = bytearray(len(text))
    position = 0
    while position < len(text):
        if text[position] != "`" or (position and text[position - 1] == "\\"):
            position += 1
            continue
        end = position
        while end < len(text) and text[end] == "`":
            end += 1
        length = end - position
        closing = end
        while closing < len(text):
            candidate = text.find("`", closing)
            if candidate < 0:
                break
            stop = candidate
            while stop < len(text) and text[stop] == "`":
                stop += 1
            if stop - candidate == length:
                mask[position:stop] = b"\x01" * (stop - position)
                position = stop
                break
            closing = stop
        else:
            candidate = -1
        if candidate < 0 or closing >= len(text):
            position = end
    return mask


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


def heading_id(text):
    text = re.sub(r'\s+#+\s*$', '', text).strip()
    return re.sub(r'[^\w\- ]', '', text.lower()).replace(' ', '-')


def markdown_sections(text):
    """ATX and setext headings outside fences, with stable GitHub-style IDs."""
    lines = text.splitlines(keepends=True)
    headings, counts, fence = [], {}, None
    for index, line in enumerate(lines):
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if fence:
            if re.match(r'^ {0,3}' + re.escape(fence[0]) + '{' + str(len(fence)) + r',}\s*$', line):
                fence = None
            continue
        if marker:
            fence = marker.group(1)
            continue
        match = re.match(r'^ {0,3}(#{1,6})\s+(.+?)\s*$', line)
        if match:
            level, title, start = len(match.group(1)), re.sub(r'\s+#+$', '', match.group(2)), index
        elif index and re.match(r'^ {0,3}(=+|-+)\s*$', line) and lines[index - 1].strip() and not (index == 1 and lines[0].strip() == '---'):
            level, title, start = (1 if line.lstrip().startswith('=') else 2), lines[index - 1].strip(), index - 1
        else:
            continue
        slug = heading_id(title)
        count = counts.get(slug, 0); counts[slug] = count + 1
        headings.append({'title': title, 'id': slug + (f'-{count}' if count else ''), 'level': level, 'start': start})
    for i, heading in enumerate(headings):
        heading['end'] = next((h['start'] for h in headings[i + 1:] if h['level'] <= heading['level']), len(lines))
    return lines, headings


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


def export(target, profile='standalone', skills=None, *, task=None, support=(), references=(), style_profile=None, mode=None, conditions=(), layout='source', output_format='flat'):
    root = ROOT.resolve()
    target = Path(target).absolute()
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
    selected = set(selections)
    unsupported = sorted(rid for rid in selected if resources[rid].get('snapshot') == 'source_distribution_only')
    if unsupported:
        raise ValueError('Use complete source distribution for maintenance tools; cannot publish an executable flat/deployed snapshot for: ' + ', '.join(unsupported))
    output_paths = {rid: res['export_alias' if output_format == 'flat' else 'deployment_path'] for rid, res in resources.items()}
    # Both physical layouts use the exact same resolved selections.
    # All logical paths resolve through this registry in either physical layout.
    path_ids = {}
    for rid, res in resources.items():
        for key in ('source_path', 'deployment_path'):
            path_ids[(root / res[key]).resolve()] = rid
    generated = {'ECON_INDEX.md', 'SOURCE.md', 'OPTIONAL_INPUTS.md', 'PROJECT_INSTRUCTIONS.txt'}
    aliases = {output_paths[rid]: rid for rid in selected}
    if {name.casefold() for name in aliases} & {name.casefold() for name in generated}:
        # The instruction template is rendered below if declared as a resource.
        collisions = {name.casefold() for name in aliases} & {name.casefold() for name in generated - {'PROJECT_INSTRUCTIONS.txt'}}
        if collisions:
            raise ValueError('Reserved generated aliases: ' + ', '.join(collisions))
    if custom and 'CUSTOM_STYLE.md' in aliases:
        raise ValueError('Custom profile alias collision')
    # Validate each selected required rule before any optional-link conversion or publication.
    # Errors identify the stable rule and originating operation, including missing files/headings.
    for operation in operations + reference_required:
        for rule_id in operation.get('active_rules', []):
            for rid, rule_scope in rule_selection(routes, rule_id, operation['canonical_operation']).items():
                try:
                    source_text = resource_path(root, resources[rid], layout).read_text(encoding='utf-8')
                    extract_sections(source_text, rule_scope, rid)
                except (OSError, ValueError) as error:
                    raise ValueError(f'Missing required rule {rule_id}; operation {operation["canonical_operation"]}: {error}') from error
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
    def destination(source, link, output='ECON_INDEX.md'):
        def local(path):
            return os.path.relpath(path, str(Path(output).parent)).replace(os.sep, '/')
        parts = urlsplit(link)
        if parts.scheme or link.startswith('//'):
            return link
        clean = unquote(parts.path)
        suffix = '#' + parts.fragment if parts.fragment else ''
        if clean in aliases or clean in generated or (custom and clean == 'CUSTOM_STYLE.md'):
            return local(clean) + suffix
        path = ((root / clean.lstrip('/') if clean.startswith('/') else source.parent / clean) if clean else source).resolve()
        if path in project_aliases:
            return local(project_aliases[path]) + suffix
        rid = path_ids.get(path)
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
                optional_section = rid + '--' + unquote(parts.fragment)
                omitted.add(optional_section)
                return local('OPTIONAL_INPUTS.md') + '#' + heading_id(optional_section)
            return local(output_paths[rid]) + suffix
        if rid:
            omitted.add(rid)
            return local('OPTIONAL_INPUTS.md') + '#' + heading_id(rid)
        raise ValueError(f'Unregistered local reference in {source.name}: {link}')
    contents = {}
    records = []
    for rid in sorted(selected):
        res = resources[rid]
        source = resource_path(root, res, layout)
        text = extract_sections(raw[rid].decode('utf-8').replace('\r\n', '\n'), selections[rid], rid)
        if res['source_path'] == 'docs/ai/compiled_ai_skills.md':
            text = '# Selected operations\n\n' + '\n'.join(f"- {op['canonical_operation']}" for op in operations) + '\n'
        text = rewrite_markdown(text, lambda link: destination(source, link, output_paths[rid]))
        # Inline physical references become included aliases or explicit optional inputs.
        for other, item in sorted(resources.items(), key=lambda pair: -len(pair[1]['source_path'])):
            for key in ('source_path', 'deployment_path'):
                token = '`' + item[key] + '`'
                if token in text:
                    replacement = os.path.relpath(output_paths[other], str(Path(output_paths[rid]).parent)).replace(os.sep, '/') if other in selected else 'optional input: ' + other
                    text = text.replace(token, '`' + replacement + '`')
                    if other not in selected:
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
    if custom:
        data = custom.read_bytes()
        text = rewrite_markdown(data.decode(), lambda link: destination(custom, link))
        contents['CUSTOM_STYLE.md'] = text
        records.append({'logical_id': 'profile.custom', 'source': 'external-profile', 'output': 'CUSTOM_STYLE.md', 'source_sha256': sha256(data), 'export_sha256': sha256(text.encode())})
    lines = ['# Selected task operations', '', 'Read the included common rules once. Support inherits this task and returns to its owner.', '']
    lines += [f"- {op['skill_id']} / {op['mode']}: {op['operation']}" for op in operations]
    lines += ['', 'Included resources:', ''] + [f'- [{rid}]({output_paths[rid]})' for rid in sorted(selected)]
    if custom:
        lines += ['', 'Task writing profile: [custom](CUSTOM_STYLE.md). This overrides the project preference for this task only.']
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
        contents['PROJECT_INSTRUCTIONS.txt'] = 'Follow ECON_INDEX.md for the selected operation and included common rules. SOURCE.md identifies this content snapshot. Request optional inputs only when their function is needed.\n'
    if output_format == 'deployed':
        pointers = routes.get('placements', {}).get('policy_pointers', [])
        if 'repository-policy' in resources:
            pointers = pointers + [resources['repository-policy']]
        for pointer in pointers:
            filename = relative(pointer['deployment_path'])
            parent = str(Path(filename).parent)
            core_link = os.path.relpath(output_paths['core'], parent).replace(os.sep, '/')
            index_link = os.path.relpath('ECON_INDEX.md', parent).replace(os.sep, '/')
            contents[filename] = f'# Economics task entry\n\nRead [common rules]({core_link}) once, then [selected operation]({index_link}).\n'
        instructions = resources.get('project-instructions', {}).get('deployment_path', 'docs/ai/project_instructions.txt')
        contents[instructions] = 'Follow ' + os.path.relpath('ECON_INDEX.md', str(Path(instructions).parent)).replace(os.sep, '/') + ' for the selected operation and common rules.\n'
    if len(contents['PROJECT_INSTRUCTIONS.txt'].replace('\n', '\r\n')) > 8000:
        raise ValueError('Project instructions exceed 8,000 characters')
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
    # Every emitted local prose reference must resolve within the package.
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
                raise ValueError(f'Missing packaged reference in {name}: {link}')
            if parts.fragment:
                anchors = {h['id'] for h in markdown_sections(contents[destination_name])[1]}
                if unquote(parts.fragment) not in anchors:
                    raise ValueError(f'Missing packaged section in {name}: {link}')
            return link
        rewrite_markdown(text, validate_link)
    # Validate all content before publishing the directory. No Git or network needed.
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.econ-export-', dir=target.parent))
    try:
        for name, text in contents.items():
            (temporary / name).parent.mkdir(parents=True, exist_ok=True)
            (temporary / name).write_text(text, encoding='utf-8')
        if target.exists() or target.is_symlink():
            raise ValueError('Output appeared while preparing export')
        os.rename(temporary, target)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return len(contents)


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
            generate_entries(ROOT)
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
