import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


CATEGORIAS_SUPORTE = [
    ("bug", "🐞 Relatar Bug"),
    ("feature", "💡 Sugerir Funcionalidade"),
    ("performance", "⚡ Reportar Problema de Desempenho"),
    ("security", "🛡️ Reportar Problema de Segurança"),
    ("user_report", "🚫 Denunciar Usuário"),
    ("question", "❓ Dúvidas"),
    ("feedback", "💬 Feedback Geral"),
    ("support", "🎮 Solicitar Suporte"),
    ("other", "📌 Outro"),
]

PRIORIDADES_SUPORTE = ["Baixa", "Média", "Alta", "Crítica"]

STATUS_SUPORTE_INICIAIS = [
    ("aberto", "Aberto"),
    ("em_analise", "Em análise"),
    ("em_desenvolvimento", "Em desenvolvimento"),
    ("aguardando_resposta", "Aguardando resposta"),
    ("resolvido", "Resolvido"),
    ("fechado", "Fechado"),
]

PREFIXOS_SUPORTE = {
    "bug": "BUG",
    "feature": "SUG",
    "performance": "PER",
    "security": "SEG",
    "user_report": "DEN",
    "question": "DUV",
    "feedback": "FDB",
    "support": "SUP",
    "other": "OUT",
}


@dataclass
class ChamadoSuporte:
    id: Optional[int] = None
    codigo: str = ""
    titulo: str = ""
    categoria_slug: str = "other"
    descricao: str = ""
    passos_reproducao: str = ""
    resultado_esperado: str = ""
    resultado_obtido: str = ""
    prioridade: str = "Média"
    versao_gamelink: str = ""
    so: str = ""
    navegador: str = ""
    resolucao_tela: str = ""
    data_criacao: Optional[datetime] = None
    hora_criacao: str = ""
    usuario_email: str = ""
    usuario_nome: str = ""
    usuario_id: Optional[int] = None
    email_contato: str = ""
    status_slug: str = "aberto"
    status_id: Optional[int] = None


@dataclass
class MensagemSuporte:
    id: Optional[int] = None
    chamado_id: Optional[int] = None
    autor_email: str = ""
    autor_nome: str = ""
    conteudo: str = ""
    tipo: str = "usuario"
    data_envio: Optional[datetime] = None


@dataclass
class AnexoSuporte:
    id: Optional[int] = None
    chamado_id: Optional[int] = None
    mensagem_id: Optional[int] = None
    nome_original: str = ""
    nome_arquivo: str = ""
    caminho: str = ""
    tipo_mime: str = ""
    tamanho: int = 0
    data_upload: Optional[datetime] = None


@dataclass
class HistoricoSuporte:
    id: Optional[int] = None
    chamado_id: Optional[int] = None
    usuario_email: str = ""
    acao: str = ""
    detalhes: str = ""
    data_registro: Optional[datetime] = None


def normalizar_slug(texto: str) -> str:
    texto = (texto or "").strip().lower()
    return re.sub(r"[^a-z0-9]+", "-", texto).strip("-")


def gerar_codigo_suporte(categoria_slug: str, conn) -> str:
    slug = (categoria_slug or "other").strip().lower()
    prefixo = PREFIXOS_SUPORTE.get(slug, "SUP")
    cursor = conn.execute(
        "SELECT codigo FROM suporte_chamados WHERE codigo LIKE ? ORDER BY id DESC LIMIT 1",
        (f"{prefixo}-%",),
    )
    row = cursor.fetchone()
    if row and row[0]:
        numero = int(str(row[0]).split("-", 1)[1]) + 1
    else:
        numero = 1
    return f"{prefixo}-{numero:04d}"
