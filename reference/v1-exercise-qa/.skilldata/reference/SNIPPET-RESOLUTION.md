# Snippet Resolution for Exercise Testing

## Problem

Red Hat Training courses use **AsciiDoc includes** to reuse content:

```asciidoc
include::{gls_snippets_dir}/step_one_lab.adoc[]
include::{common_procedures}/verify_service.adoc[]
include::{shared_content}/cleanup_hosts.adoc[]
```

When the EPUB is generated, these includes are usually expanded. However:
- Some builds may preserve include directives
- Snippet content might not be in the EPUB
- Workflow parsing needs to handle both cases

## Solution Approaches

### Approach 1: Always Use Generated EPUB ✅ RECOMMENDED

**Assumption**: The published EPUB has all includes already expanded.

**Validation**:
```bash
# Check if EPUB has expanded content
unzip -p course.epub EPUB/chapter.xhtml | grep "include::"

# If no include:: found → Content is expanded ✅
# If include:: found → Need to resolve snippets ⚠️
```

**When this works**:
- Production EPUB builds (final release)
- Most `sk build epub3` builds
- EPUB files in course repos under `.cache/generated/`

### Approach 2: Resolve Includes from Source ⚠️ COMPLEX

**When needed**: Testing from course source before EPUB is built.

**Process**:
1. Find snippet directories from `antora.yml` or build config
2. Read snippet files referenced in includes
3. Expand includes recursively
4. Build complete content tree

**Variables to resolve**:
- `{gls_snippets_dir}` → Usually `modules/ROOT/pages/_snippets/`
- `{common_procedures}` → Course-specific
- `{shared_content}` → Lesson-specific

**Example resolution**:
```python
import re
from pathlib import Path

def resolve_include(include_directive, source_dir):
    # Parse: include::{var}/file.adoc[]
    match = re.match(r'include::\{([^}]+)\}/(.+)\[\]', include_directive)
    if match:
        var_name = match.group(1)
        file_path = match.group(2)

        # Resolve variable (context-specific)
        var_value = resolve_variable(var_name, source_dir)

        # Read snippet file
        snippet_path = Path(source_dir) / var_value / file_path
        if snippet_path.exists():
            with open(snippet_path) as f:
                return f.read()

    return ""  # Include not resolved
```

### Approach 3: Hybrid - Parse EPUB, Fallback to Source

**Best of both worlds**:

1. **Try EPUB first** (fast, includes already expanded)
2. **If incomplete**, check for include directives
3. **Resolve from source** only if needed
4. **Cache resolved content** for reuse

## Detection Strategy

### Check if Includes are Expanded

```python
def has_unexpanded_includes(xhtml_content):
    """Check if EPUB has unresolved includes."""
    return 'include::' in xhtml_content

def get_procedure_step_count(xhtml_content):
    """Count actual procedure steps in EPUB."""
    # Look for ordered list items in procedure section
    procedure_match = re.search(
        r'<section[^>]*class="[^"]*procedure[^"]*">(.*?)</section>',
        xhtml_content,
        re.DOTALL
    )
    if procedure_match:
        procedure_section = procedure_match.group(1)
        steps = len(re.findall(r'<li[^>]*>', procedure_section))
        return steps
    return 0

# If step count is very low (< 3) → Might be includes
# If includes detected → Need resolution
```

### Quality Check

Before testing:
```python
def validate_workflow_completeness(workflow):
    """Ensure workflow has enough detail to execute."""
    issues = []

    if workflow['total_steps'] < 3:
        issues.append("Too few steps - might be unexpanded includes")

    steps_with_commands = sum(1 for s in workflow['steps'] if s['commands'])
    if steps_with_commands == 0:
        issues.append("No executable commands found - check for includes")

    avg_description_length = sum(len(s['description']) for s in workflow['steps']) / len(workflow['steps'])
    if avg_description_length < 20:
        issues.append("Step descriptions too short - might be unexpanded")

    return issues
```

## Snippet Directory Structure

### Typical Course Layout

```
course-repo/
├── modules/
│   └── ROOT/
│       └── pages/
│           ├── _snippets/          # Reusable snippets
│           │   ├── lab_start.adoc
│           │   ├── lab_finish.adoc
│           │   ├── verify_service.adoc
│           │   └── common_setup.adoc
│           └── chapter1/
│               └── section1.adoc   # Uses include::
└── antora.yml                       # Config with snippet paths
```

### Common Snippet Patterns

1. **Lab Start/Finish**:
   ```asciidoc
   include::{gls_snippets_dir}/lab_start_workstation.adoc[]
   ```

2. **Verification Steps**:
   ```asciidoc
   include::{verify_snippets}/check_httpd_running.adoc[]
   ```

3. **Common Procedures**:
   ```asciidoc
   include::{common_procedures}/ssh_to_servera.adoc[]
   ```

## Implementation for exercise-qa Skill

### Current Behavior
- ✅ Parse EPUB (assumes includes expanded)
- ❌ No snippet resolution
- ❌ No validation of completeness

### Recommended Enhancement

```python
def extract_workflow_safe(epub_path, exercise_id, source_dir=None):
    """
    Extract workflow with snippet resolution fallback.

    Args:
        epub_path: Path to EPUB
        exercise_id: Exercise identifier
        source_dir: Optional path to course source (for snippet resolution)

    Returns:
        Workflow with validation status
    """
    # Parse EPUB
    workflow = extract_workflow_from_epub(epub_path, exercise_id)

    # Validate completeness
    issues = validate_workflow_completeness(workflow)

    if issues and source_dir:
        print(f"⚠️  Workflow may be incomplete: {issues}")
        print(f"🔍 Attempting snippet resolution from source...")

        # Try to resolve from source
        workflow = resolve_workflow_from_source(source_dir, exercise_id)

        # Validate again
        issues = validate_workflow_completeness(workflow)

    workflow['validation'] = {
        'complete': len(issues) == 0,
        'issues': issues
    }

    return workflow
```

## Testing Strategy

### For QA Testing

1. **Primary**: Use published EPUB (includes expanded)
2. **Validation**: Check for unexpanded includes
3. **Fallback**: Resolve from source if needed
4. **Warn**: If workflow seems incomplete

### Quality Gates

Before executing workflow:
- ✅ Minimum 3 steps extracted
- ✅ At least 50% of steps have commands
- ✅ No unexpanded include directives
- ✅ Average step description > 20 characters

If any fail → Warn user and request review.

## Future Enhancement: Snippet Library

Build a **common snippet library** for frequently used procedures:

```
config/snippets/
├── lab-start/
│   ├── workstation_login.md
│   └── verify_environment.md
├── lab-finish/
│   └── cleanup_hosts.md
└── verification/
    ├── check_service_running.md
    ├── verify_file_content.md
    └── test_network_connectivity.md
```

Map common snippets to executable workflows for reuse across courses.

---

## Summary

**Current State**: EPUB parsing works if includes are expanded
**Gap**: No snippet resolution for unexpanded includes
**Risk**: Missing steps/commands if includes not expanded
**Solution**: Validate completeness, fallback to source resolution if needed
**Priority**: MEDIUM (most EPUBs have includes expanded)

**Recommendation**:
1. Add validation to detect unexpanded includes
2. Warn user if workflow seems incomplete
3. Implement source resolution as future enhancement
