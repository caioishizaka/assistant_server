import asyncio

from assistant_server.modules.casa.colisoes import carregar_verificado
from assistant_server.modules.casa.hub_client import HubClient
from assistant_server.modules.casa.module import ModuloCasa
from tests.conftest import RAIZ

CATALOGO = carregar_verificado(RAIZ / "config" / "casa.yaml")


def test_reverificacao_acompanha_o_hub(hub_falso):
    hub = hub_falso([e for e in hub_falso().equipamentos if e["id"] != 35])

    async def rodar():
        cliente = HubClient("http://hub", "hub-token", hub.transport())
        modulo = ModuloCasa(CATALOGO, cliente, dry_run=False)
        try:
            estados = [await modulo.verificar()]
            hub.equipamentos = hub_falso().equipamentos  # o 35 voltou
            estados.append(await modulo.verificar())
            hub.falha_leitura = True  # hub caiu depois do ok
            estados.append(await modulo.verificar())
            return estados, modulo.hub_ok
        finally:
            await cliente.aclose()

    estados, hub_ok = asyncio.run(rodar())
    assert estados == ["invalid", "ok", "ok"]
    assert hub_ok is False
