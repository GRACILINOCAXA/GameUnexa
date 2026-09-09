"""
Detecção automática de presença em tempo real para Steam, Hydra, executáveis e launchers.
Monitora processos sem bloquear a aplicação Flask.
"""

import ctypes
import ctypes.wintypes as wintypes
import json
import os
import platform
import re
import subprocess
import threading
import time
from datetime import datetime, timezone
from typing import Callable
from difflib import SequenceMatcher

from modelos.jogo import JOGOS_DB
from modelos.amigos_biblioteca import BIBLIOTECA_DB
from steam_local import carregar_indice_steam_local, listar_jogos_instalados

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

_STEAM_PROCESSOS = {'steam.exe', 'steamservice.exe', 'steamwebhelper.exe', 'steamclient.exe'}
_HYDRA_PROCESSOS = {'hydra.exe', 'hydralauncher.exe', 'hydra launcher.exe'}
_PROCESS_SIGNATURES = {
    're4': 'Resident Evil 4',
    're4remake': 'Resident Evil 4 Remake',
    'bio4': 'Resident Evil 4',
    'eldenring': 'Elden Ring',
    'witcher3': 'The Witcher 3',
    'gta5': 'Grand Theft Auto V',
    'gta5exe': 'Grand Theft Auto V',
}

_BLACKLISTED_EXES = {
    'steamwebhelper.exe', 'crashhandler.exe', 'unitycrashhandler.exe',
    'easyanticheat.exe', 'battleye.exe', 'launcher.exe', 'updater.exe',
    'update.exe', 'helper.exe', 'bootstrapper.exe', 'eabackgroundservice.exe',
    'helperservice.exe', 'fdm.exe', 'pservice.exe', 'wallpaperservice32_c.exe',
    'epiconlineservices.exe', 'discord.exe', 'chrome.exe', 'brave.exe',
    'msedge.exe', 'firefox.exe', 'opera.exe', 'explorer.exe', 'dwm.exe',
    'runtimebroker.exe', 'searchhost.exe', 'widgets.exe', 'systemsettings.exe',
    'taskhostw.exe', 'taskhost.exe', 'conhost.exe', 'dllhost.exe',
    'svchost.exe', 'services.exe', 'spoolsv.exe', 'code.exe', 'devenv.exe',
    'notepad.exe', 'notepad++.exe', 'calc.exe', 'mspaint.exe', 'taskmgr.exe',
    'cmd.exe', 'powershell.exe', 'pwsh.exe', 'wt.exe', 'applicationframehost.exe',
    'shellhost.exe', 'searchui.exe', 'paint.exe', 'spotify.exe', 'slack.exe',
    'teams.exe', 'outlook.exe', 'skype.exe', 'onedrive.exe', 'steamcloader.exe',
}

_KNOWN_SYSTEM_EXES = {
    'explorer.exe', 'taskhostw.exe', 'taskhost.exe', 'conhost.exe', 'dllhost.exe',
    'chrome.exe', 'firefox.exe', 'msedge.exe', 'opera.exe', 'discord.exe',
    'teams.exe', 'slack.exe', 'telegram.exe', 'whatsapp.exe', 'outlook.exe',
    'code.exe', 'devenv.exe', 'notepad.exe', 'notepad++.exe', 'python.exe',
    'pythonw.exe', 'node.exe', 'java.exe', 'powershell.exe', 'pwsh.exe',
    'searchui.exe', 'taskmgr.exe', 'cmd.exe', 'wt.exe', 'mspaint.exe',
    'calc.exe', 'spotify.exe', 'skype.exe', 'onedrive.exe', 'chrome_child.exe',
    'openconsole.exe', 'registry.exe', 'memcompression.exe', 'searchindexer.exe',
}

_KNOWN_GAME_PATH_TOKENS = (
    'steamapps', 'steamapps\\common', 'epic games', 'gog games',
    'origin games', 'ubisoft', 'battle.net', 'battle.net launcher',
    'ea games', 'ea app', 'xbox games', 'windowsapps', 'games', 'jogos',
    'gog galaxy', 'steam', 'uplay', 'rockstar games', 'bethesda',
)

_WINDOWS_SYSTEM_ROOTS = (
    'c:\\windows',
    'c:\\windows\\system32',
    'c:\\program files\\windowsapps',
)
_NON_GAME_PATH_TOKENS = (
    'free download manager',
)

_VERSION_TITLE_RE = re.compile(r'^(?:v|version|release|beta|alpha|preview)?\s*[0-9]+(?:[._-][0-9]+)*(?:[._-]?[0-9]*)?$', re.IGNORECASE)


