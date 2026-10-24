# App "Assistente"

Cliente fino do assistente de voz (PLAN.md, seção 8): ouve o comando em pt-BR, manda as hipóteses
para o servidor `assistant_server` e fala a resposta. Nenhuma frase, comando ou equipamento fica no app.

## Construir e instalar

Com o celular conectado por USB (depuração USB ligada) e o SDK em `~/android-sdk`:

```
ANDROID_HOME=~/android-sdk python3 android/build.py           # gera android/build/assistente.apk
ANDROID_HOME=~/android-sdk python3 android/build.py install   # gera e instala (adb install -r)
```

Ferramentas: JDK 21 (`javac --release 17`), build-tools 36.1.0, `android-36`, platform-tools. Sem Gradle.
A chave de assinatura é a de debug (`~/.android/debug.keystore`, criada na primeira vez).

## Endereços

Na tela "Configurações": endereço da LAN (`http://192.168.68.86/assistant_server/`), da Meshnet
(`http://caio.ishizaka-andes.nord/assistant_server/`) e o token do servidor (`ASSISTANT_TOKEN` do `.env`
de produção, nunca no git). Para o staging, `adb reverse tcp:8197 tcp:8197` e a LAN em
`http://127.0.0.1:8197/`.

A ordem é LAN primeiro, com timeout de conexão de 800 ms. Só falha de conexão passa para a Meshnet.
Resposta de erro do servidor (401, 4xx, 5xx) não repete.

## Teste da confiança (Fase 7, passo 2)

A tela mostra, para cada resultado do reconhecedor, o texto e o `CONFIDENCE_SCORES` cru. Fale 10
frases da tabela da seção 5 do `PLAN.md` e anote, para cada uma:
- quantas hipóteses aparecem;
- se aparece a linha `CONFIDENCE_SCORES` com valores ou `ausente`;
- se a confiança vem só na primeira hipótese ou em todas.

O relato vai para a seção 11 do plano.
