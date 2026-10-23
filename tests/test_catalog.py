import json
from pathlib import Path

import pytest
import yaml

from assistant_server.modules.casa.catalog import (
    ALVO_TODAS_LUZES,
    TIPOS_HUB,
    CadastroInvalido,
    carregar,
    montar,
)

RAIZ = Path(__file__).resolve().parent.parent
CASA = RAIZ / "config" / "casa.yaml"
FIXTURE = RAIZ / "tests" / "fixtures" / "equipment.json"


def cadastro(devices, groups=None, phrases=None):
    bruto = {"devices": devices}
    if groups is not None:
        bruto["groups"] = groups
    if phrases is not None:
        bruto["phrases"] = phrases
    return yaml.safe_dump(bruto, allow_unicode=True)


def carregar_texto(texto):
    return montar(yaml.safe_load(texto))


def test_casa_yaml_carrega():
    catalogo = carregar(CASA)
    assert len(catalogo.equipamentos) == 45
    assert len(catalogo.grupos) == 12
    assert catalogo.frases == ()
    assert catalogo.equipamentos[4].apelidos == (("luz", "sacada"),)


def test_grupo_com_alvo_unico_vira_tupla():
    catalogo = carregar(CASA)
    assert catalogo.grupos["cortinas_jantar"].alvo == (35,)


def test_todas_luzes_usa_o_endpoint_do_hub():
    catalogo = carregar(CASA)
    assert catalogo.grupos["todas_luzes"].alvo == ALVO_TODAS_LUZES
    assert catalogo.grupos["todas_luzes"].escopo == "global"


def test_nao_existe_grupo_de_persianas():
    catalogo = carregar(CASA)
    assert not [g for g in catalogo.grupos.values() if g.tipo == "persiana"]


def test_ids_do_hub_incluem_o_35():
    assert 35 in carregar(CASA).ids_do_hub()


def test_cadastro_bate_com_a_fixture_do_hub():
    """Cada id do YAML existe na fixture com o tipo certo. Não substitui a checagem na Fase 3."""
    casa = carregar(CASA)
    hub = {e["id"]: e for e in json.loads(FIXTURE.read_text(encoding="utf-8"))["equipment"]}
    for equipamento in casa.equipamentos.values():
        h = hub[equipamento.id]
        assert h["kind"] == TIPOS_HUB[equipamento.tipo], equipamento.id
        assert h.get("momentary", False) is False, equipamento.id
    for grupo in casa.grupos.values():
        if isinstance(grupo.alvo, tuple):
            for id_ in grupo.alvo:
                assert id_ in hub, (grupo.chave, id_)
                assert hub[id_]["kind"] == TIPOS_HUB[grupo.tipo], (grupo.chave, id_)


def test_fixture_tem_os_47_equipamentos():
    dados = json.loads(FIXTURE.read_text(encoding="utf-8"))["equipment"]
    assert sorted(e["id"] for e in dados) == list(range(1, 48))


def test_alvo_de_outro_tipo_falha():
    with pytest.raises(CadastroInvalido, match="é do tipo cortina"):
        carregar_texto(cadastro(
            {1: {"tipo": "luz", "falado": "luz", "apelidos": ["luz a"]},
             2: {"tipo": "cortina", "falado": "cortina", "apelidos": ["cortina a"]}},
            {"g": {"tipo": "luz", "falado": "luzes", "apelidos": ["luzes a"], "alvo": [1, 2]}},
        ))


def test_apelido_repetido_no_mesmo_tipo_falha():
    with pytest.raises(CadastroInvalido, match="aparece em equipamento 1 e em equipamento 2"):
        carregar_texto(cadastro({
            1: {"tipo": "luz", "falado": "luz a", "apelidos": ["luz sacada"]},
            2: {"tipo": "luz", "falado": "luz b", "apelidos": ["luz sacada"]},
        }))


def test_apelido_repetido_entre_equipamento_e_grupo_falha():
    with pytest.raises(CadastroInvalido, match="apelido 'luzes sala'"):
        carregar_texto(cadastro(
            {1: {"tipo": "luz", "falado": "luz", "apelidos": ["luzes sala"]}},
            {"g": {"tipo": "luz", "falado": "luzes", "apelidos": ["luzes sala"], "alvo": [1]}},
        ))


def test_mesmo_apelido_em_tipos_diferentes_nao_falha():
    carregar_texto(cadastro(
        {1: {"tipo": "luz", "falado": "luz", "apelidos": ["box a"]},
         2: {"tipo": "cortina", "falado": "cortina", "apelidos": ["box a"]}},
    ))


def test_dois_globais_do_mesmo_tipo_falham():
    with pytest.raises(CadastroInvalido, match="mais de um grupo global do tipo luz"):
        carregar_texto(cadastro(
            {1: {"tipo": "luz", "falado": "luz", "apelidos": ["luz a"]}},
            {
                "g1": {"tipo": "luz", "escopo": "global", "falado": "todas", "apelidos": ["luzes casa"],
                       "alvo": [1]},
                "g2": {"tipo": "luz", "escopo": "global", "falado": "todas", "apelidos": ["luzes geral"],
                       "alvo": [1]},
            },
        ))


def test_todas_luzes_so_para_luz():
    with pytest.raises(CadastroInvalido, match="só vale para tipo luz"):
        carregar_texto(cadastro(
            {1: {"tipo": "cortina", "falado": "cortina", "apelidos": ["cortina a"]}},
            {"g": {"tipo": "cortina", "escopo": "global", "falado": "x", "apelidos": ["cortinas casa"],
                   "alvo": ALVO_TODAS_LUZES}},
        ))


def test_campo_desconhecido_falha():
    with pytest.raises(CadastroInvalido, match="campos desconhecidos"):
        carregar_texto(cadastro({1: {"tipo": "luz", "falado": "luz", "apelido": ["luz a"]}}))


def test_apelido_com_quantificador_falha():
    with pytest.raises(CadastroInvalido, match="quantificador"):
        carregar_texto(cadastro({1: {"tipo": "luz", "falado": "luz", "apelidos": ["todas luzes"]}}))

