#!/usr/bin/env python3
"""
Detect Workstation Host from SSH Config

Reads ~/.ssh/config and identifies hosts that could be the workstation machine.
Looks for patterns like "workstation", "dev_workstation", "au294_workstation", etc.

Usage:
    python scripts/detect_workstation.py
"""

import os
import re
from pathlib import Path


def parse_ssh_config(config_path):
    """
    Parse SSH config file and extract host entries.

    Returns:
        list: List of dictionaries with host configurations
    """
    hosts = []
    current_host = None

    try:
        with open(config_path, 'r') as f:
            for line in f:
                line = line.strip()

                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue

                # Handle Include directives
                if line.startswith('Include '):
                    include_pattern = line.split(None, 1)[1]
                    include_path = os.path.expanduser(f"~/.ssh/{include_pattern}")

                    # Parse included files
                    if os.path.exists(include_path):
                        included_hosts = parse_ssh_config(include_path)
                        hosts.extend(included_hosts)
                    continue

                # Host declaration
                if line.startswith('Host '):
                    if current_host:
                        hosts.append(current_host)

                    host_name = line.split(None, 1)[1]
                    current_host = {
                        'name': host_name,
                        'hostname': None,
                        'user': None,
                        'port': None
                    }

                # Host properties
                elif current_host:
                    if line.startswith('Hostname '):
                        current_host['hostname'] = line.split(None, 1)[1]
                    elif line.startswith('User '):
                        current_host['user'] = line.split(None, 1)[1]
                    elif line.startswith('Port '):
                        current_host['port'] = line.split(None, 1)[1]

            # Add last host
            if current_host:
                hosts.append(current_host)

    except FileNotFoundError:
        return []

    return hosts


def find_workstation_candidates(hosts):
    """
    Find hosts that match workstation patterns.

    Args:
        hosts: List of host dictionaries from parse_ssh_config

    Returns:
        list: List of candidate host names
    """
    candidates = []

    # Patterns to match (case-insensitive)
    patterns = [
        r'^workstation$',           # Exact match
        r'.*workstation.*',          # Contains "workstation"
        r'^dev_workstation$',        # dev_workstation
        r'^.*_workstation$',         # Anything ending with _workstation
        r'^workstation_.*$',         # Anything starting with workstation_
    ]

    for host in hosts:
        host_name = host['name']

        # Skip wildcard hosts
        if '*' in host_name or '?' in host_name:
            continue

        # Check if host matches any pattern
        for pattern in patterns:
            if re.match(pattern, host_name, re.IGNORECASE):
                candidates.append({
                    'name': host_name,
                    'hostname': host.get('hostname', 'N/A'),
                    'user': host.get('user', 'N/A')
                })
                break

    return candidates


def main():
    """Main function to detect workstation."""
    config_path = os.path.expanduser('~/.ssh/config')

    print(f"🔍 Analyzing SSH config: {config_path}\n")

    if not os.path.exists(config_path):
        print(f"❌ SSH config not found at {config_path}")
        print("   Please create ~/.ssh/config with workstation host configuration")
        return 1

    # Parse SSH config
    hosts = parse_ssh_config(config_path)

    if not hosts:
        print("❌ No hosts found in SSH config")
        return 1

    print(f"✅ Found {len(hosts)} host(s) in SSH config\n")

    # Find workstation candidates
    candidates = find_workstation_candidates(hosts)

    if not candidates:
        print("❌ No workstation candidates found")
        print("\nSearched for patterns:")
        print("  - workstation")
        print("  - *workstation*")
        print("  - dev_workstation")
        print("  - au294_workstation")
        print("\nAvailable hosts:")
        for host in hosts:
            if '*' not in host['name'] and '?' not in host['name']:
                print(f"  - {host['name']}")
        return 1

    print("🎯 Workstation candidates found:\n")
    for i, candidate in enumerate(candidates, 1):
        print(f"{i}. Host: {candidate['name']}")
        print(f"   Hostname: {candidate['hostname']}")
        print(f"   User: {candidate['user']}")
        print()

    # If only one candidate, recommend it
    if len(candidates) == 1:
        print(f"✅ Recommended workstation: {candidates[0]['name']}")
        print(f"\nVerify with: ssh {candidates[0]['name']} hostname")
    else:
        print(f"⚠️  Multiple candidates found. Please verify which one to use.")

    return 0


if __name__ == "__main__":
    exit(main())
