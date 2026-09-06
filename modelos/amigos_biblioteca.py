from datetime import datetime
from modelos.base import EntidadeBase
from excecao import OperacaoInvalidaError

# Banco de dados simulado para amigos, biblioteca, reviews e mensagens
AMIZADES_DB = {}  
BIBLIOTECA_DB = {}  
REVIEWS_DB = {}  
REVIEW_COMENTARIOS_DB = []
NOTIFICACOES_DB = {}  
MENSAGENS_DB = []  

class SolicitacaoAmizade(EntidadeBase):
    """Classe para gerenciar solicitações de amizade"""
    def __init__(self, id_entidade: int, email_solicitante: str, email_receptor: str):
        super().__init__(id_entidade)
        self.email_solicitante = email_solicitante
        self.email_receptor = email_receptor
        self.status = 'pendente'  
        self.data_solicitacao = datetime.now()

    def aceitar(self):
        self.status = 'aceito'
        self.data_aceito = datetime.now()

    def recusar(self):
        self.status = 'recusado'

    def obter_resumo(self) -> str:
        return f"Solicitação de {self.email_solicitante} para {self.email_receptor}: {self.status}"


class BibliotecaJogo(EntidadeBase):
    """Classe para armazenar informações do jogo na biblioteca do usuário"""
    def __init__(self, id_entidade: int, email_usuario: str, jogo_id: int, origem: str = 'manual', launcher: str | None = None):
        super().__init__(id_entidade)
        self.email_usuario = email_usuario
        self.jogo_id = jogo_id
        self.data_adicao = datetime.now()
        self.tempo_jogado_horas = 0  
        self.concluido = False
        self.platinado = False  
        self.avaliacao = 0.0
        self.comentario_avaliacao = ""
        self.origem = origem
        self.launcher = (launcher or origem or 'manual').strip().lower()
        self.codigo_origem = ""
        self.conquistas_desbloqueadas = 0
        self.conquistas_total = 0
        self.cover_url = ""
        self.favorito = False
        self.executable_path = ""
        self.pasta_instalacao = ""
        self.install_folder = ""
        self.executable_name = ""
        self.updated_at = None
        self.manual_override = False
        self.last_launched_at = None
        self.last_played_game = ""
        self.status = 'offline'

    def atualizar_tempo_jogado(self, horas: int):
        if horas >= 0:
            self.tempo_jogado_horas = horas
        else:
            raise OperacaoInvalidaError("Tempo jogado não pode ser negativo")

    def atualizar_avaliacao(self, nota: float):
        if nota < 0:
            nota = 0.0
        elif nota > 5:
            nota = 5.0
        self.avaliacao = round(float(nota), 1)

    def atualizar_comentario_avaliacao(self, comentario: str):
        self.comentario_avaliacao = (comentario or "").strip()

    def marcar_concluido(self):
        self.concluido = True

    def marcar_platinado(self):
        self.platinado = True
        self.concluido = True

    def alternar_favorito(self):
        self.favorito = not bool(self.favorito)

    def obter_resumo(self) -> str:
        status = "Platinado" if self.platinado else ("Concluído" if self.concluido else "Jogando")
        return f"{self.email_usuario} - Jogo {self.jogo_id}: {status} ({self.tempo_jogado_horas}h) - Avaliação: {self.avaliacao}/5.0"


