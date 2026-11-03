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
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise ProviderError(f"cannot read {path}: {e}") from e
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ProviderError(f"{path} is not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ProviderError(f"{path} must be a JSON object")
    name = data.get("provider", DEFAULT_PROVIDER)
    if not isinstance(name, str):
        raise ProviderError("provider in config.json must be a string")
    return name


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
