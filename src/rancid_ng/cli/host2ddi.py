"""
host2ddi.py - Host Configuration Lookup for DDI Systems

Retrieves host/network configuration from DDI (DNS/DHCP/IPAM) systems
including Infoblox and BlueCat. Supports multiple connection methods:
- HTTP/HTTPS API
- SSH
- Telnet

Usage:
    host2ddi 10.0.0.50
    host2ddi myhost.example.com --device-type infoblox --method api
    host2ddi 192.168.1.0/24 --device-type bluecat --live
    host2ddi --host router1 --method ssh --device-type cisco
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request
import ssl
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Literal
from base64 import b64encode

import click

from rancid_ng.config.cloginrc import CloginrcParser, load_cloginrc
from rancid_ng.login.session import LoginSession


ConnectionMethod = Literal["api", "http", "ssh", "telnet"]


@dataclass
class HostRecord:
    """DNS host record."""
    hostname: str
    ip_address: str
    mac_address: str = ""
    aliases: list[str] = field(default_factory=list)
    ttl: int = 0
    zone: str = ""
    view: str = ""
    comment: str = ""


@dataclass
class DHCPLease:
    """DHCP lease information."""
    ip_address: str
    mac_address: str = ""
    hostname: str = ""
    lease_start: str = ""
    lease_end: str = ""
    state: str = ""
    network: str = ""


@dataclass
class NetworkInfo:
    """Network/subnet information."""
    network: str
    netmask: str = ""
    cidr: int = 0
    gateway: str = ""
    dns_servers: list[str] = field(default_factory=list)
    dhcp_enabled: bool = False
    vlan: str = ""
    comment: str = ""


@dataclass
class DDILookupResult:
    """Result from DDI lookup."""
    query: str
    query_type: str = ""  # host, ip, network
    source: str = ""  # infoblox, bluecat, config
    method: str = ""  # api, ssh, telnet
    host_records: list[HostRecord] = field(default_factory=list)
    dhcp_leases: list[DHCPLease] = field(default_factory=list)
    networks: list[NetworkInfo] = field(default_factory=list)
    raw_data: dict = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON."""
        return {
            "query": self.query,
            "query_type": self.query_type,
            "source": self.source,
            "method": self.method,
            "host_records": [asdict(h) for h in self.host_records],
            "dhcp_leases": [asdict(l) for l in self.dhcp_leases],
            "networks": [asdict(n) for n in self.networks],
            "error": self.error,
        }


class DDIClient:
    """Base DDI client interface."""

    def __init__(
        self,
        host: str,
        username: str | None = None,
        password: str | None = None,
        verify_ssl: bool = True,
    ):
        self.host = host
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl

    def lookup_host(self, hostname: str) -> DDILookupResult:
        """Lookup a host by name."""
        raise NotImplementedError

    def lookup_ip(self, ip_address: str) -> DDILookupResult:
        """Lookup by IP address."""
        raise NotImplementedError

    def lookup_network(self, network: str) -> DDILookupResult:
        """Lookup network information."""
        raise NotImplementedError

    def get_dhcp_lease(self, identifier: str) -> DDILookupResult:
        """Get DHCP lease by IP or MAC."""
        raise NotImplementedError


