"""Interface dos resolvedores (PLAN.md, seção 3). Cada resolvedor responde para um texto normalizado."""

from dataclasses import dataclass
from typing import Protocol

from assistant_server.normalize import Normalizado

CASOU = "match"
AMBIGUO = "ambiguous"
NAO_CASOU = "no_match"


@dataclass(frozen=True)
class Resolucao:
    status: str
    acao: str | None = None
    alvo: int | str | None = None  # id de equipamento ou chave de grupo

    @classmethod
    def casou(cls, acao: str, alvo: int | str) -> "Resolucao":
        return cls(CASOU, acao, alvo)

    @classmethod
    def ambiguo(cls) -> "Resolucao":
        return cls(AMBIGUO)

    @classmethod
    def nao_casou(cls) -> "Resolucao":
        return cls(NAO_CASOU)


class Resolvedor(Protocol):
    nome: str

    def resolve(self, texto: Normalizado) -> Resolucao: ...
