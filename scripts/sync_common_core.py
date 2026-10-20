#!/usr/bin/env python3
"""Compare or synchronize an explicit set of common files between Git repositories."""

import argparse
import base64
from contextlib import contextmanager, ExitStack
from functools import lru_cache
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import tempfile
import stat
from urllib.parse import urlsplit
from pathlib import Path

# Resolve default synchronization scope from the selected source's route registry.
# Explicit --path remains available for project-specific subsets.
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from route_registry import load_routes, transform_entry_references, resolve_operation


@lru_cache(maxsize=1)
def runtime_io():
    root = Path(__file__).resolve().parents[1]
    helper = next(p for p in (root / 'harness/local_checks.py',
        root / '.agents/harness/local_checks.py') if p.is_file())
    spec = importlib.util.spec_from_file_location('maintenance_local_io', helper)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def common_paths(source):
    routes = load_routes(source)
    registry_paths = routes.get("registry_source_paths", ["runtime/ROUTES.yaml"])
    return tuple(sorted({resource["source_path"] for resource in routes["resources"].values()
                         if resource.get("sync", True)} | set(registry_paths)))


LOCAL_CONFIG_PATHS = (".codex/config.toml",)

RECEIPT_PATH = "docs/ai/integration.md"
RECEIPT_START = "<!-- common-core-receipt:v2 -->"
RECEIPT_END = "<!-- /common-core-receipt:v2 -->"
LEGACY_START = "<!-- common-core-receipt:v1 -->"
LEGACY_END = "<!-- /common-core-receipt:v1 -->"
FENCE = chr(96) * 3
SYNC_LOCK = 'econ-common-sync.lock'
SYNC_JOURNAL = 'econ-common-sync.json'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def git(root, *args, required=True):
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=False,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )
    if required and result.returncode:
        raise ValueError(f"Git operation failed: {args[0]}")
    return result.stdout if result.returncode == 0 else None


def identity(origin):
    """Public, credential-free host/owner/repository identity."""
    match = re.fullmatch(r"(?:[^/@:]+@)?([^/:]+):([^?#]+)", origin)
    if match and "://" not in origin:
        host, path = match.groups()
    else:
        parsed = urlsplit(origin)
        if parsed.scheme not in {"https", "http", "ssh", "git"} or not parsed.hostname:
            raise ValueError("Repository origin must identify a remote host and repository")
        if parsed.password or parsed.query or parsed.fragment or (parsed.scheme in {"http", "https"} and parsed.username):
            raise ValueError("Credential-bearing or parameterized origins are not accepted")
        host = parsed.hostname + (f":{parsed.port}" if parsed.port else "")
        path = parsed.path.lstrip("/")
    path = path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    if len(path.split("/")) < 2 or any(part in {"", ".", ".."} for part in path.split("/")):
        raise ValueError("Origin must contain its complete owner and repository path")
    return host.lower() + "/" + path


