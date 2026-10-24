"""Cliente da API do hub do home_devices (PLAN.md, seções 2 e 3). Bearer, timeout de 5 s."""

import httpx


class HubIndisponivel(Exception):
    """Hub não respondeu: fora do ar, porta fechada, timeout."""


class HubRecusou(Exception):
    """Hub respondeu erro numa leitura (401: token do assistente inválido ou revogado)."""

    def __init__(self, status: int):
        super().__init__(f"hub respondeu {status}")
        self.status = status


class HubClient:
    def __init__(self, base_url: str, token: str, transport: httpx.AsyncBaseTransport | None = None):
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _req(self, metodo: str, caminho: str, corpo: dict | None = None) -> httpx.Response:
        try:
            return await self._http.request(metodo, caminho, json=corpo)
        except httpx.HTTPError as exc:
            raise HubIndisponivel(str(exc)) from exc

    async def _get(self, caminho: str) -> dict:
        resposta = await self._req("GET", caminho)
        if resposta.status_code != 200:
            raise HubRecusou(resposta.status_code)
        return resposta.json()

    async def equipamentos(self) -> list[dict]:
        return (await self._get("/api/equipment"))["equipment"]

    async def health(self) -> dict:
        return await self._get("/api/health")

    async def definir(self, equipamento_id: int, ligar: bool) -> httpx.Response:
        return await self._req("POST", f"/api/equipment/{equipamento_id}/set", {"value": ligar})

    async def mover(self, equipamento_id: int, acao: str) -> httpx.Response:
        return await self._req("POST", f"/api/equipment/{equipamento_id}/move", {"action": acao})

    async def apagar_luzes(self) -> httpx.Response:
        return await self._req("POST", "/api/lights/off")

    async def acender_luzes(self) -> httpx.Response:
        """Não existe no hub até a Fase 0B (PLAN.md, seção 10). Até lá responde 404."""
        return await self._req("POST", "/api/lights/on")
