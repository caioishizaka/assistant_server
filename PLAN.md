# Plano: `assistant_server`, assistente de voz da casa

Escrito em 2026-10-23. Objetivo: comandar luzes, cortinas e persianas do `home_devices` pela voz,
a partir do celular (Motorola Razr 60, Android). O app só captura a fala, manda o texto e fala a
resposta. O servidor, um projeto Python novo no `andes`, interpreta o texto de forma determinística
e chama a API do hub do `home_devices`.

Este plano foi escrito para ser executado em partes por modelos diferentes. Cada fase diz **quem**
faz: **Haiku** (🤖H), **Opus** (🧠O) ou **Caio** (👤C). O Haiku só executa as fases marcadas para
ele e para nos pontos de parada da seção 9. Em cada fase, a linha **"Volta para"** diz quem
continua.

## 1. Decisões (tomadas pelo Caio)

| Tema | Decisão |
|---|---|
| Papel do app | Cliente fino: botão ou gesto de assistente → `SpeechRecognizer` → envia as hipóteses → fala a resposta (TTS local). Nenhuma frase, comando ou equipamento fixo no app. |
| Papel do servidor | Repo próprio, `assistant_server` (não é parte do `home_devices`). Faz todo o parsing e chama a API do hub com um token próprio. |
| MCP | Fora. O servidor fala direto com a API do hub. |
| Resolução | Só rota determinística na v1. O Jev (TypeSafe AI) fica no roadmap como mais um resolvedor. |
| Cadastro | YAML no repo. Mudança = PR + redeploy (aceitável). |
| Fonte da verdade dos equipamentos | API do hub. O YAML guarda só apelidos, grupos, frases e o texto falado. |
| Ambiguidade | Sempre falha com "equipamento não identificado". Nunca escolhe um padrão. |
| Apelidos | Coerentes por construção: se uma palavra-âncora existe em mais de um equipamento (pia, mesa, box, espelho, spot), **todo** apelido com ela leva o qualificador. Palavras extras na frase continuam ignoradas. |
| Grupos | Só grupos explícitos no YAML. Marcados por plural ou por quantificador (`todo/toda/todos/todas/tudo`). |
| Todas as luzes | Grupo `todas_luzes`, executado por **endpoint do hub** (não por lista de ids). Apagar já existe (`POST /api/lights/off`); acender não existe e será criado no `home_devices` (Fase 0B). |
| Persianas | Não existe grupo de persianas (nem por cômodo, nem global). |
| Hipóteses | Tentadas em ordem; a primeira que resolver sem ambiguidade vence. |
| Autenticação app → servidor | Token fixo (Bearer). O app não será distribuído. |
| Rede | URL da LAN primeiro; Meshnet da Nord como reserva. |
| Resposta | Frase curta gerada pelo servidor, falada pelo TTS nativo do Android. |
| Acionamento | Só botão ou gesto de assistente. Sem wake word. |
| Handoff para o Claude | Fora do escopo. |
| Escopo de equipamentos | Luzes, cortinas e persianas. Triturador (id 27) fora. |
| App Android | Java puro com `build.py` próprio, **no molde do `~/dev/home_devices/android/`** (sem Gradle, sem Kotlin, sem bibliotecas). É o padrão que já funciona na casa (ver seção 8). |

## 2. Levantamento (feito pelo Opus em 2026-10-23, só leitura)

**Hub do `home_devices`** (código em `~/dev/home_devices/hub/api.py`; ler à vontade, **nunca editar**
fora da Fase 0B):

- FastAPI + uvicorn, `127.0.0.1:8103` em produção. O `assistant_server` fala direto com
  `http://127.0.0.1:8103`, sem passar pelo nginx (igual ao `caio_mcp`).
- Autenticação: `Authorization: Bearer <token>`. Token criado por `POST /api/auth/login` com
  `{"username", "password", "label"}`. O `label` aparece no log do hub em cada comando. O nosso:
  **`Assistente de voz`**. Não precisa de usuário de serviço novo: o rótulo já identifica o cliente,
  como no `caio_mcp`.
- `GET /api/equipment` → `{"equipment": [{"id", "name", "kind", "room_id", "momentary", ...}]}`.
  `kind`: `light`, `curtain`, `blind` (e outros fora do escopo, como `disposal`).
- `POST /api/equipment/{id}/set` com `{"value": bool}`: 202 aceito; 503 controlador fora; 409 é cortina.
- `POST /api/equipment/{id}/move` com `{"action": "open" | "close" | "stop"}`: 202 enviado (sem
  confirmação de movimento); 503 hub IR/RF fora; 409 aprendendo. O id 35 (`Cortinas Geral`) é
  `curtain` comum: abre e fecha pelo mesmo endpoint.
- `POST /api/lights/off` → `{"accepted": [ids], "unreachable": [ids], "skipped": [...]}`. Apaga todo
  equipamento `kind == "light"` (hoje as 33 luzes do YAML; nenhuma é `momentary`).
- `POST /api/lights/on`: **não existe.** Criado na Fase 0B.
- `POST /api/rooms/{id}/lights/off` existe, mas **não serve** para os grupos de cômodo: os cômodos
  do hub incluem os banheiros (Corredor tem o banheiro social, Escritório e Suíte têm os seus), e no
  YAML os banheiros são grupos separados. Grupos de cômodo continuam como lista de ids.
- `GET /api/health` (com token) → estado dos controladores.
- Dev: `~/dev/home_devices`, `.venv/bin/python -m tools.devhub` (porta 8199, login `dev`/`dev`). É
  uma **casa de exemplo com outros ids**: não serve para validar o YAML. Os testes do
  `assistant_server` usam um hub falso próprio (seção 9).

**Cadastro real** (lido de `~/apps/home_devices/data/config.db` em modo somente leitura): os ids,
tipos e cômodos do YAML da seção 6 conferem com o hub. Cômodos do hub: 1 Corredor, 2 Sala de Jogos,
3 Sala de Jantar, 4 Sala de estar, 5 Área de Serviço, 6 Cozinha, 7 Escritório, 8 Suíte master.

