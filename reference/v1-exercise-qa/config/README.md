# Configuration Files

This directory contains **course mappings** (auto-generated) and **editable reference files** (you can customize).

---

## 📁 Editable Reference Files

These files can be extended as you discover new patterns, technologies, and problems:

### COMMON-PROBLEMS-AND-SOLUTIONS.md
**Add new problems you encounter during testing:**
- Common student mistakes
- Environment issues
- Tool-specific errors
- Solutions and workarounds

### COURSE-TECHNOLOGIES.md
**Add new course types and technologies:**
- New course prefixes (DO*, RH*, AU*, etc.)
- Technology-specific testing approaches
- Tools and commands for each technology

### GRADING-SCRIPTS-ALL-COURSES.md
**Add grading patterns from new courses:**
- Grading script structures
- Common grading check patterns
- Course-specific grading approaches

### TECHNOLOGY-GUIDE.md
**Add new technology testing guides:**
- Technology detection methods
- Testing workflows per technology
- Tool-specific validation steps


---

## 📁 courses/

**Purpose:** Course mapping files that tell the QA skill how to find and test exercises.

**How they are created:** The QA skill automatically generates these files by reading the course's `outline.yml`.

**Files:**
- `<RHEL-COURSE>-mapping.json` - Auto-generated: Multi-repo course
- `<ANSIBLE-COURSE>-mapping.json` - Auto-generated: Single-repo, chapter-based course
- `<ANSIBLE-COURSE>-mapping.json` - Auto-generated: Single-repo, lesson-based course

---

## How Auto-Mapping Works

### Step 1: You Point the QA Skill to a Course

```bash
# Test a course by providing path to outline.yml or course repo
/exercise-qa /home/developer/git-repos/active/<ANSIBLE-COURSE>
```

### Step 2: QA Skill Analyzes Course Structure

The skill reads `outline.yml` and automatically:

1. **Detects the course pattern:**
   - Pattern 1: Single-Repo, Lesson-Based (e.g., <ANSIBLE-COURSE>)
   - Pattern 2: Multi-Repo, Lesson-Based (e.g., <RHEL-COURSE>)
   - Pattern 3: Single-Repo, Chapter-Based (e.g., <ANSIBLE-COURSE>)

2. **Extracts course metadata:**
   - Course code, title, chapters
   - Exercise names and types
   - Repository locations

3. **Builds the mapping structure:**
   ```json
   {
     "course_code": "<ANSIBLE-COURSE>",
     "course_title": "Developing Advanced Automation with Ansible",
     "mapping_type": "single_repo_lesson",
     "chapters": {
       "1": {"lesson_code": "<lesson-code>", "exercises": [...]},
       "2": {"lesson_code": "<lesson-code>", "exercises": [...]}
     }
   }
   ```

### Step 3: QA Skill Shows You the Mapping

```
🔍 AUTO-DETECTING COURSE STRUCTURE...

Course: <ANSIBLE-COURSE> - Developing Advanced Automation with Ansible
Pattern: Single-Repo, Lesson-Based
Chapters: 9
Exercises: 18

Mapping:
  Chapter 1 → <lesson-code> (2 exercises)
  Chapter 2 → <lesson-code> (3 exercises)
  Chapter 3 → au0021l (2 exercises)
  ...

Does this look correct? (yes/no)
```

### Step 4: You Confirm

```
User: yes
```

### Step 5: QA Skill Saves the Mapping

```
✅ Saved mapping to config/courses/<ANSIBLE-COURSE>-mapping.json

You can now test by chapter:
  /exercise-qa chapter 2
  /exercise-qa chapter 3

Or test specific exercises:
  /exercise-qa <lesson-code> <exercise-name>
```

---

## When Mappings Are Generated

**Automatically generated when:**

1. **First time testing a course:**
   ```bash
   /exercise-qa /path/to/course/repo
   ```

2. **Testing by chapter without a mapping:**
   ```bash
   /exercise-qa chapter 2
   # If no mapping exists, skill reads outline.yml and creates one
   ```

3. **Mapping file is missing or outdated:**
   ```bash
   /exercise-qa au294 <exercise-name>
   # Skill detects missing mapping, reads outline.yml, creates mapping
   ```

