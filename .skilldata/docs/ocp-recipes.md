# OpenShift / Kubernetes Courses (DO*)

These courses use `oc` and `kubectl` commands, virtual machines via OpenShift Virtualization, and the OpenShift web console.

**Lab environment setup:**
1. The workstation must be provisioned with an OCP cluster image (check `cat /etc/rht` for `RHT_COURSE` and `RHT_VMTREE`)
2. The lab manifest (`~/.grading/lab_manifest.json`) lists which exercise SKUs are available
3. Run `lab install <lesson-sku>` to install grading packages for each lesson — the SKU is the lowercase lesson code (e.g., `do0024l`)
4. If `lab install` fails with "not part of this course curriculum", the workstation image doesn't include that course. Check `lab list` for available SKUs

**DynoLabs package installation:**
- The `lab` binary is a compiled Rust CLI (`/usr/local/bin/lab`) that manages Python grading packages via `uv`
- Each lesson has a Python grading package in `classroom/grading/` with a `pyproject.toml`
- `lab install <sku>` uses `uv` to install the package from the Red Hat Training PyPI mirror — but is blocked for packages not in the manifest
- `lab force <sku>` bypasses all manifest constraints and is the correct tool for QA/development when testing packages not in the workstation's manifest
- The package depends on `rht-labs-core` (the DynoLabs framework) and course-specific libraries (e.g., `rht-labs-ocp` for OpenShift)
- The lab manifest (`~/.grading/lab_manifest.json`) maps exercise names to their lesson SKU and version
- `lab version` shows the active course library name and version
- `lab activate <sku>` switches between already-installed courses without reinstalling

**Storage classes:**
- Before creating PVCs, always check available storage classes: `oc get sc`
- Different clusters use different storage backends (Ceph RBD, LVMS, etc.)
- Use the default storage class or the one the exercise specifies
- Common pattern: `ocs-external-storagecluster-ceph-rbd-virtualization` for VM disks

**Virtual machine operations:**
- Use `ssh_tool.py vm-exec <vm> -n <ns> -c <cmd>` to run commands inside VMs. It auto-detects the auth method (SSH keys vs password) and falls back to serial console when needed.
- Check the course profile's `vm_auth` field: `"ssh_keys"` means `virtctl ssh` works directly, `"password"` means the VMs use password auth via the VNC/serial console. The `vm_default_password` field contains the password if detected.
- `virtctl console <vm>` is interactive — use `ssh_tool.py vm-exec` or `virtctl ssh <user>@<vm> --command '<cmd>' -l <user> --known-hosts=` for non-interactive execution
- Wait for VMs to be in `Running` status before connecting: `oc get vm -n <project>`
- Verify disk state from outside the VM using `virsh domblklist` via the virt-launcher pod:
  ```bash
  oc exec -n <ns> $(oc get pods -n <ns> -l vm.kubevirt.io/name=<vm> --no-headers -o name) -- virsh domblklist 1
  ```

**Adding disks to VMs (programmatic equivalent of web console "Add disk"):**

The web console's "Add disk" creates a DataVolume and patches the VM spec. To replicate this programmatically:

1. **Create a DataVolume** for the disk:
```bash
ssh_tool.py run "cat <<'EOF' | oc apply -f -
apiVersion: cdi.kubevirt.io/v1beta1
kind: DataVolume
metadata:
  name: <disk-name>
  namespace: <ns>
spec:
  source:
    blank: {}
  storage:
    accessModes: [ReadWriteMany]
    resources:
      requests:
        storage: <size>   # e.g. 5Gi
    storageClassName: <sc> # e.g. ocs-external-storagecluster-ceph-rbd-virtualization
    volumeMode: Block      # Block for RBD, Filesystem for NFS
EOF"
```

2. **Wait for the DataVolume to be ready:**
```bash
ssh_tool.py run "oc wait dv/<disk-name> -n <ns> --for=condition=Ready --timeout=120s"
```

3a. **Attach with virtio interface** (VM must be stopped):
```bash
ssh_tool.py run "virtctl stop <vm> -n <ns>"
# Wait for stop, then patch VM spec to add disk + volume
ssh_tool.py run "oc patch vm <vm> -n <ns> --type=json -p '[
  {\"op\":\"add\",\"path\":\"/spec/template/spec/domain/devices/disks/-\",\"value\":{\"name\":\"<disk-name>\",\"disk\":{\"bus\":\"virtio\"}}},
  {\"op\":\"add\",\"path\":\"/spec/template/spec/volumes/-\",\"value\":{\"name\":\"<disk-name>\",\"dataVolume\":{\"name\":\"<disk-name>\"}}}
]'"
ssh_tool.py run "virtctl start <vm> -n <ns>"
```
Note: If the `disks` array doesn't exist in the VM spec, use `"op":"add","path":"/spec/template/spec/domain/devices/disks","value":[...]` to create it.

