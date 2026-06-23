#!/bin/bash
# Google Antigravity Auth Plugin Installer for Hermes Agent (macOS/Linux)

# Resolve Hermes home folder
if [ "$(uname)" == "Darwin" ]; then
    HERMES_DIR="$HOME/Library/Application Support/hermes"
    if [ ! -d "$HERMES_DIR" ]; then
        HERMES_DIR="$HOME/.hermes"
    fi
else
    HERMES_DIR="$HOME/.hermes"
fi

if [ ! -d "$HERMES_DIR" ]; then
    echo "Could not find Hermes home directory. Please make sure Hermes is installed."
    exit 1
fi

PLUGINS_DIR="$HERMES_DIR/plugins"
MODEL_PROVIDERS_DEST="$PLUGINS_DIR/model-providers/antigravity"
GENERAL_DEST="$PLUGINS_DIR/antigravity_mrhisyammm"

# Check if we are running from web stream
if [ ! -d "plugins/antigravity_mrhisyammm" ]; then
    echo "Running from web/remote stream. Downloading files from GitHub..."
    TEMP_DIR="/tmp/hermes-antigravity-auth-temp"
    rm -rf "$TEMP_DIR"
    mkdir -p "$TEMP_DIR"
    
    curl -fsSL https://github.com/mrhisyammm/hermes-antigravity-auth/archive/refs/heads/main.zip -o "$TEMP_DIR/repo.zip"
    unzip -q "$TEMP_DIR/repo.zip" -d "$TEMP_DIR"
    
    SRC_PATH="$TEMP_DIR/hermes-antigravity-auth-main"
else
    SRC_PATH="."
    TEMP_DIR=""
fi

echo "Installing plugin files to $PLUGINS_DIR..."

# Create directories
mkdir -p "$MODEL_PROVIDERS_DEST"
mkdir -p "$GENERAL_DEST"

# Copy files
cp -rf "$SRC_PATH/plugins/model-providers/antigravity/"* "$MODEL_PROVIDERS_DEST/"
cp -rf "$SRC_PATH/plugins/antigravity_mrhisyammm/"* "$GENERAL_DEST/"

echo "✓ Plugin files copied successfully."

# Configure config.yaml
CONFIG_PATH="$HERMES_DIR/config.yaml"
if [ -f "$CONFIG_PATH" ]; then
    echo "Configuring config.yaml..."
    
    # 1. Add antigravity provider to providers section
    if ! grep -q "antigravity" "$CONFIG_PATH"; then
        sed -i 's/providers: {}/providers:
  antigravity:
    api_key: mock
    base_url: http://127.0.0.1:8999/v1/g' "$CONFIG_PATH"
    fi
    
    # 2. Add antigravity_mrhisyammm to plugins.enabled list
    if ! grep -q "antigravity_mrhisyammm" "$CONFIG_PATH"; then
        if grep -q "enabled:" "$CONFIG_PATH"; then
            sed -i 's/enabled:/enabled:
  - antigravity_mrhisyammm/g' "$CONFIG_PATH"
        else
            echo -e "
plugins:
  enabled:
  - antigravity_mrhisyammm
  disabled: []" >> "$CONFIG_PATH"
        fi
    fi
    echo "✓ config.yaml configured successfully."
fi

# Configure .env file
ENV_PATH="$HERMES_DIR/.env"
if [ -f "$ENV_PATH" ]; then
    echo "Configuring .env..."
    if ! grep -q "ANTIGRAVITY_API_KEY" "$ENV_PATH"; then
        echo -e "
ANTIGRAVITY_API_KEY=mock
ANTIGRAVITY_BASE_URL=http://127.0.0.1:8999/v1" >> "$ENV_PATH"
        echo "✓ .env configured successfully."
    fi
fi

# Clean up temp dir
if [ -n "$TEMP_DIR" ] && [ -d "$TEMP_DIR" ]; then
    rm -rf "$TEMP_DIR"
fi

echo -e "
============================================================"
echo -e "  Installation Completed Successfully!"
echo -e "============================================================"
echo -e "Next Steps:"
echo -e "1. Run 'hermes' in your terminal."
echo -e "2. Inside the chat, type '/antigravity-mrhisyammm' to open the Accounts Manager."
echo -e "   (From there, select option 2 to log in your Google account)."
echo -e "3. Run 'hermes model --refresh' to refresh models list, and select 'Google Antigravity' as provider."
echo -e "============================================================"
