"""Caminhos seguros para recursos empacotados e dados persistentes do Game-Unexa."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "GAME-UNEXA"


def resource_path(relative_path: str = "") -> str:
    """Retorna um recurso somente leitura no projeto ou no bundle PyInstaller."""
    if getattr(sys, "frozen", False):
        base_path = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base_path = Path(__file__).resolve().parent
    return str(base_path / relative_path)


def get_app_data_dir() -> str:
    """Retorna a raiz gravavel do usuario, sem depender do diretorio atual."""
    if os.environ.get("VERCEL") == "1":
        return str(Path(os.environ.get("TMPDIR") or "/tmp") / APP_NAME)

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return str(Path(local_app_data) / APP_NAME)

    user_profile = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    if user_profile and user_profile != "~":
        return str(Path(user_profile) / "AppData" / "Local" / APP_NAME)

    temp_dir = os.environ.get("TEMP") or os.environ.get("TMP")
    if temp_dir:
        return str(Path(temp_dir) / APP_NAME)

    raise OSError("Nao foi possivel localizar uma pasta gravavel para os dados do GAME-UNEXA.")


APP_DATA_DIR = Path(get_app_data_dir())
CACHE_DIR = APP_DATA_DIR / "cache"
DATA_DIR = APP_DATA_DIR / "data"
CONFIG_DIR = APP_DATA_DIR / "config"
LOGS_DIR = APP_DATA_DIR / "logs"
SAVES_DIR = APP_DATA_DIR / "saves"
UPLOADS_DIR = APP_DATA_DIR / "uploads"
SOUNDBOARD_DIR = UPLOADS_DIR / "soundboard"
CHAT_UPLOAD_DIR = UPLOADS_DIR / "chat"
SUPPORT_UPLOAD_DIR = UPLOADS_DIR / "suporte"
BACKGROUND_DIR = APP_DATA_DIR / "backgrounds"
TEMP_DIR = APP_DATA_DIR / "tmp"
DB_PATH = DATA_DIR / "gamelink.db"
ENV_PATH = CONFIG_DIR / ".env"


def ensure_app_data_dirs() -> None:
    """Cria a estrutura persistente e informa o caminho exato em caso de falha."""
    directories = (
        APP_DATA_DIR, CACHE_DIR, DATA_DIR, CONFIG_DIR, LOGS_DIR, SAVES_DIR,
        UPLOADS_DIR, SOUNDBOARD_DIR, CHAT_UPLOAD_DIR, SUPPORT_UPLOAD_DIR,
        BACKGROUND_DIR, TEMP_DIR,
    )
    try:
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OSError(
            f"Nao foi possivel criar a pasta de dados do GAME-UNEXA em:\n{directory}\n"
            "Escolha uma conta com acesso a AppData e tente novamente."
        ) from exc


try:
    ensure_app_data_dirs()
except OSError as exc:
    if os.environ.get("VERCEL") != "1":
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(APP_NAME, str(exc))
            root.destroy()
        except Exception:
            pass
    raise SystemExit(1) from exc

