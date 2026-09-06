from modelos.base import EntidadeBase
from excecao import OperacaoInvalidaError

# Banco de dados simulado em memória para Jogos
JOGOS_DB = {}

class Categoria(EntidadeBase):
    # Classe para categorização de jogos/posts
    def __init__(self, id_entidade: int, nome: str):
        super().__init__(id_entidade)
        self.nome = nome

    def obter_resumo(self) -> str:
        return f"Categoria: {self.nome}"


class Jogo(EntidadeBase):
    # Classe concreta para o Cadastro de Jogos
    def __init__(self, id_entidade: int, titulo: str, genero: str, desenvolvedora: str, ano: int):
        super().__init__(id_entidade)
        self.titulo = titulo
        self.genero = genero
        self.desenvolvedora = desenvolvedora
        self.ano = ano
        self._categorias = [] # Lista de objetos Categoria

    def associar_categoria(self, categoria: Categoria):
        if categoria not in self._categorias:
            self._categorias.append(categoria)
        else:
            raise OperacaoInvalidaError("Esta categoria já está associada ao jogo.")

    def listar_categorias(self):
        return [cat.nome for cat in self._categorias]

    def obter_resumo(self) -> str:
        return f"{self.titulo} ({self.ano}) - Gênero: {self.genero}"