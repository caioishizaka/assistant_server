from assistant_server.modules.base import Resolucao
from assistant_server.normalize import normalizar
from assistant_server.pipeline import Pipeline


class Falso:
    """Resolvedor de mentira. `respostas` mapeia o texto original à resolução; o resto não casa.
    Anota as chamadas para o teste ver quais hipóteses foram tentadas."""

    def __init__(self, nome, respostas=None):
        self.nome = nome
        self.respostas = respostas or {}
        self.chamadas = []

    def resolve(self, texto):
        self.chamadas.append(texto.original)
        return self.respostas.get(texto.original, Resolucao.nao_casou())


SACADA = "acende a luz da sacada"
ESCADA = "acende a luz da escada"
CASOU = Resolucao.casou("on", 4)
AMBIGUO = Resolucao.ambiguo()


def test_primeira_hipotese_que_casa_vence():
    segunda = Falso("grammar", {SACADA: CASOU, ESCADA: CASOU})
    decisao = Pipeline([Falso("phrase"), segunda]).decidir([SACADA, ESCADA])
    assert (decisao.status, decisao.resolver, decisao.texto, decisao.alvo) == ("ok", "grammar", SACADA, 4)
    assert segunda.chamadas == [SACADA]


def test_segunda_hipotese_resolve_quando_a_primeira_nao_casa():
    decisao = Pipeline([Falso("grammar", {SACADA: CASOU})]).decidir(["bom dia", SACADA])
    assert (decisao.status, decisao.texto) == ("ok", SACADA)


def test_primeira_ambigua_e_a_segunda_resolve():
    gramatica = Falso("grammar", {"acende a luz da sacada e da copa": AMBIGUO, SACADA: CASOU})
    decisao = Pipeline([gramatica]).decidir(["acende a luz da sacada e da copa", SACADA])
    assert (decisao.status, decisao.texto) == ("ok", SACADA)


def test_todas_ambiguas():
    decisao = Pipeline([Falso("grammar", {SACADA: AMBIGUO, ESCADA: AMBIGUO})]).decidir([SACADA, ESCADA])
    assert (decisao.status, decisao.resolver) == ("not_identified", "none")


def test_ambiguidade_nao_e_desempatada_pelo_resolvedor_seguinte():
    seguinte = Falso("grammar", {SACADA: CASOU})
    decisao = Pipeline([Falso("phrase", {SACADA: AMBIGUO}), seguinte]).decidir([SACADA])
    assert decisao.status == "not_identified"
    assert seguinte.chamadas == []


def test_nenhuma_hipotese_casa():
    decisao = Pipeline([Falso("grammar")]).decidir(["bom dia", "oi"])
    assert (decisao.status, decisao.resolver) == ("not_identified", "none")


def test_frase_cadastrada_vem_antes_da_gramatica():
    gramatica = Falso("grammar", {SACADA: CASOU})
    frase = Falso("phrase", {SACADA: Resolucao.casou("off", 33)})
    decisao = Pipeline([frase, gramatica]).decidir([SACADA])
    assert (decisao.resolver, decisao.alvo) == ("phrase", 33)
    assert gramatica.chamadas == []


def test_hipotese_passa_normalizada_aos_resolvedores():
    gramatica = Falso("grammar", {"Acende a luz da sacada, por favor!": CASOU})
    decisao = Pipeline([gramatica]).decidir(["Acende a luz da sacada, por favor!"])
    assert decisao.status == "ok"
    assert normalizar("Acende a luz da sacada, por favor!").tokens == ("acende", "luz", "sacada")
