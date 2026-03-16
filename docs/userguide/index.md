# CausalIQ Workflow User Guide

## Overview

CausalIQ Workflow provides a declarative YAML-based system for defining and
executing causal discovery and analysis pipelines. It is part of the
[CausalIQ ecosystem](https://causaliq.org/) for intelligent causal discovery.

## Key Features

| Feature | Description |
|---------|-------------|
| **Declarative YAML syntax** | Define workflows in familiar GitHub Actions-style YAML |
| **Matrix expansion** | Run steps across multiple parameter combinations |
| **Template variables** | Reference workflow and matrix values in step parameters |
| **Workflow caching** | SQLite-based result storage with conservative execution |
| **Action patterns** | Create, update, and aggregate patterns for different use cases |
| **CLI and programmatic access** | Execute workflows from command line or Python code |

## Documentation Structure

This user guide covers how to use CausalIQ Workflow effectively:

| Section | Content |
|---------|---------|
| [Core Concepts](core_concepts.md) | Workflows, steps, actions, and matrix expansion |
| [Action Patterns](action_patterns.md) | Create, update, and aggregate step patterns |
| [Workflow Caching](caching.md) | Result storage and conservative execution |
| [Common Parameters](common_parameters.md) | Parameters shared across all actions |
| [CLI Usage](cli.md) | Command-line interface and execution modes |

For Python API details, see the [API Reference](../api/overview.md).

For implementation design notes, see the
[Architecture Documentation](../architecture/overview.md).

## Quick Start

A minimal workflow that runs a single action:

```yaml
# my_workflow.yml
steps:
  - name: "Run Analysis"
    uses: "causaliq-analysis"
    with:
      action: "merge_graphs"
      input: "results/graphs.db"
      output: "results/merged.db"
```

Execute with:

```bash
cqflow run my_workflow.yml --mode=run
```

## Where to Find Action Documentation

Each CausalIQ package provides its own action documentation:

| Package | Example Actions | Documentation |
|---------|---------|---------------|
| causaliq-analysis | `migrate_trace`, `merge_graphs`, `evaluate_graph`, `summarise` | [Analysis User Guide](https://analysis.causaliq.org/userguide/) |
| causaliq-discovery | `learn_structure` *(planned)* | — |
| causaliq-knowledge | `generate_graph` | — |

This workflow documentation covers **common concepts** that apply across all
actions. Individual action parameters and behaviour are documented in their
respective packages.
