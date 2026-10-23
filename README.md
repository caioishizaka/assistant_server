# assistant_server

Servidor do assistente de voz da casa. Recebe o texto que o celular reconheceu, interpreta de forma determinística e chama a API do hub do `home_devices`.

O plano completo, com as fases e as regras de quem executa cada uma, está em `PLAN.md`.

## Desenvolvimento

```
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

O cadastro da casa fica em `config/casa.yaml`. Mudança no cadastro passa por teste antes de ir para o servidor.
