"""Conservative public payload check; optional private deny list stays outside Git."""
import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_SUFFIXES = {".pdf", ".epub", ".xlsx", ".xls", ".csv", ".zip", ".png", ".jpg", ".db", ".sqlite"}


def check(files, deny=()):
    errors = []
    for name, content in files:
        path = Path(name)
        if path.parts[0] in {"private", "outputs"} or path.suffix.lower() in FORBIDDEN_SUFFIXES or path.name.startswith(".env"):
            errors.append({"file": name, "reason": "forbidden runtime/input artifact"})
            continue
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            errors.append({"file": name, "reason": "unreviewed binary"})
            continue
        patterns = [r"gh[pousr]_" + r"[A-Za-z0-9]{20,}", r"-----BEGIN " + r"(?:RSA |OPENSSH )?PRIVATE KEY-----",
                    r"https?://(?:www\.)?workbuddy\.link/p/" + r"[A-Za-z0-9]+",
                    r"[A-Za-z]:[/\\]Users[/\\]" + r"[^\s/\\]+", r"(?<![A-Za-z0-9])\d{18,}(?![A-Za-z0-9])"]
        if any(re.search(p, text) for p in patterns):
            errors.append({"file": name, "reason": "credential, private share URL, local user path or long account identifier"})
        if any(x and x.casefold() in text.casefold() for x in deny):
            errors.append({"file": name, "reason": "matches private deny-list"})
    return errors


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--git-index", action="store_true")
    p.add_argument("--deny-file", type=Path)
    args = p.parse_args()
    deny = args.deny_file.read_text(encoding="utf-8").splitlines() if args.deny_file else []
    if args.git_index:
        names = subprocess.check_output(["git", "ls-files", "--cached", "-z"], cwd=ROOT).decode().split("\0")
        files = [(n, subprocess.check_output(["git", "show", ":" + n], cwd=ROOT)) for n in names if n]
    else:
        files = [(str(x.relative_to(ROOT)), x.read_bytes()) for x in ROOT.rglob("*") if x.is_file() and not any(y in {".git", "private", "outputs", "__pycache__"} for y in x.relative_to(ROOT).parts)]
    errors = check(files, deny)
    print(json.dumps({"ok": not errors, "files_checked": len(files), "errors": errors}, ensure_ascii=False, indent=2))
    raise SystemExit(bool(errors))
