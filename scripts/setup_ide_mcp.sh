#!/usr/bin/env bash
# Configuration generation; no client processes or installers are invoked.
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PROJECT_ROOT
exec python3 -B - "$@" <<'PY'
import argparse
import copy
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import sys
import tempfile
import tomllib
import subprocess
from urllib.parse import urlsplit

ROOT = Path(os.environ['PROJECT_ROOT'])
sys.path.insert(0, str(ROOT / 'scripts'))
from route_registry import load_routes

def read(path):
    if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != ROOT.parent):
        raise ValueError(f'Symlink configuration path refused: {path}')
    return path.read_bytes() if path.exists() else None

def encode(data):
    return (json.dumps(data, indent=2, ensure_ascii=False) + '\n').encode()

def replace(path, content):
    if content is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            os.chmod(temp, path.stat().st_mode & 0o777)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def apply(plan):
    # All inputs and outputs have already been parsed. Recheck the full read set.
    for path, (before, after) in plan.items():
        if read(path) != before:
            raise RuntimeError(f'Concurrent edit preserved: {path}')
    done = []
    try:
        for path, (before, after) in plan.items():
            if before == after:
                continue
            if read(path) != before:
                raise RuntimeError(f'Concurrent edit preserved: {path}')
            replace(path, after)
            done.append(path)
    except BaseException:
        for path in reversed(done):
            before, after = plan[path]
            # Never undo another writer's edit during recovery.
            try:
                if read(path) == after:
                    replace(path, before)
                else:
                    print(f'Recovery preserved concurrent edit: {path}', file=sys.stderr)
            except (OSError, ValueError) as error:
                print(f'Recovery could not restore {path}: {error}', file=sys.stderr)
        raise

def merge(actual, expected, previous):
    # Old name-only ownership cannot prove content ownership; preserve it.
    if not isinstance(previous, dict) or 'owned' not in previous:
        previous = {'owned': {}, 'released': []}
    owned = previous['owned']
    released = set(previous.get('released', []))
    result = copy.deepcopy(actual)
    next_owned = {}
    for name, old in owned.items():
        if name not in actual or actual[name] != old:
            released.add(name)
        elif name not in expected:
            result.pop(name)
        else:
            result[name] = expected[name]
            next_owned[name] = expected[name]
    for name, value in expected.items():
        if name not in actual and name not in released and name not in owned:
            result[name] = value
            next_owned[name] = value
    return result, {'owned': next_owned, 'released': sorted(released)}

def toml_servers(text):
    parsed = tomllib.loads(text)
    actual = parsed.get('mcp_servers', {})
    # Preserve raw user text; supported generated entries use explicit table headers.
    headers = list(re.finditer(r'^\s*\[([^\]\n]+)\][ \t]*(?:#[^\n]*)?$', text, re.M))
    spans = {}
    for i, match in enumerate(headers):
        name = match.group(1)
        if name.startswith('mcp_servers.'):
            key_text = name[len('mcp_servers.'):]
            keys = tomllib.loads('[' + name + ']\n')['mcp_servers']
            key = next(iter(keys))
            if key_text != key and key_text != json.dumps(key):
                continue
            spans[key] = (match.start(), headers[i+1].start() if i+1 < len(headers) else len(text))
    return actual, spans

def toml_entry(name, server):
    key = name if re.fullmatch(r'[A-Za-z0-9_-]+', name) else json.dumps(name)
    lines = ['[mcp_servers.' + key + ']']
    for field in ('command', 'args', 'url', 'env_vars'):
        if field in server:
            lines.append(field + ' = ' + json.dumps(server[field]))
    return '\n'.join(lines) + '\n\n'

