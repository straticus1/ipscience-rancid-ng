#!/usr/bin/env bash
#
# RANCID-NG Installation Script
# Installs rancid-ng to /usr/local/rancid-ng/
#
set -e

# Configuration
INSTALL_DIR="/usr/local/rancid-ng"
SYMLINK_DIR="/usr/local/bin"
PYTHON_MIN_VERSION="3.10"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Options
CREATE_SYMLINKS=false
FORCE=false
UNINSTALL=false

usage() {
    cat <<EOF
RANCID-NG Installation Script

Usage: $(basename "$0") [OPTIONS]

Options:
    --symlink       Create symlinks in $SYMLINK_DIR
    --force         Overwrite existing installation
    --uninstall     Remove installation and symlinks
    -h, --help      Show this help message

Examples:
    sudo ./install.sh                  # Basic installation
    sudo ./install.sh --symlink        # Install with symlinks to /usr/local/bin
    sudo ./install.sh --uninstall      # Remove installation
EOF
    exit 0
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

check_python() {
    local python_cmd=""

    # Try to find a suitable Python
    for cmd in python3.12 python3.11 python3.10 python3; do
        if command -v "$cmd" &> /dev/null; then
            local version=$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
            if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
                python_cmd="$cmd"
                break
            fi
        fi
    done

    if [[ -z "$python_cmd" ]]; then
        log_error "Python >= $PYTHON_MIN_VERSION is required but not found"
        exit 1
    fi

    echo "$python_cmd"
}

# List of binaries to install
BINARIES=(
    "rancid-ng"
    "rancid"
    "clogin"
    "jlogin"
    "hlogin"
    "flogin"
    "xilogin"
    "panlogin"
    "fnlogin"
    "noklogin"
    "mtlogin"
    "rancid-run"
    "rancid-cvs"
    "extract-ddi"
    "host2ddi"
)

create_symlinks() {
    log_info "Creating symlinks in $SYMLINK_DIR..."

    for bin in "${BINARIES[@]}"; do
        local src="$INSTALL_DIR/bin/$bin"
        local dst="$SYMLINK_DIR/$bin"

        if [[ -L "$dst" ]]; then
            rm "$dst"
        elif [[ -e "$dst" ]]; then
            log_warn "Skipping $dst (file exists and is not a symlink)"
            continue
        fi

        ln -s "$src" "$dst"
        log_info "  $dst -> $src"
    done
}

remove_symlinks() {
    log_info "Removing symlinks from $SYMLINK_DIR..."

    for bin in "${BINARIES[@]}"; do
        local dst="$SYMLINK_DIR/$bin"

        if [[ -L "$dst" ]]; then
            # Verify it points to our installation
            local target=$(readlink "$dst")
            if [[ "$target" == "$INSTALL_DIR/bin/$bin" ]]; then
                rm "$dst"
                log_info "  Removed $dst"
            else
                log_warn "  Skipping $dst (points to $target, not our installation)"
            fi
        fi
    done
}

do_uninstall() {
    check_root

    log_info "Uninstalling RANCID-NG..."

    # Remove symlinks first
    remove_symlinks

    # Remove installation directory
    if [[ -d "$INSTALL_DIR" ]]; then
        rm -rf "$INSTALL_DIR"
        log_info "Removed $INSTALL_DIR"
    else
        log_warn "$INSTALL_DIR does not exist"
    fi

    log_info "Uninstallation complete"
    exit 0
}

do_install() {
    check_root

    local PYTHON=$(check_python)
    log_info "Using Python: $PYTHON ($($PYTHON --version))"

    # Check if already installed
    if [[ -d "$INSTALL_DIR" ]]; then
        if [[ "$FORCE" == true ]]; then
            log_warn "Removing existing installation..."
            rm -rf "$INSTALL_DIR"
        else
            log_error "$INSTALL_DIR already exists. Use --force to overwrite."
            exit 1
        fi
    fi

    # Create installation directory
    log_info "Creating installation directory: $INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"

    # Copy source files
    log_info "Copying source files..."
    cp -r "$SCRIPT_DIR/src" "$INSTALL_DIR/"
    cp -r "$SCRIPT_DIR/etc" "$INSTALL_DIR/" 2>/dev/null || true
    cp "$SCRIPT_DIR/pyproject.toml" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/README.md" "$INSTALL_DIR/" 2>/dev/null || true

    # Create virtual environment
    log_info "Creating virtual environment..."
    "$PYTHON" -m venv "$INSTALL_DIR/.venv"

    # Install dependencies
    log_info "Installing dependencies..."
    "$INSTALL_DIR/.venv/bin/pip" install --upgrade pip --quiet
    "$INSTALL_DIR/.venv/bin/pip" install -e "$INSTALL_DIR" --quiet

    # Create bin directory and wrapper scripts
    log_info "Creating wrapper scripts..."
    mkdir -p "$INSTALL_DIR/bin"

    # Generate wrapper scripts
    cat > "$INSTALL_DIR/bin/rancid-ng" <<'WRAPPER'
#!/usr/bin/env bash
INSTALL_DIR="/usr/local/rancid-ng"
exec "$INSTALL_DIR/.venv/bin/python" -m rancid_ng.cli.main "$@"
WRAPPER

    cat > "$INSTALL_DIR/bin/rancid" <<'WRAPPER'
#!/usr/bin/env bash
INSTALL_DIR="/usr/local/rancid-ng"
exec "$INSTALL_DIR/.venv/bin/python" -m rancid_ng.cli.rancid "$@"
WRAPPER

    cat > "$INSTALL_DIR/bin/clogin" <<'WRAPPER'
#!/usr/bin/env bash
INSTALL_DIR="/usr/local/rancid-ng"
exec "$INSTALL_DIR/.venv/bin/python" -m rancid_ng.cli.clogin "$@"
WRAPPER

    cat > "$INSTALL_DIR/bin/jlogin" <<'WRAPPER'
#!/usr/bin/env bash
INSTALL_DIR="/usr/local/rancid-ng"
exec "$INSTALL_DIR/.venv/bin/python" -m rancid_ng.cli.jlogin "$@"
WRAPPER

    cat > "$INSTALL_DIR/bin/hlogin" <<'WRAPPER'
#!/usr/bin/env bash
INSTALL_DIR="/usr/local/rancid-ng"
exec "$INSTALL_DIR/.venv/bin/python" -m rancid_ng.cli.hlogin "$@"
WRAPPER

    cat > "$INSTALL_DIR/bin/flogin" <<'WRAPPER'
#!/usr/bin/env bash
INSTALL_DIR="/usr/local/rancid-ng"
exec "$INSTALL_DIR/.venv/bin/python" -m rancid_ng.cli.flogin "$@"
WRAPPER

    cat > "$INSTALL_DIR/bin/xilogin" <<'WRAPPER'
#!/usr/bin/env bash
INSTALL_DIR="/usr/local/rancid-ng"
exec "$INSTALL_DIR/.venv/bin/python" -m rancid_ng.cli.xilogin "$@"
WRAPPER

    cat > "$INSTALL_DIR/bin/panlogin" <<'WRAPPER'
#!/usr/bin/env bash
INSTALL_DIR="/usr/local/rancid-ng"
exec "$INSTALL_DIR/.venv/bin/python" -m rancid_ng.cli.panlogin "$@"
WRAPPER

    cat > "$INSTALL_DIR/bin/fnlogin" <<'WRAPPER'
#!/usr/bin/env bash
INSTALL_DIR="/usr/local/rancid-ng"
exec "$INSTALL_DIR/.venv/bin/python" -m rancid_ng.cli.fnlogin "$@"
WRAPPER

    cat > "$INSTALL_DIR/bin/noklogin" <<'WRAPPER'
#!/usr/bin/env bash
INSTALL_DIR="/usr/local/rancid-ng"
exec "$INSTALL_DIR/.venv/bin/python" -m rancid_ng.cli.noklogin "$@"
WRAPPER

    cat > "$INSTALL_DIR/bin/mtlogin" <<'WRAPPER'
#!/usr/bin/env bash
INSTALL_DIR="/usr/local/rancid-ng"
exec "$INSTALL_DIR/.venv/bin/python" -m rancid_ng.cli.mtlogin "$@"
WRAPPER

    cat > "$INSTALL_DIR/bin/rancid-run" <<'WRAPPER'
#!/usr/bin/env bash
INSTALL_DIR="/usr/local/rancid-ng"
exec "$INSTALL_DIR/.venv/bin/python" -m rancid_ng.cli.rancid_run "$@"
WRAPPER

    cat > "$INSTALL_DIR/bin/rancid-cvs" <<'WRAPPER'
#!/usr/bin/env bash
INSTALL_DIR="/usr/local/rancid-ng"
exec "$INSTALL_DIR/.venv/bin/python" -m rancid_ng.cli.rancid_cvs "$@"
WRAPPER

    cat > "$INSTALL_DIR/bin/extract-ddi" <<'WRAPPER'
#!/usr/bin/env bash
INSTALL_DIR="/usr/local/rancid-ng"
exec "$INSTALL_DIR/.venv/bin/python" -m rancid_ng.cli.extract_ddi "$@"
WRAPPER

    cat > "$INSTALL_DIR/bin/host2ddi" <<'WRAPPER'
#!/usr/bin/env bash
INSTALL_DIR="/usr/local/rancid-ng"
exec "$INSTALL_DIR/.venv/bin/python" -m rancid_ng.cli.host2ddi "$@"
WRAPPER

    # Make all scripts executable
    chmod +x "$INSTALL_DIR/bin/"*

    # Create symlinks if requested
    if [[ "$CREATE_SYMLINKS" == true ]]; then
        create_symlinks
    fi

    log_info "Installation complete!"
    echo ""
    echo "RANCID-NG has been installed to: $INSTALL_DIR"
    echo ""
    echo "Binaries are available at: $INSTALL_DIR/bin/"
    echo ""
    if [[ "$CREATE_SYMLINKS" == true ]]; then
        echo "Symlinks have been created in: $SYMLINK_DIR"
        echo "You can now run commands like: rancid-ng --help"
    else
        echo "To add to your PATH, run:"
        echo "  export PATH=\"$INSTALL_DIR/bin:\$PATH\""
        echo ""
        echo "Or create symlinks with:"
        echo "  sudo $0 --symlink"
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --symlink)
            CREATE_SYMLINKS=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --uninstall)
            UNINSTALL=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            ;;
    esac
done

# Main execution
if [[ "$UNINSTALL" == true ]]; then
    do_uninstall
else
    do_install
fi
