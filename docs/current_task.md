# refactor codebase according to module and method rules

Plan to refactor all modules to obey the development policies. This is
for standardisation and preparatory work before an analysis and
improvement of slow performance [subsequent tasks].

## Constraints learned from other package refactors

- **Behaviour must stay byte-identical**
- **Preserve import binding sites**
- **No behaviour-free bulk test rewrites**: add focused tests
  only where coverage gaps appear

## Commits

Stage the work as **three to four commits** which the user will do:

1. **workflow.py** is by far the biggest challenge and may need to be done in
several slices of work: aim to split it up into meaningful functional areas:
e.g. validation, execution, matrix handling etc.
1. **remaining modules** can probably be done in one commit (slice)
2. **documentation** — one documentation commit **after** all code and test changes committed

Do not mix documentation-only changes into the code commit.

## Gates after each slice (as in `scripts/check_ci.ps1`)

- `black --check src tests`
- `isort --check-only src tests`
- `flake8 src tests`
- `mypy src/`
- `python scripts/check_code_rules.py --strict src/causaliq_data`

## Outcome

The refactor is complete. `python scripts/check_code_rules.py --strict
src/causaliq_workflow` reports zero breaches across all 26 modules, the full
test suite passes with 100 % coverage, and behaviour is unchanged.

| Stage | Modules refactored | Breaches reported |
| --- | --- | --- |
| Starting point | – | 37 |
| Slice 1 | `workflow` (split into a 12-module sub-package) | 13 |
| Slice 2 | `cli`, `registry`, `schema`, `cache/export`, `cache/import_`, `cache/workflow_cache` | 0 |

### What changed

- `workflow.py` (2199 lines, 926 statements) was decomposed into the
  `workflow/` sub-package of functional mixins which the original module path
  re-exports, so the public API, module paths and import sites are unchanged.
  The decomposition is recorded in the
  [architecture overview](architecture/overview.md).
- The CLI moved its result-reporting helpers into `cli_report.py`, re-used by
  `cli.py`, so `causaliq_workflow.cli._report_results` still resolves.
- Long functions across `cli`, `registry`, `schema` and the `cache` modules
  were split into private helpers, keeping every function within the statement
  and nesting-depth limits.
- Import binding sites and patch targets were preserved: modules whose
  functions are substituted in tests with `monkeypatch.setattr` still intercept
  the calls (for example `causaliq_workflow.workflow.load_workflow_file` and
  `causaliq_workflow.workflow.validate_workflow` resolve through the package).
- Runtime behaviour is unchanged; focused tests were added only where the
  refactor created coverage gaps.

### Verification

- `python scripts/check_code_rules.py --strict src/causaliq_workflow` — zero
  breaches across 26 modules.
- `black --check`, `isort --check-only`, `flake8`, `mypy src/` — clean.
- `pytest` full suite — passes with 100 % coverage.