class Review(EntidadeBase):
    """Classe para avaliações/reviews de jogos"""
    def __init__(self, id_entidade: int, jogo_id: int, email_usuario: str, titulo: str, conteudo: str, nota: int):
        super().__init__(id_entidade)
        self.jogo_id = jogo_id
        self.email_usuario = email_usuario
        self.titulo = titulo
        self.conteudo = conteudo
        self.nota = max(1, min(nota, 5))  # Correção Sênior: Limitado de 1 a 5 conforme o requisito RF06 do projeto
        self.data_criacao = datetime.now()
        self.visivel = True
        self.curtidas = 0  
        self.comentarios_ids = []

    def atualizar_nota(self, nova_nota: int):
        self.nota = max(1, min(nova_nota, 5))

    def atualizar_conteudo(self, novo_titulo: str, novo_conteudo: str):
        self.titulo = novo_titulo
        self.conteudo = novo_conteudo

    def adicionar_curtida(self):
        self.curtidas += 1

    def remover_curtida(self):
        if self.curtidas > 0:
            self.curtidas -= 1

    def adicionar_comentario(self, comentario_id: int):
        if comentario_id not in self.comentarios_ids:
            self.comentarios_ids.append(comentario_id)

    def obter_resumo(self) -> str:
        return f"Review: {self.titulo} ({self.nota}/5) por {self.email_usuario}"


class ComentarioReview(EntidadeBase):
    """Classe para comentários em reviews de jogos"""
    def __init__(self, id_entidade: int, review_id: int, email_usuario: str, texto: str):
        super().__init__(id_entidade)
        self.review_id = review_id
        self.email_usuario = email_usuario
        self.texto = texto
        self.data_criacao = datetime.now()
        self.visivel = True

    def obter_resumo(self) -> str:
        return f"ComentárioReview #{self.id} - {self.email_usuario}: {self.texto[:50]}..."


class Notificacao(EntidadeBase):
    """Classe para notificações de atividades"""
    def __init__(self, id_entidade: int, email_receptor: str, tipo: str, titulo: str, descricao: str, link: str = None):
        super().__init__(id_entidade)
        self.email_receptor = email_receptor
        self.tipo = tipo  
        self.titulo = titulo
        self.descricao = descricao
        self.link = link
        self.data_criacao = datetime.now()
        self.lida = False

    def marcar_como_lida(self):
        self.lida = True

    def obter_resumo(self) -> str:
        status = "Lida" if self.lida else "Não lida"
        return f"Notificação ({self.tipo}): {self.titulo} - {status}"