**Servidor `andes`** (`~/andes/GUIA-APPS.md`):

- Apps ouvem só em `127.0.0.1`; o nginx expõe por subcaminho. Portas em uso: 8101 (wol), 8102
  (finance_tracker), 8103 (home_devices), 8104 (caio_mcp).
- **Portas deste projeto:** produção **8105**; staging **8197** (só `127.0.0.1`, sem unit).
- Rota nginx: **`/assistant_server/`**. URLs que o app usa:
  - LAN: `http://192.168.68.86/assistant_server/`
  - Meshnet: `http://caio.ishizaka-andes.nord/assistant_server/` (mesmo nome que o app "Casa" do
    `home_devices` já usa)
- Debian 13 (trixie): Python 3.13, sem pip global (só venv), sem Java instalado. O trixie empacota o
  **OpenJDK 21** (o 17 do plano antigo não existe nele).

## 3. Arquitetura

```
[Razr 60]                                    [andes]
botão / gesto de assistente                  nginx :80  /assistant_server/  →  127.0.0.1:8105
  → SpeechRecognizer (pt-BR)                 assistant_server (FastAPI)
  → POST /v1/command  ────────────────────►    normalização
    (Bearer, hipóteses)                        resolvedores em cadeia:
                                                 1. frase cadastrada
                                                 2. gramática (módulo casa)
                                                 3. [roadmap] Jev
                                                 4. não identificado
                                               → API do hub 127.0.0.1:8103 (Bearer "Assistente de voz")
  ← { status, speech }  ◄─────────────────     data/requests.jsonl
  → TextToSpeech fala "speech"
```

### Estrutura do repo

```
assistant_server/
  assistant_server/
    __init__.py
    __main__.py            # python -m assistant_server [--port N]; lê env, sobe uvicorn
    config.py              # variáveis de ambiente e caminhos (data_dir)
    api.py                 # FastAPI: /v1/command, /v1/health; auth Bearer
    normalize.py           # normalização de texto
    pipeline.py            # hipóteses × resolvedores
    request_log.py         # data/requests.jsonl
    modules/
      base.py              # Resolution, Action, Result, interface de módulo
      casa/
        catalog.py         # carga e validação do YAML (+ verificação contra o hub)
        grammar.py         # resolvedor de gramática
        phrases.py         # resolvedor de frase cadastrada
        speech.py          # frases faladas (concordância)
        hub_client.py      # cliente da API do hub
        module.py          # resolve() e execute()
  config/
    casa.yaml              # cadastro (seção 6)
  tests/
    fixtures/equipment.json   # snapshot de GET /api/equipment (seção 9, Fase 1)
    frases.yaml            # tabela frase → resultado esperado
    test_*.py
  android/                 # app (seção 8)
  deploy/
    assistant-server.service
    assistant_server.conf  # location do nginx
  data/                    # ignorado pelo git: requests.jsonl
  requirements.txt
  requirements-dev.txt
  CLAUDE.md                # @~/andes/GUIA-APPS.md + "ler PLAN.md antes de mudar algo"
  README.md                # o que é, rodar em dev, testar, implantar; curto
  PLAN.md                  # este arquivo
```

Interface de módulo (nasce modular, mesmo com um só módulo):

- `resolve(norm: NormalizedText) -> Resolution`: `match` (ação + alvo), `ambiguous` ou `no_match`.
- `execute(action) -> Result`: chama o hub e devolve `ok`/`error` + frase.
- Um verbo que nenhum módulo reconhece = `no_match` geral.

### Variáveis de ambiente

| Variável | Uso |
|---|---|
| `ASSISTANT_TOKEN` | Token que o app manda no Bearer. Gerar com `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`. |
| `CASA_HUB_URL` | `http://127.0.0.1:8103` em produção. |
| `CASA_HUB_TOKEN` | Token do hub com o rótulo `Assistente de voz`. |
| `ASSISTANT_DRY_RUN` | `1` = resolve e loga, mas não manda comando ao hub (só leituras). Usado no staging. |
| `ASSISTANT_DATA_DIR` | Pasta do log. Padrão: `<repo>/data`. |

## 4. Contrato HTTP

`POST /v1/command`, header `Authorization: Bearer <ASSISTANT_TOKEN>` (comparar com
`secrets.compare_digest`; sem token ou errado → 401).

```json
{
  "hypotheses": [
    {"text": "acende a luz da sacada", "confidence": 0.91},
    {"text": "acende a luz da escada"}
  ]
}
```

`confidence` é opcional (o `SpeechRecognizer` muitas vezes não manda). A ordem da lista é a ordem
de tentativa; o servidor **não reordena**. Lista vazia ou mais de 10 hipóteses → 422.

Resposta (sempre 200 quando autenticado e o corpo é válido):

```json
{
  "status": "ok",
  "speech": "luz da sacada acesa",
  "resolver": "grammar",
  "matched_text": "acende a luz da sacada",
  "action": {"verb": "on", "target": "4", "ids": [4]},
  "dry_run": false
}
```

- `status`: `ok` | `not_identified` | `error`.
- `resolver`: `phrase` | `grammar` | `none`.
- `action.target`: id do equipamento (como texto) ou chave do grupo (`luzes_cozinha`, `todas_luzes`).
- `action.ids`: ids afetados (para `todas_luzes`, a lista que o hub devolveu em `accepted`).
- Com `not_identified`, `action` e `matched_text` vêm `null`.

Regra das hipóteses: tentar em ordem; a primeira que resolver de forma não ambígua vence. Se
nenhuma resolver → `not_identified`.

`GET /v1/health`, sem autenticação: `{"status": "ok", "hub": "ok" | "down", "catalog": "ok" |
"pending" | "invalid"}`. Não expõe nada além disso.

## 5. Normalização e gramática

### Normalização (`normalize.py`)

1. Minúsculas, remover acentos e pontuação.
2. Números por extenso → dígitos: `um/uma`→1, `dois/duas`→2, `tres`→3 … `dez`→10.
3. Registrar os marcadores de grupo antes de remover qualquer coisa: quantificador presente
   (`todo/toda/todos/todas/tudo`) e substantivos de tipo no plural (`luzes`, `cortinas`, `persianas`).
