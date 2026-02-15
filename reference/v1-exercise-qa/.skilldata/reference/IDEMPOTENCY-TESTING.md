# Idempotency Testing Guide

**Purpose:** Ensure students can practice exercises repeatedly with consistent results.

**Key Principle:** `lab start` → `lab finish` → `lab start` must produce identical initial state.

---

## Why Idempotency Matters

### Student Needs
- Practice multiple times to master concepts
- Retry after making mistakes
- Study for certifications
- Get consistent, predictable results

### Without Idempotency
```
First attempt: Clean environment, exercise works
Second attempt: Leftover artifacts, unexpected behavior
Third attempt: More artifacts accumulate, exercise breaks
```

### With Idempotency
```
Every attempt: Clean environment, consistent behavior
Students can practice 10, 20, 100 times - always same starting point
```

---

## How to Test

```bash
# Cycle 1
lab finish <exercise>           # Clean any previous state
lab start <exercise>
<capture state: users, groups, files, services>
<run exercise>
lab finish <exercise>

# Cycle 2
lab start <exercise>
<capture state again>

# Compare
diff state1 state2             # Must be IDENTICAL
```

### Automated Test Script

```bash
#!/bin/bash
EXERCISE="$1"

# Capture state function
capture_state() {
    local prefix=$1
    ansible all -m shell -a 'hostname; getent passwd; getent group; ls -la ~student' > "${prefix}_state.txt"
}

# Test
lab finish $EXERCISE
lab start $EXERCISE
capture_state "cycle1"
lab finish $EXERCISE

lab start $EXERCISE
capture_state "cycle2"

# Compare
if diff -q cycle1_state.txt cycle2_state.txt; then
    echo "✅ IDEMPOTENT"
else
    echo "❌ NOT IDEMPOTENT"
    diff cycle1_state.txt cycle2_state.txt
fi
```

---

## Common Issues

### 1. Incomplete Cleanup

**Problem:** `finish.yml` doesn't remove all artifacts

**Example:**
```yaml
# start.yml creates users on servera
# finish.yml only removes from servera
# But student experimentation created users on serverb
# → Users remain on serverb!
```

**Fix:**
```yaml
# Remove from ALL hosts, not just expected ones
- hosts: all                    # Not just servera
  tasks:
    - name: Remove users
      ansible.builtin.user:
        name: "{{ item }}"
        state: absent
        remove: yes
      loop: [mary, nick]
      failed_when: false          # OK if user doesn't exist
```

### 2. Asymmetric Operations

**Problem:** Start creates on Host A, finish removes from Host B

**Example:**
```yaml
# start.yml
- hosts: servera
  tasks:
    - copy: dest=/etc/config.conf ...

# finish.yml
- hosts: serverb              # Wrong host!
  tasks:
    - file: path=/etc/config.conf state=absent
```

**Fix:** Mirror setup and cleanup
```yaml
# finish.yml
- hosts: servera              # Same host as start
  tasks:
    - file: path=/etc/config.conf state=absent
```

### 3. Conditional Artifacts

**Problem:** Artifacts created based on conditions, cleanup unconditional

**Example:**
```yaml
# Exercise creates users based on SELinux mode
# Student changes SELinux mode during practice
# Users end up in unexpected places
# Cleanup assumes expected locations → Fails
```

**Fix:** Comprehensive cleanup regardless of conditions
```yaml
- hosts: all
  tasks:
    - name: Remove all exercise users everywhere
      ansible.builtin.user:
        name: "{{ item }}"
        state: absent
      loop: [user1, user2, user3]
      failed_when: false
```

### 4. Forgotten Dependencies

**Problem:** Groups, files, services created but not removed

**Example:**
```yaml
# start.yml
- name: Create developer group
  group: name=developer state=present

# finish.yml
- name: Remove users
  user: name={{ item }} state=absent
  # Forgot to remove developer group!
```

**Fix:** Track and remove ALL created resources
```yaml
# finish.yml
- name: Remove users
  user: name={{ item }} state=absent

- name: Remove groups              # Add this
  group: name=developer state=absent
```

---

## Best Practices

### 1. Clean from ALL Hosts

```yaml
# Good
- hosts: all
  tasks:
    - name: Remove artifacts
      ...

# Bad (assumes artifacts only on specific host)
- hosts: servera
  tasks:
    - name: Remove artifacts
      ...
```

### 2. Use failed_when: false

```yaml
# Good (idempotent)
- name: Remove user
  user: name=mary state=absent
  failed_when: false          # OK if doesn't exist

# Bad (fails if user doesn't exist)
- name: Remove user
  user: name=mary state=absent
```

### 3. Mirror Setup and Cleanup

```yaml
# start.yml
- hosts: datacenter_west
  tasks:
    - name: Create config
      copy: ...

# finish.yml (must match)
- hosts: datacenter_west      # Same hosts
  tasks:
    - name: Remove config
      file: ... state=absent
```

### 4. Remove Everything

**Checklist:**
- [ ] All users created
- [ ] All groups created
- [ ] All files/directories created
- [ ] All services started/enabled
- [ ] All configuration changes
- [ ] All firewall rules
- [ ] All network changes

---

## Testing Checklist

- [ ] Run: `lab start <exercise>`
- [ ] Capture initial state (users, groups, files, services)
- [ ] Run solution
- [ ] Run: `lab finish <exercise>`
- [ ] Run: `lab start <exercise>`
- [ ] Capture state again
- [ ] Compare states → must match
- [ ] Repeat with student experiments/mistakes
- [ ] Verify cleanup handles all cases

---

## When to Report as Bug

**Always P1 (Critical) if idempotency broken:**
- Students cannot practice repeatedly
- Environment accumulates artifacts
- Second run behaves differently than first

**Even if:**
- Exercise works on first run
- Instructions correct
- Solutions work

**Why:** Repeatability is essential for training.

---

## Summary

**Idempotent Exercise:**
```
start → finish → start → finish → start
  ↓         ↓        ↓         ↓        ↓
clean     clean    clean     clean    clean
  (identical initial state every time)
```

**Key Points:**
1. Remove artifacts from ALL hosts
2. Use `failed_when: false` for idempotent cleanup
3. Mirror setup and cleanup
4. Test: start → finish → start
5. Always P1 severity if broken

**Remember:** If students can't practice repeatedly, the exercise is broken.
