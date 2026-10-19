# Design for structure and propagation of _meta.json

We have removed the UPDATE ActionPattern, which now means a workflow cache entry is always created by one action only. This provides an opportunity to simplify the current highly-nested metadata. However, we must consider this in the light of requirements to propagate metadata which are not yet fully realized. I wish to discuss the design options with you and agree a way forward.

Here is an example of the current _meta.json structure:

```json
  "metadata": {
    "causaliq-discovery": {
      "learn_graph": {
        "num_runs": 1,
        "algorithm": "hc",
        "hyperparameters": {
          "score": "bic",
          "iss": 1.0,
          "penalty_weight": 1.0
        },

```

which we **could** flatten to something like:

```json
  "package": "causaliq-discovery",
  "action": "learn_graph",
  "num_runs": 1,
  "algorithm": "hc",
  "score": "bic",
  "iss": 1.0,
  "penalty_weight": 1.0
```

**BUT** we also want to be able to filter on, report on, and chart **selected** metadata values, some examples being:

* provide a bar chart of `learn_graph` statuses (ok, time out, invalid input etc.)
* provide a summary of `learn_graph` f1 values but only where the algorithm took less than 1 hour to run
* provide a chart of `learn_graph` f1 values, but only where iss > 10, and sample_sise < 10000>

Thus, we need to be able to filter on, and report on metadata values; and note that this is metadata from **previous actions**, not the one doing the charting, for example.

Thus we have two interelated design issues, firstly how do we propagate metadata from earlier actions e.g. learning graphs, to later actions where they are needed, e.g. plotting charts which may filter by or display these **previous** metadata options.

Some propagation options are:

1. We keep the existing nested metadata structure, and metadata from previous actions (possibly from completely separate workflows) is always included in the current metadata. The metadata grows and grows as it has more
previous provenances to incorporate. Documentation and selection of metadata fields is an issue.

1. The metadata in an entry only relates to the current action. If we wish to use metadata from previous actions
we must merge entries from different caches - e.g. graph caches carry graph learning status information and metrics from a metrics cache. This would be a nightmare for the user to comprehend I feel.

2. We add action-specific metadata copying for relevant actions. For example, we could add a metric `status` to `evaluate_graph` which internally is coded to pick up the status metadata fields from the graph object's metadata and copy it into the metrics object (not NOT the metadata, which retains its purpose of just listing the provenance of the current action). It then becomes just another variable in the metrics object which we can filter by or display as with other metrics such as f1.

At the moment I favour the latter as the simplest and most understandable. This would also allow us to flatten the metadata if we wish.


## All Workflows

Please plan to make the followoing improvements to workflow metadata.

* Place holders in a workflow name are not replaced, for example, the {{series}}
placeholder in the name @causaliq-research/papers/variable-ordering/workflows/hc_std.yml
is not replaced by the actual series value in the output messages

```yaml
steps:
  - name: "Learn graph using bnlearn for {{series}}"
    uses: "causaliq-discovery"
```

* We wish to be able to filter on **any** metadata value (matrix and non-matrix values) e.g. status, elapsed seconds, network, algorithm etc. oto provide powerful and flexible analysis. To accommodate this we could allow structured names in filter conditions e.g.: `learn_graph.hyperparameters.iss > 1.0" OR should the provenence metadata in _meta.json be flattened espeically as we have simplified things bu removing the UPDATE pattern, so each entry is only written by one action.


could be instead be represented as

```json
  "package": "causaliq-discovery",
  "action": "learn_graph",
  "num_runs": 1,
  "algorithm": "hc",
  "score": "bic",
  "iss": 1.0,
  "penalty_weight": 1.0
```

* the provenance metadata should include details of the the software versions 
(as defined in \_\_init\_\_.py if each package, e.g. `0.8.0.dev4`) used environment and the job was run on (as provided )

## Metadata changes for specific actions

### `causaliq-analysis:evaluate_graph`

* the metrics json should have line feeds in to make it more readable (when exported)
* currently, the extraction of metrics for an empty graph (when the `learn_graph` had failed) - this is somewhat misleading as the matrics extraction itself is not failing,
though we do need to somehow record that the graph was not previously produced. I suggest
that maybe we support another metric (like `shd`, `f1`) which is `status` which is the main status from the `learn_graph` operation.