4. Remover stopwords: artigos e preposições (`a o as os da do das dos de no na nos nas em e`),
   cortesias (`por favor`, `pfv`, `porfavor`).
5. Remover os quantificadores (já registrados).
6. Tokenizar. **Não singularizar nada.**

Saída: `NormalizedText(original, tokens: list[str], has_quantifier: bool, plural_types: set[str])`.

### Fuzzy

- `rapidfuzz.fuzz.ratio`, limiar **88**, só para tokens com **5 letras ou mais**, e só contra o
  vocabulário de apelidos do YAML.
- **Nunca fuzzy** em: verbos, substantivos de tipo (`luz/luzes`, `cortina/cortinas`,
  `persiana/persianas`, `spot/spots`), números e quantificadores. Esses casam exatos.
- Token que já existe no vocabulário não passa pelo fuzzy.
- Se o fuzzy der mais de uma palavra candidata para um token, o token fica como está (não casa
  nada). O fuzzy nunca transforma um match único em escolha entre vários.

### Verbos → ação e tipos permitidos (casam exatos)

| Ação | Verbos | Tipos |
|---|---|---|
| `on` | acender, acende, acenda, ligar, liga, ligue | luz |
| `off` | apagar, apaga, apague, desligar, desliga, desligue | luz |
| `open` | abrir, abre, abra | cortina, persiana |
| `close` | fechar, fecha, feche | cortina, persiana |

Verbo ausente, desconhecido, ou dois verbos de ações diferentes na frase → `no_match`.

### Resolução (`grammar.py`)

1. **Frase cadastrada** (`phrases.py`, resolvedor 1): os tokens normalizados (com quantificadores)
   iguais aos de uma frase do YAML → executa a ação mapeada.
2. **Equipamento por apelido** (resolvedor 2):
   - Filtrar equipamentos pelo tipo permitido pelo verbo.
   - Um apelido casa quando a frase contém todas as palavras dele (ordem livre; palavras extras na
     frase são ignoradas).
   - Vence o(s) apelido(s) com mais palavras. Todos do mesmo equipamento → executa. Equipamentos
     diferentes → `ambiguous`.
   - Apelidos de equipamento são avaliados antes de qualquer grupo (resolve "spots da bancada" =
     18 e "luzes do corredor" = 1).
3. **Grupo com apelido** (só se nenhum equipamento casou):
   - Exige marcador de grupo: plural de tipo ou quantificador.
   - Mesmo critério de match dos equipamentos (todas as palavras, mais longo vence, empate entre
     grupos diferentes = `ambiguous`).
   - Inclui os globais, que têm apelido com "casa" (`luzes casa`, `cortinas casa`).
4. **Global por quantificador** (só se nada acima casou):
   - Exige quantificador **e** que os tokens restantes (fora o verbo) sejam só plurais de tipo, ou
     nenhum. Qualquer outra palavra sobrando → `no_match`.
   - Candidatos: grupos `escopo: global` cujo tipo o verbo permite; se a frase tem plural de tipo,
     só os desse tipo.
   - Exatamente um candidato → executa. Zero ou mais de um → `no_match`.
   - Plural sem quantificador não aciona ("apaga as luzes" = não identificado).
5. Nada casou → `not_identified`, fala "equipamento não identificado".

### Exemplos esperados (viram `tests/frases.yaml`)

| Frase | Resultado |
|---|---|
| acende a luz da sacada | on → 4 |
| acende a luz da sacada por favor | on → 4 |
| fecha a cortina 3 | close → 38 |
| fecha a cortina três | close → 38 |
| abre a cortina oito | open → 43 |
| fecha as cortinas do jantar | close → cortinas_jantar (35) |
| fecha todas as cortinas do jantar | close → cortinas_jantar (35) |
| fecha a cortina do jantar | not_identified (singular sem número) |
| acende os spots da bancada | on → 18 |
| acende o box do banheiro | not_identified |
| acende o box do banheiro da suíte | on → 24 |
| abre a luz da sala | not_identified (verbo não permite luz) |
| liga a cortina 3 | not_identified (verbo não permite cortina) |
| apaga as luzes da sala de estar | off → [4, 14, 17, 28, 31, 32] |
| apaga todas as luzes da cozinha | off → [6, 7, 8, 15] |
| apaga as luzes do banheiro da suíte | off → [22, 23, 24] |
| apaga as luzes do banheiro | not_identified |
| apaga as luzes | not_identified (plural sem cômodo nem quantificador) |
| apaga tudo | off → todas_luzes (endpoint) |
| apaga todas as luzes | off → todas_luzes |
| apaga as luzes da casa | off → todas_luzes |
| acende todas as luzes | on → todas_luzes (depende da Fase 0B) |
| apaga todas as luzes da sala | not_identified (sobra "sala") |
| acende todas as luzes do jardim | not_identified (sobra "jardim") |
| fecha todas as cortinas | close → todas_cortinas |
| abre as cortinas da casa | open → todas_cortinas |
| fecha tudo | close → todas_cortinas (único global de abre/fecha) |
| fecha todas as persianas | not_identified (não há grupo de persianas) |
| fecha a persiana | not_identified (3 persianas) |
| fecha a persiana do quarto | close → 46 |
| acende o spot da sala | not_identified ("sala" sem qualificador) |
| acender a luz do quarto | on → 33 |
| apaga a luz da suíte | off → 33 |
| apaga todas as luzes do quarto | off → [33, 34] (não contém `luz`) |
| acende a luz da pia do banheiro social | on → 9 |
| acende a luz da pia da cozinha | on → 8 |
| acende a luz da pia do banheiro | not_identified (sem "luz pia" genérico) |
| acende a luz da mesa | not_identified |
| acende a luz da mesa do escritório | not_identified |
| acende a mesa inferior | on → 29 |
| apaga as luzes do corredor | off → 1 |
| acende a luz da sacada e da copa | not_identified (dois equipamentos) |
| abre e fecha a cortina 3 | not_identified (dois verbos) |
| acende | not_identified |
| bom dia | not_identified |
| acende a luz da sacadas | on → 4 (fuzzy: `sacadas`×`sacada` ≈ 92) |
| acende a luz da escada | not_identified (fuzzy: `escada`×`sacada` ≈ 83) |

