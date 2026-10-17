#!/usr/bin/env bash
# Project-local generation; no client processes or installers are invoked.
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

def describe(actual, expected):
    # Report structural differences without printing private configuration values.
    return [('+' if name not in actual else '-' if name not in expected else '~') + ' server ' + name
            for name in sorted(actual.keys() | expected.keys()) if actual.get(name) != expected.get(name)]

def main():
    parser = argparse.ArgumentParser(description='Preview or apply selected project-local MCP configuration. Python 3.11+ required.')
    modes = parser.add_mutually_exclusive_group()
    for flag in ('diff', 'check', 'print', 'write'):
        modes.add_argument('--' + flag, dest='mode', action='store_const', const=flag)
    parser.set_defaults(mode='diff')
    parser.add_argument('--client', action='append', default=[])
    args = parser.parse_args()
    # Client paths have one definition shared with deployment/export.
    routes = load_routes(ROOT)
    clients = routes['placements']['configuration']['configuration_clients']
    if any(client not in clients for client in args.client):
        parser.error('Unknown client; choose from: ' + ', '.join(clients))
    if args.mode == 'write' and not args.client:
        parser.error('--write requires at least one --client')
    selected = list(dict.fromkeys(args.client))
    if not selected and args.mode != 'print':
        selected = [name for name, specs in clients.items()
                    if all(spec['format'] != 'devcontainer' or (ROOT / spec['path']).exists() for spec in specs)]
    servers = json.loads((ROOT / 'docs/ai/config-templates/mcp.example.json').read_text())['mcpServers']
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
    state_path = ROOT / '.agents/state/mcp-generated.json'
    state_bytes = read(state_path)
    state = json.loads(state_bytes) if state_bytes is not None else {}
    next_state = copy.deepcopy(state)
    plan = {}
    change_details = {}
    for client in selected:
        for spec in clients[client]:
            relative = spec['path']
            path = ROOT / relative
            if path.is_absolute() and not path.resolve().is_relative_to(ROOT):
                raise ValueError('Configuration target escapes project: ' + relative)
            before = read(path)
            kind = spec['format']
            if kind == 'toml':
                original = before.decode() if before is not None else ''
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
                result = original
                for name in sorted(changed, key=lambda n: spans[n][0], reverse=True):
                    start, end = spans[name]
                    result = result[:start] + (toml_entry(name, merged[name]) if name in merged else '') + result[end:]
                for name in sorted(merged.keys() - actual.keys()):
                    result += ('\n' if result and not result.endswith('\n\n') else '') + toml_entry(name, merged[name])
                tomllib.loads(result)
                after = result.encode()
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
    plan[state_path] = (state_bytes, encode(next_state))
    differences = [path for path, (before, after) in plan.items() if before != after]
    for path in differences:
        print(('Would update: ' if args.mode != 'write' else 'Planned update: ') + str(path.relative_to(ROOT)))
    for key, changes in change_details.items():
        for change in changes:
            print('  ' + key + ': ' + change)
    if args.mode == 'check':
        return int(bool(differences))
    if args.mode == 'write':
        apply(plan)
        print('Applied selected MCP configuration.')
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, TypeError, RuntimeError) as error:
        print('Configuration failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
PY