def toml_team(text, settings):
    """Update the selected scalar settings while retaining unrelated TOML text."""
    parsed = tomllib.loads(text)
    def table(data, section):
        for part in section.split('.') if section else ():
            data = data.get(part, {})
            if not isinstance(data, dict):
                raise ValueError('Codex ' + section + ' setting must be a table')
        return data
    if 'agents' in parsed and not isinstance(parsed['agents'], dict):
        raise ValueError('Codex agents setting must be a table')
    lines = text.splitlines(keepends=True)
    sections = {section: [] for section in settings}
    section = ''
    table_seen = False
    for index, line in enumerate(lines):
        if re.match(r'^\s*\[\[', line):
            section = None
            continue
        header = re.match(r'^\s*\[([^\]\n]+)\][ \t]*(?:#[^\n]*)?(?:\n|$)', line)
        if header:
            section = header.group(1).strip()
            if section == 'agents':
                table_seen = True
            continue
        if section in sections:
            sections[section].append(index)

    insertions = {section: [] for section in settings}
    for section, values in settings.items():
        actual = table(parsed, section)
        for key, value in values.items():
            matches = []
            for index in sections[section]:
                match = re.match(r'^([ \t]*' + re.escape(key) + r'[ \t]*=[ \t]*)(.*?)(\r?\n)?$', lines[index])
                if match:
                    matches.append((index, match))
            if len(matches) > 1 or (key in actual and not matches):
                raise ValueError(f'Unsupported Codex TOML layout for {section + "." if section else ""}{key}')
            rendered = json.dumps(value)
            if not matches:
                insertions[section].append(f'{key} = {rendered}\n')
                continue
            index, match = matches[0]
            # The managed keys are scalar; parsing the original line also rejects
            # multiline or dotted layouts before any files are written.
            try:
                tomllib.loads(lines[index])
            except tomllib.TOMLDecodeError as error:
                raise ValueError(f'Unsupported Codex TOML assignment for {key}') from error
            value_text = match.group(2)
            in_string = False
            quote = ''
            escaped = False
            comment = ''
            for position, char in enumerate(value_text):
                if escaped:
                    escaped = False
                elif in_string and quote == '"' and char == '\\':
                    escaped = True
                elif in_string and char == quote:
                    in_string = False
                elif not in_string and char in ('"', "'"):
                    in_string, quote = True, char
                elif not in_string and char == '#':
                    comment = ' ' + value_text[position:].rstrip()
                    break
            lines[index] = match.group(1) + rendered + comment + (match.group(3) or '\n')
    # Root fields must precede the first table. A late [agents] header is valid
    # even if a child table such as [agents.reviewer] appeared earlier.
    first_table = next((i for i, line in enumerate(lines) if re.match(r'^\s*\[', line)), len(lines))
    if insertions[''] and first_table and not lines[first_table - 1].endswith('\n'):
        lines[first_table - 1] += '\n'
    lines[first_table:first_table] = insertions['']
    result = ''.join(lines)
    if insertions['agents']:
        if table_seen:
            header = re.search(r'^\s*\[agents\][ \t]*(?:#[^\n]*)?(?:\n|$)', result, re.M)
            result = result[:header.end()] + ''.join(insertions['agents']) + result[header.end():]
        else:
            if 'agents' in parsed and not any(re.match(r'^\s*\[agents\.', line) for line in lines):
                raise ValueError('Unsupported Codex agents table layout')
            result += ('\n' if result and not result.endswith('\n') else '') + '\n[agents]\n' + ''.join(insertions['agents'])
    updated = tomllib.loads(result)
    original_other = copy.deepcopy(parsed)
    updated_other = copy.deepcopy(updated)
    for section, values in settings.items():
        actual = table(updated, section)
        if any(actual.get(key) != value for key, value in values.items()):
            raise ValueError('Could not apply Codex team settings')
        for data in (original_other, updated_other):
            target = table(data, section)
            for key in values:
                target.pop(key, None)
    if 'agents' not in original_other and updated_other.get('agents') == {}:
        updated_other.pop('agents')
    if original_other != updated_other:
        raise ValueError('Codex team settings would change unrelated TOML data')
    return result

def describe(actual, expected):
    # Report structural differences without printing private configuration values.
    return [('+' if name not in actual else '-' if name not in expected else '~') + ' server ' + name
            for name in sorted(actual.keys() | expected.keys()) if actual.get(name) != expected.get(name)]

