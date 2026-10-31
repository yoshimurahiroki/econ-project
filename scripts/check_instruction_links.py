"""Check registered instruction links in canonical and deployed layouts."""
import argparse
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit

from export_project import markdown_sections, rewrite_markdown


def check(root: Path, layout: str) -> list[str]:
    registry = json.loads((root / 'registry/resources.json').read_text())
    placements = json.loads((root / 'registry/placements.json').read_text())
    paths = {record['source_path'] if layout == 'source' else
             placements['resources'][name]['deployment_path']
             for name, record in registry['resources'].items()
             if not record.get('source_distribution_only')}
    if layout == 'deployed':
        paths.update(('PROJECT_INSTRUCTIONS.txt', 'ECON_INDEX.md', 'OPTIONAL_INPUTS.md'))
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
        if relative == 'PROJECT_INSTRUCTIONS.txt' and 'SOURCE.md identifies' in text:
            validate('SOURCE.md')
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--layout', choices=('source', 'deployed', 'both'), default='both')
    args = parser.parse_args()
    layouts = ('source', 'deployed') if args.layout == 'both' else (args.layout,)
    failures = [failure for layout in layouts for failure in check(args.root.resolve(), layout)]
    for failure in failures:
        print(failure)
    print(f'{len(failures)} instruction link failures; layouts={",".join(layouts)}')
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
