#!/bin/bash
# Setup script for Boundless Studios team members with access to private repos
# This script clones private repos and creates symlinks for development.
#
# Unlike subtrees, this approach:
# - Clones private repos as separate directories (siblings to gaia-free)
# - Creates symlinks from gaia-free to those clones
# - Keeps private content OUT of gaia-free's git history
# - Safe for public repositories

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR"
PARENT_DIR="$(cd "$ROOT_DIR/.." && pwd)"

# Private repositories (cloned as siblings)
PRIVATE_REPO="git@github.com:Boundless-Studios/gaia-private.git"
PRIVATE_CLONE_DIR="$PARENT_DIR/gaia-private"

CAMPAIGNS_REPO="git@github.com:Boundless-Studios/gaia-campaigns.git"
CAMPAIGNS_CLONE_DIR="$PARENT_DIR/gaia-campaigns"

# Symlink targets inside gaia-free
PRIVATE_LINK="$ROOT_DIR/backend/src/gaia_private"
CAMPAIGNS_LINK="$ROOT_DIR/backend/src/gaia_campaigns"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if user has access to private repositories
check_access() {
    log_info "Checking access to private repositories..."

    # Check gaia-private access
    if ! git ls-remote "$PRIVATE_REPO" &>/dev/null; then
        log_error "Cannot access $PRIVATE_REPO"
        log_error "Make sure you have SSH access to Boundless-Studios/gaia-private"
        exit 1
    fi
    log_info "  ✓ gaia-private access confirmed"

    # Check gaia-campaigns access
    if ! git ls-remote "$CAMPAIGNS_REPO" &>/dev/null; then
        log_error "Cannot access $CAMPAIGNS_REPO"
        log_error "Make sure you have SSH access to Boundless-Studios/gaia-campaigns"
        exit 1
    fi
    log_info "  ✓ gaia-campaigns access confirmed"
}

# Clone or update private repository
setup_private_clone() {
    log_info "Setting up gaia-private..."

    if [ -d "$PRIVATE_CLONE_DIR" ]; then
        log_info "  gaia-private already cloned, pulling latest..."
        (cd "$PRIVATE_CLONE_DIR" && git pull origin main) || {
            log_warn "  Pull failed - you may need to resolve conflicts"
        }
    else
        log_info "  Cloning gaia-private..."
        git clone "$PRIVATE_REPO" "$PRIVATE_CLONE_DIR"
    fi
}

# Clone or update campaigns repository
setup_campaigns_clone() {
    log_info "Setting up gaia-campaigns..."

    if [ -d "$CAMPAIGNS_CLONE_DIR" ]; then
        log_info "  gaia-campaigns already cloned, pulling latest..."
        (cd "$CAMPAIGNS_CLONE_DIR" && git pull origin main) || {
            log_warn "  Pull failed - you may need to resolve conflicts"
        }
    else
        log_info "  Cloning gaia-campaigns..."
        git clone "$CAMPAIGNS_REPO" "$CAMPAIGNS_CLONE_DIR"
    fi
}

# Create symlink for private code
create_private_symlink() {
    log_info "Creating gaia_private symlink..."

    if [ ! -d "$PRIVATE_CLONE_DIR" ]; then
        log_warn "  gaia-private not cloned - skipping"
        return
    fi

    # Remove existing symlink or directory
    if [ -L "$PRIVATE_LINK" ]; then
        rm "$PRIVATE_LINK"
    elif [ -d "$PRIVATE_LINK" ]; then
        log_warn "  backend/src/gaia_private/ exists as directory, backing up..."
        mv "$PRIVATE_LINK" "${PRIVATE_LINK}.bak"
    fi

    ln -sf "$PRIVATE_CLONE_DIR" "$PRIVATE_LINK"
    log_info "  Linked: backend/src/gaia_private/ -> ../../../gaia-private/"
}

# Create symlink for campaigns
create_campaigns_symlink() {
    log_info "Creating gaia_campaigns symlink..."

    if [ ! -d "$CAMPAIGNS_CLONE_DIR" ]; then
        log_warn "  gaia-campaigns not cloned - skipping"
        return
    fi

    # Remove existing symlink or directory
    if [ -L "$CAMPAIGNS_LINK" ]; then
        rm "$CAMPAIGNS_LINK"
    elif [ -d "$CAMPAIGNS_LINK" ]; then
        log_warn "  backend/src/gaia_campaigns/ exists as directory, backing up..."
        mv "$CAMPAIGNS_LINK" "${CAMPAIGNS_LINK}.bak"
    fi

    ln -sf "$CAMPAIGNS_CLONE_DIR" "$CAMPAIGNS_LINK"
    log_info "  Linked: backend/src/gaia_campaigns/ -> ../../../gaia-campaigns/"
}

