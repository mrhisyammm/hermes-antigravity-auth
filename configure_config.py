import os
import sys
import re

def configure(hermes_dir):
    config_path = os.path.join(hermes_dir, "config.yaml")
    if not os.path.exists(config_path):
        print(f"config.yaml not found at {config_path}")
        return

    with open(config_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Clean up any existing antigravity lines to avoid duplicate/corrupt states
    clean_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if "antigravity:" in line:
            # Skip this line and the next 2 lines (api_key and base_url)
            i += 3
            continue
        if "antigravity_mrhisyammm" in line:
            i += 1
            continue
        clean_lines.append(line)
        i += 1
    
    lines = clean_lines

    # 1. Ensure providers.antigravity is defined
    # Check for active providers: line (not under model_catalog)
    providers_idx = -1
    is_inside_model_catalog = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "model_catalog:":
            is_inside_model_catalog = True
        elif is_inside_model_catalog and stripped:
            if not line.startswith("  ") and not line.startswith(" "):
                is_inside_model_catalog = False
        
        if stripped.startswith("providers:") and not is_inside_model_catalog:
            providers_idx = i
            break
    
    if providers_idx != -1:
        print("Inserted antigravity under active providers: section in config.yaml")
    else:
        # Check for commented # providers: line
        commented_providers_idx = -1
        for i, line in enumerate(lines):
            if line.strip() == "# providers:":
                commented_providers_idx = i
                break
        
        if commented_providers_idx != -1:
            lines[commented_providers_idx] = "providers:\n  antigravity:\n    api_key: mock\n    base_url: http://127.0.0.1:8999/v1\n"
            print("Activated and set antigravity under providers: in config.yaml")
        else:
            # Append a new providers section
            lines.append("\nproviders:\n  antigravity:\n    api_key: mock\n    base_url: http://127.0.0.1:8999/v1\n")
            print("Appended providers section with antigravity to config.yaml")

    # 2. Ensure antigravity_mrhisyammm is in plugins.enabled
    plugins_idx = -1
    for i, line in enumerate(lines):
        if line.strip() == "plugins:":
            plugins_idx = i
            break
    
    if plugins_idx != -1:
        enabled_idx = -1
        for j in range(plugins_idx + 1, len(lines)):
            if lines[j].strip() == "enabled:":
                enabled_idx = j
                break
            if lines[j].strip() and not lines[j].startswith(" "):
                break
        
        if enabled_idx != -1:
            lines.insert(enabled_idx + 1, "  - antigravity_mrhisyammm\n")
        else:
            lines.insert(plugins_idx + 1, "  enabled:\n  - antigravity_mrhisyammm\n")
        print("Added antigravity_mrhisyammm under enabled plugins in config.yaml")
    else:
        lines.append("\nplugins:\n  enabled:\n  - antigravity_mrhisyammm\n  disabled: []\n")
        print("Appended plugins section with antigravity_mrhisyammm in config.yaml")

    with open(config_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    # Configure .env
    env_path = os.path.join(hermes_dir, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            env_content = f.read()
        
        # Remove any existing antigravity variables first to ensure clean state
        env_lines = env_content.splitlines()
        env_lines = [l for l in env_lines if "ANTIGRAVITY_API_KEY" not in l and "ANTIGRAVITY_BASE_URL" not in l]
        env_content = "\n".join(env_lines)
        
        env_content += "\nANTIGRAVITY_API_KEY=mock\nANTIGRAVITY_BASE_URL=http://127.0.0.1:8999/v1"
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(env_content)
        print("env configured successfully via Python.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        configure(sys.argv[1])
