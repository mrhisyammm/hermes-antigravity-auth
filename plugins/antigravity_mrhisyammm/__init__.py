import json
import urllib.request
import urllib.parse
import os
import threading
import socket
import http.server
import socketserver
import webbrowser
import time
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer

# ── Proxy Configuration ──────────────────────────────────────
PROXY_PORT = 8999
CLIENT_ID = "1071006060591-tmhssin2h21lcre235vtolojh4g403ep" + ".apps.googleusercontent.com"
CLIENT_SECRET = "GOCSPX-" + "K58FWR486LdLJ1mLB8sXC4z6qDAf"
ENDPOINT = "https://daily-cloudcode-pa.sandbox.googleapis.com"
REDIRECT_URI = "http://localhost:51121/oauth-callback"
SCOPES = "https://www.googleapis.com/auth/cloud-platform https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile"

# Token & Project Cache
_token_cache = {}  # email -> token
_project_cache = {}  # email -> project_id
_cooldown_cache = {} # "email:family" -> timestamp until cooldown expires
_consecutive_failures = {} # "email:family" -> int count
_cache_lock = threading.Lock()

# ── Auth & Account Helpers ────────────────────────────────────
def get_accounts_file_path():
    path = os.path.expanduser('~/AppData/Local/hermes/antigravity-accounts.json')
    if not os.path.exists(path):
        # Fallback to OpenCode path
        opencode_path = os.path.expanduser('~/.config/opencode/antigravity-accounts.json')
        if not os.path.exists(opencode_path):
            appdata = os.environ.get('APPDATA')
            if appdata:
                opencode_path = os.path.join(appdata, 'opencode', 'antigravity-accounts.json')
        if os.path.exists(opencode_path):
            return opencode_path
    return path

def load_accounts_data():
    path = get_accounts_file_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"version": 4, "accounts": [], "activeIndex": 0, "activeIndexByFamily": {"claude": 0, "gemini": 0}}

def save_accounts_data(data):
    path = get_accounts_file_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def get_active_account():
    data = load_accounts_data()
    accounts = data.get("accounts", [])
    if not accounts:
        raise ValueError("No accounts configured. Type /antigravity-login in chat to log in.")
        
    active_idx = data.get("activeIndex", 0)
    if active_idx < 0 or active_idx >= len(accounts):
        active_idx = 0
    return accounts[active_idx]

def refresh_token(ref_token):
    url = "https://oauth2.googleapis.com/token"
    data = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": ref_token,
        "grant_type": "refresh_token"
    }).encode("utf-8")
    
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req) as resp:
        res_data = json.loads(resp.read().decode("utf-8"))
        return res_data["access_token"]

def load_project_id(access_token):
    url = f"{ENDPOINT}/v1internal:loadCodeAssist"
    body = json.dumps({
        "metadata": {
            "ideType": "ANTIGRAVITY",
            "platform": "PLATFORM_UNSPECIFIED",
            "pluginType": "GEMINI"
        }
    }).encode("utf-8")
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": "google-api-nodejs-client/9.15.1",
        "X-Goog-Api-Client": "google-cloud-sdk vscode_cloudshelleditor/0.1",
        "Client-Metadata": '{"ideType":"ANTIGRAVITY","platform":"PLATFORM_UNSPECIFIED","pluginType":"GEMINI"}'
    }
    
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req) as resp:
        res_data = json.loads(resp.read().decode("utf-8"))
        project_field = res_data.get("cloudaicompanionProject")
        if isinstance(project_field, dict):
            return project_field.get("id")
        return project_field

def get_auth_credentials(account):
    email = account.get("email", "")
    with _cache_lock:
        token = _token_cache.get(email)
        project_id = _project_cache.get(email)
        
    if not token:
        token = refresh_token(account["refreshToken"])
        project_id = load_project_id(token)
        with _cache_lock:
            _token_cache[email] = token
            _project_cache[email] = project_id
            
    return token, project_id

