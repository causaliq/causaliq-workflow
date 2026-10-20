# Metadata Structure Standardisation

The design decision is recorded in
[Metadata Structure](architecture/metadata_structure.md).

## Near-term task

Standardise every action on schema version 2: framework provenance,
`inputs` and `result` blocks, the reserved `history` block, and version 1
read compatibility. Existing action metadata moves into `result`; the
input/result classification is a separate values audit.

## Follow-on tasks

- **Values audit:** classify fields into `inputs` and `result`, and check
  each action's completeness and usefulness.
- **History population:** the reserved `history` step parameter for
  one-to-one aggregate steps.
- **Reporting:** `plot` filtering and categorical summarisation.
- **Hat 2 clean-up:** consolidate duplicate flatteners and remove dead
  write paths.