class InfobloxAPIClient(DDIClient):
    """Infoblox WAPI client."""

    def __init__(
        self,
        host: str,
        username: str | None = None,
        password: str | None = None,
        verify_ssl: bool = True,
        api_version: str = "v2.12",
    ):
        super().__init__(host, username, password, verify_ssl)
        self.api_version = api_version
        self.base_url = f"https://{host}/wapi/{api_version}"

    def _request(self, endpoint: str, params: dict | None = None) -> dict:
        """Make API request."""
        url = f"{self.base_url}/{endpoint}"
        if params:
            url += "?" + urllib.parse.urlencode(params)

        request = urllib.request.Request(url)

        # Add auth header
        if self.username and self.password:
            credentials = b64encode(
                f"{self.username}:{self.password}".encode()
            ).decode()
            request.add_header("Authorization", f"Basic {credentials}")

        # SSL context
        context = ssl.create_default_context()
        if not self.verify_ssl:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        try:
            with urllib.request.urlopen(request, context=context) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            return {"error": str(e)}

    def lookup_host(self, hostname: str) -> DDILookupResult:
        """Lookup host record."""
        result = DDILookupResult(
            query=hostname,
            query_type="host",
            source="infoblox",
            method="api"
        )

        # Search for host record
        data = self._request("record:host", {
            "name~": hostname,
            "_return_fields": "name,ipv4addrs,aliases,comment,zone"
        })

        if isinstance(data, list):
            for record in data:
                host = HostRecord(
                    hostname=record.get("name", ""),
                    ip_address=record.get("ipv4addrs", [{}])[0].get("ipv4addr", ""),
                    aliases=record.get("aliases", []),
                    zone=record.get("zone", ""),
                    comment=record.get("comment", ""),
                )
                result.host_records.append(host)

        # Also search A records
        data = self._request("record:a", {
            "name~": hostname,
            "_return_fields": "name,ipv4addr,ttl,zone,comment"
        })

        if isinstance(data, list):
            for record in data:
                host = HostRecord(
                    hostname=record.get("name", ""),
                    ip_address=record.get("ipv4addr", ""),
                    ttl=record.get("ttl", 0),
                    zone=record.get("zone", ""),
                    comment=record.get("comment", ""),
                )
                # Avoid duplicates
                if not any(h.hostname == host.hostname and h.ip_address == host.ip_address
                          for h in result.host_records):
                    result.host_records.append(host)

        return result

    def lookup_ip(self, ip_address: str) -> DDILookupResult:
        """Lookup by IP address."""
        result = DDILookupResult(
            query=ip_address,
            query_type="ip",
            source="infoblox",
            method="api"
        )

        # Search for host records with this IP
        data = self._request("ipv4address", {
            "ip_address": ip_address,
            "_return_fields": "ip_address,mac_address,names,network,status,types"
        })

        if isinstance(data, list) and data:
            ip_data = data[0]
            names = ip_data.get("names", [])
            if names:
                for name in names:
                    host = HostRecord(
                        hostname=name,
                        ip_address=ip_address,
                        mac_address=ip_data.get("mac_address", ""),
                    )
                    result.host_records.append(host)

            # Check for DHCP lease
            if "DHCP" in ip_data.get("types", []):
                lease = DHCPLease(
                    ip_address=ip_address,
                    mac_address=ip_data.get("mac_address", ""),
                    hostname=names[0] if names else "",
                    network=ip_data.get("network", ""),
                    state=ip_data.get("status", ""),
                )
                result.dhcp_leases.append(lease)

        return result

    def lookup_network(self, network: str) -> DDILookupResult:
        """Lookup network information."""
        result = DDILookupResult(
            query=network,
            query_type="network",
            source="infoblox",
            method="api"
        )

        data = self._request("network", {
            "network": network,
            "_return_fields": "network,netmask,comment,options"
        })

        if isinstance(data, list):
            for net in data:
                network_info = NetworkInfo(
                    network=net.get("network", ""),
                    netmask=net.get("netmask", ""),
                    comment=net.get("comment", ""),
                )
                result.networks.append(network_info)

        return result

    def get_dhcp_lease(self, identifier: str) -> DDILookupResult:
        """Get DHCP lease."""
        result = DDILookupResult(
            query=identifier,
            query_type="dhcp",
            source="infoblox",
            method="api"
        )

        # Try as IP first
        search_field = "address" if "." in identifier else "hardware"
        data = self._request("lease", {
            search_field: identifier,
            "_return_fields": "address,hardware,client_hostname,starts,ends,binding_state,network"
        })

        if isinstance(data, list):
            for lease_data in data:
                lease = DHCPLease(
                    ip_address=lease_data.get("address", ""),
                    mac_address=lease_data.get("hardware", ""),
                    hostname=lease_data.get("client_hostname", ""),
                    lease_start=lease_data.get("starts", ""),
                    lease_end=lease_data.get("ends", ""),
                    state=lease_data.get("binding_state", ""),
                    network=lease_data.get("network", ""),
                )
                result.dhcp_leases.append(lease)

        return result


