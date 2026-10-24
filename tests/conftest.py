import json
from pathlib import Path

import httpx
import pytest

from assistant_server.config import Settings

RAIZ = Path(__file__).resolve().parent.parent
FIXTURE = RAIZ / "tests" / "fixtures" / "equipment.json"
TOKEN = "segredo"


def equipamentos_da_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["equipment"]


class HubFalso:
    """Hub de mentira com as rotas do home_devices. Anota cada chamada em `chamadas`."""

    def __init__(self, equipamentos=None, *, set_status=None, move_status=None, lights_off=None,
                 lights_on_status=404, falha_leitura=False, falha_comando=False):
        self.equipamentos = equipamentos if equipamentos is not None else equipamentos_da_fixture()
        self.set_status = set_status or (lambda id_: 202)
        self.move_status = move_status or (lambda id_: 202)
        self.lights_off = lights_off or {"accepted": [1, 2, 3, 4], "unreachable": []}
        self.lights_on_status = lights_on_status
        self.falha_leitura = falha_leitura
        self.falha_comando = falha_comando
        self.chamadas = []

    def comandos(self):
        return [c for c in self.chamadas if c[0] == "POST"]

    async def _responder(self, request: httpx.Request) -> httpx.Response:
        caminho = request.url.path
        self.chamadas.append((request.method, caminho))
        if self.falha_leitura and request.method == "GET" or self.falha_comando and request.method == "POST":
            raise httpx.ConnectError("sem rota para o hub", request=request)
        if request.method == "GET" and caminho == "/api/equipment":
            return httpx.Response(200, json={"equipment": self.equipamentos})
        if request.method == "POST" and caminho == "/api/lights/off":
            return httpx.Response(202, json=self.lights_off)
        if request.method == "POST" and caminho == "/api/lights/on":
            return httpx.Response(self.lights_on_status, json={"accepted": [], "unreachable": []})
        if request.method == "POST" and caminho.endswith("/set"):
            return httpx.Response(self.set_status(int(caminho.split("/")[3])))
        if request.method == "POST" and caminho.endswith("/move"):
            return httpx.Response(self.move_status(int(caminho.split("/")[3])))
        return httpx.Response(404)

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._responder)


@pytest.fixture
def hub_falso():
    return HubFalso


@pytest.fixture
def ajustes(tmp_path):
    return Settings(
        assistant_token=TOKEN,
        casa_hub_url="http://hub",
        casa_hub_token="hub-token",
        dry_run=False,
        data_dir=tmp_path,
    )


@pytest.fixture
def cabecalho():
    return {"Authorization": f"Bearer {TOKEN}"}