As duas últimas linhas existem para fixar o comportamento do fuzzy: se o limiar escolhido não der
esses resultados, o Haiku para e chama o Opus (não ajusta o limiar sozinho).

## 6. Cadastro: `config/casa.yaml`

Formato, por equipamento: `tipo`, `falado` (texto da resposta), `apelidos` e, quando não for
feminino singular, `genero` (`m`) e/ou `plural: true`. Grupos são sempre plurais; `genero` padrão
`f`.

```yaml
devices:
  # Regra: todo apelido tem uma palavra-âncora: o substantivo do tipo no singular (luz, spot,
  # cortina, persiana) ou um nome próprio do equipamento (lustre, painel, box, espelho, pia,
  # mesa...). Âncora presente em mais de um equipamento (pia, mesa, box, espelho, spot) sempre
  # leva qualificador. Nenhum apelido de equipamento pode estar contido numa frase de grupo.

  # Área de Serviço
  5:  { tipo: luz, falado: "luz da área de serviço", apelidos: ["luz area servico", "luzes area servico"] }
  # Cozinha
  6:  { tipo: luz, falado: "luz da geladeira", apelidos: ["luz geladeira"] }
  7:  { tipo: luz, falado: "luz da copa", apelidos: ["luz copa"] }
  8:  { tipo: luz, falado: "luz da pia da cozinha", apelidos: ["luz pia cozinha", "pia cozinha"] }
  15: { tipo: luz, falado: "luz da despensa", apelidos: ["luz despensa"] }
  # Sala de estar
  4:  { tipo: luz, falado: "luz da sacada", apelidos: ["luz sacada"] }
  14: { tipo: luz, falado: "spot da sala de estar", genero: m, apelidos: ["spot sala estar"] }
  17: { tipo: luz, falado: "spot da decoração", genero: m, apelidos: ["spot decoracao", "luz decoracao"] }
  28: { tipo: luz, falado: "retângulo da sala de estar", genero: m, apelidos: ["luz retangulo", "retangulo sala estar"] }
  31: { tipo: luz, falado: "luz do painel da TV", apelidos: ["luz painel", "painel tv"] }
  32: { tipo: luz, falado: "perímetro da sala de estar", genero: m, apelidos: ["luz perimetro", "perimetro sala estar"] }
  42: { tipo: cortina, falado: "cortina 7", apelidos: ["cortina 7"] }
  43: { tipo: cortina, falado: "cortina 8", apelidos: ["cortina 8"] }
  44: { tipo: cortina, falado: "cortina 9", apelidos: ["cortina 9"] }
  # Sala de Jantar
  3:  { tipo: luz, falado: "spot do pilar", genero: m, apelidos: ["spot pilar", "luz pilar"] }
  16: { tipo: luz, falado: "luz da mesa de jantar", apelidos: ["luz mesa jantar", "mesa jantar"] }
  18: { tipo: luz, falado: "spots da bancada", genero: m, plural: true, apelidos: ["spots bancada", "spot bancada", "luz bancada"] }
  25: { tipo: luz, falado: "luz da churrasqueira", apelidos: ["luz churrasqueira"] }
  26: { tipo: luz, falado: "lustre do jantar", genero: m, apelidos: ["lustre"] }
  36: { tipo: cortina, falado: "cortina 1", apelidos: ["cortina 1"] }
  37: { tipo: cortina, falado: "cortina 2", apelidos: ["cortina 2"] }
  38: { tipo: cortina, falado: "cortina 3", apelidos: ["cortina 3"] }
  39: { tipo: cortina, falado: "cortina 4", apelidos: ["cortina 4"] }
  40: { tipo: cortina, falado: "cortina 5", apelidos: ["cortina 5"] }
  41: { tipo: cortina, falado: "cortina 6", apelidos: ["cortina 6"] }
  # Corredor (inclui o banheiro social)
  1:  { tipo: luz, falado: "luz do corredor", apelidos: ["luz corredor", "luzes corredor"] }
  9:  { tipo: luz, falado: "pia do banheiro social", apelidos: ["pia banheiro social", "luz pia banheiro social"] }
  10: { tipo: luz, falado: "luz do banheiro social", apelidos: ["luz banheiro social", "luz central banheiro social"] }
  11: { tipo: luz, falado: "box do banheiro social", genero: m, apelidos: ["box banheiro social", "box social"] }
  # Sala de Jogos
  2:  { tipo: luz, falado: "spots da sala de jogos", genero: m, plural: true, apelidos: ["spots jogos", "spot jogos", "luz sala jogos", "luzes sala jogos"] }
  47: { tipo: persiana, falado: "persiana da sala de jogos", apelidos: ["persiana jogos", "persiana sala jogos"] }
  # Escritório (inclui o banheiro do escritório)
  12: { tipo: luz, falado: "luz do armário", apelidos: ["luz armario"] }
  13: { tipo: luz, falado: "spot do escritório", genero: m, apelidos: ["spot escritorio"] }
  29: { tipo: luz, falado: "mesa inferior", apelidos: ["mesa inferior"] }
  30: { tipo: luz, falado: "mesa superior", apelidos: ["mesa superior"] }
  19: { tipo: luz, falado: "luz do banheiro do escritório", apelidos: ["luz banheiro escritorio", "luz central banheiro escritorio"] }
  20: { tipo: luz, falado: "box do banheiro do escritório", genero: m, apelidos: ["box banheiro escritorio", "box escritorio"] }
  21: { tipo: luz, falado: "espelho do banheiro do escritório", genero: m, apelidos: ["espelho banheiro escritorio", "espelho escritorio"] }
  45: { tipo: persiana, falado: "persiana do escritório", apelidos: ["persiana escritorio"] }
  # Suíte master (único quarto; "quarto" e "suíte" são sinônimos)
  33: { tipo: luz, falado: "luz do quarto", apelidos: ["luz quarto", "luz suite"] }
  34: { tipo: luz, falado: "spot do quarto", genero: m, apelidos: ["spot quarto", "spot suite"] }
  22: { tipo: luz, falado: "luz do banheiro da suíte", apelidos: ["luz banheiro suite", "luz banheiro quarto", "luz central banheiro suite"] }
  23: { tipo: luz, falado: "espelho do banheiro da suíte", genero: m, apelidos: ["espelho banheiro suite", "espelho suite", "espelho quarto"] }
  24: { tipo: luz, falado: "box do banheiro da suíte", genero: m, apelidos: ["box banheiro suite", "box suite", "box quarto"] }
  46: { tipo: persiana, falado: "persiana do quarto", apelidos: ["persiana quarto", "persiana suite"] }

groups:
  # --- Luzes por cômodo (lista de ids; os banheiros são grupos à parte) ---
  luzes_cozinha:
    { tipo: luz, falado: "luzes da cozinha", apelidos: ["luzes cozinha"], alvo: [6, 7, 8, 15] }
  luzes_sala_estar:
    { tipo: luz, falado: "luzes da sala de estar", apelidos: ["luzes sala estar"], alvo: [4, 14, 17, 28, 31, 32] }
  luzes_sala_jantar:
    { tipo: luz, falado: "luzes da sala de jantar", apelidos: ["luzes sala jantar", "luzes jantar"], alvo: [3, 16, 18, 25, 26] }
  luzes_banheiro_social:
    { tipo: luz, falado: "luzes do banheiro social", apelidos: ["luzes banheiro social"], alvo: [9, 10, 11] }
  luzes_escritorio:
    { tipo: luz, falado: "luzes do escritório", apelidos: ["luzes escritorio"], alvo: [12, 13, 29, 30] }
  luzes_banheiro_escritorio:
    { tipo: luz, falado: "luzes do banheiro do escritório", apelidos: ["luzes banheiro escritorio"], alvo: [19, 20, 21] }
  luzes_quarto:
    { tipo: luz, falado: "luzes do quarto", apelidos: ["luzes quarto", "luzes suite"], alvo: [33, 34] }
  luzes_banheiro_suite:
    { tipo: luz, falado: "luzes do banheiro da suíte", apelidos: ["luzes banheiro suite", "luzes banheiro quarto"], alvo: [22, 23, 24] }
  # Cômodos com uma luz só (área de serviço, corredor, sala de jogos): o apelido plural fica no
  # próprio equipamento ("luzes do corredor" → id 1).

  # --- Cortinas ---
  cortinas_jantar:
    { tipo: cortina, falado: "cortinas do jantar", apelidos: ["cortinas jantar", "cortinas sala jantar"], alvo: [35] }  # 35 = "Cortinas Geral", equipamento físico
  cortinas_sala_estar:
    { tipo: cortina, falado: "cortinas da sala de estar", apelidos: ["cortinas sala estar"], alvo: [42, 43, 44] }

  # --- Globais ---
  todas_luzes:
    { tipo: luz, escopo: global, falado: "todas as luzes", apelidos: ["luzes casa"], alvo: hub_todas_luzes }
  todas_cortinas:
    { tipo: cortina, escopo: global, falado: "todas as cortinas", apelidos: ["cortinas casa"], alvo: [35, 42, 43, 44] }

  # Não existe grupo de persianas, nem global.

phrases: {}
  # "boa noite": { acao: off, alvo: todas_luzes }
```

