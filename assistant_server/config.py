"""Configuração vinda do ambiente (PLAN.md, seção 3)."""

from dataclasses import dataclass
from pathlib import Path
from collections.abc import Mapping

RAIZ = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    assistant_token: str
    casa_hub_url: str
    casa_hub_token: str
    dry_run: bool
    data_dir: Path
    casa_yaml: Path = RAIZ / "config" / "casa.yaml"

    @classmethod
    def do_ambiente(cls, ambiente: Mapping[str, str]) -> "Settings":
        return cls(
            assistant_token=ambiente.get("ASSISTANT_TOKEN", ""),
            casa_hub_url=ambiente.get("CASA_HUB_URL", "http://127.0.0.1:8103"),
            casa_hub_token=ambiente.get("CASA_HUB_TOKEN", ""),
            dry_run=ambiente.get("ASSISTANT_DRY_RUN", "0") == "1",
            data_dir=Path(ambiente.get("ASSISTANT_DATA_DIR", RAIZ / "data")),
        )
