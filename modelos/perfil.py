def __str__(self) -> str:
        if not self.jogos:
            return "Nenhum jogo cadastrado na biblioteca."

        linhas = [
            "Jogos preferidos e avaliações:"
        ]
        for jogo, avaliacao in self.jogos.items():
            linhas.append(f"- {jogo}: {avaliacao}/10")
        return "\n".join(linhas)


class PerfilJogador:
    def __init__(self, nome: str, telefone: str, plataforma: str, biblioteca: BibliotecaJogos = None):
        self.nome = nome
        self.telefone = telefone
        self.plataforma = plataforma
        self.biblioteca = biblioteca if biblioteca is not None else BibliotecaJogos()
        self.amigos = []  # lista de nomes de amigos

    def adicionar_amigo(self, nome_amigo: str) -> None:
        if nome_amigo not in self.amigos:
            self.amigos.append(nome_amigo)

    def remover_amigo(self, nome_amigo: str) -> None:
        if nome_amigo in self.amigos:
            self.amigos.remove(nome_amigo)

    def listar_amigos(self) -> str:
        if not self.amigos:
            return "Nenhum amigo cadastrado."
        return "Amigos:\n" + "\n".join(f"- {a}" for a in self.amigos)

    def __str__(self) -> str:
        return (
            f"Nome: {self.nome}\n"
            f"Telefone: {self.telefone}\n"
            f"Plataforma de jogos utilizada: {self.plataforma}\n\n"
            f"{self.biblioteca}\n\n"
            f"{self.listar_amigos()}"
        )


if __name__ == "__main__":
    biblioteca = BibliotecaJogos()
    biblioteca.adicionar_jogo("The Witcher 3", 9.5)
    biblioteca.adicionar_jogo("FIFA 24", 8.0)
    biblioteca.adicionar_jogo("Horizon Forbidden West", 9.0)

    perfil = PerfilJogador(
        nome="João Silva",
        telefone="(11) 99999-9999",
        plataforma="PC",
        biblioteca=biblioteca
    )
    print(perfil)
