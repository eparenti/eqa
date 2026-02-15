# Course Structure Patterns

## Overview

Red Hat Training courses use **three different repository structure patterns**. Understanding these patterns is critical for effective QA testing.

---

## Pattern 1: Single-Repo, Lesson-Based (<ANSIBLE-COURSE>)

### Characteristics

- ✅ **One repository** contains all lessons
- ✅ **Lesson codes** used (not chapter numbers)
- ✅ **Materials path**: `au294/materials/labs/{lesson-name}/`
- ✅ **Grading scripts**: `{lesson-name}.py`
- ✅ **EPUB chapters**: Map to lesson names

### Example: <ANSIBLE-COURSE> (Red Hat Ansible Automation)

```
<ANSIBLE-COURSE>/
├── outline.yml
├── <ANSIBLE-COURSE>-RHAAP2.5-en-1.epub
└── classroom/grading/src/au294/
    ├── materials/labs/
    │   ├── <exercise-name>/      # Lesson 1
    │   ├── develop-review/           # Lesson 2
    │   ├── <exercise-name>/             # Lesson 3
    │   └── <exercise-name>/             # Lesson 4
    ├── <exercise-name>.py
    ├── develop-review.py
    ├── <exercise-name>.py
    └── <exercise-name>.py
```

### Outline.yml Format

```yaml
dco:
  chapters:
    - keyword: develop
      title: "Developing Playbooks"
      # NO repository field - all in same repo
    - keyword: roles
      title: "Reusing Content with Roles"
```

### Exercise Discovery

```bash
# List all lessons
ls <ANSIBLE-COURSE>/classroom/grading/src/au294/materials/labs/

# Find grading scripts
ls <ANSIBLE-COURSE>/classroom/grading/src/au294/*.py

# Test a lesson
/exercise-qa au294 <exercise-name>
```

---

## Pattern 2: Multi-Repo, Lesson-Based (<RHEL-COURSE>)

### Characteristics

- ✅ **Multiple repositories** (one per chapter/lesson)
- ✅ **Lesson codes** used (AU0004L, AU0005L, etc.)
- ✅ **Materials path**: `au0004l/materials/labs/{exercise-name}/`
- ✅ **Grading scripts**: `{chapter_keyword}-{topic}.py`
- ✅ **EPUB chapters**: Match chapter keyword
- ✅ **Outline.yml**: Maps chapters to lesson repos

### Example: <RHEL-COURSE> (Services Management)

```
<RHEL-COURSE>/  # Main course repo
├── outline.yml  # Maps chapters to lesson repos
└── <RHEL-COURSE>-RHEL9.4-en-1.epub

AU0004L/  # Chapter 1 lesson repo
└── classroom/grading/src/au0004l/
    ├── materials/labs/
    │   ├── servicemgmt-automation/
    │   └── <chapter>-review/
    ├── servicemgmt-netservice.py
    ├── servicemgmt-netreview.py
    ├── servicemgmt-automation.py
    └── <chapter>-review.py

AU0005L/  # Chapter 2 lesson repo
└── classroom/grading/src/au0005l/
    ├── materials/labs/
    │   ├── netlink-automation/
    │   └── netlink-review/
    ├── netlink-bonding.py
    └── netlink-review.py
```

### Outline.yml Format

```yaml
dco:
  chapters:
    - keyword: servicemgmt
      repository: git@github.com:RedHatTraining/AU0004L.git  # <-- Separate repo!
      revision: "main"
      remoteChapter: servicemgmt

    - keyword: netlink
      repository: git@github.com:RedHatTraining/AU0005L.git  # <-- Separate repo!
      revision: "main"
      remoteChapter: netlink
```

### Exercise Discovery

```bash
# Clone lesson repos first
git clone git@github.com:RedHatTraining/AU0004L.git
git clone git@github.com:RedHatTraining/AU0005L.git

# List exercises in chapter 1
ls AU0004L/classroom/grading/src/au0004l/*.py

# Test from specific lesson repo
/exercise-qa au0004l <chapter>-review
```

---

## Pattern 3: Single-Repo, Chapter-Based (<ANSIBLE-COURSE>)

### Characteristics

- ✅ **One repository** with chapter-based organization
- ✅ **Chapter keywords** used (not lesson codes)
- ✅ **Materials path**: `content/{chapter-keyword}/`
- ✅ **Grading scripts**: `{chapter}_{topic}.py`
- ✅ **EPUB chapters**: Match chapter keyword
- ✅ **No separate lesson repos**

### Example: <ANSIBLE-COURSE> (Managing Enterprise Automation)

```
<ANSIBLE-COURSE>/
├── outline.yml
├── <ANSIBLE-COURSE>-RHAAP2.5-en-1.epub
├── content/
│   ├── install/      # Chapter 1
│   ├── code/         # Chapter 2
│   ├── host/         # Chapter 3
│   └── inventory/    # Chapter 4
└── classroom/grading/src/au467/
    ├── install_config.py       # Chapter 1, topic config
    ├── code_api.py             # Chapter 2, topic api
    ├── code_collection.py      # Chapter 2, topic collection
    ├── code_review.py          # Chapter 2, lab
    ├── host_credential.py      # Chapter 3, topic credential
    └── host_inventory.py       # Chapter 3, topic inventory
```

