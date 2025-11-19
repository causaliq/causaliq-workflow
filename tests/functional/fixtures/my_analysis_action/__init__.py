"""
My Analysis Action Package

A simple custom action following the causaliq-workflow convention.
This demonstrates creating your own action package with minimal dependencies.

Usage in workflow:
```yaml
steps:
  - name: "Simple Analysis Step"
    uses: "my_analysis_action"
    with:
      input_file: "/data/input.csv"
      analysis_type: "count"
      output_dir: "/results"
```
"""

import csv
from pathlib import Path
from typing import Any, Dict

from causaliq_workflow.action import Action


class CausalIQAction(Action):
    """Simple data analysis action with no external dependencies."""

    name = "my-analysis-action"
    version = "1.0.0"
    description = (
        "Performs simple analysis on CSV files using built-in Python libraries"
    )

    def run(self, inputs: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Execute the simple analysis action."""

        # Get input parameters
        input_file = inputs.get("input_file", "data.csv")
        analysis_type = inputs.get("analysis_type", "count")
        output_dir = Path(inputs.get("output_dir", "."))
        message = inputs.get("message", "Hello from my analysis action!")

        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        mode = kwargs.get("mode", "dry-run")

        if mode == "dry-run":
            # In dry-run mode, just validate inputs and show what would happen
            result = {
                "status": "dry-run-success",
                "message": (
                    f"Would analyze {input_file} with {analysis_type} analysis"
                ),
                "would_create": str(
                    output_dir / f"{analysis_type}_results.txt"
                ),
                "input_validated": (
                    Path(input_file).exists() if input_file else False
                ),
                "user_message": message,
            }
        else:
            # In run mode, perform actual analysis
            try:
                # Simple file reading and analysis
                with open(input_file, "r", newline="") as csvfile:
                    reader = csv.reader(csvfile)
                    rows = list(reader)

                # Perform simple analysis based on type
                if analysis_type == "count":
                    # Count rows and columns
                    row_count = len(rows)
                    col_count = len(rows[0]) if rows else 0
                    header = rows[0] if rows else []

                    output_file = output_dir / "count_results.txt"
                    with open(output_file, "w") as f:
                        f.write("Analysis Results\n")
                        f.write("================\n")
                        f.write(
                            f"Total rows (including header): {row_count}\n"
                        )
                        f.write(f"Total columns: {col_count}\n")
                        f.write(f"Header columns: {', '.join(header)}\n")
                        f.write(f"User message: {message}\n")

                    analysis_result = (
                        f"Row and column counts saved to {output_file}"
                    )

                elif analysis_type == "preview":
                    # Show first few rows
                    output_file = output_dir / "preview_results.txt"
                    with open(output_file, "w") as f:
                        f.write("Data Preview\n")
                        f.write("============\n")
                        f.write(f"User message: {message}\n\n")
                        for i, row in enumerate(rows[:5]):  # First 5 rows
                            f.write(f"Row {i}: {', '.join(row)}\n")

                    analysis_result = f"Data preview saved to {output_file}"

                else:
                    # Basic info
                    output_file = output_dir / "basic_results.txt"
                    with open(output_file, "w") as f:
                        f.write("Basic Analysis\n")
                        f.write("==============\n")
                        f.write(f"Input file: {input_file}\n")
                        f.write(f"Analysis type: {analysis_type}\n")
                        f.write(f"User message: {message}\n")
                        f.write(f"File exists: {Path(input_file).exists()}\n")

                    analysis_result = f"Basic info saved to {output_file}"

                result = {
                    "status": "success",
                    "message": f"Successfully analyzed {input_file}",
                    "analysis_type": analysis_type,
                    "input_rows": len(rows),
                    "input_columns": len(rows[0]) if rows else 0,
                    "analysis_result": analysis_result,
                    "output_file": str(output_file),
                    "user_message": message,
                }

            except Exception as e:
                result = {
                    "status": "error",
                    "message": f"Analysis failed: {str(e)}",
                    "analysis_type": analysis_type,
                    "input_file": input_file,
                }

        return result
