#!/usr/bin/env python3
"""Build a LuaLaTeX document, restoring its previous PDF if a build step fails."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def has_citations(aux: Path, directory: Path, seen: set[Path] | None = None) -> bool:
    """Inspect BibTeX's auxiliary closure; incomplete closure must reach BibTeX."""
    seen = set() if seen is None else seen
    path = aux.resolve()
    if path in seen or not path.is_file():
        return True
    seen.add(path)
    data = path.read_bytes()
    if re.search(rb"\\citation\s*\{", data):
        return True
    for name in re.findall(rb"\\@input\s*\{([^{}]+)\}", data):
        try:
            child = directory / name.decode("utf-8")
        except UnicodeDecodeError:
            return True
        if has_citations(child, directory, seen):
            return True
    return False


def build(source: Path) -> None:
    source = source.absolute()
    if not source.is_file():
        raise FileNotFoundError(f"LaTeX source not found: {source}")
    pdf = source.with_suffix(".pdf")
    latex = [
        "lualatex",
        "-shell-escape",
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-file-line-error",
    ]
    # Keep the original Make working/output directory: relative bibliography
    # paths and nested \include auxiliary files must retain their locations.
    with tempfile.TemporaryDirectory(
        prefix=".latex-backup-", dir=source.parent
    ) as temporary:
        # The supplied journal class aliases the slanted and italic font
        # defaults; fontspec expects distinct defaults during its own setup.
        # Preload only for that class, leaving the user's source unchanged.
        content = source.read_bytes()
        uncommented = b"\n".join(line.split(b"%", 1)[0] for line in content.splitlines())
        journal = re.search(rb"(?m)^\s*\\documentclass\s*(?:\[[^]]*\]\s*)?\{\s*econsocart\s*\}", uncommented)
        if journal:
            copied = Path(temporary) / "source.tex"
            copied.write_bytes(content)
            latex.extend([f"-jobname={source.stem}",
                          r"\RequirePackage{fontspec}\input{" + copied.relative_to(source.parent).as_posix() + "}"])
        else:
            latex.append(f"./{source.name}")
        backup = Path(temporary) / pdf.name
        if pdf.exists():
            shutil.copy2(pdf, backup)
        # Even a zero-exit run must produce a new PDF (empty documents may not).
        pdf.unlink(missing_ok=True)
        try:
            subprocess.run(latex, cwd=source.parent, check=True)
            aux = source.with_suffix(".aux")
            if aux.is_file() and b"\\bibdata{" in aux.read_bytes():
                if has_citations(aux, source.parent):
                    subprocess.run(
                        ["pbibtex", f"./{source.stem}"],
                        cwd=source.parent,
                        check=True,
                    )
                else:
                    # An earlier cited version can leave a bibliography which
                    # would otherwise be printed by this citation-free build.
                    source.with_suffix(".bbl").unlink(missing_ok=True)
            subprocess.run(latex, cwd=source.parent, check=True)
            subprocess.run(latex, cwd=source.parent, check=True)
            # Page backreferences can first reach .brf on the third pass.
            # Read them once more so a clean paper build includes their pages.
            if source.with_suffix(".brf").is_file():
                subprocess.run(latex, cwd=source.parent, check=True)
            if not pdf.is_file():
                raise FileNotFoundError(f"LaTeX produced no PDF: {pdf}")
        except BaseException:
            if backup.is_file():
                backup.replace(pdf)
            else:
                pdf.unlink(missing_ok=True)
            raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source", type=Path, help="root .tex file (relative or absolute)"
    )
    args = parser.parse_args()
    try:
        build(args.source)
    except subprocess.CalledProcessError as exc:
        print(f"LaTeX build failed: {exc}", file=sys.stderr)
        return exc.returncode if exc.returncode > 0 else 1
    except OSError as exc:
        print(f"LaTeX build failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
