# -*- coding: utf-8 -*-
"""
Database configuration and auto-detection for GameUnexa ZERO-CONFIG VERCEL.

This module provides automatic database detection and connection management.
Supports both PostgreSQL (Vercel) and SQLite (local development).
"""

import os
import sys
from typing import Optional, Dict, Any
from pathlib import Path


class DatabaseConfig:
    """Automatic database configuration and detection."""

    # Supported database URL environment variable candidates (in priority order)
    ENV_PRIORITY = [
        'DATABASE_URL',
        'POSTGRES_URL',
        'POSTGRES_URL_NON_POOLING',
        'POSTGRES_PRISMA_URL',
        'PGDATABASE',  # Vercel will set these individually
    ]

    # Environment variables for individual PostgreSQL components
    POSTGRES_ENV_VARS = {
        'POSTGRES_HOST': 'host',
        'POSTGRES_USER': 'user',
        'POSTGRES_PASSWORD': 'password',
        'POSTGRES_DB': 'database',
        'PGHOST': 'host',
        'PGUSER': 'user',
        'PGPASSWORD': 'password',
        'PGDATABASE': 'database',
    }

    def __init__(self):
        self.is_vercel = os.environ.get('VERCEL') == '1'
        self.is_windows = os.name == 'nt'
        self.is_development = self._is_development()
        self.db_type = None  # 'postgresql' or 'sqlite'
        self.config = {}

    def _is_development(self) -> bool:
        """Detect if running in development mode."""
        if self.is_vercel:
            return False
        if self.is_windows:
            return True
        return os.environ.get('FLASK_ENV', '').lower() in {'development', 'dev'}

    def detect_database(self) -> Dict[str, Any]:
        """
        Auto-detect and configure database connection.

        Returns:
            Database configuration dictionary with keys:
            - 'type': 'postgresql' or 'sqlite'
            - 'url': Full connection URL for PostgreSQL
            - All other connection parameters
        """
        # Try PostgreSQL with standard URL first
        url = self._get_database_url()
        if url:
            self.db_type = 'postgresql'
            self.config = {'type': 'postgresql', 'url': url}
            return self.config

        # Try to construct PostgreSQL URL from individual env vars
        pg_config = self._construct_postgres_from_env_vars()
        if pg_config:
            self.db_type = 'postgresql'
            self.config = {'type': 'postgresql', **pg_config}
            return self.config

        # Fall back to SQLite
        self.db_type = 'sqlite'
        self.config = self._get_sqlite_config()
        return self.config

    def _get_database_url(self) -> Optional[str]:
        """
        Get PostgreSQL connection URL from environment.

        Tries all known PostgreSQL URL environment variable names.
        """
        for env_var in self.ENV_PRIORITY:
            url = os.environ.get(env_var, '').strip()
            if url:
                # Ensure URL starts with postgresql:// or postgres://
                if url.startswith('postgres://'):
                    url = url.replace('postgres://', 'postgresql://', 1)
                if url.startswith('postgresql://'):
                    return url
        return None

    def _construct_postgres_from_env_vars(self) -> Optional[Dict[str, Any]]:
        """
        Construct PostgreSQL connection URL from individual env vars.

        Vercel sometimes provides these instead of a full URL.
        """
        required_vars = ['POSTGRES_HOST', 'POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_DB']
        
        # Try main Postgres vars first
        env_values = {
            'host': os.environ.get('POSTGRES_HOST'),
            'user': os.environ.get('POSTGRES_USER'),
            'password': os.environ.get('POSTGRES_PASSWORD'),
            'database': os.environ.get('POSTGRES_DB'),
        }

        # Fall back to PG* vars
        if not all(env_values.values()):
            env_values = {
                'host': os.environ.get('PGHOST') or env_values['host'],
                'user': os.environ.get('PGUSER') or env_values['user'],
                'password': os.environ.get('PGPASSWORD') or env_values['password'],
                'database': os.environ.get('PGDATABASE') or env_values['database'],
            }

        # Check if we have all requirements
        if not all(env_values.values()):
            return None

        port = os.environ.get('POSTGRES_PORT', 5432)
        try:
            port = int(port)
        except ValueError:
            port = 5432

        url = (
            f"postgresql://{env_values['user']}:{env_values['password']}"
            f"@{env_values['host']}:{port}/{env_values['database']}"
        )

        return {
            'url': url,
            'host': env_values['host'],
            'user': env_values['user'],
            'password': env_values['password'],
            'database': env_values['database'],
            'port': port,
        }

    def _get_sqlite_config(self) -> Dict[str, Any]:
        """
        Get SQLite configuration for local development.

        In Vercel, this will use /tmp (ephemeral).
        On Windows, uses AppData directory (persistent).
        """
        if self.is_vercel:
            # In Vercel, SQLite goes to /tmp and won't persist
            # This is only a fallback if PostgreSQL isn't available
            db_path = Path(os.environ.get('TMPDIR', '/tmp')) / 'gameunexa-fallback.db'
            db_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            # Local development - use AppData on Windows
            if self.is_windows:
                app_data = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
                db_dir = app_data / 'GameUnexa' / 'data'
            else:
                db_dir = Path.home() / '.gameunexa' / 'data'
            
            db_dir.mkdir(parents=True, exist_ok=True)
            db_path = db_dir / 'gameunexa.db'

        return {
            'type': 'sqlite',
            'path': str(db_path),
        }

    def get_connection_string(self) -> str:
        """Get database connection string for SQLAlchemy or similar."""
        if not self.config:
            self.detect_database()

        if self.db_type == 'postgresql':
            return self.config.get('url', '')
        else:
            return f"sqlite:///{self.config.get('path', '')}"

    def is_postgresql(self) -> bool:
        """Check if using PostgreSQL."""
        if not self.config:
            self.detect_database()
        return self.db_type == 'postgresql'

    def is_sqlite(self) -> bool:
        """Check if using SQLite."""
        if not self.config:
            self.detect_database()
        return self.db_type == 'sqlite'


# Singleton instance
_db_config: Optional[DatabaseConfig] = None


def get_db_config() -> DatabaseConfig:
    """Get or create the database configuration singleton."""
    global _db_config
    if _db_config is None:
        _db_config = DatabaseConfig()
        _db_config.detect_database()
    return _db_config


def get_database_url() -> str:
    """Get database connection URL (for compatibility)."""
    config = get_db_config()
    if config.is_postgresql():
        return config.config.get('url', '')
    else:
        path = config.config.get('path', '')
        return f"sqlite:///{path}"


def is_vercel_environment() -> bool:
    """Check if running in Vercel environment."""
    return os.environ.get('VERCEL') == '1'


def is_postgresql_available() -> bool:
    """Check if PostgreSQL is available."""
    config = get_db_config()
    return config.is_postgresql()
