# -*- coding: utf-8 -*-
"""
SECRET_KEY management for GameUnexa ZERO-CONFIG VERCEL.

Provides automatic generation and persistence of SECRET_KEY
for maintaining session consistency in serverless environment.
"""

import os
import secrets
import base64
from pathlib import Path
from typing import Optional
from datetime import datetime


class SecretKeyManager:
    """Manages SECRET_KEY generation and persistence."""

    SECRET_KEY_FILE = '.gameunexa_secret'
    
    def __init__(self):
        self.is_vercel = os.environ.get('VERCEL') == '1'
        self.is_windows = os.name == 'nt'
        self._secret_key: Optional[str] = None

    def _get_secret_key_path(self) -> Path:
        """
        Get the path where SECRET_KEY should be stored.

        On Vercel: Uses environment variable if available
        On Windows: Uses AppData directory
        On Linux: Uses home directory
        """
        # First, check if there's an environment variable
        env_secret = os.environ.get('SECRET_KEY', '').strip()
        if env_secret:
            return None  # Signal that we should use env var directly

        if self.is_vercel:
            # On Vercel, we create a file in /tmp (ephemeral)
            # But the SECRET_KEY should be provided via environment
            # if persistence is needed
            return None

        if self.is_windows:
            app_data = Path(os.environ.get('LOCALAPPDATA', 
                          Path.home() / 'AppData' / 'Local'))
            config_dir = app_data / 'GameUnexa' / 'config'
        else:
            config_dir = Path.home() / '.gameunexa' / 'config'

        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / self.SECRET_KEY_FILE

    def _generate_secret_key(self) -> str:
        """Generate a cryptographically secure SECRET_KEY."""
        # Generate 32 bytes of random data
        random_bytes = secrets.token_bytes(32)
        # Encode as base64 for use as string
        return base64.urlsafe_b64encode(random_bytes).decode('utf-8')

    def _load_or_create_secret_key(self) -> str:
        """
        Load SECRET_KEY from persistent storage or create new one.

        For Vercel: Returns a stable key for the deployment
        For local: Persists key to disk for development consistency
        """
        # Check environment variable first
        env_secret = os.environ.get('SECRET_KEY', '').strip()
        if env_secret:
            return env_secret

        secret_path = self._get_secret_key_path()
        
        # On Vercel without env var configured, use fallback
        if secret_path is None:
            if self.is_vercel:
                # Generate a deterministic key based on deployment data
                # This won't change during the same deployment
                seed = os.environ.get('VERCEL_DEPLOYMENT_ID', 'default-deployment')
                # Create a stable but unique key
                return base64.urlsafe_b64encode(
                    (seed + '-stable-secret-key-' + str(datetime.now().date())).encode()
                ).decode('utf-8')
            return None

        # Try to load existing secret key
        if secret_path.exists():
            try:
                with open(secret_path, 'r', encoding='utf-8') as f:
                    stored_key = f.read().strip()
                    if stored_key and len(stored_key) > 20:
                        return stored_key
            except Exception as e:
                print(f"Warning: Could not read SECRET_KEY from {secret_path}: {e}")

        # Generate and store new SECRET_KEY
        new_key = self._generate_secret_key()
        try:
            with open(secret_path, 'w', encoding='utf-8') as f:
                f.write(new_key)
            # Restrict permissions on Unix
            if hasattr(secret_path, 'chmod'):
                secret_path.chmod(0o600)
        except Exception as e:
            print(f"Warning: Could not persist SECRET_KEY to {secret_path}: {e}")
            print("Using runtime-only key (sessions may not persist)")

        return new_key

    def get_secret_key(self) -> str:
        """Get the SECRET_KEY, generating if necessary."""
        if self._secret_key is None:
            self._secret_key = self._load_or_create_secret_key()
        return self._secret_key


# Singleton instance
_secret_manager: Optional[SecretKeyManager] = None


def get_secret_key() -> str:
    """Get or generate the SECRET_KEY for Flask."""
    global _secret_manager
    if _secret_manager is None:
        _secret_manager = SecretKeyManager()
    return _secret_manager.get_secret_key()


def ensure_secret_key() -> str:
    """Ensure SECRET_KEY is configured and return it."""
    key = get_secret_key()
    if not key:
        raise RuntimeError(
            "Could not generate or retrieve SECRET_KEY. "
            "Please set the SECRET_KEY environment variable."
        )
    return key