- `alvo: hub_todas_luzes` é o único alvo especial: `off` → `POST /api/lights/off`; `on` →
  `POST /api/lights/on`. Só vale para `tipo: luz`.
- `phrases`: chave escrita em português natural, normalizada na carga; `alvo` é um id ou uma
  chave de grupo.

### Verificações na carga (`catalog.py`)

**Locais, falham o startup** (rodam também na suíte de testes):
1. Esquema: campos obrigatórios, tipos válidos, `alvo` aponta para ids cadastrados em `devices`
   (ou `hub_todas_luzes` em grupo de luz), no máximo um global por tipo.
2. Nenhum apelido repetido entre equipamentos/grupos do mesmo tipo.
3. Colisão por resolução (usa o resolvedor de verdade):
   - cada apelido de equipamento, em "{verbo} {apelido}" com um verbo do tipo, resolve para o
     próprio equipamento;
   - cada `falado` de equipamento, em "{verbo} {falado}", resolve para o próprio equipamento;
   - cada apelido de grupo, em "{verbo} as {apelido}" e "{verbo} todas as {apelido}", resolve para
     o próprio grupo e não é capturado por equipamento.

**Contra o hub, não derrubam o serviço:** no startup e a cada 60 s até passar, `GET /api/equipment`:
- todo id do YAML existe, com `kind` compatível (`luz`→`light`, `cortina`→`curtain`,
  `persiana`→`blind`) e não `momentary`. Falhou → `catalog: "invalid"`, `/v1/command` responde
  `error` com "cadastro inválido, veja o log" e o journal diz qual id;
- equipamento `light`/`curtain`/`blind` do hub que não está no YAML → só aviso no log;
- enquanto o hub não respondeu nenhuma vez → `catalog: "pending"`, comandos respondem `error`
  "hub da casa fora do ar".

## 7. Execução, respostas e log

**Execução (`module.py`)**:
- Equipamento: `set` (luz) ou `move` (cortina/persiana).
- Grupo com lista: um comando por id, em paralelo (`asyncio.gather`).
- `hub_todas_luzes`: endpoint do hub.
- Timeout do cliente do hub: 5 s.
- `ASSISTANT_DRY_RUN=1`: não chama `set`/`move`/`lights`; responde como se todos fossem aceitos,
  com `dry_run: true` e a fala prefixada com "teste: ".

**Frases faladas (`speech.py`)**, a partir de `falado`, `genero` e `plural`:

| Ação | f | m | f plural | m plural |
|---|---|---|---|---|
| `on` | acesa | aceso | acesas | acesos |
| `off` | apagada | apagado | apagadas | apagados |
| `open` | aberta | aberto | abertas | abertos |
| `close` | fechada | fechado | fechadas | fechados |

