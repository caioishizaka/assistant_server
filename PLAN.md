# Assistente de voz — plano v1

Assistente de voz próprio no celular (Motorola Razr 60, Android) para comandar a casa. O app só captura a fala e manda o texto. Um serviço Python novo no servidor `andes` interpreta o texto de forma determinística e chama a API do `home_devices`.

## Decisões fechadas

| Tema | Decisão |
|---|---|
| Papel do app | Cliente fino: botão → `SpeechRecognizer` → envia hipóteses → fala a resposta (TTS local). Nenhuma frase, comando ou equipamento fixo no app. |
| Papel do servidor | Projeto novo em Python (não é parte do `home_devices`). Faz todo o parsing e chama a API do `home_devices` com um usuário de serviço. |
| MCP | Fora. O serviço bate direto na API do `home_devices`. |
| Decisão v1 | Só rota determinística. Jev (TypeSafe AI) fica no roadmap como mais um resolvedor. |
| Cadastro | Arquivo YAML no servidor. Mudança = redeploy (aceitável). |
| Fonte da verdade dos equipamentos | API do `home_devices`. O YAML guarda só apelidos, grupos e frases. |
| Ambiguidade | Sempre falha com "equipamento não identificado". Nunca escolhe um padrão. |
| Grupos | Só grupos explícitos no YAML. Marcados por plural ou por "todo/toda/todos/todas/tudo". |
| Autenticação app → servidor | Token fixo (Bearer). App não será distribuído. |
| Rede | URL local (IP fixo) primeiro; namespace do Nord como backup. |
| Resposta | Frase curta gerada pelo servidor, falada pelo TTS nativo do Android. |
| Acionamento | Só botão / gesto de assistente. Sem wake word. |
| Handoff para o Claude | Fora do escopo. Quando precisar, abre o Claude direto. |
| Escopo de equipamentos | Luzes, cortinas e persianas. Triturador fora. |
| Ambiente de dev | Debian (`avell`/`andes`), sem Android Studio: JDK 17 + Android SDK command-line tools + Gradle wrapper + `adb` sem fio. |

## Arquitetura

```
[Razr 60]                                 [andes]
botão/gesto assistente                    voice-assistant (Python)
  → SpeechRecognizer (pt-BR)                POST /v1/command
  → POST hipóteses + token  ───────────►    normalização
                                            resolvedores em cadeia:
                                              1. frase cadastrada
                                              2. gramática (módulo home_devices)
                                              3. [roadmap] Jev
                                              4. não identificado
                                            → API home_devices
  ← { status, speech }  ◄────────────────   log JSONL
  → TextToSpeech fala "speech"
```

### Estrutura do serviço (sugestão)

```
voice-assistant/
  app/
    main.py              # HTTP (seguir o framework/convenções do home_devices)
    normalize.py         # normalização de texto
    pipeline.py          # cadeia de resolvedores
    modules/
      base.py            # interface de módulo
      home_devices/
        module.py        # resolve() e execute()
        client.py        # cliente da API do home_devices
  config/
    home_devices.yaml    # apelidos, grupos, frases
  tests/
    frases.yaml          # tabela frase → resultado esperado
  logs/                  # requests.jsonl
```

Interface de módulo (para nascer modular, mesmo com um só módulo):

- `resolve(tokens) -> Resolution` — devolve `match` (ação + alvo), `ambiguous`, ou `no_match`.
- `execute(action) -> Result` — chama o backend e devolve sucesso/erro + frase.
- Um verbo que nenhum módulo reconhece = `no_match` geral.

## Contrato HTTP

`POST /v1/command` — header `Authorization: Bearer <token>`

```json
{
  "hypotheses": [
    {"text": "acende a luz da sacada", "confidence": 0.91},
    {"text": "acende a luz da escada", "confidence": 0.42}
  ]
}
```

Resposta:

```json
{
  "status": "ok",                 // ok | not_identified | error
  "speech": "luz da sacada acesa",
  "resolver": "grammar",          // phrase | grammar | none
  "matched_text": "acende a luz da sacada",
  "action": {"verb": "on", "targets": [4]}
}
```

`GET /v1/health` — status do serviço e da conexão com o `home_devices`.

Regra das hipóteses: tentar em ordem de confiança; a primeira que resolver de forma não ambígua vence. Se nenhuma resolver → `not_identified`.

## Normalização

