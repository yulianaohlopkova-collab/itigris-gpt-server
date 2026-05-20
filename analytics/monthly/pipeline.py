from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from ..contracts import MonthFacts, monthfacts_to_dict


def write_month_facts_json(facts: MonthFacts, out_path: str) -> None:
    Path(out_path).write_text(json.dumps(monthfacts_to_dict(facts), ensure_ascii=False, indent=2), encoding="utf-8")


def write_signals_json(facts: MonthFacts, out_path: str) -> None:
    """
    MVP v1: keep signals engine minimal. We'll expand iteratively.
    """
    signals: Dict[str, Any] = {
        "month": facts.month_meta.month,
        "source": {"type": facts.source_type, "id": facts.source_id, "generated_at_unix": facts.generated_at_unix},
        "signals": [],
    }
    Path(out_path).write_text(json.dumps(signals, ensure_ascii=False, indent=2), encoding="utf-8")

