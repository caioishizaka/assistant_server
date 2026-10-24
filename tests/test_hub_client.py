import asyncio

import httpx
import pytest

from assistant_server.config import Settings
from assistant_server.modules.casa.hub_client import HubClient, HubIndisponivel, HubRecusou
from assistant_server.modules.casa.speech import participio


def cliente(handler):
    return HubClient("http://hub", "hub-token", httpx.MockTransport(handler))


def test_envia_bearer_e_le_equipamentos():
    vistos = []

    def handler(request):
        vistos.append(request.headers["authorization"])
        return httpx.Response(200, json={"equipment": [{"id": 4}]})

    async def rodar():
        c = cliente(handler)
        try:
            return await c.equipamentos()
        finally:
            await c.aclose()

    assert asyncio.run(rodar()) == [{"id": 4}]
    assert vistos == ["Bearer hub-token"]


def test_token_recusado_vira_hub_recusou():
    async def rodar():
        c = cliente(lambda request: httpx.Response(401))
        try:
            await c.equipamentos()
        finally:
            await c.aclose()

    with pytest.raises(HubRecusou) as erro:
        asyncio.run(rodar())
    assert erro.value.status == 401


def test_conexao_recusada_vira_hub_indisponivel():
    def handler(request):
        raise httpx.ConnectError("recusada", request=request)

    async def rodar():
        c = cliente(handler)
        try:
            await c.equipamentos()
        finally:
            await c.aclose()

    with pytest.raises(HubIndisponivel):
        asyncio.run(rodar())


def test_comandos_mandam_o_corpo_certo():
    corpos = []

    def handler(request):
        corpos.append((request.method, request.url.path, request.content))
        return httpx.Response(202)

    async def rodar():
        c = cliente(handler)
        try:
            await c.definir(4, True)
            await c.mover(38, "close")
            await c.apagar_luzes()
        finally:
            await c.aclose()

    asyncio.run(rodar())
    assert corpos == [
        ("POST", "/api/equipment/4/set", b'{"value":true}'),
        ("POST", "/api/equipment/38/move", b'{"action":"close"}'),
        ("POST", "/api/lights/off", b""),
    ]


def test_configuracao_padrao_e_dry_run():
    ajustes = Settings.do_ambiente({"ASSISTANT_TOKEN": "t", "ASSISTANT_DRY_RUN": "1"})
    assert ajustes.dry_run is True
    assert ajustes.casa_hub_url == "http://127.0.0.1:8103"
    assert Settings.do_ambiente({}).dry_run is False


@pytest.mark.parametrize("acao, genero, plural, esperado", [
    ("on", "f", False, "acesa"),
    ("on", "m", True, "acesos"),
    ("off", "f", True, "apagadas"),
    ("open", "m", False, "aberto"),
    ("close", "f", False, "fechada"),
])
def test_participio_concorda_com_o_cadastro(acao, genero, plural, esperado):
    assert participio(acao, genero, plural) == esperado