- Sucesso total: "{falado} {particípio}" (ex.: "spots da bancada acesos", "todas as luzes apagadas").
- Parcial (algum 503 ou `unreachable`): "{falado} {particípio}, {n} sem conexão", com `status: ok`.
- Nenhum aceito, ou hub inacessível: `status: error`, "não consegui executar".
- `not_identified`: "equipamento não identificado".
- Cortina e persiana: 202 significa **enviado**; a frase não promete que mexeu, mas também não
  avisa disso (fica curta).

**Log (`request_log.py`)**: uma linha por requisição em `data/requests.jsonl`: `ts` (ISO, fuso
local), `hypotheses`, `resolver`, `status`, `matched_text`, `action`, `hub_result` (resumido),
`dry_run`, `latency_ms`. Sem token. Sem rotação na v1 (volume pequeno); esse log vira o
conjunto de teste do Jev.

## 8. App Android

**Molde:** `~/dev/home_devices/android/` (app "Casa"): Java, `AndroidManifest.xml`, `res/`, `src/`
e um `build.py` que chama `aapt2`, `javac`, `d8` e `apksigner` direto, sem Gradle. Foi feito para
o Windows (`%LOCALAPPDATA%`); aqui ele é adaptado para Linux. Copiar a estrutura, **não** importar
nada daquele repo.

Fluxo (`MainActivity`, tela pequena e translúcida):
1. Ao abrir: confere `RECORD_AUDIO` (pede na primeira vez) e inicia o `SpeechRecognizer` com
   `LANGUAGE_MODEL_FREE_FORM`, `EXTRA_LANGUAGE = "pt-BR"`, `EXTRA_MAX_RESULTS = 5`.
2. `onResults`: lê `RESULTS_RECOGNITION` e `CONFIDENCE_SCORES` (pode vir `null`; valor `-1` ou
   `0` = sem confiança, não manda o campo).
3. `POST {url}v1/command` (`HttpURLConnection`, em thread de fundo), tentando a URL da LAN com
   timeout de conexão de **800 ms**; **só em falha de conexão** (não em 4xx/5xx), tenta a URL da
   Meshnet. Timeout de leitura: 6 s. Repetir é seguro: todos os comandos são idempotentes (não
   incluir "alternar" no futuro sem rever isso).
4. Mostra o que ouviu e a resposta; fala `speech` com `TextToSpeech` pt-BR; fecha ao terminar de
   falar.
5. Erro de rede: fala "sem conexão com a casa".

`SettingsActivity`: URL da LAN, URL da Meshnet e token, em `SharedPreferences`.
`allowBackup="false"`. Valores padrão: `http://192.168.68.86/assistant_server/` e
`http://caio.ishizaka-andes.nord/assistant_server/`.

Manifesto:
- `INTERNET`, `RECORD_AUDIO`.
- `<queries>` com os intents `android.speech.RecognitionService` e
  `android.intent.action.TTS_SERVICE` (Android 11+: sem isso o reconhecimento e o TTS ficam
  invisíveis para o app).
- `network_security_config`: cleartext liberado só para `192.168.68.86`,
  `caio.ishizaka-andes.nord` e `127.0.0.1` (este último para testar no staging com `adb reverse`).

Assistente padrão (Fase 8, Opus): o provável mínimo para aparecer em "App assistente digital
padrão" é `VoiceInteractionService` + `VoiceInteractionSessionService` + um `RecognitionService`
vazio + `res/xml/voice_interaction_service.xml` (`sessionService`, `recognitionService`,
`supportsAssist="true"`). A sessão só abre a `MainActivity`. **A verificar** na fase; uma activity
com `ACTION_ASSIST` sozinha provavelmente não basta nas versões atuais.

## 9. Regras para o Haiku

- Trabalha só em `~/dev/assistant_server`, numa branch de feature. Commit e push só dessa branch.
- **Nunca edita outro repo.** `~/dev/home_devices` é só para ler o código do hub e o molde do app.
- Nunca usa `~/apps/`, `sudo`, `data/` de produção, nem o hub de produção (`:8103`). Hub, para ele,
  é o hub falso dos testes (`httpx.MockTransport` sobre `tests/fixtures/equipment.json`).
- Segue o contrato e a gramática das seções 4 a 7 **sem mudar comportamento**. Se uma biblioteca
  instalada não bater com o que o plano supõe, adapta a implementação e relata.
- **Nunca altera** `tests/frases.yaml` para um teste passar, nem o limiar do fuzzy, nem apelidos do
  `casa.yaml`. Se a gramática não der o resultado da tabela, para.
- **Para e chama o Opus se:**
  - um teste falhar duas vezes seguidas sem causa clara;
  - um exemplo da tabela da seção 5 não sair como escrito;
  - a verificação de colisão acusar algo no `casa.yaml`;
  - for preciso mexer fora do que a fase pede;
  - a fase pedir deploy, systemd, nginx, `sudo` ou o hub de produção.
- Ao terminar uma fase: `pytest` verde, commit, push, e um relato curto: o que fez, o que desviou
  do plano e o que o Caio precisa testar.

**Como o Caio entrega uma fase ao Haiku:** abrir o Claude Code em `~/dev/assistant_server` com o
modelo Haiku (`/model haiku`) e pedir: *"Leia `PLAN.md` e execute a Fase N. Respeite a seção 9."*
Para voltar ao Opus: `/model opus` e *"Revise a Fase N do `PLAN.md`"* (ou o ponto de parada que o
Haiku relatou).

## 10. Fases

Legenda: 🤖H = Haiku, 🧠O = Opus, 👤C = Caio.

### Fase 0A: levantamento (🧠O, feito em 2026-10-23)
Resultado na seção 2. Nada a fazer.

### Fase 0B: `POST /api/lights/on` no `home_devices` (🧠O, numa sessão do `home_devices`)
Pode correr em paralelo às Fases 1 a 3; só bloqueia o exemplo "acende todas as luzes" no staging.
1. Ler o `CLAUDE.md` e os desenhos do `home_devices` (o "Apagar luzes" está no desenho §5.9).
2. Na branch `feat/lights-on`: generalizar `Hub.lights_off` para `lights_set(lights, value, client)`,
   rota `POST /api/lights/on` com a mesma resposta; manter `/api/lights/off` igual. Testes no molde
   dos de `lights/off`.
