import logging
from pathlib import Path
from typing import Any
import yaml
from ..models import SOPDefinition

logger = logging.getLogger(__name__)

_LOADED_SOPS_CACHE: list[SOPDefinition] | None = None


def extract_required_fields(condition: dict[str, Any]) -> set[str]:
    fields = set()
    if "field" in condition:
        fields.add(str(condition["field"]))
    for key in ("all", "any"):
        if key in condition and isinstance(condition[key], list):
            for child in condition[key]:
                if isinstance(child, dict):
                    fields.update(extract_required_fields(child))
    if "not" in condition and isinstance(condition["not"], dict):
        fields.update(extract_required_fields(condition["not"]))
    if "fuzzy_score" in condition and isinstance(condition["fuzzy_score"], dict):
        for factor in condition["fuzzy_score"].get("factors", []):
            if isinstance(factor, dict) and "field" in factor:
                fields.add(str(factor["field"]))
    return fields


def get_default_sops_path() -> Path:
    # Walk up from this file's location to locate config/sops.yaml
    current = Path(__file__).resolve().parent
    candidates = [
        current.parent.parent / "config" / "sops.yaml",          # backend/config/sops.yaml
        current.parent.parent.parent / "config" / "sops.yaml",   # repo_root/config/sops.yaml
    ]
    for cand in candidates:
        if cand.is_file():
            return cand
    # Fallback to current working directory relative
    cwd_cand = Path.cwd() / "config" / "sops.yaml"
    if cwd_cand.is_file():
        return cwd_cand
    return candidates[0]


def load_sops(path: Path | None = None, reload: bool = False) -> list[SOPDefinition]:
    global _LOADED_SOPS_CACHE
    if _LOADED_SOPS_CACHE is not None and not reload and path is None:
        return _LOADED_SOPS_CACHE

    target_path = path or get_default_sops_path()
    if not target_path.exists():
        raise FileNotFoundError(f"SOP configuration file not found at: {target_path}")

    with target_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict) or "sops" not in data or not isinstance(data["sops"], list):
        raise ValueError("Invalid SOP file structure: expected top-level 'sops' list")

    definitions: list[SOPDefinition] = []
    version = data.get("version", 1)

    for item in data["sops"]:
        if not isinstance(item, dict):
            continue
        req_fields = sorted(extract_required_fields(item.get("conditions", {})))
        sop = SOPDefinition(
            id=item["id"],
            title=item["title"],
            category=item["category"],
            activities=item.get("activities", []),
            severity=item["severity"],
            priority=int(item["priority"]),
            conditions=item["conditions"],
            guidance=item.get("guidance", []),
            required_weather_fields=req_fields,
            version=version,
        )
        definitions.append(sop)

    if path is None:
        _LOADED_SOPS_CACHE = definitions

    logger.info("Successfully loaded %d SOP definitions from %s", len(definitions), target_path)
    return definitions