class Mensagem(EntidadeBase):
    """Classe para mensagens privadas entre amigos"""
    def __init__(self, id_entidade: int, email_remetente: str, email_destino: str, conteudo: str):
        super().__init__(id_entidade)
        self.email_remetente = email_remetente
        self.email_destino = email_destino
        self.conteudo = conteudo
        self.data_envio = datetime.now()
        self.tipo = 'text'
        self.anexo_url = None
        self.anexo_nome = None
        self.anexo_tamanho = None
        self.anexo_tipo = None
        self.reply_to_id = None
        self.reply_to_conteudo = None
        self.reacoes = {}
        self.reacoes_por_usuario = {}
        self.status = 'sent'
        self.editado = False
        self.removida = False
        self.canceled_at = None
        self.canceled_by = None

    def alternar_reacao(self, emoji: str, email_usuario: str):
        if not emoji:
            return None

        email_usuario = (email_usuario or '').strip().lower()
        if not email_usuario:
            return None

        emoji = str(emoji).strip()
        if not emoji:
            return None

        reacao_atual = self.reacoes_por_usuario.get(email_usuario)
        if reacao_atual == emoji:
            self.reacoes_por_usuario.pop(email_usuario, None)
            self.reacoes[emoji] = self.reacoes.get(emoji, 0) - 1
            if self.reacoes[emoji] <= 0:
                del self.reacoes[emoji]
            return None

        if reacao_atual:
            self.reacoes[reacao_atual] = self.reacoes.get(reacao_atual, 0) - 1
            if self.reacoes[reacao_atual] <= 0:
                del self.reacoes[reacao_atual]

        self.reacoes_por_usuario[email_usuario] = emoji
        self.reacoes[emoji] = self.reacoes.get(emoji, 0) + 1
        return emoji

    def registrar_reacao(self, emoji: str, email_usuario: str):
        if not emoji or not email_usuario:
            return
        email_usuario = (email_usuario or '').strip().lower()
        if email_usuario in self.reacoes_por_usuario:
            return
        self.reacoes_por_usuario[email_usuario] = emoji
        self.reacoes[emoji] = self.reacoes.get(emoji, 0) + 1

    def serializar(self, usuario_logado: str = None) -> dict:
        email_logado = (usuario_logado or '').strip().lower()
        return {
            'id': self.id,
            'email_remetente': self.email_remetente,
            'email_destino': self.email_destino,
            'conteudo': self.conteudo,
            'data_envio': self.data_envio.isoformat(timespec='seconds'),
            'tipo': self.tipo,
            'anexo_url': self.anexo_url,
            'anexo_nome': self.anexo_nome,
            'anexo_tamanho': self.anexo_tamanho,
            'anexo_tipo': self.anexo_tipo,
            'reply_to_id': self.reply_to_id,
            'reply_to_conteudo': self.reply_to_conteudo,
            'reacoes': dict(self.reacoes),
            'user_reaction': self.reacoes_por_usuario.get(email_logado),
            'status': self.status,
            'editado': self.editado,
            'removida': self.removida,
            'canceled_at': self.canceled_at.isoformat(timespec='seconds') if self.canceled_at else None,
            'canceled_by': self.canceled_by,
        }

    def cancelar(self, email_usuario: str):
        if (email_usuario or '').strip().lower() != (self.email_remetente or '').strip().lower():
            raise OperacaoInvalidaError('Apenas o autor pode cancelar esta mensagem')
        self.status = 'cancelada'
        self.canceled_at = datetime.now()
        self.canceled_by = (email_usuario or '').strip().lower()
        self.conteudo = ''
        self.anexo_url = None
        self.anexo_nome = None
        self.anexo_tamanho = None
        self.anexo_tipo = None
        self.reply_to_id = None
        self.reply_to_conteudo = None

    def obter_resumo(self) -> str:
        return f"{self.email_remetente} -> {self.email_destino}: {self.conteudo[:50]}"


class GerenciadorMensagens:
    """Classe para gerenciar mensagens privadas"""
    @staticmethod
    def enviar_mensagem(id_mensagem: int, email_remetente: str, email_destino: str, conteudo: str) -> Mensagem:
        mensagem = Mensagem(id_mensagem, email_remetente, email_destino, conteudo)
        MENSAGENS_DB.append(mensagem)
        return mensagem

    @staticmethod
    def obter_conversa(email1: str, email2: str) -> list:
        conversa = [m for m in MENSAGENS_DB if {m.email_remetente, m.email_destino} == {email1, email2}]
        return sorted(conversa, key=lambda x: x.data_envio)

    @staticmethod
    def obter_conversas_recentes(email: str) -> list:
        conversas = {}
        for m in MENSAGENS_DB:
            if m.email_remetente == email or m.email_destino == email:
                amigo = m.email_destino if m.email_remetente == email else m.email_remetente
                if amigo not in conversas or m.data_envio > conversas[amigo].data_envio:
                    conversas[amigo] = m
        return sorted(conversas.values(), key=lambda x: x.data_envio, reverse=True)


