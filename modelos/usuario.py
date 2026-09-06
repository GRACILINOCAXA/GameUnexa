import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from modelos.base import EntidadeBase
from excecao import AutenticacaoError

# Banco de dados simulado em memória para este módulo
USUARIOS_DB = {}


def obter_senha_admin_padrao() -> str:
    return os.environ.get('ADMIN_PASSWORD') or 'GameLink@Admin#2026'


class Usuario(EntidadeBase):
    # Classe concreta para usuários comuns
    def __init__(self, id_entidade: int, nome: str, email: str, password: str):
        super().__init__(id_entidade)
        self.nome = nome
        self.email = email
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