### Outline.yml Format

```yaml
course:  # <-- Note: "course:" not "dco:"
  chapters:
    - keyword: install       # Chapter 1
      title: "Installing Red Hat Ansible Automation Platform"
      topics:
        - keyword: config    # Topic in chapter
          sections:
            - type: ge       # Guided Exercise

    - keyword: code         # Chapter 2
      title: "Managing Automation Code"
      topics:
        - keyword: api
          sections:
            - type: ge
        - keyword: review
          sections:
            - type: lab      # Lab
```

### Exercise Discovery

```bash
# List all grading scripts
ls <ANSIBLE-COURSE>/classroom/grading/src/au467/*.py

# Pattern: {chapter}_{topic}.py
# Examples:
#   install_config.py    → Chapter: install, Topic: config
#   code_api.py          → Chapter: code, Topic: api
#   host_review.py       → Chapter: host, Lab: review

# Test an exercise
/exercise-qa au467 code_api
```

---

## Pattern Comparison Table

| Aspect | Pattern 1: <ANSIBLE-COURSE> | Pattern 2: <RHEL-COURSE> | Pattern 3: <ANSIBLE-COURSE> |
|--------|------------------|------------------|------------------|
| **Repo Structure** | Single repo | Multiple repos | Single repo |
| **Organization** | Lesson-based | Lesson-based | Chapter-based |
| **Lesson Codes** | au294 | au0004l, au0005l, ... | au467 |
| **Outline Format** | `dco:` | `dco:` | `course:` |
| **Repo Field** | No | Yes (`repository:`) | No |
| **Materials Path** | `au294/materials/labs/` | `au0004l/materials/labs/` | `content/{chapter}/` |
| **Exercise Naming** | `{lesson-name}` | `{keyword}-{topic}` | `{chapter}_{topic}` |
| **Grading Scripts** | `<exercise-name>.py` | `<chapter>-review.py` | `install_config.py` |
| **EPUB Mapping** | Chapter → Lesson | Chapter → Keyword | Chapter → Keyword |
| **Cloning** | Once | Multiple times | Once |

---

## Detection Algorithm

### Step 1: Read outline.yml

```python
with open('outline.yml') as f:
    outline = yaml.safe_load(f)

# Check root key
if 'dco' in outline:
    # Pattern 1 or 2
    chapters = outline['dco']['chapters']
elif 'course' in outline:
    # Pattern 3
    chapters = outline['course']['chapters']
```

### Step 2: Check for Repository Field

```python
for chapter in chapters:
    if 'repository' in chapter:
        # Pattern 2: Multi-Repo, Lesson-Based
        return "multi_repo_lesson"
    else:
        # Pattern 1 or 3: Single-Repo
        break
```

### Step 3: Check Organization Type

```python
# For single-repo, check materials directory structure
if os.path.exists('classroom/grading/src/materials/'):
    # Pattern 1: Lesson-Based
    return "single_repo_lesson"
elif os.path.exists('content/'):
    # Pattern 3: Chapter-Based
    return "single_repo_chapter"
```

---

## QA Testing Strategy by Pattern

### Pattern 1: Single-Repo, Lesson-Based

```bash
# Simple and straightforward
cd <ANSIBLE-COURSE>/
/exercise-qa au294 <exercise-name>
/exercise-qa au294 develop-review
```

**Advantages:**
- ✅ All exercises in one place
- ✅ Simple directory structure
- ✅ Easy to discover exercises

**Challenges:**
- ⚠️ Large repo with many exercises
- ⚠️ Lesson naming may not match chapter numbering

---

### Pattern 2: Multi-Repo, Lesson-Based

```bash
# Must clone lesson repos first
git clone git@github.com:RedHatTraining/AU0004L.git
git clone git@github.com:RedHatTraining/AU0005L.git

# Test from each lesson repo
cd AU0004L/
/exercise-qa au0004l <chapter>-review

cd AU0005L/
/exercise-qa au0005l netlink-review
```

**Advantages:**
- ✅ Modular, independently versioned lessons
- ✅ Smaller, focused repositories
- ✅ Reusable across courses

**Challenges:**
- ⚠️ Must clone multiple repos
- ⚠️ Complex chapter-to-lesson mapping
- ⚠️ Different paths for each lesson

---

### Pattern 3: Single-Repo, Chapter-Based

```bash
# All in one repo, but organized by chapters
cd <ANSIBLE-COURSE>/
/exercise-qa au467 install_config
/exercise-qa au467 code_api
/exercise-qa au467 code_review
```

**Advantages:**
- ✅ All exercises in one repo
- ✅ Clear chapter organization
- ✅ Direct chapter-to-exercise mapping