3. Fluxo normal do `home_devices`: push, link de comparação, merge do Caio, deploy completo
   (`pull --ff-only` + `sudo systemctl restart home-devices` para o Caio, na mesma resposta),
   conferência no journal. Fora das janelas de agendamento do hub.
4. Se o Caio desistir do acender tudo: `todas_luzes` aceita só `off`, e "acende todas as luzes" /
   "acende tudo" viram `not_identified` (ajustar a seção 5).

Volta para: ninguém (independente).

### Fase 1: esqueleto, normalização e cadastro (🤖H, ~1 h)
1. `git checkout -b feat/fase1-base`. Estrutura da seção 3 (sem `android/` e `deploy/` ainda):
   `.gitignore` (`.venv/`, `data/`, `__pycache__/`, `.env`), `CLAUDE.md`, `README.md` mínimo.
2. `.venv` com `python3 -m venv .venv`; `requirements.txt`: `fastapi`, `uvicorn`, `httpx`,
   `pyyaml`, `rapidfuzz`; `requirements-dev.txt`: `-r requirements.txt` + `pytest`,
   `pytest-asyncio`. Fixar com `==` as versões que instalar.
3. `normalize.py` + `tests/test_normalize.py`: acentos, pontuação, números por extenso, stopwords,
   cortesias, quantificadores registrados e removidos, plurais de tipo registrados, nada
   singularizado.
4. `tests/fixtures/equipment.json`: lista no formato de `GET /api/equipment` com os 47
   equipamentos da seção 6 (ids 1–47; `kind` a partir do `tipo`; o 27 como
   `{"kind": "disposal", "momentary": true}`; `name` livre; `room_id` conforme a seção 2).
5. `config/casa.yaml` exatamente como a seção 6. `catalog.py`: carga + verificações locais 1 e 2
   (a 3 entra na Fase 2). Testes: YAML válido carrega; YAML com id inexistente no `alvo`, apelido
   repetido e dois globais do mesmo tipo falham com mensagem clara.

Volta para: 🤖H (Fase 2).

### Fase 2: gramática e pipeline (🤖H, ~1–2 h)
1. Branch `feat/fase2-gramatica` (a partir da Fase 1).
2. `modules/base.py`, `phrases.py`, `grammar.py`, `pipeline.py`, conforme a seção 5.
3. `tests/frases.yaml` com **todas** as linhas da tabela da seção 5, no formato
   `- {frase: "...", status: ok, verb: on, target: "4"}` ou `- {frase: "...", status: not_identified}`.
   Um teste parametrizado lê o arquivo.
4. Pipeline de hipóteses: testes com a primeira ambígua e a segunda resolvendo (vence a segunda),
   todas sem match (`not_identified`), e a primeira resolvendo (as outras nem são tentadas).
5. Verificação local 3 (colisão por resolução) no `catalog.py`, chamada na carga e num teste.
6. Commit, push e relato.

Volta para: 🧠O (revisão da gramática).

### Revisão 1: gramática (🧠O)
Ponto mais sensível do projeto; não segue para a Fase 3 sem ela.
1. Ler o diff das Fases 1 e 2 inteiro.
2. Procurar frases que passem pelas regras e acionem a coisa errada (sobras de palavras, fuzzy,
   números, "e", dois verbos). Acrescentar os casos ao `frases.yaml`.
3. Rever o `casa.yaml` com a regra das âncoras compartilhadas.
4. Corrigir na própria branch ou devolver ao Haiku com instruções.

Volta para: 🤖H (Fase 3).

### Fase 3: hub, execução, HTTP e log (🤖H, ~1–2 h)
1. Branch `feat/fase3-api`.
2. `hub_client.py` (no molde do `~/dev/caio_mcp/caio_mcp/casa/hub_client.py`: `httpx.AsyncClient`,
   Bearer, timeout 5 s, exceções `HubIndisponivel` e `HubRecusou`) com `equipment()`, `set()`,
   `move()`, `lights_off()`, `lights_on()`, `health()`.
3. Verificação contra o hub (seção 6) com nova tentativa a cada 60 s; estados `pending`/`ok`/`invalid`.
4. `module.py` (`execute`), `speech.py`, dry-run (seção 7).
5. `api.py`: `/v1/command` e `/v1/health` (seção 4); `__main__.py` com `--port` (padrão 8105) e
   `--host 127.0.0.1` fixo; `request_log.py`.
6. Testes com `httpx.MockTransport` + `fastapi.testclient`: 401 sem token; 422 sem hipóteses;
   ok/parcial/erro para equipamento, grupo e `todas_luzes`; dry-run não chama o hub; hub fora →
   `catalog: pending`; id do YAML ausente no hub → `invalid`; uma linha no `requests.jsonl` por
   requisição, sem token.
7. Sem teste manual nesta fase (o devhub tem outros ids); basta o `pytest`. Commit, push, relato.

Volta para: 🧠O (Fase 4).

### Fase 4: staging (🧠O + 👤C)
1. 🧠O: revisão do diff da Fase 3.
2. 👤C cria o token do hub com o rótulo `Assistente de voz` (comando exato passado pelo Opus, com
   `read -s` para a senha não ir para o histórico) e guarda em `~/dev/assistant_server/.env.staging`
   (`chmod 600`, ignorado pelo git) junto de um `ASSISTANT_TOKEN` de staging. O mesmo token do hub
   serve depois em produção.
3. 🧠O sobe o staging: `CASA_HUB_URL=http://127.0.0.1:8103`, `ASSISTANT_DRY_RUN=1`,
   `.venv/bin/python -m assistant_server --port 8197`. Só leituras no hub de produção.
4. 🧠O roda a tabela da seção 5 com `curl` contra o staging e confere `catalog: ok` (ids reais).
5. 👤C testa por `curl` (ou pelo app, a partir da Fase 7, com `adb reverse tcp:8197 tcp:8197`).
6. Com o Caio por perto: `ASSISTANT_DRY_RUN=0` e três comandos reais (uma luz, um grupo, uma
   cortina). Derrubar o staging.
