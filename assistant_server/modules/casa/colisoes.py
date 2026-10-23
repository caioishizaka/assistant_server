"""Verificação 3 do cadastro (PLAN.md, seção 6): colisão por resolução.

Usa o próprio pipeline, então o que é verificado é o que roda. Roda na carga do serviço
(`carregar_verificado`) e na suíte de testes.
"""

from pathlib import Path

from assistant_server.modules.casa.catalog import CadastroInvalido, Catalogo, carregar
from assistant_server.modules.casa.grammar import GramaticaCasa
from assistant_server.modules.casa.phrases import FrasesCasa
from assistant_server.pipeline import Pipeline

# Verbo usado em cada checagem. Equipamento: qualquer verbo do tipo serve.
VERBO_EQUIPAMENTO = {"luz": "acende", "cortina": "abre", "persiana": "abre"}
# Grupo: "{verbo} as {apelido}" e "{verbo} todas as {apelido}".
VERBO_GRUPO = {"luz": "apaga", "cortina": "fecha", "persiana": "fecha"}


def verificar(catalogo: Catalogo) -> list[str]:
    pipeline = Pipeline([FrasesCasa(catalogo), GramaticaCasa(catalogo)])
    problemas = []

    for equipamento in catalogo.equipamentos.values():
        verbo = VERBO_EQUIPAMENTO[equipamento.tipo]
        textos = [equipamento.falado] + [" ".join(a) for a in equipamento.apelidos]
        for texto in textos:
            decisao = pipeline.decidir([f"{verbo} {texto}"])
            if decisao.status != "ok" or decisao.alvo != equipamento.id:
                problemas.append(
                    f"equipamento {equipamento.id}: '{verbo} {texto}' não resolve para ele "
                    f"(resolveu {decisao.alvo!r}, status {decisao.status})")

    for grupo in catalogo.grupos.values():
        verbo = VERBO_GRUPO[grupo.tipo]
        for apelido in grupo.apelidos:
            texto = " ".join(apelido)
            for frase in (f"{verbo} as {texto}", f"{verbo} todas as {texto}"):
                decisao = pipeline.decidir([frase])
                if decisao.status != "ok" or decisao.alvo != grupo.chave:
                    problemas.append(
                        f"grupo {grupo.chave}: '{frase}' não resolve para ele "
                        f"(resolveu {decisao.alvo!r}, status {decisao.status})")
    return problemas


def carregar_verificado(caminho: Path) -> Catalogo:
    catalogo = carregar(caminho)
    problemas = verificar(catalogo)
    if problemas:
        raise CadastroInvalido("colisões no cadastro:\n" + "\n".join(problemas))
    return catalogo
