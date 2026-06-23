# hermes-antigravity-auth

Google Antigravity IDE OAuth auth plugin and proxy provider for **Hermes Agent** (developed by Nous Research). This is the **official Hermes version** of the popular [@mrhisyammm/opencode-antigravity-auth](https://github.com/mrhisyammm/opencode-antigravity-auth) plugin!

Allows you to use Gemini 3.5 Flash, Gemini 3.1 Pro, and Claude 4.6 (Opus/Sonnet) for **FREE** inside Hermes Agent using your Google OAuth credentials pool with **isolated cooldowns** and **exponential backoff auto-rotation**!

## ⚡ Quick One-Line Installation

Open your terminal and run the command corresponding to your operating system to automatically download, install, and configure the plugin:

- **Windows (PowerShell - run as Administrator):**
  ```powershell
  Set-ExecutionPolicy Bypass -Scope Process -Force; irm https://raw.githubusercontent.com/mrhisyammm/hermes-antigravity-auth/main/install.ps1 | iex
  ```
- **macOS / Linux:**
  ```bash
  curl -fsSL https://raw.githubusercontent.com/mrhisyammm/hermes-antigravity-auth/main/install.sh | bash
  ```

---

## What You Get (Features)

- **Claude Opus 4.6, Sonnet 4.6** and **Gemini 3.5 Flash / 3.1 Pro / 3 Pro / 3 Flash** via Google OAuth
- **Self-Contained Proxy**: Runs its own lightweight proxy server locally in the background (`port 8999`), making it 100% plug-and-play without any external software dependencies.
- **Multi-Account Support**: Add multiple Google accounts; requests auto-rotate dynamically.
- **Isolated Cooldowns**: Cooldowns are tracked separately per account and model family (`claude` vs `gemini`). If Claude gets rate-limited, you can still use Gemini models on the same account!
- **Progressive Cooldowns (Exponential Backoff)**: Cooldown duration escalates based on consecutive failures (1 min → 5 mins → 30 mins → 2 hours) to avoid Google account blocks/verification checks and ensure long-term account safety.
- **Interactive TUI Manager**: Run account operations via `/antigravity-mrhisyammm` which spawns a separate terminal window to handle your logins, active account selection, and quota checks seamlessly without input hijacking.
- **Dynamic Model Mapping**: Model names are translated automatically for the target Google API (e.g., `gemini-3.5-flash` → `gemini-3.5-flash-low` in background) for seamless compatibility.

---

## How to Use

### 1. Log in your Google Account (Interactive Manager)
Start a normal Hermes session:
```bash
hermes
```
Inside the chat box, type the main command:
```text
/antigravity-mrhisyammm
```
This will automatically launch the **Google Antigravity Accounts Manager** interactive menu in a new PowerShell window. Select option **`2`** to log in your Google account, option **`1`** to choose your active account, or option **`3`** to check quotas.

### 2. Direct Chat Commands
- **`/antigravity-mrhisyammm-login`**: Directly triggers the browser login flow and sets the account active, printing the result in your chat.
- **`/antigravity-mrhisyammm-quota`**: Directly fetches and prints your live Weekly and 5-Hour limits right in your chat window.

### 3. Select Model
Run the model configuration wizard:
```bash
hermes model --refresh
```
Select **`Google Antigravity`** as your provider, and then choose any of the models (e.g. `gemini-3.5-flash`, `claude-opus-4-6-thinking`, or `claude-sonnet-4-6-thinking`).

---

## Technical Details

### Configuration Path
The plugin shares the exact same accounts file as the OpenCode version, meaning if you already logged in on OpenCode, your accounts will automatically load in Hermes:

- **Accounts Database**: `~/.config/opencode/antigravity-accounts.json` (on Windows, `~` is your home directory)
- **Fallback Directory**: `~/AppData/Local/hermes/antigravity-accounts.json` (if OpenCode is not installed on the machine, the plugin runs completely self-contained here).
