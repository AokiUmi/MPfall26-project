# Mock detector

Static analysis of Python test mocks. Requires Python 3.9+; no runtime dependencies.

## Run

From the repository root:

```bash
cd adeline
python3 -m mock_detector examples/test_shop.py --source-root examples --target shop.calculate_total --boundary shop.fetch_price
python3 -m unittest discover -s tests -v
```

Add `--format json` for pipeline output. To call it from another component, install it with `python3 -m pip install -e ./adeline` from the repository root, then use `mock-detector` or import `analyze`.

```python
from mock_detector import analyze

findings = analyze(
    "/path/to/test_generated.py",
    targets=["package.module.function"],
    source_root="/path/to/repo/src",
    boundaries=["package.client.fetch_remote"],
)
```

`source_root` is the Python import root, not necessarily the repository root. Run one target and its generated test file per case. Boundary prefixes are optional and should identify specific external interactions.

## Output

| Rule | Meaning |
|---|---|
| OM001 | A patch replaces the declared function under test. |
| OM002 | A project-internal target is mocked; needs review. |
| BOUNDARY | Matches an explicitly configured boundary prefix. |
| STATE_PATCH | Changes dictionary state with `patch.dict`; needs review. |
| UNRESOLVED | Dynamic target or insufficient information. |

JSON contains `schema_version`, `files_scanned`, `findings`, and `errors`. Each finding includes its location, target, rule, status, explanation, and suggested change.

Exit code is 0 by default, including when findings exist; 2 means an input or parse error. Use `--fail-on warning` or `--fail-on review` to return 1 for matching findings.

## Code layout

- `mock_detector/detector.py`: AST traversal, target resolution, and rules.
- `mock_detector/__main__.py`: CLI and JSON output.
- `tests/test_detector.py`: regression tests.
- `examples/`: small detector input examples.

## What to work on next

1. Try a real benchmark case and check target resolution against its imports.
2. Add failing regression cases before extending resolution or rules.
3. Agree on harmful-mock labels before changing OM002 from a review candidate into an experimental prediction.

Supported forms include `patch`, `patch.object`, `patch.multiple`, and `patch.dict`, with common unittest.mock aliases and standard pytest-mock fixtures. Explicit source import bindings are followed.

This version does not analyze control flow, assertions, or call graphs. Name shadowing, dynamic targets, custom fixture aliases, star imports, relative test imports, and package re-exports may not resolve correctly. Unparseable source files are skipped during indexing. An internal mock is not automatically harmful, and a configured boundary is not independently verified. Benchmark accuracy has not been measured yet.
