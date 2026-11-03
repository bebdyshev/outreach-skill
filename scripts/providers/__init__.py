"""Pick the email provider named in config.json and call its enrich()."""
from __future__ import annotations

import importlib
import json
import re

from paths import data_dir

DEFAULT_PROVIDER = "guess"


class ProviderError(Exception):
    pass


def provider_name() -> str:
    path = data_dir() / "config.json"
    if not path.exists():
        return DEFAULT_PROVIDER
    try:
        return json.loads(path.read_text()).get("provider", DEFAULT_PROVIDER)
    except json.JSONDecodeError as e:
        raise ProviderError(f"{path} is not valid JSON: {e}") from e


def enrich(company: str, domain: str, person: str, known: list[dict] | None = None) -> dict:
    name = provider_name()
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        raise ProviderError(f"invalid provider name '{name}' in config.json")
    module_name = f"providers.{name}"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        if e.name != module_name:
            raise
        raise ProviderError(f"unknown provider '{name}' in config.json") from e
    return module.enrich(company, domain, person, known or [])
