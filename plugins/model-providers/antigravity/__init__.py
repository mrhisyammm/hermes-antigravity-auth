from providers import register_provider
from providers.base import ProviderProfile

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

class AntigravityProfile(ProviderProfile):
    def fetch_models(self, *, api_key=None, timeout=8.0):
        return list(MODEL_MAPPING.keys())

antigravity = AntigravityProfile(
    name="antigravity",
    aliases=("agy",),
    display_name="Google Antigravity",
    description="Query Gemini and Claude models directly using your Google OAuth accounts pool",
    signup_url="https://github.com/mrhisyammm/opencode-antigravity-auth",
    env_vars=("ANTIGRAVITY_API_KEY", "ANTIGRAVITY_BASE_URL"),
    base_url="http://127.0.0.1:8999/v1",
    auth_type="api_key",
    default_aux_model="gemini-3.5-flash",
    fallback_models=tuple(MODEL_MAPPING.keys()),
)

register_provider(antigravity)
