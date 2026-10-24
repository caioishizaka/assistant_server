"""API HTTP do assistente (PLAN.md, seção 4). O token é verificado antes de ler o corpo."""

import asyncio
import secrets
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from assistant_server.config import Settings
from assistant_server.modules.casa.catalog import Catalogo
from assistant_server.modules.casa.colisoes import carregar_verificado
from assistant_server.modules.casa.hub_client import HubClient
from assistant_server.modules.casa.module import ModuloCasa
from assistant_server.request_log import RegistroRequisicoes

INTERVALO_VERIFICACAO = 60  # segundos


class Hipotese(BaseModel):
    text: str
    confidence: float | None = None


class ComandoEntrada(BaseModel):
    hypotheses: list[Hipotese] = Field(min_length=1, max_length=10)


async def _reverificar(modulo: ModuloCasa) -> None:
    """Sempre, não só até passar: um equipamento apagado no hub depois do startup também invalida
    o cadastro, e o `hub` do /v1/health não fica parado no último comando."""
    while True:
        await asyncio.sleep(INTERVALO_VERIFICACAO)
        await modulo.verificar()


def create_app(settings: Settings, *, catalogo: Catalogo | None = None,
               transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    if catalogo is None:
        catalogo = carregar_verificado(settings.casa_yaml)
    hub = HubClient(settings.casa_hub_url, settings.casa_hub_token, transport)
    modulo = ModuloCasa(catalogo, hub, settings.dry_run)
    registro = RegistroRequisicoes(settings.data_dir)

    @asynccontextmanager
    async def ciclo(_app: FastAPI) -> AsyncIterator[None]:
        await modulo.verificar()
        tarefa = asyncio.create_task(_reverificar(modulo))
        try:
            yield
        finally:
            tarefa.cancel()
            await hub.aclose()

    app = FastAPI(title="assistant_server", lifespan=ciclo)
    app.state.modulo = modulo

    def exigir_token(request: Request) -> None:
        if not settings.assistant_token:
            raise HTTPException(401, "não autorizado")
        esperado = f"Bearer {settings.assistant_token}".encode()
        recebido = request.headers.get("authorization", "").encode()
        if not secrets.compare_digest(recebido, esperado):
            raise HTTPException(401, "não autorizado")

    @app.post("/v1/command", dependencies=[Depends(exigir_token)])
    async def comando(corpo: ComandoEntrada):
        inicio = time.perf_counter()
        resposta = await modulo.comando([h.text for h in corpo.hypotheses])
        registro.escrever({
            "hypotheses": [h.model_dump() for h in corpo.hypotheses],
            "resolver": resposta.resolver,
            "status": resposta.status,
            "matched_text": resposta.matched_text,
            "action": resposta.action,
            "hub_result": resposta.hub,
            "dry_run": resposta.dry_run,
            "latency_ms": round((time.perf_counter() - inicio) * 1000),
        })
        return resposta.para_json()

    @app.get("/v1/health")
    async def saude():
        return {"status": "ok", "hub": "ok" if modulo.hub_ok else "down", "catalog": modulo.catalogo_estado}

    return app
