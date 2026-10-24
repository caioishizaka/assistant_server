"""Frases faladas (PLAN.md, seção 7). A concordância sai de `genero` e `plural` do cadastro."""

PARTICIPIO = {
    "on": {("f", False): "acesa", ("m", False): "aceso", ("f", True): "acesas", ("m", True): "acesos"},
    "off": {("f", False): "apagada", ("m", False): "apagado", ("f", True): "apagadas", ("m", True): "apagados"},
    "open": {("f", False): "aberta", ("m", False): "aberto", ("f", True): "abertas", ("m", True): "abertos"},
    "close": {("f", False): "fechada", ("m", False): "fechado", ("f", True): "fechadas", ("m", True): "fechados"},
}

NAO_IDENTIFICADO = "equipamento não identificado"
NAO_CONSEGUI = "não consegui executar"
HUB_FORA = "hub da casa fora do ar"
CADASTRO_INVALIDO = "cadastro inválido, veja o log"
PREFIXO_TESTE = "teste: "


def participio(acao: str, genero: str, plural: bool) -> str:
    return PARTICIPIO[acao][(genero, plural)]
