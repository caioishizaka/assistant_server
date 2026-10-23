from pathlib import Path

import pytest
import yaml

from assistant_server.modules.casa.catalog import carregar
from assistant_server.modules.casa.grammar import GramaticaCasa
from assistant_server.modules.casa.phrases import FrasesCasa
from assistant_server.pipeline import Pipeline

RAIZ = Path(__file__).resolve().parent.parent
CATALOGO = carregar(RAIZ / "config" / "casa.yaml")
PIPELINE = Pipeline([FrasesCasa(CATALOGO), GramaticaCasa(CATALOGO)])
CASOS = yaml.safe_load((RAIZ / "tests" / "frases.yaml").read_text(encoding="utf-8"))


def ids_do_alvo(alvo):
    if isinstance(alvo, int):
        return (alvo,)
    return CATALOGO.grupos[alvo].alvo


@pytest.mark.parametrize("caso", CASOS, ids=lambda c: c["frase"])
def test_tabela(caso):
    decisao = PIPELINE.decidir([caso["frase"]])
    if caso["status"] == "not_identified":
        assert decisao.status == "not_identified", decisao
        return
    assert decisao.status == "ok", decisao
    assert decisao.acao == caso["acao"]
    assert decisao.alvo == caso["alvo"]
    if "ids" in caso:
        assert list(ids_do_alvo(decisao.alvo)) == caso["ids"]
