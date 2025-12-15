"""
Output filtering functions for RANCID-NG.

These filters handle:
- Password/secret filtering (FILTER_PWDS)
- SNMP community string filtering (NOCOMMSTR)
- Oscillating data filtering (FILTER_OSC)
- ACL filtering (ACLFILTERREGEX, ACLFILTERSEQ)
"""

from __future__ import annotations

import re
from enum import IntEnum
from typing import Pattern


class FilterMode(IntEnum):
    """Filter mode levels matching original RANCID behavior."""
    NO = 0      # No filtering
    YES = 1     # Standard filtering
    ALL = 2     # Aggressive filtering


# Common password/secret patterns across vendors
PASSWORD_PATTERNS: list[tuple[Pattern, str]] = [
    # Cisco patterns
    (re.compile(r'(password|passwd|secret)\s+\d+\s+\S+', re.I),
     r'\1 <removed>'),
    (re.compile(r'(password|passwd|secret)\s+\S+', re.I),
     r'\1 <removed>'),
    (re.compile(r'(enable\s+secret)\s+\d+\s+\S+', re.I),
     r'\1 <removed>'),
    (re.compile(r'(username\s+\S+\s+password)\s+\d+\s+\S+', re.I),
     r'\1 <removed>'),
    (re.compile(r'(username\s+\S+\s+secret)\s+\d+\s+\S+', re.I),
     r'\1 <removed>'),
    (re.compile(r'(ip\s+ftp\s+password)\s+\d+\s+\S+', re.I),
     r'\1 <removed>'),
    (re.compile(r'(ip\s+ospf\s+authentication-key)\s+\S+', re.I),
     r'\1 <removed>'),
    (re.compile(r'(ip\s+ospf\s+message-digest-key\s+\d+\s+md5)\s+\S+', re.I),
     r'\1 <removed>'),
    (re.compile(r'(standby\s+\d+\s+authentication)\s+\S+', re.I),
     r'\1 <removed>'),
    (re.compile(r'(l2tp\s+tunnel\s+password)\s+\S+', re.I),
     r'\1 <removed>'),
    (re.compile(r'(digest\s+secret)\s+\d+\s+\S+', re.I),
     r'\1 <removed>'),
    (re.compile(r'(ppp\s+.*\s+password)\s+\d+\s+\S+', re.I),
     r'\1 <removed>'),
    (re.compile(r'(pre-shared-key)\s+(address|hostname)\s+\S+\s+(key)\s+\S+', re.I),
     r'\1 \2 <removed> \3 <removed>'),
    (re.compile(r'(ntp\s+authentication-key\s+\d+\s+md5)\s+\S+', re.I),
     r'\1 <removed>'),
    (re.compile(r'(key\s+\d+)\s+\S+', re.I),
     r'\1 <removed>'),
    (re.compile(r'(syscon\s+address\s+\S+)\s+\S+', re.I),
     r'\1 <removed>'),
    (re.compile(r'(snmp-server\s+usm-user.*\s+auth\s+\S+)\s+\S+', re.I),
     r'\1 <removed>'),

    # Juniper patterns
    (re.compile(r'(encrypted-password)\s+"[^"]+";', re.I),
     r'\1 "<removed>";'),
    (re.compile(r'(secret)\s+"\$[^"]+";', re.I),
     r'\1 "<removed>";'),
    (re.compile(r'(authentication-key)\s+"[^"]+";', re.I),
     r'\1 "<removed>";'),
    (re.compile(r'(community)\s+"[^"]+";', re.I),
     r'\1 "<removed>";'),

    # Generic patterns
    (re.compile(r'(key-string)\s+\S+', re.I),
     r'\1 <removed>'),
    (re.compile(r'(md5)\s+\S+', re.I),
     r'\1 <removed>'),
]

