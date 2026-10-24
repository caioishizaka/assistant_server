"""Cadeia de resolução sobre as hipóteses do reconhecedor (PLAN.md, seções 4 e 5)."""

from dataclasses import dataclass

from assistant_server.modules.base import CASOU, NAO_CASOU, Resolvedor
from assistant_server.normalize import normalizar


@dataclass(frozen=True)
class Decisao:
    status: str  # "ok" | "not_identified"
    resolver: str  # "phrase" | "grammar" | "none"
    texto: str | None  # hipótese que casou
    acao: str | None = None
    alvo: int | str | None = None


class Pipeline:
    def __init__(self, resolvedores: list[Resolvedor]):
        self._resolvedores = list(resolvedores)

    def decidir(self, hipoteses: list[str]) -> Decisao:
        """Hipóteses em ordem, resolvedores em ordem. A primeira que casar sem ambiguidade vence.
        Ambiguidade encerra a hipótese (os resolvedores seguintes não a desempatam) e passa para a
        próxima, que pode ser a transcrição certa (decisão do Caio)."""
        for texto in hipoteses:
            normalizado = normalizar(texto)
            for resolvedor in self._resolvedores:
                resolucao = resolvedor.resolve(normalizado)
                if resolucao.status == CASOU:
                    return Decisao("ok", resolvedor.nome, texto, resolucao.acao, resolucao.alvo)
                if resolucao.status != NAO_CASOU:
                    break
        return Decisao("not_identified", "none", None)