def repository(root):
    root = Path(root).resolve(strict=True)
    top = Path(git(root, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    if root != top:
        raise ValueError("Use the actual Git repository root")
    origin = git(root, "remote", "get-url", "origin").decode().strip()
    return root, identity(origin), git(root, "rev-parse", "HEAD").decode().strip()


def checked_path(relative):
    path = Path(relative)
    if not relative or any(ord(c) < 32 for c in relative) or path.is_absolute() or "\\" in relative or any(part in {"", ".", ".."} for part in relative.split("/")):
        raise ValueError(f"Invalid managed relative path: {relative}")
    if ".git" in path.parts or relative == RECEIPT_PATH or relative.startswith('.agents/state/'):
        raise ValueError(f"Reserved managed path: {relative}")
    return relative


def safe_file(root, relative):
    path = root / relative
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError(f"Refuse symlink or escaping path: {relative}")
    if any(parent.is_symlink() for parent in path.parents if parent != root and parent.is_relative_to(root)):
        raise ValueError(f"Refuse symlink parent: {relative}")
    if path.exists() and not path.is_file():
        raise ValueError(f"Expected a regular file: {relative}")
    return path


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def head_file(root, head, relative):
    entry = git(root, "ls-tree", head, "--", relative).decode().strip()
    if not entry:
        return None, None
    metadata, _ = entry.split("\t", 1)
    mode, kind, oid = metadata.split()
    if kind != "blob" or mode not in {"100644", "100755"}:
        raise ValueError(f"Unsupported Git entry: {relative}")
    return oid, mode



def index_file(root, relative):
    entries = []
    for line in git(root, "ls-files", "--stage", "--", relative).decode().splitlines():
        metadata, _ = line.split("\t", 1)
        mode, oid, stage = metadata.split()
        entries.append((oid, mode, stage))
    return tuple(entries)


def index_matches_head(root, head, relative, entries):
    oid, mode = head_file(root, head, relative)
    expected = ((oid, mode, "0"),) if oid is not None else ()
    return entries == expected

def file_mode(path, root=None, head=None, relative=None):
    if root is not None and git(root, "config", "--get", "core.filemode", required=False) == b"false\n":
        _, tracked_mode = head_file(root, head, relative)
        if tracked_mode is not None:
            return tracked_mode
    return "100755" if path.stat().st_mode & 0o111 else "100644"


def snapshot(root, head, relative, modes=False):
    path = safe_file(root, relative)
    if not path.exists():
        return {"data": None, "sha256": None, "mode": None, "git_blob": None, "filesystem_mode": None}
    data = path.read_bytes()
    mode = file_mode(path, root, head, relative) if modes is False else ((modes or {}).get(relative) or ("100755" if path.stat().st_mode & 0o111 else "100644"))
    return {"data": data, "sha256": hashlib.sha256(data).hexdigest(),
            "mode": mode, "git_blob": blob(data),
            "filesystem_mode": "100755" if path.stat().st_mode & 0o111 else "100644"}


def signature(state):
    return state["sha256"], state["mode"]

def same_snapshot(current, expected):
    """Ownership compares content and the physical mode in both writers."""
    return (signature(current) == signature(expected)
            and current.get('filesystem_mode') == (expected.get('filesystem_mode') or expected['mode']))


def tree_records(root):
    """Content/mode records for generation inputs and moved backup trees."""
    root = Path(root)
    if not root.exists() and not root.is_symlink():
        return {}
    result = {}
    def record(path):
        metadata = path.lstat()
        mode = str(stat.S_IMODE(metadata.st_mode))
        if stat.S_ISLNK(metadata.st_mode):
            digest = hashlib.sha256(os.readlink(path).encode()).hexdigest()
            kind = 'symlink'
        elif stat.S_ISREG(metadata.st_mode):
            value = hashlib.sha256()
            fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
            with os.fdopen(fd, 'rb') as handle:
                before = os.fstat(handle.fileno())
                for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                    value.update(chunk)
                after = os.fstat(handle.fileno())
            if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_mode) != (after.st_ino, after.st_size, after.st_mtime_ns, after.st_mode):
                raise ValueError('File changed while snapshotting: ' + str(path))
            digest, kind = value.hexdigest(), 'file'
        elif stat.S_ISDIR(metadata.st_mode):
            digest, kind = None, 'directory'
        else:
            raise ValueError('Nonregular generation input: ' + str(path))
        result[path.relative_to(root).as_posix()] = {'sha256': digest, 'mode': kind + ':' + mode, 'filesystem_mode': kind + ':' + mode}
    record(root)
    if root.is_dir() and not root.is_symlink():
        for directory, directories, files in os.walk(root, followlinks=False):
            directories[:] = [name for name in directories if name not in {'.git', '__pycache__'}]
            for name in [*directories, *[n for n in files if not n.endswith('.pyc')]]:
                record(Path(directory) / name)
    return result


def same_tree(current, expected):
    return set(current) == set(expected) and all(same_snapshot(current[key], expected[key]) for key in expected)


def fingerprint(state):
    return "absent" if state["data"] is None else f'{state["sha256"]}:{state["mode"]}'


def read_receipt(original):
    text = original.decode("utf-8")
    found = []
    for version, start, end in ((2, RECEIPT_START, RECEIPT_END), (1, LEGACY_START, LEGACY_END)):
        if text.count(start) != text.count(end) or text.count(start) > 1:
            raise ValueError("Malformed common-core receipt")
        if start in text:
            a, b = text.index(start), text.index(end)
            if b < a:
                raise ValueError("Malformed common-core receipt")
            body = text[a + len(start):b].strip()
            if not body.startswith(FENCE + "json\n") or not body.endswith("\n" + FENCE):
                raise ValueError("Malformed receipt JSON block")
            receipt = json.loads(body[len(FENCE + "json\n"):-len("\n" + FENCE)])
            found.append((version, receipt, a, b + len(end)))
    if len(found) > 1:
        raise ValueError("Multiple common-core receipts")
    return found[0] if found else (None, {}, None, None)


def receipt_bytes(original, receipt):
    _, _, start, end = read_receipt(original)
    text = original.decode("utf-8")
    block = RECEIPT_START + "\n" + FENCE + "json\n" + json.dumps(receipt, ensure_ascii=False, indent=2) + "\n" + FENCE + "\n" + RECEIPT_END
    if start is not None:
        text = text[:start] + block + text[end:]
    else:
        separator = "" if not text or text.endswith("\n\n") else "\n" if text.endswith("\n") else "\n\n"
        text += separator + block + "\n"
    return text.encode("utf-8")


def baseline(receipt, version, source, source_name, target_name, migrate, released=()):
    if not version:
        return {}
    old_source = receipt.get("source_repository", "")
    if version == 1:
        if not migrate:
            raise ValueError("Legacy receipt requires --migrate-receipt after checking its recorded source")
        if "/" in old_source and not old_source.startswith(("https:", "ssh:")) and old_source.count("/") == 1:
            old_source = "github.com/" + old_source
    if old_source != source_name:
        raise ValueError("Receipt belongs to another source repository")
    if version == 2 and receipt.get("target_repository") != target_name:
        raise ValueError("Receipt belongs to another target repository")
    rows = {}
    for row in receipt.get("paths", []):
        path = checked_path(row["path"])
        if path in released:
            continue
        if path in rows:
            raise ValueError(f"Repeated receipt path: {path}")
        row = dict(row)
        if version == 1:
            oid, mode = head_file(source, receipt["source_base_commit"], path)
            data = git(source, "show", f'{receipt["source_base_commit"]}:{path}')
            if oid != row.get("git_blob") or hashlib.sha256(data).hexdigest() != row.get("sha256"):
                raise ValueError(f"Legacy receipt cannot establish committed baseline: {path}; use an explicit --claim")
            row["mode"] = mode
            row["state"] = "present"
        if row.get("state") == "deleted":
            row["sha256"], row["mode"] = None, None
        elif not re.fullmatch(r"[0-9a-f]{64}", row.get("sha256", "")) or row.get("mode") not in {"100644", "100755"}:
            raise ValueError(f"Invalid receipt baseline: {path}")
        rows[path] = row
    return rows


def _atomic_write(path, data, mode):
    if data is None:
        if path.exists():
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".common-sync-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o755 if mode == "100755" else 0o644)
        runtime_io().replace_path(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def _target_lock(root):
    path = _metadata_file(root, SYNC_LOCK)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_CLOEXEC', 0) | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('Synchronization lock must be a regular file')
        try:
            runtime_io().lock_fd(fd)
        except BlockingIOError as error:
            raise ValueError('Synchronization writer active: ' + str(root)) from error
        yield
    finally:
        os.close(fd)


def _metadata_file(root, name):
    # Git's private per-worktree administration area is never staged by add -A.
    # Resolve worktree gitfiles through Git rather than assuming .git is a folder.
    location = Path(git(root, 'rev-parse', '--git-path', name).decode().strip())
    path = location if location.is_absolute() else root / location
    path = path.absolute()
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise ValueError('Refuse symlink synchronization metadata')
    if path.exists() and not path.is_file():
        raise ValueError('Synchronization metadata must be a regular file')
    return path


def _journal_write(root, entries):
    path = _metadata_file(root, SYNC_JOURNAL)
    if path.exists():
        raise ValueError('Recover the pending synchronization before replacing its journal')
    def encoded(state, desired=False):
        return {key: state.get(key) for key in ('sha256', 'mode', 'filesystem_mode')} | {
            'filesystem_mode': state['mode'] if desired else state.get('filesystem_mode'),
            'data': None if state['data'] is None else base64.b64encode(state['data']).decode('ascii')}
    journal = {'schema_version': 1, 'target_root': str(root),
               'head': entries[0][1], 'files': [
                   {'path': relative, 'index': index_file(root, relative),
                    'before': encoded(before), 'desired': encoded(desired, True)}
                   for _, _, relative, before, desired in entries]}
    fd, temporary = tempfile.mkstemp(prefix='.common-sync-journal-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(canonical(journal))
            handle.flush()
            os.fsync(handle.fileno())
        runtime_io().replace_path(temporary, path)
        runtime_io().sync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _recover_journal(root):
    """Restore only exact task-owned bytes, keeping changed concurrent files intact."""
    path = _metadata_file(root, SYNC_JOURNAL)
    if not path.exists():
        return []
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate synchronization journal field')
            result[key] = value
        return result
    saved = json.loads(path.read_bytes(), object_pairs_hook=pairs)
    if (not isinstance(saved, dict) or set(saved) != {'schema_version', 'target_root', 'head', 'files'}
            or type(saved['schema_version']) is not int or saved['schema_version'] != 1
            or saved['target_root'] != str(root) or not isinstance(saved['files'], list)):
        raise ValueError('Invalid synchronization journal: ' + str(path))
    if repository(root)[2] != saved['head']:
        raise ValueError('Pending synchronization target HEAD changed; journal retained: ' + str(path))
    def decoded(value):
        if not isinstance(value, dict) or set(value) != {'sha256', 'mode', 'filesystem_mode', 'data'}:
            raise ValueError('Invalid synchronization journal snapshot')
        data = None if value['data'] is None else base64.b64decode(value['data'], validate=True)
        expected = None if data is None else hashlib.sha256(data).hexdigest()
        if value['sha256'] != expected or value['mode'] not in (None, '100644', '100755'):
            raise ValueError('Synchronization journal snapshot hash or mode mismatch')
        if value['filesystem_mode'] not in (None, '100644', '100755'):
            raise ValueError('Invalid synchronization journal filesystem mode')
        return {**value, 'data': data}
    matches = same_snapshot
    pending, seen, conflicts = [], set(), []
    for row in saved['files']:
        if not isinstance(row, dict) or set(row) != {'path', 'index', 'before', 'desired'}:
            raise ValueError('Invalid synchronization journal entry')
        relative = row['path']
        if relative != RECEIPT_PATH:
            checked_path(relative)
        if relative in seen:
            raise ValueError('Duplicate synchronization journal target')
        seen.add(relative)
        if [list(item) for item in index_file(root, relative)] != row['index']:
            conflicts.append(relative)
            continue
        before, desired = decoded(row['before']), decoded(row['desired'])
        current = snapshot(root, saved['head'], relative)
        if matches(current, before):
            continue
        if not matches(current, desired):
            conflicts.append(relative)
            continue
        pending.append((relative, before, desired))
    restored = []
    for relative, before, desired in reversed(pending):
        if repository(root)[2] != saved['head'] or not matches(snapshot(root, saved['head'], relative), desired):
            conflicts.append(relative)
            continue
        _atomic_write(safe_file(root, relative), before['data'], before.get('filesystem_mode') or before['mode'])
        restored.append(relative)
    if conflicts:
        # Every remaining changed path is owned by the concurrent writer. After
        # reverting our other writes, ordinary receipt/claim checks can resume.
        path.unlink()
        raise ValueError('Concurrent files retained: ' + ', '.join(conflicts))
    path.unlink()
    return restored


def synchronize(source, targets, *, apply=False, expected=None, expected_source=None,
                expected_content=None, paths=None, deletes=(), releases=(), claims=None, migrate=False):
    targets = list(targets)
    source_record = repository(source)
    target_records = [repository(target) for target in targets]
    roots = sorted({row[0] for row in target_records}, key=str)
    if len(roots) != len(targets) or source_record[0] in roots:
        raise ValueError('Source and destination roots must be distinct')
    if apply and source_record[2] != expected_source:
        raise ValueError('Expected source HEAD mismatch or absent')
    if apply and any((expected or {}).get(name) != head for _, name, head in target_records):
        raise ValueError('Expected target HEAD mismatch or absent')
    with ExitStack() as locks:
        recovered = {}
        if apply:
            for root in roots:
                locks.enter_context(_target_lock(root))
            for root in roots:
                restored = _recover_journal(root)
                if restored:
                    recovered[str(root)] = restored
        elif any(_metadata_file(root, SYNC_JOURNAL).exists() for root in roots):
            raise ValueError('Pending synchronization journal; resume the authorized apply to recover it')
        report, status = _synchronize(source, targets, apply=apply, expected=expected,
            expected_source=expected_source, expected_content=expected_content, paths=paths,
            deletes=deletes, releases=releases, claims=claims, migrate=migrate)
        if recovered:
            report['recovered_paths'] = recovered
        return report, status


def _repository_policy(root):
    if not (root / 'registry/resources.json').is_file():
        return None
    routes = load_routes(root)
    spec = importlib.util.spec_from_file_location('sync_candidate_policy', root / routes['resources']['policy-assets']['source_path'])
    policy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(policy)
    return routes, policy, policy.catalog_paths(root)


def repository_inputs(source, inputs, target=None, head=None, observations=None):
    """Build each destination manifest from exactly its resulting asset bytes."""
    catalog = _repository_policy(source)
    if catalog is None:
        return inputs
    routes, _, paths = catalog
    manifest_path = routes['resources']['policy-manifest']['source_path']
    if not set(inputs) & (set(paths.values()) | {manifest_path}):
        return inputs
    if target is None:
        return _render_repository_inputs(source, inputs)
    names = set(common_paths(source))
    target_registry = target / 'registry/resources.json'
    if target_registry.is_file():
        # Existing repositories can use an older operation schema. Only their
        # declared resource paths are needed to preserve unselected files here;
        # the resulting source-version candidate is validated below.
        previous = json.loads(target_registry.read_text(encoding='utf-8'))
        names.update(checked_path(record['source_path'])
                     for record in previous['resources'].values()
                     if record.get('sync', True))
    candidate = {}
    for relative in sorted(names | set(inputs)):
        if relative in inputs:
            candidate[relative] = dict(inputs[relative])
        else:
            state = snapshot(target, head, relative)
            if state['data'] is not None:
                candidate[relative] = state
                if observations is not None:
                    observations.append((target, head, relative, state))
    with tempfile.TemporaryDirectory(prefix='.econ-sync-candidate-', dir=source.parent) as temporary:
        staged = Path(temporary)
        for relative, state in candidate.items():
            if state['data'] is None:
                continue
            path = staged / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(state['data'])
            path.chmod(0o755 if state['mode'] == '100755' else 0o644)
        entries = [name for name in inputs if re.fullmatch(r'skills/[^/]+/SKILL\.md', name)]
        rendered = _render_repository_inputs(staged, candidate, entries)
    return {path: rendered[path] for path in set(inputs) | {manifest_path}}


def _render_repository_inputs(source, inputs, entries=None):
    """Render a repository candidate, preserving raw source snapshots separately."""
    entries = ([name for name in inputs if re.fullmatch(r'skills/[^/]+/SKILL\.md', name)]
               if entries is None else entries)
    from export_project import validate_required_bodies
    routes = load_routes(source)
    resources = routes['resources']
    by_path = {record['source_path']: rid for rid, record in resources.items()}
    rendered = {path: dict(state) for path, state in inputs.items()}
    def replace(path, data):
        rendered[path].update(data=data, sha256=hashlib.sha256(data).hexdigest(), git_blob=blob(data))
    for path in entries:
        replace(path, transform_entry_references(routes, by_path[path], inputs[path]['data'].decode('utf-8'), 'source').encode('utf-8'))
    manifest_path = resources['policy-manifest']['source_path']
    if manifest_path not in rendered:
        raise ValueError('Repository skill synchronization requires its policy manifest and runtime dependency closure')
    spec = importlib.util.spec_from_file_location('sync_policy_assets', source / resources['policy-assets']['source_path'])
    policy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(policy)
    paths = {key: path for key, path in policy.catalog_paths(source).items()
             if resources[by_path[path]].get('sync', True)}
    missing = set(paths.values()) - rendered.keys()
    if missing:
        raise ValueError('Repository synchronization lacks runtime dependencies: ' + ', '.join(sorted(missing)))
    assets = {key: rendered[path]['data'] for key, path in paths.items()}
    catalog = policy.build_manifest(assets, paths=paths)
    operations = [resolve_operation(routes, op['id']) for op in routes['operations']]
    selections = {rid: {'whole_resource': True} for rid, record in resources.items() if record['source_path'] in rendered}
    validate_required_bodies(routes, operations, selections, lambda rid: rendered[resources[rid]['source_path']]['data'])
    for operation in operations:
        policy.select_manifest(catalog, assets, operation['canonical_operation'])
    replace(manifest_path, (json.dumps(catalog, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    contents = {path: state['data'].decode('utf-8') for path, state in rendered.items() if state['data'] is not None}
    # Validate every entry link against the same candidate bytes to be published.
    # Other documents can include optional source-distribution links outside scope.
    from export_project import rewrite_markdown, markdown_sections
    from urllib.parse import unquote
    for path in entries:
        def check(link):
            parsed = urlsplit(link)
            if parsed.scheme or parsed.netloc:
                return link
            target = os.path.normpath(str(Path(path).parent / unquote(parsed.path))) if parsed.path else path
            if target not in contents:
                raise ValueError('Missing synchronized entry dependency: ' + path + ': ' + link)
            if parsed.fragment and parsed.fragment not in {h['id'] for h in markdown_sections(contents[target])[1]}:
                raise ValueError('Missing synchronized entry section: ' + path + ': ' + link)
            return link
        rewrite_markdown(contents[path], check)
    return rendered


def _synchronize(source, targets, *, apply=False, expected=None, expected_source=None,
                expected_content=None, paths=None, deletes=(), releases=(), claims=None, migrate=False):
    source, source_name, source_head = repository(source)
    destinations = [repository(target) for target in targets]
    roots = [source, *(item[0] for item in destinations)]
    if len(set(roots)) != len(roots):
        raise ValueError("Source and destination roots must be distinct")
    names = [item[1] for item in destinations]
    if len(set(names)) != len(names):
        raise ValueError("Specify each complete destination identity once")
    expected, claims = expected or {}, claims or {}
    if set(expected) - set(names):
        raise ValueError("Expected HEAD supplied for an unselected destination")
    selected = {checked_path(p) for p in (common_paths(source) if paths is None and not deletes and not releases else (paths or []))}
    released = {checked_path(p) for p in releases}
    deleted = {checked_path(p) for p in deletes}
    if not selected and not deleted and not released:
        raise ValueError("Select at least one managed file")
    if (selected | deleted) & released:
        raise ValueError("A released path cannot also be copied or deleted")
    if selected & deleted:
        raise ValueError("A path cannot be both copied and deleted")
    managed = selected | deleted
    catalog = _repository_policy(source)
    if catalog is not None:
        routes, _, asset_paths = catalog
        manifest_path = routes['resources']['policy-manifest']['source_path']
        if managed & (set(asset_paths.values()) | {manifest_path}):
            managed.add(manifest_path)
    if any(name not in names or path not in managed for name, path in claims):
        raise ValueError("Claim supplied outside the selected destinations or paths")
    if apply and expected_source != source_head:
        raise ValueError(f"Expected source HEAD mismatch or absent: {source_name}; actual {source_head}")
    for _, name, head in destinations:
        if apply and expected.get(name) != head:
            raise ValueError(f"Expected target HEAD mismatch or absent: {name}; actual {head}")

    mode_configs, mode_context = {}, {}
    for root, _, head in [(source, source_name, source_head), *destinations]:
        config = git(root, "config", "--get", "core.filemode", required=False)
        mode_configs[root] = config
        modes = {}
        if config == b"false\n":
            for entry in git(root, "ls-tree", "-r", "-z", head, "--", *sorted(managed | {RECEIPT_PATH})).split(b"\0"):
                if entry:
                    metadata, relative = entry.decode().split("\t", 1)
                    modes[relative] = metadata.split()[0]
        mode_context[root] = modes
    def snap(root, head, relative):
        return snapshot(root, head, relative, modes=mode_context[root])

    inputs = {}
    committed = True
    for relative in sorted(selected):
        state = snap(source, source_head, relative)
        if state["data"] is None:
            raise ValueError(f"Source file absent: {relative}; deletion requires --delete")
        committed &= (state["git_blob"], state["mode"]) == head_file(source, source_head, relative)
        inputs[relative] = state
    for relative in deleted:
        committed &= head_file(source, source_head, relative) == (None, None)
        if snap(source, source_head, relative)["data"] is not None:
            raise ValueError(f"Deletion source must be absent: {relative}")
        inputs[relative] = {"data": None, "sha256": None, "git_blob": None, "mode": None}
    content_id = hashlib.sha256(canonical([[p, inputs[p]["sha256"], inputs[p]["mode"]] for p in sorted(inputs)] + [[p, "released", None] for p in sorted(released)])).hexdigest()
    if expected_content is not None and expected_content != content_id:
        raise ValueError("Expected source content does not match selected inputs")
    if apply and not committed and expected_content != content_id:
        raise ValueError("Working source requires --expect-source-content from the reviewed comparison")
    raw_inputs = inputs
    report = {"source_repository": source_name, "source_head": source_head,
              "source_state": "committed" if committed else "working",
              "common_content_id": content_id, "managed_paths": sorted(managed), "released_paths": sorted(released), "targets": []}
    observations, indexes, writes, receipts, conflicts = [], [], [], [], []
    different = False
    for root, name, head in destinations:
        inputs = repository_inputs(source, raw_inputs, root, head, observations)
        integration = snap(root, head, RECEIPT_PATH)
        original = integration["data"] or b""
        version, old_receipt, _, _ = read_receipt(original)
        all_released = released | set(old_receipt.get("released_paths", []))
        if managed & all_released:
            raise ValueError("Previously released local paths cannot be synchronized")
        old_rows = baseline(old_receipt, version, source, source_name, name, migrate, all_released)
        receipt_index = index_file(root, RECEIPT_PATH)
        indexes.append((root, RECEIPT_PATH, receipt_index))
        if not index_matches_head(root, head, RECEIPT_PATH, receipt_index):
            conflicts.append(f"{name}:{RECEIPT_PATH}: staged receipt changes are protected")
        rows, new_rows = [], dict(old_rows)
        for relative, desired in sorted(inputs.items()):
            current = snap(root, head, relative)
            observations.append((root, head, relative, current))
            staged = index_file(root, relative)
            indexes.append((root, relative, staged))
            previous = old_rows.get(relative)
            matches = signature(current) == signature(desired)
            repair_execute = desired["mode"] == current["mode"] == "100755" and current.get("filesystem_mode") != "100755"
            matches = matches and not repair_execute
            own = previous is not None and signature(current) == (previous["sha256"], previous["mode"])
            claimed = claims.get((name, relative)) == fingerprint(current)
            conflict = None
            if not own and not claimed and (previous is not None or current["data"] is not None):
                conflict = "target changed since receipt" if previous else "existing file requires explicit ownership claim"
            if (name, relative) in claims and not claimed:
                conflict = "claim fingerprint does not match target"
            if not index_matches_head(root, head, relative, staged):
                conflict = "staged target changes are protected"
            if desired["mode"] is not None and desired["mode"] != (current["mode"] or "100644") and mode_configs[root] == b"false\n":
                conflict = "executable mode change requires Git core.filemode=true; synchronization does not stage index changes"
            if conflict:
                conflicts.append(f"{name}:{relative}: {conflict}")
            different |= not matches
            rows.append({"path": relative, "source_sha256": desired["sha256"],
                         "source_mode": desired["mode"], "destination_fingerprint": fingerprint(current),
                         "repair_execute_bit": repair_execute,
                         "previous_sha256": previous["sha256"] if previous else None,
                         "destination_index": staged,
                         "different": not matches, "conflict": conflict})
            if not matches and not conflict:
                writes.append((root, head, relative, current, desired))
            new_rows[relative] = {"path": relative, "state": "deleted" if desired["data"] is None else "present",
                                  "sha256": desired["sha256"], "git_blob": desired["git_blob"],
                                  "mode": desired["mode"], "source_repository": source_name,
                                  "source_commit": source_head}
        receipt = {"schema_version": 2, "source_repository": source_name,
                   "source_base_commit": source_head, "source_state": report["source_state"],
                   "common_content_id": content_id, "target_repository": name,
                   "paths": [new_rows[p] for p in sorted(new_rows)], "released_paths": sorted(all_released)}
        updated = receipt_bytes(original, receipt)
        observations.append((root, head, RECEIPT_PATH, integration))
        if updated != original:
            different = True
            desired = {"data": updated, "sha256": hashlib.sha256(updated).hexdigest(),
                       "git_blob": blob(updated), "mode": integration["mode"] or "100644"}
            receipts.append((root, head, RECEIPT_PATH, integration, desired))
        report["targets"].append({"repository": name, "head": head, "files": rows})
    report["conflicts"] = conflicts
    report["applied"], report["different"] = False, different
    if apply:
        if conflicts:
            raise ValueError("Conflicts:\n" + "\n".join(conflicts))

        def verify_inputs():
            if repository(source) != (source, source_name, source_head):
                raise ValueError("Source repository changed during synchronization")
            for p, before in raw_inputs.items():
                if signature(snap(source, source_head, p)) != signature(before):
                    raise ValueError(f"Source changed during synchronization: {p}")
            by_root = {}
            for root, relative, before_index in indexes:
                by_root.setdefault(root, {})[relative] = before_index
            for root, previous_index in by_root.items():
                current_index = {p: [] for p in previous_index}
                for entry in git(root, "ls-files", "--stage", "-z", "--", *previous_index).split(b"\0"):
                    if entry:
                        metadata, relative = entry.decode().split("\t", 1)
                        mode, oid, stage = metadata.split()
                        current_index[relative].append((oid, mode, stage))
                for relative, before_index in previous_index.items():
                    if tuple(current_index[relative]) != before_index:
                        raise ValueError(f"Target index changed during synchronization: {relative}")
            for root, before_config in mode_configs.items():
                if git(root, "config", "--get", "core.filemode", required=False) != before_config:
                    raise ValueError("Git mode configuration changed during synchronization")
            for root, name, head in destinations:
                if repository(root) != (root, name, head):
                    raise ValueError(f"Target repository changed during synchronization: {name}")

        verify_inputs()
        for root, head, relative, before in observations:
            if signature(snap(root, head, relative)) != signature(before):
                raise ValueError(f"Changed during preflight: {relative}")
        completed = []
        try:
            for target_root in sorted({root for root, _, _, _, _ in [*writes, *receipts]}, key=str):
                _journal_write(target_root, [row for row in [*writes, *receipts] if row[0] == target_root])
            for root, head, relative, before, desired in [*writes, *receipts]:
                # Recheck this target immediately; shared inputs and all applied
                # results are checked once at each publication boundary.
                expected_name = next(name for destination, name, _ in destinations if destination == root)
                if repository(root) != (root, expected_name, head):
                    raise ValueError("Target repository changed during synchronization")
                prior_index = next(state for index_root, index_path, state in indexes
                                   if index_root == root and index_path == relative)
                if index_file(root, relative) != prior_index:
                    raise ValueError(f"Target index changed during synchronization: {relative}")
                if git(root, "config", "--get", "core.filemode", required=False) != mode_configs[root]:
                    raise ValueError("Git mode configuration changed during synchronization")
                if signature(snap(root, head, relative)) != signature(before):
                    raise ValueError(f"Target changed during synchronization: {relative}")
                _atomic_write(safe_file(root, relative), desired["data"], desired["mode"])
                completed.append((root, head, relative, before, desired))
            verify_inputs()
            adopted = {(root, relative): desired for root, _, relative, _, desired in completed}
            for root, head, relative, before in observations:
                final = adopted.get((root, relative), before)
                if signature(snap(root, head, relative)) != signature(final):
                    raise ValueError(f"Final content verification failed: {relative}")
        except BaseException as error:
            unresolved = []
            for target_root in sorted({row[0] for row in [*writes, *receipts]}, key=str):
                try:
                    _recover_journal(target_root)
                except (OSError, ValueError) as recovery_error:
                    unresolved.append(str(recovery_error))
            detail = f"; concurrent files retained: {', '.join(unresolved)}" if unresolved else "; task writes rolled back"
            if not isinstance(error, (OSError, ValueError)):
                raise
            raise ValueError(f"Incomplete synchronization: {error}{detail}") from error
        for target_root in sorted({row[0] for row in [*writes, *receipts]}, key=str):
            _metadata_file(target_root, SYNC_JOURNAL).unlink()
        report["applied"] = True
    return report, 0 if apply or not different else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, action="append", required=True)
    parser.add_argument("--path", action="append", help="Explicit copied relative path; default: COMMON_PATHS")
    parser.add_argument("--delete", action="append", default=[], help="Explicit removed relative path, absent from source")
    parser.add_argument("--release", action="append", default=[], help="Release receipt ownership without touching local files or index")
    parser.add_argument("--release-local-configs", action="store_true", help="Release receipt ownership for local Codex settings; retain the local file")
    parser.add_argument("--move", action="append", default=[], help="OLD=NEW; source NEW exists and OLD is absent")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expect-source-head")
    parser.add_argument("--expect-source-content")
    parser.add_argument("--expect-head", nargs="+", action="extend", default=[])
    parser.add_argument("--claim", action="append", default=[], help="HOST/OWNER/REPO:PATH=SHA256:MODE or =absent")
    parser.add_argument("--migrate-receipt", action="store_true", help="Verify and migrate the recorded v1 baseline")
    args = parser.parse_args()
    try:
        expected, claims = {}, {}
        for item in args.expect_head:
            name, separator, value = item.partition("=")
            if not separator or name in expected or not re.fullmatch(r"[0-9a-f]{40,64}", value):
                raise ValueError("Invalid or repeated expected target HEAD")
            expected[name] = value
        for item in args.claim:
            location, separator, value = item.partition("=")
            name, colon, path = location.rpartition(":")
            if not separator or not colon or (name, path) in claims or not re.fullmatch(r"(?:[0-9a-f]{64}:100(?:644|755)|absent)", value):
                raise ValueError("Invalid or repeated ownership claim")
            claims[(name, checked_path(path))] = value
        releases = [*args.release, *(LOCAL_CONFIG_PATHS if args.release_local_configs else ())]
        copied = list(args.path) if args.path is not None else ([] if args.move or args.delete or releases else None)
        deleted = list(args.delete)
        for item in args.move:
            old, separator, new = item.partition("=")
            if not separator:
                raise ValueError("Move must be OLD=NEW")
            deleted.append(old)
            copied.append(new)
        report, status = synchronize(
            args.source, args.target, apply=args.apply, expected=expected,
            expected_source=args.expect_source_head, expected_content=args.expect_source_content,
            paths=copied, deletes=deleted, releases=releases, claims=claims, migrate=args.migrate_receipt,
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"Sync: {error}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(status)


if __name__ == "__main__":
    main()
