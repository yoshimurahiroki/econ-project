#!/usr/bin/env python3
"""Build and verify an explicitly selected, current research reproduction package.

Build config: manifest, optional profile, tasks (stage -> completed task ID),
outputs (stage -> output -> comparison), allow_inputs (exact input paths),
allow_env (environment names), interpreters (stage -> executable), and optional
helpers (research.py, state.py, local_checks.py -> source paths). Comparisons
are {"method":"sha256"} or {"method":"numeric-json", "path":[keys],
"unit_path":[keys], "rtol":number, "atol":number}. All required inputs and
environment names must be approved. `verify` checks the inventory; `environment`
reports selected runtime closures and resource bounds; `restore` creates an isolated
Python environment from pinned inputs and recorded versions; `reproduce` replays
into a temporary project or a new persistent `--output` directory. `--python`
selects the restored interpreter and `--workers` bounds common thread settings.
"""
import argparse
import json
import math
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

import research
import state

HELPERS = ('research.py', 'state.py', 'local_checks.py', 'reproduction.py')
LEARNING_HELPERS = ('experience.py', 'native_check.py', 'requirements_check.py', 'policy_assets.py', 'paragraph.py', 'argument.py')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(root, name):
    return state.gate.regular_bytes(root / state.relative(root, name))


def dump(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def safe_tree(root):
    rows = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs:
            require(not (Path(directory) / name).is_symlink(), 'Symlink in package')
        for name in files:
            path = Path(directory) / name
            rel = path.relative_to(root).as_posix()
            state.relative(root, rel)
            rows[rel] = state.gate.file_snapshot(path).sha256
    return rows


def verify(package):
    package = package.absolute()
    require(package.is_dir() and not any(p.is_symlink() for p in (package, *package.parents)), 'Invalid package directory')
    record = json.loads(read(package, 'inventory.json'))
    actual = safe_tree(package)
    actual.pop('inventory.json')
    require(actual == record['files'], 'Package inventory differs from current files')
    return record


def selected(root, store, config):
    require(set(config) <= {'manifest', 'profile', 'tasks', 'outputs', 'allow_inputs', 'allow_env', 'interpreters', 'helpers'}, 'Unknown config field')
    for key in ('manifest', 'tasks', 'outputs', 'allow_inputs', 'allow_env', 'interpreters'):
        require(key in config, 'Missing config field: ' + key)
    manifest = research.read_json(root / state.relative(root, config['manifest']))
    profile = config.get('profile')
    stages = research.validate(root, manifest, profile)
    by_id = {s['id']: s for s in stages}
    require(isinstance(config['tasks'], dict) and isinstance(config['outputs'], dict) and isinstance(config['interpreters'], dict), 'Invalid selection maps')
    require(set(config['tasks']) <= set(by_id) and set(config['outputs']) <= set(config['tasks']) and set(config['interpreters']) <= set(config['tasks']), 'Unknown selected stage')
    for key in ('allow_inputs', 'allow_env'):
        require(isinstance(config[key], list) and all(isinstance(x, str) and x for x in config[key]) and len(set(config[key])) == len(config[key]), 'Invalid ' + key)
    failure_candidates = {ref['stage'] for stage in stages if 'select' in stage
                          and research.protocol(root, stage)['on_failure'] == 'exclude'
                          for ref in stage['select']['candidates'].values()}
    all_env = {name for s in stages for name in [*s.get('env', {}), *s.get('inherit_env', [])]}
    require(all_env <= set(config['allow_env']), 'Unapproved environment names: ' + ', '.join(sorted(all_env - set(config['allow_env']))))
    helpers = config.get('helpers', {name: 'harness/' + name for name in HELPERS if name != 'reproduction.py'})
    require(isinstance(helpers, dict) and set(helpers) == set(HELPERS) - {'reproduction.py'} and all(isinstance(v, str) for v in helpers.values()), 'Helpers require the three runner source paths')
    for name, module in [('research.py', research), ('state.py', state), ('local_checks.py', state.gate)]:
        require(state.gate.file_snapshot(root / state.relative(root, helpers[name])).sha256 == state.digest(Path(module.__file__)), 'Selected helper differs from current runner: ' + name)
    tasks = research.load(root, store)
    mapped = config['tasks']
    require(bool(config['outputs']), 'Select at least one comparison output')
    input_paths = {item for stage in stages for item in stage['inputs']}
    recorded = {}
    for stage in stages:
        sid = stage['id']
        if sid not in mapped:
            w = stage.get('when')
            require(w and w['stage'] in mapped, 'Each non-skipped stage needs an explicit completed task: ' + sid)
            selector = tasks[mapped[w['stage']]]['outputs']['research:outputs']['value'][w['output']]
            require(state.output_current(root, tasks, mapped[w['stage']], selector), 'Selector output is stale')
            require(research.read_json(root / selector)['selected'] != w['equals'], 'Selected conditional stage needs its completed task')
            continue
        task_id = mapped[sid]
        require(task_id in tasks, 'Selected task does not exist: ' + sid)
        task = tasks[task_id]
        failed = task['status'] == 'failed'
        require(task['status'] == 'completed' or (failed and sid in failure_candidates), 'Task must be completed or an excluded failed candidate: ' + sid)
        require(state.output_current(root, tasks, task_id, 'research:signature') and
                (failed or state.output_current(root, tasks, task_id, 'research:outputs')), 'Stage receipts are stale: ' + sid)
        signature = task['outputs']['research:signature']['value']
        require(signature['stage'] == {k: v for k, v in stage.items() if k != 'learn'} and signature.get('profile') == profile, 'Stage signature differs: ' + sid)
        require(signature['runner_sha256'] == state.digest(Path(research.__file__)) and signature['state_sha256'] == state.digest(Path(state.__file__)) and signature['state_io_sha256'] == state.digest(Path(state.gate.__file__)), 'Runner changed since execution')
        require(not state.input_changes(root, task) and not state.context_changes(root, task) and state.constraints_current(root, tasks, task) and state.consumed_current(root, tasks, task), 'Task dependencies or context are stale: ' + sid)
        mapping = {} if failed else task['outputs']['research:outputs']['value']
        require(failed or set(mapping) == set(stage['outputs']), 'Output identities differ: ' + sid)
        for name, path in mapping.items():
            require(state.output_current(root, tasks, task_id, path), 'Output is stale: ' + sid + ':' + name)
            require(task['outputs'][path].get('definition_versions', {}).get('stage') == state.content_hash(signature), 'Output stage identity differs: ' + sid + ':' + name)
        expected = set()
        for dep, names in stage['depends'].items():
            require(dep in mapped, 'Consumed producer must be selected: ' + dep)
            producer = tasks[mapped[dep]]
            for name in names:
                output = 'research:execution' if producer['status'] == 'failed' else producer['outputs']['research:outputs']['value'][name]
                expected.add((mapped[dep], output, producer['outputs'][output]['version']))
        actual = {(r['producer_id'], r['output_id'], r['content_version']) for r in task['consumes']}
        require(expected == actual, 'Consumed result identities differ: ' + sid)
        require(set(stage['inputs']) <= set(task['consumed_inputs']), 'Untracked stage input: ' + sid)
        input_paths.update(task['consumed_inputs'])
        input_paths.update(task['read_dependencies'])
        env_names = set(stage.get('env', {})) | set(stage.get('inherit_env', []))
        require(env_names <= set(config['allow_env']), 'Unapproved environment names: ' + ', '.join(sorted(env_names - set(config['allow_env']))))
        execution = task['outputs']['research:execution']['value']
        require(state.output_current(root, tasks, task_id, 'research:execution') and type(execution.get('returncode')) is int
                and ((execution['returncode'] != 0) if failed else (execution['returncode'] == 0)), 'Execution receipt is stale: ' + sid)
        environment = {k: os.environ[k] for k in stage.get('inherit_env', []) if k in os.environ}
        require(len(environment) == len(stage.get('inherit_env', [])), 'Inherited environment missing: ' + sid)
        environment.update(stage.get('env', {}))
        require(environment == signature['environment'], 'Stage environment changed: ' + sid)
        exe = signature.get('executable')
        if exe:
            require(Path(exe['path']).resolve() == Path(exe['resolved_path']) and Path(exe['resolved_path']).is_file() and state.digest(Path(exe['resolved_path'])) == exe['sha256'], 'Executed interpreter changed: ' + sid)
        if 'runtime' in stage:
            require(research.probe_runtime(root, stage, environment, exe) == signature.get('runtime') == execution.get('runtime'), 'Runtime changed: ' + sid)
        context_hashes = []
        ancestor = task
        while ancestor:
            context_hashes.append(state.context_id(ancestor))
            parent = ancestor.get('parent')
            ancestor = tasks[parent] if parent else None
        learning = None
        if 'learn' in stage:
            require(not failed, 'Failed candidate cannot have a completed learning capture')
            import experience
            name, metadata, source_hash = research.learning_metadata(root, stage)
            input_paths.add(name)
            def resolve(ref):
                return {'output_id': ref['output'] if ref['output'] == 'research:execution' else mapping[ref['output']], 'path': ref['path']}
            capture_spec = {'producer_id': task_id, 'output_id': mapping[metadata['output']], 'execution_output_id': 'research:execution',
                            'conditions': {key: resolve(ref) for key, ref in metadata['conditions'].items()},
                            'permitted_switches': {key: resolve(ref) for key, ref in metadata.get('permitted_switches', {}).items()}}
            identity = state.content_hash({'producer': task_id, 'metadata_path': name, 'metadata': source_hash, 'spec': capture_spec,
                                           'experience_sha256': state.digest(Path(experience.__file__)),
                                           'native_check_sha256': state.digest(Path(experience.native_check.__file__))})
            capture_id = 'experience-' + identity
            require(capture_id in tasks and tasks[capture_id]['parent'] == task_id
                    and state.completion_current(root, tasks, capture_id), 'Learning capture is stale: ' + sid)
            learning = {'task': capture_id, 'procedure_sha256': tasks[capture_id]['outputs']['experience:procedure']['version']}
        recorded[sid] = {'task': task_id, 'outputs': mapping, 'signature': signature, 'execution': execution,
                         'context_hashes': context_hashes, 'failed': failed, 'learning': learning}
    missing = input_paths - set(config['allow_inputs'])
    require(not missing, 'Required input acquisition/approval required: ' + ', '.join(sorted(missing)))
    require(all(isinstance(v, str) and v for v in config['interpreters'].values()), 'Invalid interpreter')
    for sid, comparisons in config['outputs'].items():
        require(isinstance(comparisons, dict) and comparisons, 'Select output comparisons')
        for name, spec in comparisons.items():
            require(name in by_id[sid]['outputs'] and isinstance(spec, dict), 'Unknown output comparison')
            if spec.get('method') == 'sha256':
                require(set(spec) == {'method'}, 'Invalid SHA-256 comparison')
            elif spec.get('method') == 'numeric-json':
                require(set(spec) == {'method', 'path', 'unit_path', 'rtol', 'atol'} and all(isinstance(spec[k], list) and spec[k] and all(isinstance(x, str) for x in spec[k]) for k in ('path', 'unit_path')) and all(type(spec[k]) in (int, float) and math.isfinite(spec[k]) and spec[k] >= 0 for k in ('rtol', 'atol')), 'Invalid numeric comparison')
            else:
                raise ValueError('Unknown comparison method')
    return manifest, stages, recorded, input_paths


def build(root, store, config, target):
    root, target = root.resolve(), target.absolute()
    require(target.parent.is_dir() and not any(p.is_symlink() for p in (target, *target.parents)), 'Invalid destination')
    require(not target.exists() and not target.is_symlink(), 'Destination already exists')
    manifest, stages, records, inputs = selected(root, store, config)
    manifest_hash = state.gate.sha(read(root, config['manifest']))
    replay = {'pipeline': manifest['pipeline'], 'stages': [dict(s) for s in stages]}
    for stage in replay['stages']:
        sid = stage['id']
        if sid in config['interpreters']:
            require('argv' in stage, 'Interpreter override requires argv')
            stage['argv'] = list(stage['argv'])
            stage['argv'][0] = config['interpreters'][sid]
            if 'runtime' in stage:
                stage['runtime'] = dict(stage['runtime'])
                stage['runtime']['probe_argv'] = list(stage['runtime']['probe_argv'])
                stage['runtime']['probe_argv'][0] = stage['argv'][0]
    source_map = {}
    temp = Path(tempfile.mkdtemp(prefix='.' + target.name + '-', dir=target.parent))
    try:
        def copy(source, dest):
            snapshot = state.gate.file_snapshot(root / state.relative(root, source))
            path = temp / state.relative(temp, dest, exists=False)
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                require(dest in source_map.get(source, []) and state.gate.file_snapshot(path).sha256 == snapshot.sha256,
                        'Conflicting package paths: ' + dest)
                return
            with path.open('xb') as output:
                state.gate.write_content(output, snapshot)
            source_map.setdefault(source, []).append(dest)
        for name in sorted(inputs):
            copy(name, 'project/' + name)
        helpers = config.get('helpers', {name: 'harness/' + name for name in HELPERS if name != 'reproduction.py'})
        for name, source in helpers.items():
            copy(source, 'project/harness/' + name)
        if any('learn' in stage for stage in stages):
            import experience
            for name in LEARNING_HELPERS:
                module = __import__(name[:-3])
                source = 'harness/' + name
                require(state.digest(root / source) == state.digest(Path(module.__file__)), 'Learning helper differs: ' + name)
                copy(source, 'project/harness/' + name)
            copy('registry/operations.json', 'project/registry/operations.json')
        tool_snapshot = state.gate.file_snapshot(Path(__file__))
        with (temp / 'project/harness/reproduction.py').open('xb') as output:
            state.gate.write_content(output, tool_snapshot)
        expected = {}
        provenance = {}
        for sid, rec in records.items():
            sig, execution = rec['signature'], rec['execution']
            restore_runtime = None
            stage = next(item for item in stages if item['id'] == sid)
            if stage.get('runtime', {}).get('language') == 'python' and stage['runtime'].get('packages'):
                probe_stage = dict(stage); probe_stage['runtime'] = dict(stage['runtime'])
                packages = dict(probe_stage['runtime'].get('packages', {})); packages.setdefault('packaging', None)
                probe_stage['runtime']['packages'] = packages
                restore_runtime = research.probe_runtime(root, probe_stage, sig['environment'], sig['executable'])
            provenance[sid] = {'task': rec['task'], 'stage_sha256': state.content_hash(sig['stage']),
                'environment_sha256': {k: state.content_hash(v) for k, v in sig['environment'].items()},
                'executable': sig.get('executable'), 'runtime': sig.get('runtime'), 'restore_runtime': restore_runtime,
                'argv': execution.get('argv'), 'cwd': execution.get('cwd'), 'execution_returncode': execution.get('returncode'),
                'signature_sha256': state.content_hash(sig), 'execution_sha256': state.content_hash(execution),
                'governing_context_sha256': rec['context_hashes'], 'failed': rec['failed'], 'learning': rec['learning']}
            for name, spec in config['outputs'].get(sid, {}).items():
                source = rec['outputs'][name]
                dest = 'expected/' + sid + '/' + name
                if spec['method'] == 'numeric-json':
                    data = json.loads(read(root, source))
                    number = value_at(data, spec['path'])
                    unit = value_at(data, spec['unit_path'])
                    require(type(number) in (int, float) and math.isfinite(number) and isinstance(unit, str) and bool(unit), 'Expected statistic or unit is invalid')
                copy(source, dest)
                expected.setdefault(sid, {})[name] = {'path': dest, 'comparison': spec}
        (temp / 'project' / 'manifest.json').write_bytes(dump(replay))
        metadata = {'source_map': source_map, 'expected': expected, 'provenance': provenance,
                    'manifest_sha256': manifest_hash,
                    'profile': config.get('profile'), 'git_revision': state.revision(root),
                    'config_sha256': state.content_hash(config)}
        (temp / 'metadata.json').write_bytes(dump(metadata))
        (temp / 'inventory.json').write_bytes(dump({'files': safe_tree(temp)}))
        verify(temp)
        current = selected(root, store, config)
        require(current == (manifest, stages, records, inputs) and state.gate.sha(read(root, config['manifest'])) == manifest_hash, 'Selection changed during packaging')
        for source, destinations in source_map.items():
            current_hash = state.gate.file_snapshot(root / state.relative(root, source)).sha256
            require(all(current_hash == state.gate.file_snapshot(temp / dest).sha256 for dest in destinations), 'Source changed during copy: ' + source)
        require(state.gate.file_snapshot(Path(__file__)).sha256 == tool_snapshot.sha256, 'Reproduction tool changed during copy')
        state.gate.atomic_publish(temp, target)
    finally:
        if temp.exists():
            shutil.rmtree(temp)
    return {'package': str(target), 'files': len(safe_tree(target))}


def value_at(data, keys):
    for key in keys:
        data = data[key]
    return data


def available_resources(device, requested_workers, memory_per_worker_mb, minimum_memory_mb):
    require(device in ('cpu', 'gpu') and type(requested_workers) is int and requested_workers > 0,
            'Device and positive requested worker count are required')
    require(type(memory_per_worker_mb) is int and memory_per_worker_mb >= 0 and
            type(minimum_memory_mb) is int and minimum_memory_mb >= 0, 'Memory requirements must be nonnegative MiB')
    cpus = len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else os.cpu_count()
    require(cpus is not None and cpus > 0, 'Available CPU count cannot be established')
    quota_path = Path('/sys/fs/cgroup/cpu.max')
    if quota_path.is_file():
        quota, period = quota_path.read_text().split()
        if quota != 'max':
            cpus = min(cpus, max(1, int(quota)//int(period)))
    available = None
    meminfo = Path('/proc/meminfo')
    if meminfo.is_file():
        fields = dict(line.split(':', 1) for line in meminfo.read_text().splitlines() if ':' in line)
        if 'MemAvailable' in fields:
            available = int(fields['MemAvailable'].split()[0])*1024
    limit = Path('/sys/fs/cgroup/memory.max'); used = Path('/sys/fs/cgroup/memory.current')
    if limit.is_file() and used.is_file() and limit.read_text().strip() != 'max':
        remaining = max(0, int(limit.read_text())-int(used.read_text()))
        available = remaining if available is None else min(available, remaining)
    if available is None:
        try:
            available = os.sysconf('SC_AVPHYS_PAGES') * os.sysconf('SC_PAGE_SIZE')
        except (AttributeError, OSError, ValueError):
            pass
    if minimum_memory_mb or memory_per_worker_mb:
        require(available is not None, 'Available memory cannot be established')
        require(available >= minimum_memory_mb*1024*1024, 'Available memory is below the requested minimum')
    workers = min(requested_workers, cpus)
    if memory_per_worker_mb:
        workers = min(workers, available//(memory_per_worker_mb*1024*1024))
    require(workers > 0, 'Available memory cannot support one requested worker')
    return {'device': device, 'available_cpus': cpus, 'available_memory_bytes': available,
            'minimum_memory_mb': minimum_memory_mb, 'memory_per_worker_mb': memory_per_worker_mb,
            'requested_workers': requested_workers, 'bounded_workers': workers}


def environment(package, device='cpu', workers=1, memory_per_worker_mb=0, minimum_memory_mb=0, python=None):
    package = package.absolute(); verify(package)
    root = package/'project'; manifest = json.loads(read(root, 'manifest.json'))
    metadata = json.loads(read(package, 'metadata.json'))
    resources = available_resources(device, workers, memory_per_worker_mb, minimum_memory_mb)
    runtimes = {}; requirements = {}; git_sources = {}; gpu_seen = False
    for stage in research.validate(root, manifest):
        if 'runtime' not in stage:
            continue
        runtime = stage['runtime']
        stage_env = {k: os.environ[k] for k in stage.get('inherit_env', []) if k in os.environ}
        require(len(stage_env) == len(stage.get('inherit_env', [])), 'Inherited environment missing: '+stage['id'])
        stage_env.update(stage.get('env', {}))
        recorded = metadata['provenance'].get(stage['id'], {}).get('restore_runtime') or metadata['provenance'].get(stage['id'], {}).get('runtime')
        selected_executable = str(python) if python is not None and runtime['language'] == 'python' else runtime['probe_argv'][0]
        actual = None
        if Path(selected_executable).is_file():
            changed = dict(stage); changed['argv'] = list(stage['argv']); changed['argv'][0] = selected_executable
            changed['runtime'] = dict(runtime); changed['runtime']['probe_argv'] = list(runtime['probe_argv'])
            changed['runtime']['probe_argv'][0] = selected_executable
            if runtime['language'] == 'python' and runtime.get('packages'):
                packages = dict(runtime['packages']); packages.setdefault('packaging', None)
                changed['runtime']['packages'] = packages
            executable = research.runtime_file(selected_executable)
            actual = research.probe_runtime(root, changed, stage_env, executable)
        if python is not None and runtime['language'] == 'python':
            require(actual is not None, 'Selected Python interpreter is unavailable: '+str(python))
        require(actual is not None or recorded is not None, 'No recorded or available runtime: '+stage['id'])
        if actual is not None and recorded is not None and runtime['language'] in ('python', 'r'):
            wanted = recorded['observed'].get('packages', {})
            found = actual['observed'].get('packages', {})
            require(all(found.get(name, {}).get('version') == info['version'] for name, info in wanted.items()),
                    'Selected runtime dependency closure differs: '+stage['id'])
        if runtime['language'] == 'python':
            for path in runtime.get('files', []):
                if re.fullmatch(r'requirements(?:[-_.A-Za-z0-9]*)?\.txt', Path(path).name):
                    raw = read(root, path)
                    for line in raw.decode('utf-8').splitlines():
                        line = line.strip()
                        if line and not line.startswith('#'):
                            exact = re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*==[A-Za-z0-9][A-Za-z0-9.+_-]*', line)
                            pinned_git = re.fullmatch(r'([A-Za-z0-9][A-Za-z0-9._-]*)\s*@\s*git\+(https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git)@([0-9a-f]{40})', line)
                            require(exact is not None or pinned_git is not None,
                                    'Restore requires exact Python package pins: '+path)
                            if pinned_git:
                                name = re.sub(r'[-_.]+', '-', pinned_git.group(1)).lower()
                                source = {'name': name, 'url': pinned_git.group(2), 'commit': pinned_git.group(3)}
                                require(name not in git_sources or git_sources[name] == source, 'Conflicting Git source pin: '+name)
                                git_sources[name] = source
                    requirements[path] = state.gate.sha(raw)
            if device == 'gpu' and 'jax' in {name.lower() for name in runtime.get('packages', {})}:
                require(actual is not None, 'Requested GPU requires an available selected Python runtime')
                proc = subprocess.run([selected_executable, '-c', 'import json,jax; print(json.dumps([str(d) for d in jax.devices("gpu")]))'],
                                      env=stage_env, capture_output=True, text=True)
                require(proc.returncode == 0, 'Requested GPU is unavailable: '+(proc.stderr.strip() or proc.stdout.strip()))
                devices = json.loads(proc.stdout)
                require(isinstance(devices, list) and devices, 'Requested GPU is unavailable')
                resources['gpu_devices'] = devices
                gpu_seen = True
        # Recorded provenance selects restore pins; available runtime evidence is reported separately.
        runtimes[stage['id']] = {'recorded': recorded, 'available': actual}
    if device == 'gpu':
        require(gpu_seen, 'GPU requires a selected Python stage declaring the JAX runtime')
    return {'resources': resources, 'runtimes': runtimes,
            'python_requirements': [{'path': path, 'sha256': digest} for path, digest in sorted(requirements.items())],
            'python_git_sources': [git_sources[name] for name in sorted(git_sources)]}


def restore(package, target, python):
    package = package.absolute(); target = target.absolute()
    require(target.parent.is_dir() and not any(p.is_symlink() for p in (target, *target.parents)), 'Invalid environment destination')
    require(not target.exists(), 'Environment destination already exists')
    plan = environment(package)
    selected = [row['recorded'] or row['available'] for row in plan['runtimes'].values()
                if (row['recorded'] or row['available'])['language'] == 'python']
    require(selected, 'Package does not select a Python runtime')
    require(plan['python_requirements'] or not any(r['observed']['packages'] for r in selected),
            'Selected Python packages require tracked pinned requirements')
    pins = {}
    for runtime in selected:
        for name, item in runtime['observed']['packages'].items():
            require(name not in pins or pins[name] == item['version'], 'Selected Python runtimes require conflicting '+name+' versions')
            pins[name] = item['version']
    target_python = target/('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    commands = [[str(python), '-m', 'venv', str(target)], [str(target_python), '-m', 'pip', 'install']]
    for item in plan['python_requirements']:
        commands[1].extend(['-r', str(package/'project'/item['path'])])
    git_names = {source['name'] for source in plan['python_git_sources']}
    commands[1].extend(name+'=='+version for name, version in sorted(pins.items()) if name not in git_names)
    for command in (commands if plan['python_requirements'] or pins else commands[:1]):
        proc = subprocess.run(command, text=True, capture_output=True)
        require(proc.returncode == 0, 'Environment restore failed: '+(proc.stderr.strip() or proc.stdout.strip()))
    for source in plan['python_git_sources']:
        probe = subprocess.run([str(target_python), '-c',
            'import importlib.metadata as m,sys; print(m.distribution(sys.argv[1]).read_text("direct_url.json") or "{}")',
            source['name']], text=True, capture_output=True)
        require(probe.returncode == 0, 'Installed Git source metadata unavailable: '+source['name'])
        direct = json.loads(probe.stdout)
        require(direct.get('vcs_info', {}).get('commit_id') == source['commit']
                and direct.get('url', '').removesuffix('.git') == source['url'].removesuffix('.git'),
                'Installed Git source differs from pinned commit: '+source['name'])
    root = package/'project'; manifest = json.loads(read(root, 'manifest.json')); observed = {}
    for stage in research.validate(root, manifest):
        if stage.get('runtime', {}).get('language') != 'python':
            continue
        changed = dict(stage); changed['argv'] = list(stage['argv']); changed['argv'][0] = str(target_python)
        changed['runtime'] = dict(stage['runtime']); changed['runtime']['probe_argv'] = list(stage['runtime']['probe_argv'])
        changed['runtime']['probe_argv'][0] = str(target_python)
        env = {k: os.environ[k] for k in stage.get('inherit_env', []) if k in os.environ}; env.update(stage.get('env', {}))
        observed[stage['id']] = research.probe_runtime(root, changed, env, research.runtime_file(target_python))
        actual = observed[stage['id']]['observed']['packages']
        expected = (plan['runtimes'][stage['id']]['recorded'] or plan['runtimes'][stage['id']]['available'])['observed']['packages']
        require(all(actual.get(name, {}).get('version') == info['version'] for name, info in expected.items() if name != 'packaging'),
                'Restored Python dependency closure differs: '+stage['id'])
    return {'environment': str(target), 'interpreter': str(target_python), 'requirements': plan['python_requirements'],
            'package_pins': pins, 'git_sources': plan['python_git_sources'], 'runtimes': observed}


def reproduce(package, destination=None, python=None, device='cpu', workers=None, memory_per_worker_mb=0, minimum_memory_mb=0):
    package = package.absolute()
    verify(package)
    plan = environment(package, device, 1 if workers is None else workers, memory_per_worker_mb, minimum_memory_mb, python)
    metadata = json.loads(read(package, 'metadata.json'))
    temp = None
    if destination is None:
        temp = tempfile.TemporaryDirectory(prefix='research-reproduction-')
        target = Path(temp.name)
    else:
        target = destination.absolute()
        require(target.parent.is_dir() and not any(p.is_symlink() for p in (target, *target.parents)), 'Invalid replay destination')
        require(not target.exists(), 'Replay destination already exists')
        target.mkdir()
    try:
        root = target/'project'
        shutil.copytree(package/'project', root)
        if python is not None or workers is not None or device == 'gpu':
            replay_manifest = json.loads(read(root, 'manifest.json'))
            for stage in replay_manifest['stages']:
                if python is not None and stage.get('runtime', {}).get('language') == 'python':
                    stage['argv'][0] = str(python)
                    stage['runtime']['probe_argv'][0] = str(python)
                if workers is not None and 'argv' in stage:
                    stage.setdefault('env', {}).update({key: str(plan['resources']['bounded_workers']) for key in
                        ('RESEARCH_WORKERS', 'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')})
                if device == 'gpu' and stage.get('runtime', {}).get('language') == 'python' and 'jax' in stage['runtime'].get('packages', {}):
                    stage.setdefault('env', {})['JAX_PLATFORMS'] = 'gpu'
            (root/'manifest.json').write_bytes(dump(replay_manifest))
        proc = subprocess.run([sys.executable, str(root/'harness/research.py'), '--root', str(root), 'manifest.json'], text=True, capture_output=True)
        require(proc.returncode == 0, 'Research runner failed: '+proc.stderr+proc.stdout)
        results = json.loads(proc.stdout)
        replay_tasks = research.load(root, '.agents/state/team.json')
        for sid, original in metadata['provenance'].items():
            if original.get('failed'):
                require(results[sid]['status'] == 'failed' and
                        replay_tasks[results[sid]['task']]['outputs']['research:execution']['value']['returncode']
                        == original['execution_returncode'], 'Failed candidate return differs: '+sid)
            if original.get('learning'):
                require(results[sid].get('learning', {}).get('status') in ('captured', 'reused'), 'Learning capture did not complete: '+sid)
        compared = []
        for sid, outputs in metadata['expected'].items():
            require(results[sid]['status'] in ('executed', 'reused', 'recovered'), 'Stage did not complete: '+sid)
            for name, row in outputs.items():
                actual, expected = root/results[sid]['outputs'][name], package/row['path']
                spec = row['comparison']
                if spec['method'] == 'sha256':
                    require(state.digest(actual) == state.digest(expected), 'Output differs: '+sid+':'+name)
                else:
                    a, e = json.loads(actual.read_bytes()), json.loads(expected.read_bytes())
                    av, ev = value_at(a, spec['path']), value_at(e, spec['path'])
                    require(type(av) in (int, float) and type(ev) in (int, float) and math.isfinite(av) and math.isfinite(ev) and value_at(a, spec['unit_path']) == value_at(e, spec['unit_path']) and math.isclose(av, ev, rel_tol=spec['rtol'], abs_tol=spec['atol']), 'Statistic or unit differs: '+sid+':'+name)
                compared.append(sid+':'+name)
        result = {'compared': compared, 'resources': plan['resources']}
        if destination is not None:
            result.update({'project': str(root), 'stages': results})
            (target/'reproduction-result.json').write_bytes(dump(result))
        verify(package)
        return result
    finally:
        if temp is not None:
            temp.cleanup()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    b = sub.add_parser('build')
    b.add_argument('--root', type=Path, required=True)
    b.add_argument('--store', default='.agents/state/team.json')
    b.add_argument('--config', required=True)
    b.add_argument('target', type=Path)
    v = sub.add_parser('verify'); v.add_argument('package', type=Path)
    r = sub.add_parser('reproduce'); r.add_argument('package', type=Path); r.add_argument('--output', type=Path)
    r.add_argument('--python', type=Path); r.add_argument('--device', choices=('cpu', 'gpu'), default='cpu')
    r.add_argument('--workers', type=int); r.add_argument('--memory-per-worker-mb', type=int, default=0)
    r.add_argument('--minimum-memory-mb', type=int, default=0)
    e = sub.add_parser('environment'); e.add_argument('package', type=Path)
    e.add_argument('--device', choices=('cpu', 'gpu'), default='cpu'); e.add_argument('--workers', type=int, default=1)
    e.add_argument('--memory-per-worker-mb', type=int, default=0); e.add_argument('--minimum-memory-mb', type=int, default=0)
    e.add_argument('--python', type=Path)
    restore_parser = sub.add_parser('restore'); restore_parser.add_argument('package', type=Path)
    restore_parser.add_argument('--python', type=Path, required=True); restore_parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'build':
        root = args.root.resolve()
        state.relative(root, args.store)
        config_path = Path(args.config)
        config = json.loads(state.gate.regular_bytes(config_path if config_path.is_absolute() else root / state.relative(root, args.config)))
        with state.locked(root / '.agents/state/.research-runner.json'):
            result = build(root, args.store, config, args.target)
    else:
        if args.command == 'verify':
            result = verify(args.package)
        elif args.command == 'reproduce':
            result = reproduce(args.package, args.output, args.python, args.device, args.workers,
                               args.memory_per_worker_mb, args.minimum_memory_mb)
        elif args.command == 'environment':
            result = environment(args.package, args.device, args.workers, args.memory_per_worker_mb, args.minimum_memory_mb, args.python)
        else:
            result = restore(args.package, args.output, args.python)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