class BlueCatAPIClient(DDIClient):
    """BlueCat Address Manager API client."""

    def __init__(
        self,
        host: str,
        username: str | None = None,
        password: str | None = None,
        verify_ssl: bool = True,
    ):
        super().__init__(host, username, password, verify_ssl)
        self.base_url = f"https://{host}/Services/REST/v1"
        self.token: str | None = None

    def _login(self) -> bool:
        """Authenticate and get token."""
        url = f"{self.base_url}/login"
        params = {
            "username": self.username,
            "password": self.password
        }
        url += "?" + urllib.parse.urlencode(params)

        request = urllib.request.Request(url)
        context = ssl.create_default_context()
        if not self.verify_ssl:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        try:
            with urllib.request.urlopen(request, context=context) as response:
                result = response.read().decode()
                # Token is returned in format: "BAMAuthToken: tokenstring"
                if "BAMAuthToken:" in result:
                    self.token = result.split("BAMAuthToken:")[1].strip()
                    return True
        except Exception:
            pass
        return False

    def _request(self, endpoint: str, params: dict | None = None) -> Any:
        """Make API request."""
        if not self.token:
            self._login()

        url = f"{self.base_url}/{endpoint}"
        if params:
            url += "?" + urllib.parse.urlencode(params)

        request = urllib.request.Request(url)
        if self.token:
            request.add_header("Authorization", f"BAMAuthToken: {self.token}")

        context = ssl.create_default_context()
        if not self.verify_ssl:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        try:
            with urllib.request.urlopen(request, context=context) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            return {"error": str(e)}

    def lookup_host(self, hostname: str) -> DDILookupResult:
        """Lookup host record."""
        result = DDILookupResult(
            query=hostname,
            query_type="host",
            source="bluecat",
            method="api"
        )

        # Search for host records
        data = self._request("searchByObjectTypes", {
            "keyword": hostname,
            "types": "HostRecord",
            "start": 0,
            "count": 100
        })

        if isinstance(data, list):
            for record in data:
                props = self._parse_properties(record.get("properties", ""))
                host = HostRecord(
                    hostname=record.get("name", ""),
                    ip_address=props.get("addresses", ""),
                    comment=props.get("comments", ""),
                )
                result.host_records.append(host)

        return result

    def lookup_ip(self, ip_address: str) -> DDILookupResult:
        """Lookup by IP address."""
        result = DDILookupResult(
            query=ip_address,
            query_type="ip",
            source="bluecat",
            method="api"
        )

        data = self._request("getIP4Address", {
            "address": ip_address
        })

        if isinstance(data, dict) and "id" in data:
            props = self._parse_properties(data.get("properties", ""))
            host = HostRecord(
                hostname=props.get("name", ""),
                ip_address=ip_address,
                mac_address=props.get("macAddress", ""),
            )
            result.host_records.append(host)

            if props.get("state") == "DHCP_ALLOCATED":
                lease = DHCPLease(
                    ip_address=ip_address,
                    mac_address=props.get("macAddress", ""),
                    hostname=props.get("name", ""),
                    lease_start=props.get("leaseTime", ""),
                    lease_end=props.get("expiryTime", ""),
                    state=props.get("state", ""),
                )
                result.dhcp_leases.append(lease)

        return result

    def lookup_network(self, network: str) -> DDILookupResult:
        """Lookup network information."""
        result = DDILookupResult(
            query=network,
            query_type="network",
            source="bluecat",
            method="api"
        )

        data = self._request("searchByObjectTypes", {
            "keyword": network,
            "types": "IP4Network",
            "start": 0,
            "count": 100
        })

        if isinstance(data, list):
            for net in data:
                props = self._parse_properties(net.get("properties", ""))
                network_info = NetworkInfo(
                    network=props.get("CIDR", ""),
                    gateway=props.get("gateway", ""),
                    comment=net.get("name", ""),
                )
                result.networks.append(network_info)

        return result

    def get_dhcp_lease(self, identifier: str) -> DDILookupResult:
        """Get DHCP lease - uses IP lookup."""
        return self.lookup_ip(identifier)

    @staticmethod
    def _parse_properties(props_str: str) -> dict:
        """Parse BlueCat properties string (key=value|key=value)."""
        result = {}
        if props_str:
            for pair in props_str.split("|"):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    result[key] = value
        return result