1. Minúsculas, remover acentos e pontuação.
2. Números por extenso → dígitos (`um/uma`→1, `dois/duas`→2, … `dez`→10). Cobrir "cortina três" e "cortina 3".
3. Remover stopwords: artigos e preposições (`a o as os da do das dos de no na nos nas em`), cortesias (`por favor`, `pfv`).
4. Tokenizar. Guardar se o texto tem marcador de grupo antes de remover qualquer coisa.

Tolerância a erro de transcrição: comparação fuzzy por token (ex.: `rapidfuzz`, limiar alto, ~85–90). O fuzzy nunca pode transformar um match único em escolha entre vários: se o fuzzy gerar mais de um candidato, é ambíguo.

## Gramática (módulo home_devices)

### Verbos → ação e tipos permitidos

| Ação | Verbos (formas normalizadas) | Tipos |
|---|---|---|
| `on` | acender, acende, acenda, ligar, liga, ligue | luz |
| `off` | apagar, apaga, apague, desligar, desliga, desligue | luz |
| `open` | abrir, abre, abra | cortina, persiana |
| `close` | fechar, fecha, feche | cortina, persiana |

Verbo ausente ou desconhecido → `not_identified`. Persianas usam só abrir/fechar, como cortinas.

### Resolução

1. **Frase cadastrada** (resolvedor 1): texto normalizado igual a uma frase do YAML → executa a ação mapeada.
2. **Equipamento por apelido** (resolvedor 2):
   - Filtrar equipamentos pelo tipo permitido pelo verbo.
   - Um apelido casa quando a frase contém todas as palavras do apelido (ordem livre; palavras extras na frase são ignoradas). Ex.: "acender a luz do quarto" → tokens {luz, quarto} contêm o apelido "luz quarto" → id 33.
   - Vence o(s) apelido(s) com mais palavras. Se todos apontam para o mesmo equipamento → executa. Se apontam para equipamentos diferentes → `not_identified`. Ex.: "acende a luz do banheiro da suíte" casa "luz suite" (2) e "luz banheiro suite" (3) → vence 22.
   - Substantivos de tipo e números casam exatos, nunca fuzzy: `luz` ≠ `luzes`, `cortina` ≠ `cortinas`, `persiana` ≠ `persianas`, `3` ≠ `8`. É isso que separa equipamento (singular) de grupo (plural): "todas as luzes do quarto" não contém `luz`, então não casa "luz quarto" e cai no grupo `luzes_quarto`. Fuzzy só vale para as demais palavras.
   - A normalização não singulariza nada.
   - Apelidos de equipamento são avaliados antes da regra de grupo. Isso resolve equipamentos com nome no plural ("spots da bancada" = id 18, "spots dos jogos" = id 2).
3. **Grupo** (só se nenhum equipamento casou):
   - Exige marcador de grupo: substantivo de tipo no plural (`luzes`, `cortinas`, `persianas`) ou quantificador (`todo/toda/todos/todas/tudo`).
   - Quantificadores são marcadores, não tokens de apelido: são registrados e removidos antes do match. Isso evita empate entre "todas as luzes" e "luzes da cozinha" em "apaga todas as luzes da cozinha".
   - 3a. Grupos de cômodo: casar com apelidos, mesmo critério dos equipamentos (todos os tokens, mais longo vence, empate entre grupos diferentes = ambíguo).
   - 3b. Grupos globais (`escopo: global`): só se nenhum grupo de cômodo casou **e** há quantificador. Escolhidos pelo tipo do verbo e, quando houver, pelo apelido (`cortinas`). Sem apelido, vale o grupo global se ele for o único compatível com o verbo; se houver mais de um, `not_identified`. Plural sozinho não aciona global ("apaga as luzes" = não identificado; "apaga todas as luzes" = todas).
   - Grupo pode apontar para um equipamento físico (ex.: id 35) ou para uma lista de ids.
4. Nada casou → `not_identified` com fala "equipamento não identificado".

### Exemplos esperados

