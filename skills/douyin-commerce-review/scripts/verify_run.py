"""Replay evidence, calculations and rendered output against the immutable input."""
import argparse
import json
from pathlib import Path
from review import analyse, digest, load_input, render_report


def verify(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    errors = []
    source = Path(manifest["input_path"])
    if not source.is_file() or digest(source) != manifest["input_sha256"]:
        return {"ok": False, "errors": ["Source missing or fingerprint changed"]}
    for name in ["audit.json", "review.html"]:
        p = directory / name
        if not p.is_file() or digest(p) != manifest["outputs"].get(name):
            errors.append(f"Output fingerprint changed: {name}")
    expected = analyse(load_input(source, manifest["format"]))
    actual = json.loads((directory / "audit.json").read_text(encoding="utf-8"))
    if expected != actual:
        errors.append("Evidence, calculations or findings differ from source replay")
    if (directory / "review.html").read_text(encoding="utf-8") != render_report(expected, manifest):
        errors.append("Rendered report differs from verified audit")
    return {"ok": not errors, "errors": errors, "facts": len(expected["facts"]),
            "calculations": len(expected["calculations"]),
            "limit": "Replay checks input fidelity, not platform truth, external canonical mapping or business effect"}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory", type=Path)
    args = p.parse_args()
    result = verify(args.directory)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["ok"] else 1)