class GerenciadorAmigos:
    """Classe para gerenciar sistema de amizade"""
    @staticmethod
    def enviar_solicitacao(id_solicitacao: int, email_solicitante: str, email_receptor: str) -> SolicitacaoAmizade:
        chave = f"{min(email_solicitante, email_receptor)}_{max(email_solicitante, email_receptor)}"
        amizade_existente = AMIZADES_DB.get(chave)
        if amizade_existente:
            if amizade_existente.status == 'aceito':
                raise OperacaoInvalidaError("Vocês já são amigos")
            if amizade_existente.status == 'pendente':
                raise OperacaoInvalidaError("Já existe uma solicitação entre esses usuários")
        solicitacao = SolicitacaoAmizade(id_solicitacao, email_solicitante, email_receptor)
        AMIZADES_DB[chave] = solicitacao
        return solicitacao

    @staticmethod
    def aceitar_solicitacao(email1: str, email2: str):
        chave = f"{min(email1, email2)}_{max(email1, email2)}"
        if chave in AMIZADES_DB:
            AMIZADES_DB[chave].aceitar()
        else:
            raise OperacaoInvalidaError("Solicitação não encontrada")

    @staticmethod
    def recusar_solicitacao(email1: str, email2: str):
        chave = f"{min(email1, email2)}_{max(email1, email2)}"
        if chave in AMIZADES_DB:
            AMIZADES_DB[chave].recusar()
        else:
            raise OperacaoInvalidaError("Solicitação não encontrada")

    @staticmethod
    def obter_amigos(email: str) -> list:
        amigos = []
        for amizade in AMIZADES_DB.values():
            if amizade.status == 'aceito':
                if amizade.email_solicitante == email:
                    amigos.append(amizade.email_receptor)
                elif amizade.email_receptor == email:
                    amigos.append(amizade.email_solicitante)
        return amigos

    @staticmethod
    def obter_solicitacoes_pendentes(email: str) -> list:
        solicitacoes = []
        for amizade in AMIZADES_DB.values():
            if amizade.status == 'pendente' and amizade.email_receptor == email:
                solicitacoes.append(amizade)
        return solicitacoes

    @staticmethod
    def sao_amigos(email1: str, email2: str) -> bool:
        chave = f"{min(email1, email2)}_{max(email1, email2)}"
        amizade = AMIZADES_DB.get(chave)
        return amizade is not None and amizade.status == 'aceito'


class GerenciadorBiblioteca:
    """Classe para gerenciar biblioteca pessoal de jogos"""
    @staticmethod
    def adicionar_jogo(id_biblioteca: int, email: str, jogo_id: int, origem: str = 'manual', launcher: str | None = None) -> BibliotecaJogo:
        chave = f"{email}_{jogo_id}"
        if chave in BIBLIOTECA_DB:
            raise OperacaoInvalidaError("Jogo já existente na biblioteca")
        item = BibliotecaJogo(id_biblioteca, email, jogo_id, origem, launcher)
        BIBLIOTECA_DB[chave] = item
        return item

    @staticmethod
    def atualizar_avaliacao(email: str, jogo_id: int, nota: float, comentario: str = ""):
        chave = f"{email}_{jogo_id}"
        if chave not in BIBLIOTECA_DB:
            raise OperacaoInvalidaError("Jogo não encontrado na biblioteca")
        item = BIBLIOTECA_DB[chave]
        item.atualizar_avaliacao(nota)
        item.atualizar_comentario_avaliacao(comentario)
        return item

    @staticmethod
    def remover_jogo(email: str, jogo_id: int):
        chave = f"{email}_{jogo_id}"
        if chave in BIBLIOTECA_DB:
            del BIBLIOTECA_DB[chave]
        else:
            raise OperacaoInvalidaError("Jogo não encontrado na biblioteca")

    @staticmethod
    def obter_biblioteca(email: str) -> list:
        return [b for b in BIBLIOTECA_DB.values() if b.email_usuario == email]

    @staticmethod
    def jogo_na_biblioteca(email: str, jogo_id: int) -> bool:
        return f"{email}_{jogo_id}" in BIBLIOTECA_DB