**Challenges:**
- ⚠️ Exercise naming uses underscores, not hyphens
- ⚠️ Materials may be in content/ not materials/labs/
- ⚠️ Different outline.yml format (`course:` vs `dco:`)

---

## Creating Mapping Files

### Pattern 1: <ANSIBLE-COURSE>

```json
{
  "course_code": "<ANSIBLE-COURSE>",
  "mapping_type": "single_repo_lesson",
  "lesson_code": "au294",
  "mapping": {
    "1": {
      "chapter_title": "Developing Playbooks",
      "keyword": "develop",
      "lesson_name": "<exercise-name>",
      "exercises": ["<exercise-name>", "develop-review"]
    }
  }
}
```

### Pattern 2: <RHEL-COURSE>

```json
{
  "course_code": "<RHEL-COURSE>",
  "mapping_type": "multi_repo_lesson",
  "mapping": {
    "1": {
      "chapter_title": "Managing Network Services",
      "keyword": "servicemgmt",
      "lesson_code": "au0004l",
      "lesson_repo": "git@github.com:RedHatTraining/AU0004L.git",
      "exercises": ["servicemgmt-netservice", "<chapter>-review"]
    }
  }
}
```

### Pattern 3: <ANSIBLE-COURSE>

```json
{
  "course_code": "<ANSIBLE-COURSE>",
  "mapping_type": "single_repo_chapter",
  "lesson_code": "au467",
  "mapping": {
    "1": {
      "chapter_title": "Installing Ansible Automation Platform",
      "keyword": "install",
      "topics": [
        {"topic": "config", "exercise": "install_config", "type": "ge"}
      ]
    },
    "2": {
      "chapter_title": "Managing Automation Code",
      "keyword": "code",
      "topics": [
        {"topic": "api", "exercise": "code_api", "type": "ge"},
        {"topic": "collection", "exercise": "code_collection", "type": "ge"},
        {"topic": "review", "exercise": "code_review", "type": "lab"}
      ]
    }
  }
}
```

---

## Exercise Naming Patterns

### Pattern 1: Lesson-Based (<ANSIBLE-COURSE>)

**Format:** `{descriptive-name}`

- `<exercise-name>` (Lesson about developing a single playbook)
- `develop-review` (Review lab for develop chapter)
- `<exercise-name>` (Lesson about creating roles)
- `<exercise-name>` (Review lab for roles chapter)

**Pattern:** Descriptive names, often `{keyword}-{action}`

---

### Pattern 2: Multi-Repo Lesson (<RHEL-COURSE>)

**Format:** `{chapter_keyword}-{topic}`

- `servicemgmt-netservice` (Service management, network service topic)
- `<chapter>-review` (Service management, review lab)
- `netlink-bonding` (Network link, bonding topic)
- `netlink-review` (Network link, review lab)

**Pattern:** Prefix matches chapter keyword

---

### Pattern 3: Chapter-Based (<ANSIBLE-COURSE>)

**Format:** `{chapter}_{topic}`

- `install_config` (Install chapter, config topic)
- `code_api` (Code chapter, API topic)
- `host_inventory` (Host chapter, inventory topic)
- `mesh_manage` (Mesh chapter, manage topic)

**Pattern:** Underscore separator (not hyphen!)

---

## EPUB Chapter Mapping

### All Patterns: EPUB Structure

```bash
# Extract EPUB
unzip -l course.epub | grep .xhtml

# Pattern 1: <ANSIBLE-COURSE>
#   EPUB/develop.xhtml → Chapter "develop"
#   EPUB/roles.xhtml   → Chapter "roles"

# Pattern 2: <RHEL-COURSE>
#   EPUB/servicemgmt.xhtml → Chapter "servicemgmt" → AU0004L
#   EPUB/netlink.xhtml     → Chapter "netlink"     → AU0005L

# Pattern 3: <ANSIBLE-COURSE>
#   EPUB/install.xhtml     → Chapter "install"
#   EPUB/code.xhtml        → Chapter "code"
```

**Observation:** EPUB chapter filenames match the `keyword` field in outline.yml across all patterns.

---

## Summary

### Key Takeaways

1. **Three distinct patterns** exist for course organization
2. **outline.yml format** indicates the pattern (`dco:` vs `course:`, `repository:` field)
3. **Materials location** varies by pattern
4. **Exercise naming conventions** differ significantly
5. **EPUB chapter mapping** is consistent (keyword-based)

### When to Use Each Pattern

- **Pattern 1** (Single-Repo, Lesson): Small to medium courses, tightly coupled content
- **Pattern 2** (Multi-Repo, Lesson): Large courses, reusable lessons across courses
- **Pattern 3** (Single-Repo, Chapter): Focused courses, chapter-centric organization

### QA Implications

- Must **detect pattern** before testing
- Must **adapt paths** based on pattern
- Must **handle naming conventions** correctly
- Must **support all three patterns** in QA skill

The QA skill now intelligently detects and supports all three course structure patterns.
