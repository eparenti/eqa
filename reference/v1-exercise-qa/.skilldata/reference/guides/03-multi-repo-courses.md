# Multi-Repo Course Structure

## Overview

Some Red Hat courses (like <RHEL-COURSE>) use a **multi-repository structure** where each chapter is maintained in a separate lesson repository, unlike <ANSIBLE-COURSE> which is a single repository.

---

## Course Structure Comparison

### Single-Repo Course (<ANSIBLE-COURSE>)

```
<ANSIBLE-COURSE>/
└── classroom/grading/src/au294/
    ├── materials/labs/
    │   ├── <exercise-name>/
    │   ├── develop-review/
    │   ├── <exercise-name>/
    │   └── <exercise-name>/
    └── *.py  # All grading scripts in one repo
```

**Characteristics:**
- One repository contains all lessons
- All exercises in `materials/labs/`
- Single lesson code (e.g., au294)

---

### Multi-Repo Course (<RHEL-COURSE>, <RHEL-COURSE>, etc.)

```
<RHEL-COURSE>/  # Main course repo
├── outline.yml  # Maps chapters to lesson repos
├── content/
└── <RHEL-COURSE>.epub

AU0004L/  # Chapter 1 lesson repo
├── classroom/grading/src/au0004l/
│   ├── materials/labs/
│   │   ├── servicemgmt-automation/
│   │   └── <chapter>-review/
│   └── servicemgmt-*.py

AU0005L/  # Chapter 2 lesson repo
├── classroom/grading/src/au0005l/
│   ├── materials/labs/
│   │   ├── netlink-automation/
│   │   └── netlink-review/
│   └── netlink-*.py
```

**Characteristics:**
- Main course repo contains `outline.yml` and EPUB
- Each chapter = separate AU00XXL repository
- Each lesson repo has its own materials directory
- Multiple lesson codes (au0004l, au0005l, etc.)

---

## Discovering Multi-Repo Structure

### 1. Read outline.yml

The `outline.yml` file in the main course repo defines the chapter-to-lesson mapping:

```yaml
dco:
  chapters:
    # Chapter 01
    - keyword: servicemgmt
      repository: git@github.com:RedHatTraining/AU0004L.git
      revision: "main"
      remoteChapter: servicemgmt

    # Chapter 02
    - keyword: netlink
      repository: git@github.com:RedHatTraining/AU0005L.git
      revision: "main"
      remoteChapter: netlink
```

**Key Fields:**
- `keyword`: Chapter identifier (matches EPUB chapter filename)
- `repository`: GitHub URL for lesson repo
- `remoteChapter`: Chapter name in lesson repo

---

### 2. Extract EPUB Chapter Structure

EPUB chapters match the `keyword` field:

```bash
# List EPUB chapters
unzip -l <RHEL-COURSE>.epub | grep .xhtml

# Output shows:
#   servicemgmt.xhtml  (Chapter 1)
#   netlink.xhtml      (Chapter 2)
#   dns.xhtml          (Chapter 3)
#   etc.
```

---

### 3. Clone Lesson Repositories

```bash
# Clone lesson repos for chapters 1-2
cd /path/to/repos/active/
git clone git@github.com:RedHatTraining/AU0004L.git
git clone git@github.com:RedHatTraining/AU0005L.git
```

---

## Exercise Naming Patterns

### Pattern: {keyword}-{topic}[-suffix]

**Examples from <RHEL-COURSE>:**

| Exercise ID | Type | Keyword | Topic | Suffix |
|-------------|------|---------|-------|--------|
| `servicemgmt-netservice` | GE | servicemgmt | netservice | (none) |
| `servicemgmt-automation` | GE | servicemgmt | automation | (none) |
| `<chapter>-review` | Lab | servicemgmt | review | (none) |
| `netlink-bonding` | GE | netlink | bonding | (none) |
| `netlink-review` | Lab | netlink | review | (none) |

