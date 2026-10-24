import dataclasses
import json

from fastapi.testclient import TestClient

from assistant_server.api import create_app

CORPO = {"hypotheses": [{"text": "acende a luz da sacada", "confidence": 0.91}]}


def cliente(ajustes, hub, *, dry_run=False):
    ajustes = dataclasses.replace(ajustes, dry_run=dry_run)
    return TestClient(create_app(ajustes, transport=hub.transport()))


def comando(client, cabecalho, texto):
    return client.post("/v1/command", headers=cabecalho, json={"hypotheses": [{"text": texto}]}).json()


# ---- autenticação e corpo ----------------------------------------------------------

def test_sem_token_401(ajustes, hub_falso):
    with cliente(ajustes, hub_falso()) as client:
        assert client.post("/v1/command", json=CORPO).status_code == 401


def test_token_errado_401(ajustes, hub_falso):
    with cliente(ajustes, hub_falso()) as client:
        resposta = client.post("/v1/command", json=CORPO, headers={"Authorization": "Bearer errado"})
        assert resposta.status_code == 401


def test_token_sem_bearer_401(ajustes, hub_falso):
    with cliente(ajustes, hub_falso()) as client:
        resposta = client.post("/v1/command", json=CORPO, headers={"Authorization": "segredo"})
        assert resposta.status_code == 401


def test_sem_token_configurado_recusa_tudo(ajustes, hub_falso, cabecalho):
    ajustes = dataclasses.replace(ajustes, assistant_token="")
    with cliente(ajustes, hub_falso()) as client:
        assert client.post("/v1/command", json=CORPO, headers={"Authorization": "Bearer "}).status_code == 401


def test_sem_hipoteses_422(ajustes, hub_falso, cabecalho):
    with cliente(ajustes, hub_falso()) as client:
        assert client.post("/v1/command", headers=cabecalho, json={"hypotheses": []}).status_code == 422


def test_mais_de_dez_hipoteses_422(ajustes, hub_falso, cabecalho):
    corpo = {"hypotheses": [{"text": "acende a luz da sacada"}] * 11}
    with cliente(ajustes, hub_falso()) as client:
        assert client.post("/v1/command", headers=cabecalho, json=corpo).status_code == 422


def test_health_sem_token(ajustes, hub_falso):
    with cliente(ajustes, hub_falso()) as client:
        assert client.get("/v1/health").json() == {"status": "ok", "hub": "ok", "catalog": "ok"}


# ---- comandos ----------------------------------------------------------------------

def test_luz_acesa(ajustes, hub_falso, cabecalho):
    hub = hub_falso()
    with cliente(ajustes, hub) as client:
        resposta = client.post("/v1/command", headers=cabecalho, json=CORPO)
    assert resposta.status_code == 200
    assert resposta.json() == {
        "status": "ok",
        "speech": "luz da sacada acesa",
        "resolver": "grammar",
        "matched_text": "acende a luz da sacada",
        "action": {"verb": "on", "target": "4", "ids": [4]},
        "dry_run": False,
    }
    assert ("POST", "/api/equipment/4/set") in hub.chamadas


def test_cortina_fechada_usa_move(ajustes, hub_falso, cabecalho):
    hub = hub_falso()
    with cliente(ajustes, hub) as client:
        assert comando(client, cabecalho, "fecha a cortina 3")["speech"] == "cortina 3 fechada"
    assert ("POST", "/api/equipment/38/move") in hub.chamadas


def test_grupo_com_uma_luz_sem_conexao_e_parcial(ajustes, hub_falso, cabecalho):
    hub = hub_falso(set_status=lambda id_: 503 if id_ == 14 else 202)
    with cliente(ajustes, hub) as client:
        dados = comando(client, cabecalho, "apaga as luzes da sala de estar")
    assert dados["status"] == "ok"
    assert dados["speech"] == "luzes da sala de estar apagadas, 1 sem conexão"
    assert dados["action"] == {"verb": "off", "target": "luzes_sala_estar", "ids": [4, 17, 28, 31, 32]}


def test_grupo_sem_nenhum_aceito_e_erro(ajustes, hub_falso, cabecalho):
    hub = hub_falso(set_status=lambda id_: 503)
    with cliente(ajustes, hub) as client:
        dados = comando(client, cabecalho, "apaga todas as luzes da cozinha")
    assert (dados["status"], dados["speech"]) == ("error", "não consegui executar")


def test_hub_fora_no_comando_e_erro(ajustes, hub_falso, cabecalho):
    hub = hub_falso(falha_comando=True)
    with cliente(ajustes, hub) as client:
        dados = comando(client, cabecalho, "acende a luz da sacada")
    assert (dados["status"], dados["speech"]) == ("error", "não consegui executar")


def test_apagar_tudo_usa_o_endpoint_do_hub(ajustes, hub_falso, cabecalho):
    hub = hub_falso(lights_off={"accepted": [1, 2, 4], "unreachable": []})
    with cliente(ajustes, hub) as client:
        dados = comando(client, cabecalho, "apaga tudo")
    assert dados["speech"] == "todas as luzes apagadas"
    assert dados["action"] == {"verb": "off", "target": "todas_luzes", "ids": [1, 2, 4]}
    assert ("POST", "/api/lights/off") in hub.chamadas
    assert not [c for c in hub.comandos() if c[1].endswith("/set")]


