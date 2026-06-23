import os
import sys

def configure(hermes_dir):
    config_path = os.path.join(hermes_dir, "config.yaml")
    if not os.path.exists(config_path):
        print(f"config.yaml not found at {config_path}")
        return

    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Ensure providers.antigravity is defined
    if "antigravity:" not in content:
        # Check if providers: {} exists
        if "providers: {}" in content:
            content = content.replace("providers: {}", "providers:\n  antigravity:\n    api_key: mock\n    base_url: http://127.0.0.1:8999/v1")
        elif "providers:" in content:
            # Insert under providers:
            content = content.replace("providers:", "providers:\n  antigravity:\n    api_key: mock\n    base_url: http://127.0.0.1:8999/v1")
        else:
            # Append providers section
            content += "\nproviders:\n  antigravity:\n    api_key: mock\n    base_url: http://127.0.0.1:8999/v1"
        print("✓ Added antigravity provider under providers: in config.yaml")
    else:
        # Auto-update base_url if it has the old 8045 port
        if "8045" in content:
            import re
            content = re.sub(r"base_url:\s*.*8045.*", "base_url: http://127.0.0.1:8999/v1", content)
            print("✓ Updated base_url port from 8045 to 8999 in config.yaml")

    # 2. Ensure antigravity_mrhisyammm is in plugins.enabled
    if "antigravity_mrhisyammm" not in content:
        if "plugins:" in content:
            if "enabled:" in content:
                content = content.replace("enabled:", "enabled:\n  - antigravity_mrhisyammm")
            else:
                content = content.replace("plugins:", "plugins:\n  enabled:\n  - antigravity_mrhisyammm\n  disabled: []")
        else:
            content += "\nplugins:\n  enabled:\n  - antigravity_mrhisyammm\n  disabled: []"
        print("✓ Added antigravity_mrhisyammm to plugins enabled list in config.yaml")

    with open(config_path, "w", encoding="utf-8") as f:
        f.write(content)

    # Configure .env
    env_path = os.path.join(hermes_dir, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            env_content = f.read()
        
        if "ANTIGRAVITY_API_KEY" not in env_content:
            env_content += "\nANTIGRAVITY_API_KEY=mock\nANTIGRAVITY_BASE_URL=http://127.0.0.1:8999/v1"
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(env_content)
            print("✓ .env configured successfully via Python.")
        elif "8045" in env_content:
            import re
            env_content = re.sub(r"ANTIGRAVITY_BASE_URL=.*8045.*", "ANTIGRAVITY_BASE_URL=http://127.0.0.1:8999/v1", env_content)
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(env_content)
            print("✓ .env base URL updated successfully via Python.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        configure(sys.argv[1])
