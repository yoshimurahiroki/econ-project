#!/usr/bin/env python3
"""Execute an adopted, explicit research DAG using the existing state store."""
import argparse
from contextlib import contextmanager, redirect_stdout
import copy
import hashlib
import importlib
import io
import itertools
import json
import math
import os
from pathlib import Path
import re
import selectors
import signal
import shutil
import subprocess
import sys
import tempfile
import uuid
import zipfile

import state

TOKEN = re.compile(r'\{(root|out:[A-Za-z0-9_.-]+|dep:[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+)\}')
MANUSCRIPT_TOKEN = re.compile(r'\{\{(stat|definition):([A-Za-z0-9_.-]+)\}\}')
NAME = re.compile(r'^[A-Za-z0-9_-]+$')


def fail(message):
    raise ValueError(message)


def path(root, value, exists=True):
    return state.relative(root, value, exists=exists)


def read_json(target):
    import research_evidence
    return research_evidence.read_json(target.read_bytes(), str(target))


RESEARCH_SCRIPTS = {'research.py', 'research_data.py', 'research_causal.py', 'research_dynamic.py',
                    'research_macro.py', 'research_macro_extended.py', 'research_dsge.py',
                    'research_numerics.py', 'research_markets.py', 'equity.py'}


def research_entry(root, stage):
    """Locate the invoked ERS program in its source, deployed or flat runtime."""
    argv = stage.get('argv', [])
    if not argv:
        return None
    runtime = stage.get('runtime')
    if runtime:
        if runtime['language'] != 'python':
            return None
        index = len(runtime['probe_argv'])
    elif re.fullmatch(r'(?:python|pypy)(?:\d+(?:\.\d+)*)?(?:\.exe)?', Path(argv[0]).name):
        index = 1
        while index < len(argv) and argv[index].startswith('-'):
            option = argv[index]
            if option in {'-', '-c', '-m'}:
                return None
            index += 2 if option in {'-W', '-X', '--check-hash-based-pycs'} else 1
            if option == '--':
                break
    else:
        index = 0
    if index >= len(argv):
        return None
    target = Path(argv[index].replace('{root}', str(root)))
    name = 'research.py' if target.name == 'research_estimator.py' else target.name
    if name not in RESEARCH_SCRIPTS or not target.is_absolute():
        return None
    target = target.resolve()
    runtime_directory = Path(__file__).resolve().parent
    sources = {(base / 'skills/econ-data/scripts' / name).resolve()
               for base in {root, root / '.agents', runtime_directory.parent}}
    alias = 'research_estimator.py' if name == 'research.py' else name
    sources.update((base / alias).resolve() for base in {root, runtime_directory, target.parent}
                   if (base / 'RESOURCES.json').is_file())
    if target not in sources:
        if not target.is_file() or not any(source.is_file() and state.digest(source) == state.digest(target)
                                           for source in sources):
            return None
    return index, name


def specification_inputs(root, stage, deps=None):
    """Resolve inputs read by the existing research entry points, using their path bases."""
    argv = stage.get('argv', [])
    entry = research_entry(root, stage)
    if entry is None:
        return [], []
    index, script = entry
    positional, skip = [], False
    for arg in argv[index + 1:]:
        if skip:
            skip = False
        elif arg in {'-o', '--output', '--root', '--rscript'}:
            skip = True
        elif arg == '--output-record' or any(arg.startswith(option + '=') for option in ('--output', '--root', '--rscript')):
            continue
        elif arg.startswith('-o'):
            continue
        else:
            positional.append(arg)
    if len(positional) < 2:
        return [], []
    command = positional[0]
    dependencies = {} if deps is None else deps

    def argument(value):
        def replace(match):
            token = match.group(1)
            if token == 'root':
                return str(root)
            parts = token.split(':')
            if parts[0] == 'dep' and tuple(parts[1:]) in dependencies:
                return str(dependencies[tuple(parts[1:])])
            return match.group(0)
        result = TOKEN.sub(replace, value)
        return None if '{' in result else result

    found, specifications = set(), []

    def reference(value, base):
        value = value.get('path') if isinstance(value, dict) else value
        if value is None:
            return None
        if not isinstance(value, str) or not value:
            fail('Research input reference must contain a nonempty path')
        target = Path(value)
        if not target.is_absolute():
            if base is None:
                fail('Research data commands with relative spec inputs require an explicit --root')
            target = base / target
        target = target.resolve()
        try:
            relative = target.relative_to(root).as_posix()
        except ValueError:
            fail('Research spec input must be inside the project: ' + str(target))
        found.add(path(root, relative))
        return target

    count = 2 if script == 'research_markets.py' and command == 'counterfactual' else 1
    for item in positional[1:1 + count]:
        value = argument(item)
        if value is None or value == '-':
            continue
        if not Path(value).is_absolute():
            fail('Research spec arguments must use {root}, a dependency reference or an absolute path')
        source = reference(value, root)
        spec = read_json(source)
        if not isinstance(spec, dict):
            fail('Research specification must be an object: ' + str(source))
        specifications.append(spec)
        base = source.parent
        if script in {'research_data.py', 'equity.py'}:
            roots = [argument(argv[i + 1] if arg == '--root' else arg.split('=', 1)[1])
                     for i, arg in enumerate(argv) if arg.startswith('--root=') or arg == '--root' and i + 1 < len(argv)]
            declared_root = roots[-1] if roots else None
            base = Path(declared_root) if declared_root and Path(declared_root).is_absolute() else None
        if script == 'equity.py':
            pending = [spec]
            while pending:
                node = pending.pop()
                if isinstance(node, dict):
                    for key, value in node.items():
                        if key in {'products', 'agents', 'reference_products', 'observations'} and isinstance(value, str):
                            reference(value, base)
                        elif isinstance(value, (dict, list)):
                            pending.append(value)
                elif isinstance(node, list):
                    pending.extend(node)
            continue
        if script == 'research_markets.py' and command == 'counterfactual':
            continue
        for key in ('data', 'train_data', 'evaluation_data', 'fit_path'):
            value = spec.get(key)
            if isinstance(value, str) or isinstance(value, dict) and 'path' in value:
                reference(value, base)
        for key in ('base', 'geography', 'source', 'saved_solution', 'yaml_model', 'observations'):
            value = spec.get(key)
            if isinstance(value, dict) and 'path' in value:
                reference(value, base)
        scenario = spec.get('scenario', {})
        if isinstance(scenario, dict) and isinstance(scenario.get('saved_solution'), dict):
            reference(scenario['saved_solution'], base)
        sample = spec.get('sample', {})
        if isinstance(sample, dict) and sample.get('policy') == 'fitted':
            reference(sample['result'], base)
        if isinstance(spec.get('data_record'), dict):
            record_path = reference(spec['data_record'], base)
            record = read_json(record_path)
            reference(record['table'], record_path.parent)
        sql = spec.get('sql', {})
        if not isinstance(sql, dict) or not isinstance(sql.get('tables', {}), dict):
            fail('SQL specification requires its declared tables mapping')
        for table in sql.get('tables', {}).values():
            reference(table, base)
        for join in spec.get('joins', []):
            if isinstance(join, dict) and 'table' in join:
                reference(join['table'], base)
        params = spec.get('params')
        if isinstance(params, dict) and 'path' in params:
            reference(params, base)
        model = spec.get('model_definition', {})
        if isinstance(model, dict) and 'module' in model:
            reference(model['module'], base)
        callbacks = spec.get('moment_functions', spec.get('moments', {}))
        if isinstance(callbacks, dict) and 'module' in callbacks:
            reference(callbacks['module'], base)
        options = spec.get('options', {})
        if isinstance(options, dict):
            for key in ('baseline_result', 'assignment_result', 'model_file', 'evaluation_data', 'adjacency'):
                if key in options:
                    reference(options[key], base)
            for value in options.get('model_dependencies', []):
                reference(value, base)
            if spec.get('method') in {'network_spillover', 'spatial_lag'} and 'weights' in options:
                reference(options['weights'], base)
    return sorted(found - set(stage['inputs'])), specifications


def execution_stage(root, stage, deps=None):
    """Add actual spec inputs and their table readers without changing the adopted manifest."""
    effective = copy.deepcopy(stage)
    if deps and 'argv' in effective:
        for (producer, name), target in deps.items():
            token = '{dep:' + producer + ':' + name + '}'
            effective['argv'] = [arg.replace(token, str(target)) for arg in effective['argv']]
    referenced, specifications = specification_inputs(root, effective, deps)
    effective['inputs'] = list(dict.fromkeys([*stage['inputs'], *referenced]))
    if 'runtime' in effective and (research_entry(root, effective) is not None
            or any(Path(name).name == 'research_data.py' for name in effective['inputs'])):
        formats = {Path(name).suffix.lower() for name in
                   [*effective['inputs'], *effective['outputs'].values(), *(deps or {}).values()]}
        formats.update('.' + spec['output_format'] for spec in specifications
                       if spec.get('output_format') in {'parquet', 'arrow'})
        typed = formats.intersection({'.parquet', '.arrow', '.feather', '.ipc'})
        sql = any('sql' in spec for spec in specifications)
        for runtime in [effective['runtime'], *effective['runtime'].get('companions', [])]:
            packages = runtime.setdefault('packages', {})
            if runtime['language'] == 'python':
                declared = {re.sub(r'[-_.]+', '-', name).lower() for name in packages}
                if (typed or sql) and 'pyarrow' not in declared:
                    packages['pyarrow'] = None
                if sql and 'duckdb' not in declared:
                    packages['duckdb'] = None
            elif runtime['language'] == 'r' and typed:
                packages.setdefault('arrow', None)
            elif runtime['language'] == 'julia' and formats.intersection({'.csv', '.parquet', '.arrow', '.feather', '.ipc'}):
                for name in ('Tables', 'DataFrames'):
                    packages.setdefault(name, None)
                if '.csv' in formats:
                    packages.setdefault('CSV', None)
                if '.parquet' in typed:
                    packages.setdefault('Parquet2', None)
                if typed - {'.parquet'}:
                    packages.setdefault('Arrow', None)
    return effective


