from datetime import datetime
from modelos.base import EntidadeBase
from excecao import OperacaoInvalidaError

# Banco de dados simulado para posts
POSTS_DB = {}
COMENTARIOS_POSTS_DB = []  # Lista global de comentários de posts

class Comentario(EntidadeBase):
    """Classe para comentários em posts"""
    def __init__(self, id_entidade: int, post_id: int, autor_email: str, texto: str):
        super().__init__(id_entidade)
        self.post_id = post_id
        self.autor_email = autor_email
        self.texto = texto
        self.data_criacao = datetime.now()
        self.visivel = True

    def obter_resumo(self) -> str:
        return f"Comentário #{self.id} - {self.autor_email}: {self.texto[:50]}..."


class Post(EntidadeBase):
    """Classe para posts de usuários"""
    def __init__(self, id_entidade: int, autor_email: str, titulo: str, conteudo: str, imagem_url: str = None):
        super().__init__(id_entidade)
        self.autor_email = autor_email
        self.titulo = titulo
        self.conteudo = conteudo
        self.imagem_url = imagem_url  
        self.data_criacao = datetime.now()
        self.visivel = True
        self.comentarios_ids = []  
        self.usuarios_curtidas = []  

    def adicionar_comentario(self, comentario_id: int):
        if comentario_id not in self.comentarios_ids:
            self.comentarios_ids.append(comentario_id)

    def curtir(self, email_usuario: str):
        if email_usuario not in self.usuarios_curtidas:
            self.usuarios_curtidas.append(email_usuario)
            return True
        return False

    def descurtir(self, email_usuario: str):
        if email_usuario in self.usuarios_curtidas:
            self.usuarios_curtidas.remove(email_usuario)
            return True
        return False

    def get_total_curtidas(self) -> int:
        return len(self.usuarios_curtidas)

    def usuario_curtiu(self, email_usuario: str) -> bool:
        return email_usuario in self.usuarios_curtidas

    def obter_resumo(self) -> str:
        return f"Post #{self.id} - {self.autor_email}: {self.titulo}"