class SSHDDIClient(DDIClient):
    """DDI client using SSH connection."""

    def __init__(
        self,
        host: str,
        username: str | None = None,
        password: str | None = None,
        device_type: str = "infoblox",
    ):
        super().__init__(host, username, password)
        self.device_type = device_type
        self.session: LoginSession | None = None

    def _connect(self) -> bool:
        """Establish SSH connection."""
        if self.session and self.session.connected:
            return True

        self.session = LoginSession(
            hostname=self.host,
            username=self.username,
            password=self.password,
            device_type=self.device_type,
        )
        return self.session.connect()

    def _send_command(self, command: str) -> str:
        """Send command via SSH."""
        if not self._connect():
            return ""
        return self.session.send_command(command)

    def lookup_host(self, hostname: str) -> DDILookupResult:
        """Lookup host via SSH."""
        result = DDILookupResult(
            query=hostname,
            query_type="host",
            source=self.device_type,
            method="ssh"
        )

        if self.device_type == "infoblox":
            output = self._send_command(f"show dns a-record {hostname}")
            # Parse Infoblox CLI output
            for match in re.finditer(
                r'(\S+)\s+IN\s+A\s+(\d+\.\d+\.\d+\.\d+)',
                output
            ):
                host = HostRecord(
                    hostname=match.group(1),
                    ip_address=match.group(2),
                )
                result.host_records.append(host)

        elif self.device_type == "bluecat":
            output = self._send_command(f"show host {hostname}")
            # Parse BlueCat CLI output
            for line in output.splitlines():
                match = re.search(r'(\S+)\s+(\d+\.\d+\.\d+\.\d+)', line)
                if match:
                    host = HostRecord(
                        hostname=match.group(1),
                        ip_address=match.group(2),
                    )
                    result.host_records.append(host)

        return result

    def lookup_ip(self, ip_address: str) -> DDILookupResult:
        """Lookup IP via SSH."""
        result = DDILookupResult(
            query=ip_address,
            query_type="ip",
            source=self.device_type,
            method="ssh"
        )

        if self.device_type == "infoblox":
            output = self._send_command(f"show ipam address {ip_address}")
            result.raw_data["output"] = output

        elif self.device_type == "bluecat":
            output = self._send_command(f"show ip {ip_address}")
            result.raw_data["output"] = output

        return result

    def lookup_network(self, network: str) -> DDILookupResult:
        """Lookup network via SSH."""
        result = DDILookupResult(
            query=network,
            query_type="network",
            source=self.device_type,
            method="ssh"
        )

        if self.device_type == "infoblox":
            output = self._send_command(f"show network {network}")
        elif self.device_type == "bluecat":
            output = self._send_command(f"show network {network}")
        else:
            output = ""

        result.raw_data["output"] = output
        return result

    def get_dhcp_lease(self, identifier: str) -> DDILookupResult:
        """Get DHCP lease via SSH."""
        result = DDILookupResult(
            query=identifier,
            query_type="dhcp",
            source=self.device_type,
            method="ssh"
        )

        if self.device_type == "infoblox":
            output = self._send_command(f"show dhcp lease {identifier}")
        elif self.device_type == "bluecat":
            output = self._send_command(f"show dhcp lease {identifier}")
        else:
            output = ""

        result.raw_data["output"] = output
        return result


def get_client(
    host: str,
    device_type: str,
    method: ConnectionMethod,
    username: str | None = None,
    password: str | None = None,
    verify_ssl: bool = True,
) -> DDIClient:
    """Get appropriate DDI client based on device type and method."""
    if method in ("api", "http"):
        if device_type == "infoblox":
            return InfobloxAPIClient(host, username, password, verify_ssl)
        elif device_type == "bluecat":
            return BlueCatAPIClient(host, username, password, verify_ssl)
        else:
            raise ValueError(f"API method not supported for device type: {device_type}")

    elif method == "ssh":
        return SSHDDIClient(host, username, password, device_type)

    elif method == "telnet":
        # Telnet uses same client as SSH but different transport
        return SSHDDIClient(host, username, password, device_type)

    else:
        raise ValueError(f"Unknown method: {method}")


