"""Resolvedor 2 (PLAN.md, seção 5): gramática da casa. Equipamento por apelido, grupo com apelido,
e global por quantificador. Ambiguidade nunca vira escolha."""

from rapidfuzz import fuzz

from assistant_server.modules.base import Resolucao
from assistant_server.modules.casa.catalog import Catalogo
from assistant_server.normalize import PLURAIS_DE_TIPO, Normalizado

VERBOS = {
    "acender": "on", "acende": "on", "acenda": "on", "ligar": "on", "liga": "on", "ligue": "on",
    "apagar": "off", "apaga": "off", "apague": "off", "desligar": "off", "desliga": "off", "desligue": "off",
    "abrir": "open", "abre": "open", "abra": "open",
    "fechar": "close", "fecha": "close", "feche": "close",
}
TIPOS_POR_ACAO = {"on": ("luz",), "off": ("luz",), "open": ("cortina", "persiana"), "close": ("cortina", "persiana")}
# Verbos, substantivos de tipo e números casam exatos, nunca por fuzzy.
EXATOS = frozenset(VERBOS) | frozenset(PLURAIS_DE_TIPO) | {"luz", "cortina", "persiana", "spot", "spots"} | {
    str(n) for n in range(1, 11)}
FUZZY_MIN_LETRAS = 5
FUZZY_LIMIAR = 88


class GramaticaCasa:
    nome = "grammar"

    def __init__(self, catalogo: Catalogo):
        self._equipamentos = [(e.tipo, apelido, e.id) for e in catalogo.equipamentos.values() for apelido in e.apelidos]
        self._grupos = [(g.tipo, apelido, g.chave) for g in catalogo.grupos.values() for apelido in g.apelidos]
        self._globais = [g for g in catalogo.grupos.values() if g.escopo == "global"]
        self._vocabulario = frozenset(t for _, apelido, _ in self._equipamentos + self._grupos for t in apelido)
        self._vocabulario_fuzzy = self._vocabulario - EXATOS

    def resolve(self, texto: Normalizado) -> Resolucao:
        acoes = {VERBOS[t] for t in texto.tokens if t in VERBOS}
        if len(acoes) != 1:
            return Resolucao.nao_casou()
        acao = acoes.pop()
        tipos = TIPOS_POR_ACAO[acao]
        palavras = self._corrigir([t for t in texto.tokens if t not in VERBOS])
        resto = set(palavras)

        equipamentos = self._casar(self._equipamentos, resto, tipos)
        if equipamentos:
            return self._decidir(acao, equipamentos)

        if texto.tem_quantificador or texto.tipos_no_plural:
            grupos = self._casar(self._grupos, resto, tipos)
            if grupos:
                return self._decidir(acao, grupos)

        if texto.tem_quantificador:
            return self._global(acao, tipos, palavras, texto.tipos_no_plural)
        return Resolucao.nao_casou()

    def _corrigir(self, palavras: list[str]) -> list[str]:
        """Erro de transcrição: palavra fora do vocabulário vira a única palavra parecida, se houver uma."""
        corrigidas = []
        for palavra in palavras:
            if palavra in self._vocabulario or palavra in EXATOS or len(palavra) < FUZZY_MIN_LETRAS:
                corrigidas.append(palavra)
                continue
            candidatas = [v for v in self._vocabulario_fuzzy if fuzz.ratio(palavra, v) >= FUZZY_LIMIAR]
            corrigidas.append(candidatas[0] if len(candidatas) == 1 else palavra)
        return corrigidas

    @staticmethod
    def _casar(entradas, resto: set[str], tipos: tuple[str, ...]) -> set:
        """Apelidos cujas palavras estão todas na frase. Vence o(s) de mais palavras."""
        achados = [(len(apelido), alvo) for tipo, apelido, alvo in entradas
                   if tipo in tipos and set(apelido) <= resto]
        if not achados:
            return set()
        maior = max(tamanho for tamanho, _ in achados)
        return {alvo for tamanho, alvo in achados if tamanho == maior}

    @staticmethod
    def _decidir(acao: str, candidatos: set) -> Resolucao:
        if len(candidatos) == 1:
            return Resolucao.casou(acao, candidatos.pop())
        return Resolucao.ambiguo()

    def _global(self, acao: str, tipos: tuple[str, ...], palavras: list[str],
                plurais: frozenset[str]) -> Resolucao:
        """Com quantificador e sem palavra sobrando além de plural de tipo. Se a frase tem plural de
        tipo, só global desse tipo. Exige exatamente um candidato."""
        if any(p not in PLURAIS_DE_TIPO for p in palavras):
            return Resolucao.nao_casou()
        candidatos = {g.chave for g in self._globais
                      if g.tipo in tipos and (not plurais or g.tipo in plurais)}
        if len(candidatos) == 1:
            return Resolucao.casou(acao, candidatos.pop())
        return Resolucao.nao_casou()
