#!/bin/bash
# Google Antigravity Auth Plugin Installer for Hermes Agent (macOS/Linux)

# Resolve Hermes home folder
HERMES_DIR="$HOME/.hermes"

if [ ! -d "$HERMES_DIR" ]; then
    echo "Could not find Hermes home directory. Please make sure Hermes is installed."
    exit 1
fi

PLUGINS_DIR="$HERMES_DIR/plugins"
MODEL_PROVIDERS_DEST="$PLUGINS_DIR/model-providers/antigravity"
GENERAL_DEST="$PLUGINS_DIR/antigravity_mrhisyammm"

# Kill existing running processes to prevent file locks and ensure reload
echo "Stopping running Hermes and background proxy daemons..."
# Kill proxy listening on port 8999
PROXY_PID=$(lsof -t -i:8999 2>/dev/null)
if [ -n "$PROXY_PID" ]; then
    kill -9 $PROXY_PID 2>/dev/null || true
fi
# Kill hermes processes
HERMES_PIDS=$(ps aux | grep -i "hermes" | grep -v "grep" | awk '{print $2}')
if [ -n "$HERMES_PIDS" ]; then
    kill -9 $HERMES_PIDS 2>/dev/null || true
fi
echo "✓ Active daemons stopped."

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

# Configure config.yaml and .env via Python helper first
PYTHON_CONFIGURED=0
if command -v python3 &>/dev/null; then
    echo "Running Python configuration helper..."
    python3 "$SRC_PATH/configure_config.py" "$HERMES_DIR"
    PYTHON_CONFIGURED=1
elif command -v python &>/dev/null; then
    echo "Running Python configuration helper..."
    python "$SRC_PATH/configure_config.py" "$HERMES_DIR"
    PYTHON_CONFIGURED=1
fi

if [ "$PYTHON_CONFIGURED" -eq 0 ]; then
    # Configure config.yaml
    CONFIG_PATH="$HERMES_DIR/config.yaml"
    if [ -f "$CONFIG_PATH" ]; then
        echo "Configuring config.yaml (Bash fallback)..."
        
        # 1. Add antigravity provider to providers section
        if ! grep -q "antigravity:" "$CONFIG_PATH"; then
            if grep -q "providers: {}" "$CONFIG_PATH"; then
                # providers: {} -> replace it
                # Using python-like inline script or perl for robust multi-line sed to avoid OS-specific sed issues
                perl -i -pe 's/providers: \{\}/providers:\n  antigravity:\n    api_key: mock\n    base_url: http:\/\/127.0.0.1:8999\/v1/g' "$CONFIG_PATH" 2>/dev/null || \
                sed -i 's/providers: {}/providers:\n  antigravity:\n    api_key: mock\n    base_url: http:\/\/127.0.0.1:8999\/v1/g' "$CONFIG_PATH"
            elif grep -q "^providers:" "$CONFIG_PATH"; then
                # Insert under providers:
                perl -i -pe 's/^providers:/providers:\n  antigravity:\n    api_key: mock\n    base_url: http:\/\/127.0.0.1:8999\/v1/g' "$CONFIG_PATH" 2>/dev/null || \
                sed -i 's/^providers:/providers:\n  antigravity:\n    api_key: mock\n    base_url: http:\/\/127.0.0.1:8999\/v1/g' "$CONFIG_PATH"
            else
                # Append providers section
                echo -e "\nproviders:\n  antigravity:\n    api_key: mock\n    base_url: http://127.0.0.1:8999/v1" >> "$CONFIG_PATH"
            fi
            echo "✓ Added antigravity provider under providers: in config.yaml"
        else
            # Auto-update base_url if it contains the old 8045 port
            if grep -q "8045" "$CONFIG_PATH"; then
                perl -i -pe 's/base_url:.*8045.*/base_url: http:\/\/127.0.0.1:8999\/v1/g' "$CONFIG_PATH" 2>/dev/null || \
                sed -i 's/base_url:.*8045.*/base_url: http:\/\/127.0.0.1:8999\/v1/g' "$CONFIG_PATH"
                echo "✓ Updated base_url port from 8045 to 8999 in config.yaml"
            fi
        fi
        
        # 2. Add antigravity_mrhisyammm to plugins.enabled list
        if ! grep -q "antigravity_mrhisyammm" "$CONFIG_PATH"; then
            if grep -q "^plugins:" "$CONFIG_PATH"; then
                if grep -q "enabled:" "$CONFIG_PATH"; then
                    perl -i -pe 's/enabled:/enabled:\n  - antigravity_mrhisyammm/g' "$CONFIG_PATH" 2>/dev/null || \
                    sed -i 's/enabled:/enabled:\n  - antigravity_mrhisyammm/g' "$CONFIG_PATH"
                else
                    perl -i -pe 's/^plugins:/plugins:\n  enabled:\n  - antigravity_mrhisyammm\n  disabled: []/g' "$CONFIG_PATH" 2>/dev/null || \
                    sed -i 's/^plugins:/plugins:\n  enabled:\n  - antigravity_mrhisyammm\n  disabled: []/g' "$CONFIG_PATH"
                fi
            else
                echo -e "\nplugins:\n  enabled:\n  - antigravity_mrhisyammm\n  disabled: []" >> "$CONFIG_PATH"
            fi
            echo "✓ Added antigravity_mrhisyammm to plugins enabled list in config.yaml"
        fi
    fi

    # Configure .env file
    ENV_PATH="$HERMES_DIR/.env"
    if [ -f "$ENV_PATH" ]; then
        echo "Configuring .env (Bash fallback)..."
        if ! grep -q "ANTIGRAVITY_API_KEY" "$ENV_PATH"; then
            echo -e "\nANTIGRAVITY_API_KEY=mock\nANTIGRAVITY_BASE_URL=http://127.0.0.1:8999/v1" >> "$ENV_PATH"
            echo "✓ .env configured successfully."
        else
            # Auto-update base_url if it contains the old 8045 port
            if grep -q "ANTIGRAVITY_BASE_URL=.*8045" "$ENV_PATH"; then
                perl -i -pe 's/ANTIGRAVITY_BASE_URL=.*8045.*/ANTIGRAVITY_BASE_URL=http:\/\/127.0.0.1:8999\/v1/g' "$ENV_PATH" 2>/dev/null || \
                sed -i 's/ANTIGRAVITY_BASE_URL=.*8045.*/ANTIGRAVITY_BASE_URL=http:\/\/127.0.0.1:8999\/v1/g' "$ENV_PATH"
                echo "✓ .env base URL updated successfully."
            fi
        fi
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
