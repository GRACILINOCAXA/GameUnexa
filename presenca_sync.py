"""
Integração entre detector de presença e sincronização automática de Steam/Hydra.
"""

import os
from datetime import datetime

from modelos.usuario import USUARIOS_DB
from steam_api import obter_status


def _sincronizar_usuario_automaticamente(email: str, estado: dict | None = None) -> bool:
    """Sincroniza status do usuário com base no estado detectado pelo monitor."""
    user = USUARIOS_DB.get(email)
    if not user:
        return False

    try:
        steam_id = getattr(user, 'steam_id64', '') or getattr(user, 'steam_id', '')
        api_key = getattr(user, 'steam_api_key', '')
        estado_presenca = estado or {}

        novo_online = bool(estado_presenca.get('online', False) or estado_presenca.get('steam_ativo', False) or estado_presenca.get('hydra_ativo', False))
        novo_jogo = estado_presenca.get('jogo_atual') or ''
        novo_appid = estado_presenca.get('appid')
        novo_path = estado_presenca.get('path')
        novo_launcher = (estado_presenca.get('launcher') or '').lower()

        if steam_id and not estado:
            try:
                status = obter_status(steam_id, api_key or os.environ.get('STEAM_API_KEY', ''))
                novo_online = bool(status.get('online') or novo_online)
                if not novo_jogo and status.get('game') and not estado:
                    novo_jogo = status.get('game') or ''
            except Exception as exc:
                print(f'[Auto Sync] Erro ao consultar Steam API: {exc}')
        # Atualiza campos conforme launcher detectado
        mudou = False

        # Se há jogo detectado pelo monitor, priorizar esses dados
        if novo_jogo:
            if novo_launcher == 'steam' or estado_presenca.get('steam_ativo'):
                if user.steam_current_game != novo_jogo or user.steam_current_game_appid != novo_appid or not user.steam_online:
                    user.steam_current_game = novo_jogo
                    user.steam_current_game_appid = novo_appid
                    user.steam_online = True
                    user.steam_last_update = datetime.now().isoformat()
                    mudou = True
            elif novo_launcher == 'hydra' or estado_presenca.get('hydra_ativo'):
                if user.hydra_current_game != novo_jogo or not user.hydra_last_update:
                    user.hydra_current_game = novo_jogo
                    user.hydra_last_update = datetime.now().isoformat()
                    mudou = True
            else:
                # Jogo local executando; não persistir no campo steam/hydra, mas atualizar timestamp
                user.steam_last_update = datetime.now().isoformat()
                mudou = True

        else:
            # Sem jogo detectado: atualizar flags de launcher
            if user.steam_online != bool(estado_presenca.get('steam_ativo', False)):
                user.steam_online = bool(estado_presenca.get('steam_ativo', False))
                mudou = True
            # O detector confirmou que nenhum processo de jogo está ativo.
            if user.steam_current_game or user.steam_current_game_appid:
                user.steam_current_game = ''
                user.steam_current_game_appid = None
                user.steam_last_update = datetime.now().isoformat()
                mudou = True
            if user.hydra_current_game:
                user.hydra_current_game = ''
                user.hydra_last_update = datetime.now().isoformat()
                mudou = True

        if mudou:
            from database import persistir_usuario
            persistir_usuario(user)
            print(f'[Auto Sync] {email}: online={user.steam_online or bool(user.hydra_current_game)}, steam_game="{getattr(user, "steam_current_game", "")}", hydra_game="{getattr(user, "hydra_current_game", "")}", appid={getattr(user, "steam_current_game_appid", None)}')
            return True

        return False
    except Exception as exc:
        print(f'[Auto Sync] Erro ao sincronizar {email}: {exc}')
        return False


def callback_mudanca_presenca(email: str):
    """Factory para criar callback de mudança de presença."""
    def _callback(estado: dict):
        steam_ativo = estado.get('steam_ativo', False)
        hydra_ativo = estado.get('hydra_ativo', False)
        jogo = estado.get('jogo_atual', '')
        online = estado.get('online', False)

        print(f'[Presence] {email}: Steam={steam_ativo}, Hydra={hydra_ativo}, Online={online}, Jogando={bool(jogo)}')

        if online or steam_ativo or hydra_ativo:
            _sincronizar_usuario_automaticamente(email, estado)
        else:
            user = USUARIOS_DB.get(email)
            if user and (user.steam_online or user.steam_current_game or user.hydra_current_game):
                user.steam_online = False
                user.steam_current_game = ''
                user.steam_current_game_appid = None
                user.steam_last_update = datetime.now().isoformat()
                # Limpar Hydra também
                user.hydra_current_game = ''
                user.hydra_last_update = None
                from database import persistir_usuario
                persistir_usuario(user)
                print(f'[Auto Sync] {email}: Marcado como offline')

    return _callback


def callback_mudanca_presenca_global(estado: dict) -> None:
    """Propaga o estado real do detector para os usuários carregados localmente."""
    for email in tuple(USUARIOS_DB):
        callback_mudanca_presenca(email)(estado)