# Create symlinks for config files
create_config_symlinks() {
    log_info "Creating config symlinks..."

    local config_source="$PRIVATE_CLONE_DIR/_config"
    local config_target="$ROOT_DIR/config"

    if [ ! -d "$config_source" ]; then
        log_warn "  No _config directory in gaia-private - skipping config symlinks"
        return
    fi

    for config_file in "$config_source"/*.env; do
        if [ -f "$config_file" ]; then
            local filename=$(basename "$config_file")
            local target="$config_target/$filename"

            if [ -L "$target" ]; then
                rm "$target"
            elif [ -f "$target" ]; then
                log_warn "  $filename exists as file, backing up to ${filename}.bak"
                mv "$target" "${target}.bak"
            fi

            ln -sf "$config_file" "$target"
            log_info "  Linked: config/$filename"
        fi
    done
}

# Create symlinks for secrets
create_secrets_symlinks() {
    log_info "Creating secrets symlinks..."

    local secrets_source="$PRIVATE_CLONE_DIR/_secrets"
    local secrets_target="$ROOT_DIR/secrets"

    if [ ! -d "$secrets_source" ]; then
        log_warn "  No _secrets directory in gaia-private - skipping secrets symlinks"
        return
    fi

    if [ -f "$secrets_source/.secrets.env" ]; then
        local target="$secrets_target/.secrets.env"

        if [ -L "$target" ]; then
            rm "$target"
        elif [ -f "$target" ]; then
            log_warn "  .secrets.env exists as file, backing up"
            mv "$target" "${target}.bak"
        fi

        ln -sf "$secrets_source/.secrets.env" "$target"
        log_info "  Linked: secrets/.secrets.env"
    fi
}

# Create symlink for infra directory
create_infra_symlink() {
    log_info "Creating infrastructure symlink..."

    local infra_source="$PRIVATE_CLONE_DIR/_infra"
    local infra_target="$ROOT_DIR/infra"

    if [ ! -d "$infra_source" ]; then
        log_warn "  No _infra directory in gaia-private - skipping"
        return
    fi

    if [ -L "$infra_target" ]; then
        rm "$infra_target"
    elif [ -d "$infra_target" ]; then
        log_warn "  infra/ exists as directory, backing up to infra.bak/"
        mv "$infra_target" "${infra_target}.bak"
    fi

    ln -sf "$infra_source" "$infra_target"
    log_info "  Linked: infra/ -> gaia-private/_infra/"
}

# Create symlinks for service settings files
create_settings_symlinks() {
    log_info "Creating service settings symlinks..."

    local settings_source="$PRIVATE_CLONE_DIR/_settings"

    if [ ! -d "$settings_source" ]; then
        log_warn "  No _settings directory in gaia-private - skipping settings symlinks"
        return
    fi

    # Frontend settings
    if [ -f "$settings_source/frontend.settings.docker.env" ]; then
        local target="$ROOT_DIR/frontend/.settings.docker.env"

        if [ -L "$target" ]; then
            rm "$target"
        elif [ -f "$target" ]; then
            log_warn "  frontend/.settings.docker.env exists as file, backing up"
            mv "$target" "${target}.bak"
        fi

        ln -sf "$settings_source/frontend.settings.docker.env" "$target"
        log_info "  Linked: frontend/.settings.docker.env"
    fi

    # Speech-to-text settings
    if [ -f "$settings_source/speech-to-text.settings.docker.env" ]; then
        local target="$ROOT_DIR/speech-to-text/.settings.docker.env"

        if [ -L "$target" ]; then
            rm "$target"
        elif [ -f "$target" ]; then
            log_warn "  speech-to-text/.settings.docker.env exists as file, backing up"
            mv "$target" "${target}.bak"
        fi

        ln -sf "$settings_source/speech-to-text.settings.docker.env" "$target"
        log_info "  Linked: speech-to-text/.settings.docker.env"
    fi
}

# Create symlink for scripts directory
create_scripts_symlink() {
    log_info "Creating scripts symlink..."

    local scripts_source="$PRIVATE_CLONE_DIR/_scripts"
    local scripts_target="$ROOT_DIR/scripts"

    if [ ! -d "$scripts_source" ]; then
        log_warn "  No _scripts directory in gaia-private - skipping"
        return
    fi

    if [ -L "$scripts_target" ]; then
        rm "$scripts_target"
    elif [ -d "$scripts_target" ]; then
        log_warn "  scripts/ exists as directory, backing up to scripts.bak/"
        mv "$scripts_target" "${scripts_target}.bak"
    fi

    ln -sf "$scripts_source" "$scripts_target"
    log_info "  Linked: scripts/ -> gaia-private/_scripts/"
}

# Create symlink for campaign_storage directory
create_campaign_storage_symlink() {
    log_info "Creating campaign_storage symlink..."

    local campaigns_target="$ROOT_DIR/campaign_storage"

    if [ ! -d "$CAMPAIGNS_CLONE_DIR" ]; then
        log_warn "  gaia-campaigns not cloned - skipping campaign_storage symlink"
        return
    fi

    if [ -L "$campaigns_target" ]; then
        rm "$campaigns_target"
    elif [ -d "$campaigns_target" ]; then
        log_warn "  campaign_storage/ exists as directory, backing up to campaign_storage.bak/"
        mv "$campaigns_target" "${campaigns_target}.bak"
    fi

    ln -sf "$CAMPAIGNS_CLONE_DIR" "$campaigns_target"
    log_info "  Linked: campaign_storage/ -> gaia-campaigns/"
}

# Verify setup
verify_setup() {
    log_info "Verifying setup..."
    local errors=0

    # Check private clone
    if [ -d "$PRIVATE_CLONE_DIR" ]; then
        log_info "  ✓ gaia-private cloned"
    else
        log_error "  ✗ gaia-private not found"
        errors=$((errors + 1))
    fi

    # Check campaigns clone
    if [ -d "$CAMPAIGNS_CLONE_DIR" ]; then
        log_info "  ✓ gaia-campaigns cloned"
    else
        log_error "  ✗ gaia-campaigns not found"
        errors=$((errors + 1))
    fi

    # Check symlinks
    if [ -L "$PRIVATE_LINK" ]; then
        log_info "  ✓ backend/src/gaia_private symlink"
    else
        log_warn "  ✗ backend/src/gaia_private symlink missing"
    fi

    if [ -L "$CAMPAIGNS_LINK" ]; then
        log_info "  ✓ backend/src/gaia_campaigns symlink"
    else
        log_warn "  ✗ backend/src/gaia_campaigns symlink missing"
    fi

    if [ -L "$ROOT_DIR/scripts" ]; then
        log_info "  ✓ scripts/ symlink"
    else
        log_warn "  ✗ scripts/ symlink missing"
    fi

    if [ -L "$ROOT_DIR/infra" ]; then
        log_info "  ✓ infra/ symlink"
    else
        log_warn "  ✗ infra/ symlink missing"
    fi

    if [ -L "$ROOT_DIR/campaign_storage" ]; then
        log_info "  ✓ campaign_storage/ symlink"
    else
        log_warn "  ✗ campaign_storage/ symlink missing"
    fi

    if [ $errors -gt 0 ]; then
        log_error "Setup completed with $errors errors"
        exit 1
    fi

    log_info "Private setup complete!"
}

# Main
main() {
    cd "$ROOT_DIR"

    echo "========================================"
    echo "  Gaia Private Repository Setup"
    echo "========================================"
    echo ""
    echo "This will clone private repos as siblings and create symlinks:"
    echo "  - gaia-private -> $PRIVATE_CLONE_DIR"
    echo "  - gaia-campaigns -> $CAMPAIGNS_CLONE_DIR"
    echo ""

    check_access
    setup_private_clone
    setup_campaigns_clone
    create_private_symlink
    create_campaigns_symlink
    create_config_symlinks
    create_secrets_symlinks
    create_infra_symlink
    create_settings_symlinks
    create_scripts_symlink
    create_campaign_storage_symlink
    verify_setup

    echo ""
    log_info "You can now use the private code and campaigns!"
    log_info ""
    log_info "Workflow:"
    log_info "  - Edit private code in ../gaia-private/ and commit there"
    log_info "  - Edit campaigns in ../gaia-campaigns/ and commit there"
    log_info "  - gaia-free stays clean - no private content in its git"
    log_info ""
    log_info "Update commands:"
    log_info "  cd ../gaia-private && git pull    # Update private code"
    log_info "  cd ../gaia-campaigns && git pull  # Update campaigns"
}

main "$@"
