"""Sobe o serviço: `python -m assistant_server [--port 8105]`. Escuta só em 127.0.0.1 (o nginx é quem expõe)."""

import argparse
import os
import sys

import uvicorn

from assistant_server.api import create_app
from assistant_server.config import Settings


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="assistant_server")
    parser.add_argument("--port", type=int, default=8105)
    args = parser.parse_args(argv)

    settings = Settings.do_ambiente(os.environ)
    faltando = [nome for nome, valor in (("ASSISTANT_TOKEN", settings.assistant_token),
                                         ("CASA_HUB_TOKEN", settings.casa_hub_token)) if not valor]
    if faltando:
        sys.exit(f"faltam variáveis de ambiente: {', '.join(faltando)}")
    uvicorn.run(create_app(settings), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
