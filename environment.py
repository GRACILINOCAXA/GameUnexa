# -*- coding: utf-8 -*-
"""
Environment detection and feature availability for GameUnexa ZERO-CONFIG VERCEL.

Provides clear separation between:
- Windows/Desktop (Hydra, local executables, file system access)
- Web/Vercel (serverless API)

All Windows-specific code is disabled on Vercel.
"""

import os
import sys
from typing import Optional

IS_WINDOWS = os.name == 'nt'
IS_VERCEL = os.environ.get('VERCEL') == '1'
IS_DEV = os.environ.get('FLASK_ENV', '').lower() in {'development', 'dev'}


class EnvironmentProfile:
    """Determines which environment we're running in."""

    def __init__(self):
        self.is_windows_desktop = IS_WINDOWS and not IS_VERCEL
        self.is_vercel_web = IS_VERCEL
        self.is_linux_desktop = not IS_WINDOWS and not IS_VERCEL
        self.is_development = IS_DEV or self.is_windows_desktop or self.is_linux_desktop

    def is_desktop(self) -> bool:
        """Running on desktop (Windows/Linux)."""
        return self.is_windows_desktop or self.is_linux_desktop

    def is_web(self) -> bool:
        """Running on Vercel (serverless)."""
        return self.is_vercel_web

    def supports_local_files(self) -> bool:
        """Can access persistent local file system."""
        return self.is_desktop()

    def supports_local_executables(self) -> bool:
        """Can launch local Windows executables."""
        return self.is_windows_desktop

    def supports_hydra(self) -> bool:
        """Can use Hydra game launcher (Windows only)."""
        return self.is_windows_desktop

    def supports_steam_launcher(self) -> bool:
        """Can interact with Steam launcher (desktop only)."""
        return self.is_desktop()

    def supports_subprocess(self) -> bool:
        """Can spawn subprocesses (not recommended on serverless)."""
        return self.is_desktop()

    def supports_background_tasks(self) -> bool:
        """Can run long-running background tasks."""
        return self.is_desktop()


# Singleton instance
_environment: Optional[EnvironmentProfile] = None


def get_environment() -> EnvironmentProfile:
    """Get the current environment profile."""
    global _environment
    if _environment is None:
        _environment = EnvironmentProfile()
    return _environment


def get_env() -> EnvironmentProfile:
    """Alias for get_environment()."""
    return get_environment()


# Helper functions for feature checks
def is_desktop() -> bool:
    """Running on desktop environment."""
    return get_environment().is_desktop()


def is_web() -> bool:
    """Running on Vercel or serverless."""
    return get_environment().is_web()


def can_access_files() -> bool:
    """Can access persistent local file system."""
    return get_environment().supports_local_files()


def can_execute_programs() -> bool:
    """Can execute local programs/executables."""
    return get_environment().supports_local_executables()


def can_use_hydra() -> bool:
    """Can use Hydra game launcher."""
    return get_environment().supports_hydra()


def can_use_steam_launcher() -> bool:
    """Can interact with Steam."""
    return get_environment().supports_steam_launcher()


def should_scan_local_games() -> bool:
    """Should scan computer for installed games."""
    return is_desktop()


def should_use_subprocess() -> bool:
    """Should use subprocess (spawning child processes)."""
    return is_desktop()


def should_run_background_jobs() -> bool:
    """Should run background jobs."""
    return is_desktop()


class FeatureAvailability:
    """Check if specific features are available."""

    @staticmethod
    def hydra() -> bool:
        """Hydra game launcher integration."""
        if not can_use_hydra():
            return False
        # Check if Hydra config exists
        try:
            from modelos.usuario import Usuario
            # Could add additional Hydra availability check
            return True
        except Exception:
            return False

    @staticmethod
    def steam() -> bool:
        """Steam integration (optional)."""
        if not can_use_steam_launcher():
            return False
        # Check if Steam API key is provided
        return bool(os.environ.get('STEAM_API_KEY', '').strip())

    @staticmethod
    def background_scanning() -> bool:
        """Background game library scanning."""
        return is_desktop()

    @staticmethod
    def local_game_launching() -> bool:
        """Launching local games."""
        return can_execute_programs()

    @staticmethod
    def file_uploads() -> bool:
        """File upload support."""
        return True  # Should work on both

    @staticmethod
    def email_notifications() -> bool:
        """Email notification support."""
        return True  # Database-driven, works everywhere

    @staticmethod
    def friend_system() -> bool:
        """Friend system."""
        return True  # Database-driven, works everywhere

    @staticmethod
    def messaging() -> bool:
        """User messaging."""
        return True  # Database-driven, works everywhere

    @staticmethod
    def posts_and_comments() -> bool:
        """Posts and comments social features."""
        return True  # Database-driven, works everywhere


def ensure_vercel_safe(operation_name: str, capability: bool) -> None:
    """
    Verify that an operation is safe for current environment.

    Raises:
        RuntimeError: If operation is not safe for current environment
    """
    if not capability and is_web():
        raise RuntimeError(
            f"Operation '{operation_name}' is not available on Vercel. "
            f"This feature requires desktop environment."
        )


def log_environment() -> None:
    """Log current environment details for debugging."""
    env = get_environment()
    print("[ENVIRONMENT]")
    print(f"  Windows Desktop: {env.is_windows_desktop}")
    print(f"  Vercel Web: {env.is_vercel_web}")
    print(f"  Linux Desktop: {env.is_linux_desktop}")
    print(f"  Development: {env.is_development}")
    print(f"  Local Files: {env.supports_local_files()}")
    print(f"  Executables: {env.supports_local_executables()}")
    print(f"  Hydra: {env.supports_hydra()}")
    print(f"  Steam: {env.supports_steam_launcher()}")
