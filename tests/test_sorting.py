"""Tests for RANCID-NG sorting functions."""

import pytest

from rancid_ng.core.sorting import (
    keysort,
    keynsort,
    numsort,
    valsort,
    ipsort,
    ipaddrval,
    sortbyipaddr,
    aclsort,
)


class TestKeysort:
    """Tests for keysort function."""

    def test_alphabetical_sort(self):
        """Test basic alphabetical sorting on keys."""
        lines = {
            "B": "line B",
            "A": "line A",
            "C": "line C",
        }
        result = keysort(lines)
        assert result == ["line A", "line B", "line C"]

    def test_alphanumeric_keys(self):
        """Test sorting with alphanumeric keys."""
        lines = {
            "A10": "line A10",
            "A2": "line A2",
            "A1": "line A1",
        }
        result = keysort(lines)
        # Alphabetical sort: A1 < A10 < A2
        assert result == ["line A1", "line A10", "line A2"]

    def test_empty_dict(self):
        """Test with empty dictionary."""
        assert keysort({}) == []

    def test_single_entry(self):
        """Test with single entry."""
        lines = {"only": "single line"}
        assert keysort(lines) == ["single line"]


class TestKeynsort:
    """Tests for keynsort function."""

    def test_numeric_sort(self):
        """Test numeric sorting on keys."""
        lines = {
            "10": "line 10",
            "2": "line 2",
            "1": "line 1",
        }
        result = keynsort(lines)
        assert result == ["line 1", "line 2", "line 10"]

    def test_mixed_numeric_keys(self):
        """Test with varying numeric values."""
        lines = {
            "100": "hundred",
            "5": "five",
            "50": "fifty",
            "1": "one",
        }
        result = keynsort(lines)
        assert result == ["one", "five", "fifty", "hundred"]

    def test_non_numeric_keys_default_to_zero(self):
        """Test that non-numeric keys sort as zero."""
        lines = {
            "abc": "non-numeric",
            "1": "one",
        }
        result = keynsort(lines)
        # "abc" converts to 0, so it comes before 1
        assert result == ["non-numeric", "one"]

    def test_empty_dict(self):
        """Test with empty dictionary."""
        assert keynsort({}) == []


class TestNumsort:
    """Tests for numsort function."""

    def test_numeric_sort(self):
        """Test numeric sorting."""
        lines = {
            10: "ten",
            2: "two",
            1: "one",
        }
        result = numsort(lines)
        assert result == ["one", "two", "ten"]

    def test_float_keys(self):
        """Test with float keys."""
        lines = {
            "1.5": "one point five",
            "2.0": "two",
            "1.0": "one",
        }
        result = numsort(lines)
        assert result == ["one", "one point five", "two"]


class TestValsort:
    """Tests for valsort function."""

    def test_sort_by_value(self):
        """Test sorting by value."""
        lines = {
            "key1": "zebra",
            "key2": "apple",
            "key3": "monkey",
        }
        result = valsort(lines)
        assert result == ["apple", "monkey", "zebra"]

    def test_empty_dict(self):
        """Test with empty dictionary."""
        assert valsort({}) == []


class TestIpaddrval:
    """Tests for ipaddrval function."""

    def test_ipv4_address(self):
        """Test IPv4 address conversion."""
        result = ipaddrval("192.168.1.1")
        # Should return "4" prefix + zero-padded octets
        assert result == "4192168001001"

    def test_ipv4_with_prefix(self):
        """Test IPv4 address with prefix."""
        result = ipaddrval("192.168.1.0/24")
        assert result.startswith("4")

    def test_ipv6_address(self):
        """Test IPv6 address conversion."""
        result = ipaddrval("2001:db8::1")
        # Should return "6" prefix + expanded hex
        assert result.startswith("6")
        assert "2001" in result

    def test_invalid_address(self):
        """Test that invalid addresses return original."""
        result = ipaddrval("not-an-ip")
        assert result == "not-an-ip"


class TestSortbyipaddr:
    """Tests for sortbyipaddr function."""

    def test_ipv4_comparison(self):
        """Test IPv4 address comparison."""
        assert sortbyipaddr("192.168.1.1", "192.168.1.2") == -1
        assert sortbyipaddr("192.168.1.2", "192.168.1.1") == 1
        assert sortbyipaddr("192.168.1.1", "192.168.1.1") == 0

    def test_different_networks(self):
        """Test different network comparison."""
        assert sortbyipaddr("10.0.0.1", "192.168.1.1") == -1
        assert sortbyipaddr("192.168.1.1", "10.0.0.1") == 1


class TestIpsort:
    """Tests for ipsort function."""

    def test_ipv4_sort(self):
        """Test sorting IPv4 addresses."""
        lines = {
            "192.168.1.10": "host 10",
            "192.168.1.2": "host 2",
            "10.0.0.1": "private",
        }
        result = ipsort(lines)
        assert result == ["private", "host 2", "host 10"]

    def test_mixed_ip_versions(self):
        """Test sorting mixed IPv4 and IPv6."""
        lines = {
            "192.168.1.1": "ipv4 host",
            "2001:db8::1": "ipv6 host",
            "10.0.0.1": "private",
        }
        result = ipsort(lines)
        # IPv4 (prefix "4") comes before IPv6 (prefix "6")
        assert result[0] == "private"
        assert result[1] == "ipv4 host"
        assert result[2] == "ipv6 host"

    def test_empty_dict(self):
        """Test with empty dictionary."""
        assert ipsort({}) == []


class TestAclsort:
    """Tests for aclsort function."""

    def test_acl_with_ip_addresses(self):
        """Test ACL sorting with IP addresses."""
        lines = [
            "permit ip 192.168.1.0 0.0.0.255 any",
            "permit ip 10.0.0.0 0.0.0.255 any",
            "permit ip 172.16.0.0 0.0.255.255 any",
        ]
        result = aclsort(lines)
        # Should sort by extracted IP addresses
        assert "10.0.0.0" in result[0]

    def test_acl_without_ip(self):
        """Test ACL entries without IP addresses."""
        lines = [
            "remark Third line",
            "remark First line",
            "remark Second line",
        ]
        result = aclsort(lines)
        # Should sort by full line content
        assert result[0] == "remark First line"

    def test_empty_list(self):
        """Test with empty list."""
        assert aclsort([]) == []