| Frase | Resultado |
|---|---|
| acende a luz da sacada | on → 4 |
| fecha a cortina 3 | close → 38 |
| fecha a cortina três | close → 38 |
| fecha as cortinas do jantar | close → 35 (grupo) |
| fecha todas as cortinas do jantar | close → 35 (grupo) |
| fecha a cortina do jantar | not_identified (singular, 6 candidatos) |
| acende os spots da bancada | on → 18 (equipamento, não grupo) |
| acende o box do banheiro | not_identified (3 banheiros) |
| acende o box do banheiro da suíte | on → 24 |
| abre a luz da sala | not_identified (verbo não permite luz) |
| apaga as luzes da sala de estar | off → [4, 14, 17, 28, 31, 32] |
| apaga todas as luzes da cozinha | off → [6, 7, 8, 15] |
| apaga as luzes do banheiro da suíte | off → [22, 23, 24] (3 tokens vencem "luzes suite") |
| apaga as luzes do banheiro | not_identified |
| apaga as luzes | not_identified (plural sem cômodo nem quantificador) |
| apaga tudo / apaga todas as luzes | off → todas_luzes |
| fecha todas as cortinas | close → todas_cortinas |
| fecha tudo | close → todas_cortinas (único global compatível) |
| fecha todas as persianas | not_identified (sem grupo de persianas) |
| acende o spot da sala | not_identified ("sala" sem qualificador) |
| acender a luz do quarto | on → 33 |
| apaga todas as luzes do quarto | off → [33, 34] (não contém `luz`) |
| acende a luz da pia do banheiro social | on → 9 (4 palavras vencem "luz pia" e "luz banheiro social") |
| apaga as luzes do corredor | off → 1 (apelido plural do próprio equipamento) |
| fecha a persiana do quarto | close → 46 |

## YAML — rascunho para revisão

IDs conferem com o `home_devices`. Apelidos são sugestões a revisar; o servidor deve validar na subida que todo id do YAML existe na API (falhar o startup se não existir).