7. 🧠O: push, link de comparação; 👤C abre o PR e faz o merge.

Volta para: 🧠O (Fase 5).

### Fase 5: produção do servidor (🧠O + 👤C)
Primeira instalação de app nova no andes: checklist completo do `GUIA-APPS.md`.
1. 🧠O, numa branch: `deploy/assistant-server.service` no molde da unit de referência do guia
   (`ExecStart=... -m assistant_server --port 8105`, `EnvironmentFile=.../.env`,
   `ReadWritePaths=/home/caio/apps/assistant_server/data`, `NoNewPrivileges=true`,
   `After=home-devices.service` sem `Requires`) e `deploy/assistant_server.conf`
   (`location /assistant_server/ { proxy_pass http://127.0.0.1:8105/; include /etc/nginx/proxy_params; }`).
   README com o runbook. Push, link, merge do 👤C.
2. 🧠O: `git clone` em `~/apps/assistant_server`, `mkdir data`, venv, `pip install -r requirements.txt`.
3. 👤C: `~/apps/assistant_server/.env` (`chmod 600`) com `ASSISTANT_TOKEN` (novo, de produção),
   `CASA_HUB_URL=http://127.0.0.1:8103` e `CASA_HUB_TOKEN`.
4. 🧠O passa, na mesma resposta, os `sudo` (um por bloco): `cp` da unit, `daemon-reload`,
   `enable --now assistant-server`, `cp` da conf do nginx de `~/staging/andes-locations/`,
   `nginx -t`, `reload nginx`, `cp` da página inicial com o cartão novo.
5. 🧠O confere: journal, `curl 127.0.0.1:8105/v1/health`, `curl http://192.168.68.86/assistant_server/v1/health`,
   um comando real com o Caio, `diff` da conf instalada.
6. 🧠O atualiza `~/andes/GUIA-APPS.md` (porta 8105 e staging 8197, "O que já está no ar") e
   `~/andes/ESTADO.md` (serviço, nginx, apps).

Volta para: 👤C (Fase 6). Deploys seguintes: fluxo normal do guia.

### Fase 6: ambiente de build Android no andes (👤C + 🧠O)
1. 🧠O passa o `sudo apt install openjdk-21-jdk-headless` para o 👤C.
2. 🧠O, sem `sudo`: Android SDK command-line tools em `~/android-sdk` (zip oficial, conferindo o
   SHA-256 publicado), `sdkmanager "platform-tools" "build-tools;<atual>" "platforms;android-<atual>"`,
   aceitar as licenças (👤C confirma). Nada no `PATH` global; o `build.py` acha pelo `ANDROID_HOME`.
3. 👤C, no celular: Opções do desenvolvedor → Depuração sem fio → "Parear com código". 🧠O roda
   `adb pair <ip>:<porta>` e `adb connect <ip>:<porta>` com os números que o Caio ditar.
4. Teste: `adb devices` lista o Razr.

Volta para: 🤖H (Fase 7).

### Fase 7: app, fluxo básico (🤖H código, 👤C teste)
1. Branch `feat/fase7-app`. `android/` no molde do app "Casa" (seção 8): `build.py` para Linux
   (`ANDROID_HOME`, saída em `android/build/`, ignorada pelo git; `build.py install` faz
   `adb install -r`), `MainActivity`, `SettingsActivity`, manifesto, `network_security_config`.
   Pacote `br.caiocosta.assistente`, nome "Assistente".
2. **Passo explícito de teste da confiança:** a `MainActivity` mostra na tela, durante a fase,
   todas as hipóteses com o `CONFIDENCE_SCORES` cru de cada uma. 👤C fala 10 frases da tabela da
   seção 5 e anota: quantas hipóteses vêm, se a confiança vem, se vem só na primeira. O relato
   vai para a seção 11 deste plano. Se a ordem do Android não for a da confiança, 🧠O decide se o
   app reordena antes de mandar.
3. 👤C testa contra o staging (`adb reverse tcp:8197 tcp:8197`, URL `http://127.0.0.1:8197/`,
   dry-run) e depois contra a produção, em casa (LAN) e fora (Meshnet; Wi-Fi desligado).
4. Teste do reconhecimento offline: com o pacote pt-BR baixado e o celular em modo avião + Wi-Fi da
   casa. Só anotar; não bloqueia.

**Para e chama o Opus** se o `build.py` não gerar um APK instalável em duas tentativas.

Volta para: 🧠O (Fase 8).

### Fase 8: assistente padrão (🧠O)
1. Revisar o diff da Fase 7.
2. Implementar o registro da seção 8 e verificar no Razr se aparece em Configurações → Apps →
   Apps padrão → App assistente digital. Testar o gesto (segurar o botão liga/desliga, ou o que o
   Razr oferecer) e a tela bloqueada.
3. Se o mínimo não bastar, pesquisar a documentação da versão do Android do aparelho antes de
   acrescentar peças.
4. Push, link, merge do 👤C. APK instalado por `build.py install`.

Volta para: 👤C (Fase 9).

### Fase 9: uso real (👤C uma semana, depois 🧠O)
1. 👤C usa por uma semana.
2. 🧠O lê o `requests.jsonl` de produção (só leitura) e propõe: apelidos novos, frases novas para o
   `frases.yaml`, verbos que faltaram. Mudanças pelo fluxo normal (Haiku pode implementar se a
   lista vier fechada).

## 11. Resultados de testes (preenchido durante as fases)

- Confiança do `SpeechRecognizer` no Razr (Fase 7): _pendente_.
- Reconhecimento offline pt-BR (Fase 7): _pendente_.

## 12. Roadmap (fora da v1)

- Resolvedor Jev (TypeSafe AI) entre gramática e não identificado, com opção obrigatória
  "equipamento não identificado". Testar 1 vs 2 camadas (módulo → ação) em acerto e latência
  usando o `requests.jsonl`.
- Novos módulos além da casa.
- Handoff para o Claude.
