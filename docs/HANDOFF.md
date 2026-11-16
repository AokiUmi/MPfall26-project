# Integration notes

## Benchmark input

For each case, provide:

- Repository commit and Python environment.
- Source import root, such as `/path/repo/src`.
- Fully qualified function under test, such as `package.module.function`.
- Generated test file path.
- Optional boundary prefixes agreed during annotation.

One case is enough to start integration; the full benchmark can follow later.

## Pipeline call

After installing the detector from the repository root:

```bash
python3 -m pip install -e ./adeline
mock-detector /path/test_generated.py \
  --source-root /path/repo/src \
  --target package.module.function \
  --format json
```

Alternatively, run `python3 -m mock_detector` from `adeline/` without installing.

Use one target/test case per invocation. Add `--boundary package.client.fetch_remote` for an approved boundary. Multiple targets in one invocation apply to every inspected test.

JSON schema version is `1.0`. Top-level fields are `schema_version`, `files_scanned`, `findings`, and `errors`.

Each finding has:

- `file`, `line`, `column`, `test`: location and function/class context. Lines and columns start at 1; columns are UTF-8 byte offsets.
- `syntax`: patch, object, multiple, or dict.
- `target`, `resolved_target`: patch location and import-resolved target; may be null.
- `rule_id`, `status`, `severity`: classification.
- `message`, `suggestion`: feedback for revision.

Suggested initial feedback: send `warning` and `review` findings to the model, explaining that review candidates are uncertain. Preserve all findings in experiment logs. Agree in advance whether unknown findings are included in prompts. Exit code 2 means inspection failed, not that no mocks were found.

The detector does not run tests or manage LLM attempts. The pipeline should handle generation, revision budgets, execution, coverage, and mutation scores.

## Annotation and evaluation

Agree on harmful, legitimate, and uncertain labels before evaluation. OM001 is a direct target replacement; OM002 only identifies an internal target for review. Decide the binary prediction mapping in advance, or report OM001 and OM001 + OM002 separately.

Count `patch.multiple` attributes as separate instances. Independently enumerate mocks when measuring recall, including mocks the detector misses. Keep unknown cases visible and report resolution coverage. Compute Cohen's kappa from independent annotations before resolving disagreements.

## Continuing development

Detector changes belong in `adeline/`; other components can use their own top-level folders. Keep each component's dependencies and run instructions in that folder. Run `python3 -m unittest discover -s tests -v` from `adeline/` after detector changes.
