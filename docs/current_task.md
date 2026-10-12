# Remove redundant workflow validation pass

## Summary

`cqflow run` validates a workflow twice before executing it:

1. `cli.py` calls `executor.execute_workflow(workflow, mode="validate")`
   to report validation errors early, then
2. `execute_workflow` unconditionally runs `_validate_execution(...)`
   again at the start of the execution call.

Both passes iterate every matrix job and, for AGGREGATE and UPDATE steps,
scan the input caches, so the validation work is duplicated.

## Why it is not urgent

The aggregation scan now reuses a memoised per-cache index (see the
completed "analyse slow performance" task), so the second validation pass
no longer re-reads and decompresses the caches. The remaining cost is the
per-job matching and filter evaluation, which is small but still redundant.

## Proposed change

Skip the second validation when the caller has already validated the same
workflow. Preferred approach:

- Add `execute_workflow(..., validate: bool = True)`.
- Pass `validate=False` from `cli._run_workflow_jobs()`.

## Impact

- No change to behaviour or log output: the CLI still prints
  "VALIDATING ... VALIDATED" once before "EXECUTING".
- The `execute_workflow` mocks in `tests/functional/test_cli.py` must
  accept the new keyword argument.

## Alternatives considered

- Cache the validation result on the executor keyed by the workflow
  object. Fragile (identity-based) and less explicit.
- Move validation entirely into `execute_workflow` and drop the CLI pass.
  Rejected: it would remove the early "VALIDATING/VALIDATED" reporting.

## Scope and constraints

- Hat 1 (Fix) only: no structural refactor or file moves.
- Update only the tests directly affected by the signature change.
- 79-character lines, British English, and the usual quality gates
  (`black`, `isort`, `flake8`, `mypy`, `pytest` at 100% coverage).
- Do not commit changes (development policy).

## Acceptance criteria

- A single `cqflow run` invocation performs the entry-validation pass
  once.
- All existing CLI tests pass with the updated mocks.
- No change to user-visible workflow output.
