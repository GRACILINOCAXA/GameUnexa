from abc import ABC, abstractmethod

class EntidadeBase(ABC):
    #Classe abstrata para garantir que toda entidade tenha um ID único.
    def __init__(self, id_entidade: int):
        self._id = id_entidade  # Atributo protegido (Visibilidade)

    @property
    def id(self):
        return self._id

    @abstractmethod
    def obter_resumo(self) -> str:
        #Método abstrato que força as subclasses a implementarem um resumo.
        pass