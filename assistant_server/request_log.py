"""Log de requisições em `data/requests.jsonl` (PLAN.md, seção 7). Uma linha por comando. Sem token."""

import json
from datetime import datetime
from pathlib import Path


class RegistroRequisicoes:
    def __init__(self, pasta: Path):
        self._arquivo = pasta / "requests.jsonl"

    def escrever(self, registro: dict) -> None:
        self._arquivo.parent.mkdir(parents=True, exist_ok=True)
        linha = {"ts": datetime.now().astimezone().isoformat(timespec="seconds"), **registro}
        with self._arquivo.open("a", encoding="utf-8") as arquivo:
            arquivo.write(json.dumps(linha, ensure_ascii=False) + "\n")