**Manually regenerating:**
```bash
# Delete old mapping to force regeneration
rm config/courses/<ANSIBLE-COURSE>-mapping.json

# Next time you run QA skill, it will regenerate
/exercise-qa chapter 2
```

---

## What the QA Skill Detects

### Pattern 1: Single-Repo, Lesson-Based

**Indicators in outline.yml:**
- `dco:` in root (not `course:`)
- No `repository:` field in chapters
- Chapters have `lesson:` field

**Auto-detected:**
- Lesson codes (<lesson-code>, <lesson-code>, etc.)
- Exercise names from chapter content
- Materials path structure
- Exercise types (GE vs Lab)

---

### Pattern 2: Multi-Repo, Lesson-Based

**Indicators in outline.yml:**
- `dco:` in root
- `repository:` field in each chapter
- Each chapter maps to a separate repository

**Auto-detected:**
- Repository URLs for each chapter
- Lesson codes from repository names
- Exercise naming pattern (e.g., `<chapter>-review`)
- Need to clone lesson repositories

**QA skill will ask:**
```
Course uses multiple repositories. Clone them now?
  [ ] Clone all lesson repositories
  [ ] Use already-cloned repositories
```

---

### Pattern 3: Single-Repo, Chapter-Based

**Indicators in outline.yml:**
- `course:` in root (not `dco:`)
- Chapters organized by keywords
- No separate lesson codes

**Auto-detected:**
- Chapter keywords
- Exercise naming pattern (e.g., `install_config`)
- Materials path: `content/{keyword}/`
- Single repository structure

---

## Handling Mapping Errors

### If Auto-Detection Fails

```
⚠️  Could not auto-detect course structure.

Found in outline.yml:
  - Course code: AU999
  - Pattern: Unknown
  - Chapters: 5

Please verify:
  1. outline.yml exists and is valid YAML
  2. Course follows one of the 3 known patterns
  3. Chapters have required fields
```

**What to do:**
1. Check `outline.yml` for syntax errors
2. Verify the course follows a known pattern
3. Report the issue if it's a new pattern

### If Mapping Looks Wrong

```
Does this look correct? (yes/no)
User: no
```

**QA skill will ask:**
```
What's incorrect about the mapping?
  [ ] Wrong number of chapters
  [ ] Missing exercises
  [ ] Wrong lesson codes
  [ ] Other (please describe)
```

Then adjust and regenerate.

---

## Manual Override (Rare)

**You should rarely need to manually edit mappings**, but if you do:

1. **Edit the auto-generated file:**
   ```bash
   vim config/courses/<ANSIBLE-COURSE>-mapping.json
   ```

2. **Add a note explaining the override:**
   ```json
   {
     "course_code": "<ANSIBLE-COURSE>",
     "_manual_override": "Modified chapter 5 exercise list - not all exercises ready for testing",
     "mapping": {
       ...
     }
   }
   ```

3. **Test your changes:**
   ```bash
   /exercise-qa chapter 2 config/courses/<ANSIBLE-COURSE>-mapping.json
   ```

---

## Tips

✅ **DO:**
- Let the QA skill auto-generate mappings
- Review and confirm auto-detected mappings
- Regenerate mappings when course structure changes
- Commit mapping files to version control

❌ **DON'T:**
- Manually create mapping files from scratch
- Edit mappings unless absolutely necessary
- Hardcode paths or workstation names
- Ignore warnings during auto-detection

---

## Example Workflow

```bash
# 1. Clone course repo (if needed)
cd ~/git-repos/active/
git clone git@github.com:RedHatTraining/<ANSIBLE-COURSE>.git

# 2. Let QA skill auto-generate mapping
cd <ANSIBLE-COURSE>/
/exercise-qa chapter 2

# QA skill will:
#   - Read outline.yml
#   - Detect pattern
#   - Show you the mapping
#   - Ask for confirmation
#   - Save to config/courses/<ANSIBLE-COURSE>-mapping.json

# 3. Use the generated mapping
/exercise-qa chapter 3
/exercise-qa au0021l <exercise-name>

# 4. Commit the mapping file
git add ~/.claude/skills/qa/config/courses/<ANSIBLE-COURSE>-mapping.json
git commit -m "Add <ANSIBLE-COURSE> course mapping"
```

---

**Remember:** Course mappings are created automatically. Just point the QA skill at a course and it will figure out the structure.
