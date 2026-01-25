#!/bin/bash
# pkmdex installer
# Usage: curl -fsSL https://raw.githubusercontent.com/cloonix/pkmdex/main/install.sh | bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REPO_URL="https://github.com/cloonix/pkmdex.git"
INSTALL_DIR="$HOME/.local/share/pkmdex-bin"
BIN_DIR="$HOME/.local/bin"
APP_NAME="pkm"

# Print colored message
info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

success() {
    echo -e "${GREEN}✓${NC} $1"
}

warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

error() {
    echo -e "${RED}✗${NC} $1"
    exit 1
}

# Detect OS
detect_os() {
    case "$(uname -s)" in
        Linux*)     OS="Linux";;
        Darwin*)    OS="macOS";;
        *)          error "Unsupported OS: $(uname -s)";;
    esac
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Install uv if not present
install_uv() {
    if ! command_exists uv; then
        info "Installing uv package manager..."
        if command_exists curl; then
            curl -LsSf https://astral.sh/uv/install.sh | sh
        else
            error "curl is required but not installed. Please install curl first."
        fi
        
        # Source the shell config to get uv in PATH
        export PATH="$HOME/.cargo/bin:$PATH"
        
        if ! command_exists uv; then
            error "Failed to install uv. Please install it manually: https://github.com/astral-sh/uv"
        fi
        success "uv installed successfully"
    else
        info "uv is already installed"
    fi
}

# Check for git
check_git() {
    if ! command_exists git; then
        error "git is required but not installed. Please install git first."
    fi
}

# Detect if this is an update
is_update() {
    [ -d "$INSTALL_DIR" ] && [ -f "$BIN_DIR/$APP_NAME" ]
}

# Backup existing installation
backup_installation() {
    if is_update; then
        info "Existing installation detected"
        BACKUP_DIR="$INSTALL_DIR.backup.$(date +%Y%m%d_%H%M%S)"
        mv "$INSTALL_DIR" "$BACKUP_DIR"
        success "Backed up existing installation to $BACKUP_DIR"
    fi
}

# Clone or update repository
setup_repository() {
    mkdir -p "$(dirname "$INSTALL_DIR")"
    
    if [ -d "$INSTALL_DIR" ]; then
        info "Updating pkmdex..."
        cd "$INSTALL_DIR"
        git fetch origin
        git reset --hard origin/main
    else
        info "Downloading pkmdex..."
        git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
        cd "$INSTALL_DIR"
    fi
    
    success "Repository ready"
}

# Install dependencies and create wrapper
install_app() {
    cd "$INSTALL_DIR"
    
    info "Installing dependencies..."
    uv sync --all-extras
    
    # Create bin directory if it doesn't exist
    mkdir -p "$BIN_DIR"
    
    # Create wrapper script
    info "Creating executable wrapper..."
    cat > "$BIN_DIR/$APP_NAME" << 'EOF'
#!/bin/bash
# pkmdex wrapper script
INSTALL_DIR="$HOME/.local/share/pkmdex-bin"
exec uv --directory "$INSTALL_DIR" run python -m src.cli "$@"
EOF
    
    chmod +x "$BIN_DIR/$APP_NAME"
    success "Executable installed to $BIN_DIR/$APP_NAME"
}

# Check if bin directory is in PATH
check_path() {
    if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
        warn "$BIN_DIR is not in your PATH"
        echo ""
        echo "Add the following to your shell configuration file:"
        echo ""
        
        if [ "$OS" = "macOS" ]; then
            SHELL_CONFIG="$HOME/.zshrc"
        else
            case "$SHELL" in
                */zsh) SHELL_CONFIG="$HOME/.zshrc";;
                */bash) SHELL_CONFIG="$HOME/.bashrc";;
                *) SHELL_CONFIG="$HOME/.profile";;
            esac
        fi
        
        echo -e "${BLUE}export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
        echo ""
        echo "Then run: source $SHELL_CONFIG"
        echo ""
    fi
}

# Show completion message
show_completion() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if is_update; then
        success "pkmdex updated successfully!"
    else
        success "pkmdex installed successfully!"
    fi
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Get started:"
    echo "  $APP_NAME --help              Show all commands"
    echo "  $APP_NAME setup --show        Show configuration"
    echo "  $APP_NAME add de:me01:136     Add a card"
    echo "  $APP_NAME list                View collection"
    echo ""
    echo "Installation location: $INSTALL_DIR"
    echo ""
}

# Main installation flow
main() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  pkmdex installer"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    detect_os
    info "Detected OS: $OS"
    
    check_git
    install_uv
    backup_installation
    setup_repository
    install_app
    check_path
    show_completion
}

# Run main function
main
