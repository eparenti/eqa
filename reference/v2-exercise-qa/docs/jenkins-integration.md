# Jenkins Integration for exercise-qa-2

## Overview

This document describes how to integrate exercise-qa-2 with the curriculum-jenkins-library to enable automated exercise testing in Jenkins pipelines.

## Jenkinsfile Configuration

Add the following parameters to the `flamel()` call:

```groovy
flamel([
    // ... existing parameters ...
    'exercise_qa': true,
    'exercise_qa_tests': 'all'  // Options: 'all', 'static', or comma-separated test categories
])
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `exercise_qa` | boolean | false | Enable exercise QA testing |
| `exercise_qa_tests` | string | 'all' | Which tests to run: 'all', 'static', or comma-separated list |

### Test Options

- `'all'` - Run all 20 test categories (requires lab environment)
- `'static'` - Run static analysis only: TC-LINT, TC-VARS, TC-DEPS, TC-SECURITY, TC-CONTRACT, TC-SOL
- `'TC-LINT,TC-VARS'` - Run specific test categories

## Shared Library Implementation

Add the following stage to the `flamel` pipeline in `curriculum-jenkins-library`:

```groovy
// In vars/flamel.groovy or equivalent

stage('Exercise QA') {
    when {
        expression { config.exercise_qa == true }
    }
    steps {
        script {
            def testsArg = ''
            if (config.exercise_qa_tests == 'static') {
                testsArg = '--tests TC-LINT,TC-VARS,TC-DEPS,TC-SECURITY,TC-CONTRACT,TC-SOL'
            } else if (config.exercise_qa_tests != 'all') {
                testsArg = "--tests ${config.exercise_qa_tests}"
            }

            // Run exercise-qa-2 with CI mode
            sh """
                exercise-qa ${config.sku} --ci ${testsArg} -o exercise-qa-results.xml
            """
        }
    }
    post {
        always {
            // Publish JUnit results to Jenkins
            junit allowEmptyResults: true, testResults: 'exercise-qa-results.xml'

            // Archive the results
            archiveArtifacts artifacts: 'exercise-qa-results.xml', allowEmptyArchive: true
        }
    }
}
```

## Installation Requirements

The Jenkins agent must have exercise-qa-2 installed:

```bash
# Option 1: Install from pip (when published)
pip install exercise-qa-2

# Option 2: Install from source
pip install git+https://github.com/RedHatTraining/curriculum-ai-tools.git#subdirectory=claude_code/skills/exercise-qa-2

# Option 3: Add to container image
# Add to the jenkins-agent-python Dockerfile
```

## Output Format

exercise-qa-2 with `--ci` flag produces JUnit XML compatible with Jenkins:

```xml
<?xml version="1.0" ?>
<testsuites name="exercise-qa-AU0031L" tests="20" failures="2" errors="0" time="45.123">
  <testsuite name="exercise-intro-ge" tests="10" failures="1" errors="0" time="12.456">
    <testcase name="TC-LINT" classname="exercise-intro-ge.TC-LINT" time="1.234">
    </testcase>
    <testcase name="TC-VARS" classname="exercise-intro-ge.TC-VARS" time="0.567">
      <failure message="1 issue(s) found" type="AssertionError">
        [P2] Undefined variable: my_var (used in playbook.yml)
        Fix: Define variable 'my_var' in vars or defaults
      </failure>
    </testcase>
    <!-- ... more test cases ... -->
  </testsuite>
</testsuites>
```

## Jenkins UI

After integration, Jenkins will display:

1. **Test Results Trend** - Graph showing pass/fail over time
2. **Test Results Summary** - Per-exercise breakdown
3. **Failure Details** - Clickable failures with bug descriptions and fix recommendations

## Example Pipeline Run

```
[Exercise QA] Running exercise-qa AU0031L --ci -o exercise-qa-results.xml
[Exercise QA] Testing 15 exercises...
[Exercise QA] ✓ TC-LINT: 15/15 passed
[Exercise QA] ✓ TC-VARS: 14/15 passed
[Exercise QA] ✓ TC-DEPS: 15/15 passed
[Exercise QA] Report saved: exercise-qa-results.xml
[Exercise QA] Test Results: 58 passed, 2 failed
```

## Troubleshooting

### SSH Connection Issues

If tests requiring lab interaction fail with SSH errors, ensure:

1. The Jenkins agent has SSH access to the workstation
2. SSH keys are configured in Jenkins credentials
3. The lab environment is provisioned before Exercise QA runs

### Missing EPUB

If the EPUB is not found, ensure:

1. The scaffolding build stage runs before Exercise QA
2. The EPUB is in the expected location (`.cache/generated/en-US/*.epub`)

### Timeout Issues

For large courses with many exercises, increase the timeout:

```groovy
stage('Exercise QA') {
    options {
        timeout(time: 30, unit: 'MINUTES')
    }
    // ...
}
```
