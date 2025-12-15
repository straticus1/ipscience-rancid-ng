# RANCID-NG

**Really Awesome New Cisco confIg Differ - Next Generation**

A Python 3 rewrite of the classic RANCID network configuration backup and differ tool.

An **[ipscience.io](https://ipscience.io)** product from [After Dark Systems, LLC](https://afterdarksystems.com)

## Overview

RANCID-NG is a modern, Python-based replacement for the traditional Perl-based RANCID tool. It connects to network devices, collects their configurations, and stores them in a version control system (Git, SVN, or CVS) for change tracking and auditing.

## Features

- **Multi-vendor support**: Cisco IOS/IOS-XE/NX-OS/IOS-XR, Juniper JunOS, Arista EOS, Palo Alto PAN-OS, F5 BIG-IP, Fortinet FortiGate, Nokia SR-OS, and many more
- **NEW device types** not in original RANCID:
  - Cisco IronPort (ESA, WSA, SMA) / AsyncOS
  - Proofpoint Email Security
  - BlueCat DDI (DNS, DHCP, IPAM)
  - Infoblox NIOS
  - Bluecoat/Symantec ProxySG
- **Modern Python 3.10+**: Type hints, async support, modern packaging
- **Multiple VCS backends**: Git (recommended), SVN, CVS
- **Password filtering**: Automatically removes secrets from stored configs
- **Flexible authentication**: SSH keys, passwords, TACACS+, RADIUS

## Requirements

- Python 3.10 or later
- Git (for Git backend)
- Network access to managed devices

## Installation

```bash
# From PyPI (when published)
pip install rancid-ng

# From source
git clone https://github.com/straticus1/ipscience-rancid-ng.git
cd ipscience-rancid-ng
pip install -e .

# System-wide installation
sudo ./install.sh --symlink

# With development dependencies
pip install -e ".[dev]"
```

## Quick Start

1. **Create authentication file** (`~/.cloginrc`):

```
# Device credentials
add user router* admin
add password router* {vtypassword} {enablepassword}
add method router* ssh

# Switches use different credentials
add user switch* netadmin
add password switch* {switchpass}
add noenable switch* 1
```

2. **Create router database** (`router.db`):

```
router1.example.com:cisco:up
router2.example.com:juniper:up
switch1.example.com:arista:up
firewall1.example.com:paloalto:up
```

3. **Initialize repository**:

```bash
rancid-ng init --group production
```

4. **Run collection**:

```bash
rancid-ng run --group production
```

## CLI Commands

### Main Commands

- `rancid-ng run` - Run configuration collection
- `rancid-ng init` - Initialize a new group/repository
- `rancid-ng diff` - Show configuration changes
- `rancid-ng show` - Display device information

### Login Scripts (for interactive use)

- `clogin` - Cisco login (IOS, IOS-XE, NX-OS)
- `jlogin` - Juniper login (JunOS)
- `hlogin` - HP/Aruba login
- `flogin` - Foundry/Brocade login
- `panlogin` - Palo Alto login
- `fnlogin` - Fortinet login
- `noklogin` - Nokia login
- `mtlogin` - MikroTik login

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `RANCID_SYSCONFDIR` | Config directory | `/etc/rancid` |
| `FILTER_PWDS` | Password filtering (NO/YES/ALL) | `YES` |
| `NOCOMMSTR` | Filter SNMP communities | `NO` |
| `FILTER_OSC` | Filter oscillating data | `YES` |

### Device Types

Device types are defined in `rancid.types.base` and `rancid.types.conf`:

```
# Format: devtype;directive;value

cisco;script;rancid -t cisco
cisco;login;clogin
cisco;module;cisco
cisco;command;cisco::ShowVersion;show version
cisco;command;cisco::WriteTerm;show running-config
```

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=rancid_ng

# Format code
black src tests
ruff check src tests

# Type checking
mypy src
```

## Project Structure

```
rancid-ng/
├── src/rancid_ng/
│   ├── core/           # Core functionality
│   │   ├── processor.py    # ProcessHistory output handling
│   │   ├── filters.py      # Password/data filtering
│   │   ├── sorting.py      # IP and key sorting
│   │   └── device.py       # Base device module
│   ├── config/         # Configuration parsers
│   │   ├── cloginrc.py     # Authentication config
│   │   ├── types.py        # Device type registry
│   │   └── rancid_conf.py  # Main config file
│   ├── login/          # Connection handlers
│   │   ├── session.py      # Login session
│   │   ├── ssh.py          # SSH backend
│   │   └── telnet.py       # Telnet backend
│   ├── devices/        # Device modules
│   │   ├── cisco/          # Cisco family
│   │   ├── juniper/        # Juniper family
│   │   ├── arista/         # Arista
│   │   ├── paloalto/       # Palo Alto
│   │   └── ...             # Other vendors
│   ├── vcs/            # Version control
│   │   ├── git.py          # Git backend
│   │   └── base.py         # VCS interface
│   └── cli/            # CLI commands
├── etc/                # Configuration files
├── tests/              # Test suite
└── pyproject.toml      # Package metadata
```

## Supported Device Types

### Routing & Switching
- Cisco IOS, IOS-XE, IOS-XR, NX-OS
- Juniper JunOS, JunOS-EVO
- Arista EOS
- Dell DNOS9, DNOS10
- Extreme EXOS
- Foundry/Brocade
- MikroTik RouterOS
- Nokia SR-OS
- Ubiquiti EdgeRouter

### Firewalls
- Palo Alto PAN-OS
- Fortinet FortiGate
- Cisco FXOS/FTD

### Load Balancers
- F5 BIG-IP

### Security Appliances
- Cisco IronPort (ESA/WSA/SMA)
- Proofpoint Email Security
- Bluecoat/Symantec ProxySG

### Infrastructure
- BlueCat DDI
- Infoblox NIOS
- Cisco Wireless LAN Controller

## License

BSD 3-Clause License

## Credits

- Original RANCID by Shrubbery Networks
- RANCID-NG developed by **[ipscience.io](https://ipscience.io)**, a service from [After Dark Systems, LLC](https://afterdarksystems.com)

## Support

For issues and feature requests, please use the [GitHub issue tracker](https://github.com/straticus1/ipscience-rancid-ng/issues).
