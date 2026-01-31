# CLI Interface

The command-line interface provides direct workflow execution and management capabilities, with support for CI/CD pipeline integration.

## Core Interface

### causaliq_workflow.cli

::: causaliq_workflow.cli
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

---

## Command Line Usage

### Basic Workflow Execution

```bash
# Execute a workflow file
python -m causaliq_workflow experiments/my-workflow.yml

# Execute with specific output directory
python -m causaliq_workflow experiments/my-workflow.yml --output-dir /results

# Dry-run mode (parse and validate without execution)
python -m causaliq_workflow experiments/my-workflow.yml --dry-run

# Verbose output for debugging
python -m causaliq_workflow experiments/my-workflow.yml --verbose
```

### Matrix Expansion

```bash
# Show matrix expansion without execution
python -m causaliq_workflow experiments/matrix-workflow.yml --expand-matrix

# Execute specific matrix job
python -m causaliq_workflow experiments/matrix-workflow.yml --matrix-job 0

# Execute range of matrix jobs (useful for parallel execution)
python -m causaliq_workflow experiments/matrix-workflow.yml --matrix-range 0-5
```

### Workflow Validation

```bash
# Validate workflow syntax and schema
python -m causaliq_workflow validate experiments/my-workflow.yml

# Validate all workflows in directory
python -m causaliq_workflow validate experiments/

# Validate with custom schema
python -m causaliq_workflow validate experiments/my-workflow.yml --schema custom-schema.json
```

## CI/CD Integration

### GitHub Actions Integration

```yaml
name: Execute Causal Discovery Workflow

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-python@v4
      with:
        python-version: '3.9'
        
    - name: Install dependencies
      run: |
        pip install causaliq-workflow
        
    - name: Validate workflows
      run: |
        python -m causaliq_workflow validate workflows/
        
  execute:
    needs: validate
    runs-on: ubuntu-latest
    strategy:
      matrix:
        workflow: [
          "workflows/causal-discovery.yml",
          "workflows/model-validation.yml"
        ]
    steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-python@v4
      with:
        python-version: '3.9'
        
    - name: Install dependencies
      run: |
        pip install causaliq-workflow
        
    - name: Execute workflow
      run: |
        python -m causaliq_workflow ${{ matrix.workflow }} --output-dir results/
        
    - name: Upload results
      uses: actions/upload-artifact@v3
      with:
        name: workflow-results
        path: results/
```

### Jenkins Pipeline

```groovy
pipeline {
    agent any
    
    environment {
        PYTHONPATH = "${WORKSPACE}"
    }
    
    stages {
        stage('Setup') {
            steps {
                sh 'pip install causaliq-workflow'
            }
        }
        
        stage('Validate') {
            steps {
                sh 'python -m causaliq_workflow validate workflows/'
            }
        }
        
        stage('Execute Workflows') {
            parallel {
                stage('Causal Discovery') {
                    steps {
                        sh '''
                            python -m causaliq_workflow workflows/causal-discovery.yml \\
                                --output-dir results/causal-discovery/
                        '''
                    }
                }
                stage('Model Validation') {
                    steps {
                        sh '''
                            python -m causaliq_workflow workflows/model-validation.yml \\
                                --output-dir results/model-validation/
                        '''
                    }
                }
            }
        }
        
        stage('Archive Results') {
            steps {
                archiveArtifacts artifacts: 'results/**/*', fingerprint: true
            }
        }
    }
    
    post {
        always {
            cleanWs()
        }
    }
}
```

## Advanced Usage Patterns

### Parameterized Execution

```bash
# Execute workflow with environment variable substitution
export DATASET_PATH="/data/experiments/asia.csv"
export ALPHA_VALUE="0.05"
python -m causaliq_workflow experiments/parameterized-workflow.yml

# Execute with explicit parameter overrides
python -m causaliq_workflow experiments/workflow.yml \\
    --set dataset_path=/data/custom.csv \\
    --set alpha=0.01 \\
    --set output_format=graphml
```

### Batch Processing

```bash
# Execute multiple workflows sequentially
for workflow in workflows/*.yml; do
    echo "Executing $workflow..."
    python -m causaliq_workflow "$workflow" --output-dir "results/$(basename $workflow .yml)/"
done

# Parallel execution using GNU parallel
find workflows/ -name "*.yml" | parallel python -m causaliq_workflow {} --output-dir "results/{/.}/"
```

### Matrix Job Distribution

```bash
# Show total number of matrix jobs
python -m causaliq_workflow experiments/large-matrix.yml --count-jobs

# Execute jobs in parallel across multiple machines
# Machine 1: jobs 0-9
python -m causaliq_workflow experiments/large-matrix.yml --matrix-range 0-9

# Machine 2: jobs 10-19  
python -m causaliq_workflow experiments/large-matrix.yml --matrix-range 10-19

# Machine 3: jobs 20-29
python -m causaliq_workflow experiments/large-matrix.yml --matrix-range 20-29
```

## Error Handling and Debugging

### Verbose Output

```bash
# Enable debug logging
python -m causaliq_workflow experiments/workflow.yml --verbose --log-level DEBUG

# Output structured logs in JSON format
python -m causaliq_workflow experiments/workflow.yml --log-format json

# Save logs to file
python -m causaliq_workflow experiments/workflow.yml --log-file execution.log
```

### Error Recovery

```bash
# Continue execution on action failures
python -m causaliq_workflow experiments/workflow.yml --continue-on-error

# Retry failed actions
python -m causaliq_workflow experiments/workflow.yml --retry-count 3 --retry-delay 5

# Skip specific steps
python -m causaliq_workflow experiments/workflow.yml --skip-steps "step1,step3"
```

## Configuration

### Configuration File

Create `~/.causaliq-workflow.toml`:

```toml
[execution]
default_output_dir = "/experiments/results"
continue_on_error = false
retry_count = 1
retry_delay = 2

[logging]
level = "INFO"
format = "structured"
file = "~/.causaliq-workflow.log"

[registry]
packages = [
    "causaliq_workflow.actions",
    "my_custom_actions"
]

[validation]
strict_mode = true
schema_path = "~/.causaliq-workflow-schema.json"
```

### Environment Variables

```bash
# Configure via environment
export CAUSALIQ_OUTPUT_DIR="/experiments/results"
export CAUSALIQ_LOG_LEVEL="DEBUG"
export CAUSALIQ_RETRY_COUNT="3"
export CAUSALIQ_CONTINUE_ON_ERROR="true"

python -m causaliq_workflow experiments/workflow.yml
```

---

**[← Previous: Schema Validation](schema.md)** | **[Back to API Overview](overview.md)** | **[Next: Examples →](examples.md)**