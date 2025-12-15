"""
extract-ddi.py - DDI Data Extraction Script for RANCID-NG

Connects to any supported device and extracts:
- Hostname
- DHCP settings
- DNS settings
- Route table

Outputs data in JSON format for DDI (DNS/DHCP/IPAM) integration.

Usage:
    extract-ddi router1.example.com --device-type cisco
    extract-ddi switch1.example.com -t juniper --output routes.json
    extract-ddi --router-db /path/to/router.db --group production
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import click

from rancid_ng.config.cloginrc import CloginrcParser, load_cloginrc
from rancid_ng.config.types import DeviceTypeRegistry, load_default_types
from rancid_ng.login.session import LoginSession


@dataclass
class DHCPPool:
    """DHCP pool configuration."""
    name: str
    network: str = ""
    netmask: str = ""
    default_router: str = ""
    dns_servers: list[str] = field(default_factory=list)
    lease_time: str = ""
    range_start: str = ""
    range_end: str = ""
    options: dict[str, str] = field(default_factory=dict)


@dataclass
class DNSConfig:
    """DNS configuration."""
    domain_name: str = ""
    domain_search: list[str] = field(default_factory=list)
    name_servers: list[str] = field(default_factory=list)
    dns_views: list[str] = field(default_factory=list)
    forwarders: list[str] = field(default_factory=list)


@dataclass
class Route:
    """Route table entry."""
    network: str
    netmask: str = ""
    prefix_length: int = 0
    next_hop: str = ""
    interface: str = ""
    protocol: str = "static"
    metric: int = 0
    ad: int = 1  # Administrative distance
    vrf: str = ""


@dataclass
class DDIData:
    """Complete DDI data extracted from device."""
    hostname: str
    device_type: str
    domain_name: str = ""
    dhcp_pools: list[DHCPPool] = field(default_factory=list)
    dns_config: DNSConfig = field(default_factory=DNSConfig)
    routes: list[Route] = field(default_factory=list)
    interfaces: list[dict] = field(default_factory=list)
    vrfs: list[str] = field(default_factory=list)
    raw_sections: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "hostname": self.hostname,
            "device_type": self.device_type,
            "domain_name": self.domain_name,
            "dhcp_pools": [asdict(p) for p in self.dhcp_pools],
            "dns_config": asdict(self.dns_config),
            "routes": [asdict(r) for r in self.routes],
            "interfaces": self.interfaces,
            "vrfs": self.vrfs,
        }


class DDIExtractor:
    """Base DDI data extractor."""

    def __init__(self, session: LoginSession, device_type: str):
        self.session = session
        self.device_type = device_type
        self.data = DDIData(hostname="", device_type=device_type)

    def extract(self) -> DDIData:
        """Extract all DDI data from device."""
        self.extract_hostname()
        self.extract_dhcp()
        self.extract_dns()
        self.extract_routes()
        return self.data

    def extract_hostname(self) -> None:
        """Extract device hostname."""
        raise NotImplementedError

    def extract_dhcp(self) -> None:
        """Extract DHCP configuration."""
        pass  # Not all devices have DHCP

    def extract_dns(self) -> None:
        """Extract DNS configuration."""
        raise NotImplementedError

    def extract_routes(self) -> None:
        """Extract route table."""
        raise NotImplementedError

    def send_command(self, command: str) -> str:
        """Send command and return output."""
        return self.session.send_command(command)


class CiscoExtractor(DDIExtractor):
    """DDI extractor for Cisco IOS/IOS-XE devices."""

    def extract_hostname(self) -> None:
        """Extract hostname from running config."""
        output = self.send_command("show running-config | include hostname")
        match = re.search(r'hostname\s+(\S+)', output)
        if match:
            self.data.hostname = match.group(1)

    def extract_dns(self) -> None:
        """Extract DNS configuration."""
        output = self.send_command("show running-config | section ip domain")
        dns = self.data.dns_config

        # Domain name
        match = re.search(r'ip domain[- ]name\s+(\S+)', output)
        if match:
            dns.domain_name = match.group(1)
            self.data.domain_name = match.group(1)

        # Domain search list
        for match in re.finditer(r'ip domain[- ]list\s+(\S+)', output):
            dns.domain_search.append(match.group(1))

        # Name servers
        output = self.send_command("show running-config | include name-server")
        for match in re.finditer(r'ip name-server\s+(\S+)', output):
            dns.name_servers.append(match.group(1))

    def extract_dhcp(self) -> None:
        """Extract DHCP pool configuration."""
        output = self.send_command("show running-config | section ip dhcp pool")

        current_pool = None
        for line in output.splitlines():
            line = line.strip()

            # New pool definition
            match = re.match(r'ip dhcp pool\s+(\S+)', line)
            if match:
                if current_pool:
                    self.data.dhcp_pools.append(current_pool)
                current_pool = DHCPPool(name=match.group(1))
                continue

            if current_pool:
                # Network
                match = re.match(r'network\s+(\S+)\s+(\S+)', line)
                if match:
                    current_pool.network = match.group(1)
                    current_pool.netmask = match.group(2)

                # Default router
                match = re.match(r'default-router\s+(\S+)', line)
                if match:
                    current_pool.default_router = match.group(1)

                # DNS server
                match = re.match(r'dns-server\s+(.+)', line)
                if match:
                    current_pool.dns_servers = match.group(1).split()

                # Lease
                match = re.match(r'lease\s+(.+)', line)
                if match:
                    current_pool.lease_time = match.group(1)

        if current_pool:
            self.data.dhcp_pools.append(current_pool)

    def extract_routes(self) -> None:
        """Extract route table."""
        output = self.send_command("show ip route")

        for line in output.splitlines():
            # Static routes: S    10.0.0.0/8 [1/0] via 192.168.1.1
            match = re.match(
                r'\s*([SCODBRELNIM*>i]+)\s+'
                r'(\d+\.\d+\.\d+\.\d+)/(\d+)'
                r'(?:\s+\[(\d+)/(\d+)\])?'
                r'(?:\s+via\s+(\S+))?'
                r'(?:,\s*(\S+))?',
                line
            )
            if match:
                route = Route(
                    network=match.group(2),
                    prefix_length=int(match.group(3)),
                )
                if match.group(4):
                    route.ad = int(match.group(4))
                if match.group(5):
                    route.metric = int(match.group(5))
                if match.group(6):
                    route.next_hop = match.group(6)
                if match.group(7):
                    route.interface = match.group(7)

                # Determine protocol from code
                code = match.group(1)
                if 'C' in code:
                    route.protocol = "connected"
                elif 'S' in code:
                    route.protocol = "static"
                elif 'O' in code:
                    route.protocol = "ospf"
                elif 'B' in code:
                    route.protocol = "bgp"
                elif 'R' in code:
                    route.protocol = "rip"
                elif 'E' in code:
                    route.protocol = "eigrp"

                self.data.routes.append(route)


class JuniperExtractor(DDIExtractor):
    """DDI extractor for Juniper JunOS devices."""

    def extract_hostname(self) -> None:
        """Extract hostname."""
        output = self.send_command("show configuration system host-name")
        match = re.search(r'host-name\s+(\S+);?', output)
        if match:
            self.data.hostname = match.group(1)

    def extract_dns(self) -> None:
        """Extract DNS configuration."""
        output = self.send_command("show configuration system name-server")
        dns = self.data.dns_config

        for match in re.finditer(r'(\d+\.\d+\.\d+\.\d+)', output):
            dns.name_servers.append(match.group(1))

        # Domain name
        output = self.send_command("show configuration system domain-name")
        match = re.search(r'domain-name\s+(\S+)', output)
        if match:
            dns.domain_name = match.group(1)
            self.data.domain_name = match.group(1)

        # Domain search
        output = self.send_command("show configuration system domain-search")
        for match in re.finditer(r'domain-search\s+"?([^";]+)"?', output):
            dns.domain_search.append(match.group(1))

    def extract_routes(self) -> None:
        """Extract route table."""
        output = self.send_command("show route terse")

        for line in output.splitlines():
            # Format: prefix          next-hop
            match = re.match(
                r'\*?\s*(\d+\.\d+\.\d+\.\d+/\d+)\s+'
                r'(?:\S+\s+)?'
                r'(?:>\s+)?'
                r'(\d+\.\d+\.\d+\.\d+)?',
                line
            )
            if match:
                network, prefix = match.group(1).split('/')
                route = Route(
                    network=network,
                    prefix_length=int(prefix),
                    next_hop=match.group(2) or "",
                )
                self.data.routes.append(route)


class BlueCatExtractor(DDIExtractor):
    """DDI extractor for BlueCat DDI devices."""

    def extract_hostname(self) -> None:
        """Extract hostname."""
        output = self.send_command("show system")
        match = re.search(r'Hostname:\s*(\S+)', output)
        if match:
            self.data.hostname = match.group(1)

    def extract_dns(self) -> None:
        """Extract DNS configuration."""
        output = self.send_command("show dns configuration")
        dns = self.data.dns_config

        for match in re.finditer(r'forwarder\s+(\d+\.\d+\.\d+\.\d+)', output, re.I):
            dns.forwarders.append(match.group(1))

        for match in re.finditer(r'view\s+"([^"]+)"', output):
            dns.dns_views.append(match.group(1))

    def extract_dhcp(self) -> None:
        """Extract DHCP configuration."""
        output = self.send_command("show dhcp configuration")
        # Parse BlueCat DHCP configuration
        self.data.raw_sections['dhcp'] = output

    def extract_routes(self) -> None:
        """Extract routes."""
        output = self.send_command("show network")
        for match in re.finditer(
            r'(\d+\.\d+\.\d+\.\d+)/(\d+)\s+.*gateway\s+(\d+\.\d+\.\d+\.\d+)',
            output, re.I
        ):
            route = Route(
                network=match.group(1),
                prefix_length=int(match.group(2)),
                next_hop=match.group(3),
            )
            self.data.routes.append(route)


class InfobloxExtractor(DDIExtractor):
    """DDI extractor for Infoblox NIOS devices."""

    def extract_hostname(self) -> None:
        """Extract hostname."""
        output = self.send_command("show hostname")
        match = re.search(r'Hostname:\s*(\S+)', output)
        if match:
            self.data.hostname = match.group(1)
        else:
            self.data.hostname = output.strip()

    def extract_dns(self) -> None:
        """Extract DNS configuration."""
        output = self.send_command("show dns configuration")
        dns = self.data.dns_config
        self.data.raw_sections['dns'] = output

        for match in re.finditer(r'forwarder.*?(\d+\.\d+\.\d+\.\d+)', output, re.I):
            dns.forwarders.append(match.group(1))

    def extract_dhcp(self) -> None:
        """Extract DHCP configuration."""
        output = self.send_command("show dhcp configuration")
        self.data.raw_sections['dhcp'] = output

    def extract_routes(self) -> None:
        """Extract routes."""
        output = self.send_command("show network")
        for match in re.finditer(
            r'(\d+\.\d+\.\d+\.\d+)/(\d+)',
            output
        ):
            route = Route(
                network=match.group(1),
                prefix_length=int(match.group(2)),
            )
            self.data.routes.append(route)


class AristaExtractor(CiscoExtractor):
    """DDI extractor for Arista EOS (similar to Cisco IOS)."""
    pass


class PaloAltoExtractor(DDIExtractor):
    """DDI extractor for Palo Alto PAN-OS."""

    def extract_hostname(self) -> None:
        """Extract hostname."""
        output = self.send_command("show system info")
        match = re.search(r'hostname:\s*(\S+)', output)
        if match:
            self.data.hostname = match.group(1)

    def extract_dns(self) -> None:
        """Extract DNS configuration."""
        output = self.send_command("show config running")
        dns = self.data.dns_config

        for match in re.finditer(r'dns-setting.*?primary.*?(\d+\.\d+\.\d+\.\d+)', output, re.S):
            dns.name_servers.append(match.group(1))

    def extract_routes(self) -> None:
        """Extract route table."""
        output = self.send_command("show routing route")

        for line in output.splitlines():
            match = re.match(
                r'\s*(\d+\.\d+\.\d+\.\d+/\d+)\s+\S+\s+\S+\s+(\d+)\s+(\S+)',
                line
            )
            if match:
                network, prefix = match.group(1).split('/')
                route = Route(
                    network=network,
                    prefix_length=int(prefix),
                    metric=int(match.group(2)),
                    next_hop=match.group(3),
                )
                self.data.routes.append(route)


class GenericExtractor(DDIExtractor):
    """Generic DDI extractor for unknown device types."""

    def extract_hostname(self) -> None:
        """Try common hostname commands."""
        commands = [
            "show hostname",
            "show system info",
            "show version",
            "hostname",
        ]
        for cmd in commands:
            try:
                output = self.send_command(cmd)
                # Look for hostname patterns
                match = re.search(r'(?:hostname|host[- ]name):\s*(\S+)', output, re.I)
                if match:
                    self.data.hostname = match.group(1)
                    return
            except Exception:
                continue

    def extract_dns(self) -> None:
        """Try common DNS commands."""
        commands = [
            "show dns",
            "show name-server",
            "show running-config | include name-server",
        ]
        dns = self.data.dns_config
        for cmd in commands:
            try:
                output = self.send_command(cmd)
                for match in re.finditer(r'(\d+\.\d+\.\d+\.\d+)', output):
                    if match.group(1) not in dns.name_servers:
                        dns.name_servers.append(match.group(1))
            except Exception:
                continue

    def extract_routes(self) -> None:
        """Try common route commands."""
        commands = [
            "show ip route",
            "show route",
            "show routing table",
            "netstat -rn",
        ]
        for cmd in commands:
            try:
                output = self.send_command(cmd)
                # Generic route pattern
                for match in re.finditer(
                    r'(\d+\.\d+\.\d+\.\d+)(?:/(\d+))?\s+'
                    r'(?:via\s+)?(\d+\.\d+\.\d+\.\d+)?',
                    output
                ):
                    route = Route(
                        network=match.group(1),
                        prefix_length=int(match.group(2) or 24),
                        next_hop=match.group(3) or "",
                    )
                    self.data.routes.append(route)
                if self.data.routes:
                    return
            except Exception:
                continue


def get_extractor(session: LoginSession, device_type: str) -> DDIExtractor:
    """Get the appropriate extractor for device type."""
    device_type = device_type.lower()

    extractors = {
        "cisco": CiscoExtractor,
        "ios": CiscoExtractor,
        "ios-xe": CiscoExtractor,
        "nxos": CiscoExtractor,
        "juniper": JuniperExtractor,
        "junos": JuniperExtractor,
        "arista": AristaExtractor,
        "eos": AristaExtractor,
        "bluecat": BlueCatExtractor,
        "infoblox": InfobloxExtractor,
        "nios": InfobloxExtractor,
        "paloalto": PaloAltoExtractor,
        "panos": PaloAltoExtractor,
    }

    extractor_class = extractors.get(device_type, GenericExtractor)
    return extractor_class(session, device_type)


@click.command()
@click.argument("hostname", required=False)
@click.option(
    "-t", "--device-type",
    help="Device type (cisco, juniper, arista, bluecat, infoblox, etc.)"
)
@click.option(
    "-o", "--output",
    type=click.Path(),
    help="Output file (default: stdout)"
)
@click.option(
    "--router-db",
    type=click.Path(exists=True),
    help="Path to router.db file"
)
@click.option(
    "--group",
    help="Device group name (requires --router-db)"
)
@click.option(
    "-u", "--user",
    help="Override username"
)
@click.option(
    "-p", "--password",
    help="Override password"
)
@click.option(
    "--enable-password",
    help="Override enable password"
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
    hostname: str | None,
    device_type: str | None,
    output: str | None,
    router_db: str | None,
    group: str | None,
    user: str | None,
    password: str | None,
    enable_password: str | None,
    pretty: bool,
    verbose: bool,
):
    """
    Extract DDI (DNS/DHCP/IPAM) data from network devices.

    Connects to devices and extracts hostname, DHCP configuration,
    DNS settings, and route tables into JSON format.

    Examples:

        # Extract from single device
        extract-ddi router1.example.com -t cisco

        # Extract from multiple devices in router.db
        extract-ddi --router-db /etc/rancid/router.db --group production

        # Output to file
        extract-ddi switch1.example.com -t juniper -o switch1.json
    """
    # Load authentication config
    cloginrc = load_cloginrc()

    results = []

    if hostname:
        # Single device mode
        if not device_type:
            click.echo("Error: --device-type is required for single host mode", err=True)
            sys.exit(1)

        result = extract_from_device(
            hostname, device_type, cloginrc,
            user=user, password=password,
            enable_password=enable_password,
            verbose=verbose
        )
        if result:
            results.append(result)

    elif router_db:
        # Router.db mode
        devices = parse_router_db(router_db, group)
        for host, dtype, status in devices:
            if status.lower() != "up":
                if verbose:
                    click.echo(f"Skipping {host} (status: {status})", err=True)
                continue

            result = extract_from_device(
                host, dtype, cloginrc,
                user=user, password=password,
                enable_password=enable_password,
                verbose=verbose
            )
            if result:
                results.append(result)
    else:
        click.echo("Error: Either HOSTNAME or --router-db is required", err=True)
        sys.exit(1)

    # Output results
    if len(results) == 1:
        output_data = results[0]
    else:
        output_data = {"devices": results}

    json_output = json.dumps(
        output_data,
        indent=2 if pretty else None,
        default=str
    )

    if output:
        Path(output).write_text(json_output)
        if verbose:
            click.echo(f"Output written to {output}", err=True)
    else:
        click.echo(json_output)


def extract_from_device(
    hostname: str,
    device_type: str,
    cloginrc: CloginrcParser,
    user: str | None = None,
    password: str | None = None,
    enable_password: str | None = None,
    verbose: bool = False,
) -> dict | None:
    """Extract DDI data from a single device."""
    if verbose:
        click.echo(f"Connecting to {hostname} ({device_type})...", err=True)

    # Get auth config
    auth = cloginrc.get_auth(hostname)
    if user:
        auth.user = user
    if password:
        auth.password = password
    if enable_password:
        auth.enable_password = enable_password

    try:
        # Create session
        session = LoginSession(
            hostname=hostname,
            username=auth.user,
            password=auth.get_password(),
            enable_password=auth.get_enable_password(),
            device_type=device_type,
        )

        # Connect
        if not session.connect():
            click.echo(f"Error: Failed to connect to {hostname}", err=True)
            return None

        # Extract data
        extractor = get_extractor(session, device_type)
        data = extractor.extract()

        # Disconnect
        session.disconnect()

        if verbose:
            click.echo(f"Successfully extracted data from {hostname}", err=True)

        return data.to_dict()

    except Exception as e:
        click.echo(f"Error extracting from {hostname}: {e}", err=True)
        return None


def parse_router_db(path: str, group: str | None = None) -> list[tuple[str, str, str]]:
    """Parse router.db file and return list of (hostname, type, status)."""
    devices = []

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split(":")
            if len(parts) >= 3:
                hostname, dtype, status = parts[0], parts[1], parts[2]
                devices.append((hostname, dtype, status))

    return devices


if __name__ == "__main__":
    main()
