# -*- coding: utf-8 -*-
"""
Database initialization and connection management for GameUnexa ZERO-CONFIG VERCEL.

Provides automatic database schema initialization (CREATE TABLE IF NOT EXISTS).
Supports both PostgreSQL and SQLite.
"""

import os
import sqlite3
import threading
from typing import Optional, Any, Dict, List, Tuple
from contextlib import contextmanager
from pathlib import Path

try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

from db_config import get_db_config, is_postgresql_available


class DatabaseInitializer:
    """Handles database schema initialization and migrations."""

    def __init__(self):
        self.db_config = get_db_config()
        self._initialized = False
        self._lock = threading.Lock()

    def initialize_database(self) -> bool:
        """
        Initialize database by creating all tables.

        Returns:
            True if successful, False otherwise
        """
        if self._initialized:
            return True

        with self._lock:
            if self._initialized:
                return True

            try:
                self._create_tables()
                self._initialized = True
                print("[DATABASE] Successfully initialized all tables")
                return True
            except Exception as e:
                print(f"[DATABASE ERROR] Failed to initialize database: {e}")
                return False

    def _create_tables(self):
        """Execute CREATE TABLE IF NOT EXISTS for all schema."""
        if self.db_config.is_postgresql():
            self._create_tables_postgresql()
        else:
            self._create_tables_sqlite()

    def _create_tables_postgresql(self):
        """Create all tables in PostgreSQL database."""
        if not PSYCOPG2_AVAILABLE:
            raise ImportError("psycopg2 is required for PostgreSQL support")

        schema_statements = self._get_schema_statements_postgresql()
        url = self.db_config.config.get('url', '')
        
        conn = psycopg2.connect(url)
        try:
            conn.autocommit = True
            cursor = conn.cursor()
            for statement in schema_statements:
                try:
                    cursor.execute(statement)
                except Exception as e:
                    print(f"[DATABASE] Table creation statement failed: {e}")
                    print(f"[DATABASE] Statement: {statement[:100]}...")
            cursor.close()
        finally:
            conn.close()

    def _create_tables_sqlite(self):
        """Create all tables in SQLite database."""
        db_path = self.db_config.config.get('path', '')
        
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            schema_statements = self._get_schema_statements_sqlite()
            
            for statement in schema_statements:
                try:
                    cursor.execute(statement)
                except Exception as e:
                    print(f"[DATABASE] Table creation failed: {e}")
                    print(f"[DATABASE] Statement: {statement[:100]}...")
            
            conn.commit()
        finally:
            conn.close()

    def _get_schema_statements_sqlite(self) -> List[str]:
        """Get all CREATE TABLE statements for SQLite."""
        return [
            """PRAGMA foreign_keys = ON;""",
            """CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                token_recuperacao TEXT,
                idade INTEGER,
                gosto_jogos TEXT,
                telefone TEXT,
                steam_id64 TEXT,
                steam_api_key TEXT,
                steam_library_path TEXT,
                hydra_library_path TEXT,
                hydra_account_email TEXT,
                hydra_usuario TEXT,
                hydra_pin TEXT,
                hydra_token TEXT,
                hydra_current_game TEXT,
                hydra_last_update TEXT,
                library_style TEXT NOT NULL DEFAULT 'classic',
                auto_library_enabled INTEGER NOT NULL DEFAULT 0,
                auto_library_folders TEXT NOT NULL DEFAULT '[]',
                auto_last_scan TEXT,
                foto_perfil TEXT,
                data_cadastro TEXT,
                is_admin INTEGER NOT NULL DEFAULT 0
            );""",
            """CREATE TABLE IF NOT EXISTS categorias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE
            );""",
            """CREATE TABLE IF NOT EXISTS jogos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                genero TEXT NOT NULL,
                desenvolvedora TEXT NOT NULL,
                ano INTEGER NOT NULL
            );""",
            """CREATE TABLE IF NOT EXISTS jogo_categoria (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                jogo_id INTEGER NOT NULL,
                categoria_id INTEGER NOT NULL,
                UNIQUE(jogo_id, categoria_id),
                FOREIGN KEY(jogo_id) REFERENCES jogos(id) ON DELETE CASCADE,
                FOREIGN KEY(categoria_id) REFERENCES categorias(id) ON DELETE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                autor_email TEXT NOT NULL,
                titulo TEXT NOT NULL,
                conteudo TEXT NOT NULL,
                imagem_url TEXT,
                data_criacao TEXT NOT NULL,
                visivel INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY(autor_email) REFERENCES usuarios(email) ON DELETE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS comentarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                autor_email TEXT NOT NULL,
                texto TEXT NOT NULL,
                data_criacao TEXT NOT NULL,
                visivel INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY(post_id) REFERENCES posts(id) ON DELETE CASCADE,
                FOREIGN KEY(autor_email) REFERENCES usuarios(email) ON DELETE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS amizades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_solicitante TEXT NOT NULL,
                email_receptor TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pendente',
                data_solicitacao TEXT NOT NULL,
                data_aceito TEXT,
                UNIQUE(email_solicitante, email_receptor),
                FOREIGN KEY(email_solicitante) REFERENCES usuarios(email) ON DELETE CASCADE,
                FOREIGN KEY(email_receptor) REFERENCES usuarios(email) ON DELETE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS biblioteca (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_usuario TEXT NOT NULL,
                jogo_id INTEGER NOT NULL,
                data_adicao TEXT NOT NULL,
                tempo_jogado_horas INTEGER NOT NULL DEFAULT 0,
                concluido INTEGER NOT NULL DEFAULT 0,
                platinado INTEGER NOT NULL DEFAULT 0,
                origem TEXT DEFAULT 'manual',
                launcher TEXT DEFAULT 'manual',
                codigo_origem TEXT DEFAULT '',
                cover_url TEXT DEFAULT '',
                executable_path TEXT DEFAULT '',
                install_folder TEXT DEFAULT '',
                executable_name TEXT DEFAULT '',
                updated_at TEXT,
                manual_override INTEGER NOT NULL DEFAULT 0,
                favorito INTEGER NOT NULL DEFAULT 0,
                last_launched_at TEXT,
                last_played_game TEXT DEFAULT '',
                status TEXT DEFAULT 'offline',
                conquistas_desbloqueadas INTEGER NOT NULL DEFAULT 0,
                conquistas_total INTEGER NOT NULL DEFAULT 0,
                UNIQUE(email_usuario, jogo_id),
                FOREIGN KEY(email_usuario) REFERENCES usuarios(email) ON DELETE CASCADE,
                FOREIGN KEY(jogo_id) REFERENCES jogos(id) ON DELETE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                jogo_id INTEGER NOT NULL,
                email_usuario TEXT NOT NULL,
                titulo TEXT NOT NULL,
                conteudo TEXT NOT NULL,
                nota INTEGER NOT NULL,
                data_criacao TEXT NOT NULL,
                visivel INTEGER NOT NULL DEFAULT 1,
                curtidas INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(jogo_id) REFERENCES jogos(id) ON DELETE CASCADE,
                FOREIGN KEY(email_usuario) REFERENCES usuarios(email) ON DELETE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS review_comentarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                review_id INTEGER NOT NULL,
                email_usuario TEXT NOT NULL,
                texto TEXT NOT NULL,
                data_criacao TEXT NOT NULL,
                visivel INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY(review_id) REFERENCES reviews(id) ON DELETE CASCADE,
                FOREIGN KEY(email_usuario) REFERENCES usuarios(email) ON DELETE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS notificacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_receptor TEXT NOT NULL,
                tipo TEXT NOT NULL,
                titulo TEXT NOT NULL,
                descricao TEXT NOT NULL,
                link TEXT,
                data_criacao TEXT NOT NULL,
                lida INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(email_receptor) REFERENCES usuarios(email) ON DELETE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS post_likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                email_usuario TEXT NOT NULL,
                UNIQUE(post_id, email_usuario),
                FOREIGN KEY(post_id) REFERENCES posts(id) ON DELETE CASCADE,
                FOREIGN KEY(email_usuario) REFERENCES usuarios(email) ON DELETE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS suporte_categorias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL UNIQUE,
                nome TEXT NOT NULL
            );""",
            """CREATE TABLE IF NOT EXISTS suporte_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL UNIQUE,
                nome TEXT NOT NULL
            );""",
            """CREATE TABLE IF NOT EXISTS suporte_chamados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT NOT NULL UNIQUE,
                titulo TEXT NOT NULL,
                categoria_slug TEXT NOT NULL,
                descricao TEXT NOT NULL,
                passos_reproducao TEXT,
                resultado_esperado TEXT,
                resultado_obtido TEXT,
                prioridade TEXT NOT NULL DEFAULT 'Média',
                versao_gamelink TEXT,
                so TEXT,
                navegador TEXT,
                resolucao_tela TEXT,
                data_criacao TEXT NOT NULL,
                hora_criacao TEXT NOT NULL,
                usuario_email TEXT NOT NULL,
                usuario_nome TEXT NOT NULL,
                usuario_id INTEGER,
                email_contato TEXT,
                status_slug TEXT NOT NULL DEFAULT 'aberto',
                status_id INTEGER,
                FOREIGN KEY(usuario_email) REFERENCES usuarios(email) ON DELETE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS suporte_mensagens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chamado_id INTEGER NOT NULL,
                autor_email TEXT NOT NULL,
                autor_nome TEXT NOT NULL,
                conteudo TEXT NOT NULL,
                tipo TEXT NOT NULL DEFAULT 'usuario',
                data_envio TEXT NOT NULL,
                FOREIGN KEY(chamado_id) REFERENCES suporte_chamados(id) ON DELETE CASCADE,
                FOREIGN KEY(autor_email) REFERENCES usuarios(email) ON DELETE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS suporte_anexos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chamado_id INTEGER NOT NULL,
                mensagem_id INTEGER,
                nome_original TEXT NOT NULL,
                nome_arquivo TEXT NOT NULL,
                caminho TEXT NOT NULL,
                tipo_mime TEXT,
                tamanho INTEGER NOT NULL DEFAULT 0,
                data_upload TEXT NOT NULL,
                FOREIGN KEY(chamado_id) REFERENCES suporte_chamados(id) ON DELETE CASCADE,
                FOREIGN KEY(mensagem_id) REFERENCES suporte_mensagens(id) ON DELETE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS suporte_historico (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chamado_id INTEGER NOT NULL,
                usuario_email TEXT NOT NULL,
                acao TEXT NOT NULL,
                detalhes TEXT,
                data_registro TEXT NOT NULL,
                FOREIGN KEY(chamado_id) REFERENCES suporte_chamados(id) ON DELETE CASCADE,
                FOREIGN KEY(usuario_email) REFERENCES usuarios(email) ON DELETE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS mensagens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_remetente TEXT NOT NULL,
                email_destino TEXT NOT NULL,
                conteudo TEXT NOT NULL,
                data_envio TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'sent',
                canceled_at TEXT,
                canceled_by TEXT,
                FOREIGN KEY(email_remetente) REFERENCES usuarios(email) ON DELETE CASCADE,
                FOREIGN KEY(email_destino) REFERENCES usuarios(email) ON DELETE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS mensagem_reacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mensagem_id INTEGER NOT NULL,
                email_usuario TEXT NOT NULL,
                emoji TEXT NOT NULL,
                data_reacao TEXT NOT NULL,
                UNIQUE(mensagem_id, email_usuario),
                FOREIGN KEY(mensagem_id) REFERENCES mensagens(id) ON DELETE CASCADE,
                FOREIGN KEY(email_usuario) REFERENCES usuarios(email) ON DELETE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS background_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL UNIQUE,
                type TEXT DEFAULT 'none',
                effect TEXT,
                file TEXT,
                folder TEXT,
                color1 TEXT DEFAULT '#38bdf8',
                color2 TEXT DEFAULT '#0f172a',
                speed INTEGER DEFAULT 500,
                opacity INTEGER DEFAULT 100,
                fps INTEGER DEFAULT 60,
                shuffle INTEGER DEFAULT 0,
                transition INTEGER DEFAULT 500,
                options TEXT DEFAULT '{}',
                updated_at TEXT
            );""",
        ]

    def _get_schema_statements_postgresql(self) -> List[str]:
        """Get all CREATE TABLE statements for PostgreSQL."""
        # PostgreSQL uses SERIAL instead of AUTOINCREMENT
        return [
            """CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                nome TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                token_recuperacao TEXT,
                idade INTEGER,
                gosto_jogos TEXT,
                telefone TEXT,
                steam_id64 TEXT,
                steam_api_key TEXT,
                steam_library_path TEXT,
                hydra_library_path TEXT,
                hydra_account_email TEXT,
                hydra_usuario TEXT,
                hydra_pin TEXT,
                hydra_token TEXT,
                hydra_current_game TEXT,
                hydra_last_update TEXT,
                library_style TEXT NOT NULL DEFAULT 'classic',
                auto_library_enabled INTEGER NOT NULL DEFAULT 0,
                auto_library_folders TEXT NOT NULL DEFAULT '[]',
                auto_last_scan TEXT,
                foto_perfil TEXT,
                data_cadastro TEXT,
                is_admin INTEGER NOT NULL DEFAULT 0
            );""",
            """CREATE TABLE IF NOT EXISTS categorias (
                id SERIAL PRIMARY KEY,
                nome TEXT NOT NULL UNIQUE
            );""",
            """CREATE TABLE IF NOT EXISTS jogos (
                id SERIAL PRIMARY KEY,
                titulo TEXT NOT NULL,
                genero TEXT NOT NULL,
                desenvolvedora TEXT NOT NULL,
                ano INTEGER NOT NULL
            );""",
            """CREATE TABLE IF NOT EXISTS jogo_categoria (
                id SERIAL PRIMARY KEY,
                jogo_id INTEGER NOT NULL,
                categoria_id INTEGER NOT NULL,
                UNIQUE(jogo_id, categoria_id),
                FOREIGN KEY(jogo_id) REFERENCES jogos(id) ON DELETE CASCADE,
                FOREIGN KEY(categoria_id) REFERENCES categorias(id) ON DELETE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS posts (
                id SERIAL PRIMARY KEY,
                autor_email TEXT NOT NULL,
                titulo TEXT NOT NULL,
                conteudo TEXT NOT NULL,
                imagem_url TEXT,
                data_criacao TEXT NOT NULL,
                visivel INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY(autor_email) REFERENCES usuarios(email) ON DELETE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS comentarios (
                id SERIAL PRIMARY KEY,
                post_id INTEGER NOT NULL,
                autor_email TEXT NOT NULL,
                texto TEXT NOT NULL,
                data_criacao TEXT NOT NULL,
                visivel INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY(post_id) REFERENCES posts(id) ON DELETE CASCADE,
                FOREIGN KEY(autor_email) REFERENCES usuarios(email) ON DELETE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS amizades (
                id SERIAL PRIMARY KEY,
                email_solicitante TEXT NOT NULL,
                email_receptor TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pendente',
                data_solicitacao TEXT NOT NULL,
                data_aceito TEXT,
                UNIQUE(email_solicitante, email_receptor),
                FOREIGN KEY(email_solicitante) REFERENCES usuarios(email) ON DELETE CASCADE,
                FOREIGN KEY(email_receptor) REFERENCES usuarios(email) ON DELETE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS biblioteca (
                id SERIAL PRIMARY KEY,
                email_usuario TEXT NOT NULL,
                jogo_id INTEGER NOT NULL,
                data_adicao TEXT NOT NULL,
                tempo_jogado_horas INTEGER NOT NULL DEFAULT 0,
                concluido INTEGER NOT NULL DEFAULT 0,
                platinado INTEGER NOT NULL DEFAULT 0,
                origem TEXT DEFAULT 'manual',
                launcher TEXT DEFAULT 'manual',
                codigo_origem TEXT DEFAULT '',
                cover_url TEXT DEFAULT '',
                executable_path TEXT DEFAULT '',
                install_folder TEXT DEFAULT '',
                executable_name TEXT DEFAULT '',
                updated_at TEXT,
                manual_override INTEGER NOT NULL DEFAULT 0,
                favorito INTEGER NOT NULL DEFAULT 0,
                last_launched_at TEXT,
                last_played_game TEXT DEFAULT '',
                status TEXT DEFAULT 'offline',
                conquistas_desbloqueadas INTEGER NOT NULL DEFAULT 0,
                conquistas_total INTEGER NOT NULL DEFAULT 0,
                UNIQUE(email_usuario, jogo_id),
                FOREIGN KEY(email_usuario) REFERENCES usuarios(email) ON DELETE CASCADE,
                FOREIGN KEY(jogo_id) REFERENCES jogos(id) ON DELETE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS reviews (
                id SERIAL PRIMARY KEY,
                jogo_id INTEGER NOT NULL,
                email_usuario TEXT NOT NULL,
                titulo TEXT NOT NULL,
                conteudo TEXT NOT NULL,
                nota INTEGER NOT NULL,
                data_criacao TEXT NOT NULL,
                visivel INTEGER NOT NULL DEFAULT 1,
                curtidas INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(jogo_id) REFERENCES jogos(id) ON DELETE CASCADE,
                FOREIGN KEY(email_usuario) REFERENCES usuarios(email) ON DELETE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS review_comentarios (
                id SERIAL PRIMARY KEY,
                review_id INTEGER NOT NULL,
                email_usuario TEXT NOT NULL,
                texto TEXT NOT NULL,
                data_criacao TEXT NOT NULL,
                visivel INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY(review_id) REFERENCES reviews(id) ON DELETE CASCADE,
                FOREIGN KEY(email_usuario) REFERENCES usuarios(email) ON DELETE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS notificacoes (
                id SERIAL PRIMARY KEY,
                email_receptor TEXT NOT NULL,
                tipo TEXT NOT NULL,
                titulo TEXT NOT NULL,
                descricao TEXT NOT NULL,
                link TEXT,
                data_criacao TEXT NOT NULL,
                lida INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(email_receptor) REFERENCES usuarios(email) ON DELETE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS post_likes (
                id SERIAL PRIMARY KEY,
                post_id INTEGER NOT NULL,
                email_usuario TEXT NOT NULL,
                UNIQUE(post_id, email_usuario),
                FOREIGN KEY(post_id) REFERENCES posts(id) ON DELETE CASCADE,
                FOREIGN KEY(email_usuario) REFERENCES usuarios(email) ON DELETE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS suporte_categorias (
                id SERIAL PRIMARY KEY,
                slug TEXT NOT NULL UNIQUE,
                nome TEXT NOT NULL
            );""",
            """CREATE TABLE IF NOT EXISTS suporte_status (
                id SERIAL PRIMARY KEY,
                slug TEXT NOT NULL UNIQUE,
                nome TEXT NOT NULL
            );""",
            """CREATE TABLE IF NOT EXISTS suporte_chamados (
                id SERIAL PRIMARY KEY,
                codigo TEXT NOT NULL UNIQUE,
                titulo TEXT NOT NULL,
                categoria_slug TEXT NOT NULL,
                descricao TEXT NOT NULL,
                passos_reproducao TEXT,
                resultado_esperado TEXT,
                resultado_obtido TEXT,
                prioridade TEXT NOT NULL DEFAULT 'Média',
                versao_gamelink TEXT,
                so TEXT,
                navegador TEXT,
                resolucao_tela TEXT,
                data_criacao TEXT NOT NULL,
                hora_criacao TEXT NOT NULL,
                usuario_email TEXT NOT NULL,
                usuario_nome TEXT NOT NULL,
                usuario_id INTEGER,
                email_contato TEXT,
                status_slug TEXT NOT NULL DEFAULT 'aberto',
                status_id INTEGER,
                FOREIGN KEY(usuario_email) REFERENCES usuarios(email) ON DELETE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS suporte_mensagens (
                id SERIAL PRIMARY KEY,
                chamado_id INTEGER NOT NULL,
                autor_email TEXT NOT NULL,
                autor_nome TEXT NOT NULL,
                conteudo TEXT NOT NULL,
                tipo TEXT NOT NULL DEFAULT 'usuario',
                data_envio TEXT NOT NULL,
                FOREIGN KEY(chamado_id) REFERENCES suporte_chamados(id) ON DELETE CASCADE,
                FOREIGN KEY(autor_email) REFERENCES usuarios(email) ON DELETE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS suporte_anexos (
                id SERIAL PRIMARY KEY,
                chamado_id INTEGER NOT NULL,
                mensagem_id INTEGER,
                nome_original TEXT NOT NULL,
                nome_arquivo TEXT NOT NULL,
                caminho TEXT NOT NULL,
                tipo_mime TEXT,
                tamanho INTEGER NOT NULL DEFAULT 0,
                data_upload TEXT NOT NULL,
                FOREIGN KEY(chamado_id) REFERENCES suporte_chamados(id) ON DELETE CASCADE,
                FOREIGN KEY(mensagem_id) REFERENCES suporte_mensagens(id) ON DELETE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS suporte_historico (
                id SERIAL PRIMARY KEY,
                chamado_id INTEGER NOT NULL,
                usuario_email TEXT NOT NULL,
                acao TEXT NOT NULL,
                detalhes TEXT,
                data_registro TEXT NOT NULL,
                FOREIGN KEY(chamado_id) REFERENCES suporte_chamados(id) ON DELETE CASCADE,
                FOREIGN KEY(usuario_email) REFERENCES usuarios(email) ON DELETE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS mensagens (
                id SERIAL PRIMARY KEY,
                email_remetente TEXT NOT NULL,
                email_destino TEXT NOT NULL,
                conteudo TEXT NOT NULL,
                data_envio TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'sent',
                canceled_at TEXT,
                canceled_by TEXT,
                FOREIGN KEY(email_remetente) REFERENCES usuarios(email) ON DELETE CASCADE,
                FOREIGN KEY(email_destino) REFERENCES usuarios(email) ON DELETE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS mensagem_reacoes (
                id SERIAL PRIMARY KEY,
                mensagem_id INTEGER NOT NULL,
                email_usuario TEXT NOT NULL,
                emoji TEXT NOT NULL,
                data_reacao TEXT NOT NULL,
                UNIQUE(mensagem_id, email_usuario),
                FOREIGN KEY(mensagem_id) REFERENCES mensagens(id) ON DELETE CASCADE,
                FOREIGN KEY(email_usuario) REFERENCES usuarios(email) ON DELETE CASCADE
            );""",
            """CREATE TABLE IF NOT EXISTS background_settings (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL UNIQUE,
                type TEXT DEFAULT 'none',
                effect TEXT,
                file TEXT,
                folder TEXT,
                color1 TEXT DEFAULT '#38bdf8',
                color2 TEXT DEFAULT '#0f172a',
                speed INTEGER DEFAULT 500,
                opacity INTEGER DEFAULT 100,
                fps INTEGER DEFAULT 60,
                shuffle INTEGER DEFAULT 0,
                transition INTEGER DEFAULT 500,
                options TEXT DEFAULT '{}',
                updated_at TEXT
            );""",
        ]


# Singleton instance
_db_initializer: Optional[DatabaseInitializer] = None


def get_db_initializer() -> DatabaseInitializer:
    """Get or create the database initializer."""
    global _db_initializer
    if _db_initializer is None:
        _db_initializer = DatabaseInitializer()
    return _db_initializer


def ensure_database_initialized() -> bool:
    """Ensure database is fully initialized."""
    initializer = get_db_initializer()
    return initializer.initialize_database()