class GerenciadorReviews:
    """Classe para gerenciar reviews de jogos"""
    @staticmethod
    def criar_review(id_review: int, jogo_id: int, email: str, titulo: str, conteudo: str, nota: int) -> Review:
        review = Review(id_review, jogo_id, email, titulo, conteudo, nota)
        REVIEWS_DB[id_review] = review
        return review

    @staticmethod
    def adicionar_comentario_review(id_comentario: int, review_id: int, email: str, texto: str) -> ComentarioReview:
        review = REVIEWS_DB.get(review_id)
        if not review or not review.visivel:
            raise OperacaoInvalidaError("Review não encontrada")

        comentario = ComentarioReview(id_comentario, review_id, email, texto)
        REVIEW_COMENTARIOS_DB.append(comentario)
        review.adicionar_comentario(id_comentario)
        return comentario

    @staticmethod
    def obter_reviews_jogo(jogo_id: int) -> list:
        reviews = [r for r in REVIEWS_DB.values() if r.jogo_id == jogo_id and r.visivel]
        return sorted(reviews, key=lambda x: x.curtidas, reverse=True)

    @staticmethod
    def obter_reviews_usuario(email: str) -> list:
        reviews = [r for r in REVIEWS_DB.values() if r.email_usuario == email]
        return sorted(reviews, key=lambda x: x.data_criacao, reverse=True)

    @staticmethod
    def deletar_review(review_id: int):
        if review_id in REVIEWS_DB:
            REVIEWS_DB[review_id].visivel = False
        else:
            raise OperacaoInvalidaError("Review não encontrado")

    @staticmethod
    def obter_comentarios_review(review_id: int) -> list:
        comentarios = [c for c in REVIEW_COMENTARIOS_DB if c.review_id == review_id and c.visivel]
        return sorted(comentarios, key=lambda x: x.data_criacao)

    @staticmethod
    def deletar_comentario_review(comentario_id: int):
        comentario = next((c for c in REVIEW_COMENTARIOS_DB if c.id == comentario_id), None)
        if not comentario:
            raise OperacaoInvalidaError("Comentário de review não encontrado")
        comentario.visivel = False

    @staticmethod
    def obter_media_nota_jogo(jogo_id: int) -> float:
        reviews = GerenciadorReviews.obter_reviews_jogo(jogo_id)
        if not reviews:
            return 0.0
        return sum(r.nota for r in reviews) / len(reviews)


class GerenciadorNotificacoes:
    """Classe para gerenciar notificações"""
    @staticmethod
    def criar_notificacao(id_notif: int, email_receptor: str, tipo: str, titulo: str, descricao: str, link: str = None):
        notif = Notificacao(id_notif, email_receptor, tipo, titulo, descricao, link)
        if email_receptor not in NOTIFICACOES_DB:
            NOTIFICACOES_DB[email_receptor] = []
        NOTIFICACOES_DB[email_receptor].append(notif)
        return notif

    @staticmethod
    def obter_notificacoes(email: str, nao_lidas_apenas: bool = False) -> list:
        notificacoes = NOTIFICACOES_DB.get(email, [])
        if nao_lidas_apenas:
            return [n for n in notificacoes if not n.lida]
        return sorted(notificacoes, key=lambda x: x.data_criacao, reverse=True)

    @staticmethod
    def marcar_como_lida(email: str, notif_id: int):
        notificacoes = NOTIFICACOES_DB.get(email, [])
        for n in notificacoes:
            if n.id == notif_id:
                n.marcar_como_lida()
                break

    @staticmethod
    def contar_nao_lidas(email: str) -> int:
        return len(GerenciadorNotificacoes.obter_notificacoes(email, nao_lidas_apenas=True))

    @staticmethod
    def contar_nao_lidas_por_tipo(email: str, tipo: str) -> int:
        return sum(
            1
            for notificacao in GerenciadorNotificacoes.obter_notificacoes(email, nao_lidas_apenas=True)
            if notificacao.tipo == tipo
        )

    @staticmethod
    def notificar_novo_post(email_receptor: str, titulo: str, descricao: str, post_id: int, id_notif: int):
        GerenciadorNotificacoes.criar_notificacao(
            id_notif, 
            email_receptor, 
            'amigo_post',
            "📝 Novo post",
            descricao,
            f"/posts/{post_id}"
        )