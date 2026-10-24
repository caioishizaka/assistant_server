# assistant_server

Servidor do assistente de voz da casa. Recebe o texto que o celular reconheceu, interpreta de forma determinística e chama a API do hub do `home_devices`.

O plano completo, com as fases e as regras de quem executa cada uma, está em `PLAN.md`.

## Desenvolvimento

```
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

O cadastro da casa fica em `config/casa.yaml`. Mudança no cadastro passa por teste antes de ir para o servidor: a suíte inclui a verificação de colisões, que também roda no startup (com colisão, o serviço não sobe).

## Staging

Na porta 8197, em dry-run (só lê o hub de produção, não manda comando). `.env.staging` (ignorado pelo git, `chmod 600`) tem o `CASA_HUB_TOKEN`:

```
set -a && . ./.env.staging && set +a && ASSISTANT_TOKEN=<qualquer> ASSISTANT_DRY_RUN=1 \
  CASA_HUB_URL=http://127.0.0.1:8103 .venv/bin/python -m assistant_server --port 8197
```

## Produção

- Clone em `~/apps/assistant_server`, venv `.venv`, unit `assistant-server` (`deploy/assistant-server.service`), `127.0.0.1:8105`.
- nginx: `deploy/assistant_server.conf` em `/etc/nginx/andes-locations/`. Endereços: `http://192.168.68.86/assistant_server/` (LAN) e `http://caio.ishizaka-andes.nord/assistant_server/` (Meshnet).
- `.env` (`chmod 600`, fora do git): `ASSISTANT_TOKEN` (o que o app manda), `CASA_HUB_URL=http://127.0.0.1:8103`, `CASA_HUB_TOKEN` (token do hub com o rótulo `Assistente de voz`).
- Dados: `data/requests.jsonl`, uma linha por comando.

Deploy de mudança de código: `git -C ~/apps/assistant_server pull --ff-only`, `pip install -r requirements.txt` se ele mudou, e `sudo systemctl restart assistant-server`.

Conferir:

```
curl -s http://127.0.0.1:8105/v1/health
curl -s http://192.168.68.86/assistant_server/v1/health
journalctl -u assistant-server -n 30 --no-pager
```

`/v1/health` responde `{"status": "ok", "hub": "ok" | "down", "catalog": "ok" | "pending" | "invalid"}`. Com `catalog: invalid`, o journal diz qual id do cadastro não bate com o hub; os comandos respondem "cadastro inválido, veja o log" até o cadastro ser corrigido.

Revogar o acesso do assistente ao hub: apagar o token `Assistente de voz` pela API de tokens do hub (`DELETE /api/auth/tokens/{id}`).