def test_todas_luzes_parcial_pelo_unreachable(ajustes, hub_falso, cabecalho):
    hub = hub_falso(lights_off={"accepted": [1, 2], "unreachable": [4]})
    with cliente(ajustes, hub) as client:
        dados = comando(client, cabecalho, "apaga as luzes da casa")
    assert dados["speech"] == "todas as luzes apagadas, 1 sem conexão"
    assert dados["action"]["ids"] == [1, 2]


def test_acender_todas_sem_endpoint_no_hub_e_erro(ajustes, hub_falso, cabecalho):
    hub = hub_falso(lights_on_status=404)
    with cliente(ajustes, hub) as client:
        dados = comando(client, cabecalho, "acende todas as luzes")
    assert (dados["status"], dados["speech"]) == ("error", "não consegui executar")


def test_nao_identificado(ajustes, hub_falso, cabecalho):
    with cliente(ajustes, hub_falso()) as client:
        dados = comando(client, cabecalho, "bom dia")
    assert dados == {
        "status": "not_identified",
        "speech": "equipamento não identificado",
        "resolver": "none",
        "matched_text": None,
        "action": None,
        "dry_run": False,
    }


def test_dry_run_so_le_o_hub(ajustes, hub_falso, cabecalho):
    hub = hub_falso()
    with cliente(ajustes, hub, dry_run=True) as client:
        dados = comando(client, cabecalho, "acende a luz da sacada")
    assert dados["speech"] == "teste: luz da sacada acesa"
    assert dados["dry_run"] is True
    assert dados["action"]["ids"] == [4]
    assert hub.comandos() == []


def test_dry_run_todas_luzes_nao_chama_o_hub(ajustes, hub_falso, cabecalho):
    hub = hub_falso()
    with cliente(ajustes, hub, dry_run=True) as client:
        dados = comando(client, cabecalho, "apaga tudo")
    assert dados["speech"].startswith("teste: todas as luzes apagadas")
    assert hub.comandos() == []


# ---- estado do cadastro -------------------------------------------------------------

def test_hub_fora_na_carga_deixa_pendente(ajustes, hub_falso, cabecalho):
    hub = hub_falso(falha_leitura=True)
    with cliente(ajustes, hub) as client:
        assert client.get("/v1/health").json() == {"status": "ok", "hub": "down", "catalog": "pending"}
        dados = comando(client, cabecalho, "acende a luz da sacada")
    assert (dados["status"], dados["speech"], dados["action"]) == ("error", "hub da casa fora do ar", None)


def test_tipo_errado_no_hub_deixa_invalido(ajustes, hub_falso, cabecalho):
    equipamentos = hub_falso().equipamentos
    for e in equipamentos:
        if e["id"] == 33:
            e["kind"] = "curtain"
    with cliente(ajustes, hub_falso(equipamentos)) as client:
        assert client.get("/v1/health").json()["catalog"] == "invalid"
        dados = comando(client, cabecalho, "acende a luz do quarto")
    assert (dados["status"], dados["speech"]) == ("error", "cadastro inválido, veja o log")


def test_id_do_cadastro_ausente_no_hub_deixa_invalido(ajustes, hub_falso):
    equipamentos = [e for e in hub_falso().equipamentos if e["id"] != 35]
    with cliente(ajustes, hub_falso(equipamentos)) as client:
        assert client.get("/v1/health").json()["catalog"] == "invalid"


def test_momentaneo_no_hub_deixa_invalido(ajustes, hub_falso):
    equipamentos = hub_falso().equipamentos
    for e in equipamentos:
        if e["id"] == 4:
            e["momentary"] = True
    with cliente(ajustes, hub_falso(equipamentos)) as client:
        assert client.get("/v1/health").json()["catalog"] == "invalid"


# ---- log ------------------------------------------------------------------------------

def test_log_uma_linha_por_comando_sem_token(ajustes, hub_falso, cabecalho):
    with cliente(ajustes, hub_falso()) as client:
        comando(client, cabecalho, "acende a luz da sacada")
        comando(client, cabecalho, "bom dia")
    linhas = (ajustes.data_dir / "requests.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(linhas) == 2
    primeira = json.loads(linhas[0])
    assert primeira["status"] == "ok"
    assert primeira["hypotheses"] == [{"text": "acende a luz da sacada", "confidence": None}]
    assert primeira["hub_result"] == {"aceitos": 1, "sem_conexao": 0, "recusados": 0}
    assert set(primeira) >= {"ts", "resolver", "matched_text", "action", "dry_run", "latency_ms"}
    texto = (ajustes.data_dir / "requests.jsonl").read_text(encoding="utf-8")
    assert "segredo" not in texto and "hub-token" not in texto


def test_requisicao_sem_token_nao_entra_no_log(ajustes, hub_falso):
    with cliente(ajustes, hub_falso()) as client:
        client.post("/v1/command", json=CORPO)
    assert not (ajustes.data_dir / "requests.jsonl").exists()
