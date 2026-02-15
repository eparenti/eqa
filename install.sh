#!/usr/bin/env bash
# Install exercise-qa-4 (eqa) on the current system

set -e

EQA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${HOME}/.local/bin"

echo "Installing exercise-qa-4..."
echo "  Source: $EQA_DIR"
echo "  Install dir: $INSTALL_DIR"

# Create install directory if it doesn't exist
mkdir -p "$INSTALL_DIR"

# Create symlink to eqa script
if [ -L "$INSTALL_DIR/eqa" ]; then
    echo "  Removing existing symlink..."
    rm "$INSTALL_DIR/eqa"
elif [ -e "$INSTALL_DIR/eqa" ]; then
    echo "  ERROR: $INSTALL_DIR/eqa exists and is not a symlink"
    echo "  Please remove it manually and try again"
    exit 1
fi

ln -s "$EQA_DIR/eqa" "$INSTALL_DIR/eqa"
echo "  Created symlink: $INSTALL_DIR/eqa -> $EQA_DIR/eqa"

# Check if ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo ""
    echo "  WARNING: $HOME/.local/bin is not in your PATH"
    echo "  Add this line to your ~/.bashrc or ~/.zshrc:"
    echo ""
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
fi

echo ""
echo "✓ Installation complete!"
echo ""
echo "Usage:"
echo "  eqa AU0024L                    # test all exercises in a lesson"
echo "  eqa AU0024L scale-files        # test one exercise"
echo "  eqa AU294 --chapter 4          # test chapter 4"
echo "  eqa AU0022L control-flow --cycles 2  # idempotency testing"
echo "  eqa --help                     # see all options"
echo ""
