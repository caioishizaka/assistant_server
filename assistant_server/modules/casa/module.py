"""Módulo da casa: resolve as hipóteses e executa no hub (PLAN.md, seções 6 e 7).

Estado do cadastro contra o hub: `pending` até o hub responder uma vez; `ok` ou `invalid` depois.
Com `dry_run`, o hub só é lido, nunca comandado.
"""

import asyncio
import logging
from dataclasses import dataclass, field

from assistant_server.modules.casa.catalog import ALVO_TODAS_LUZES, TIPOS_HUB, Catalogo
from assistant_server.modules.casa.grammar import GramaticaCasa
from assistant_server.modules.casa.hub_client import HubClient, HubIndisponivel, HubRecusou
from assistant_server.modules.casa.phrases import FrasesCasa
from assistant_server.modules.casa.speech import (
    CADASTRO_INVALIDO,
    HUB_FORA,
    NAO_CONSEGUI,
    NAO_IDENTIFICADO,
    PREFIXO_TESTE,
    participio,
)
from assistant_server.pipeline import Decisao, Pipeline

logger = logging.getLogger(__name__)

PENDENTE = "pending"
OK = "ok"
INVALIDO = "invalid"


@dataclass
class Resultado:
    aceitos: list[int] = field(default_factory=list)
    sem_conexao: list[int] = field(default_factory=list)
    recusados: int = 0
    hub_fora: bool = False

    def resumo(self) -> dict:
        if self.hub_fora:
            return {"hub": "fora"}
        return {"aceitos": len(self.aceitos), "sem_conexao": len(self.sem_conexao), "recusados": self.recusados}


@dataclass(frozen=True)
class Resposta:
    status: str
    speech: str
    resolver: str
    matched_text: str | None = None
    action: dict | None = None
    dry_run: bool = False
    hub: dict | None = None  # resumo do que o hub respondeu; vai para o log, não para a resposta

    def para_json(self) -> dict:
        return {
            "status": self.status,
            "speech": self.speech,
            "resolver": self.resolver,
            "matched_text": self.matched_text,
            "action": self.action,
            "dry_run": self.dry_run,
        }


def _situacao(status_code: int) -> str:
    if status_code == 202:
        return "aceito"
    if status_code == 503:
        return "sem_conexao"
    return "recusado"