# Aggressive password patterns (FILTER_PWDS=ALL)
PASSWORD_PATTERNS_ALL: list[tuple[Pattern, str]] = [
    (re.compile(r'(certificate)\s+"[^"]+"', re.I),
     r'\1 "<removed>"'),
    (re.compile(r'(key-hash\s+sha256)\s+\S+', re.I),
     r'\1 <removed>'),
]

# SNMP community string patterns
COMMUNITY_PATTERNS: list[tuple[Pattern, str]] = [
    (re.compile(r'(snmp-server\s+community)\s+(\S+)', re.I),
     r'\1 <removed>'),
    (re.compile(r'(community)\s+(\S+)(\s+(ro|rw))?', re.I),
     r'\1 <removed>\3'),
    (re.compile(r'(trap-group\s+\S+\s+.*community)\s+"?[^"\s]+"?', re.I),
     r'\1 "<removed>"'),
]

# Oscillating data patterns (timestamps, counters, etc.)
OSCILLATING_PATTERNS: list[tuple[Pattern, str]] = [
    # Timestamps
    (re.compile(r'\b\d{2}:\d{2}:\d{2}\b'),
     '<time>'),
    (re.compile(r'\b\d{4}-\d{2}-\d{2}\b'),
     '<date>'),
    (re.compile(r'\b\d{2}/\d{2}/\d{4}\b'),
     '<date>'),

    # Uptimes
    (re.compile(r'uptime\s+is\s+.*$', re.I | re.M),
     'uptime is <uptime>'),

    # Last config change
    (re.compile(r'Last\s+configuration\s+change\s+at\s+.*$', re.I | re.M),
     'Last configuration change at <timestamp>'),
    (re.compile(r'NVRAM\s+config\s+last\s+updated\s+at\s+.*$', re.I | re.M),
     'NVRAM config last updated at <timestamp>'),

    # Counters
    (re.compile(r'(\d+)\s+packets\s+(input|output)', re.I),
     '<count> packets \\2'),
    (re.compile(r'(\d+)\s+bytes', re.I),
     '<count> bytes'),
]


def filter_passwords(
    line: str,
    mode: FilterMode = FilterMode.YES,
) -> str:
    """
    Filter passwords and secrets from a configuration line.

    Args:
        line: Configuration line to filter
        mode: Filter mode (NO, YES, ALL)

    Returns:
        Filtered line with passwords replaced
    """
    if mode == FilterMode.NO:
        return line

    result = line

    # Apply standard patterns
    for pattern, replacement in PASSWORD_PATTERNS:
        result = pattern.sub(replacement, result)

    # Apply aggressive patterns if ALL mode
    if mode == FilterMode.ALL:
        for pattern, replacement in PASSWORD_PATTERNS_ALL:
            result = pattern.sub(replacement, result)

    return result


def filter_community_strings(
    line: str,
    enabled: bool = True,
) -> str:
    """
    Filter SNMP community strings from a configuration line.

    Args:
        line: Configuration line to filter
        enabled: Whether filtering is enabled

    Returns:
        Filtered line with community strings replaced
    """
    if not enabled:
        return line

    result = line
    for pattern, replacement in COMMUNITY_PATTERNS:
        result = pattern.sub(replacement, result)

    return result


def filter_oscillating_data(
    line: str,
    mode: FilterMode = FilterMode.YES,
) -> str:
    """
    Filter oscillating data (timestamps, counters) from a configuration line.

    This helps reduce noise in diffs by removing data that changes frequently
    but isn't significant to the configuration.

    Args:
        line: Configuration line to filter
        mode: Filter mode (NO, YES, ALL)

    Returns:
        Filtered line with oscillating data replaced
    """
    if mode == FilterMode.NO:
        return line

    result = line
    for pattern, replacement in OSCILLATING_PATTERNS:
        result = pattern.sub(replacement, result)

    return result