# ── Model Mapping ─────────────────────────────────────────────
MODEL_MAPPING = {
    # Standard mappings
    "claude-3-5-sonnet-latest": "claude-sonnet-4-6-thinking",
    "claude-3-5-sonnet-20241022": "claude-sonnet-4-6-thinking",
    "claude-3-5-sonnet-20240620": "claude-sonnet-4-6",
    "claude-3-opus-20240229": "claude-opus-4-6-thinking",
    "claude-3-5-haiku-latest": "claude-sonnet-4-6",
    "gemini-3.5-flash": "gemini-3.5-flash-low",
    "gemini-3-flash": "gemini-3-flash",
    
    # Direct Antigravity mappings
    "claude-opus-4-6-thinking": "claude-opus-4-6-thinking",
    "claude-opus-4-6": "claude-opus-4-6-thinking",
    "claude-sonnet-4-6-thinking": "claude-sonnet-4-6-thinking",
    "claude-sonnet-4-6": "claude-sonnet-4-6",
    "gemini-3.1-pro-high": "gemini-3.1-pro-high",
    "gemini-3.1-pro-low": "gemini-3.1-pro-low",
}

def translate_openai_to_gemini(messages):
    contents = []
    for msg in messages:
        role = msg.get("role", "user")
        if role == "assistant":
            role = "model"
        elif role == "system":
            role = "user"
            
        content = msg.get("content", "")
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    parts.append({"text": part.get("text", "")})
            contents.append({"role": role, "parts": parts})
        else:
            contents.append({"role": role, "parts": [{"text": str(content)}]})
            
    return contents

