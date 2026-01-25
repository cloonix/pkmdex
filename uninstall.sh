#!/bin/bash
# pkmdex uninstaller

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="$HOME/.local/share/pkmdex-bin"
BIN_DIR="$HOME/.local/bin"
APP_NAME="pkm"
CONFIG_DIR="$HOME/.config/pkmdex"
DATA_DIR="$HOME/.local/share/pkmdex"

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
}

# Ask for confirmation
confirm() {
    local prompt="$1"
    local default="${2:-n}"
    
    if [ "$default" = "y" ]; then
        prompt="$prompt [Y/n] "
    else
        prompt="$prompt [y/N] "
    fi
    
    read -p "$prompt" response
    response=${response:-$default}
    
    case "$response" in
        [yY]|[yY][eE][sS]) return 0 ;;
        *) return 1 ;;
    esac
}

# Remove installation directory
remove_installation() {
    if [ -d "$INSTALL_DIR" ]; then
        info "Removing installation directory..."
        rm -rf "$INSTALL_DIR"
        success "Installation directory removed"
    else
        info "Installation directory not found (already removed)"
    fi
}

# Remove executable
remove_executable() {
    if [ -f "$BIN_DIR/$APP_NAME" ]; then
        info "Removing executable..."
        rm -f "$BIN_DIR/$APP_NAME"
        success "Executable removed"
    else
        info "Executable not found (already removed)"
    fi
}

# Remove configuration and data
remove_data() {
    local remove_config=false
    local remove_data=false
    
    if [ -d "$CONFIG_DIR" ] || [ -d "$DATA_DIR" ]; then
        echo ""
        warn "This will remove your configuration and collection data!"
        echo ""
        [ -d "$CONFIG_DIR" ] && echo "  Config: $CONFIG_DIR"
        [ -d "$DATA_DIR" ] && echo "  Data:   $DATA_DIR"
        echo ""
        
        if confirm "Remove configuration and data?" "n"; then
            if [ -d "$CONFIG_DIR" ]; then
                rm -rf "$CONFIG_DIR"
                success "Configuration removed"
            fi
            
            if [ -d "$DATA_DIR" ]; then
                # Offer to backup first
                if confirm "Create backup before removing data?" "y"; then
                    BACKUP_FILE="$HOME/pkmdex-backup-$(date +%Y%m%d_%H%M%S).tar.gz"
                    tar -czf "$BACKUP_FILE" -C "$(dirname "$DATA_DIR")" "$(basename "$DATA_DIR")"
                    success "Backup saved to: $BACKUP_FILE"
                fi
                
                rm -rf "$DATA_DIR"
                success "Data directory removed"
            fi
        else
            info "Keeping configuration and data"
            echo "  Config: $CONFIG_DIR"
            echo "  Data:   $DATA_DIR"
        fi
    fi
}

# Show completion message
show_completion() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    success "pkmdex uninstalled successfully"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "To reinstall, run:"
    echo "  curl -fsSL https://raw.githubusercontent.com/cloonix/pkmdex/main/install.sh | bash"
    echo ""
}

# Main uninstall flow
main() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  pkmdex uninstaller"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    if [ ! -d "$INSTALL_DIR" ] && [ ! -f "$BIN_DIR/$APP_NAME" ]; then
        warn "pkmdex does not appear to be installed"
        exit 0
    fi
    
    if ! confirm "Are you sure you want to uninstall pkmdex?" "n"; then
        info "Uninstallation cancelled"
        exit 0
    fi
    
    echo ""
    remove_installation
    remove_executable
    remove_data
    show_completion
}

# Run main function
main
