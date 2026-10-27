# Action Parameter Contract

## Purpose

This document is the design record for how action parameters, defaults and
"not applicable" values work across CausalIQ packages. It exists so that a
workflow keeps working as parameters and defaults change, and so that users
never have to distinguish "use the default" from "this parameter does not
apply".

## The Contract

- A parameter is **omitted** when the user wants the declared default, and
  omitted when the parameter does not apply to that action in that
  configuration. The two cases are indistinguishable to the user.
- Every declared default is a value the user could have supplied, and the
  framework supplies it before the action runs. A default is therefore
  defined once, in the action's input specification.
- A parameter that does not apply is **absent** from the step and from the
  metadata. It is never recorded as `null`.
- The `parameters` metadata block records the **effective** value of every
  parameter that applied, expressed in that parameter's own vocabulary.
  Resolved values (`variant`, `hyperparameters`) stay in `parameters`; a
  state that has an explicit token (`no-randomise`) is recorded as that
  token.

## Declaration

Inputs are declared with `causaliq_core.ActionInput`:

```python
NO_DEFAULT  # sentinel: the parameter has no default

ActionInput(
    name="randomise",
    description="Randomisation options",
    required=False,
    default="no-randomise",
    type_hint="list[str] or str",
    choices=("no-randomise", "var_order", "var_best"),
)
```

- `default` is either a concrete value or `NO_DEFAULT`.
- `default=None` is rejected: `None` cannot distinguish "no default" from
  "the default is null", and it is not a value a user should write.
- `choices` is the closed set of values the parameter may take, or `None`
  when any value of the declared type is accepted. For a list-valued
  parameter the choices enumerate the values each element may take, in
  addition to any scalar "off" token.
- An enumerated default must appear in `choices`. An open-domain default
  (for example `timeout=60`) is inherently a legal value.

## Three Kinds of Parameter

| Kind | Declaration | Framework behaviour | Recorded value |
|------|-------------|---------------------|----------------|
| Enumerated with a default (`randomise`) | `default` plus `choices` | injects the default when omitted | the effective token or list |
| Open domain with a default (`timeout`) | `default`, no `choices` | injects the default when omitted | the effective value |
| Conditional (`seed`, `reference`, `trace`) | `required=False`, `NO_DEFAULT` | injects nothing | omitted when not applicable |

## Runtime Resolution

`causaliq_core.resolve_action_parameters(provider, action, supplied)`
produces the effective parameters:

- a supplied value wins;
- a parameter supplied as `None` marks a matrix dimension that is not
  applicable: it is dropped and does **not** receive a default;
- an omitted parameter takes its declared default when it applies to the
  action;
- applicability comes from the provider's `action_parameters` mapping when
  it declares one, otherwise every declared input applies.

`causaliq-workflow` calls the resolver in both the execution and the
validation path, so a workflow validates and runs with the same effective
parameters.

## Metadata

The `parameters` block follows the same rule as the action:

- explicit values are recorded as supplied;
- defaulted values are recorded as the declared default;
- parameters that do not apply are absent.

No value in `parameters` is ever `null`. Because defaults are recorded as
values, a filter can address them directly, for example
`learn_graph.randomise == 'no-randomise'`.

## Tokens

A token expresses a state that has no other natural value:

| Token | Meaning |
|-------|---------|
| `no-randomise` | apply no randomisation (the `randomise` default) |
| `all` | use every row (the `sample_size` default) |
| `impute` | infer variable types from the data (the `variable_types` default) |

Tokens are ordinary values: they can be supplied explicitly, stored in a
workflow matrix, compared in a filter, and passed to a called workflow.

## Passing Defaults Through Sub-workflows

A caller can pass a token through a `{{placeholder}}` so that a child
reaches the same state as omitting the parameter:

```yaml
matrix:
  randomise: [no-randomise, var_best]

steps:
  - name: Learn
    uses: ./modules/learn-graphs.yml
    with:
      randomise: "{{randomise}}"
```

Forwarding a parameter only when the caller sets it is not supported yet;
that requires workflow-level default declaration.

## Enforcement

`CausalIQActionProvider.__init_subclass__` checks every declared input when
the provider class is defined:

- a specification key must match its declared `name`;
- a required input must not declare a default;
- a default must not be `None`;
- `choices`, when declared, must be non-empty, must not contain `None`, and
  must contain the default.

A failing provider is surfaced by the workflow registry as a discovery
error rather than an import crash. Each package also carries a test that
asserts the invariant, so CI catches drift before release.

## See Also

- [Architecture Overview](overview.md) - core package structure
- `causaliq-workflow/docs/architecture/metadata_structure.md` - the
  parameters and result blocks of a cache entry
- `causaliq-workflow/docs/userguide/core_concepts.md` - workflow
  parameters, matrix values and template variables
- `causaliq-workflow/docs/userguide/common_parameters.md` - parameters
  shared across actions
