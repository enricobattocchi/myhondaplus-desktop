"""Application session and persistence orchestration."""

from pymyhondaplus import HondaAPI, HondaAuth, get_storage

from .config import Settings, device_key_file, token_file


class AppSession:
    """Owns settings, credential storage, and authenticated API state."""

    def __init__(self, settings: Settings | None = None, storage=None, api: HondaAPI | None = None):
        self.settings = settings or Settings.load()
        self.storage = storage or self._build_storage()
        self.api = api or HondaAPI(storage=self.storage)

    @staticmethod
    def _build_storage():
        token_path = token_file()
        device_key_path = device_key_file()
        token_path.parent.mkdir(parents=True, exist_ok=True)
        device_key_path.parent.mkdir(parents=True, exist_ok=True)
        return get_storage(token_path, device_key_path)

    def restore_authenticated_session(self) -> bool:
        """Refresh an expired session when possible and report if it is usable."""
        if not self.api.tokens.access_token:
            return False
        if self.api.tokens.is_expired and self.api.tokens.refresh_token:
            try:
                self.api.refresh_auth()
            except Exception:
                return False
        return not self.api.tokens.is_expired

    def apply_login_tokens(self, tokens: dict):
        """Persist tokens received from the login flow."""
        user_id = HondaAuth.extract_user_id(tokens["access_token"])
        self.api.set_tokens(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            expires_in=tokens.get("expires_in", 3599),
            user_id=user_id,
        )

    def reset(self) -> HondaAPI:
        """Clear persisted auth state and replace the API client."""
        self.storage.clear()
        self.api = HondaAPI(storage=self.storage)
        return self.api

    def save_settings(self):
        self.settings.save()
