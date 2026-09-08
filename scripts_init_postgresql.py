"""Inicializa o PostgreSQL persistente do GameUnexa.

Uso local:
    set DATABASE_URL=postgresql://...
    python scripts_init_postgresql.py

Na Vercel, a mesma inicialização é executada automaticamente pelo app.
"""
from database import init_external_auth_db

init_external_auth_db()
print('PostgreSQL do GameUnexa inicializado com sucesso.')