@click.command()
@click.argument("query")
@click.option(
    "-t", "--device-type",
    default="infoblox",
    help="DDI device type (infoblox, bluecat)"
)
@click.option(
    "--ddi-host",
    envvar="DDI_HOST",
    help="DDI server hostname/IP (or set DDI_HOST env var)"
)
@click.option(
    "-m", "--method",
    type=click.Choice(["api", "http", "ssh", "telnet"]),
    default="api",
    help="Connection method"
)
@click.option(
    "--live",
    is_flag=True,
    help="Query live device instead of cached configs"
)
@click.option(
    "-u", "--user",
    envvar="DDI_USER",
    help="Username (or set DDI_USER env var)"
)
@click.option(
    "-p", "--password",
    envvar="DDI_PASSWORD",
    help="Password (or set DDI_PASSWORD env var)"
)
@click.option(
    "--config-dir",
    type=click.Path(exists=True),
    help="Directory containing cached DDI configs"
)
@click.option(
    "--no-verify-ssl",
    is_flag=True,
    help="Disable SSL certificate verification"
)
@click.option(
    "--type",
    "query_type",
    type=click.Choice(["auto", "host", "ip", "network", "dhcp"]),
    default="auto",
    help="Query type (auto-detected by default)"
)
@click.option(
    "-o", "--output",
    type=click.Path(),
    help="Output file (default: stdout)"
)
@click.option(
    "--pretty/--compact",
    default=True,
    help="Pretty-print JSON output"
)
@click.option(
    "-v", "--verbose",
    is_flag=True,
    help="Verbose output"
)
def main(
    query: str,
    device_type: str,
    ddi_host: str | None,
    method: ConnectionMethod,
    live: bool,
    user: str | None,
    password: str | None,
    config_dir: str | None,
    no_verify_ssl: bool,
    query_type: str,
    output: str | None,
    pretty: bool,
    verbose: bool,
):
    """
    Lookup host/network configuration from DDI systems.

    QUERY can be a hostname, IP address, network (CIDR), or MAC address.

    Examples:

        # Lookup host by name via API
        host2ddi myhost.example.com --ddi-host infoblox.local

        # Lookup IP address via SSH
        host2ddi 10.0.0.50 --device-type bluecat --method ssh

        # Lookup network
        host2ddi 192.168.1.0/24 --type network

        # Query live device (not cached)
        host2ddi router1 --live --device-type infoblox

        # Use environment variables
        export DDI_HOST=infoblox.example.com
        export DDI_USER=admin
        export DDI_PASSWORD=secret
        host2ddi myhost.example.com
    """
    # Auto-detect query type
    if query_type == "auto":
        query_type = detect_query_type(query)

    if verbose:
        click.echo(f"Query: {query} (type: {query_type})", err=True)
        click.echo(f"Method: {method}, Device: {device_type}", err=True)

    result: DDILookupResult

    if live or method in ("api", "http", "ssh", "telnet"):
        # Live query to DDI system
        if not ddi_host:
            click.echo("Error: --ddi-host is required for live queries", err=True)
            sys.exit(1)

        # Load credentials from cloginrc if not provided
        if not user or not password:
            cloginrc = load_cloginrc()
            auth = cloginrc.get_auth(ddi_host)
            if not user:
                user = auth.user
            if not password:
                password = auth.get_password()

        try:
            client = get_client(
                ddi_host, device_type, method,
                username=user,
                password=password,
                verify_ssl=not no_verify_ssl,
            )

            if query_type == "host":
                result = client.lookup_host(query)
            elif query_type == "ip":
                result = client.lookup_ip(query)
            elif query_type == "network":
                result = client.lookup_network(query)
            elif query_type == "dhcp":
                result = client.get_dhcp_lease(query)
            else:
                result = client.lookup_host(query)

        except Exception as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)

    else:
        # Lookup from cached configs
        result = lookup_from_configs(query, query_type, config_dir)

    # Output result
    json_output = json.dumps(
        result.to_dict(),
        indent=2 if pretty else None,
        default=str
    )

    if output:
        Path(output).write_text(json_output)
        if verbose:
            click.echo(f"Output written to {output}", err=True)
    else:
        click.echo(json_output)


def detect_query_type(query: str) -> str:
    """Auto-detect query type from query string."""
    # IP address
    if re.match(r'^\d+\.\d+\.\d+\.\d+$', query):
        return "ip"

    # Network CIDR
    if re.match(r'^\d+\.\d+\.\d+\.\d+/\d+$', query):
        return "network"

    # MAC address
    if re.match(r'^([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}$', query):
        return "dhcp"

    # Default to hostname
    return "host"


def lookup_from_configs(
    query: str,
    query_type: str,
    config_dir: str | None
) -> DDILookupResult:
    """Lookup from cached configuration files."""
    result = DDILookupResult(
        query=query,
        query_type=query_type,
        source="config",
        method="file"
    )

    if not config_dir:
        # Try default locations
        config_dir = os.environ.get("RANCID_BASEDIR", "/var/rancid")

    config_path = Path(config_dir)
    if not config_path.exists():
        result.error = f"Config directory not found: {config_dir}"
        return result

    # Search through config files for matching data
    # This is a simplified implementation - production would need more sophisticated parsing
    for config_file in config_path.rglob("*.config"):
        try:
            content = config_file.read_text()

            if query_type == "host":
                # Look for hostname in configs
                for match in re.finditer(
                    rf'{re.escape(query)}\s+.*?(\d+\.\d+\.\d+\.\d+)',
                    content, re.I
                ):
                    host = HostRecord(
                        hostname=query,
                        ip_address=match.group(1),
                    )
                    result.host_records.append(host)

            elif query_type == "ip":
                # Look for IP in configs
                if query in content:
                    # Extract hostname associated with IP
                    for match in re.finditer(
                        rf'(\S+)\s+.*?{re.escape(query)}',
                        content
                    ):
                        host = HostRecord(
                            hostname=match.group(1),
                            ip_address=query,
                        )
                        result.host_records.append(host)

        except Exception:
            continue

    return result


if __name__ == "__main__":
    main()