```yaml
devices:
  # Regra: todo apelido tem uma "palavra-âncora" — o substantivo do tipo no singular
  # (luz, spot, cortina, persiana) ou um nome próprio do equipamento (lustre, painel,
  # box, espelho, pia, mesa...). Nenhum apelido de equipamento pode ser formado só por
  # palavras que aparecem em apelidos de grupo (ver regras de match).

  # Área de Serviço
  5:  { tipo: luz, falado: "luz da área de serviço", apelidos: ["luz area servico", "luzes area servico"] }
  # Cozinha
  6:  { tipo: luz, falado: "luz da geladeira", apelidos: ["luz geladeira"] }
  7:  { tipo: luz, falado: "luz da copa", apelidos: ["luz copa"] }
  8:  { tipo: luz, falado: "luz da pia da cozinha", apelidos: ["luz pia cozinha", "luz pia"] }
  15: { tipo: luz, falado: "luz da despensa", apelidos: ["luz despensa"] }
  # Sala de estar
  4:  { tipo: luz, falado: "luz da sacada", apelidos: ["luz sacada"] }
  14: { tipo: luz, falado: "spot da sala de estar", apelidos: ["spot sala estar"] }
  17: { tipo: luz, falado: "spot da decoração", apelidos: ["spot decoracao", "luz decoracao"] }
  28: { tipo: luz, falado: "retângulo da sala", apelidos: ["luz retangulo", "retangulo sala estar"] }
  31: { tipo: luz, falado: "luz do painel da TV", apelidos: ["luz painel", "painel tv"] }
  32: { tipo: luz, falado: "perímetro da sala", apelidos: ["luz perimetro", "perimetro sala estar"] }
  42: { tipo: cortina, falado: "cortina 7", apelidos: ["cortina 7"] }
  43: { tipo: cortina, falado: "cortina 8", apelidos: ["cortina 8"] }
  44: { tipo: cortina, falado: "cortina 9", apelidos: ["cortina 9"] }
  # Sala de Jantar
  3:  { tipo: luz, falado: "spot do pilar", apelidos: ["spot pilar", "luz pilar"] }
  16: { tipo: luz, falado: "luz da mesa de jantar", apelidos: ["luz mesa jantar", "luz mesa"] }
  18: { tipo: luz, falado: "spots da bancada", apelidos: ["spots bancada", "spot bancada", "luz bancada"] }
  25: { tipo: luz, falado: "luz da churrasqueira", apelidos: ["luz churrasqueira"] }
  26: { tipo: luz, falado: "lustre do jantar", apelidos: ["lustre"] }
  36: { tipo: cortina, falado: "cortina 1", apelidos: ["cortina 1"] }
  37: { tipo: cortina, falado: "cortina 2", apelidos: ["cortina 2"] }
  38: { tipo: cortina, falado: "cortina 3", apelidos: ["cortina 3"] }
  39: { tipo: cortina, falado: "cortina 4", apelidos: ["cortina 4"] }
  40: { tipo: cortina, falado: "cortina 5", apelidos: ["cortina 5"] }
  41: { tipo: cortina, falado: "cortina 6", apelidos: ["cortina 6"] }
  # Corredor
  1:  { tipo: luz, falado: "luz do corredor", apelidos: ["luz corredor", "luzes corredor"] }
  9:  { tipo: luz, falado: "pia do banheiro social", apelidos: ["pia banheiro social", "luz pia banheiro social"] }
  10: { tipo: luz, falado: "luz do banheiro social", apelidos: ["luz banheiro social", "luz central banheiro social"] }
  11: { tipo: luz, falado: "box do banheiro social", apelidos: ["box banheiro social", "box social"] }
  # Sala de Jogos
  2:  { tipo: luz, falado: "spots da sala de jogos", apelidos: ["spots jogos", "spot jogos", "luz sala jogos", "luzes sala jogos"] }
  47: { tipo: persiana, falado: "persiana da sala de jogos", apelidos: ["persiana jogos", "persiana sala jogos"] }
  # Escritório
  12: { tipo: luz, falado: "luz do armário", apelidos: ["luz armario"] }
  13: { tipo: luz, falado: "spot do escritório", apelidos: ["spot escritorio"] }
  29: { tipo: luz, falado: "mesa inferior", apelidos: ["mesa inferior"] }
  30: { tipo: luz, falado: "mesa superior", apelidos: ["mesa superior"] }
  19: { tipo: luz, falado: "luz do banheiro do escritório", apelidos: ["luz banheiro escritorio", "luz central banheiro escritorio"] }
  20: { tipo: luz, falado: "box do banheiro do escritório", apelidos: ["box banheiro escritorio", "box escritorio"] }
  21: { tipo: luz, falado: "espelho do banheiro do escritório", apelidos: ["espelho banheiro escritorio", "espelho escritorio"] }
  45: { tipo: persiana, falado: "persiana do escritório", apelidos: ["persiana escritorio"] }
  # Suíte master (único quarto)
  33: { tipo: luz, falado: "luz do quarto", apelidos: ["luz quarto", "luz suite"] }
  34: { tipo: luz, falado: "spot do quarto", apelidos: ["spot quarto", "spot suite"] }
  22: { tipo: luz, falado: "luz do banheiro da suíte", apelidos: ["luz banheiro suite", "luz banheiro quarto", "luz central banheiro suite"] }
  23: { tipo: luz, falado: "espelho do banheiro da suíte", apelidos: ["espelho banheiro suite", "espelho suite", "espelho quarto"] }
  24: { tipo: luz, falado: "box do banheiro da suíte", apelidos: ["box banheiro suite", "box suite", "box quarto"] }
  46: { tipo: persiana, falado: "persiana do quarto", apelidos: ["persiana quarto", "persiana suite"] }

groups:
  # --- Luzes por cômodo ---
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
  # Cômodos com uma luz só (área de serviço, corredor, sala de jogos) não precisam
  # de grupo: o apelido do próprio equipamento já casa ("luzes da sala de jogos" → id 2).

  # --- Cortinas e persianas ---
  cortinas_jantar:
    { tipo: cortina, falado: "cortinas do jantar", apelidos: ["cortinas jantar", "cortinas sala jantar"], alvo: 35 }  # equipamento físico "Cortinas Geral"
  cortinas_sala_estar:
    { tipo: cortina, falado: "cortinas da sala de estar", apelidos: ["cortinas sala estar"], alvo: [42, 43, 44] }

  # --- Globais (sem apelido; só com quantificador, ver Gramática) ---
  todas_luzes:
    { tipo: luz, escopo: global, falado: "todas as luzes",
      alvo: [5, 6, 7, 8, 15, 4, 14, 17, 28, 31, 32, 3, 16, 18, 25, 26, 1, 9, 10, 11, 2, 12, 13, 29, 30, 19, 20, 21, 33, 34, 22, 23, 24] }
  todas_cortinas:
    { tipo: cortina, escopo: global, falado: "todas as cortinas", apelidos: ["cortinas"], alvo: [35, 42, 43, 44] }

phrases: {}
  # "boa noite": { acao: off, alvo: [...] }
```

