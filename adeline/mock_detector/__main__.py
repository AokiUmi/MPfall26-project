import argparse
import json
import sys
from pathlib import Path

from .detector import SCHEMA_VERSION, analyze


def main(argv=None):
    parser = argparse.ArgumentParser(description="Inspect Python test mocks without executing code.")
    parser.add_argument("paths", nargs="+", help="Python files or directories (directories scan test_*.py and *_test.py)")
    parser.add_argument("--target", action="append", default=[], help="Dotted function under test; repeatable")
    parser.add_argument("--source-root", type=Path, help="Import root: e.g. repo/src for a src layout")
    parser.add_argument("--boundary", action="append", default=[], help="Explicit allowed dotted prefix; repeatable")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--fail-on", choices=["none", "warning", "review"], default="none")
    args = parser.parse_args(argv)
    files, errors, findings = set(), [], []
    if args.source_root is not None and not args.source_root.is_dir():
        errors.append({"file": str(args.source_root), "message": "Source root is not a directory"})
    for name in args.paths:
        path = Path(name)
        if path.is_dir():
            files.update(p for p in path.rglob("*.py") if p.name.startswith("test_") or p.name.endswith("_test.py"))
        elif path.is_file():
            files.add(path)
        else:
            errors.append({"file": name, "message": "Path does not exist"})
    for path in sorted(files):
        try:
            findings.extend(analyze(path, args.target, args.source_root, args.boundary))
        except (OSError, SyntaxError, ValueError) as exc:
            errors.append({"file": str(path), "message": str(exc)})
    if not files and not errors:
        errors.append({"file": None, "message": "No test files found"})
    report = {"schema_version": SCHEMA_VERSION, "files_scanned": len(files), "findings": findings, "errors": errors}
    if args.format == "json":
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for f in findings:
            print(f"{f['file']}:{f['line']}:{f['column']} [{f['rule_id']}/{f['status']}] {f['target'] or '<dynamic>'}: {f['message']}\n  {f['suggestion']}")
        for error in errors:
            print(f"ERROR {error['file']}: {error['message']}", file=sys.stderr)
        print(f"Scanned {len(files)} files; found {len(findings)} patch instances; {len(errors)} errors.")
    if errors:
        return 2
    if args.fail_on != "none" and any(f["status"] == "warning" or (args.fail_on == "review" and f["status"] == "review") for f in findings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
