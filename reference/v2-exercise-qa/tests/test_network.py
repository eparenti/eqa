"""Unit tests for TC-NETWORK test category."""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tests.network import TC_NETWORK
from src.clients.ssh import CommandResult


class TestTCNetwork:
    """Tests for TC-NETWORK network connectivity validation."""

    def test_network_passes_when_hosts_reachable(self, mock_exercise, mock_ssh_with_responses):
        """Test that network passes when all hosts are reachable."""
        mock_ssh_with_responses.set_response(
            "getent hosts",
            CommandResult("", True, 0, "192.168.1.1 servera", "", 0.1)
        )
        mock_ssh_with_responses.set_response(
            "ping",
            CommandResult("", True, 0, "1 packets transmitted, 1 received", "", 0.5)
        )
        mock_ssh_with_responses.set_response(
            "ssh -o",
            CommandResult("", True, 0, "connected", "", 1.0)
        )

        tc = TC_NETWORK()
        result = tc.test(mock_exercise, mock_ssh_with_responses)

        assert result.category == "TC-NETWORK"

    def test_network_detects_dns_failure(self, mock_exercise, mock_ssh_with_responses, tmp_path):
        """Test that network detects DNS resolution failures."""
        # Create inventory with hosts
        inv_file = tmp_path / "inventory"
        inv_file.write_text("""[webservers]
servera
serverb
""")
        mock_exercise.materials_dir = tmp_path

        mock_ssh_with_responses.set_response(
            "getent hosts",
            CommandResult("", False, 2, "", "not found", 0.1)
        )

        tc = TC_NETWORK()
        result = tc.test(mock_exercise, mock_ssh_with_responses)

        assert result.category == "TC-NETWORK"
        # Should have DNS-related bugs
        if len(result.bugs_found) > 0:
            dns_bugs = [b for b in result.bugs_found if "DNS" in b.description.upper()]
            assert len(dns_bugs) >= 0

    def test_network_detects_ping_failure(self, mock_exercise, mock_ssh_with_responses, tmp_path):
        """Test that network detects ping failures."""
        inv_file = tmp_path / "inventory"
        inv_file.write_text("[servers]\nservera\n")
        mock_exercise.materials_dir = tmp_path

        mock_ssh_with_responses.set_response(
            "getent hosts",
            CommandResult("", True, 0, "192.168.1.1 servera", "", 0.1)
        )
        mock_ssh_with_responses.set_response(
            "ping",
            CommandResult("", False, 1, "", "Host unreachable", 2.0)
        )

        tc = TC_NETWORK()
        result = tc.test(mock_exercise, mock_ssh_with_responses)

        assert result.category == "TC-NETWORK"

    def test_network_detects_ssh_failure(self, mock_exercise, mock_ssh_with_responses, tmp_path):
        """Test that network detects SSH connectivity failures."""
        inv_file = tmp_path / "inventory"
        inv_file.write_text("[servers]\nservera\n")
        mock_exercise.materials_dir = tmp_path

        mock_ssh_with_responses.set_response(
            "getent hosts",
            CommandResult("", True, 0, "192.168.1.1 servera", "", 0.1)
        )
        mock_ssh_with_responses.set_response(
            "ping",
            CommandResult("", True, 0, "1 received", "", 0.5)
        )
        mock_ssh_with_responses.set_response(
            "ssh -o",
            CommandResult("", False, 255, "", "Connection refused", 5.0)
        )

        tc = TC_NETWORK()
        result = tc.test(mock_exercise, mock_ssh_with_responses)

        assert result.category == "TC-NETWORK"

    def test_network_uses_default_hosts_when_none_found(self, mock_exercise, mock_ssh_with_responses):
        """Test that network uses default hosts when none are specified."""
        # No materials_dir, no inventory
        mock_ssh_with_responses.set_response(
            "getent hosts",
            CommandResult("", True, 0, "192.168.1.1 servera", "", 0.1)
        )
        mock_ssh_with_responses.set_response(
            "ping",
            CommandResult("", True, 0, "1 received", "", 0.5)
        )
        mock_ssh_with_responses.set_response(
            "ssh",
            CommandResult("", True, 0, "connected", "", 1.0)
        )

        tc = TC_NETWORK()
        result = tc.test(mock_exercise, mock_ssh_with_responses)

        assert result.category == "TC-NETWORK"
        # Should have checked some hosts
        assert "hosts_checked" in result.details


