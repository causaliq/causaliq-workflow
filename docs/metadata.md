# More metadata work

Please plan to make the following improvements to workflow metadata.

* Place holders in a workflow name are not replaced, for example, the {{series}}
placeholder in the name @causaliq-research/papers/variable-ordering/workflows/hc_std.yml
is not replaced by the actual series value in the output messages

```yaml
steps:
  - name: "Learn graph using bnlearn for {{series}}"
    uses: "causaliq-discovery"
```

* the provenance metadata should include details of the the software versions 
(as defined in \_\_init\_\_.py if each package, e.g. `0.8.0.dev4`) used environment and the job was run on (as provided )

## Metadata changes for specific actions

### `causaliq-analysis:evaluate_graph`

* the metrics json should have line feeds in to make it more readable (when exported)
* currently, the extraction of metrics for an empty graph (when the `learn_graph` had failed) - this is somewhat misleading as the matrics extraction itself is not failing