# ── Proxy HTTP Handler ─────────────────────────────────────────
class AntigravityProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/v1/models" or self.path == "/models":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            
            models = []
            for oai in MODEL_MAPPING.keys():
                models.append({
                    "id": oai,
                    "object": "model",
                    "created": 1782210769,
                    "owned_by": "antigravity"
                })
            
            self.wfile.write(json.dumps({"object": "list", "data": models}).encode("utf-8"))
            return
            
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path != "/v1/chat/completions" and self.path != "/chat/completions":
            self.send_response(404)
            self.end_headers()
            return
            
        # Parse body
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        req_json = json.loads(post_data.decode('utf-8'))
        
        # Load all accounts to enable rotation
        data = load_accounts_data()
        accounts = data.get("accounts", [])
        if not accounts:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "No accounts configured. Type /antigravity-login in chat."}).encode("utf-8"))
            return
            
        active_idx = data.get("activeIndex", 0)
        if active_idx < 0 or active_idx >= len(accounts):
            active_idx = 0
            
        # Resolve model
        req_model = req_json.get("model", "gemini-3.5-flash")
        is_claude = "claude" in req_model.lower()
        family = "claude" if is_claude else "gemini"
        mapped_model = MODEL_MAPPING.get(req_model, "gemini-3.5-flash-low")
        
        success = False
        last_err = None
        
        # Rotate through accounts starting from the active one
        for offset in range(len(accounts)):
            idx = (active_idx + offset) % len(accounts)
            account = accounts[idx]
            email = account.get("email", "")
            
            if not account.get("enabled", True):
                continue
                
            # Check family-specific isolated cooldown
            cooldown_key = f"{email}:{family}"
            with _cache_lock:
                cooldown_until = _cooldown_cache.get(cooldown_key, 0)
            if time.time() < cooldown_until:
                continue
                
            try:
                token, project_id = get_auth_credentials(account)
            except Exception as e:
                last_err = f"Auth error on {email}: {str(e)}"
                continue
                
            # Translate body
            gemini_contents = translate_openai_to_gemini(req_json.get("messages", []))
            
            stream = req_json.get("stream", False)
            action = "streamGenerateContent" if stream else "generateContent"
            
            url = f"{ENDPOINT}/v1internal:{action}"
            if stream:
                url += "?alt=sse"
                
            gemini_body = {
                "contents": gemini_contents,
                "generationConfig": {
                    "temperature": req_json.get("temperature", 0.7),
                }
            }
            
            wrapped_body = json.dumps({
                "project": project_id,
                "model": mapped_model,
                "request": gemini_body
            }).encode("utf-8")
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "antigravity/windows/amd64",
                "X-Goog-Api-Client": "google-cloud-sdk vscode_cloudshelleditor/0.1",
                "Client-Metadata": '{"ideType":"ANTIGRAVITY","platform":"PLATFORM_UNSPECIFIED","pluginType":"GEMINI"}'
            }
            
            try:
                req = urllib.request.Request(url, data=wrapped_body, headers=headers)
                resp = urllib.request.urlopen(req, timeout=30)
                
                success = True
                
                # Reset consecutive failures count on success
                with _cache_lock:
                    _consecutive_failures[cooldown_key] = 0
                
                # Update active index on success to keep it sticky
                if idx != active_idx:
                    data["activeIndex"] = idx
                    data["activeIndexByFamily"] = {"claude": idx, "gemini": idx}
                    save_accounts_data(data)
                
                break
            except urllib.error.HTTPError as he:
                status_code = he.code
                err_text = he.read().decode('utf-8', errors='ignore')
                last_err = f"Upstream HTTP {status_code} on {email}: {err_text}"
                
                # If rate limited (429) or forbidden (403), cooldown this family on this account
                if status_code in (429, 403):
                    with _cache_lock:
                        # Increment consecutive failures
                        failures = _consecutive_failures.get(cooldown_key, 0) + 1
                        _consecutive_failures[cooldown_key] = failures
                        
                        # Apply exponential backoff cooldown
                        if failures == 1:
                            cooldown_duration = 60      # 1 minute
                        elif failures == 2:
                            cooldown_duration = 300     # 5 minutes
                        elif failures == 3:
                            cooldown_duration = 1800    # 30 minutes
                        else:
                            cooldown_duration = 7200    # 2 hours
                            
                        _cooldown_cache[cooldown_key] = time.time() + cooldown_duration
                        
                        # Clear cached credentials to force fresh reload next time on error
                        if email in _token_cache: del _token_cache[email]
                        if email in _project_cache: del _project_cache[email]
                    print(f"[Proxy] Account {email} got HTTP {status_code} on {family} (consecutive failures: {failures}), {cooldown_duration}s cooldown applied.")
                continue
            except Exception as e:
                last_err = f"Request error on {email}: {str(e)}"
                continue
                
        if not success:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"All accounts failed. Last error: {last_err}"}).encode("utf-8"))
            return

        if stream:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            
            buffer = ""
            while True:
                chunk = resp.read(1024)
                if not chunk:
                    break
                buffer += chunk.decode('utf-8')
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if line.startswith("data:"):
                        try:
                            data_str = line[5:].strip()
                            if not data_str:
                                continue
                            gemini_data = json.loads(data_str)
                            response_obj = gemini_data.get("response", {})
                            candidates = response_obj.get("candidates", [])
                            text = ""
                            finish_reason = None
                            if candidates:
                                text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                                raw_reason = candidates[0].get("finishReason")
                                if raw_reason == "STOP":
                                    finish_reason = "stop"
                                
                            if text or finish_reason:
                                # Translate to OpenAI chunk
                                chunk_json = {
                                    "choices": [
                                        {
                                            "delta": {"content": text} if text else {},
                                            "index": 0,
                                            "finish_reason": finish_reason
                                        }
                                    ]
                                }
                                self.wfile.write(f"data: {json.dumps(chunk_json)}\n\n".encode("utf-8"))
                                self.wfile.flush()
                        except Exception as parse_err:
                            pass
            
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        else:
            res_data = json.loads(resp.read().decode("utf-8"))
            response_obj = res_data.get("response", {})
            candidates = response_obj.get("candidates", [])
            text = ""
            if candidates:
                text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                
            openai_resp = {
                "id": "chatcmpl-mock",
                "object": "chat.completion",
                "created": 1782210769,
                "model": req_model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": text
                        },
                        "finish_reason": "stop"
                    }
                ]
            }
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(openai_resp).encode("utf-8"))

