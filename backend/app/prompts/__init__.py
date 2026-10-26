"""Judge prompt rendering (M3).

``judge.md`` is the HANDOFF §7 prompt verbatim with ``{schema}``,
``{rules}``, and ``{detections_table}`` slots. ``render_judge_prompt``
fills them; ``build_detections_table`` formats the candidates the
judge sees (same ids as the overlay labels). Slots are replaced with
plain string substitution so JSON braces in the schema value can
never disturb rendering.
"""

import json
import re
from pathlib import Path

from app.schemas import Detection, Verdict

_JUDGE_TEMPLATE = Path(__file__).resolve().parent / "judge.md"


def _format_mm(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else "-"


def build_detections_table(detections: list[Detection]) -> str:
    """One line per candidate: id, label, score, size in px and mm."""
    if not detections:
        return "(no candidates)"
    lines = [
        "id | label | score | area_px | length_px | area_mm2 | length_mm"
    ]
    for detection in detections:
        lines.append(
            f"{detection.id} | {detection.label} | {detection.score:.2f} | "
            f"{detection.area_px} | {detection.length_px:.1f} | "
            f"{_format_mm(detection.area_mm2)} | "
            f"{_format_mm(detection.length_mm)}"
        )
    return "\n".join(lines)


def render_judge_prompt(rules: str, detections: list[Detection]) -> str:
    """Render ``judge.md`` with the Verdict schema, rules, and table."""
    template = _JUDGE_TEMPLATE.read_text(encoding="utf-8")
    values = {
        "{schema}": json.dumps(Verdict.model_json_schema(), sort_keys=True),
        "{rules}": rules,
        "{detections_table}": build_detections_table(detections),
    }
    return re.sub(
        r"\{schema\}|\{rules\}|\{detections_table\}",
        lambda match: values[match.group(0)],
        template,
    )
