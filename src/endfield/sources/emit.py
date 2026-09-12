"""确定性序列化：把规范化中间数据写成逐字节一致的 JSON。

细则：

- UTF-8、**无 BOM**、``\\n`` 换行、文件末尾单个换行；
- JSON 键排序（``sort_keys=True``）、固定缩进 2；
- 速率 / 数量 / 时间一律以**精确有理数** ``{num, den, value}`` 表达，
  不依赖浮点序列化（``json`` 的浮点输出跨版本可能变化，且有理数可被求解器直接使用）；
- 不写入任何时间戳 / 环境相关信息。

因此同一输入连跑两次产生的字节完全相同（``endfield.cli`` 会做 SHA256 校验）。
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from typing import Mapping

from endfield.domain.logistics import BASE_PORT_SPECS, LOGISTICS_FOOTPRINT, LogisticsElementType
from endfield.domain.recipes import CATALYST_PER_MINUTE, MAX_STACK_PER_SLOT, EXPLICIT_SLOT_COUNTS
from endfield.items import (
    CONTAINER_EXCEPTIONS,
    EXPLICIT_LIQUID_NAMES,
    GAS_KEYWORDS,
    KIND_RULE_SOURCE,
    LIQUID_KEYWORDS,
)
from endfield.sources import parser as parser_module
from endfield.sources.parser import SourceBundle

SCHEMA_ID = "endfield.sources"
SCHEMA_VERSION = 1


def fraction_dict(value: Fraction) -> dict[str, object]:
    fraction = Fraction(value)
    if fraction.denominator == 1:
        value_out: object = fraction.numerator
    else:
        value_out = float(fraction)
    return {"num": fraction.numerator, "den": fraction.denominator, "value": value_out}


def build_document(bundle: SourceBundle) -> dict[str, object]:
    """把 ``SourceBundle`` 组装成规范化文档（纯数据，可直接 ``json.dumps``）。"""
    return {
        "schema": SCHEMA_ID,
        "schemaVersion": SCHEMA_VERSION,
        "generatedBy": "endfield.sources.parser（阶段 2：统一数据入口）",
        "conventions": {
            "timeUnit": "second",
            "solidUnit": "item",
            "fluidUnit": "drop",
            "rateUnit": "per-minute",
            "powerUnit": "kW",
            "rationale": "速率以精确有理数 {num, den, value} 表达，避免浮点序列化破坏可重复性",
        },
        "constants": {
            "catalystPerMinute": fraction_dict(CATALYST_PER_MINUTE),
            "maxStackPerSlot": MAX_STACK_PER_SLOT,
            "slotCounts": dict(EXPLICIT_SLOT_COUNTS),
            "baseSizes": {"主基地": [80, 80], "副基地": [50, 50]},
            "powerBaselineKw": 9600,
            "maxPathLength": 80,
        },
        "itemKindRule": {
            "source": KIND_RULE_SOURCE,
            "explicitLiquidNames": sorted(EXPLICIT_LIQUID_NAMES),
            "liquidKeywords": list(LIQUID_KEYWORDS),
            "gasKeywords": list(GAS_KEYWORDS),
            "containerExceptions": sorted(CONTAINER_EXCEPTIONS),
        },
        "markers": [{"marker": marker, "meaning": meaning} for marker, meaning in bundle.markers],
        "deviceCategories": list(parser_module.DEVICE_CATEGORY_NAMES),
        "specialDevices": [device.as_dict() for device in bundle.special_devices],
        "devices": [device.as_dict() for device in bundle.device_types],
        "recipes": [recipe.as_dict() for recipe in bundle.recipes],
        "powerEntries": [entry.as_dict() for entry in bundle.power_entries],
        "items": [item.as_dict() for item in bundle.items],
        "logisticsElements": logistics_element_types(),
        "externalSourceDevices": list(parser_module.EXTERNAL_SOURCE_DEVICES),
        "specOnlyInRules": list(parser_module.SPEC_ONLY_IN_RULES),
        "rules": {
            "note": "规则文档不做自动解析，人工维护为带编号的规则元数据",
            "paragraphCount": len(bundle.rule_paragraphs),
        },
        "validation": bundle.report.as_dict(),
        "sourceFiles": dict(bundle.file_hashes),
    }


def logistics_element_types() -> list[dict[str, object]]:
    """12 种物流元件：**按类型 + 旋转生成端口**（不套用四面接口串）。"""
    rows: list[dict[str, object]] = []
    for element_type in LogisticsElementType:
        specs = BASE_PORT_SPECS[element_type]
        rows.append(
            {
                "elementType": element_type.value,
                "family": element_type.family,
                "footprint": {"width": LOGISTICS_FOOTPRINT, "height": LOGISTICS_FOOTPRINT},
                "portCount": len(specs),
                "basePorts": [spec.as_dict() for spec in specs],
                "isBridge": element_type.is_bridge,
                "isGate": element_type.is_gate,
                "maxRatePerMinute": element_type.max_rate_per_minute,
                "speedStepPerMinute": element_type.speed_step_per_minute,
                "specSource": "B-9：全部 1×1，没有固定的四面接口串，按类型 + 旋转生成端口",
            }
        )
    return rows


def dumps(document: Mapping[str, object]) -> str:
    """确定性 JSON 文本。"""
    return json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def write(document: Mapping[str, object], path: Path) -> tuple[str, int]:
    """写文件并返回 ``(sha256, 字节数)``；父目录自动创建。"""
    import hashlib

    text = dumps(document)
    payload = text.encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest(), len(payload)


def load(path: Path) -> dict[str, object]:
    """读回规范化数据（供 ``tools/show_facility.py`` 等下游使用）。"""
    return json.loads(path.read_text(encoding="utf-8"))