class ModuloCasa:
    def __init__(self, catalogo: Catalogo, hub: HubClient, dry_run: bool):
        self._catalogo = catalogo
        self._hub = hub
        self._dry_run = dry_run
        self._pipeline = Pipeline([FrasesCasa(catalogo), GramaticaCasa(catalogo)])
        self._estado = PENDENTE
        self._hub_ok = False
        self._ja_respondeu = False

    @property
    def catalogo_estado(self) -> str:
        return self._estado

    @property
    def hub_ok(self) -> bool:
        return self._hub_ok

    async def verificar(self) -> str:
        """Compara o cadastro com o hub. Sem resposta do hub nenhuma vez, continua pendente."""
        try:
            equipamentos = await self._hub.equipamentos()
        except (HubIndisponivel, HubRecusou) as erro:
            logger.warning("hub não verificado: %s", erro)
            self._hub_ok = False
            if not self._ja_respondeu:
                self._estado = PENDENTE
            return self._estado
        self._hub_ok = True
        self._ja_respondeu = True
        problemas = self._comparar(equipamentos)
        for problema in problemas:
            logger.error("cadastro: %s", problema)
        self._estado = INVALIDO if problemas else OK
        return self._estado

    def _tipos_esperados(self) -> dict[int, str | None]:
        """Id do hub que o cadastro usa, com o tipo que ele precisa ter (None: só existir)."""
        esperados: dict[int, str | None] = {i: e.tipo for i, e in self._catalogo.equipamentos.items()}
        for grupo in self._catalogo.grupos.values():
            if isinstance(grupo.alvo, tuple):
                for id_ in grupo.alvo:
                    esperados.setdefault(id_, grupo.tipo)
        for frase in self._catalogo.frases:
            if isinstance(frase.alvo, int):
                esperados.setdefault(frase.alvo, None)
        return esperados

    def _comparar(self, equipamentos: list[dict]) -> list[str]:
        por_id = {e["id"]: e for e in equipamentos}
        esperados = self._tipos_esperados()
        problemas = []
        for id_, tipo in esperados.items():
            hub = por_id.get(id_)
            if hub is None:
                problemas.append(f"id {id_} não existe no hub")
                continue
            if hub.get("momentary"):
                problemas.append(f"id {id_} é momentâneo no hub")
            if tipo is not None and hub["kind"] != TIPOS_HUB[tipo]:
                problemas.append(f"id {id_}: cadastro diz {tipo} ({TIPOS_HUB[tipo]}), hub diz {hub['kind']}")
        for e in equipamentos:
            if e["kind"] in TIPOS_HUB.values() and e["id"] not in esperados:
                logger.warning("hub tem o equipamento %s (%s) fora do cadastro", e["id"], e["kind"])
        return problemas

    async def comando(self, hipoteses: list[str]) -> Resposta:
        if self._estado == PENDENTE:
            return Resposta("error", HUB_FORA, "none")
        if self._estado == INVALIDO:
            return Resposta("error", CADASTRO_INVALIDO, "none")
        decisao = self._pipeline.decidir(hipoteses)
        if decisao.status != "ok":
            return Resposta("not_identified", NAO_IDENTIFICADO, decisao.resolver)
        return await self._executar(decisao)

    async def _executar(self, decisao: Decisao) -> Resposta:
        alvo = decisao.alvo
        if isinstance(alvo, int):
            equipamento = self._catalogo.equipamentos[alvo]
            resultado = await self._por_ids(decisao.acao, [alvo], equipamento.tipo)
            falado, genero, plural = equipamento.falado, equipamento.genero, equipamento.plural
        else:
            grupo = self._catalogo.grupos[alvo]
            if grupo.alvo == ALVO_TODAS_LUZES:
                resultado = await self._luzes_do_hub(decisao.acao)
            else:
                resultado = await self._por_ids(decisao.acao, list(grupo.alvo), grupo.tipo)
            falado, genero, plural = grupo.falado, grupo.genero, True
        return self._resposta(decisao, falado, genero, plural, resultado)

    def _resposta(self, decisao: Decisao, falado: str, genero: str, plural: bool, resultado: Resultado) -> Resposta:
        action = {"verb": decisao.acao, "target": str(decisao.alvo), "ids": resultado.aceitos}
        comum = {
            "resolver": decisao.resolver,
            "matched_text": decisao.texto,
            "action": action,
            "dry_run": self._dry_run,
            "hub": resultado.resumo(),
        }
        if resultado.hub_fora or not resultado.aceitos:
            return Resposta("error", NAO_CONSEGUI, **comum)
        frase = f"{falado} {participio(decisao.acao, genero, plural)}"
        nao_aceitos = len(resultado.sem_conexao) + resultado.recusados
        if nao_aceitos:
            frase += f", {nao_aceitos} sem conexão"
        if self._dry_run:
            frase = PREFIXO_TESTE + frase
        return Resposta("ok", frase, **comum)

    async def _por_ids(self, acao: str, ids: list[int], tipo: str) -> Resultado:
        if self._dry_run:
            return Resultado(aceitos=list(ids))
        try:
            situacoes = await asyncio.gather(*(self._um(acao, id_, tipo) for id_ in ids))
        except HubIndisponivel as erro:
            logger.warning("hub fora durante o comando: %s", erro)
            self._hub_ok = False
            return Resultado(hub_fora=True)
        self._hub_ok = True
        resultado = Resultado()
        for id_, situacao in zip(ids, situacoes):
            if situacao == "aceito":
                resultado.aceitos.append(id_)
            elif situacao == "sem_conexao":
                resultado.sem_conexao.append(id_)
            else:
                resultado.recusados += 1
        return resultado

    async def _um(self, acao: str, id_: int, tipo: str) -> str:
        if tipo == "luz":
            resposta = await self._hub.definir(id_, acao == "on")
        else:
            resposta = await self._hub.mover(id_, acao)
        return _situacao(resposta.status_code)

    async def _luzes_do_hub(self, acao: str) -> Resultado:
        """Todas as luzes: um endpoint do hub, que devolve `accepted` e `unreachable`."""
        if self._dry_run:
            return Resultado(aceitos=[i for i, e in self._catalogo.equipamentos.items() if e.tipo == "luz"])
        try:
            resposta = await (self._hub.apagar_luzes() if acao == "off" else self._hub.acender_luzes())
        except HubIndisponivel as erro:
            logger.warning("hub fora durante o comando: %s", erro)
            self._hub_ok = False
            return Resultado(hub_fora=True)
        self._hub_ok = True
        if resposta.status_code != 202:
            return Resultado(recusados=1)
        corpo = resposta.json()
        return Resultado(aceitos=list(corpo["accepted"]), sem_conexao=list(corpo["unreachable"]))
