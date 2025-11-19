# My Analysis Action

A custom data analysis action for the causaliq-workflow system.

## Features
- Correlation analysis
- Summary statistics  
- Basic data profiling
- CSV input/output support

## Usage
```yaml
steps:
  - name: "Analyze Data"
    uses: "my_analysis_action"
    with:
      input_file: "data.csv"
      analysis_type: "correlation"  # or "summary" or "basic"
      output_dir: "results"
```