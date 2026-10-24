"""Resolvedor 1 (PLAN.md, seção 5): texto normalizado igual a uma frase cadastrada."""

from assistant_server.modules.base import Resolucao
from assistant_server.modules.casa.catalog import Catalogo
from assistant_server.normalize import Normalizado


class FrasesCasa:
    nome = "phrase"

    def __init__(self, catalogo: Catalogo):
        self._frases = {frase.frase: frase for frase in catalogo.frases}

    def resolve(self, texto: Normalizado) -> Resolucao:
        frase = self._frases.get(texto.tokens)
        if frase is None:
            return Resolucao.nao_casou()
        return Resolucao.casou(frase.acao, frase.alvo)
