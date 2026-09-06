import os
import re
import subprocess
import ctypes
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable

from game_validator import is_valid_game_record
from game_matcher import names_match

IGNORAR_NOMES = {
    'unins000.exe',
    'setup.exe',
    'install.exe',
    'launcher_updater.exe',
    'crashreport.exe',
    'vc_redist.exe',
    'dxsetup.exe',
    'easyanticheat.exe',
    'redistributable.exe',
    'benchmark.exe',
    'updater.exe',
    'installer.exe',
    'uninstall.exe',
    'steam.exe',
    'unitycrashhandler.exe',
    'eac.exe',
}

IGNORAR_PASTAS = {
    '_commonredist',
    'engine',
    'redistributables',
    'support',
    'installer',
    'directx',
    'vc',
    'tools',
    'redist',
    'bin',
}

PRIORIDADE_NOMES = [
    'shipping',
    'win64',
    'game',
    'b1',
    're4',
    'eldenring',
    'tekken',
    'resident',
    'witcher',
    'gow',
    'doom',
]


def iniciar_executavel(executavel: str, cwd: str | None = None, logger=None) -> dict:
    """Inicia um jogo normal ou com elevação quando o executável exigir UAC."""
    caminho = (executavel or '').strip()
    diretorio = cwd or os.path.dirname(os.path.abspath(caminho))
    try:
        processo = subprocess.Popen([caminho], cwd=diretorio, shell=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {'ok': True, 'pid': getattr(processo, 'pid', None), 'elevated': False}
    except OSError as exc:
        winerror = getattr(exc, 'winerror', None)
        if os.name != 'nt' or winerror != 740:
            raise

        if logger:
            logger(f'[Jogar] {os.path.basename(caminho)} exige elevação; solicitando UAC.')
        resultado = ctypes.windll.shell32.ShellExecuteW(None, 'runas', caminho, None, diretorio, 1)
        if resultado <= 32:
            raise OSError(f'Falha ao iniciar com elevação (ShellExecuteW={resultado}).')
        return {'ok': True, 'pid': None, 'elevated': True}


class LauncherManager:
    def __init__(self, logger=None):
        self.logger = logger

    def log(self, mensagem: str) -> None:
        if self.logger:
            self.logger(mensagem)
        else:
            print(mensagem)

    def _normalizar(self, texto: str) -> str:
        return re.sub(r'\s+', ' ', (texto or '').strip().lower())

    def _tokens_do_texto(self, texto: str) -> list[str]:
        return re.findall(r'[a-z0-9]+', (texto or '').lower())

    def _similaridade_textos(self, a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        return SequenceMatcher(None, self._normalizar(a), self._normalizar(b)).ratio()

    def _is_ignored_name(self, nome_arquivo: str) -> bool:
        nome = (nome_arquivo or '').lower()
        base = os.path.splitext(nome)[0].lower()
        return base in IGNORAR_NOMES or nome in IGNORAR_NOMES

    def _is_ignored_dir(self, path: str) -> bool:
        if not path:
            return True
        parts = [p.lower() for p in Path(path).parts]
        return any(part in IGNORAR_PASTAS for part in parts)

    def _candidate_score(self, exe_path: str, folder_name: str) -> tuple[int, str, str]:
        nome_arquivo = Path(exe_path).stem.lower()
        folder = (folder_name or '').lower()
        score = 0
        size = os.path.getsize(exe_path) if os.path.exists(exe_path) else 0
        score += min(size // 1_000_000, 50)

        similaridade = self._similaridade_textos(folder, nome_arquivo)
        if similaridade > 0.5:
            score += int(similaridade * 120)

        tokens_pasta = set(self._tokens_do_texto(folder))
        tokens_arquivo = set(self._tokens_do_texto(nome_arquivo))
        overlap = len(tokens_pasta & tokens_arquivo)
        if overlap:
            score += overlap * 35

        if 'shipping' in nome_arquivo:
            score += 40
        if 'win64' in nome_arquivo:
            score += 25

        for token in PRIORIDADE_NOMES:
            if token in nome_arquivo:
                score += 20

        if 'launcher' in nome_arquivo or 'updater' in nome_arquivo or 'crash' in nome_arquivo:
            score -= 200

        return score, nome_arquivo, exe_path

    def localizar_executavel_em_pasta(self, pasta_base: str, nome_jogo: str | None = None) -> str:
        if not pasta_base or not os.path.isdir(pasta_base):
            return ''

        candidatos: list[tuple[int, str, str]] = []
        for raiz, dirs, arquivos in os.walk(pasta_base):
            dirs[:] = [d for d in dirs if not self._is_ignored_dir(os.path.join(raiz, d))]
            for nome_arquivo in sorted(arquivos):
                if not nome_arquivo.lower().endswith('.exe'):
                    continue
                if self._is_ignored_name(nome_arquivo):
                    continue
                caminho = os.path.join(raiz, nome_arquivo)
                if not os.path.exists(caminho):
                    continue
                if self._is_ignored_dir(caminho):
                    continue
                score, _, _ = self._candidate_score(caminho, nome_jogo or os.path.basename(pasta_base))
                if score > 0 or not candidatos:
                    candidatos.append((score, nome_arquivo, caminho))

        if not candidatos:
            return ''

        candidatos.sort(key=lambda item: (item[0], os.path.getsize(item[2]), item[1]), reverse=True)
        return candidatos[0][2]

    def resolver_executavel_para_item(self, item, titulo: str | None = None) -> str:
        caminho_salvo = (getattr(item, 'executable_path', '') or '').strip()
        if caminho_salvo and os.path.isfile(caminho_salvo):
            return caminho_salvo
        if getattr(item, 'manual_override', False):
            return ''

        pasta_base = (getattr(item, 'pasta_instalacao', '') or '').strip()
        if not pasta_base or not os.path.isdir(pasta_base):
            return ''

        executavel = self.localizar_executavel_em_pasta(pasta_base, titulo or getattr(item, 'last_played_game', '') or '')
        if not executavel:
            return ''

        item.executable_path = executavel
        item.pasta_instalacao = os.path.dirname(executavel) or pasta_base

        if not is_valid_game_record({
            'game_folder': item.pasta_instalacao,
            'exe_path': item.executable_path,
        }):
            return ''

        try:
            from database import persistir_biblioteca_item
            persistir_biblioteca_item(item)
        except Exception:
            pass

        return executavel

    def iniciar_jogo(self, item) -> dict:
        origem = (getattr(item, 'launcher', '') or getattr(item, 'origem', '') or '').strip().lower()
        titulo = getattr(item, 'last_played_game', '') or getattr(item, 'titulo', '') or ''
        item_id = getattr(item, 'id', getattr(item, 'jogo_id', 0))
        game_folder = (getattr(item, 'pasta_instalacao', '') or '').strip() or os.path.dirname(getattr(item, 'executable_path', '') or '')
        exe_path = (getattr(item, 'executable_path', '') or '').strip()


        self.log('========== PLAY ==========' )
        self.log(f'ID: {item_id}')
        self.log(f'Nome: {titulo}')
        self.log(f'Launcher: {origem or "manual"}')
        self.log(f'AppID: {getattr(item, "codigo_origem", "") or getattr(item, "jogo_id", "")}')
        self.log(f'Game Folder: {game_folder or ""}')
        self.log(f'Exe: {exe_path or ""}')
        self.log(f'Existe: {bool(exe_path and os.path.exists(exe_path))}')
        self.log(f'Origem: {origem or "manual"}')
        self.log('==========================')

        if exe_path:
            if not os.path.isfile(exe_path):
                mensagem = 'O executável salvo não foi encontrado. Deseja selecionar outro?' if getattr(item, 'manual_override', False) else 'Este jogo ainda não possui executável configurado. Clique no ícone da pasta para selecionar o .exe.'
                return {'ok': False, 'success': False, 'modo': origem or 'manual', 'error': mensagem, 'manual_missing': bool(getattr(item, 'manual_override', False))}
        else:
            return {'ok': False, 'success': False, 'modo': origem or 'manual', 'error': 'Este jogo ainda não possui executável configurado. Clique no ícone da pasta para selecionar o .exe.'}

        executavel = exe_path
        self.log(f'[Jogar] Executável: {executavel}')
        self.log(f'[Jogar] Existe: {os.path.exists(executavel)}')

        if not executavel or not os.path.exists(executavel):
            return {'ok': False, 'success': False, 'modo': origem or 'manual', 'error': 'Executável não encontrado ou origem inválida.'}

        cwd = os.path.dirname(executavel) or os.path.dirname(os.path.abspath(executavel))
        try:
            resultado = iniciar_executavel(executavel, cwd=cwd, logger=self.log)
            pid = resultado.get('pid')
            self.log(f'[Jogar] PID: {pid}')
            return {'ok': True, 'success': True, 'modo': origem or 'manual', 'pid': pid, 'elevated': resultado.get('elevated', False)}
        except Exception as exc:
            self.log(f'[Jogar] Exceção ao iniciar executável: {type(exc).__name__}: {exc}')
            return {'ok': False, 'success': False, 'modo': origem or 'manual', 'error': f'{type(exc).__name__}: {exc}'}

    def abrir_pasta_jogo(self, item) -> dict:
        pasta = (getattr(item, 'pasta_instalacao', '') or '').strip()
        if not pasta:
            pasta = os.path.dirname(getattr(item, 'executable_path', '') or '')
        if not pasta or not os.path.isdir(pasta):
            return {'ok': False, 'success': False, 'error': 'Pasta não encontrada.'}
        try:
            os.startfile(pasta)
            return {'ok': True, 'success': True, 'pasta': pasta}
        except Exception as exc:
            return {'ok': False, 'success': False, 'error': f'{type(exc).__name__}: {exc}'}
