"""Generate THIRD-PARTY-NOTICES.txt for the installed build.

Run with the build environment's Python (the x64 venv PyInstaller bundles
from), so the list matches exactly what ships:

    python make_notices.py <output.txt> [--python-license <LICENSE.txt>]

For each installed distribution it records the name, version, declared
license and the full text of any license, notice or copying files it ships.
Components that are not Python packages are listed by hand below.
"""

from __future__ import annotations

import argparse
import re
from importlib import metadata
from pathlib import Path

SKIP = {"pip", "setuptools", "wheel"}  # build tooling, not shipped in the bundle
LICENSE_FILE = re.compile(r"(^|/)(licen[cs]e|copying|notice|authors)[^/]*$", re.IGNORECASE)

MANUAL = [
    (
        "all-MiniLM-L6-v2 embedding model",
        "Apache License 2.0",
        "Sentence embedding model by the sentence-transformers project, distributed by Chroma as an "
        "ONNX export. https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2",
    ),
    (
        "Cinzel and IM Fell English fonts",
        "SIL Open Font License 1.1",
        "Cinzel by Natanael Gama; IM Fell English by Igino Marini. https://openfontlicense.org",
    ),
    (
        "GitHub Copilot CLI (not bundled)",
        "GitHub terms",
        "Installed separately from GitHub through Windows Package Manager when you choose to; "
        "governed by GitHub's own license and terms.",
    ),
]


def declared_license(meta: metadata.PackageMetadata) -> str:
    expr = meta.get("License-Expression")
    if expr:
        return expr.strip()
    lic = (meta.get("License") or "").strip()
    if lic and len(lic) < 120 and "\n" not in lic:
        return lic
    classifiers = [c.split("::")[-1].strip() for c in meta.get_all("Classifier") or [] if c.startswith("License ::")]
    if classifiers:
        return "; ".join(sorted(set(classifiers)))
    return "See license text below" if lic else "Not declared"


def license_texts(dist: metadata.Distribution) -> list[tuple[str, str]]:
    out = []
    for f in dist.files or []:
        name = str(f).replace("\\", "/")
        if ".dist-info/" not in name and ".egg-info/" not in name:
            continue
        if not LICENSE_FILE.search(name) or name.endswith((".py", ".pyc")):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace").strip()
        except (OSError, FileNotFoundError):
            continue
        if text:
            out.append((name.split("/")[-1], text))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("output")
    ap.add_argument("--python-license", default="")
    args = ap.parse_args()

    dists = {}
    for d in metadata.distributions():
        name = (d.metadata.get("Name") or "").strip()
        if name and name.lower() not in SKIP and name.lower() not in dists:
            dists[name.lower()] = d

    lines = [
        "THIRD-PARTY NOTICES FOR PENSIEVE",
        "",
        "Pensieve (MIT License, Copyright (c) 2026 Andy Herman) bundles the components listed",
        "below. Each is used under its own license, reproduced here. Nothing in Pensieve's own",
        "license changes these terms.",
        "",
        "=" * 79,
        "SUMMARY",
        "=" * 79,
    ]
    lines.append(f"Python {__import__('sys').version.split()[0]} (Python Software Foundation License)")
    for key in sorted(dists):
        d = dists[key]
        lines.append(f"{d.metadata['Name']} {d.version} ({declared_license(d.metadata)})")
    for title, lic, _ in MANUAL:
        lines.append(f"{title} ({lic})")

    if args.python_license and Path(args.python_license).is_file():
        lines += ["", "=" * 79, "Python", "=" * 79,
                  Path(args.python_license).read_text(encoding="utf-8", errors="replace").strip()]

    for key in sorted(dists):
        d = dists[key]
        lines += ["", "=" * 79, f"{d.metadata['Name']} {d.version}", "=" * 79,
                  f"License: {declared_license(d.metadata)}"]
        home = d.metadata.get("Home-page") or next(
            (u.split(",", 1)[-1].strip() for u in d.metadata.get_all("Project-URL") or []), "")
        if home:
            lines.append(f"Project: {home}")
        for fname, text in license_texts(d):
            lines += ["", f"--- {fname} ---", text]

    for title, lic, note in MANUAL:
        lines += ["", "=" * 79, title, "=" * 79, f"License: {lic}", note]

    Path(args.output).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.output}: {len(dists)} packages")


if __name__ == "__main__":
    main()
