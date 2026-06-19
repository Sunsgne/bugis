"""Localized default work order titles."""
from __future__ import annotations

from app.models.enums import WorkOrderType

_TITLES: dict[str, dict[WorkOrderType, str]] = {
    "zh": {
        WorkOrderType.PROVISION: "开通专线 {code}",
        WorkOrderType.MODIFY: "变更专线 {code}",
        WorkOrderType.DECOMMISSION: "拆除专线 {code}",
        WorkOrderType.MIGRATE: "迁移专线 {code}",
    },
    "en": {
        WorkOrderType.PROVISION: "Provision circuit {code}",
        WorkOrderType.MODIFY: "Modify circuit {code}",
        WorkOrderType.DECOMMISSION: "Decommission circuit {code}",
        WorkOrderType.MIGRATE: "Migrate circuit {code}",
    },
}


def normalize_locale(locale: str | None) -> str:
    if not locale:
        return "zh"
    loc = locale.strip().lower()
    if loc.startswith("en"):
        return "en"
    return "zh"


def default_work_order_title(
    wo_type: WorkOrderType,
    circuit_code: str,
    *,
    locale: str | None = None,
) -> str:
    loc = normalize_locale(locale)
    template = _TITLES[loc].get(
        wo_type, f"{wo_type.value} circuit {{code}}"
    )
    return template.format(code=circuit_code)