def main():
    parser = argparse.ArgumentParser(description='Preview or apply selected MCP or Codex team configuration. Python 3.11+ required.')
    modes = parser.add_mutually_exclusive_group()
    for flag in ('diff', 'check', 'print', 'write'):
        modes.add_argument('--' + flag, dest='mode', action='store_const', const=flag)
    parser.set_defaults(mode='diff')
    parser.add_argument('--client', action='append', default=[])
    parser.add_argument('--codex-team', '--agent-team', dest='codex_team', action='store_true', help='Apply native agent team settings and roles')
    parser.add_argument('--openai-preset', action='store_true', help='Apply the explicit Codex OpenAI model preset')
    parser.add_argument('--codex-hooks', action='store_true', help='Install the existing Codex lifecycle hooks')
    parser.add_argument('--scope', choices=('project', 'user'), default='project', help='Configuration destination (user is supported for the Codex team only)')
    args = parser.parse_args()
    # Client paths have one definition shared with deployment/export.
    routes = load_routes(ROOT)
    clients = routes['placements']['configuration']['configuration_clients']
    if any(client not in clients and not (args.codex_team and client == 'opencode') for client in args.client):
        parser.error('Unknown client; choose from: ' + ', '.join(clients))
    if args.codex_team and (len(set(args.client)) != 1 or args.client[0] not in ('codex', 'claude', 'opencode', 'gemini') or args.mode == 'print'):
        parser.error('--agent-team requires one client: codex, claude, opencode or gemini, and cannot be combined with --print')
    if args.openai_preset and (not args.codex_team or set(args.client) != {'codex'}):
        parser.error('--openai-preset requires --agent-team --client codex')
    if args.codex_hooks and (set(args.client) != {'codex'} or args.mode == 'print'):
        parser.error('--codex-hooks requires only --client codex and cannot be combined with --print')
    if args.scope == 'user' and (not (args.codex_team or args.codex_hooks) or set(args.client) != {'codex'}):
        parser.error('--scope user requires --codex-team or --codex-hooks and --client codex')
    if args.mode == 'write' and not args.client:
        parser.error('--write requires at least one --client')
    selected = list(dict.fromkeys(args.client))
    if not selected and args.mode != 'print':
        selected = [name for name, specs in clients.items()
                    if all(spec['format'] != 'devcontainer' or (ROOT / spec['path']).exists() for spec in specs)]
    if not (args.codex_team or args.codex_hooks):
        servers = json.loads((ROOT / 'docs/ai/config-templates/mcp.example.json').read_text())['mcpServers']
        if os.environ.get('ENABLE_ECONOMICS_CHECKED_MCP') == '1':
            endpoint = os.environ.get('ECONOMICS_CHECKED_MCP_URL', '').strip()
            parsed = urlsplit(endpoint)
            parsed.port  # Validate a supplied port before writing any settings.
            if (parsed.scheme != 'https' or not parsed.hostname or parsed.username
                    or parsed.password or parsed.query or parsed.fragment
                    or any(char.isspace() or ord(char) < 32 for char in endpoint)):
                raise ValueError('Enabled Economics Checked MCP requires an HTTPS endpoint without credentials, query or fragment')
            if any(client in ('vscode', 'devcontainer') for client in selected):
                raise ValueError('Personal Economics Checked MCP requires a Git-ignored local client configuration')
            if shutil.which('git'):
                repo = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
                if repo.returncode == 0:
                    for client in selected:
                        for spec in clients[client]:
                            relative = spec['path']
                            tracked = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '--error-unmatch', '--', relative], capture_output=True)
                            ignored = subprocess.run(['git', '-C', str(ROOT), 'check-ignore', '--no-index', '-q', '--', relative], capture_output=True)
                            if tracked.returncode == 0 or ignored.returncode != 0:
                                raise ValueError('Personal Economics Checked MCP destination must be untracked and Git-ignored: ' + relative)
            servers['economics-checked-artifacts'] = {'type': 'http', 'url': endpoint}
        environment = {'brave-search': 'BRAVE_API_KEY', 'exa': 'EXA_API_KEY', 'github': 'GITHUB_PERSONAL_ACCESS_TOKEN', 'postgres': 'DATABASE_URL'}
        definitions = {
            'brave-search': {'command': 'mcp-server-brave-search', 'args': []},
            'exa': {'command': 'npx', 'args': ['--no-install', 'exa-mcp-server']},
            'github': {'command': 'npx', 'args': ['--no-install', '@modelcontextprotocol/server-github']},
            'postgres': {'command': 'bash', 'args': ['-c', 'exec mcp-server-postgres "${DATABASE_URL:?Set DATABASE_URL in the IDE environment}"']},
        }
        for name, variable in environment.items():
            if os.environ.get(variable):
                servers[name] = definitions[name]
        if os.environ.get('ENABLE_GOOGLE_DRIVE_MCP') == '1':
            if not (ROOT / 'secrets/credentials.json').is_file():
                raise ValueError('Enabled Google Drive requires secrets/credentials.json')
            servers['google-drive'] = {'command': 'bash', 'args': ['-lc', 'cd ' + shlex.quote(str(ROOT / 'secrets')) + ' && exec mcp-server-gdrive']}
        if os.environ.get('ENABLE_CONTEXT_MCP') == '1':
            for command in ('codebase-memory-mcp', 'token-optimizer-mcp'):
                if not shutil.which(command):
                    raise ValueError('Enabled context integration missing command: ' + command)
                servers[command] = {'command': command, 'args': []}
    if args.mode == 'print':
        print(json.dumps({'mcpServers': servers}, indent=2))
        return 0
    if args.scope == 'user':
        configured_home = os.environ.get('CODEX_HOME')
        codex_home = Path(configured_home).expanduser() if configured_home else Path.home() / '.codex'
        if not codex_home.is_absolute():
            codex_home = Path.cwd() / codex_home
        target_root = codex_home
        state_path = codex_home / '.agents/state/mcp-generated.json'
    else:
        target_root = ROOT
        state_path = ROOT / '.agents/state/mcp-generated.json'
    state_bytes = read(state_path)
    state = json.loads(state_bytes) if state_bytes is not None else {}
    next_state = copy.deepcopy(state)
    plan = {}
    change_details = {}
    conflicts = []
    for client in selected:
        if args.codex_team and client != 'codex':
            continue
        for spec in clients[client]:
            relative = spec['path']
            if args.scope == 'user':
                relative = 'config.toml'
            path = target_root / relative
            if args.scope == 'project' and path.is_absolute() and not path.resolve().is_relative_to(ROOT):
                raise ValueError('Configuration target escapes project: ' + relative)
            before = read(path)
            kind = spec['format']
            if kind == 'toml':
                original = before.decode() if before is not None else ''
                result = original
                if not (args.codex_team or args.codex_hooks):
                    actual, spans = toml_servers(original)
                    expected = {name: {k: v for k, v in server.items() if k in ('command', 'args', 'url')} for name, server in servers.items()}
                    for name, variable in environment.items():
                        if name in expected:
                            expected[name]['env_vars'] = [variable]
                    merged, ownership = merge(actual, expected, state.get(relative))
                    change_details[relative] = describe(actual, merged)
                    changed = {name for name in actual if actual[name] != merged.get(name)}
                    if changed - spans.keys():
                        raise ValueError('Unsupported edited TOML layout in ' + relative)
                    for name in sorted(changed, key=lambda n: spans[n][0], reverse=True):
                        start, end = spans[name]
                        result = result[:start] + (toml_entry(name, merged[name]) if name in merged else '') + result[end:]
                    for name in sorted(merged.keys() - actual.keys()):
                        result += ('\n' if result and not result.endswith('\n\n') else '') + toml_entry(name, merged[name])
                if args.codex_team and client == 'codex':
                    template_path = ROOT / 'docs/ai/config-templates/codex.example.toml'
                    template_bytes = read(template_path)
                    if template_bytes is None:
                        raise ValueError('Codex team template is missing')
                    template = tomllib.loads(template_bytes.decode())
                    plan[template_path] = (template_bytes, template_bytes)
                    configured = tomllib.loads(result)
                    agents = configured.get('agents', {})
                    if not isinstance(agents, dict):
                        raise ValueError('Codex agents setting must be a table')
                    capacity_keys = [key for key in ('max_concurrent_threads_per_session', 'max_threads') if key in agents]
                    if len(capacity_keys) > 1:
                        raise ValueError('Codex agents capacity aliases cannot both be set')
                    capacity_key = capacity_keys[0] if capacity_keys else 'max_concurrent_threads_per_session'
                    settings = {'': {}, 'agents': {'enabled': True}}
                    for key, limit in ((capacity_key, 3), ('max_depth', 2)):
                        value = agents.get(key, limit)
                        if type(value) is not int or (key == capacity_key and value < 1) or (key == 'max_depth' and not -(2**31) <= value < 2**31):
                            raise ValueError('Invalid Codex agents ' + key)
                        settings['agents'][key] = min(value, limit)
                    features = configured.get('features', {})
                    if not isinstance(features, dict):
                        raise ValueError('Codex features setting must be a table')
                    v2 = features.get('multi_agent_v2')
                    capacity_field = 'max_concurrent_threads_per_session'
                    if isinstance(v2, dict) and capacity_field in v2:
                        value = v2[capacity_field]
                        if type(value) is not int or value < 1:
                            raise ValueError('Invalid Codex V2 session capacity')
                        if value > 4:
                            settings['features.multi_agent_v2'] = {capacity_field: 4}
                    if args.openai_preset:
                        root_keys = ('model', 'model_reasoning_effort', 'forced_login_method')
                        if args.scope == 'user':
                            root_keys += ('model_provider',)
                        expected = {key: template[key] for key in root_keys}
                        expected.update({'agents.' + key: template['agents'][key] for key in
                                         ('default_subagent_model', 'default_subagent_reasoning_effort')})
                        actual = {key: configured[key] for key in root_keys if key in configured}
                        actual.update({'agents.' + key: agents[key] for key in
                                       ('default_subagent_model', 'default_subagent_reasoning_effort') if key in agents})
                        merged, ownership = merge(actual, expected, state.get(relative + '#openai-preset'))
                        if merged != expected:
                            conflicts.append(relative + '#openai-preset')
                        next_state[relative + '#openai-preset'] = ownership
                        for key in expected:
                            if key in merged and (key not in actual or merged[key] != actual[key]):
                                section, field = ('agents', key[7:]) if key.startswith('agents.') else ('', key)
                                settings[section][field] = merged[key]
                    result = toml_team(result, settings)
                tomllib.loads(result)
                after = result.encode()
                if not (args.codex_team or args.codex_hooks):
                    next_state[relative] = ownership
            else:
                if kind == 'devcontainer' and before is None:
                    raise ValueError('Selected devcontainer input missing: ' + relative)
                data = json.loads(before) if before is not None else {}
                if kind == 'devcontainer':
                    targets = []
                    for name, customization in data.get('customizations', {}).items():
                        settings = customization.get('settings', {})
                        if 'mcpServers' in settings:
                            targets.append((relative + '#' + name, settings))
                    if not targets:
                        raise ValueError('Selected devcontainer has no settings.mcpServers target')
                else:
                    targets = [(relative, data)]
                for key, container in targets:
                    actual = container.get('mcpServers', {})
                    if not isinstance(actual, dict):
                        raise ValueError('mcpServers must be an object: ' + key)
                    merged, ownership = merge(actual, servers, state.get(key))
                    change_details[key] = describe(actual, merged)
                    container['mcpServers'] = merged
                    next_state[key] = ownership
                after = encode(data) if before is None or json.loads(before) != data else before
            plan[path] = (before, after)
    if args.codex_team:
        client = selected[0]
        roles = ('lead', 'implementer', 'retriever', 'specialist', 'reviewer')
        role_presets = {}
        if args.openai_preset:
            # Explicit selection owns these native fields; ordinary setup inherits.
            role_presets = {
                'lead': (template['model'], 'high'),
                'implementer': (template['model'], 'medium'),
                'retriever': ('gpt-6-luna', 'low'),
                'specialist': (template['model'], 'ultra'),
                'reviewer': (template['model'], 'high'),
            }
        if client == 'codex':
            roles += ('terra', 'luna', 'astra')
        for role in roles:
            source = ROOT / 'references/repository-policy/.codex/agents' / (role + '.toml')
            source_bytes = read(source)
            if source_bytes is None:
                raise ValueError('Team role template is missing: ' + role)
            source_role = tomllib.loads(source_bytes.decode())
            if source_role.get('name') != role or not all(isinstance(source_role.get(key), str) for key in ('description', 'developer_instructions')):
                raise ValueError('Invalid team role template: ' + role)
            plan[source] = (source_bytes, source_bytes)
            if client == 'codex':
                relative = f'{"agents" if args.scope == "user" else ".codex/agents"}/{role}.toml'
                content = source_bytes.decode()
                if role in role_presets:
                    model, effort = role_presets[role]
                    content = ('model = ' + json.dumps(model) + '\n' +
                               'model_reasoning_effort = ' + json.dumps(effort) + '\n' + content)
                    tomllib.loads(content)
            else:
                relative = f'.{client}/agents/{role}.md'
                fields = ['---']
                if client in ('claude', 'gemini'):
                    fields.append('name: ' + json.dumps(source_role['name']))
                fields.append('description: ' + json.dumps(source_role['description']))
                if client == 'claude':
                    fields.extend(['model: inherit', 'color: blue'])
                elif client == 'opencode':
                    fields.append('mode: subagent')
                content = '\n'.join(fields + ['---', '', source_role['developer_instructions'], ''])
            path = target_root / relative
            before = read(path)
            expected = {'content': content}
            actual = {'content': before.decode()} if before is not None else {}
            merged, ownership = merge(actual, expected, state.get(relative))
            if merged != expected:
                conflicts.append(relative)
            else:
                plan[path] = (before, merged['content'].encode())
                next_state[relative] = ownership
    if args.codex_hooks:
        config_path = target_root / ('config.toml' if args.scope == 'user' else '.codex/config.toml')
        config_bytes = read(config_path)
        config = tomllib.loads(config_bytes.decode()) if config_bytes else {}
        if config.get('hooks'):
            raise ValueError('Inline Codex hooks already exist at this configuration layer')
        if config_path not in plan:
            plan[config_path] = (config_bytes, config_bytes)
        template_path = ROOT / 'hooks/hooks.json'
        wrapper_path = ROOT / 'hooks/check.py'
        template_bytes, wrapper_bytes = read(template_path), read(wrapper_path)
        if template_bytes is None or wrapper_bytes is None:
            raise ValueError('Codex hook template or wrapper is missing')
        plan[template_path] = (template_bytes, template_bytes)
        plan[wrapper_path] = (wrapper_bytes, wrapper_bytes)
        relative = 'hooks.json' if args.scope == 'user' else '.codex/hooks.json'
        path = target_root / relative
        before = read(path)
        document = json.loads(before) if before else {'hooks': {}}
        if not isinstance(document, dict) or not isinstance(document.get('hooks'), dict):
            raise ValueError('Invalid Codex hooks configuration')
        configured = document['hooks']
        expected = json.loads(template_bytes)['hooks']
        data_path = target_root / '.agents/state/codex-hooks'
        for event, entries in expected.items():
            for item in entries:
                for handler in item['hooks']:
                    handler['command'] = ('env PLUGIN_ROOT=' + shlex.quote(str(ROOT)) +
                                          ' PLUGIN_DATA=' + shlex.quote(str(data_path)) + ' python3 ' +
                                          shlex.quote(str(wrapper_path)) + ' ' + shlex.quote(event))
        prior = state.get(relative, {})
        owned = prior.get('owned', {}) if isinstance(prior, dict) else {}
        updated_owned = {}
        for event, entries in expected.items():
            current = configured.setdefault(event, [])
            if not isinstance(current, list) or len(entries) != 1:
                raise ValueError('Unsupported Codex hook entries for ' + event)
            old = owned.get(event)
            if old is not None:
                if old not in current:
                    conflicts.append(relative + ':' + event)
                    continue
                current.remove(old)
            elif entries[0] in current:
                conflicts.append(relative + ':' + event)
                continue
            current.append(entries[0])
            updated_owned[event] = entries[0]
        if not conflicts:
            plan[path] = (before, encode(document))
            next_state[relative] = {'owned': updated_owned, 'released': []}
    if conflicts:
        for relative in conflicts:
            print('Conflict: user-owned or edited role file preserved: ' + relative, file=sys.stderr)
        return 1
    plan[state_path] = (state_bytes, encode(next_state))
    differences = [path for path, (before, after) in plan.items() if before != after]
    for path in differences:
        display = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
        print(('Would update: ' if args.mode != 'write' else 'Planned update: ') + str(display))
    for key, changes in change_details.items():
        for change in changes:
            print('  ' + key + ': ' + change)
    if args.mode == 'check':
        return int(bool(differences))
    if args.mode == 'write':
        apply(plan)
        print('Applied selected agent team configuration.' if args.codex_team else 'Applied selected MCP configuration.')
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, TypeError, RuntimeError) as error:
        print('Configuration failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
PY
