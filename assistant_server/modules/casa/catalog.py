"""Cadastro da casa, `config/casa.yaml` (PLAN.md, seção 6): carga e verificações locais.

Feito aqui: verificação 1 (esquema) e 2 (apelido repetido entre equipamentos e grupos do mesmo
tipo). A 3 (colisão por resolução) entra na Fase 2; a checagem contra o hub, na Fase 3.

Ids usados em grupo ou frase que não estão em `devices` (hoje o 35, "Cortinas Geral") não são
checados aqui: vêm do hub. `Catalogo.ids_do_hub` lista todos eles para a Fase 3.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from assistant_server.normalize import normalizar

# Tipo do cadastro -> `kind` no hub (api do home_devices, `GET /api/equipment`).
TIPOS_HUB = {"luz": "light", "cortina": "curtain", "persiana": "blind"}
ALVO_TODAS_LUZES = "hub_todas_luzes"
ACOES = frozenset({"on", "off", "open", "close"})
GENEROS = frozenset({"f", "m"})
ESCOPOS = frozenset({"comodo", "global"})
CHAVES_RAIZ = frozenset({"devices", "groups", "phrases"})


class CadastroInvalido(ValueError):
    pass


class _Carregador(yaml.SafeLoader):
    """YAML 1.1 lê `on`/`off`/`yes`/`no` como booleano, e `acao: off` viraria False. Aqui só
    `true`/`false` são booleanos."""


_Carregador.yaml_implicit_resolvers = {
    inicial: [(tag, regex) for tag, regex in resolvedores if tag != "tag:yaml.org,2002:bool"]
    for inicial, resolvedores in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_Carregador.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF"))


def ler_yaml(texto: str):
    return yaml.load(texto, Loader=_Carregador)


@dataclass(frozen=True)
class Equipamento:
    id: int
    tipo: str
    falado: str
    genero: str
    plural: bool
    apelidos: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class Grupo:
    chave: str
    tipo: str
    escopo: str
    falado: str
    genero: str
    apelidos: tuple[tuple[str, ...], ...]
    alvo: tuple[int, ...] | str  # ids, ou ALVO_TODAS_LUZES


@dataclass(frozen=True)
class Frase:
    frase: tuple[str, ...]
    acao: str
    alvo: int | str  # id ou chave de grupo


@dataclass(frozen=True)
class Catalogo:
    equipamentos: dict[int, Equipamento]
    grupos: dict[str, Grupo]
    frases: tuple[Frase, ...]

    def ids_do_hub(self) -> set[int]:
        ids = set(self.equipamentos)
        for grupo in self.grupos.values():
            if isinstance(grupo.alvo, tuple):
                ids.update(grupo.alvo)
        for frase in self.frases:
            if isinstance(frase.alvo, int):
                ids.add(frase.alvo)
        return ids


def carregar(caminho: Path) -> Catalogo:
    return montar(ler_yaml(caminho.read_text(encoding="utf-8")))


def montar(bruto) -> Catalogo:
    if not isinstance(bruto, dict):
        raise CadastroInvalido("casa.yaml: o conteúdo precisa ser um mapa")
    _chaves("casa.yaml", bruto, CHAVES_RAIZ, {"devices"})

    equipamentos = _equipamentos(bruto["devices"])
    grupos = _grupos(bruto.get("groups") or {}, equipamentos)
    frases = _frases(bruto.get("phrases") or {}, grupos)
    _verificar_apelidos(equipamentos, grupos)
    _verificar_um_global_por_tipo(grupos)
    return Catalogo(equipamentos, grupos, frases)


def _equipamentos(bruto) -> dict[int, Equipamento]:
    if not isinstance(bruto, dict) or not bruto:
        raise CadastroInvalido("devices: precisa ser um mapa com pelo menos um equipamento")
    equipamentos = {}
    for id_, dados in bruto.items():
        origem = f"equipamento {id_}"
        if type(id_) is not int:
            raise CadastroInvalido(f"{origem}: a chave precisa ser o id numérico do hub")
        _chaves(origem, dados, {"tipo", "falado", "genero", "plural", "apelidos"}, {"tipo", "falado", "apelidos"})
        equipamentos[id_] = Equipamento(
            id=id_,
            tipo=_tipo(origem, dados["tipo"]),
            falado=_texto(origem, dados["falado"], "falado"),
            genero=_genero(origem, dados),
            plural=_booleano(origem, dados, "plural"),
            apelidos=_apelidos(origem, dados["apelidos"]),
        )
    return equipamentos


def _grupos(bruto, equipamentos: dict[int, Equipamento]) -> dict[str, Grupo]:
    if not isinstance(bruto, dict):
        raise CadastroInvalido("groups: precisa ser um mapa")
    grupos = {}
    for chave, dados in bruto.items():
        origem = f"grupo {chave}"
        if not isinstance(chave, str):
            raise CadastroInvalido(f"{origem}: a chave precisa ser texto")
        _chaves(origem, dados, {"tipo", "escopo", "falado", "genero", "apelidos", "alvo"},
                {"tipo", "falado", "apelidos", "alvo"})
        tipo = _tipo(origem, dados["tipo"])
        escopo = dados.get("escopo", "comodo")
        if not isinstance(escopo, str) or escopo not in ESCOPOS:
            raise CadastroInvalido(f"{origem}: escopo {escopo!r} inválido (aceitos: comodo, global)")
        alvo = _alvo(origem, tipo, dados["alvo"], equipamentos)
        grupos[chave] = Grupo(
            chave=chave,
            tipo=tipo,
            escopo=escopo,
            falado=_texto(origem, dados["falado"], "falado"),
            genero=_genero(origem, dados),
            apelidos=_apelidos(origem, dados["apelidos"]),
            alvo=alvo,
        )
    return grupos


def _alvo(origem: str, tipo: str, bruto, equipamentos: dict[int, Equipamento]) -> tuple[int, ...] | str:
    if bruto == ALVO_TODAS_LUZES:
        if tipo != "luz":
            raise CadastroInvalido(f"{origem}: {ALVO_TODAS_LUZES} só vale para tipo luz")
        return ALVO_TODAS_LUZES
    ids = (bruto,) if type(bruto) is int else tuple(bruto) if isinstance(bruto, list) else None
    if not ids or not all(type(i) is int for i in ids):
        raise CadastroInvalido(f"{origem}: 'alvo' precisa ser um id, uma lista de ids ou {ALVO_TODAS_LUZES}")
    for id_ in ids:
        if id_ in equipamentos and equipamentos[id_].tipo != tipo:
            raise CadastroInvalido(f"{origem}: o equipamento {id_} é do tipo {equipamentos[id_].tipo}, não {tipo}")
    return ids


def _frases(bruto, grupos: dict[str, Grupo]) -> tuple[Frase, ...]:
    if not isinstance(bruto, dict):
        raise CadastroInvalido("phrases: precisa ser um mapa")
    frases = []
    vistas = set()
    for texto, dados in bruto.items():
        origem = f"frase {texto!r}"
        _chaves(origem, dados, {"acao", "alvo"}, {"acao", "alvo"})
        acao = dados["acao"]
        if not isinstance(acao, str) or acao not in ACOES:
            raise CadastroInvalido(f"{origem}: ação {acao!r} inválida (aceitas: {', '.join(sorted(ACOES))})")
        alvo = dados["alvo"]
        if type(alvo) is not int and not (isinstance(alvo, str) and alvo in grupos):
            raise CadastroInvalido(f"{origem}: alvo {alvo!r} precisa ser um id ou a chave de um grupo")
        frase = normalizar(texto).tokens
        if not frase:
            raise CadastroInvalido(f"{origem}: a frase fica vazia depois da normalização")
        if frase in vistas:
            raise CadastroInvalido(f"{origem}: frase repetida depois da normalização")
        vistas.add(frase)
        frases.append(Frase(frase, acao, alvo))
    return tuple(frases)


def _verificar_apelidos(equipamentos: dict[int, Equipamento], grupos: dict[str, Grupo]) -> None:
    donos: dict[tuple[str, tuple[str, ...]], str] = {}

    def registrar(tipo: str, apelido: tuple[str, ...], dono: str) -> None:
        chave = (tipo, apelido)
        if chave in donos:
            raise CadastroInvalido(
                f"apelido {' '.join(apelido)!r} ({tipo}) aparece em {donos[chave]} e em {dono}")
        donos[chave] = dono

    for equipamento in equipamentos.values():
        for apelido in equipamento.apelidos:
            registrar(equipamento.tipo, apelido, f"equipamento {equipamento.id}")
    for grupo in grupos.values():
        for apelido in grupo.apelidos:
            registrar(grupo.tipo, apelido, f"grupo {grupo.chave}")


def _verificar_um_global_por_tipo(grupos: dict[str, Grupo]) -> None:
    for tipo in TIPOS_HUB:
        globais = [g.chave for g in grupos.values() if g.escopo == "global" and g.tipo == tipo]
        if len(globais) > 1:
            raise CadastroInvalido(f"mais de um grupo global do tipo {tipo}: {', '.join(globais)}")


def _chaves(origem: str, dados, aceitas: set[str], obrigatorias: set[str]) -> None:
    if not isinstance(dados, dict):
        raise CadastroInvalido(f"{origem}: precisa ser um mapa")
    desconhecidas = set(dados) - aceitas
    if desconhecidas:
        raise CadastroInvalido(f"{origem}: campos desconhecidos {sorted(desconhecidas)}")
    faltando = obrigatorias - set(dados)
    if faltando:
        raise CadastroInvalido(f"{origem}: faltam os campos {sorted(faltando)}")


def _tipo(origem: str, valor) -> str:
    if not isinstance(valor, str) or valor not in TIPOS_HUB:
        raise CadastroInvalido(f"{origem}: tipo {valor!r} inválido (aceitos: {', '.join(TIPOS_HUB)})")
    return valor


def _genero(origem: str, dados: dict) -> str:
    genero = dados.get("genero", "f")
    if not isinstance(genero, str) or genero not in GENEROS:
        raise CadastroInvalido(f"{origem}: genero {genero!r} inválido (aceitos: f, m)")
    return genero


def _booleano(origem: str, dados: dict, campo: str) -> bool:
    valor = dados.get(campo, False)
    if type(valor) is not bool:
        raise CadastroInvalido(f"{origem}: '{campo}' precisa ser true ou false")
    return valor


def _texto(origem: str, valor, campo: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise CadastroInvalido(f"{origem}: '{campo}' precisa ser texto não vazio")
    return valor


def _apelidos(origem: str, valor) -> tuple[tuple[str, ...], ...]:
    if not isinstance(valor, list) or not valor:
        raise CadastroInvalido(f"{origem}: 'apelidos' precisa ser uma lista com pelo menos um item")
    apelidos = []
    for texto in valor:
        if not isinstance(texto, str):
            raise CadastroInvalido(f"{origem}: apelido {texto!r} precisa ser texto")
        n = normalizar(texto)
        if not n.tokens or n.tem_quantificador:
            raise CadastroInvalido(f"{origem}: apelido {texto!r} vazio ou com quantificador")
        apelidos.append(n.tokens)
    return tuple(apelidos)
