"""Runtime-editable settings stored in the system_settings table (credentials stay in env vars)."""
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.system import SystemSetting


def defaults() -> dict[str, dict[str, Any]]:
    s = get_settings()
    return {
        "company_name": {"value": "", "description": "Company name used in BUI's answers."},
        "llm_provider": {"value": s.llm_provider, "description": "ollama | openai | extractive"},
        "llm_model": {"value": "", "description": "Model name for the selected provider. Leave empty to use the server default (OLLAMA_MODEL / OPENAI_MODEL)."},
        "llm_temperature": {"value": s.llm_temperature, "description": "Lower = more deterministic answers."},
        "answer_min_score": {"value": 0.30, "description": "Minimum retrieval relevance (0-1) required before BUI answers from the knowledge base."},
        "retrieval_top_k": {"value": 6, "description": "Number of knowledge chunks given to the model."},
        "web_research_enabled": {"value": True, "description": "Allow online research from chat and the research module."},
        "team_can_research_from_chat": {"value": True, "description": "Allow team members to request online research from chat (results are clearly marked unverified)."},
        "official_domains": {"value": [], "description": "Domains treated as official manufacturer sources (e.g. example.com)."},
        "answer_cache_ttl_seconds": {"value": 3600, "description": "How long identical questions are served from cache. Cache is cleared on any knowledge change."},
        "default_language": {"value": "en-US", "description": "Default chat/voice language."},
    }


def get_setting(db: Session, key: str) -> Any:
    row = db.get(SystemSetting, key)
    if row is not None:
        return row.value
    d = defaults().get(key)
    return d["value"] if d else None


def all_settings(db: Session) -> dict[str, dict[str, Any]]:
    result = defaults()
    for row in db.query(SystemSetting).all():
        if row.key in result:
            result[row.key]["value"] = row.value
    return result


def set_setting(db: Session, key: str, value: Any, user_id: int | None) -> None:
    if key not in defaults():
        raise KeyError(key)
    row = db.get(SystemSetting, key)
    if row is None:
        row = SystemSetting(key=key, description=defaults()[key]["description"])
        db.add(row)
    row.value = value
    row.updated_by_id = user_id
