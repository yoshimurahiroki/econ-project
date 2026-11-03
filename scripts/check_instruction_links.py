"""Check registered instruction links in canonical and deployed layouts."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from urllib.parse import unquote, urlsplit

from export_project import markdown_sections, rewrite_markdown
from route_registry import generate_entries, load_routes, relative as safe_relative


def check(root: Path, layout: str) -> list[str]:
    installed = root / '.agents/registry'
    registry_root = installed if layout == 'deployed' and (installed / 'resources.json').is_file() else root / 'registry'
    registry = json.loads((registry_root / 'resources.json').read_text())
    placements = json.loads((registry_root / 'placements.json').read_text())
    paths = {record['source_path'] if layout == 'source' else
             placements['resources'][name]['deployment_path']
             for name, record in registry['resources'].items()
             if not record.get('source_distribution_only')}
    policy_root = placements.get('deployed', {}).get('policy_root', '.') if layout == 'deployed' else '.'
    if policy_root != '.':
        safe_relative(policy_root)
    instructions = (Path(policy_root) / 'PROJECT_INSTRUCTIONS.txt').as_posix()
    if layout == 'deployed':
        paths.update((Path(policy_root) / name).as_posix()
                     for name in ('PROJECT_INSTRUCTIONS.txt', 'ECON_INDEX.md', 'OPTIONAL_INPUTS.md'))
    failures = []
    for relative in sorted(paths):
        source = root / relative
        if source.suffix not in ('.md', '.txt', '.mdc', ''):
            continue
        if not source.is_file():
            failures.append(f'{layout}: missing instruction {relative}')
            continue

        def validate(link: str) -> str:
            parsed = urlsplit(link)
            if parsed.scheme or link.startswith('//'):
                return link
            target = (source.parent / unquote(parsed.path)).resolve() if parsed.path else source.resolve()
            if not target.is_relative_to(root) or not target.is_file():
                failures.append(f'{layout}: {relative}: missing file {link}')
            elif parsed.fragment and target.suffix in ('.md', '.txt', '.mdc', ''):
                anchors = {row['id'] for row in markdown_sections(target.read_text())[1]}
                if unquote(parsed.fragment) not in anchors:
                    failures.append(f'{layout}: {relative}: missing anchor {link}')
            return link

        text = source.read_text()
        rewrite_markdown(text, validate)
        if relative == instructions and 'SOURCE.md identifies' in text:
            validate('SOURCE.md')
    return failures


def check_generated(root: Path) -> list[str]:
    """Compare canonical generated entries through their existing producer."""
    root = root.resolve()
    routes = load_routes(root)
    # The entry producer lists source-only records but never reads their payloads.
    names = {row['source_path'] for row in routes['resources'].values()
             if not row.get('source_distribution_only')}
    names.update(('registry/operations.json', 'registry/resources.json',
                  'registry/placements.json', 'scripts/route_registry.py', 'README.md'))
    with tempfile.TemporaryDirectory(prefix='instruction-generation-') as temporary:
        stage = Path(temporary)
        before = {}
        for name in sorted(names):
            source = root / name
            if any(path.is_symlink() for path in (source, *source.parents) if path != root.parent):
                raise ValueError('Generated instruction input uses a symlink: ' + name)
            if not source.is_file():
                raise ValueError('Missing generated instruction input: ' + name)
            before[name] = source.read_bytes()
            destination = stage / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        generate_entries(stage)
        return ['source: generated instruction differs from its producer: ' + path.relative_to(stage).as_posix()
                for path in sorted(stage.rglob('*')) if path.is_file()
                and path.read_bytes() != before.get(path.relative_to(stage).as_posix())]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--layout', choices=('source', 'deployed', 'both'), default='both')
    parser.add_argument('--generated', action='store_true', help='Compare source-generated entries in a disposable copy')
    args = parser.parse_args()
    layouts = ('source', 'deployed') if args.layout == 'both' else (args.layout,)
    failures = [failure for layout in layouts for failure in check(args.root.resolve(), layout)]
    if args.generated:
        if args.layout != 'source':
            parser.error('--generated selects the canonical source layout; use --layout source')
        failures.extend(check_generated(args.root.resolve()))
    for failure in failures:
        print(failure)
    print(f'{len(failures)} instruction link failures; layouts={",".join(layouts)}')
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