def bind_runtime_requirements(root, config, inputs):
    """Use the selected requirement files as the existing runtime's package pins."""
    requirements = config.get('requirements', [])
    if (not isinstance(requirements, list)
            or any(not isinstance(name, str) or name not in inputs for name in requirements)
            or len(requirements) != len(set(requirements))):
        fail('Runtime requirements must name distinct declared stage inputs')
    packages = dict(config.get('packages', {}))
    canonical = lambda name: re.sub(r'[-_.]+', '-', name).lower() if config['language'] == 'python' else name
    pins = {canonical(name): (name, version) for name, version in packages.items()}
    if len(pins) != len(packages):
        fail('Runtime package names must be distinct after normalization')
    sources = {}
    for name in requirements:
        content = (root / path(root, name)).read_text(encoding='utf-8')
        if config['language'] == 'python':
            rows = []
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                exact = re.fullmatch(r'([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9._+!-]*)', line)
                vcs = re.fullmatch(r'([A-Za-z0-9][A-Za-z0-9._-]*)\s*@\s*git\+(https://[^\s]+)@([0-9a-f]{40})', line)
                if exact:
                    rows.append(exact.groups())
                elif vcs:
                    package, url, commit = vcs.groups()
                    source = {'url': url.removesuffix('.git'), 'commit_id': commit}
                    key = canonical(package)
                    if key in sources and sources[key] != source:
                        fail('Conflicting source revisions for ' + package)
                    sources[key] = source
                    rows.append((package, None))
                else:
                    fail('Runtime requirements need exact versions or full Git commit references: ' + name)
        elif config['language'] == 'r':
            declared = json.loads(content)
            if not isinstance(declared.get('packages'), dict) or not isinstance(declared.get('r_version'), str):
                fail('R requirements need r_version and packages')
            if config.get('version', declared['r_version']) != declared['r_version']:
                fail('R runtime version conflicts with ' + name)
            config['version'] = declared['r_version']
            rows = declared['packages'].items()
        else:
            fail('Use Julia Project/Manifest files in runtime.files')
        for package, version in rows:
            if (not isinstance(package, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', package)
                    or (version is not None and (not isinstance(version, str) or not version))):
                fail('Invalid package pin in ' + name)
            key = canonical(package)
            if key in pins:
                previous_name, previous_version = pins[key]
                if previous_version is not None and version is not None and previous_version != version:
                    fail('Conflicting runtime versions for ' + package)
                pins[key] = (previous_name, previous_version or version)
            else:
                pins[key] = (package, version)
    config['packages'] = {name: version for name, version in pins.values()}
    config['files'] = list(dict.fromkeys([*config.get('files', []), *requirements]))
    return sources


def execution_environment(root, stage):
    names = stage.get('inherit_env', [])
    environment = {name: os.environ[name] for name in names if name in os.environ}
    if len(environment) != len(names):
        fail('An inherited environment variable is missing or duplicated')
    environment.update(stage.get('env', {}))
    companions = stage.get('runtime', {}).get('companions', [])
    entry = research_entry(root, stage) if companions else None
    if entry is None:
        return environment
    languages = {'research_causal.py': ('r', 'julia'), 'research_data.py': ('r',)}
    for language in languages.get(entry[1], ()):
        selected = [runtime for runtime in companions if runtime['language'] == language]
        if not selected:
            continue
        if len(selected) != 1:
            fail(f'The research entry requires one selected {language} companion')
        prefix = selected[0]['probe_argv']
        variable = 'ERS_' + language.upper() + '_ARGV'
        if variable in environment:
            try:
                supplied = json.loads(environment[variable])
            except ValueError:
                fail(variable + ' must contain the declared companion prefix')
            if supplied != prefix:
                fail(variable + ' conflicts with the declared companion')
        environment[variable] = json.dumps(prefix)
    return environment


def environment_hashes(environment):
    """Bind exact child environment values without persisting inherited secrets."""
    return {name: state.content_hash(value) for name, value in environment.items()}


def call(root, store, *args):
    output = io.StringIO()
    with redirect_stdout(output):
        state.main(['--root', str(root), '--store', store, *args])
    return json.loads(output.getvalue())


class ResearchInterrupted(KeyboardInterrupt):
    def __init__(self, signum):
        super().__init__('Research execution interrupted by signal ' + str(signum))
        self.signum = signum


@contextmanager
def interruption_signals():
    def stop(signum, frame):
        raise ResearchInterrupted(signum)
    previous = {signum: signal.signal(signum, stop) for signum in (signal.SIGINT, signal.SIGTERM)}
    try:
        yield
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def run_process(argv, *, cwd=None, env=None, observation=None, stdout_limit=65536,
                complete_stdout=False, started=None):
    """Drain both pipes with bounded diagnostics and stop the child group on interruption."""
    observation = {} if observation is None else observation
    streams = {'stdout': bytearray(), 'stderr': bytearray()}
    counts = {'stdout': 0, 'stderr': 0}
    log = bytearray()
    process = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               start_new_session=os.name == 'posix')
    observation.update(launched=True, pid=process.pid, process_group=process.pid if os.name == 'posix' else None)
    try:
        if started is not None:
            started(observation)
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, 'stdout')
            selector.register(process.stderr, selectors.EVENT_READ, 'stderr')
            while selector.get_map():
                for key, _ in selector.select():
                    chunk = os.read(key.fileobj.fileno(), 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    name = key.data
                    counts[name] += len(chunk)
                    buffer = streams[name]
                    buffer.extend(chunk)
                    limit = stdout_limit if name == 'stdout' else 65536
                    if len(buffer) > limit:
                        del buffer[:len(buffer) - limit]
                    log.extend(chunk)
                    if len(log) > 65536:
                        del log[:len(log) - 65536]
        process.wait()
    except BaseException:
        if os.name == 'posix':
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        elif process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        finally:
            if os.name == 'posix':
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.wait()
        raise
    finally:
        process.stdout.close()
        process.stderr.close()
        observation.update(returncode=process.returncode, log=log.decode('utf-8', errors='replace'),
                           output_bytes=sum(counts.values()), log_truncated=sum(counts.values()) > len(log))
    if complete_stdout and counts['stdout'] > stdout_limit:
        fail('Command response exceeds the supported size: ' + str(argv[0]))
    return subprocess.CompletedProcess(argv, process.returncode,
        streams['stdout'].decode('utf-8', errors='replace'), streams['stderr'].decode('utf-8', errors='replace'))


def load(root, store):
    data = json.loads((root / store).read_text())
    state.migrate(data)
    return data['tasks']


def expand(manifest):
    """Expand a finite adopted grid into ordinary, independently recorded stages."""
    stages = list(manifest['stages'])
    for grid in manifest.get('grids', []):
        if not isinstance(grid, dict) or set(grid) - {'prefix', 'parameters', 'order', 'budget', 'seed', 'template'}:
            fail('Invalid grid fields')
        prefix, parameters, template = grid.get('prefix'), grid.get('parameters'), grid.get('template')
        if not isinstance(prefix, str) or not NAME.fullmatch(prefix) or not isinstance(parameters, dict) or not parameters or not isinstance(template, dict) or 'id' in template:
            fail('Grid needs a prefix, parameter values and a stage template without id')
        if any(not isinstance(k, str) or not NAME.fullmatch(k) or not isinstance(v, list) or not v or any(not isinstance(x, str) for x in v) or len(set(v)) != len(v) for k, v in parameters.items()):
            fail('Grid parameters must contain distinct string values')
        order = grid.get('order', sorted(parameters))
        if not isinstance(order, list) or len(order) != len(parameters) or set(order) != set(parameters):
            fail('Grid order must name each parameter once')
        budget = grid.get('budget')
        if budget is not None and (type(budget) is not int or budget < 1):
            fail('Grid budget must be a positive integer')
        seed = grid.get('seed')
        if seed is not None and (type(seed) is not int or seed < 0):
            fail('Grid seed must be a nonnegative integer')
        for index, values in enumerate(itertools.product(*(parameters[k] for k in order))):
            if budget is not None and index >= budget:
                break
            bindings = dict(zip(order, values))
            def substitute(value):
                if isinstance(value, str):
                    if '{grid:seed}' in value:
                        if seed is None:
                            fail('Grid seed placeholder requires a declared seed')
                        value = value.replace('{grid:seed}', str(seed))
                    for key, item in bindings.items():
                        value = value.replace('{param:' + key + '}', item)
                    if '{param:' in value:
                        fail('Unknown grid parameter')
                    return value
                if isinstance(value, list):
                    return [substitute(item) for item in value]
                if isinstance(value, dict):
                    return {key: substitute(item) for key, item in value.items()}
                return value
            stages.append({'id': prefix + '-' + str(index), **substitute(template),
                           'grid_meta': {'index': index, 'parameters': bindings, 'order': order,
                                         'budget': budget, 'seed': seed}})
    return stages


def protocol(root, stage):
    selection = stage['select']
    if not isinstance(selection, dict) or set(selection) != {'protocol', 'candidates'}:
        fail('Selection requires protocol and candidates')
    source = path(root, selection['protocol'])
    if source not in stage['inputs']:
        fail('Selection protocol must be a tracked input')
    value = read_json(root / source)
    if (not isinstance(value, dict) or not {'identity', 'evaluation_protocol', 'metrics', 'tie_break', 'on_failure', 'holdout'} <= set(value)
            or set(value) - {'identity', 'evaluation_protocol', 'metrics', 'tie_break', 'on_failure', 'holdout', 'seed', 'budget', 'axes'}):
        fail('Protocol requires identity, evaluation_protocol, metrics, tie_break, on_failure and holdout')
    identity = value['identity']
    if not isinstance(identity, dict) or set(identity) not in ({'estimand', 'evaluator', 'sample', 'partition'}, {'estimand', 'population', 'evaluator', 'sample', 'partition'}) or any(not isinstance(v, str) or not v for v in identity.values()):
        fail('Protocol identity requires estimand, evaluator, sample and partition')
    if not isinstance(value['evaluation_protocol'], dict) or not value['evaluation_protocol']:
        fail('Adopted evaluation_protocol must be a nonempty object')
    candidates = selection['candidates']
    if not isinstance(candidates, dict) or not candidates or any(not isinstance(k, str) or not NAME.fullmatch(k) or not isinstance(v, dict) or set(v) != {'stage', 'output'} for k, v in candidates.items()):
        fail('Candidates map names to stage and output')
    if 'seed' in value and (type(value['seed']) is not int or value['seed'] < 0):
        fail('Protocol seed must be a nonnegative integer')
    if 'seed' in value and value['evaluation_protocol'].get('seed') != value['seed']:
        fail('Evaluation protocol seed must match the adopted seed')
    if 'budget' in value and (type(value['budget']) is not int or value['budget'] < 1 or len(candidates) > value['budget']):
        fail('Candidates exceed the declared positive protocol budget')
    if not isinstance(value['tie_break'], list) or len(value['tie_break']) != len(candidates) or set(value['tie_break']) != set(candidates):
        fail('Tie break must order all candidate names')
    if value['on_failure'] not in ('block', 'exclude'):
        fail('Protocol must specify failed-trial treatment')
    if not isinstance(value['holdout'], list) or any(not isinstance(p, str) for p in value['holdout']):
        fail('Holdout must list tracked root-relative paths')
    for item in value['holdout']:
        path(root, item)
    if not isinstance(value['metrics'], list) or not value['metrics']:
        fail('Protocol needs ordered metrics')
    for m in value['metrics']:
        if not isinstance(m, dict) or set(m) - {'key', 'direction', 'min', 'max'} or m.get('direction') not in ('min', 'max') or not isinstance(m.get('key'), list) or not m['key'] or any(not isinstance(x, str) or not x for x in m['key']):
            fail('Metric needs a JSON key path and direction')
        if any(type(m[k]) not in (int, float) or not math.isfinite(m[k]) for k in ('min', 'max') if k in m) or ('min' in m and 'max' in m and m['min'] > m['max']):
            fail('Metric feasibility bounds must be finite and ordered')
    return value


def validate_checks(stage):
    checks = stage.get('checks', [])
    if not isinstance(checks, list):
        fail('Checks must be a list')
    for check in checks:
        if not isinstance(check, dict) or not isinstance(check.get('output'), str) or check['output'] not in stage['outputs']:
            fail('Check must select a declared output')
        if check.get('type') == 'json':
            if set(check) != {'type', 'output', 'fields'} or not isinstance(check['fields'], list) or not check['fields']:
                fail('JSON check requires declared fields')
            for field in check['fields']:
                if (not isinstance(field, dict) or set(field) - {'key', 'type', 'min', 'max', 'equals'}
                        or not isinstance(field.get('key'), list) or not field['key']
                        or any(not isinstance(k, str) or not k for k in field['key'])
                        or field.get('type') not in {'number', 'integer', 'string', 'object', 'array', 'boolean'}):
                    fail('JSON field check needs a key and supported type')
                for bound in ('min', 'max'):
                    if bound in field and (field['type'] not in {'number', 'integer'} or type(field[bound]) not in (int, float) or not math.isfinite(field[bound])):
                        fail('JSON bounds require finite numbers and a numeric field')
                if 'min' in field and 'max' in field and field['min'] > field['max']:
                    fail('JSON field bounds must be ordered')
        else:
            fail('Unknown output check')


def learning_metadata(root, stage):
    config = stage['learn']
    if not isinstance(config, dict) or set(config) != {'spec'} or not isinstance(config['spec'], str):
        fail('Learning requires a root-relative spec file')
    name = path(root, config['spec'])
    raw = state.gate.regular_bytes(root / name)
    data = state.gate.parse_json(raw)
    if (not isinstance(data, dict) or not {'output', 'conditions'} <= set(data)
            or set(data) - {'output', 'conditions', 'permitted_switches'}
            or not isinstance(data['output'], str) or data['output'] not in stage['outputs']
            or not isinstance(data['conditions'], dict) or not isinstance(data.get('permitted_switches', {}), dict)):
        fail('Learning spec needs a declared result output and typed condition references')
    for refs in (data['conditions'], data.get('permitted_switches', {})):
        for key, ref in refs.items():
            if (not isinstance(key, str) or not key or not isinstance(ref, dict) or set(ref) != {'output', 'path'}
                    or not isinstance(ref['output'], str) or ref['output'] not in {*stage['outputs'], 'research:execution'}
                    or not isinstance(ref['path'], list) or any(not isinstance(part, str) or not part for part in ref['path'])):
                fail('Learning references must select a declared stage output and JSON key path')
    return name, data, hashlib.sha256(raw).hexdigest()


def adaptive_protocol(root, stage):
    config = stage['adaptive']
    if (not isinstance(config, dict) or set(config) != {'protocol', 'history', 'round', 'batch', 'output'}
            or type(config['round']) is not int or config['round'] < 1
            or type(config['batch']) is not int or config['batch'] < 1
            or config['output'] not in stage['outputs'] or len(stage['outputs']) != 1):
        fail('Adaptive stage needs protocol, history, positive round and batch, and one output')
    source = path(root, config['protocol'])
    if source not in stage['inputs']:
        fail('Adaptive protocol must be a tracked input')
    raw = read_json(root / source)
    history = config['history']
    if not isinstance(history, dict) or not history or any(
            not isinstance(name, str) or not NAME.fullmatch(name) or not isinstance(ref, dict)
            or set(ref) != {'stage', 'output'} or ref['output'] not in stage['depends'].get(ref['stage'], [])
            for name, ref in history.items()):
        fail('Adaptive history must bind names to consumed completed results')
    if {(ref['stage'],ref['output']) for ref in history.values()} != {(d,n) for d,ns in stage['depends'].items() for n in ns}:
        fail('Adaptive dependencies must exactly match history')
    tie = raw.get('tie_break', []) if isinstance(raw, dict) else []
    fake = {'inputs':stage['inputs'], 'select':{'protocol':source,
            'candidates':{name:{'stage':'candidate','output':'result'} for name in tie}}}
    value = protocol(root, fake)
    if not set(history) <= set(value['tie_break']):
        fail('Adaptive history IDs must appear in the adopted tie-break order')
    if set(value['identity']) != {'estimand', 'population', 'sample', 'evaluator', 'partition'}:
        fail('Adaptive scientific identity requires estimand, population, sample, evaluator and partition')
    if not {'seed','budget','axes'} <= set(value) or value['budget'] <= len(history):
        fail('Adaptive protocol needs seed, axes, and budget greater than evaluated history')
    axes = value['axes']
    if not isinstance(axes, dict) or not axes:
        fail('Adaptive axes must be nonempty')
    for name, axis in axes.items():
        if (not isinstance(name,str) or not NAME.fullmatch(name) or not isinstance(axis,dict)
                or set(axis) != {'min','max','step'} or any(type(axis[k]) not in (int,float)
                or not math.isfinite(axis[k]) for k in ('min','max','step'))
                or axis['min'] >= axis['max'] or axis['step'] <= 0):
            fail('Each adaptive axis needs finite ordered bounds and positive step')
    if len(history)+config['batch'] > value['budget']:
        fail('Adaptive batch exceeds the total evaluation budget')
    partitions = value['evaluation_protocol'].get('partitions')
    if (not isinstance(partitions,dict) or set(partitions) != {'train','validation','holdout'}
            or any(not isinstance(v,list) or not v or any(not isinstance(x,str) or not x for x in v)
                   or len(set(v)) != len(v) for v in partitions.values())):
        fail('Adaptive evaluation requires train, validation and holdout paths')
    train, validation, held = (set(partitions[k]) for k in ('train','validation','holdout'))
    if train & validation or train & held or validation & held or held != set(value['holdout']):
        fail('Adaptive training, validation and held-out paths must be disjoint')
    membership = value['evaluation_protocol'].get('partition_membership')
    if (not isinstance(membership,dict) or set(membership) != {'train','validation','holdout'}
            or any(not isinstance(v,list) or not v or any(not isinstance(x,str) or not x for x in v)
                   or len(set(v)) != len(v) for v in membership.values())):
        fail('Adaptive protocol requires explicit unique observation IDs in each partition')
    mt,mv,mh = (set(membership[k]) for k in ('train','validation','holdout'))
    if mt & mv or mt & mh or mv & mh:
        fail('Adaptive partition observation IDs must be disjoint')
    for name in train | validation | held:
        path(root, name)
    return value


def adapt(root, stage, destinations, deps):
    config, p = stage['adaptive'], adaptive_protocol(root, stage)
    rows = []
    for name, ref in config['history'].items():
        target = deps[(ref['stage'], ref['output'])]
        result = read_json(target)
        if result.get('identity') != p['identity'] or result.get('protocol') != p['evaluation_protocol']:
            fail('Adaptive history changed the adopted scientific identity or evaluation protocol')
        expected_membership = {k:p['evaluation_protocol']['partition_membership'][k] for k in ('train','validation')}
        if result.get('partition_membership') != expected_membership:
            fail('Adaptive history must report the adopted training and validation observation IDs')
        parameters = result.get('parameters')
        if (not isinstance(parameters,dict) or set(parameters) != set(p['axes']) or any(
                type(parameters[k]) not in (int,float) or not math.isfinite(parameters[k])
                or not (axis['min'] <= parameters[k] <= axis['max']) for k,axis in p['axes'].items())):
            fail('History parameters must lie in the adopted axes')
        metrics = []
        for metric in p['metrics']:
            number = key_value(result, metric['key'])
            if type(number) not in (int,float) or not math.isfinite(number): fail('History score must be finite')
            if ('min' in metric and number < metric['min']) or ('max' in metric and number > metric['max']):
                fail('Adaptive history violates a metric feasibility bound')
            metrics.append(number)
        rows.append({'candidate':name,'parameters':parameters,'metrics':metrics,'sha256':state.digest(target)})
    rows.sort(key=lambda row: tuple(v if metric['direction']=='min' else -v
              for v,metric in zip(row['metrics'],p['metrics'])) + (p['tie_break'].index(row['candidate']),))
    best = rows[0]['parameters']; existing = {tuple(row['parameters'][k] for k in sorted(p['axes'])) for row in rows}
    proposed = []
    choices = [(name,sign) for name in sorted(p['axes']) for sign in (-1,1)]
    choices.sort(key=lambda row: hashlib.sha256(f"{p['seed']}:{config['round']}:{row[0]}:{row[1]}".encode()).hexdigest())
    for axis, sign in choices:
        candidate = dict(best); bounds = p['axes'][axis]
        candidate[axis] = min(bounds['max'],max(bounds['min'],
            best[axis] + sign*bounds['step'] * 0.5**(config['round']-1)))
        key = tuple(candidate[k] for k in sorted(p['axes']))
        if key in existing: continue
        existing.add(key)
        proposed.append({'id':f"r{config['round']}-{len(proposed)}", 'parameters':candidate,
                         'identity':p['identity'], 'protocol':p['evaluation_protocol']})
        if len(proposed) == config['batch']: break
    if len(proposed) != config['batch']:
        fail('Requested adaptive batch has insufficient distinct coordinate neighbors')
    output = {'identity':p['identity'], 'protocol':p['evaluation_protocol'],
              'protocol_sha256':state.digest(root/config['protocol']), 'round':config['round'],
              'seed':p['seed'], 'budget':p['budget'], 'axes':p['axes'],
              'history':rows, 'center':rows[0]['candidate'], 'candidates':proposed}
    destinations[config['output']].write_text(json.dumps(output,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def validate(root, manifest, profile=None):
    if not isinstance(manifest, dict) or set(manifest) - {'pipeline', 'stages', 'grids', 'profiles'} or not {'pipeline', 'stages'} <= set(manifest) or not NAME.fullmatch(manifest.get('pipeline', '')):
        fail('Manifest requires pipeline ID and stages')
    if not isinstance(manifest['stages'], list) or not isinstance(manifest.get('grids', []), list):
        fail('Stages and grids must be lists')
    stages = copy.deepcopy(expand(manifest))
    profiles = manifest.get('profiles', {})
    if not isinstance(profiles, dict) or any(not isinstance(k, str) or not NAME.fullmatch(k) for k in profiles):
        fail('Profiles must map simple names to selections')
    for name, config in profiles.items():
        if (not isinstance(config, dict) or set(config) - {'stages', 'overrides'}
                or not isinstance(config.get('stages'), list) or not config['stages']
                or any(not isinstance(x, str) or not NAME.fullmatch(x) for x in config['stages'])
                or len(set(config['stages'])) != len(config['stages'])
                or not isinstance(config.get('overrides', {}), dict)):
            fail('Profile requires distinct stage IDs and optional overrides: ' + name)
        if any(k not in config['stages'] or not isinstance(v, dict) or 'id' in v or 'grid_meta' in v
               for k, v in config.get('overrides', {}).items()):
            fail('Profile overrides must target selected stages without changing their IDs')
    if profile is not None:
        if profile not in profiles:
            fail('Unknown profile: ' + str(profile))
        config = profiles[profile]
        available = {s.get('id') for s in stages if isinstance(s, dict)}
        if set(config['stages']) - available:
            fail('Profile selects unknown stages')
        stages = [{**s, **config.get('overrides', {}).get(s['id'], {})}
                  for s in stages if s.get('id') in config['stages']]
    if not stages:
        fail('Stages must be a nonempty list')
    by_id = {}
    for s in stages:
        if not isinstance(s, dict) or set(s) - {'id', 'inputs', 'depends', 'outputs', 'argv', 'env', 'inherit_env', 'executables', 'render', 'select', 'when', 'checks', 'grid_meta', 'learn', 'runtime', 'reviewed_results', 'adaptive', 'final'}:
            fail('Invalid stage fields')
        key = s.get('id', '')
        if not NAME.fullmatch(key) or key in by_id:
            fail('Stage IDs must be unique simple names')
        if not isinstance(s.get('inputs'), list) or any(not isinstance(x, str) for x in s['inputs']):
            fail('Every stage requires an inputs list')
        for x in s['inputs']:
            path(root, x)
        if len(s['inputs']) != len(set(s['inputs'])):
            fail('Duplicate inputs')
        if not isinstance(s.get('depends'), dict) or not isinstance(s.get('outputs'), dict) or not s['outputs']:
            fail('Stages require depends and nonempty outputs mappings')
        for dep, names in s['depends'].items():
            if not NAME.fullmatch(dep) or not isinstance(names, list) or not names or len(names) != len(set(names)) or any(not isinstance(n, str) or not NAME.fullmatch(n) for n in names):
                fail('Dependencies require stage IDs and distinct output names')
        output_paths = []
        for name, target in s['outputs'].items():
            if not NAME.fullmatch(name) or not isinstance(target, str):
                fail('Invalid output declaration')
            p = Path(target)
            if p.is_absolute() or not target or '..' in p.parts or target in {'.', ''}:
                fail('Output paths must be relative and confined')
            output_paths.append(p)
        if len(set(output_paths)) != len(output_paths) or any(a in b.parents for a in output_paths for b in output_paths):
            fail('Output paths must be distinct files')
        validate_checks(s)
        if sum(k in s for k in ('argv', 'render', 'select', 'adaptive')) != 1:
            fail('Choose argv, render, select or adaptive for each stage')
        if 'learn' in s:
            if 'argv' not in s:
                fail('Learning requires a command with an actual execution return')
            learning_metadata(root, s)
        if 'argv' in s and (not isinstance(s['argv'], list) or not s['argv'] or any(not isinstance(a, str) or not a for a in s['argv'])):
            fail('argv must contain nonempty strings')
        executables = s.get('executables', [])
        if (not isinstance(executables, list)
                or any(not isinstance(name, str) or not name or '{' in name for name in executables)
                or len(executables) != len(set(executables))
                or ('executables' in s and 'argv' not in s)):
            fail('Executables must list distinct command paths or names for an argv stage')
        if not isinstance(s.get('env', {}), dict) or any(not isinstance(k, str) or not isinstance(v, str) or '=' in k or not k for k, v in s.get('env', {}).items()):
            fail('env must map names to strings')
        if not isinstance(s.get('inherit_env', []), list) or any(not isinstance(v, str) or not v for v in s.get('inherit_env', [])):
            fail('inherit_env must list environment names')
        if 'runtime' in s:
            runtime = s['runtime']
            if (not isinstance(runtime, dict) or set(runtime) - {'language', 'probe_argv', 'version', 'packages', 'files', 'companions', 'apis', 'requirements'}
                    or runtime.get('language') not in {'python', 'r', 'julia'} or 'argv' not in s
                    or not isinstance(runtime.get('probe_argv'), list) or not runtime['probe_argv']
                    or any(not isinstance(a, str) or not a or '{' in a for a in runtime['probe_argv'])
                    or s['argv'][:len(runtime['probe_argv'])] != runtime['probe_argv']
                    or not isinstance(runtime.get('packages', {}), dict)
                    or any(not isinstance(k, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', k)
                           or (v is not None and (not isinstance(v, str) or not v)) for k, v in runtime.get('packages', {}).items())
                    or not isinstance(runtime.get('files', []), list)
                    or any(not isinstance(x, str) or x not in s['inputs'] for x in runtime.get('files', []))
                    or ('version' in runtime and (not isinstance(runtime['version'], str) or not runtime['version']))):
                fail('Runtime requires a matching argv prefix, language, package selections and tracked files')
            companions = runtime.get('companions', [])
            if not isinstance(companions, list):
                fail('Runtime companions must be a finite list')
            identities = set()
            for companion in companions:
                if (not isinstance(companion, dict) or set(companion) - {'language','probe_argv','version','packages','files','apis','requirements'}
                        or companion.get('language') not in {'r','julia'}
                        or not isinstance(companion.get('probe_argv'),list) or not companion['probe_argv']
                        or any(not isinstance(a,str) or not a or '{' in a for a in companion['probe_argv'])
                        or not Path(companion['probe_argv'][0]).is_absolute()
                        or not isinstance(companion.get('packages',{}),dict)
                        or any(not isinstance(k,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*',k)
                               or (v is not None and (not isinstance(v,str) or not v))
                               for k,v in companion.get('packages',{}).items())
                        or not isinstance(companion.get('files',[]),list)
                        or any(not isinstance(x,str) or x not in s['inputs'] for x in companion.get('files',[]))
                        or ('version' in companion and (not isinstance(companion['version'],str) or not companion['version']))):
                    fail('Runtime companion needs an absolute executable, language, package selections and tracked files')
                companion_identity = (companion['language'],tuple(companion['probe_argv']))
                if companion_identity in identities: fail('Runtime companions must be distinct')
                identities.add(companion_identity)
            for selected in [runtime, *companions]:
                bind_runtime_requirements(root, selected, s['inputs'])
                apis = selected.get('apis', [])
                if not isinstance(apis, list) or (apis and selected['language'] not in {'python', 'r'}):
                    fail('Runtime APIs require a Python or R runtime and a list of contracts')
                for api in apis:
                    if (not isinstance(api, dict) or set(api) != {'package', 'symbol', 'positional', 'keywords'}
                            or not isinstance(api['package'], str) or not selected.get('packages', {}).get(api['package'])
                            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+!-]*', selected['packages'][api['package']])
                            or not isinstance(api['symbol'], str)
                            or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+', api['symbol'] if selected['language'] == 'python' else 'x.' + api['symbol'])
                            or isinstance(api['positional'], bool) or not isinstance(api['positional'], int) or api['positional'] < 0
                            or not isinstance(api['keywords'], list)
                            or any(not isinstance(k, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*' if selected['language'] == 'python' else r'[A-Za-z_][A-Za-z0-9_.]*', k) for k in api['keywords'])
                            or len(set(api['keywords'])) != len(api['keywords'])):
                        fail('Runtime API requires a selected package with explicit version, symbol, positional count and keyword names')
        if 'reviewed_results' in s:
            reviewed = s['reviewed_results']
            if (not isinstance(reviewed, dict) or not reviewed
                    or any(not isinstance(outputs, dict) or not outputs
                           or any(name not in s['depends'].get(dep, []) or not isinstance(digest, str)
                                  or not re.fullmatch(r'[0-9a-f]{64}', digest) for name, digest in outputs.items())
                           for dep, outputs in reviewed.items())):
                fail('Reviewed results must map declared dependencies to SHA-256 hashes')
        by_id[key] = s
    visiting, done, ordered = set(), set(), []
    def visit(key):
        if key in visiting:
            fail('Stage dependency cycle')
        if key in done:
            return
        if key not in by_id:
            fail(f'Unknown stage: {key}')
        visiting.add(key)
        for dep, names in by_id[key]['depends'].items():
            visit(dep)
            if set(names) - set(by_id[dep]['outputs']):
                fail(f'Unknown output from {dep}')
        visiting.remove(key)
        done.add(key)
        ordered.append(by_id[key])
    for key in by_id:
        visit(key)
    for s in stages:
        effective = execution_stage(root, s)
        s.clear()
        s.update(effective)
        if 'when' in s:
            w = s['when']
            if not isinstance(w, dict) or set(w) != {'stage', 'output', 'equals'} or not isinstance(w['equals'], str) or w['output'] not in s['depends'].get(w['stage'], []):
                fail('Conditional stages must consume their selector output')
            if 'select' not in by_id[w['stage']]:
                fail('Conditional stage requires a selection stage')
            if w['equals'] not in by_id[w['stage']]['select']['candidates']:
                fail('Conditional stage must name an adopted candidate')
        if 'adaptive' in s:
            adaptive_protocol(root, s)
        if 'select' in s:
            p = protocol(root, s)
            if len(s['outputs']) != 1:
                fail('Selection declares exactly one output')
            candidates = s['select']['candidates']
            for candidate in candidates.values():
                if candidate['output'] not in s['depends'].get(candidate['stage'], []):
                    fail('Each candidate must name a declared consumed output')
            if set(s['depends']) != {v['stage'] for v in candidates.values()}:
                fail('Selection dependencies must be exactly its candidate stages')
            protected = set(p['holdout'])
            if protected.intersection(s['inputs']):
                fail('Selection references a held-out input')
            def check_ancestors(key, seen):
                if key in seen:
                    return
                branch = by_id[key]
                if protected.intersection(branch['inputs']) or any(
                        re.search(r'(?<![A-Za-z0-9_.-])' + re.escape(item) + r'(?![A-Za-z0-9_.-])', arg)
                        for item in protected for arg in branch.get('argv', [])):
                    fail('Candidate or its ancestor references a held-out input')
                for parent in branch['depends']:
                    check_ancestors(parent, seen | {key})
            for candidate in candidates.values():
                check_ancestors(candidate['stage'], set())
            for candidate in stages:
                if 'learn' in candidate:
                    check_ancestors(candidate['id'], set())
    adaptive_stages = [s for s in stages if 'adaptive' in s]
    if adaptive_stages:
        protocols = {s['adaptive']['protocol'] for s in adaptive_stages}
        for protocol_name in protocols:
            group = [s for s in adaptive_stages if s['adaptive']['protocol'] == protocol_name]
            p = adaptive_protocol(root, group[0])
            selectors = [s for s in stages if s.get('select',{}).get('protocol') == protocol_name]
            finals = [s for s in stages if s.get('final',{}).get('protocol') == protocol_name]
            if len(selectors) != 1 or len(finals) != 1:
                fail('Adaptive search requires one final selection and one held-out evaluation')
            selector, final = selectors[0], finals[0]
            f = final['final']
            if (set(f) != {'protocol','selector','output'} or f['output'] not in final['outputs'] or f['protocol'] not in final['inputs']
                    or not isinstance(f['selector'],dict) or set(f['selector']) != {'stage','output'}
                    or f['selector']['stage'] != selector['id']
                    or f['selector']['output'] not in final['depends'].get(selector['id'], [])
                    or 'argv' not in final or not set(p['holdout']) <= set(final['inputs'])):
                fail('Final evaluation must consume the selected winner and held-out inputs')
            selected_refs = {(r['stage'],r['output']) for r in selector['select']['candidates'].values()}
            if len(selected_refs) != len(selector['select']['candidates']):
                fail('Adaptive selection must name distinct evaluated outputs')
            if any((r['stage'],r['output']) not in selected_refs for a in group for r in a['adaptive']['history'].values()):
                fail('Final selection must include the evaluated adaptive history')
            for ref in selector['select']['candidates'].values():
                def ancestor_inputs(key, seen):
                    if key in seen: return set()
                    branch = by_id[key]
                    return set(branch['inputs']).union(*(ancestor_inputs(parent, seen | {key}) for parent in branch['depends']))
                expected_inputs = set(p['evaluation_protocol']['partitions']['train'] + p['evaluation_protocol']['partitions']['validation'])
                if not expected_inputs <= ancestor_inputs(ref['stage'], set()):
                    fail('Each adaptive candidate must track the adopted training and validation inputs')
            for a in group:
                downstream = [r for r in selector['select']['candidates'].values()
                              if a['adaptive']['output'] in by_id[r['stage']]['depends'].get(a['id'], [])]
                consumers = [stage for stage in stages if 'argv' in stage and
                             a['adaptive']['output'] in stage['depends'].get(a['id'], [])]
                if (len(downstream) != a['adaptive']['batch'] or len(consumers) != len(downstream)
                        or {stage['id'] for stage in consumers} != {ref['stage'] for ref in downstream}):
                    fail('Every proposed candidate must feed exactly one selected evaluation')
            protected = set(p['holdout'])
            for stage in stages:
                if stage is final: continue
                if protected.intersection(stage['inputs']) or any(
                        re.search(r'(?<![A-Za-z0-9_.-])' + re.escape(item) + r'(?![A-Za-z0-9_.-])', arg)
                        for item in protected for arg in stage.get('argv', [])):
                    fail('Only the final evaluation may access the held-out input')
        if any('final' in s and s['final'].get('protocol') not in protocols for s in stages):
            fail('Final evaluation must belong to an adaptive protocol')
    elif any('final' in s for s in stages):
        fail('Final evaluation requires an adaptive search')
    return ordered


def key_value(value, keys):
    for key in keys:
        if not isinstance(key, str) or not isinstance(value, dict) or key not in value:
            fail('Missing JSON key: ' + str(key))
        value = value[key]
    return value


def output_checks(stage, destinations):
    """Validate declared output structure, values and the current stage log."""
    reports = []
    for check in stage.get('checks', []):
        target = destinations[check['output']]
        data = read_json(target)
        for field in check['fields']:
            value = key_value(data, field['key'])
            types = {'number': lambda x: type(x) in (float, int) and math.isfinite(x),
                     'integer': lambda x: type(x) is int, 'string': lambda x: isinstance(x, str),
                     'object': lambda x: isinstance(x, dict), 'array': lambda x: isinstance(x, list),
                     'boolean': lambda x: type(x) is bool}
            kind = field.get('type')
            if not types[kind](value):
                fail('JSON field has incorrect type: ' + '.'.join(field['key']))
            if 'equals' in field and (type(value) is not type(field['equals']) or value != field['equals']):
                fail('JSON field differs from its required value: ' + '.'.join(field['key']))
            if ('min' in field and value < field['min']) or ('max' in field and value > field['max']):
                fail('JSON field is outside its declared bounds: ' + '.'.join(field['key']))
        reports.append({'type': 'json', 'output': check['output'], 'fields': check['fields']})
    return reports


def choose(root, stage, destinations, deps, failed_candidates):
    p = protocol(root, stage)
    failures, feasible, infeasible = {}, [], []
    parameter_vectors, parameters_by_name = set(), {}
    candidate_protocol = p['evaluation_protocol']
    for name, ref in stage['select']['candidates'].items():
        if name in failed_candidates:
            failures[name] = failed_candidates[name]
            continue
        data = read_json(deps[(ref['stage'], ref['output'])])
        if not isinstance(data, dict) or data.get('identity') != p['identity']:
            fail('Candidate estimand, evaluator, sample or partition differs from the adopted protocol: ' + name)
        if 'axes' in p:
            parameters = data.get('parameters')
            if (not isinstance(parameters,dict) or set(parameters) != set(p['axes']) or any(
                    type(parameters[k]) not in (int,float) or not math.isfinite(parameters[k])
                    or not axis['min'] <= parameters[k] <= axis['max'] for k,axis in p['axes'].items())):
                fail('Candidate parameters exceed the adopted axes: ' + name)
            vector = tuple(parameters[k] for k in sorted(p['axes']))
            if vector in parameter_vectors: fail('Adaptive selection contains duplicate parameter vectors')
            parameter_vectors.add(vector)
            parameters_by_name[name] = parameters
            expected_membership = {k:p['evaluation_protocol']['partition_membership'][k] for k in ('train','validation')}
            if data.get('partition_membership') != expected_membership:
                fail('Candidate must report the adopted training and validation observation IDs: ' + name)
        used_protocol = data.get('protocol')
        if not isinstance(used_protocol, dict) or used_protocol != candidate_protocol:
            fail('Candidate execution protocol differs from the adopted evaluation protocol: ' + name)
        metrics, allowed = [], True
        for metric in p['metrics']:
            value = key_value(data, metric['key'])
            if type(value) not in (int, float) or not math.isfinite(value):
                fail('Candidate metric must be finite and numeric: ' + name)
            if ('min' in metric and value < metric['min']) or ('max' in metric and value > metric['max']):
                allowed = False
            metrics.append(value)
        (feasible if allowed else infeasible).append((name, metrics))
    if failures and p['on_failure'] == 'block':
        fail('Selection protocol blocks failed candidates')
    if not feasible:
        fail('No feasible completed candidate')
    def rank(row):
        name, values = row
        return tuple(v if m['direction'] == 'min' else -v for v, m in zip(values, p['metrics'])) + (p['tie_break'].index(name),)
    feasible.sort(key=rank)
    result = {'selected': feasible[0][0], 'identity': p['identity'],
              'protocol_sha256': state.digest(root / stage['select']['protocol']),
              'candidate_protocol': candidate_protocol,
              'ranked': [{'candidate': name, 'metrics': values} for name, values in feasible],
              'infeasible': [{'candidate': name, 'metrics': values} for name, values in infeasible],
              'failed': failures}
    if 'axes' in p:
        result['parameters'] = parameters_by_name[result['selected']]
    next(iter(destinations.values())).write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def render(root, stage, destinations, deps):
    spec = stage['render']
    if (not isinstance(spec, dict) or not {'template', 'output', 'statistics'} <= set(spec)
            or set(spec) - {'template', 'output', 'statistics', 'definitions'}):
        fail('render requires template, output and statistics, with optional definitions')
    template = path(root, spec['template'])
    definitions = spec.get('definitions', {})
    if (template not in stage['inputs'] or spec['output'] not in destinations
            or not isinstance(spec['statistics'], dict) or not isinstance(definitions, dict)):
        fail('Render template must be an input and output must be declared')
    text = (root / template).read_text(encoding='utf-8')
    tokens = set(MANUSCRIPT_TOKEN.findall(text))
    if tokens != {('stat', key) for key in spec['statistics']} | {('definition', key) for key in definitions}:
        fail('Template and statistic/definition bindings must match exactly')
    saved = {}
    replacements = {}
    for key, binding in spec['statistics'].items():
        if not isinstance(binding, dict) or set(binding) != {'stage', 'output', 'key', 'unit', 'format'}:
            fail('Statistic binding requires stage, output, key, unit and format')
        ref = (binding['stage'], binding['output'])
        if ref not in deps or not isinstance(binding['key'], list) or not binding['key']:
            fail('Statistic must select a declared dependency and JSON key path')
        if ref not in saved:
            saved[ref] = read_json(deps[ref])
        value = key_value(saved[ref], binding['key'])
        if not isinstance(value, dict) or set(value) != {'value', 'unit'} or value['unit'] != binding['unit']:
            fail('Statistic unit or shape mismatch')
        number = value['value']
        if isinstance(number, bool) or not isinstance(number, (float, int)) or not math.isfinite(number):
            fail('Statistic value must be finite and numeric')
        if not isinstance(binding['format'], str) or not re.fullmatch(r'(?:\.[0-9]{1,2})?[fge]', binding['format']):
            fail('Use a numeric format such as .2f')
        replacements[('stat', key)] = format(number, binding['format'])
    for key, binding in definitions.items():
        if not isinstance(binding, dict) or set(binding) != {'stage', 'output', 'key'}:
            fail('Definition binding requires stage, output and key')
        ref = (binding['stage'], binding['output'])
        if ref not in deps or not isinstance(binding['key'], list) or not binding['key']:
            fail('Definition must select a declared dependency and JSON key path')
        if ref not in saved:
            saved[ref] = read_json(deps[ref])
        value = key_value(saved[ref], binding['key'])
        if not isinstance(value, str) or not value.strip():
            fail('Definition must select saved nonempty text: ' + key)
        replacements[('definition', key)] = value
    # Substitute once so the saved equation or prose remains literal source text.
    rendered = MANUSCRIPT_TOKEN.sub(lambda match: replacements[match.groups()], text)
    destinations[spec['output']].write_text(rendered, encoding='utf-8')


def capture_learning(root, store, stage, producer, mapping):
    capture_id = None
    try:
        name, metadata, source_hash = learning_metadata(root, stage)
        def resolve(ref):
            output = ref['output']
            return {'output_id': output if output == 'research:execution' else mapping[output], 'path': ref['path']}
        spec = {'producer_id': producer, 'output_id': mapping[metadata['output']],
                'execution_output_id': 'research:execution',
                'conditions': {key: resolve(ref) for key, ref in metadata['conditions'].items()},
                'permitted_switches': {key: resolve(ref) for key, ref in metadata.get('permitted_switches', {}).items()}}
        experience = importlib.import_module('experience')
        identity = state.content_hash({'producer': producer, 'metadata_path': name, 'metadata': source_hash, 'spec': spec,
                                       'experience_sha256': state.digest(Path(experience.__file__)),
                                       'native_check_sha256': state.digest(Path(experience.native_check.__file__))})
        capture_id = 'experience-' + identity
        tasks = load(root, store)
        if capture_id in tasks:
            task = tasks[capture_id]
            if task['parent'] == producer and state.completion_current(root, tasks, capture_id):
                return {'status': 'reused', 'task': capture_id, 'output': 'experience:procedure'}
            return {'status': 'blocked', 'task': capture_id, 'error': 'Reconcile the existing learning capture'}
        result = experience.capture(root, store, capture_id, producer, spec,
                                    metadata_input={'path': name, 'sha256': source_hash})
        tasks = load(root, store)
        if not state.completion_current(root, tasks, capture_id):
            fail('Learning capture did not reach current completion')
        return {'status': 'captured', 'task': capture_id, 'output': result['output_id']}
    except (ImportError, ValueError, KeyError, TypeError, OSError) as exc:
        return {'status': 'blocked', 'task': capture_id, 'error': str(exc)}


PYTHON_PROBE = r'''
import hashlib, importlib, importlib.metadata as metadata, importlib.util, inspect, json, pathlib, sys
wanted = json.loads(sys.argv[1])
sources = json.loads(sys.argv[4])
if sys.argv[2]:
    sys.path[0] = sys.argv[2]
packages = {}
if wanted:
    try:
        from packaging.requirements import Requirement
        from packaging.utils import canonicalize_name
    except ImportError:
        raise SystemExit('Runtime probe requires the installed Python package packaging')
    distributions = {}
    def distribution(name):
        key = canonicalize_name(name)
        if key not in distributions:
            try:
                distributions[key] = metadata.distribution(name)
            except metadata.PackageNotFoundError:
                raise SystemExit('Missing Python package: ' + name)
        return distributions[key]
    def source_paths(dist):
        root = pathlib.Path(dist.locate_file('')).resolve()
        paths = set()
        for entry in dist.files or []:
            if '__pycache__' in entry.parts or (entry.suffix in ('.pyc', '.pyo')
                    and pathlib.Path(dist.locate_file(entry.with_suffix('.py'))).is_file()):
                continue
            item = pathlib.Path(dist.locate_file(entry)).resolve()
            try:
                first = item.relative_to(root).parts[0]
                paths.add(root / first)
            except ValueError:
                paths.add(item)
        direct = json.loads(dist.read_text('direct_url.json') or '{}')
        if direct.get('dir_info', {}).get('editable'):
            modules = (dist.read_text('top_level.txt') or dist.metadata['Name'].replace('-', '_')).splitlines()
            resolved = set()
            for module in modules:
                if not module or '.' in module:
                    continue
                found = importlib.util.find_spec(module)
                if found is None:
                    continue
                if found.submodule_search_locations:
                    resolved.update(pathlib.Path(item).resolve() for item in found.submodule_search_locations)
                elif found.origin and pathlib.Path(found.origin).is_file():
                    resolved.add(pathlib.Path(found.origin).resolve())
            if not resolved:
                raise SystemExit('Editable package has no resolvable source: ' + dist.metadata['Name'])
            paths.update(resolved)
        paths = {item for item in paths if item.is_file() or item.is_dir()}
        return sorted(str(item) for item in paths if not any(parent in paths for parent in item.parents))
    pending = [(name, frozenset()) for name in {*wanted, 'packaging'}]
    visited = set()
    while pending:
        name, extras = pending.pop()
        key = (canonicalize_name(name), extras)
        if key in visited:
            continue
        visited.add(key)
        dist = distribution(name)
        canonical = canonicalize_name(dist.metadata['Name'])
        if canonical not in packages:
            packages[canonical] = {'version': dist.version, 'path': str(dist.locate_file('').resolve()),
                                   'source_paths': source_paths(dist)}
        if canonical in sources:
            direct = json.loads(dist.read_text('direct_url.json') or '{}')
            expected = sources[canonical]
            if (direct.get('url', '').removesuffix('.git') != expected['url']
                    or direct.get('vcs_info', {}).get('commit_id') != expected['commit_id']):
                raise SystemExit('Python source revision mismatch: ' + name)
            packages[canonical]['source'] = expected
        for raw in dist.requires or []:
            req = Requirement(raw)
            if req.marker and not any(req.marker.evaluate({'extra': extra}) for extra in ({''} | set(extras))):
                continue
            dependency = distribution(req.name)
            if req.specifier and not req.specifier.contains(dependency.version, prereleases=True):
                raise SystemExit('Python dependency version mismatch: ' + req.name + ' required by ' + name)
            pending.append((req.name, frozenset(req.extras)))
result = {'version': sys.version.split()[0], 'executable': sys.executable,
          'prefix': sys.prefix, 'packages': packages}
apis = json.loads(sys.argv[3])
if apis:
    result['apis'] = []
    for api in apis:
        name, symbol = api['package'], api['symbol']
        actual = packages[canonicalize_name(name)]['version']
        if actual != wanted[name]:
            raise SystemExit(f'Python package version mismatch: {name} expected {wanted[name]}, got {actual}')
        parts = symbol.split('.')
        try:
            for split in range(len(parts) - 1, 0, -1):
                module = '.'.join(parts[:split])
                try:
                    imported = importlib.import_module(module)
                except ModuleNotFoundError as exc:
                    if exc.name != module and not module.startswith(exc.name + '.'):
                        raise
                    continue
                function = imported
                for attribute in parts[split:]:
                    function = getattr(function, attribute)
                break
            else:
                raise ImportError('No importable module for ' + symbol)
        except (ImportError, AttributeError) as exc:
            raise SystemExit(f'Unsupported API {symbol}: {exc}')
        dist = distribution(name)
        files = dist.files
        origin = getattr(imported, '__file__', None)
        installed = {pathlib.Path(dist.locate_file(f)).resolve() for f in files or []}
        direct = json.loads(dist.read_text('direct_url.json') or '{}')
        editable = direct.get('dir_info', {}).get('editable') and origin and any(
            pathlib.Path(origin).resolve().is_relative_to(pathlib.Path(item))
            for item in packages[canonicalize_name(name)]['source_paths'])
        if not origin or (pathlib.Path(origin).resolve() not in installed and not editable):
            raise SystemExit(f'Unsupported API {symbol}: module file is not in installed {name} distribution metadata')
        if not callable(function):
            raise SystemExit(f'Unsupported API {symbol}: symbol is not callable')
        try:
            signature = inspect.signature(function)
            signature.bind(*([object()] * api['positional']), **{k: object() for k in api['keywords']})
        except (ValueError, TypeError) as exc:
            raise SystemExit(f'Unsupported API {symbol}: signature or requested arguments: {exc}')
        doc = inspect.getdoc(function)
        try:
            source = inspect.getsourcefile(function)
        except (TypeError, OSError):
            source = None
        source_path = pathlib.Path(source).resolve() if source else None
        result['apis'].append({'package': name, 'version': actual, 'symbol': symbol,
            'positional': api['positional'], 'keywords': api['keywords'], 'signature': str(signature),
            'doc_sha256': hashlib.sha256(doc.encode('utf-8')).hexdigest() if doc is not None else None,
            'source': str(source_path) if source_path and source_path.is_file() else None})
print(json.dumps(result, sort_keys=True))
'''

R_PROBE = r'''
args <- commandArgs(trailingOnly=TRUE)
split <- match('--research-apis', args, nomatch=0L)
apiargs <- if (split) args[seq.int(split + 1L, length(args))] else character()
if (split) args <- if (split > 1L) args[seq_len(split - 1L)] else character()
missing <- args[!vapply(args, requireNamespace, logical(1), quietly=TRUE)]
if (length(missing)) stop(paste('Missing R package:', missing[[1]]))
descriptions <- list(); pending <- args
while (length(pending)) {
  name <- pending[[1]]; pending <- pending[-1]
  if (name == 'R' || name %in% names(descriptions)) next
  directory <- find.package(name, quiet=TRUE)
  if (!length(directory)) stop(paste('Missing R package:', name))
  description <- read.dcf(file.path(directory, 'DESCRIPTION'))[1, ]
  descriptions[[name]] <- list(path=directory, version=description[['Version']])
  # LinkingTo supplies headers when building a package, not its installed runtime.
  # Required namespaces and loaded native libraries are identified separately.
  dependencies <- description[intersect(c('Depends', 'Imports'), names(description))]
  if (length(dependencies)) {
    dependencies <- trimws(sub('[[:space:]]*[(].*$', '', unlist(strsplit(dependencies, ','))))
    pending <- c(pending, dependencies[nzchar(dependencies)])
  }
}
packages <- sort(names(descriptions))
line <- function(...) {
  fields <- c(...)
  if (any(grepl('[\t\r\n]', fields))) stop('Unsupported control character in runtime identity')
  cat(paste(fields, collapse='\t'), '\n', sep='')
}
line('version', paste(R.version$major, R.version$minor, sep='.'))
line('executable', file.path(R.home('bin'), 'exec', 'R'))
line('launcher', file.path(R.home('bin'), 'R'))
line('rscript', file.path(R.home('bin'), 'Rscript'))
for (lib in .libPaths()) line('library', lib)
for (name in packages) line('package', name, descriptions[[name]]$version, descriptions[[name]]$path)
if (length(apiargs)) for (record in apiargs) {
  fields <- strsplit(record, ',', fixed=TRUE)[[1]]
  name <- fields[[1]]; symbol <- fields[[2]]; count <- as.integer(fields[[3]])
  if (as.character(packageVersion(name)) != fields[[4]]) stop(paste('R package version mismatch:', name, 'expected', fields[[4]], 'got', as.character(packageVersion(name))))
  keywords <- if (length(fields) > 4) fields[-seq_len(4)] else character()
  f <- tryCatch(getExportedValue(name, symbol), error=function(e) stop(paste('Unsupported R API', name, symbol, conditionMessage(e))))
  if (!is.function(f) || is.null(formals(f))) stop(paste('Unsupported R API', name, symbol, ': no inspectable formals'))
  forms <- formals(f); formal_names <- names(forms); dots <- match('...', formal_names, nomatch=0L)
  positional_names <- if (dots) formal_names[seq_len(dots - 1L)] else formal_names
  if (count > length(positional_names) && !dots) stop(paste('Unsupported R API', name, symbol, ': too many positional arguments'))
  bound <- head(positional_names, count)
  if (any(keywords %in% bound) || (!dots && any(!keywords %in% formal_names)))
    stop(paste('Unsupported R API', name, symbol, ': unsupported or duplicate keyword'))
  hex <- function(x) paste(sprintf('%02x', as.integer(charToRaw(enc2utf8(x)))), collapse='')
  help <- suppressWarnings(utils::help(symbol, package=as.character(name), try.all.packages=FALSE))
  topic <- if (length(help)) as.character(help[[1]]) else ''
  line('api', name, symbol, as.character(count), paste(keywords, collapse=','),
       hex(paste(deparse(forms, width.cutoff=500L), collapse='\n')), hex(topic))
}
for (item in getLoadedDLLs()) {
  target <- item[['path']]
  if (!is.null(target) && file.exists(target) && !dir.exists(target)) line('library_file', normalizePath(target))
}
'''


JULIA_PROBE = r'''
using TOML, Libdl
function emit(fields...)
    values = string.(fields)
    any(x -> occursin(r"[\t\r\n]", x), values) && error("Invalid runtime identity field")
    println(join(values, '\t'))
end
emit("version", VERSION)
emit("executable", joinpath(Sys.BINDIR, Base.julia_exename()))
emit("project", something(Base.active_project(), ""))
for depot in DEPOT_PATH
    emit("depot", abspath(depot))
end
seen = Set{Base.PkgId}()
names = Dict{String,Base.PkgId}()
function collect_package(id)
    id in seen && return
    haskey(names,id.name) && names[id.name] != id && error("Multiple UUIDs for package " * id.name)
    push!(seen,id); names[id.name]=id
    source = Base.locate_package(id)
    source === nothing && error("Missing Julia package source: " * id.name)
    project = joinpath(dirname(dirname(source)), "Project.toml")
    isfile(project) || error("Missing package Project.toml: " * id.name)
    metadata = TOML.parsefile(project)
    get(metadata,"uuid","") == string(id.uuid) || error("Package UUID mismatch: " * id.name)
    emit("package",id.name,string(id.uuid),get(metadata,"version",""),source,project)
    for (depname, depuuid) in sort!(collect(get(metadata,"deps",Dict())))
        dep = Base.identify_package(id, depname)
        # Compatibility Projects can list the same dependency as strong and
        # weak; modern resolved environments retain only the weak binding.
        if dep === nothing && get(get(metadata,"weakdeps",Dict()),depname,nothing) == depuuid
            continue
        end
        dep === nothing && error("Missing Julia dependency " * depname * " required by " * id.name)
        string(dep.uuid) == depuuid || error("Julia dependency UUID mismatch: " * depname)
        collect_package(dep)
    end
end
for name in ARGS
    id=Base.identify_package(name)
    id === nothing && error("Missing Julia package: " * name)
    collect_package(id)
    Base.require(id)
end
for library in sort!(unique(Libdl.dllist()))
    isfile(library) && emit("library_file", abspath(library))
end
'''


_RUNTIME_DIRECTORIES = {}


def runtime_directory(target):
    """Fingerprint installed package files that form the resolved runtime closure."""
    root = Path(target).resolve(strict=True)
    if not root.is_dir(): fail('Runtime package path is not a directory: ' + str(root))
    cached = _RUNTIME_DIRECTORIES.get(root)
    if cached is not None:
        members, digest = cached
        try:
            if all(state.file_identity(item) == identity for item, identity in members.items()):
                return digest
        except OSError:
            pass
    members, files = {}, []
    for directory, names, filenames in os.walk(root):
        names[:] = sorted(name for name in names if name not in {'__pycache__', '.git', '.hg', '.svn'})
        directory = Path(directory)
        members[directory] = state.file_identity(directory)
        for name in sorted(filenames):
            item = directory / name
            if item.suffix in {'.pyc', '.pyo'} and item.with_suffix('.py').is_file():
                continue
            if item.is_file():
                members[item] = state.file_identity(item)
                files.append(item)
    digest = hashlib.sha256()
    for item in sorted(files):
        digest.update(str(item.relative_to(root)).encode() + b'\0')
        digest.update(bytes.fromhex(state.digest(item)))
    if any(state.file_identity(item) != identity for item, identity in members.items()):
        fail('Runtime package changed while reading: ' + str(root))
    result = digest.hexdigest()
    _RUNTIME_DIRECTORIES[root] = members, result
    return result


def runtime_file(target):
    selected = Path(os.path.abspath(target))
    resolved = selected.resolve(strict=True)
    if not resolved.is_file():
        fail('Runtime executable is not a file: ' + str(selected))
    return {'path': str(selected), 'resolved_path': str(resolved), 'sha256': state.digest(resolved)}


def resolve_executable(name, environment):
    if '{' in name:
        fail('Executable must be an explicit path or name')
    selected = shutil.which(name, path=environment.get('PATH', os.defpath))
    if selected is None:
        fail('Executable not found: ' + name)
    return runtime_file(selected)


def probe_runtime(root, stage, environment, executable, cwd=None):
    config = stage['runtime']
    sources = bind_runtime_requirements(root, config, stage.get('inputs', config.get('files', [])))
    for variable in ('PYTHONPATH', 'R_LIBS', 'R_LIBS_USER', 'R_LIBS_SITE', 'JULIA_DEPOT_PATH', 'JULIA_LOAD_PATH'):
        if variable in environment and any(not Path(item).is_absolute() for item in environment[variable].split(os.pathsep)):
            fail('Runtime library paths must be absolute: ' + variable)
    if 'JULIA_PROJECT' in environment and not Path(environment['JULIA_PROJECT']).is_absolute():
        fail('JULIA_PROJECT must be an absolute path')
    prefix = list(config['probe_argv'])
    prefix[0] = executable['path']
    # Wrapper arguments that name files are part of the invoked runtime as well.
    wrappers = []
    for arg in prefix[1:]:
        candidate = Path(arg)
        if not candidate.is_absolute() and (root / candidate).is_file():
            fail('Runtime wrapper file must use an absolute path: ' + arg)
        if candidate.is_file():
            wrappers.append(runtime_file(candidate))
    before = runtime_file(executable['path'])
    if before != executable:
        fail('Executable changed before runtime probe')
    if config['language'] == 'python':
        tail = stage['argv'][len(prefix):]
        if not tail:
            fail('Python runtime requires a script, -c or -m after probe_argv')
        entry = tail[0].replace('{root}', str(root))
        if entry in ('-c', '-m'):
            script_dir = ''
        elif entry.startswith('-') or '{' in entry or not Path(entry).is_absolute():
            fail('Python script must be absolute; include interpreter options in probe_argv')
        else:
            script = Path(entry).resolve()
            script_dir = str(script if script.is_dir() or zipfile.is_zipfile(script) else script.parent)
        command = prefix + ['-c', PYTHON_PROBE, json.dumps(config.get('packages', {})), script_dir, json.dumps(config.get('apis', [])), json.dumps(sources)]
    elif config['language'] == 'r':
        apiargs = [','.join([api['package'], api['symbol'], str(api['positional']), config['packages'][api['package']], *api['keywords']]) for api in config.get('apis', [])]
        command = prefix + ['-e', R_PROBE, *config.get('packages', {})]
        if apiargs:
            command += ['--research-apis', *apiargs]
    else:
        command = prefix + ['-e', JULIA_PROBE, *config.get('packages', {})]
    if cwd is None:
        with tempfile.TemporaryDirectory(prefix='.research-probe-', dir=root) as directory:
            proc = run_process(command, cwd=directory, env=environment, stdout_limit=8 * 1024 * 1024, complete_stdout=True)
    else:
        proc = run_process(command, cwd=cwd, env=environment, stdout_limit=8 * 1024 * 1024, complete_stdout=True)
    if proc.returncode:
        fail('Runtime probe failed: ' + (proc.stderr.strip() or proc.stdout.strip()))
    if runtime_file(executable['path']) != before or any(runtime_file(item['path']) != item for item in wrappers):
        fail('Executable or wrapper changed during runtime probe')
    if config['language'] == 'python':
        try:
            observed = json.loads(proc.stdout)
        except (ValueError, TypeError):
            fail('Python runtime probe returned invalid JSON')
        canonical = lambda name: re.sub(r'[-_.]+', '-', name).lower()
        for name, expected in config.get('packages', {}).items():
            actual = observed['packages'].get(canonical(name), {}).get('version')
            if expected is not None and actual != expected:
                fail(f'Python package version mismatch: {name} expected {expected}, got {actual}')
        for package in observed['packages'].values():
            paths = package['source_paths']
            package['source_sha256'] = state.content_hash({name: runtime_directory(name) if Path(name).is_dir()
                                                         else state.digest(name) for name in paths})
        for api in observed.get('apis', []):
            api['source_sha256'] = state.digest(api['source']) if api['source'] else None
        observed['executable'] = runtime_file(observed['executable'])
    elif config['language'] == 'r':
        observed = {'packages': {}, 'libraries': [], 'library_files': []}
        for row in proc.stdout.splitlines():
            fields = row.split('\t')
            if len(fields) == 2 and fields[0] in {'version', 'executable', 'launcher', 'rscript'}:
                observed[fields[0]] = fields[1]
            elif len(fields) == 2 and fields[0] == 'library':
                observed['libraries'].append(fields[1])
            elif len(fields) == 4 and fields[0] == 'package':
                observed['packages'][fields[1]] = {'version': fields[2], 'path': fields[3],
                                                    'source_sha256': runtime_directory(fields[3])}
            elif len(fields) == 2 and fields[0] == 'library_file':
                observed['library_files'].append(runtime_file(fields[1]))
            elif len(fields) == 7 and fields[0] == 'api':
                _, name, symbol, count, keywords, formals, topic = fields
                help_topic = bytes.fromhex(topic).decode('utf-8')
                help_base = Path(observed['packages'][name]['path']) / 'help' / name
                help_files = [runtime_file(str(help_base) + suffix) for suffix in ('.rdb', '.rdx') if Path(str(help_base) + suffix).is_file()] if help_topic else []
                observed.setdefault('apis', []).append({'package': name, 'version': observed['packages'][name]['version'],
                    'symbol': symbol, 'positional': int(count), 'keywords': keywords.split(',') if keywords else [],
                    'formals': bytes.fromhex(formals).decode('utf-8'), 'help_topic': help_topic or None, 'help_files': help_files})
            else:
                fail('R runtime probe returned invalid output')
        for name, expected in config.get('packages', {}).items():
            actual = observed['packages'].get(name, {}).get('version')
            if expected is not None and actual != expected:
                fail(f'R package version mismatch: {name} expected {expected}, got {actual}')
        observed['executable'] = runtime_file(observed['executable'])
        observed['launcher'] = runtime_file(observed['launcher'])
        observed['rscript'] = runtime_file(observed['rscript'])
    else:
        observed = {'packages': {}, 'depots': [], 'library_files': []}
        for row in proc.stdout.splitlines():
            fields = row.split('\t')
            if len(fields) == 2 and fields[0] in {'version','executable','project'}:
                observed[fields[0]] = fields[1]
            elif len(fields) == 2 and fields[0] == 'depot':
                observed['depots'].append(fields[1])
            elif len(fields) == 2 and fields[0] == 'library_file':
                observed['library_files'].append(runtime_file(fields[1]))
            elif len(fields) == 6 and fields[0] == 'package':
                _, name, uid, version, source, project = fields
                package_root = Path(source).parent.parent
                tracked = {'Project.toml': state.digest(project),
                           'src': runtime_directory(package_root / 'src')}
                extensions = package_root / 'ext'
                if extensions.is_dir(): tracked['ext'] = runtime_directory(extensions)
                artifacts = package_root / 'Artifacts.toml'
                if artifacts.is_file(): tracked['Artifacts.toml'] = state.digest(artifacts)
                observed['packages'][name] = {'uuid':uid,'version':version,'path':str(package_root),
                                               'source_sha256':state.content_hash(tracked)}
            else:
                fail('Julia runtime probe returned invalid output')
        if not {'version','executable','project'} <= set(observed):
            fail('Julia runtime probe omitted interpreter identity')
        for name, expected in config.get('packages', {}).items():
            actual = observed['packages'].get(name, {}).get('version')
            if actual is None: fail('Missing Julia package: ' + name)
            if expected is not None and actual != expected:
                fail(f'Julia package version mismatch: {name} expected {expected}, got {actual}')
        project = Path(observed['project']) if observed['project'] else None
        observed['project_sha256'] = state.digest(project) if project and project.is_file() else None
        manifest = project.with_name('Manifest.toml') if project else None
        observed['manifest_sha256'] = state.digest(manifest) if manifest and manifest.is_file() else None
        observed['executable'] = runtime_file(observed['executable'])
    if 'version' in config and observed['version'] != config['version']:
        fail(f"{config['language']} runtime version mismatch: expected {config['version']}, got {observed['version']}")
    result = {'language': config['language'], 'probe_argv': prefix, 'executable': before, 'wrappers': wrappers,
              'observed': observed, 'files': {name: state.digest(root / name) for name in config.get('files', [])},
              'environment_sha256': environment_hashes(environment)}
    if config.get('companions'):
        result['companions'] = []
        for companion in config['companions']:
            selected = runtime_file(companion['probe_argv'][0])
            child = {'argv': companion['probe_argv'], 'runtime': companion}
            result['companions'].append(probe_runtime(root, child, environment, selected, cwd))
    return result


def run(root, store, manifest, parent=None, retry_failed=None, retry_reason=None, retry_evidence=None, profile=None):
    stages = validate(root, manifest, profile)
    by_id = {stage['id']: stage for stage in stages}
    protected = {stage['id']: set() for stage in stages}
    for selector in stages:
        if 'select' not in selector:
            continue
        heldout = set(protocol(root, selector)['holdout'])
        def protect(sid):
            if heldout <= protected[sid]:
                return
            protected[sid].update(heldout)
            for parent_id in by_id[sid]['depends']:
                protect(parent_id)
        for candidate in selector['select']['candidates'].values():
            protect(candidate['stage'])
        for candidate in stages:
            if 'learn' in candidate:
                protect(candidate['id'])
        if any(stage.get('adaptive', {}).get('protocol') == selector['select']['protocol'] for stage in stages):
            for candidate in stages:
                if candidate.get('final', {}).get('protocol') != selector['select']['protocol']:
                    protected[candidate['id']].update(heldout)
    if retry_failed and retry_failed not in {stage['id'] for stage in stages}:
        fail('Retry stage is not in the adopted manifest')
    if not (root / store).exists():
        call(root, store, 'init')
    selected, results, excluded = {}, {}, set()
    stopped_signum = None
    prefix = 'research-' + manifest['pipeline'] + '-' + (profile + '-' if profile is not None else '')
    def accept(stage, task_id, task, mapping, status, selection, failed_stages):
        sid = stage['id']
        learning = capture_learning(root, store, stage, task_id, mapping) if 'learn' in stage else None
        if learning and learning['status'] == 'blocked':
            results[sid] = {'status': 'blocked', 'task': task_id, 'outputs': mapping,
                            'reason': 'Required learning capture is incomplete', 'learning': learning}
            return
        selected[sid] = {'id': task_id, 'task': task, 'paths': {n: root / p for n, p in mapping.items()}}
        results[sid] = {'status': status, 'task': task_id, 'outputs': mapping}
        if learning:
            results[sid]['learning'] = learning
        if selection and selection['on_failure'] == 'exclude':
            excluded.update(failed_stages)
    for stage in stages:
        sid = stage['id']
        if stopped_signum is not None:
            results[sid] = {'status': 'blocked', 'reason': 'Pipeline interrupted', 'signal': stopped_signum}
            continue
        if 'when' in stage:
            w = stage['when']
            if w['stage'] not in selected:
                results[sid] = {'status': 'blocked', 'reason': 'selector incomplete'}
                continue
            decision = read_json(selected[w['stage']]['paths'][w['output']])
            if decision['selected'] != w['equals']:
                results[sid] = {'status': 'skipped', 'selector': selected[w['stage']]['id'], 'selected': decision['selected']}
                continue
        selection = protocol(root, stage) if 'select' in stage else None
        failed_candidates = {}
        if selection:
            for name, candidate in stage['select']['candidates'].items():
                outcome = results.get(candidate['stage'], {})
                if outcome.get('status') == 'failed' and selection['on_failure'] == 'exclude':
                    record = load(root, store)[outcome['task']]['outputs'].get('research:execution', {})
                    if type(record.get('value', {}).get('returncode')) is int:
                        failed_candidates[name] = {'task': outcome['task'], 'error': outcome.get('error', '')}
        failed_stages = {stage['select']['candidates'][name]['stage'] for name in failed_candidates} if selection else set()
        if any(dep not in selected and dep not in failed_stages for dep in stage['depends']):
            results[sid] = {'status': 'blocked', 'reason': 'dependency incomplete'}
            continue
        deps = {(d, n): selected[d]['paths'][n] for d, names in stage['depends'].items() if d in selected for n in names}
        try:
            stage = execution_stage(root, stage, deps)
            if protected[sid].intersection(stage['inputs']):
                fail('Candidate or its ancestor references a held-out input')
        except (ValueError, OSError, KeyError, TypeError) as exc:
            results[sid] = {'status': 'blocked', 'reason': str(exc)}
            continue
        stale = [f'{d}:{n}' for d, names in stage.get('reviewed_results', {}).items()
                 for n, digest in names.items() if (d, n) not in deps or state.digest(deps[(d, n)]) != digest]
        if stale:
            results[sid] = {'status': 'blocked', 'reason': 'Reviewed result changed: ' + ', '.join(stale)}
            continue
        consumes = []
        tasks = load(root, store)
        for d, names in stage['depends'].items():
            if d in failed_stages:
                task_id = results[d]['task']
                record = tasks[task_id]['outputs'].get('research:execution')
                if record is None or not state.output_current(root, tasks, task_id, 'research:execution'):
                    fail('Failed trial needs its current recorded terminal result')
                consumes.append({'producer_id': task_id, 'output_id': 'research:execution', **state.output_version(record)})
                continue
            for n in names:
                upstream = selected[d]
                row = upstream['task']['outputs'][upstream['paths'][n].relative_to(root).as_posix()]
                consumes.append({'producer_id': upstream['id'], 'output_id': upstream['paths'][n].relative_to(root).as_posix(),
                                 **state.output_version(row)})
        expected_consumes = {(r['producer_id'], r['output_id'], r['content_version'],
                              json.dumps(r['definition_versions'], sort_keys=True)) for r in consumes}
        try:
            environment = execution_environment(root, stage)
            executable = resolve_executable(stage['argv'][0], environment) if 'argv' in stage else None
            executables = {name: resolve_executable(name, environment) for name in stage.get('executables', [])}
            runtime_identity = None
            if 'runtime' in stage:
                runtime_identity = probe_runtime(root, stage, environment, executable)
        except (ValueError, OSError) as exc:
            results[sid] = {'status': 'blocked', 'reason': str(exc)}
            continue
        signature = {'stage': {k: v for k, v in stage.items() if k != 'learn'},
                     'environment_sha256': environment_hashes(environment),
                     'executable': executable,
                     'runner_sha256': state.digest(Path(__file__)),
                     'state_sha256': state.digest(Path(state.__file__)),
                     'state_io_sha256': state.digest(Path(state.gate.__file__))}
        if 'final' in stage:
            chosen = read_json(root / stage['final']['protocol'])
            signature['final_holdout'] = {name:state.digest(root/name) for name in chosen['holdout']}
        if profile is not None:
            signature['profile'] = profile
        if runtime_identity is not None:
            signature['runtime'] = runtime_identity
        if executables:
            signature['executables'] = executables
        signature_hash = state.content_hash(signature)
        previous = [(k, t) for k, t in tasks.items() if k.startswith(prefix + sid + '-')
                    and t.get('parent') == parent
                    and t.get('outputs', {}).get('research:signature', {}).get('value') == signature]
        match = None
        for task_id, task in sorted(previous, key=lambda item: item[1]['updated'], reverse=True):
            actual = {(r['producer_id'], r['output_id'], r['content_version'], json.dumps(r['definition_versions'], sort_keys=True)) for r in task.get('consumes', [])}
            if expected_consumes == actual and state.completion_current(root, tasks, task_id):
                match = (task_id, task)
                break
        if match:
            task_id, task = match
            mapping = task['outputs']['research:outputs']['value']
            accept(stage, task_id, task, mapping, 'reused', selection, failed_stages)
            continue
        pending = [(k, t) for k, t in tasks.items() if k.startswith(prefix + sid + '-') and t.get('parent') == parent and t['status'] in {'running', 'blocked'}
                   and t.get('outputs', {}).get('research:signature', {}).get('value', {}).get('profile') == profile]
        if pending:
            task_id, task = max(pending, key=lambda item: item[1]['updated'])
            if (not state.constraints_current(root, tasks, task)
                    or task.get('blocked_reason') in {'permission', 'user_hold'}):
                results[sid] = {'status': 'blocked', 'task': task_id, 'reason': 'Resolve the recorded hold before resuming'}
                continue
            prepared = task['outputs'].get('research:prepared', {})
            execution = task['outputs'].get('research:execution', {})
            matching = any(k == task_id for k, _ in previous)
            actual = {(r['producer_id'], r['output_id'], r['content_version'], json.dumps(r['definition_versions'], sort_keys=True)) for r in task.get('consumes', [])}
            receipt = execution.get('value', {}).get('prepared') if execution else None
            if (not matching or expected_consumes != actual or not receipt or state.content_version(execution) != execution.get('version')
                    or prepared and state.content_version(prepared) != prepared.get('version')):
                if task['status'] == 'running':
                    call(root, store, 'transition', task_id, 'blocked', '--reason', 'interrupted', '--next', 'Reconcile the unfinished command and its actual return')
                results[sid] = {'status': 'blocked', 'task': task_id, 'reason': 'Reconcile the unfinished command and its actual return'}
                continue
            if (state.input_changes(root, task) or state.context_changes(root, task)
                    or not state.constraints_current(root, tasks, task) or not state.consumed_current(root, tasks, task)):
                results[sid] = {'status': 'blocked', 'task': task_id, 'reason': 'Reconcile changed inputs, context, holds or dependencies'}
                continue
            saved = prepared['value'] if prepared else {**receipt, 'execution_sha256': execution['version']}
            generation = '.agents/research/' + manifest['pipeline'] + '/' + task_id
            gen = root / path(root, generation, exists=False)
            work = gen.with_name('.pending-' + task_id)
            source = gen if gen.exists() else work
            destinations = {name: source / target for name, target in stage['outputs'].items()}
            expected_mapping = {n: (gen / target).relative_to(root).as_posix() for n, target in stage['outputs'].items()}
            if ({k: saved.get(k) for k in ('outputs', 'definitions', 'hashes')} != receipt
                    or saved.get('outputs') != expected_mapping or set(saved.get('hashes', {})) != set(expected_mapping)
                    or state.content_version(execution) != execution.get('version') or saved.get('execution_sha256') != execution.get('version')
                    or execution.get('value', {}).get('returncode') != 0
                    or any(not target.is_file() for target in destinations.values())):
                results[sid] = {'status': 'blocked', 'task': task_id, 'reason': 'Reconcile missing or changed terminal evidence'}
                continue
            for target in destinations.values():
                path(root, target.relative_to(root).as_posix())
            if any(state.digest(target) != saved['hashes'][name] for name, target in destinations.items()):
                results[sid] = {'status': 'blocked', 'task': task_id, 'reason': 'Reconcile changed prepared outputs'}
                continue
            output_checks(stage, destinations)
            if task['status'] == 'running':
                call(root, store, 'transition', task_id, 'blocked', '--reason', 'interrupted', '--next', 'Resume the completed stage return')
            call(root, store, 'resume', task_id)
            if not prepared:
                call(root, store, 'output', task_id, 'research:prepared', '--kind', 'object', '--value', json.dumps(saved))
            if source == work:
                os.rename(work, gen)
            for name, target in saved['outputs'].items():
                call(root, store, 'output', task_id, target, '--role', name, '--definition-versions', json.dumps(saved['definitions']))
            call(root, store, 'output', task_id, 'research:outputs', '--kind', 'object', '--value', json.dumps(saved['outputs']))
            call(root, store, 'transition', task_id, 'completed')
            task = load(root, store)[task_id]
            accept(stage, task_id, task, saved['outputs'], 'recovered', selection, failed_stages)
            continue
        if 'final_holdout' in signature:
            consumed_holdout = any(
                t.get('outputs',{}).get('research:signature',{}).get('value',{}).get('final_holdout') == signature['final_holdout']
                and type(t.get('outputs',{}).get('research:execution',{}).get('value',{}).get('returncode')) is int
                for t in tasks.values())
            if consumed_holdout:
                results[sid] = {'status':'blocked', 'reason':'Held-out data have already been evaluated; adopt a fresh holdout for a changed search'}
                continue
        failures = [(k, t) for k, t in previous if t['status'] == 'failed'
                    and not t.get('outputs', {}).get('research:execution', {}).get('value', {}).get('interrupted')
                    and not state.changed(root, {p: t['consumed_inputs'][p] for p in stage['inputs']})
                    and not state.context_changes(root, t) and state.constraints_current(root, tasks, t)
                    and {(r['producer_id'], r['output_id'], r['content_version'], json.dumps(r['definition_versions'], sort_keys=True)) for r in t.get('consumes', [])}
                    == expected_consumes]
        if failures and 'argv' in stage:
            task_id, task = max(failures, key=lambda item: item[1]['updated'])
            recorded = task.get('outputs', {}).get('research:execution', {}).get('value', {})
            if type(recorded.get('returncode')) is not int and recorded.get('launched') is not False:
                results[sid] = {'status': 'blocked', 'task': task_id, 'reason': 'Reconcile the missing command return before retrying'}
                continue
        retry = bool(failures and retry_failed == sid)
        if failures and not retry:
            task_id, task = max(failures, key=lambda item: item[1]['updated'])
            error = task.get('outputs', {}).get('research:execution', {}).get('value', {}).get('error', 'Previous terminal failure')
            results[sid] = {'status': 'failed', 'task': task_id, 'error': error}
            continue
        task_id = prefix + sid + '-' + uuid.uuid4().hex
        generation = '.agents/research/' + manifest['pipeline'] + '/' + task_id
        gen = root / path(root, generation, exists=False)
        work = gen.with_name('.pending-' + task_id)
        destinations = {name: work / target for name, target in stage['outputs'].items()}
        mapping = {n: (gen / stage['outputs'][n]).relative_to(root).as_posix() for n in destinations}
        required = [json.dumps({'role': n, 'kind': 'file', 'target': p}) for n, p in mapping.items()]
        args = ['add', task_id, '--owner', 'research-runner', '--scope', gen.parent.relative_to(root).as_posix(), '--next', 'Execute the adopted stage']
        if parent:
            args += ['--parent', parent]
        for item in required:
            args += ['--required-output', item]
        for item in stage['inputs']:
            args += ['--input', item]
        if retry:
            args += ['--input', retry_evidence]
        for item in consumes:
            args += ['--consumes', json.dumps(item)]
        returncode, argv, reports, prepared_saved = None, None, [], False
        execution = {'argv': None, 'cwd': work.relative_to(root).as_posix(), 'launched': False, 'returncode': None,
                     'log': '', 'checks': [], 'runtime': runtime_identity,
                     'retry_reason': retry_reason if retry else None,
                     'retry_evidence': ({'path': retry_evidence, 'sha256': state.digest(root / retry_evidence)} if retry else None)}
        if executables:
            execution['executables'] = executables
        try:
            call(root, store, *args)
            call(root, store, 'start', task_id)
            call(root, store, 'output', task_id, 'research:signature', '--kind', 'object', '--value', json.dumps(signature))
            work.mkdir(parents=True, exist_ok=False)
            for target in destinations.values():
                target.parent.mkdir(parents=True, exist_ok=True)
            if 'render' in stage:
                render(root, stage, destinations, deps)
                returncode = 0
            elif 'select' in stage:
                choose(root, stage, destinations, deps, failed_candidates)
                returncode = 0
            elif 'adaptive' in stage:
                adapt(root, stage, destinations, deps)
                returncode = 0
            else:
                def replace(match):
                    token = match.group(1)
                    if token == 'root':
                        return str(root)
                    parts = token.split(':')
                    if parts[0] == 'out' and parts[1] in destinations:
                        return str(destinations[parts[1]])
                    if parts[0] == 'dep' and tuple(parts[1:]) in deps:
                        return str(deps[tuple(parts[1:])])
                    fail('Unknown output or dependency placeholder')
                argv = [TOKEN.sub(replace, a) for a in stage['argv']]
                if any(re.search(r'\{(?:root|out:|dep:)[^{}]*\}', a) for a in argv):
                    fail('Invalid placeholder in argv')
                argv[0] = executable['path']
                execution['argv'] = argv
                proc = run_process(argv, cwd=work, env=environment, observation=execution,
                    started=lambda observed: call(root, store, 'output', task_id, 'research:execution',
                                                  '--kind', 'object', '--value', json.dumps(observed)))
                returncode = proc.returncode
                call(root, store, 'output', task_id, 'research:execution', '--kind', 'object', '--value', json.dumps(execution))
                if returncode:
                    fail(f'Command exited {returncode}')
            execution['returncode'] = returncode
            if 'final' in stage:
                final_data = read_json(destinations[stage['final']['output']])
                final_protocol = read_json(root / stage['final']['protocol'])
                expected_membership = {'holdout':final_protocol['evaluation_protocol']['partition_membership']['holdout']}
                selector_ref = stage['final']['selector']
                decision = read_json(deps[(selector_ref['stage'], selector_ref['output'])])
                if (final_data.get('partition_membership') != expected_membership
                        or final_data.get('identity') != final_protocol['identity']
                        or final_data.get('protocol') != final_protocol['evaluation_protocol']
                        or final_data.get('parameters') != decision.get('parameters')):
                    fail('Final result must use the selected parameters, adopted identity and held-out IDs')
            for output in destinations.values():
                path(root, output.relative_to(root).as_posix())
            reports = output_checks(stage, destinations)
            if executable and runtime_file(executable['path']) != executable:
                fail('Executable changed during execution')
            if any(resolve_executable(name, environment) != identity for name, identity in executables.items()):
                fail('Declared executable changed during execution')
            if runtime_identity is not None and probe_runtime(root, stage, environment, executable, work) != runtime_identity:
                fail('Runtime identity changed during execution')
            current = load(root, store)
            task = current[task_id]
            if (state.input_changes(root, task) or state.context_changes(root, task)
                    or not state.constraints_current(root, current, task)
                    or not state.consumed_current(root, current, task)):
                fail('Inputs, context, holds or dependencies changed during execution')
            definitions = {'stage': signature_hash, **{f'input:{x}': state.digest(root / x) for x in stage['inputs']}}
            ready = {'outputs': mapping, 'definitions': definitions,
                     'hashes': {n: state.digest(p) for n, p in destinations.items()}}
            execution.update(checks=reports, prepared=ready)
            call(root, store, 'output', task_id, 'research:execution', '--kind', 'object', '--value', json.dumps(execution))
            prepared_saved = True
            prepared = {**ready, 'execution_sha256': state.content_hash(execution)}
            call(root, store, 'output', task_id, 'research:prepared', '--kind', 'object', '--value', json.dumps(prepared))
            os.rename(work, gen)
            for n, target in mapping.items():
                call(root, store, 'output', task_id, target, '--role', n, '--definition-versions', json.dumps(definitions))
            call(root, store, 'output', task_id, 'research:outputs', '--kind', 'object', '--value', json.dumps(mapping))
            call(root, store, 'transition', task_id, 'completed')
            task = load(root, store)[task_id]
            accept(stage, task_id, task, mapping, 'executed', selection, failed_stages)
        except (ValueError, OSError, KeyError, TypeError, ArithmeticError, KeyboardInterrupt) as exc:
            interrupted = isinstance(exc, KeyboardInterrupt)
            if interrupted:
                stopped_signum = getattr(exc, 'signum', signal.SIGINT)
            message = str(exc) or 'Research execution interrupted'
            current = load(root, store).get(task_id)
            saved_execution = current.get('outputs', {}).get('research:execution', {}) if current else {}
            prepared_saved = prepared_saved or bool(saved_execution.get('value', {}).get('prepared'))
            if prepared_saved:
                if current['status'] == 'running':
                    call(root, store, 'transition', task_id, 'blocked', '--reason', 'interrupted', '--next', 'Reconcile the prepared stage publication')
                results[sid] = {'status': 'blocked', 'task': task_id, 'reason': message}
            elif current is None:
                results[sid] = {'status': 'blocked', 'reason': message}
            else:
                execution.pop('prepared', None)
                execution.update(checks=reports, error=message)
                if interrupted:
                    execution.update(interrupted=True, signal=stopped_signum)
                if current['status'] == 'running':
                    call(root, store, 'output', task_id, 'research:execution', '--kind', 'object', '--value', json.dumps(execution))
                call(root, store, 'transition', task_id, 'failed', '--next',
                     'Rerun the interrupted stage in a fresh generation' if interrupted else 'Repair the stage and run again')
                results[sid] = {'status': 'failed', 'task': task_id, 'error': message}
            if interrupted:
                results[sid].update(interrupted=True, signal=stopped_signum)
        finally:
            if not prepared_saved:
                if work.is_symlink():
                    work.unlink()
                elif work.exists():
                    shutil.rmtree(work)
    return results, any(row['status'] in {'failed', 'blocked'} and key not in excluded for key, row in results.items())


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == 'gallery':
        import research_artifacts
        return research_artifacts.gallery_main(argv[1:])
    if argv and argv[0] == 'meeting':
        import research_meetings
        return research_meetings.main(argv[1:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--store', default='.agents/state/team.json')
    parser.add_argument('--profile', help='Adopted named stage selection')
    parser.add_argument('--parent', help='Existing state task whose context, scope and holds apply')
    parser.add_argument('--retry-failed', help='ID of the terminally failed stage to retry')
    parser.add_argument('--retry-reason', help='Reason that the specific retry is justified')
    parser.add_argument('--retry-evidence', help='Root-relative file recording the actual repair or transient evidence')
    parser.add_argument('manifest')
    args = parser.parse_args(argv)
    root = args.root.resolve()
    path(root, args.store, exists=False)
    if Path(args.store).parts[:2] != ('.agents', 'state'):
        fail('Store must be in .agents/state')
    if Path(args.store).with_suffix('.lock') == Path('.agents/state/.research-runner.lock'):
        fail('Store conflicts with the research runner lock')
    manifest = read_json(root / path(root, args.manifest))
    with state.locked(root / '.agents/state/.research-runner.json'):
        if any(v is not None for v in (args.retry_failed, args.retry_reason, args.retry_evidence)):
            if not all(isinstance(v, str) and v.strip() for v in (args.retry_failed, args.retry_reason, args.retry_evidence)):
                fail('A retry requires its stage, reason and saved evidence')
            path(root, args.retry_evidence)
        with interruption_signals():
            result, failed = run(root, args.store, manifest, args.parent, args.retry_failed, args.retry_reason, args.retry_evidence, args.profile)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if any('signal' in row for row in result.values()):
        return 128 + next(row['signal'] for row in result.values() if 'signal' in row)
    return 1 if failed else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt as error:
        print(str(error) or 'Research execution interrupted', file=sys.stderr)
        sys.exit(128 + getattr(error, 'signum', signal.SIGINT))
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
