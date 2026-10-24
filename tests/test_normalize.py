import pytest

from assistant_server.normalize import normalizar


@pytest.mark.parametrize("texto, tokens", [
    ("Acende a luz da sacada", ("acende", "luz", "sacada")),
    ("acende a luz da área de serviço", ("acende", "luz", "area", "servico")),
    ("Fecha a cortina três", ("fecha", "cortina", "3")),
    ("fecha a cortina 3", ("fecha", "cortina", "3")),
    ("abre a cortina oito", ("abre", "cortina", "8")),
    ("acende a luz do banheiro da suíte!", ("acende", "luz", "banheiro", "suite")),
    ("acende a luz da sacada, por favor", ("acende", "luz", "sacada")),
    ("pfv acende a luz da sacada", ("acende", "luz", "sacada")),
])
def test_tokens(texto, tokens):
    assert normalizar(texto).tokens == tokens


def test_nao_singulariza():
    n = normalizar("acende as luzes e as cortinas")
    assert "luzes" in n.tokens and "cortinas" in n.tokens


def test_quantificador_e_removido_mas_marcado():
    n = normalizar("apaga todas as luzes da cozinha")
    assert n.tem_quantificador is True
    assert "todas" not in n.tokens
    assert n.tokens == ("apaga", "luzes", "cozinha")


def test_tudo_e_quantificador_sem_tokens():
    n = normalizar("apaga tudo")
    assert n.tem_quantificador is True
    assert n.tokens == ("apaga",)


def test_plural_de_tipo_registrado():
    assert normalizar("fecha as cortinas do jantar").tipos_no_plural == {"cortina"}
    assert normalizar("fecha a persiana do quarto").tipos_no_plural == frozenset()


def test_sem_marcadores_por_padrao():
    n = normalizar("acende a luz da sacada")
    assert n.tem_quantificador is False
    assert n.tipos_no_plural == frozenset()


def test_original_preservado():
    assert normalizar("Acende a luz").original == "Acende a luz"
