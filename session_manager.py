# -*- coding: utf-8 -*-
"""
Serverless-compatible session management for GameUnexa ZERO-CONFIG VERCEL.

Session persistence using JSON Web Tokens (JWT) stored in browser cookies.
Sessions survive across different serverless function instances.
"""

import os
import json
import hmac
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from functools import wraps

try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False


class JWTSessionManager:
    """
    Serverless-compatible session management using JWT.

    Sessions are stored in signed cookies, so they persist
    across different serverless function instances.
    """

    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self.algorithm = 'HS256'
        self.session_timeout = 24  # hours

    def create_session_token(self, user_data: Dict[str, Any]) -> str:
        """Create a signed JWT session token."""
        if not JWT_AVAILABLE:
            # Fallback if jwt library not available
            return self._create_fallback_token(user_data)

        payload = {
            'data': user_data,
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(hours=self.session_timeout)
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_session_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode a JWT session token."""
        if not JWT_AVAILABLE:
            return self._verify_fallback_token(token)

        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload.get('data', {})
        except (jwt.InvalidTokenError, jwt.ExpiredSignatureError):
            return None

    def _create_fallback_token(self, user_data: Dict[str, Any]) -> str:
        """Create a signed token without JWT library."""
        payload = {
            'data': user_data,
            'timestamp': datetime.utcnow().isoformat(),
        }

        # Convert to JSON
        json_str = json.dumps(payload, separators=(',', ':'), default=str)

        # Create HMAC signature
        signature = hmac.new(
            self.secret_key.encode(),
            json_str.encode(),
            hashlib.sha256
        ).hexdigest()

        # Return base64-like format (simplified)
        return f"{json_str}.{signature}"

    def _verify_fallback_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify a fallback token."""
        try:
            json_part, signature = token.rsplit('.', 1)

            # Verify signature
            expected_sig = hmac.new(
                self.secret_key.encode(),
                json_part.encode(),
                hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(signature, expected_sig):
                return None

            payload = json.loads(json_part)
            return payload.get('data', {})
        except Exception:
            return None


class DatabaseSessionStore:
    """
    Optional database-backed session store for persistent sessions.

    Used if PostgreSQL is available; provides better security than cookies.
    """

    SESSION_TABLE = 'session_store'

    def __init__(self, db_config=None):
        self.db_config = db_config or self._get_db_config()
        self.use_db = self.db_config is not None

    def _get_db_config(self):
        """Get database config if available."""
        try:
            from db_config import get_db_config
            return get_db_config()
        except Exception:
            return None

    def create_session(self, session_id: str, user_data: Dict[str, Any]) -> bool:
        """Store session in database."""
        if not self.use_db:
            return False

        try:
            if self.db_config.is_postgresql():
                self._create_session_postgres(session_id, user_data)
            else:
                self._create_session_sqlite(session_id, user_data)
            return True
        except Exception as e:
            print(f"[SESSION] Failed to create session: {e}")
            return False

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session from database."""
        if not self.use_db:
            return None

        try:
            if self.db_config.is_postgresql():
                return self._get_session_postgres(session_id)
            else:
                return self._get_session_sqlite(session_id)
        except Exception as e:
            print(f"[SESSION] Failed to get session: {e}")
            return None

    def delete_session(self, session_id: str) -> bool:
        """Delete session from database."""
        if not self.use_db:
            return False

        try:
            if self.db_config.is_postgresql():
                self._delete_session_postgres(session_id)
            else:
                self._delete_session_sqlite(session_id)
            return True
        except Exception as e:
            print(f"[SESSION] Failed to delete session: {e}")
            return False

    def _create_session_postgres(self, session_id: str, user_data: Dict[str, Any]):
        """Create session in PostgreSQL."""
        try:
            import psycopg2
            url = self.db_config.config.get('url', '')
            conn = psycopg2.connect(url)
            cursor = conn.cursor()

            # Create table if needed
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.SESSION_TABLE} (
                    id TEXT PRIMARY KEY,
                    data JSONB,
                    created_at TIMESTAMP DEFAULT NOW(),
                    expires_at TIMESTAMP
                )
            """)

            # Insert session
            expires_at = datetime.utcnow() + timedelta(hours=24)
            cursor.execute(f"""
                INSERT INTO {self.SESSION_TABLE} (id, data, expires_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data
            """, (session_id, json.dumps(user_data), expires_at))

            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"[SESSION] PostgreSQL error: {e}")

    def _create_session_sqlite(self, session_id: str, user_data: Dict[str, Any]):
        """Create session in SQLite."""
        import sqlite3
        db_path = self.db_config.config.get('path', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create table if needed
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.SESSION_TABLE} (
                id TEXT PRIMARY KEY,
                data TEXT,
                created_at TEXT,
                expires_at TEXT
            )
        """)

        # Insert session
        expires_at = (datetime.utcnow() + timedelta(hours=24)).isoformat()
        cursor.execute(f"""
            INSERT OR REPLACE INTO {self.SESSION_TABLE} (id, data, created_at, expires_at)
            VALUES (?, ?, ?, ?)
        """, (session_id, json.dumps(user_data), datetime.utcnow().isoformat(), expires_at))

        conn.commit()
        conn.close()

    def _get_session_postgres(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session from PostgreSQL."""
        try:
            import psycopg2
            url = self.db_config.config.get('url', '')
            conn = psycopg2.connect(url)
            cursor = conn.cursor()

            cursor.execute(f"""
                SELECT data FROM {self.SESSION_TABLE}
                WHERE id = %s AND expires_at > NOW()
            """, (session_id,))

            row = cursor.fetchone()
            cursor.close()
            conn.close()

            if row:
                return json.loads(row[0])
            return None
        except Exception as e:
            print(f"[SESSION] PostgreSQL error: {e}")
            return None

    def _get_session_sqlite(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session from SQLite."""
        import sqlite3
        db_path = self.db_config.config.get('path', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(f"""
            SELECT data FROM {self.SESSION_TABLE}
            WHERE id = ? AND expires_at > ?
        """, (session_id, datetime.utcnow().isoformat()))

        row = cursor.fetchone()
        conn.close()

        if row:
            return json.loads(row[0])
        return None

    def _delete_session_postgres(self, session_id: str):
        """Delete session from PostgreSQL."""
        try:
            import psycopg2
            url = self.db_config.config.get('url', '')
            conn = psycopg2.connect(url)
            cursor = conn.cursor()

            cursor.execute(f"DELETE FROM {self.SESSION_TABLE} WHERE id = %s", (session_id,))

            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"[SESSION] PostgreSQL error: {e}")

    def _delete_session_sqlite(self, session_id: str):
        """Delete session from SQLite."""
        import sqlite3
        db_path = self.db_config.config.get('path', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(f"DELETE FROM {self.SESSION_TABLE} WHERE id = ?", (session_id,))

        conn.commit()
        conn.close()


# Factory function to get appropriate session manager
def create_session_manager(secret_key: str):
    """Create appropriate session manager for current environment."""
    try:
        from db_config import is_postgresql_available
        if is_postgresql_available():
            # Prefer database-backed sessions on PostgreSQL
            return DatabaseSessionStore()
    except Exception:
        pass

    # Fall back to JWT-based sessions (works everywhere)
    return JWTSessionManager(secret_key)
