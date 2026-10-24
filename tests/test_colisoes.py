from pathlib import Path

from assistant_server.modules.casa.catalog import carregar
from assistant_server.modules.casa.colisoes import verificar

RAIZ = Path(__file__).resolve().parent.parent


def test_casa_yaml_sem_colisoes():
    assert verificar(carregar(RAIZ / "config" / "casa.yaml")) == []


def test_verificacao_pega_colisao_real():
    """Sem cadastro real: a verificação precisa acusar um apelido que roube outro equipamento."""
    from assistant_server.modules.casa.catalog import montar

    catalogo = montar({"devices": {
        1: {"tipo": "luz", "falado": "luz da sacada", "apelidos": ["luz sacada copa"]},
        2: {"tipo": "luz", "falado": "luz da sacada copa", "apelidos": ["copa"]},
    }})
    problemas = verificar(catalogo)
    assert any("equipamento 2" in p and "sacada copa" in p for p in problemas), problemas