**Observations:**
- Prefix matches chapter keyword
- No `-ge` or `-lab` suffix in grading script names
- Exercise type determined by `grade()` method presence
- Labs typically end with `-review`

---

## Materials Directory Pattern

### Not All Exercises Have Materials

**Pattern Discovered:**

```
classroom/grading/src/au0004l/
├── materials/labs/
│   ├── servicemgmt-automation/   ✅ Has materials
│   └── <chapter>-review/       ✅ Has materials
│
├── servicemgmt-netservice.py     ❌ No materials (simple GE)
├── servicemgmt-netreview.py      ❌ No materials (simple GE)
├── servicemgmt-automation.py     ✅ Has materials
└── <chapter>-review.py         ✅ Has materials (Lab)
```

**Why Some Don't Have Materials:**
- Simple guided exercises with step-by-step instructions
- Students follow along without needing solution files
- Only `start()` and `finish()` methods in grading script
- No complex automation or solution playbooks

**Exercises WITH Materials:**
- More complex guided exercises with solution files
- Labs with automated grading
- Include solution playbooks, configs, etc.

---

## Testing Multi-Repo Courses

### Option 1: Test by Chapter

```bash
# Create chapter mapping file
cp .claude/skills/qa/assets/templates/<RHEL-COURSE>-CHAPTER-LESSON-MAPPING.json ./rh358-mapping.json

# Test chapter 1
/qa chapter 1 rh358-mapping.json

# Test chapter 2
/qa chapter 2 rh358-mapping.json
```

---

### Option 2: Test by Lesson Code

```bash
# Test specific lesson
/qa au0004l <chapter>-review

# Test all exercises in a lesson
/qa au0004l
```

---

### Option 3: Test Specific Exercise

```bash
# Test a specific guided exercise
/qa au0004l servicemgmt-automation

# Test a specific lab
/qa au0005l netlink-review
```

---

## QA Workflow for Multi-Repo Courses

### Step 1: Discover Course Structure

```bash
# Read outline.yml
cat /path/to/<RHEL-COURSE>/outline.yml

# Extract chapter mapping
# Create mapping JSON file
```

---

### Step 2: Clone Required Lesson Repos

```bash
cd ~/git-repos/active/

# Clone repos for chapters you want to test
git clone git@github.com:RedHatTraining/AU0004L.git  # Chapter 1
git clone git@github.com:RedHatTraining/AU0005L.git  # Chapter 2
```

---

### Step 3: Identify Exercises

```bash
# Method 1: From EPUB
unzip -p <RHEL-COURSE>.epub EPUB/servicemgmt.xhtml | grep 'id=".*-ge"'
unzip -p <RHEL-COURSE>.epub EPUB/servicemgmt.xhtml | grep 'id=".*-lab"'

# Method 2: From grading scripts
ls AU0004L/classroom/grading/src/au0004l/*.py

# Method 3: From materials directory
ls AU0004L/classroom/grading/src/au0004l/materials/labs/
```

---

### Step 4: Check Exercise Type

```bash
# Check if exercise has grade() method (Lab vs GE)
grep "def grade" AU0004L/classroom/grading/src/au0004l/<chapter>-review.py

# Output indicates it's a Lab ✓

grep "def grade" AU0004L/classroom/grading/src/au0004l/servicemgmt-automation.py

# No output = Guided Exercise (no automated grading)
```

---

### Step 5: Run QA Testing

```bash
# Test with materials
/qa au0004l servicemgmt-automation

# Test without materials (will test grading script only)
/qa au0004l servicemgmt-netservice

# Test lab with grading
/qa au0004l <chapter>-review
```

---

## Creating Mapping Files

### Template Structure

```json
{
  "course_code": "<RHEL-COURSE>",
  "course_title": "Red Hat Services Management and Automation",
  "mapping_type": "multi_repo",
  "mapping": {
    "1": {
      "chapter_number": 1,
      "keyword": "servicemgmt",
      "lesson_code": "au0004l",
      "lesson_repo": "git@github.com:RedHatTraining/AU0004L.git",
      "exercises": [
        {
          "id": "<chapter>-review",
          "type": "lab",
          "has_materials": true,
          "has_grading": true
        }
      ]
    }
  }
}
```