3b. **Hot-plug with SCSI interface** (VM can stay running):
```bash
ssh_tool.py run "virtctl addvolume <vm> --volume-name=<disk-name> --disk-type=disk --persist -n <ns>"
```
Hot-plugged disks appear as `sda`/`sdb`/`sdc` (SCSI), not `vdX` (virtio).

**Detaching disks from VMs:**

- **Hot-plugged disks** (added via `virtctl addvolume`):
  ```bash
  ssh_tool.py run "virtctl removevolume <vm> --volume-name=<disk-name> --persist -n <ns>"
  ```

- **Original VM spec disks** (not hot-pluggable): Must use `oc patch` to remove from ALL three locations — `disks[]`, `volumes[]`, and `dataVolumeTemplates[]` — in a single patch. The VM must be stopped.
  ```bash
  # First, find the indexes:
  ssh_tool.py run "oc get vm <vm> -n <ns> -o json | python3 -c '
  import sys,json; vm=json.load(sys.stdin)
  for i,d in enumerate(vm[\"spec\"][\"template\"][\"spec\"][\"domain\"][\"devices\"].get(\"disks\",[])):
      print(f\"disk {i}: {d[\"name\"]}\")
  for i,v in enumerate(vm[\"spec\"][\"template\"][\"spec\"][\"volumes\"]):
      print(f\"vol  {i}: {v[\"name\"]}\")
  for i,t in enumerate(vm[\"spec\"].get(\"dataVolumeTemplates\",[])):
      print(f\"dvt  {i}: {t[\"metadata\"][\"name\"]}\")
  '"
  # Then remove by index (use the correct indexes for the disk to remove):
  ssh_tool.py run "oc patch vm <vm> -n <ns> --type=json -p '[
    {\"op\":\"remove\",\"path\":\"/spec/template/spec/domain/devices/disks/<disk-idx>\"},
    {\"op\":\"remove\",\"path\":\"/spec/template/spec/volumes/<vol-idx>\"},
    {\"op\":\"remove\",\"path\":\"/spec/dataVolumeTemplates/<dvt-idx>\"}
  ]'"
  ```
  All three removals must be in the same patch — removing a volume without its dataVolumeTemplate will be rejected by the API.

**Web console testing with Playwright:**
Many OCP exercises use the web console (console-openshift-console.apps.ocp4.example.com). Use `web_tool.py` to automate:

```bash
# Login to OCP console and navigate to VMs page (single session)
web_tool.py login "https://console-openshift-console.apps.ocp4.example.com" \
  --username admin --password redhatocp \
  --then "https://console-openshift-console.apps.ocp4.example.com/k8s/ns/storage-intro/kubevirt.io~v1~VirtualMachine" \
  --screenshot "/tmp/ocp-console.png"
```

**Important:** Always use the console URL as the login target, NOT the OAuth authorize URL. The console handles the OAuth redirect chain automatically, maintaining proper state tokens.

For actions that have CLI equivalents, prefer `oc` commands over Playwright — they're faster and more reliable. Use Playwright for:
- Verifying the web console shows the correct state (visual verification)
- Testing web console-specific workflows that have no CLI equivalent
- Taking screenshots for QA reports

## Dev Container Exercises

Some courses run tools inside podman containers instead of directly on workstation.

1. Course profile will show `uses_dev_containers: true`
2. After `lab start`, check for `.devcontainer/` in exercise dir
3. Use `devcontainer-start` to spin up the container
4. Pre-pull the EE image inside the container before running ansible-navigator
5. Run exercise commands via `devcontainer-run`
6. `lab` commands still run on workstation (not in container)
7. Let `lab finish` handle container cleanup — do NOT run `devcontainer-stop` before `lab finish`, as `lab finish` runs `remove-dev-containers.yml` which properly cleans up containers AND prunes podman storage

## ansible-navigator Commands

When running `ansible-navigator` via ssh_tool (non-interactively), **always append `-m stdout`** to prevent the interactive TUI from launching. The EPUB may or may not include this flag — add it regardless.

```bash
# EPUB says:          ansible-navigator run site.yml
# You should run:     ansible-navigator run site.yml -m stdout

# EPUB says:          ansible-navigator inventory -i inventory --list
# You should run:     ansible-navigator inventory -i inventory --list -m stdout
```

Do NOT translate `ansible-navigator` to `ansible-playbook`. The course profile tells you which tool the course expects.