class DetectorPresenca:
    """Monitora presença em background com polling eficiente."""

    def __init__(self, callback: Callable[[dict], None] | None = None, intervalo_segundos: int = 5):
        self.callback = callback
        self.intervalo = max(3, min(intervalo_segundos, 5))
        self._thread = None
        self._ativo = False
        self._lock = threading.Lock()
        self._estado_anterior = {
            'steam_ativo': False,
            'hydra_ativo': False,
            'jogo_atual': '',
            'appid': None,
            'path': '',
            'playing': False,
            'online': False,
            'launcher': 'Nenhum',
            'launcher_icon': 'fa-solid fa-circle',
            'state': 'offline',
            'timestamp': 0,
        }
        self._ultimo_pid = None
        self._ultimo_caminho = ''
        self._validacao_continua = 0
        self._sem_ultimo_jogo = False
        self._caminho_cache_aprendizado = os.path.join(os.path.dirname(__file__), 'cache', 'executaveis_aprendidos.json')
        self._jogo_esperado: dict = {}

    def registrar_jogo_esperado(self, titulo: str, appid: int | str | None = None, caminho: str = '') -> None:
        self._jogo_esperado = {
            'titulo': (titulo or '').strip(),
            'appid': str(appid or '').strip(),
            'caminho': self._normalizar_caminho(caminho),
            'expires_at': time.time() + 45,
        }

    def limpar_jogo_esperado(self) -> None:
        self._jogo_esperado = {}

    def iniciar(self) -> None:
        with self._lock:
            if self._ativo:
                return
            self._ativo = True
            try:
                print('[Presença] Monitor iniciado')
                estado_inicial = self._verificar_processos()
                self._processar_mudanca_estado(estado_inicial)
            except Exception as e:
                print(f'[Presença] Erro na verificação inicial: {e}')

        self._thread = threading.Thread(target=self._loop_monitoramento, daemon=True)
        self._thread.start()

    def parar(self) -> None:
        with self._lock:
            self._ativo = False
        if self._thread:
            self._thread.join(timeout=2)

    def _loop_monitoramento(self) -> None:
        while self._ativo:
            try:
                estado = self._verificar_processos()
                self._processar_mudanca_estado(estado)
            except Exception as e:
                print(f'[Presença] Erro ao monitorar: {e}')
            time.sleep(self.intervalo)

    def _verificar_processos(self) -> dict:
        if platform.system() != 'Windows':
            print('[Presença] Sistema não é Windows; pulando detecção.')
            return self._estado_padrao()

        processos = self._listar_processos_ativos()
        steam_ativo = self._processo_ativo(processos, _STEAM_PROCESSOS)
        hydra_ativo = self._processo_ativo(processos, _HYDRA_PROCESSOS)
        launchers_detectados = []
        if steam_ativo:
            launchers_detectados.append('Steam')
        if hydra_ativo:
            launchers_detectados.append('Hydra')

        biblioteca = self._obter_jogos_candidatos()
        jogo_info = self._identificar_jogo_info(processos, biblioteca)
        jogo_atual = jogo_info.get('name') if jogo_info else ''
        appid = jogo_info.get('appid') if jogo_info else None
        path = jogo_info.get('path') if jogo_info else ''
        launcher_from_game = jogo_info.get('launcher') if jogo_info else ''
        playing = False
        if jogo_atual and self._validar_processo_jogo(processos, jogo_info):
            playing = True
        else:
            jogo_atual = ''
            appid = None
            path = ''
            launcher_from_game = ''

        online = bool(steam_ativo or hydra_ativo or playing or launchers_detectados)

        launcher_display = ' + '.join(dict.fromkeys(launchers_detectados)) if launchers_detectados else 'Nenhum'
        launcher_icon = 'fa-brands fa-steam' if steam_ativo and not hydra_ativo else 'fa-solid fa-fire' if hydra_ativo and not steam_ativo else 'fa-solid fa-layer-group' if steam_ativo and hydra_ativo else 'fa-solid fa-circle'
        state = self._inferir_estado(steam_ativo=steam_ativo, hydra_ativo=hydra_ativo, playing=playing)

        # Logs de diagnóstico formatados
        print('[Presence]')
        print(f'Steam: {"ABERTA" if steam_ativo else "FECHADA"}')
        print(f'Hydra: {"ABERTO" if hydra_ativo else "FECHADO"}')
        print(f'Jogo: {jogo_atual or "Nenhum"}')

        if playing:
            print(f'Resultado: Jogando {jogo_atual}')
        elif steam_ativo:
            print('Resultado: Na Steam')
        elif hydra_ativo:
            print('Resultado: No Hydra Launcher')
        else:
            print('Resultado: Offline')

        return {
            'steam_ativo': steam_ativo,
            'hydra_ativo': hydra_ativo,
            'jogo_atual': jogo_atual,
            'appid': appid,
            'path': path,
            'playing': playing,
            'online': online,
            'launcher': launcher_display if not playing else (launcher_from_game or launcher_display),
            'launcher_icon': launcher_icon,
            'state': state,
            'timestamp': time.time(),
        }

    def _estado_padrao(self) -> dict:
        return {
            'steam_ativo': False,
            'hydra_ativo': False,
            'jogo_atual': '',
            'appid': None,
            'playing': False,
            'online': False,
            'launcher': 'Nenhum',
            'launcher_icon': 'fa-solid fa-circle',
            'state': 'offline',
            'timestamp': time.time(),
        }

    def _listar_processos_ativos(self) -> list[dict]:
        if not HAS_PSUTIL:
            return []
        processos: list[dict] = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
                info = proc.info or {}
                if info.get('name') or info.get('exe') or info.get('cmdline'):
                    processos.append(info)
        except Exception as exc:
            print(f'[Presença] Erro ao listar processos: {exc}')
        return processos

    def _processo_ativo(self, processos: list[dict], nomes: list[str]) -> bool:
        nomes_norm = {nome.lower() for nome in nomes}
        for proc in processos:
            nome = self._nome_proc(proc)
            if not nome:
                continue
            if nome.lower() in nomes_norm:
                return True
        return False

    def _validar_processo_jogo(self, processos: list[dict], jogo_info: dict) -> bool:
        if not jogo_info:
            return False
        path = jogo_info.get('path') or ''
        pid = jogo_info.get('pid')
        if not path:
            return False

        path_norm = self._normalizar_caminho(path)
        nome_exe = os.path.basename(path_norm).lower()
        if self._eh_executavel_blacklisted(nome_exe):
            return False
        if self._caminho_eh_software_nao_jogo(path_norm):
            return False
        if self._caminho_eh_windows(path_norm):
            return False

        for attempt in range(3):
            processos_ativos = self._listar_processos_ativos()
            proc = None
            if pid is not None:
                proc = next((p for p in processos_ativos if p.get('pid') == pid), None)
            if not proc:
                proc = next(
                    (p for p in processos_ativos if self._normalizar_caminho(self._extrair_caminho_proc(p)) == path_norm),
                    None,
                )

            if not proc:
                print(f'[Presença] Processo não encontrado no ciclo {attempt + 1} para {path_norm}')
                time.sleep(0.5)
                continue

            proc_path = self._normalizar_caminho(self._extrair_caminho_proc(proc))
            if proc_path != path_norm:
                print(f'[Presença] Caminho do processo não corresponde: {proc_path} != {path_norm}')
                return False

            if self._eh_executavel_blacklisted(self._nome_proc(proc)):
                print(f'[Presença] Processo em blacklist detectado: {proc_path}')
                return False
            if self._caminho_eh_software_nao_jogo(proc_path):
                print(f'[Presença] Software não-jogo detectado: {proc_path}')
                return False

            if self._caminho_eh_windows(proc_path):
                print(f'[Presença] Processo em pasta de sistema detectado: {proc_path}')
                return False

            if pid is not None and not self._pid_existe(pid):
                print(f'[Presença] PID removido: {pid}')
                return False

            print(f'[Presença] Processo validado: PID {proc.get("pid")} ({nome_exe})')
            return True

        print(f'[Presença] Falha na validação do processo após 3 tentativas: {path_norm}')
        return False

    def _processo_tem_janela(self, proc: dict) -> bool:
        if self._eh_executavel_blacklisted(self._nome_proc(proc)):
            return False
        janela = proc.get('window') or proc.get('window_name') or proc.get('windows')
        if isinstance(janela, (list, tuple)):
            return bool(janela)
        if isinstance(janela, str):
            return bool(janela.strip())
        return False

    def _pid_existe(self, pid: int) -> bool:
        if not HAS_PSUTIL:
            return False
        try:
            return psutil.pid_exists(pid)
        except Exception:
            return False

    def _nome_proc(self, proc: dict) -> str:
        if not proc:
            return ''
        nome = proc.get('name') or ''
        if isinstance(nome, str) and nome:
            return os.path.basename(nome)
        caminho = self._extrair_caminho_proc(proc)
        if caminho:
            return os.path.basename(caminho)
        return ''

    def _eh_executavel_blacklisted(self, nome_exe: str) -> bool:
        if not nome_exe:
            return False
        return nome_exe.lower() in _BLACKLISTED_EXES

    def _caminho_eh_windows(self, caminho: str) -> bool:
        if not caminho:
            return False
        caminho_norm = self._normalizar_caminho(caminho).lower()
        return any(caminho_norm.startswith(root) for root in _WINDOWS_SYSTEM_ROOTS)

    def _caminho_eh_jogo(self, caminho: str) -> bool:
        if not caminho:
            return False
        caminho_norm = self._normalizar_caminho(caminho).lower()
        if any(token in caminho_norm for token in _KNOWN_GAME_PATH_TOKENS):
            return True
        return False

    def _caminho_eh_software_nao_jogo(self, caminho: str) -> bool:
        caminho_norm = self._normalizar_caminho(caminho).lower()
        return any(token in caminho_norm for token in _NON_GAME_PATH_TOKENS)

    def _obter_metadados_executavel(self, caminho: str) -> dict:
        caminho_norm = self._normalizar_caminho(caminho)
        if platform.system() != 'Windows' or not caminho_norm or not os.path.isfile(caminho_norm):
            return {}

        try:
            size = ctypes.windll.version.GetFileVersionInfoSizeW(caminho_norm, None)
            if not size:
                return {}
            res = ctypes.create_string_buffer(size)
            ctypes.windll.version.GetFileVersionInfoW(caminho_norm, 0, size, res)
            lptr = wintypes.LPVOID()
            lsize = wintypes.UINT()
            if not ctypes.windll.version.VerQueryValueW(res, '\\VarFileInfo\\Translation', ctypes.byref(lptr), ctypes.byref(lsize)) or not lsize.value:
                return {}
            lang_codepage = ctypes.cast(lptr, ctypes.POINTER(ctypes.c_ushort * 2)).contents
            info = {}
            codepage = f'{lang_codepage[0]:04x}{lang_codepage[1]:04x}'
            for field in ('ProductName', 'FileDescription'):
                value_ptr = wintypes.LPVOID()
                value_size = wintypes.UINT()
                sub_block = f'\\StringFileInfo\\{codepage}\\{field}'
                if ctypes.windll.version.VerQueryValueW(res, sub_block, ctypes.byref(value_ptr), ctypes.byref(value_size)) and value_size.value:
                    info[field] = ctypes.wstring_at(value_ptr, value_size.value).strip()
            return info
        except Exception:
            return {}

    def _metadados_sugerem_jogo(self, caminho: str) -> bool:
        info = self._obter_metadados_executavel(caminho)
        if not info:
            return False
        texto = ' '.join(str(info.get(k, '') or '') for k in ('ProductName', 'FileDescription')).lower()
        if not texto:
            return False
        if any(neg in texto for neg in ('microsoft', 'windows', 'visual studio', 'chrome', 'spotify', 'discord', 'edge', 'firefox', 'opera', 'teamviewer', 'skype', 'outlook', 'onenote')):
            return False
        return any(token in texto for token in ('game', 'engine', 'play', 'edition', 'deluxe', 'remastered', 'anniversary', 'battle', 'heroes', 'legends', 'arena', 'warfare', 'story', 'adventure'))

    def _nome_valido_para_jogo(self, nome: str) -> bool:
        if not nome:
            return False
        nome_limpo = nome.strip().lower()
        if _VERSION_TITLE_RE.match(nome_limpo):
            return False
        if re.search(r'\b\d+(?:[._-]\d+){1,}\b', nome_limpo):
            return False
        return not any(token in nome_limpo for token in ('version', 'release', 'update', 'beta', 'alpha', 'preview'))

    def _extrair_caminho_proc(self, proc: dict) -> str:
        caminho_proc = proc.get('exe') or proc.get('cmdline') or ''
        if isinstance(caminho_proc, list):
            caminho_proc = ' '.join(str(item) for item in caminho_proc if item)
        elif isinstance(caminho_proc, tuple):
            caminho_proc = ' '.join(str(item) for item in caminho_proc if item)
        if isinstance(caminho_proc, str):
            return str(caminho_proc).strip()
        return ''

    def _obter_cache_aprendizado(self) -> dict:
        try:
            if not os.path.exists(self._caminho_cache_aprendizado):
                return {}
            with open(self._caminho_cache_aprendizado, 'r', encoding='utf-8') as handle:
                payload = json.load(handle)
                return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def _salvar_cache_aprendizado(self, dados: dict) -> None:
        try:
            os.makedirs(os.path.dirname(self._caminho_cache_aprendizado), exist_ok=True)
            with open(self._caminho_cache_aprendizado, 'w', encoding='utf-8') as handle:
                json.dump(dados, handle, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _aprender_executavel(self, caminho: str, nome_jogo: str, appid: str | None = None) -> None:
        if not caminho or not nome_jogo:
            return
        caminho_norm = self._normalizar_caminho(caminho)
        dados = self._obter_cache_aprendizado()
        entrada = {
            'name': nome_jogo,
            'appid': appid,
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }
        dados[caminho_norm] = entrada
        if caminho and caminho != caminho_norm:
            dados[caminho] = entrada
        self._salvar_cache_aprendizado(dados)

    def _resolver_nome_por_cache(self, caminho: str) -> str:
        if not caminho:
            return ''
        caminho_norm = self._normalizar_caminho(caminho)
        dados = self._obter_cache_aprendizado()
        item = dados.get(caminho_norm)
        if isinstance(item, dict):
            return str(item.get('name') or '').strip()
        if isinstance(item, str):
            return item.strip()
        return ''

    def _obter_jogos_candidatos(self) -> list[dict]:
        candidatos: list[dict] = []

        indice_steam = carregar_indice_steam_local()
        for jogo in indice_steam:
            nome = (jogo.get('name') or '').strip()
            pasta_instalacao = (jogo.get('path') or '').strip()
            discovered_exe = ''
            if pasta_instalacao and os.path.isdir(pasta_instalacao):
                discovered_exe = self._descobrir_executavel_em_pasta(pasta_instalacao, nome)
            if not pasta_instalacao and jogo.get('manifest'):
                try:
                    pasta_instalacao = os.path.dirname(str(jogo.get('manifest') or ''))
                except Exception:
                    pasta_instalacao = ''
                if pasta_instalacao and os.path.isdir(pasta_instalacao) and not discovered_exe:
                    discovered_exe = self._descobrir_executavel_em_pasta(pasta_instalacao, nome)

            if nome and (discovered_exe or pasta_instalacao):
                candidatos.append({
                    'titulo': nome,
                    'caminho_exe': discovered_exe,
                    'pasta_instalacao': pasta_instalacao,
                    'appid': int(jogo.get('appid')) if str(jogo.get('appid') or '').isdigit() else None,
                    'origem': 'steam_instalada'
                })

        try:
            if BIBLIOTECA_DB and isinstance(BIBLIOTECA_DB, dict):
                for item in BIBLIOTECA_DB.values():
                    item_dict = item if isinstance(item, dict) else {}
                    jogo = JOGOS_DB.get(getattr(item, 'jogo_id', None) or item_dict.get('jogo_id'))
                    titulo = (
                        getattr(jogo, 'titulo', '') if jogo else ''
                    ) or getattr(item, 'titulo', '') or getattr(item, 'name', '') or item_dict.get('titulo') or item_dict.get('name') or ''
                    caminho = str(
                        getattr(item, 'executable_path', '') or getattr(item, 'executavel', '') or
                        getattr(item, 'executable', '') or getattr(item, 'launch_path', '') or
                        item_dict.get('executable_path') or item_dict.get('executavel') or
                        item_dict.get('executable') or item_dict.get('launch_path') or ''
                    ).strip()
                    executaveis = getattr(item, 'executables', None) or getattr(item, 'executaveis', None) or item_dict.get('executables') or item_dict.get('executaveis') or []
                    if isinstance(executaveis, str):
                        executaveis = [executaveis]
                    pasta_instalacao = str(
                        getattr(item, 'install_folder', '') or getattr(item, 'pasta_instalacao', '') or
                        item_dict.get('install_folder') or item_dict.get('pasta_instalacao') or ''
                    ).strip()
                    if not pasta_instalacao and caminho:
                        pasta_instalacao = os.path.dirname(caminho)
                    appid = getattr(item, 'codigo_origem', '') or item_dict.get('codigo_origem') or ''
                    launcher = getattr(item, 'launcher', '') or item_dict.get('launcher') or getattr(item, 'origem', '') or item_dict.get('origem') or 'manual'

                    if titulo and (caminho or pasta_instalacao):
                        candidatos.append({
                            'titulo': titulo,
                            'caminho_exe': caminho,
                            'executaveis': [str(exe).strip() for exe in executaveis if str(exe).strip()],
                            'pasta_instalacao': pasta_instalacao,
                            'appid': int(appid) if str(appid).isdigit() else None,
                            'origem': 'steam_instalada' if str(launcher).lower() == 'steam' else 'biblioteca_local'
                        })
        except Exception as e:
            print(f'[Presença] Erro ao ler biblioteca local: {e}')

        # O cache é uma relação executável -> jogo aprendida pelo scanner.
        # Ele permite reconhecer jogos cadastrados sem uma nova varredura.
        for caminho, registro in self._obter_cache_aprendizado().items():
            if not isinstance(registro, dict):
                continue
            titulo = str(registro.get('name') or '').strip()
            caminho_exe = str(caminho or '').strip()
            if not titulo or not caminho_exe.lower().endswith('.exe'):
                continue
            appid = registro.get('appid')
            candidatos.append({
                'titulo': titulo,
                'caminho_exe': caminho_exe,
                'pasta_instalacao': os.path.dirname(caminho_exe),
                'appid': int(appid) if str(appid).isdigit() else None,
                'origem': 'steam_instalada' if str(appid).isdigit() else 'biblioteca_local',
            })

        return candidatos

    def _descobrir_executavel_em_pasta(self, pasta: str, titulo: str | None = None) -> str:
        """Tenta localizar o executável principal dentro de uma pasta de jogo.
        Estratégia:
        - procurar por arquivo cujo nome (sem extensão) contenha palavras do título
        - procurar por executáveis no nível superior
        - procurar em subpastas comuns (bin, Binaries, x64)
        Retorna caminho absoluto do exe encontrado ou '' se não encontrar.
        """
        try:
            title_tokens = [(t or '').lower() for t in re.split(r'\W+', (titulo or '')) if t]
        except Exception:
            title_tokens = []

        # procurar em níveis limitados
        search_paths = [pasta]
        for sub in ('Binaries', 'bin', 'Win64', 'x64'):
            search_paths.append(os.path.join(pasta, sub))

        candidates = []
        for p in search_paths:
            if not os.path.isdir(p):
                continue
            try:
                for entry in os.listdir(p):
                    full = os.path.join(p, entry)
                    if os.path.isfile(full) and entry.lower().endswith('.exe'):
                        candidates.append(full)
            except Exception:
                continue

        # Priorizar matches por título
        if title_tokens and candidates:
            for c in candidates:
                base = os.path.splitext(os.path.basename(c))[0].lower()
                if all(tok in base for tok in title_tokens[:2]):
                    return self._normalizar_caminho(c)

        # Se nenhum match por título, escolher o primeiro candidato que contenha parte do nome
        if title_tokens and candidates:
            for c in candidates:
                base = os.path.splitext(os.path.basename(c))[0].lower()
                if any(tok in base for tok in title_tokens):
                    return self._normalizar_caminho(c)

        # fallback: primeiro .exe encontrado
        if candidates:
            return self._normalizar_caminho(candidates[0])

        return ''

    def _normalizar_caminho(self, caminho: str) -> str:
        if not caminho:
            return ''
        try:
            caminho_norm = os.path.normcase(os.path.normpath(str(caminho).strip()))
        except Exception:
            caminho_norm = str(caminho).strip().lower()
        return caminho_norm

    def _caminho_eh_sistema(self, caminho: str) -> bool:
        if not caminho:
            return False
        caminho_norm = self._normalizar_caminho(caminho).lower()
        if not caminho_norm:
            return False
        roots = (
            'c:\\windows',
            'c:\\program files',
            'c:\\program files (x86)',
            '/windows',
            '/usr/bin',
            '/usr/lib',
            '/opt',
        )
        return any(caminho_norm.startswith(root) for root in roots)

    def _obter_metricas_proc(self, proc: dict, chave: str):
        valor = proc.get(chave)
        if valor is None:
            return None
        if chave == 'memory_info':
            if isinstance(valor, tuple):
                return int(valor[0] or 0)
            if hasattr(valor, 'rss'):
                return int(getattr(valor, 'rss', 0) or 0)
        return valor

    def _tem_janela_grafica(self, proc: dict) -> bool:
        janela = proc.get('window_name') or proc.get('windows') or proc.get('window')
        if isinstance(janela, (list, tuple)):
            return bool(janela)
        return bool(janela)

    def _avaliar_heuristica_jogo(self, proc: dict) -> int:
        nome_proc = self._nome_proc(proc).lower()
        caminho_proc = self._extrair_caminho_proc(proc)
        caminho_norm = self._normalizar_caminho(caminho_proc)

        if not caminho_proc and not nome_proc:
            return 0

        nome_base = os.path.splitext(os.path.basename(caminho_proc))[0].lower() if caminho_proc else nome_proc
        if nome_proc in _STEAM_PROCESSOS or nome_proc in _HYDRA_PROCESSOS or nome_proc in _KNOWN_SYSTEM_EXES or self._eh_executavel_blacklisted(nome_proc):
            return 0
        if nome_base in _STEAM_PROCESSOS or nome_base in _HYDRA_PROCESSOS:
            return 0

        if not self._caminho_eh_jogo(caminho_norm) and not self._metadados_sugerem_jogo(caminho_norm) and nome_base not in _PROCESS_SIGNATURES:
            return 0

        score = 0
        if caminho_proc.lower().endswith('.exe'):
            score += 2
        if self._caminho_eh_jogo(caminho_norm):
            score += 3
        if self._metadados_sugerem_jogo(caminho_norm):
            score += 2
        if self._tem_janela_grafica(proc):
            score += 1
        if nome_proc not in _KNOWN_SYSTEM_EXES and not nome_proc.endswith('.dll'):
            score += 1
        cpu_percent = self._obter_metricas_proc(proc, 'cpu_percent')
        if isinstance(cpu_percent, (int, float)) and cpu_percent > 5:
            score += 1
        memory_info = self._obter_metricas_proc(proc, 'memory_info')
        if isinstance(memory_info, (int, float)) and memory_info > 100 * 1024 * 1024:
            score += 1
        create_time = self._obter_metricas_proc(proc, 'create_time')
        if isinstance(create_time, (int, float)):
            idade_segundos = max(0, time.time() - float(create_time))
            if idade_segundos >= 10:
                score += 1
        if nome_base in _PROCESS_SIGNATURES or any(token in nome_proc for token in ('game', 'gameplay')):
            score += 1
        return score

    def _normalizar_nome_pasta(self, nome: str) -> str:
        nome_limpo = re.sub(r'\s+', ' ', (nome or '').replace('_', ' ').strip())
        if not nome_limpo:
            return ''
        if re.search(r'\bblack myth\b', nome_limpo, re.IGNORECASE) and re.search(r'\bwukong\b', nome_limpo, re.IGNORECASE):
            return 'Black Myth: Wukong'
        return nome_limpo

    def _caminho_compativel_com_titulo(self, caminho: str, titulo: str) -> bool:
        partes_caminho = re.split(r'[^a-z0-9]+', self._normalizar_caminho(caminho).lower())
        tokens_titulo = [token for token in re.split(r'[^a-z0-9]+', (titulo or '').lower()) if len(token) >= 4]
        return bool(tokens_titulo and any(token in partes_caminho for token in tokens_titulo))

    def _inferir_nome_jogo(self, proc: dict, caminho: str | None = None) -> str:
        caminho_proc = caminho or self._extrair_caminho_proc(proc)
        nome_proc = self._nome_proc(proc)
        base = os.path.splitext(os.path.basename(caminho_proc))[0].lower() if caminho_proc else nome_proc.lower()
        if base in _PROCESS_SIGNATURES:
            return _PROCESS_SIGNATURES[base]
        if caminho_proc:
            pasta = os.path.basename(os.path.dirname(caminho_proc))
            if pasta and pasta.lower() not in {'', '.', 'games', 'jogos'}:
                return self._normalizar_nome_pasta(pasta)
        if nome_proc:
            return self._normalizar_nome_pasta(os.path.splitext(nome_proc)[0])
        return 'Executável desconhecido'

    # Removidas funcionalidades de armazenamento de executáveis conhecidos para manter o detector focado apenas em processos atuais.

    def _identificar_jogo_info(self, processos: list[dict], biblioteca: list[dict] | None = None) -> dict:
        """Resolve o processo ativo contra os jogos já cadastrados na biblioteca."""
        jogos = biblioteca or self._obter_jogos_candidatos()
        print(f'[GAME STATUS] Processos analisados: {len(processos)} | Jogos indexados: {len(jogos)}')
        if not jogos:
            print('[Presence] Biblioteca carregada: 0 jogos')
        else:
            print(f'[Presence] Biblioteca carregada: {len(jogos)} jogos')

        melhor = None
        esperado = self._jogo_esperado if self._jogo_esperado.get('expires_at', 0) > time.time() else {}
        for proc in processos:
            caminho_proc = self._normalizar_caminho(self._extrair_caminho_proc(proc))
            nome_proc = os.path.basename(caminho_proc).lower()
            if (
                not caminho_proc
                or not caminho_proc.lower().endswith('.exe')
                or nome_proc in _KNOWN_SYSTEM_EXES
                or self._eh_executavel_blacklisted(nome_proc)
            ):
                continue
            if nome_proc in _STEAM_PROCESSOS or nome_proc in _HYDRA_PROCESSOS or self._caminho_eh_windows(caminho_proc):
                continue
            if self._caminho_eh_software_nao_jogo(caminho_proc):
                continue
            print(f'[GAME STATUS] Processo candidato: {os.path.basename(self._extrair_caminho_proc(proc)) or nome_proc}')

            processo_appid = proc.get('appid') or proc.get('gameid') or proc.get('steam_appid')
            for jogo in jogos:
                titulo = str(jogo.get('titulo') or jogo.get('title') or jogo.get('name') or '').strip()
                caminhos_exe = [jogo.get('caminho_exe') or jogo.get('exe_path') or '']
                caminhos_exe.extend(jogo.get('executaveis') or jogo.get('executables') or [])
                caminhos_exe = [self._normalizar_caminho(str(caminho).strip()) for caminho in caminhos_exe if str(caminho).strip()]
                caminho_exe = caminhos_exe[0] if caminhos_exe else ''
                pasta = self._normalizar_caminho(str(jogo.get('pasta_instalacao') or jogo.get('install_folder') or '').strip())
                appid = jogo.get('appid') if jogo.get('appid') else None
                if not titulo or (not caminho_exe and not pasta):
                    continue

                nomes_esperados = {os.path.basename(caminho).lower() for caminho in caminhos_exe}
                nomes_esperados = {
                    nome for nome in nomes_esperados
                    if nome not in _STEAM_PROCESSOS and nome not in _HYDRA_PROCESSOS and not self._eh_executavel_blacklisted(nome)
                }
                if not nomes_esperados and not pasta:
                    continue

                score = 0
                caminho_compativel = self._caminho_eh_jogo(caminho_proc) or self._caminho_compativel_com_titulo(caminho_proc, titulo)
                identidade_forte = bool(processo_appid and appid and str(processo_appid) == str(appid))
                if esperado.get('appid') and appid and esperado['appid'] == str(appid):
                    score += 220
                if esperado.get('titulo') and esperado['titulo'].casefold() == titulo.casefold():
                    score += 180
                if esperado.get('caminho') and esperado['caminho'].lower() == caminho_proc.lower():
                    score += 220
                if processo_appid and appid and str(processo_appid) == str(appid):
                    score += 150
                if caminho_proc.lower() in {caminho.lower() for caminho in caminhos_exe} and (caminho_compativel or identidade_forte):
                    score += 100
                if pasta and caminho_compativel and (caminho_proc.lower() == pasta.lower() or caminho_proc.lower().startswith(pasta.lower().rstrip('\\/') + os.sep)):
                    score += 80
                if nome_proc in nomes_esperados and pasta:
                    score += 35
                if score < 70:
                    continue

                candidato = {
                    'name': titulo,
                    'appid': appid,
                    'path': caminho_proc,
                    'launcher': 'steam' if jogo.get('origem') == 'steam_instalada' else 'local',
                    'pid': proc.get('pid') or proc.get('PID'),
                    'executable': os.path.basename(self._extrair_caminho_proc(proc)) or os.path.basename(caminho_proc),
                    'confidence': min(score / 150, 1.0),
                    '_score': score,
                }
                if melhor is None or candidato['_score'] > melhor['_score']:
                    melhor = candidato

        if melhor:
            melhor.pop('_score', None)
            self._aprender_executavel(melhor['path'], melhor['name'], str(melhor['appid']) if melhor['appid'] else None)
            melhor['source'] = 'Steam' if melhor['launcher'] == 'steam' else 'Local'
            print(f"[GAME STATUS] Jogo identificado: {melhor['name']} | Fonte: {melhor['source']} | AppID: {melhor['appid'] or 'n/a'}")
            print(f"[Presence] Processo resolvido: {melhor['executable']} -> {melhor['name']} ({melhor['confidence']:.2f})")
            return melhor

        print('[GAME STATUS] Nenhuma correspondência encontrada')
        return {}

    def _identificar_jogo_por_assinatura(self, proc: dict) -> dict:
        caminho_proc = self._extrair_caminho_proc(proc)
        caminho_proc_norm = self._normalizar_caminho(caminho_proc)
        if not caminho_proc_norm:
            return {}

        nome_proc_basename = os.path.basename(caminho_proc_norm).lower()
        if nome_proc_basename in _STEAM_PROCESSOS or nome_proc_basename in _HYDRA_PROCESSOS or self._eh_executavel_blacklisted(nome_proc_basename):
            return {}

        nome_exe_sem_extensao = os.path.splitext(nome_proc_basename)[0].lower()
        titulo = _PROCESS_SIGNATURES.get(nome_exe_sem_extensao)
        if not titulo:
            return {}

        pid = proc.get('pid') or proc.get('PID')
        return {
            'name': titulo,
            'appid': None,
            'path': caminho_proc_norm,
            'launcher': 'local',
            'pid': pid,
        }

    def _identificar_jogo_por_executavel_conhecido(self, proc: dict, executaveis: list[dict]) -> dict:
        caminho_proc = self._extrair_caminho_proc(proc)
        caminho_proc_norm = self._normalizar_caminho(caminho_proc)
        nome_proc = self._nome_proc(proc).lower()
        if not caminho_proc_norm and not nome_proc:
            return {}

        for executavel in executaveis:
            exe_path = str(executavel.get('exe_path') or '').strip()
            exe_name = str(executavel.get('exe_name') or '').strip().lower()
            if exe_path and caminho_proc_norm and self._normalizar_caminho(exe_path) == caminho_proc_norm:
                return {
                    'name': executavel.get('display_name') or self._inferir_nome_jogo(proc, exe_path),
                    'appid': None,
                    'path': caminho_proc_norm,
                    'launcher': executavel.get('launcher') or 'local',
                }
            if exe_name and nome_proc and exe_name == nome_proc:
                return {
                    'name': executavel.get('display_name') or self._inferir_nome_jogo(proc, exe_path),
                    'appid': None,
                    'path': caminho_proc_norm,
                    'launcher': executavel.get('launcher') or 'local',
                }

        return {}

    def _inferir_estado(self, *, steam_ativo: bool, hydra_ativo: bool, playing: bool) -> str:
        if playing:
            return 'playing'
        if steam_ativo:
            return 'steam_only'
        if hydra_ativo:
            return 'hydra_only'
        return 'offline'

    def _identificar_jogo_em_execucao(self, processos: list[dict], biblioteca: list[dict] | None = None) -> str:
        """Compatibilidade: retorna apenas o nome do jogo (string) como antes.
        Internamente chama `_identificar_jogo_info` e extrai o `name` quando disponível.
        """
        info = self._identificar_jogo_info(processos, biblioteca)
        return info.get('name') if info else ''

    def _score_match(self, valor_a: str, valor_b: str) -> float:
        if not valor_a or not valor_b:
            return 0.0
        return SequenceMatcher(None, valor_a, valor_b).ratio()

    def _processar_mudanca_estado(self, estado: dict) -> None:
        # Não confiar no estado anterior para decidir — recalcular sempre e propagar
        try:
            # Atualiza estado anterior para inspeção/consulta
            self._estado_anterior = estado.copy()
            # Propaga para callback sempre que o detector roda (backend decide persistir)
            if self.callback:
                self.callback(estado)

            # Mensagem de log resumida
            if estado.get('jogo_atual'):
                status = f"Jogando {estado['jogo_atual']}"
            elif estado.get('steam_ativo'):
                status = 'Na Steam'
            elif estado.get('hydra_ativo'):
                status = 'No Hydra Launcher'
            else:
                status = 'Offline'
            print(f'[Detector] Estado recalculado: {status}')
        except Exception as e:
            print(f'[Detector] Erro ao processar estado: {e}')

    def steam_aberta(self) -> bool:
        estado = self._verificar_processos()
        return estado.get('steam_ativo', False)

    def hydra_aberta(self) -> bool:
        estado = self._verificar_processos()
        return estado.get('hydra_ativo', False)

    def obter_estado(self) -> dict:
        return self._estado_anterior.copy()

    def obter_estado_ao_vivo(self) -> dict:
        try:
            estado = self._verificar_processos()
            self._processar_mudanca_estado(estado)
            return estado
        except Exception as e:
            print(f'[Detector] Erro ao obter estado ao vivo: {e}')
            return self._estado_padrao()


_detector_global: DetectorPresenca | None = None


def inicializar_detector(callback: Callable[[dict], None] | None = None) -> DetectorPresenca:
    global _detector_global
    if _detector_global is None:
        _detector_global = DetectorPresenca(callback=callback, intervalo_segundos=5)
        _detector_global.iniciar()
    return _detector_global


def obter_detector() -> DetectorPresenca | None:
    return _detector_global


def resolve_playing_game(process: dict, biblioteca: list[dict] | None = None) -> dict:
    """Resolve um processo individual usando somente jogos cadastrados."""
    detector = DetectorPresenca()
    return detector._identificar_jogo_info([process], biblioteca)


def parar_detector() -> None:
    global _detector_global
    if _detector_global:
        _detector_global.parar()
        _detector_global = None
