class GameLinkException(Exception):
    #Exceção base para o projeto GameLink.
    pass

class AutenticacaoError(GameLinkException):
    #Usada quando há falha no login ou registro.
    pass

class JogoNaoEncontradoError(GameLinkException):
    #Usada quando um jogo buscado não existe.
    pass

class OperacaoInvalidaError(GameLinkException):
    #Usada quando uma ação infringe uma regra de negócio.
    pass