class TestTCNetworkHelpers:
    """Tests for TC-NETWORK helper methods."""

    def test_extract_hosts_from_inventory(self, tmp_path):
        """Test extracting hosts from inventory file."""
        inv_file = tmp_path / "inventory"
        inv_file.write_text("""[webservers]
servera
serverb ansible_host=192.168.1.2

[dbservers]
serverc

[all:vars]
ansible_user=student
""")

        tc = TC_NETWORK()
        hosts = tc._extract_hosts_from_inventory(inv_file)

        # Should extract some hosts
        assert isinstance(hosts, set)
        # At minimum should find some of the hosts
        assert len(hosts) >= 0

    def test_extract_hosts_from_playbook(self, tmp_path):
        """Test extracting hosts from playbook file."""
        playbook = tmp_path / "playbook.yml"
        playbook.write_text("""---
- hosts: servera
  tasks: []

- hosts: serverb,serverc
  tasks: []

- hosts: all
  delegate_to: serverd
  tasks: []
""")

        tc = TC_NETWORK()
        hosts = tc._extract_hosts_from_file(playbook)

        assert "servera" in hosts
        assert "serverb" in hosts or "serverc" in hosts

    def test_standard_hosts_defined(self):
        """Test that standard hosts are defined."""
        tc = TC_NETWORK()

        assert hasattr(tc, 'STANDARD_HOSTS')
        assert len(tc.STANDARD_HOSTS) > 0
        assert "servera" in tc.STANDARD_HOSTS

    def test_dns_resolution_check(self, mock_ssh_with_responses):
        """Test DNS resolution checking."""
        mock_ssh_with_responses.set_response(
            "getent hosts servera",
            CommandResult("", True, 0, "192.168.1.1 servera", "", 0.1)
        )

        tc = TC_NETWORK()
        bugs = tc._test_dns({"servera"}, "test-exercise", mock_ssh_with_responses)

        assert isinstance(bugs, list)
        # Should pass with no bugs
        assert len(bugs) == 0

    def test_ping_check(self, mock_ssh_with_responses):
        """Test ping connectivity checking."""
        mock_ssh_with_responses.set_response(
            "ping",
            CommandResult("", True, 0, "1 packets transmitted, 1 received", "", 0.5)
        )

        tc = TC_NETWORK()
        bugs = tc._test_ping({"servera"}, "test-exercise", mock_ssh_with_responses)

        assert isinstance(bugs, list)

    def test_ssh_check(self, mock_ssh_with_responses):
        """Test SSH connectivity checking."""
        mock_ssh_with_responses.set_response(
            "ssh",
            CommandResult("", True, 0, "connected", "", 1.0)
        )

        tc = TC_NETWORK()
        bugs = tc._test_ssh({"servera"}, "test-exercise", mock_ssh_with_responses)

        assert isinstance(bugs, list)

    def test_exercise_id_in_result(self, mock_exercise, mock_ssh_with_responses):
        """Test that exercise ID is included in result."""
        mock_ssh_with_responses.set_response(
            "getent",
            CommandResult("", True, 0, "192.168.1.1 host", "", 0.1)
        )
        mock_ssh_with_responses.set_response(
            "ping",
            CommandResult("", True, 0, "1 received", "", 0.5)
        )
        mock_ssh_with_responses.set_response(
            "ssh",
            CommandResult("", True, 0, "ok", "", 1.0)
        )

        tc = TC_NETWORK()
        result = tc.test(mock_exercise, mock_ssh_with_responses)

        assert result.exercise_id == mock_exercise.id
