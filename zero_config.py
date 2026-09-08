# -*- coding: utf-8 -*-
"""
GameUnexa ZERO-CONFIG VERCEL initialization.

This module provides automatic startup and initialization
for zero-configuration deployment on Vercel.
"""

import os
import sys
from typing import Optional

# Import the zero-config systems
try:
    from db_config import get_db_config, is_postgresql_available
    from db_initializer import ensure_database_initialized
    from secret_key_manager import ensure_secret_key
    from environment import get_environment, log_environment
except ImportError as e:
    print(f"[STARTUP ERROR] Failed to import zero-config modules: {e}")
    sys.exit(1)


class GameUnexaZeroConfig:
    """Main orchestrator for zero-config Vercel startup."""

    def __init__(self):
        self.db_config = None
        self.secret_key = None
        self.environment = None
        self.initialized = False
        self.errors = []

    def initialize(self) -> bool:
        """
        Perform full zero-config initialization.

        Returns:
            True if successful, False otherwise
        """
        if self.initialized:
            return True

        try:
            print("\n" + "="*60)
            print("GameUnexa ZERO-CONFIG VERCEL Initialization")
            print("="*60)

            # Step 1: Detect environment
            self._detect_environment()

            # Step 2: Configure database
            self._configure_database()

            # Step 3: Configure SECRET_KEY
            self._configure_secret_key()

            # Step 4: Initialize database schema
            self._initialize_database_schema()

            self.initialized = True
            self._print_startup_summary()
            return True

        except Exception as e:
            self.errors.append(f"Initialization failed: {e}")
            self._print_errors()
            return False

    def _detect_environment(self) -> None:
        """Detect current environment."""
        print("\n[1] Detecting Environment...")
        self.environment = get_environment()
        
        if self.environment.is_vercel_web:
            print("    ✓ Running on Vercel (Serverless)")
        elif self.environment.is_windows_desktop:
            print("    ✓ Running on Windows Desktop")
        elif self.environment.is_linux_desktop:
            print("    ✓ Running on Linux Desktop")
        else:
            print("    ✓ Running in Development")

    def _configure_database(self) -> None:
        """Configure and detect database."""
        print("\n[2] Configuring Database...")
        self.db_config = get_db_config()

        if self.db_config.is_postgresql():
            print("    ✓ PostgreSQL detected")
            url = self.db_config.config.get('url', '')
            # Don't log full URL for security
            host = self.db_config.config.get('host', '?')
            print(f"    ✓ Host: {host}")
        else:
            print("    ✓ Using SQLite (fallback)")
            path = self.db_config.config.get('path', '')
            print(f"    ✓ Database: {path}")

    def _configure_secret_key(self) -> None:
        """Configure SECRET_KEY."""
        print("\n[3] Configuring SECRET_KEY...")
        try:
            self.secret_key = ensure_secret_key()
            if os.environ.get('SECRET_KEY'):
                print("    ✓ Using environment variable SECRET_KEY")
            else:
                print("    ✓ Generated persistent SECRET_KEY")
                print("    ✓ Sessions will persist across restarts")
        except RuntimeError as e:
            self.errors.append(str(e))
            raise

    def _initialize_database_schema(self) -> None:
        """Initialize database schema."""
        print("\n[4] Initializing Database Schema...")
        if ensure_database_initialized():
            print("    ✓ All tables created successfully")
        else:
            raise RuntimeError("Failed to initialize database schema")

    def _print_startup_summary(self) -> None:
        """Print startup summary."""
        print("\n" + "="*60)
        print("✓ GameUnexa Ready for Deployment")
        print("="*60)
        print(f"Environment: {'Vercel' if self.environment.is_vercel_web else 'Desktop'}")
        print(f"Database: {'PostgreSQL' if self.db_config.is_postgresql() else 'SQLite'}")
        print(f"Initialized: Yes")
        print("="*60 + "\n")

    def _print_errors(self) -> None:
        """Print initialization errors."""
        print("\n" + "="*60)
        print("✗ GameUnexa Initialization Failed")
        print("="*60)
        for error in self.errors:
            print(f"  ERROR: {error}")
        print("="*60 + "\n")

    def get_secret_key(self) -> str:
        """Get SECRET_KEY."""
        if not self.initialized:
            self.initialize()
        return self.secret_key


# Singleton instance
_zero_config_instance: Optional[GameUnexaZeroConfig] = None


def get_zero_config() -> GameUnexaZeroConfig:
    """Get the zero-config instance."""
    global _zero_config_instance
    if _zero_config_instance is None:
        _zero_config_instance = GameUnexaZeroConfig()
    return _zero_config_instance


def initialize_gameunexa() -> bool:
    """Initialize GameUnexa with zero-config system."""
    zero_config = get_zero_config()
    return zero_config.initialize()


def get_configured_secret_key() -> str:
    """Get the initialization SECRET_KEY."""
    zero_config = get_zero_config()
    if not zero_config.initialized:
        zero_config.initialize()
    return zero_config.get_secret_key()
