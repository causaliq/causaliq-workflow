# Investigate poor performance of workflows

Some workflows seem to be awfully slow - worrinygly so, considering the
workflow caches have perhaps hundreds of entries in them but 
workflows need to scale to many orders of magnitude more. The problem seems particullrly serious with `summarise` actions
such as `merge_graphs`.

One such example can be seen on the `causaliq-research` repo which is
where I perform active research using the CausalIQ packages. It can be seen by performing the following commands:

```bash
cd ../causaliq-research
scripts/activate
cqflow run papers/pdg-merge/workflows/bnsl-pdgs-2.yml --log-level all
```

which produces the following output showing lengthy processing even in dry run mode - 6 minutes before processing actions starts, and 15 seconds for each action:

```plaintext
(py311) PS C:\dev\causaliq\causaliq-research> cqflow run papers/pdg-merge/workflows/bnsl-pdgs-2.yml --log-level all
2026-10-12 20:11:37 [causaliq-workflow] LOADING workflow from: papers\pdg-merge\workflows\bnsl-pdgs-2.yml
2026-10-12 20:11:44 [causaliq-workflow] VALIDATING workflow syntax and parameters...
2026-10-12 20:14:46 [causaliq-workflow] VALIDATED workflow successfully
2026-10-12 20:14:46 [causaliq-workflow] EXECUTING workflow in dry-run mode...
2026-10-12 20:17:46 [merge_graphs] WOULD SKIP   Merge FGES graphs with different seeds [network=seismic, series=TETRAD/FGES_BASE4, sample_size=1K, pdg_seed=0, llm_model=None, prompt_detail=None, llm_temperature=None, llm_seed=None]
2026-10-12 20:18:01 [merge_graphs] WOULD SKIP   Merge FGES graphs with different seeds [network=seismic, series=TETRAD/FGES_BASE4, sample_size=1K, pdg_seed=1, llm_model=None, prompt_detail=None, llm_temperature=None, llm_seed=None]
....
2026-10-12 20:20:25 [merge_graphs] WOULD SKIP   Merge FGES graphs with different seeds [network=seismic, series=BNLEARN/PC_BASE4, sample_size=10K, pdg_seed=1, llm_model=None, prompt_detail=None, llm_temperature=None, llm_seed=None]
2026-10-12 20:20:25 [causaliq-workflow] COMPLETED 12 steps: 12 would skip
```

Can you investigate this by inspecting the code (probably in causaliq-workflow and causaliq-analysis), and if necessary develop a plan for temporary code instrumentation to
get any necessary diagnostics (you will likely have to change the example problem so that things run in a reasonable time).

Please do not **permanently** change any code in any repo.