---

### Auto-Generation Script

```bash
# Extract from outline.yml and EPUB
python3 .claude/skills/qa/scripts/generate_course_mapping.py \
  --course <RHEL-COURSE> \
  --outline /path/to/<RHEL-COURSE>/outline.yml \
  --epub /path/to/<RHEL-COURSE>.epub \
  --chapters 1,2 \
  --output rh358-mapping.json
```

---

## Key Differences: Multi-Repo vs Single-Repo

| Aspect | Single-Repo (<ANSIBLE-COURSE>) | Multi-Repo (<RHEL-COURSE>) |
|--------|-------------------|-------------------|
| **Structure** | One repo, all lessons | Multiple repos, one per chapter |
| **Lesson Codes** | Single (au294) | Multiple (au0004l, au0005l, ...) |
| **Discovery** | Simple directory listing | Parse outline.yml + clone repos |
| **Testing** | Test from one location | Test across multiple repos |
| **Materials Path** | `au294/materials/labs/` | `au0004l/materials/labs/` (per repo) |
| **Mapping File** | Simple chapter→exercise | Complex chapter→repo→exercise |
| **Cloning** | Clone once | Clone multiple lesson repos |
| **Exercise Naming** | Varied patterns | `{keyword}-{topic}` pattern |

---

## Common Multi-Repo Courses

- **<RHEL-COURSE>**: Red Hat System Administration I
- **<RHEL-COURSE>**: Red Hat System Administration II
- **RH294**: Red Hat System Administration III
- **<RHEL-COURSE>**: Red Hat Services Management and Automation
- **<AAP-COURSE>**: Developing Automation with Ansible Automation Platform

---

## Benefits of Multi-Repo Structure

1. **Modularity**: Each lesson is independently maintained
2. **Reusability**: Lessons can be shared across courses
3. **Version Control**: Independent versioning per lesson
4. **Team Collaboration**: Different teams can own different lessons
5. **Flexibility**: Mix and match lessons for custom courses

---

## Challenges for QA

1. **Discovery**: Must parse outline.yml to find lesson repos
2. **Cloning**: Need to clone multiple repositories
3. **Complexity**: More moving parts to coordinate
4. **Path Management**: Different paths for each lesson repo
5. **Version Sync**: Ensure lesson repo versions match course expectations

---

## Best Practices

### For QA Testing

1. **Create comprehensive mapping files** for each course
2. **Clone all required lesson repos** before testing
3. **Use consistent directory structure** (~/git-repos/active/)
4. **Document exercise types** (GE vs Lab, has_materials, etc.)
5. **Test exercises in chapter order** for logical flow

### For Mapping Files

1. **Include all metadata** (lesson_code, repo URLs, exercise lists)
2. **Document exercise characteristics** (type, materials, grading)
3. **Use clear naming conventions** (<RHEL-COURSE>-CHAPTER-LESSON-MAPPING.json)
4. **Version control mapping files** alongside QA documentation
5. **Update mappings when course structure changes**

---

## Automation Opportunities

### Future Enhancements

1. **Auto-detect multi-repo structure** from outline.yml
2. **Auto-clone required lesson repos** based on chapter selection
3. **Auto-generate mapping files** from outline.yml + EPUB analysis
4. **Smart exercise discovery** across multiple repos
5. **Parallel testing** of multiple lessons/chapters

---

## Summary

Multi-repo course structure requires:
- ✅ Understanding outline.yml format
- ✅ Mapping chapters to lesson repositories
- ✅ Cloning multiple lesson repos
- ✅ Identifying exercises across repos
- ✅ Creating comprehensive mapping files
- ✅ Adapting QA workflows for distributed structure

The QA skill now supports both single-repo and multi-repo course structures through flexible mapping files and intelligent exercise discovery.
