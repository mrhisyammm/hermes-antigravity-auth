# Google Antigravity Auth Plugin Installer for Hermes Agent (Windows)

$hermesDir = Join-Path $env:USERPROFILE 'AppData\Local\hermes'
if (-not (Test-Path $hermesDir)) {
    Write-Error "Could not find Hermes home directory at $hermesDir. Please make sure Hermes is installed."
    Exit 1
}

$pluginsDir = Join-Path $hermesDir 'plugins'
$modelProvidersDest = Join-Path $pluginsDir 'model-providers\antigravity'
$generalDest = Join-Path $pluginsDir 'antigravity_mrhisyammm'

# Check if we are running from web stream or local folder
$localPlugins = Join-Path $PSScriptRoot 'plugins'
$tempDir = Join-Path $env:TEMP 'hermes-antigravity-auth-temp'
$srcPath = $PSScriptRoot

if (-not $PSScriptRoot -or -not (Test-Path (Join-Path $localPlugins 'antigravity_mrhisyammm'))) {
    Write-Host "Running from web/remote stream. Downloading files from GitHub..."
    if (Test-Path $tempDir) {
        Remove-Item -Recurse -Force $tempDir -ErrorAction SilentlyContinue
    }
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    
    $zipPath = Join-Path $tempDir 'repo.zip'
    $zipUrl = "https://github.com/mrhisyammm/hermes-antigravity-auth/archive/refs/heads/main.zip"
    
    Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath -UseBasicParsing
    Expand-Archive -Path $zipPath -DestinationPath $tempDir -Force
    
    $srcPath = Join-Path $tempDir 'hermes-antigravity-auth-main'
}

Write-Host "Installing plugin files to $pluginsDir..."

# Create directories
New-Item -ItemType Directory -Path $modelProvidersDest -Force | Out-Null
New-Item -ItemType Directory -Path $generalDest -Force | Out-Null

# Copy files
Copy-Item -Path (Join-Path $srcPath "plugins\model-providers\antigravity\*") -Destination $modelProvidersDest -Force
Copy-Item -Path (Join-Path $srcPath "plugins\antigravity_mrhisyammm\*") -Destination $generalDest -Force

Write-Host "✓ Plugin files copied successfully."

# Configure config.yaml
$configPath = Join-Path $hermesDir 'config.yaml'
if (Test-Path $configPath) {
    Write-Host "Configuring config.yaml..."
    
    $content = [System.IO.File]::ReadAllText($configPath)
    
    # 1. Add antigravity provider to providers section
    if ($content -notlike "*providers:*antigravity:*") {
        if ($content -like "*providers: {}*") {
            $newProviders = "providers:`n  antigravity:`n    api_key: mock`n    base_url: http://127.0.0.1:8999/v1"
            $content = $content -replace "providers: \{\}", $newProviders
        } else {
            $newProvider = "providers:`n  antigravity:`n    api_key: mock`n    base_url: http://127.0.0.1:8999/v1"
            $content = $content -replace "providers:", $newProvider
        }
    } else {
        # Auto-update base_url if it contains the old 8045 port
        if ($content -like "*base_url:*8045*") {
            $content = $content -replace "base_url:.*8045.*", "base_url: http://127.0.0.1:8999/v1"
        }
    }
    
    # 2. Add antigravity_mrhisyammm to plugins.enabled list
    if ($content -notlike "*enabled:*antigravity_mrhisyammm*") {
        if ($content -like "*plugins:*enabled:*") {
            $content = $content -replace "plugins:`n  enabled:", "plugins:`n  enabled:`n  - antigravity_mrhisyammm"
        } else {
            $content = $content + "`nplugins:`n  enabled:`n  - antigravity_mrhisyammm`n  disabled: []"
        }
    }
    
    [System.IO.File]::WriteAllText($configPath, $content)
    Write-Host "✓ config.yaml configured successfully."
}

# Configure .env file
$envPath = Join-Path $hermesDir '.env'
if (Test-Path $envPath) {
    Write-Host "Configuring .env..."
    $envContent = [System.IO.File]::ReadAllText($envPath)
    if ($envContent -notlike "*ANTIGRAVITY_API_KEY*") {
        $envContent = $envContent + "`nANTIGRAVITY_API_KEY=mock`nANTIGRAVITY_BASE_URL=http://127.0.0.1:8999/v1"
        [System.IO.File]::WriteAllText($envPath, $envContent)
        Write-Host "✓ .env configured successfully."
    } else {
        # Auto-update base_url if it contains the old 8045 port
        if ($envContent -like "*ANTIGRAVITY_BASE_URL=*8045*") {
            $envContent = $envContent -replace "ANTIGRAVITY_BASE_URL=.*8045.*", "ANTIGRAVITY_BASE_URL=http://127.0.0.1:8999/v1"
            [System.IO.File]::WriteAllText($envPath, $envContent)
            Write-Host "✓ .env base URL updated successfully."
        }
    }
}

# Clean up tempDir
if (Test-Path $tempDir) {
    Remove-Item -Recurse -Force $tempDir -ErrorAction SilentlyContinue
}

Write-Host "`n============================================================" -ForegroundColor Green
Write-Host "  Installation Completed Successfully!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "Next Steps:"
Write-Host "1. Run 'hermes' in your terminal."
Write-Host "2. Inside the chat, type '/antigravity-mrhisyammm' to open the Accounts Manager."
Write-Host "   (From there, select option 2 to log in your Google account)."
Write-Host "3. Run 'hermes model --refresh' to refresh models list, and select 'Google Antigravity' as provider."
Write-Host "============================================================"
