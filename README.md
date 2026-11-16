# Detecting and Reducing Over-Mocking in LLM-Generated Unit Tests

Compare generated tests, self-reviewed tests, and tests revised using static mock warnings.

## Repository layout

- `adeline/`: AST mock detector, examples, and tests. See [detector README](adeline/README.md).
- Other components can be added in separate top-level folders, with their own dependencies and run instructions.

## Next steps

- Benchmark: provide a pinned repository version, source import root, target function, and generated test file for each case.
- LLM pipeline: call the detector with `--format json` and use its findings during revision.
- Evaluation: agree on annotation labels and how detector rules map to harmful mocks before measuring precision and recall.