# ── Background Server Thread ──────────────────────────────────
def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def start_background_proxy():
    if is_port_in_use(PROXY_PORT):
        return
        
    def run():
        try:
            server = HTTPServer(('127.0.0.1', PROXY_PORT), AntigravityProxyHandler)
            server.serve_forever()
        except Exception:
            pass
            
    t = threading.Thread(target=run, daemon=True)
    t.start()

# Launch proxy immediately
start_background_proxy()

# ── Interactive CLI & OAuth Manager ─────────────────────────
auth_code = None
server_instance = None

class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        global auth_code
        parsed_url = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed_url.query)
        
        if "code" in query:
            auth_code = query["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"""
            <html>
                <body style="font-family: sans-serif; text-align: center; padding-top: 50px;">
                    <h2 style="color: #2e7d32;">Authentication Successful!</h2>
                    <p>You can close this tab and return to the terminal.</p>
                </body>
            </html>
            """)
            threading.Thread(target=lambda: server_instance.shutdown()).start()
        else:
            self.send_response(400)
            self.end_headers()

def start_local_server():
    global server_instance
    handler = OAuthCallbackHandler
    socketserver.TCPServer.allow_reuse_address = True
    server_instance = socketserver.TCPServer(("127.0.0.1", 51121), handler)
    server_instance.serve_forever()

def perform_oauth_flow():
    global auth_code
    auth_code = None
    
    t = threading.Thread(target=start_local_server)
    t.start()
    
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent"
    }
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    
    print("\nOpening browser for Google login...")
    webbrowser.open(auth_url)
    
    print("Waiting for callback on port 51121 (timeout 60s)...")
    t.join(timeout=60)
    
    return auth_code

def exchange_code_for_tokens(code):
    url = "https://oauth2.googleapis.com/token"
    data = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }).encode("utf-8")
    
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def fetch_user_email(access_token):
    url = "https://www.googleapis.com/oauth2/v2/userinfo"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data.get("email")

def run_login_silent():
    code = perform_oauth_flow()
    if not code:
        return "Login failed: OAuth timeout or cancelled."
        
    try:
        tokens = exchange_code_for_tokens(code)
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        email = fetch_user_email(access_token)
        
        if not email:
            return "Login failed: could not fetch user email."
            
        data = load_accounts_data()
        accounts = data.get("accounts", [])
        
        existing_idx = next((i for i, a in enumerate(accounts) if a.get("email") == email), None)
        import time
        now_ms = int(time.time() * 1000)
        
        account_entry = {
            "email": email,
            "refreshToken": refresh_token,
            "addedAt": now_ms,
            "lastUsed": now_ms,
            "enabled": True
        }
        
        if existing_idx is not None:
            accounts[existing_idx] = account_entry
            msg = f"Account {email} updated successfully!"
        else:
            accounts.append(account_entry)
            msg = f"Account {email} added successfully!"
            
        new_idx = existing_idx if existing_idx is not None else len(accounts) - 1
        data["activeIndex"] = new_idx
        data["activeIndexByFamily"] = {"claude": new_idx, "gemini": new_idx}
        data["accounts"] = accounts
        save_accounts_data(data)
        
        with _cache_lock:
            _token_cache[email] = access_token
            _project_cache[email] = load_project_id(access_token)
            
        return f"✓ {msg} It is now set as the active account for Hermes Agent."
    except Exception as e:
        return f"✗ Login error: {str(e)}"

def run_login():
    code = perform_oauth_flow()
    if not code:
        print("Login failed.")
        return
        
    try:
        tokens = exchange_code_for_tokens(code)
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        email = fetch_user_email(access_token)
        
        if not email:
            print("Failed to fetch user email.")
            return
            
        data = load_accounts_data()
        accounts = data.get("accounts", [])
        
        existing_idx = next((i for i, a in enumerate(accounts) if a.get("email") == email), None)
        import time
        now_ms = int(time.time() * 1000)
        
        account_entry = {
            "email": email,
            "refreshToken": refresh_token,
            "addedAt": now_ms,
            "lastUsed": now_ms,
            "enabled": True
        }
        
        if existing_idx is not None:
            accounts[existing_idx] = account_entry
            print(f"\nAccount {email} updated successfully!")
        else:
            accounts.append(account_entry)
            print(f"\nAccount {email} added successfully!")
            
        data["accounts"] = accounts
        save_accounts_data(data)
    except Exception as e:
        print(f"\nError during login: {str(e)}")

def run_list_and_select():
    data = load_accounts_data()
    accounts = data.get("accounts", [])
    if not accounts:
        print("\nNo accounts configured.")
        return
        
    active_idx = data.get("activeIndex", 0)
    
    print("\nConfigured Accounts:")
    for idx, acc in enumerate(accounts):
        marker = "-> " if idx == active_idx else "   "
        status = "enabled" if acc.get("enabled", True) else "disabled"
        print(f"{marker}{idx + 1}. {acc.get('email')} ({status})")
        
    choice = input("\nEnter account index to select active, or press Enter to cancel: ").strip()
    if not choice:
        return
        
    try:
        idx = int(choice) - 1
        if idx >= 0 and idx < len(accounts):
            data["activeIndex"] = idx
            data["activeIndexByFamily"] = {"claude": idx, "gemini": idx}
            save_accounts_data(data)
            print(f"Selected active account: {accounts[idx].get('email')}")
        else:
            print("Invalid index.")
    except ValueError:
        print("Invalid input.")

def run_remove():
    data = load_accounts_data()
    accounts = data.get("accounts", [])
    if not accounts:
        print("\nNo accounts configured.")
        return
        
    print("\nAccounts:")
    for idx, acc in enumerate(accounts):
        print(f"  {idx + 1}. {acc.get('email')}")
        
    choice = input("\nEnter account index to remove, or press Enter to cancel: ").strip()
    if not choice:
        return
        
    try:
        idx = int(choice) - 1
        if idx >= 0 and idx < len(accounts):
            removed = accounts.pop(idx)
            active_idx = data.get("activeIndex", 0)
            if active_idx >= len(accounts):
                active_idx = max(0, len(accounts) - 1)
            data["activeIndex"] = active_idx
            data["activeIndexByFamily"] = {"claude": active_idx, "gemini": active_idx}
            data["accounts"] = accounts
            save_accounts_data(data)
            print(f"Removed account: {removed.get('email')}")
        else:
            print("Invalid index.")
    except ValueError:
        print("Invalid input.")

def get_quota_summary_string(email, access_token, project_id):
    url = f"{ENDPOINT}/v1internal:retrieveUserQuotaSummary"
    body = json.dumps({"project": project_id}).encode("utf-8")
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": "antigravity/windows/amd64",
        "X-Goog-Api-Client": "google-cloud-sdk vscode_cloudshelleditor/0.1",
        "Client-Metadata": '{"ideType":"ANTIGRAVITY","platform":"PLATFORM_UNSPECIFIED","pluginType":"GEMINI"}'
    }
    
    lines = []
    try:
        req = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            
            def format_duration(target_str):
                if not target_str: return "N/A"
                try:
                    from datetime import datetime, timezone
                    target = datetime.fromisoformat(target_str.replace("Z", "+00:00"))
                    now = datetime.now(timezone.utc)
                    delta = target - now
                    if delta.total_seconds() <= 0: return "now"
                    hours = int(delta.total_seconds() // 3600)
                    minutes = int((delta.total_seconds() % 3600) // 60)
                    if hours >= 24:
                        return f"{hours // 24}d {hours % 24}h"
                    if hours > 0:
                        return f"{hours}h {minutes}m"
                    return f"{minutes}m"
                except Exception:
                    return target_str
            
            for group in data.get("groups", []):
                lines.append(f"\n  [{group.get('displayName')}]")
                buckets = group.get("buckets", [])
                for bucket in buckets:
                    if bucket.get("disabled"):
                        lines.append(f"  - {bucket.get('displayName')}: N/A (does not apply)")
                    else:
                        pct = int(bucket.get("remainingFraction", 0) * 100)
                        reset_in = format_duration(bucket.get("resetTime"))
                        lines.append(f"  - {bucket.get('displayName')}: {pct}% (resets: {reset_in})")
    except Exception as e:
        lines.append(f"  Failed to fetch quota: {str(e)}")
    return "\n".join(lines)

def run_quota_silent():
    data = load_accounts_data()
    accounts = data.get("accounts", [])
    if not accounts:
        return "No accounts configured."
        
    outputs = []
    for acc in accounts:
        email = acc.get("email")
        disabled_str = " (disabled)" if not acc.get("enabled", True) else ""
        outputs.append(f"Account: {email}{disabled_str}")
        try:
            token = refresh_token(acc["refreshToken"])
            project_id = load_project_id(token)
            summary = get_quota_summary_string(email, token, project_id)
            outputs.append(summary)
        except Exception as e:
            outputs.append(f"  Error: {str(e)}")
        outputs.append("-" * 35)
    return "\n".join(outputs)

def fetch_and_print_quota_summary(email, access_token, project_id):
    url = f"{ENDPOINT}/v1internal:retrieveUserQuotaSummary"
    body = json.dumps({"project": project_id}).encode("utf-8")
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": "antigravity/windows/amd64",
        "X-Goog-Api-Client": "google-cloud-sdk vscode_cloudshelleditor/0.1",
        "Client-Metadata": '{"ideType":"ANTIGRAVITY","platform":"PLATFORM_UNSPECIFIED","pluginType":"GEMINI"}'
    }
    
    try:
        req = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            
            def format_duration(target_str):
                if not target_str: return "N/A"
                try:
                    from datetime import datetime, timezone
                    target = datetime.fromisoformat(target_str.replace("Z", "+00:00"))
                    now = datetime.now(timezone.utc)
                    delta = target - now
                    if delta.total_seconds() <= 0: return "now"
                    hours = int(delta.total_seconds() // 3600)
                    minutes = int((delta.total_seconds() % 3600) // 60)
                    if hours >= 24:
                        return f"{hours // 24}d {hours % 24}h"
                    if hours > 0:
                        return f"{hours}h {minutes}m"
                    return f"{minutes}m"
                except Exception:
                    return target_str
            
            for group in data.get("groups", []):
                print(f"\n  ┌─ {group.get('displayName')}")
                buckets = group.get("buckets", [])
                for b_idx, bucket in enumerate(buckets):
                    connector = "└─" if b_idx == len(buckets) - 1 else "├─"
                    if bucket.get("disabled"):
                        print(f"  │  {connector} {bucket.get('displayName').ljust(20)} N/A (does not apply)")
                    else:
                        pct = int(bucket.get("remainingFraction", 0) * 100)
                        reset_in = format_duration(bucket.get("resetTime"))
                        print(f"  │  {connector} {bucket.get('displayName').ljust(20)} {pct}% (resets: {reset_in})")
    except Exception as e:
        print(f"  ❌ Failed to fetch quota: {str(e)}")

def run_quota():
    data = load_accounts_data()
    accounts = data.get("accounts", [])
    if not accounts:
        print("\nNo accounts configured.")
        return
        
    print("\n📊 Checking quotas for all accounts...")
    for idx, acc in enumerate(accounts):
        email = acc.get("email")
        disabled_str = " (disabled)" if not acc.get("enabled", True) else ""
        print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"  {email}{disabled_str}")
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        try:
            token = refresh_token(acc["refreshToken"])
            project_id = load_project_id(token)
            fetch_and_print_quota_summary(email, token, project_id)
        except Exception as e:
            print(f"  ❌ Error: {str(e)}")
    print("")

def run_interactive_menu():
    while True:
        print("\n" + "="*45)
        print("     Google Antigravity Accounts Manager")
        print("="*45)
        print("  1. List accounts / Select active account")
        print("  2. Log in a new account (OAuth)")
        print("  3. Check quotas for all accounts")
        print("  4. Remove an account")
        print("  5. Exit")
        print("="*45)
        
        choice = input("\nChoose option: ").strip()
        if choice == "1":
            run_list_and_select()
        elif choice == "2":
            run_login()
        elif choice == "3":
            run_quota()
        elif choice == "4":
            run_remove()
        elif choice == "5":
            break
        else:
            print("Invalid option.")

def handle_cli(args):
    cmd = getattr(args, "antigravity_command", None)
    if cmd == "login":
        run_login()
    elif cmd == "list":
        run_list_and_select()
    elif cmd == "remove":
        run_remove()
    elif cmd == "quota":
        run_quota()
    else:
        run_interactive_menu()

def setup_argparse(subparser):
    subs = subparser.add_subparsers(dest="antigravity_command")
    subs.add_parser("login", help="Log in a new Google Antigravity account")
    subs.add_parser("list", help="List and select active account")
    subs.add_parser("remove", help="Remove a configured account")
    subs.add_parser("quota", help="Check live quotas for all accounts")

def handle_slash_command(raw_args: str) -> str:
    import subprocess
    print("\nLaunching Google Antigravity Accounts Manager in a new terminal window...")
    try:
        # Spawn a new powershell window running 'hermes antigravity-mrhisyammm'
        subprocess.Popen('start powershell -Command "hermes antigravity-mrhisyammm"', shell=True)
        return "✓ Google Antigravity Accounts Manager opened in a new terminal window. Manage your accounts there, then return here."
    except Exception as e:
        return f"✗ Failed to open terminal window: {str(e)}\nPlease run 'hermes antigravity-mrhisyammm' manually in a new terminal."

def _mock_pre_llm_call(*args, **kwargs):
    return None

def handle_login_slash(raw_args: str) -> str:
    return run_login_silent()

def handle_quota_slash(raw_args: str) -> str:
    return run_quota_silent()

def register(ctx):
    # Register the CLI subcommand tree
    ctx.register_cli_command(
        name="antigravity-mrhisyammm",
        help="Manage Google Antigravity accounts and quotas",
        setup_fn=setup_argparse,
        handler_fn=handle_cli
    )
    # Register the in-session slash command /antigravity (spawns external terminal)
    ctx.register_command(
        "antigravity-mrhisyammm",
        handler=handle_slash_command,
        description="Open the Google Antigravity accounts manager in a new external terminal window"
    )
    # Register the in-session slash command /antigravity-login (direct login)
    ctx.register_command(
        "antigravity-mrhisyammm-login",
        handler=handle_login_slash,
        description="Directly log in a new Google Antigravity account (Works in Desktop GUI & CLI)"
    )
    # Register the in-session slash command /antigravity-quota (direct print quota)
    ctx.register_command(
        "antigravity-mrhisyammm-quota",
        handler=handle_quota_slash,
        description="Directly display quota summary (Works in Desktop GUI & CLI)"
    )
    # Register the hook declared in plugin.yaml to pass validation
    ctx.register_hook("pre_llm_call", _mock_pre_llm_call)
