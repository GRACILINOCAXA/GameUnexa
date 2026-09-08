import os
import json
import secrets
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from modelos.base import EntidadeBase
from excecao import AutenticacaoError

# Banco de dados simulado em memória para este módulo
USUARIOS_DB = {}


def normalizar_email(email: str) -> str:
    return (email or '').strip().lower()


def from_db_row(row):
    """Cria uma instância de Usuario/Admin a partir de uma linha retornada do DB.

    Mantém compatibilidade com o cache `USUARIOS_DB` mas não é a fonte canônica
    de verdadeiro armazenamento em produção.
    """
    if not row:
        return None
    is_admin = bool(row.get('is_admin') or 0)
    cls = Admin if is_admin else Usuario
    usuario = cls(row['id'], row['nome'], row['email'], row['password'])
    usuario.token_recuperacao = row.get('token_recuperacao')
    usuario.idade = row.get('idade')
    usuario.gosto_jogos = row.get('gosto_jogos') or ''
    usuario.telefone = row.get('telefone') or ''
    usuario.foto_perfil = row.get('foto_perfil') or ''
    usuario.steam_id64 = row.get('steam_id64') or ''
    usuario.steam_api_key = row.get('steam_api_key') or ''
    usuario.steam_library_path = row.get('steam_library_path') or ''
    usuario.hydra_library_path = row.get('hydra_library_path') or ''
    usuario.hydra_account_email = row.get('hydra_account_email') or ''
    usuario.hydra_usuario = row.get('hydra_usuario') or ''
    usuario.hydra_pin = row.get('hydra_pin') or ''
    usuario.hydra_token = row.get('hydra_token') or ''
    usuario.hydra_current_game = row.get('hydra_current_game') or ''
    usuario.hydra_last_update = row.get('hydra_last_update')
    usuario.library_view = '3d' if (row.get('library_style') or '').lower() == '3d' else (row.get('library_view') or '2d')
    try:
        usuario.auto_library_folders = json.loads(row.get('auto_library_folders') or '[]')
    except Exception:
        usuario.auto_library_folders = []
    usuario.auto_library_enabled = bool(row.get('auto_library_enabled') or 0)
    usuario.data_cadastro = row.get('data_cadastro') or usuario.data_cadastro
    return usuario


def obter_senha_admin_padrao() -> str:
    return os.environ.get('ADMIN_PASSWORD') or secrets.token_urlsafe(32)


class Usuario(EntidadeBase):
    # Classe concreta para usuários comuns
    def __init__(self, id_entidade: int, nome: str, email: str, password: str):
        super().__init__(id_entidade)
        self.nome = nome
        self.email = normalizar_email(email)
        self.__password = ''
        if password:
            if self.senha_esta_hasheada(password):
                self.__password = password
            else:
                self.definir_senha(password)
        self.token_recuperacao = None
        self.idade = None
        self.gosto_jogos = ""  # Descrição dos gostos
        self.telefone = ""
        self.foto_perfil = ""
        self.discord_tag = ""
        self.discord_server = ""
        self.discord_online = False
        self.steam_input_tipo = "auto"
        self.steam_id64 = ""
        self.steam_api_key = ""
        self.steam_online = False
        self.steam_current_game = ""
        self.steam_current_game_appid = None
        self.steam_playtime_minutes = 0
        self.steam_last_update = None
        self.data_cadastro = datetime.now().isoformat(timespec='seconds')
        self.hydra_profile_id = ""
        self.hydra_api_base_url = ""
        self.hydra_account_email = ""
        self.hydra_usuario = ""
        self.hydra_pin = ""
        self.hydra_token = ""
        self.hydra_current_game = ""
        self.hydra_last_update = None
        self.library_view = "2d"
        self.auto_library_enabled = False
        self.auto_library_folders = []
        self.auto_last_scan = None

    # Getter e Setter para controle de visibilidade da senha com validação
    def verificar_senha(self, password: str) -> bool:
        senha_armazenada = self.__password or ''
        if self.senha_esta_hasheada():
            return check_password_hash(senha_armazenada, password)
        return senha_armazenada == password

    def senha_esta_hasheada(self, password: str | None = None) -> bool:
        valor = self.__password if password is None else (password or '')
        return valor.startswith('pbkdf2:') or valor.startswith('scrypt:') or valor.startswith('argon2') or valor.startswith('sha256$')

    def definir_senha(self, password: str) -> None:
        self.__password = generate_password_hash(password)

    def alterar_senha_com_token(self, token: str, nova_senha: str):
        if not self.token_recuperacao or self.token_recuperacao != token:
            raise AutenticacaoError("Token de recuperação inválido ou expirado.")
        self.definir_senha(nova_senha)
        self.token_recuperacao = None # Consome o token

    def obter_status_discord(self) -> str:
        if self.discord_online:
            return "Online no Discord"
        return "Offline no Discord"

    def tem_hydra_conectada(self) -> bool:
        return bool(
            (getattr(self, 'hydra_token', '') or '').strip()
            or (getattr(self, 'hydra_usuario', '') or '').strip()
            or (getattr(self, 'hydra_account_email', '') or '').strip()
        )

    def obter_status_hydra(self) -> str:
        if self.hydra_current_game:
            return f"Jogando {self.hydra_current_game}"
        return "Offline"

    def obter_status_steam(self) -> str:
        if self.steam_current_game:
            return f"Jogando {self.steam_current_game}"
        elif self.steam_online:
            return "Na Steam"
        return "Offline"

    def obter_status_geral(self) -> str:
        if self.steam_current_game:
            return f"🎮 Ingame: {self.steam_current_game}"
        if self.hydra_current_game:
            return f"⚡ Ingame: {self.hydra_current_game}"
        if self.steam_online:
            return "Na Steam"
        return "Offline"

    def obter_link_discord(self) -> str | None:
        if not self.discord_server:
            return None
        if self.discord_server.startswith('http'):
            return self.discord_server
        return f'https://discord.gg/{self.discord_server}'


    def obter_resumo(self) -> str:
        return f"Jogador: {self.nome} ({self.email})"


class Admin(Usuario):
    # Classe que herda de Usuario
    def __init__(self, id_entidade: int, nome: str, email: str, password: str, nivel_acesso: int = 1):
        super().__init__(id_entidade, nome, email, password)
        self.nivel_acesso = nivel_acesso

    def obter_resumo(self) -> str:
        return f"Administrador: {self.nome} - Nível {self.nivel_acesso}"