Regras de apelidos:
- Nenhum apelido de uma palavra só que seja nome de cômodo ("quarto", "suite", "corredor", "cozinha"...). Todo apelido tem palavra-âncora: substantivo de tipo no singular ou nome próprio do equipamento.
- "Sala" nunca sem qualificador (existem três: estar, jantar e jogos).
- "Quarto" e "suíte" são o mesmo cômodo (só existe um quarto) e são sinônimos nos apelidos.
- Cômodos com uma luz só (área de serviço, corredor, sala de jogos) recebem o apelido no plural direto no equipamento ("luzes corredor"), em vez de um grupo.
- Nenhum apelido de equipamento pode estar contido numa frase de grupo. Ex.: se o equipamento 22 tivesse apelido "banheiro suite", "apaga as luzes do banheiro da suíte" casaria o equipamento antes do grupo. Por isso é "luz banheiro suite".

## Respostas faladas

Montadas a partir do campo `falado`:

- `on` → "{falado} acesa" (ou "acesos" para plural; simples: tabela de gênero/número no YAML, ou frase neutra "{falado} ligado(a)" — decidir na implementação, sem complicar).
- `off` → "{falado} apagada".
- `open`/`close` → "{falado} aberta/fechada".
- `not_identified` → "equipamento não identificado".
- Falha na API → "não consegui executar".

## Log

Toda requisição em `logs/requests.jsonl`: timestamp, hipóteses, resolvedor, resultado, latência. Esse log vira o conjunto de teste do Jev.

## App Android

- Kotlin nativo, sem Android Studio. Build no Debian: JDK 17, `sdkmanager` (platform-tools, build-tools, platform alvo), `./gradlew assembleDebug`, instalação via `adb pair` + `adb connect` + `adb install`.
- Registro como assistente padrão do celular. **Verificar** o mínimo necessário para aparecer em "App assistente digital padrão" (provavelmente `VoiceInteractionService` + `VoiceInteractionSessionService` + metadata `voice-interaction-service`; checar se uma activity com `ACTION_ASSIST` basta nas versões atuais).
- Fluxo: abrir → `SpeechRecognizer` pt-BR com `EXTRA_MAX_RESULTS` → enviar todas as hipóteses com confiança → falar `speech` com `TextToSpeech` pt-BR → fechar.
- Configuração no app: URL local, URL do Nord, token. Nada mais.
- Rede: tentar URL local com timeout curto (~800 ms); em falha de conexão, tentar a URL do Nord. Não repetir em erro de aplicação (4xx/5xx).
- Testar depois se o reconhecimento pt-BR funciona offline com pacote baixado (não bloqueia o plano).

## Fases

### Fase 0 — Levantamento
- Inspecionar o `home_devices`: endpoints de ligar/desligar e abrir/fechar, endpoint de listagem, formato de autenticação, framework HTTP usado.
- Criar o usuário de serviço no `home_devices`.
- Confirmar como acionar o id 35 (abrir/fechar como cortina comum?).

### Fase 1 — Servidor
- Normalização + testes unitários.
- Carregamento do YAML + sincronização com a API (validar ids).
- Teste de colisão de apelidos, rodando no startup e na suíte de testes:
  - cada apelido de equipamento, usado como frase ("acende a {apelido}"), resolve para o próprio equipamento;
  - cada apelido de grupo, usado como frase ("apaga as {apelido}" e "apaga todas as {apelido}"), resolve para o próprio grupo e não é capturado por nenhum equipamento;
  - nenhum apelido aparece em dois equipamentos/grupos do mesmo tipo;
  - falhar o startup se houver colisão.
- Resolvedores (frase, gramática) + pipeline.
- Cliente do `home_devices` + endpoint `/v1/command` + `/v1/health` + log.
- Tabela `tests/frases.yaml` com os exemplos acima e mais casos negativos.

### Fase 2 — Deploy no `andes`
- systemd, porta fixa, token em variável de ambiente.
- Acesso pela rede local e pelo namespace do Nord.
- Teste com `curl`.

### Fase 3 — App
- Ambiente de build no Debian.
- Esqueleto: activity com botão → STT → HTTP → TTS.
- Registro como assistente padrão.

### Fase 4 — Uso real
- Uma semana de uso. Revisar `requests.jsonl`: frases que falharam viram apelidos novos ou casos de teste.

## Roadmap (fora da v1)

- Resolvedor Jev (TypeSafe AI) entre gramática e não identificado, com opção obrigatória "equipamento não identificado". Testar 1 vs 2 camadas (módulo → ação) em acerto e latência usando o log.
- Novos módulos além do `home_devices`.
- Handoff para o Claude.

## Em aberto

- Se a API do `home_devices` tiver endpoint de "apagar todas", usar no lugar da lista em `todas_luzes` (verificar na Fase 0).

Confirmado: banheiros são grupos separados dos cômodos; a lista de 33 luzes está completa; apelidos revisados.
