"""Normalização do texto vindo do reconhecedor de voz (PLAN.md, seção 5).

Não singulariza nada: "luzes" continua "luzes". Quantificadores e plurais de tipo são registrados
antes de sair da lista de tokens, porque o resolvedor de grupo depende deles.
"""

import re
import unicodedata
from dataclasses import dataclass

NUMEROS = {
    "um": "1", "uma": "1", "dois": "2", "duas": "2", "tres": "3", "quatro": "4", "cinco": "5",
    "seis": "6", "sete": "7", "oito": "8", "nove": "9", "dez": "10",
}
QUANTIFICADORES = frozenset({"todo", "toda", "todos", "todas", "tudo"})
PLURAIS_DE_TIPO = {"luzes": "luz", "cortinas": "cortina", "persianas": "persiana"}
STOPWORDS = frozenset("a o as os da do das dos de no na nos nas em e".split())
CORTESIAS = frozenset({"pfv", "porfavor"})


@dataclass(frozen=True)
class Normalizado:
    original: str
    tokens: tuple[str, ...]
    tem_quantificador: bool
    tipos_no_plural: frozenset[str]


def remover_acentos(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def normalizar(texto: str) -> Normalizado:
    limpo = remover_acentos(texto.lower())
    limpo = re.sub(r"[^a-z0-9]+", " ", limpo)
    limpo = re.sub(r"\bpor favor\b", " ", limpo)
    palavras = limpo.split()

    tem_quantificador = any(p in QUANTIFICADORES for p in palavras)
    tipos = frozenset(PLURAIS_DE_TIPO[p] for p in palavras if p in PLURAIS_DE_TIPO)

    tokens = tuple(
        NUMEROS.get(p, p)
        for p in palavras
        if p not in STOPWORDS and p not in CORTESIAS and p not in QUANTIFICADORES
    )
    return Normalizado(texto, tokens, tem_quantificador, tipos)
