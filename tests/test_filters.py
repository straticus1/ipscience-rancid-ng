"""Tests for RANCID-NG filter functions."""

import os

import pytest

from rancid_ng.core.filters import (
    FilterMode,
    filter_passwords,
    filter_community_strings,
    filter_oscillating_data,
    should_filter_acl,
    filter_acl_sequences,
    OutputFilter,
)


class TestFilterPasswords:
    """Tests for password filtering."""

    def test_cisco_password_type_7(self):
        """Test filtering Cisco type 7 passwords."""
        line = "enable password 7 0822455D0A16"
        result = filter_passwords(line, FilterMode.YES)
        assert "0822455D0A16" not in result
        assert "<removed>" in result

    def test_cisco_secret(self):
        """Test filtering Cisco enable secret."""
        line = "enable secret 5 $1$xyz$abcdefghij"
        result = filter_passwords(line, FilterMode.YES)
        assert "$1$xyz" not in result
        assert "<removed>" in result

    def test_username_password(self):
        """Test filtering username password."""
        line = "username admin password 7 045F0E0B"
        result = filter_passwords(line, FilterMode.YES)
        assert "045F0E0B" not in result
        assert "<removed>" in result

    def test_ospf_auth_key(self):
        """Test filtering OSPF authentication key."""
        line = "ip ospf authentication-key mysecretkey"
        result = filter_passwords(line, FilterMode.YES)
        assert "mysecretkey" not in result
        assert "<removed>" in result

    def test_ntp_auth_key(self):
        """Test filtering NTP authentication key."""
        line = "ntp authentication-key 1 md5 myntpkey"
        result = filter_passwords(line, FilterMode.YES)
        assert "myntpkey" not in result
        assert "<removed>" in result

    def test_juniper_encrypted_password(self):
        """Test filtering Juniper encrypted password."""
        line = 'encrypted-password "$9$abcdefghijk";'
        result = filter_passwords(line, FilterMode.YES)
        assert "$9$abcdefghijk" not in result
        assert "<removed>" in result

    def test_no_filter_mode(self):
        """Test that NO mode doesn't filter."""
        line = "enable password 7 0822455D0A16"
        result = filter_passwords(line, FilterMode.NO)
        assert result == line

    def test_all_mode_filters_certificates(self):
        """Test that ALL mode filters certificates."""
        line = 'certificate "MIIBkTCB+wIBADANBg..."'
        result = filter_passwords(line, FilterMode.ALL)
        assert "MIIBkTCB" not in result
        assert "<removed>" in result

    def test_non_password_line_unchanged(self):
        """Test that non-password lines are unchanged."""
        line = "interface GigabitEthernet0/0"
        result = filter_passwords(line, FilterMode.YES)
        assert result == line


class TestFilterCommunityStrings:
    """Tests for SNMP community string filtering."""

    def test_snmp_community(self):
        """Test filtering SNMP community string."""
        line = "snmp-server community public RO"
        result = filter_community_strings(line, enabled=True)
        assert "public" not in result
        assert "<removed>" in result

    def test_snmp_community_disabled(self):
        """Test that disabled filtering preserves community."""
        line = "snmp-server community public RO"
        result = filter_community_strings(line, enabled=False)
        assert result == line

    def test_community_rw(self):
        """Test filtering community with RW access."""
        line = "snmp-server community secret123 RW"
        result = filter_community_strings(line, enabled=True)
        assert "secret123" not in result
        assert "RW" in result  # Access level preserved

    def test_trap_group_community(self):
        """Test filtering trap group community."""
        line = 'trap-group mygroup version v2c community "mycommunity"'
        result = filter_community_strings(line, enabled=True)
        assert "mycommunity" not in result


class TestFilterOscillatingData:
    """Tests for oscillating data filtering."""

    def test_filter_time(self):
        """Test filtering time stamps."""
        line = "Last reboot at 14:30:45"
        result = filter_oscillating_data(line, FilterMode.YES)
        assert "14:30:45" not in result
        assert "<time>" in result

    def test_filter_date_iso(self):
        """Test filtering ISO date format."""
        line = "Config saved on 2024-01-15"
        result = filter_oscillating_data(line, FilterMode.YES)
        assert "2024-01-15" not in result
        assert "<date>" in result

    def test_filter_uptime(self):
        """Test filtering uptime."""
        line = "System uptime is 5 days, 4 hours, 30 minutes"
        result = filter_oscillating_data(line, FilterMode.YES)
        assert "5 days" not in result
        assert "<uptime>" in result

    def test_filter_packet_counters(self):
        """Test filtering packet counters."""
        line = "  12345678 packets input"
        result = filter_oscillating_data(line, FilterMode.YES)
        assert "12345678" not in result
        assert "<count>" in result

    def test_no_filter_mode(self):
        """Test that NO mode doesn't filter."""
        line = "System uptime is 5 days"
        result = filter_oscillating_data(line, FilterMode.NO)
        assert result == line


class TestShouldFilterAcl:
    """Tests for ACL filtering check."""

    def test_no_regex(self):
        """Test with no regex configured."""
        assert should_filter_acl("test-acl", None) is False

    def test_matching_regex(self):
        """Test with matching regex."""
        assert should_filter_acl("temp-acl", "temp-.*") is True

    def test_non_matching_regex(self):
        """Test with non-matching regex."""
        assert should_filter_acl("permanent-acl", "temp-.*") is False

    def test_multiple_regex(self):
        """Test with multiple regexes (semicolon separated)."""
        assert should_filter_acl("temp-acl", "test-.*;temp-.*") is True
        assert should_filter_acl("test-acl", "test-.*;temp-.*") is True
        assert should_filter_acl("other-acl", "test-.*;temp-.*") is False


class TestFilterAclSequences:
    """Tests for ACL sequence number filtering."""

    def test_filter_sequence_permit(self):
        """Test filtering sequence from permit."""
        line = "10 permit ip any any"
        result = filter_acl_sequences(line, enabled=True)
        assert result.strip() == "permit ip any any"

    def test_filter_sequence_deny(self):
        """Test filtering sequence from deny."""
        line = "  20 deny ip host 10.0.0.1 any"
        result = filter_acl_sequences(line, enabled=True)
        assert "20" not in result
        assert "deny ip" in result

    def test_disabled(self):
        """Test that disabled preserves sequences."""
        line = "10 permit ip any any"
        result = filter_acl_sequences(line, enabled=False)
        assert result == line


class TestOutputFilter:
    """Tests for OutputFilter class."""

    def test_combined_filtering(self):
        """Test all filters applied together."""
        filter = OutputFilter(
            filter_pwds=FilterMode.YES,
            filter_commstr=True,
            filter_osc=FilterMode.YES,
        )

        line = "enable password 7 0822455D0A16"
        result = filter.filter(line)
        assert "0822455D0A16" not in result

    def test_from_env(self, clean_env):
        """Test creating filter from environment."""
        os.environ["FILTER_PWDS"] = "ALL"
        os.environ["NOCOMMSTR"] = "YES"
        os.environ["FILTER_OSC"] = "NO"

        filter = OutputFilter.from_env()

        assert filter.filter_pwds == FilterMode.ALL
        assert filter.filter_commstr is True
        assert filter.filter_osc == FilterMode.NO

    def test_from_env_defaults(self, clean_env):
        """Test default values when env not set."""
        filter = OutputFilter.from_env()

        assert filter.filter_pwds == FilterMode.YES
        assert filter.filter_commstr is False
        assert filter.filter_osc == FilterMode.YES