def should_filter_acl(
    acl_name: str,
    filter_regex: str | None = None,
) -> bool:
    """
    Check if an ACL should be filtered based on its name.

    Args:
        acl_name: Name of the ACL
        filter_regex: Semi-colon separated list of regexes to match

    Returns:
        True if the ACL should be filtered
    """
    if not filter_regex:
        return False

    for regex in filter_regex.split(";"):
        regex = regex.strip()
        if regex and re.search(regex, acl_name):
            return True

    return False


def filter_acl_sequences(
    line: str,
    enabled: bool = True,
) -> str:
    """
    Filter ACL sequence numbers from a configuration line.

    This removes auto-generated sequence numbers from ACL entries
    to reduce diff noise.

    Args:
        line: Configuration line to filter
        enabled: Whether filtering is enabled

    Returns:
        Filtered line with sequence numbers removed
    """
    if not enabled:
        return line

    # Remove leading sequence numbers from ACL entries
    # Pattern: "10 permit ip any any" -> "permit ip any any"
    result = re.sub(r'^\s*(\d+)\s+(permit|deny)', r'\2', line)

    return result


class OutputFilter:
    """
    Combined output filter that applies all filtering rules.

    This class provides a convenient way to configure and apply
    all output filters in a single pass.
    """

    def __init__(
        self,
        filter_pwds: FilterMode = FilterMode.YES,
        filter_commstr: bool = False,
        filter_osc: FilterMode = FilterMode.YES,
        acl_filter_seq: bool = True,
        acl_filter_regex: str | None = None,
    ):
        """
        Initialize the output filter.

        Args:
            filter_pwds: Password filtering mode
            filter_commstr: Whether to filter community strings
            filter_osc: Oscillating data filtering mode
            acl_filter_seq: Whether to filter ACL sequence numbers
            acl_filter_regex: Regex for ACL name filtering
        """
        self.filter_pwds = filter_pwds
        self.filter_commstr = filter_commstr
        self.filter_osc = filter_osc
        self.acl_filter_seq = acl_filter_seq
        self.acl_filter_regex = acl_filter_regex

    def filter(self, line: str) -> str:
        """
        Apply all configured filters to a line.

        Args:
            line: Configuration line to filter

        Returns:
            Filtered line
        """
        result = line

        result = filter_passwords(result, self.filter_pwds)
        result = filter_community_strings(result, self.filter_commstr)
        result = filter_oscillating_data(result, self.filter_osc)

        return result

    @classmethod
    def from_env(cls) -> "OutputFilter":
        """
        Create an OutputFilter from environment variables.

        This matches the original RANCID behavior of reading
        FILTER_PWDS, NOCOMMSTR, FILTER_OSC, etc. from environment.

        Returns:
            Configured OutputFilter instance
        """
        import os

        # Parse FILTER_PWDS
        filter_pwds_str = os.environ.get("FILTER_PWDS", "YES").upper()
        if filter_pwds_str == "NO":
            filter_pwds = FilterMode.NO
        elif filter_pwds_str == "ALL":
            filter_pwds = FilterMode.ALL
        else:
            filter_pwds = FilterMode.YES

        # Parse NOCOMMSTR
        filter_commstr = os.environ.get("NOCOMMSTR", "").upper() == "YES"

        # Parse FILTER_OSC
        filter_osc_str = os.environ.get("FILTER_OSC", "YES").upper()
        if filter_osc_str == "NO":
            filter_osc = FilterMode.NO
        elif filter_osc_str == "ALL":
            filter_osc = FilterMode.ALL
        else:
            filter_osc = FilterMode.YES

        # Parse ACL options
        acl_filter_seq = os.environ.get("ACLFILTERSEQ", "YES").upper() != "NO"
        acl_filter_regex = os.environ.get("ACLFILTERREGEX")

        return cls(
            filter_pwds=filter_pwds,
            filter_commstr=filter_commstr,
            filter_osc=filter_osc,
            acl_filter_seq=acl_filter_seq,
            acl_filter_regex=acl_filter_regex,
        )
