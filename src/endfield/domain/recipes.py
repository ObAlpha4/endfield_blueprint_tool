"""配方与发电模型：``Flow`` / ``Recipe`` / ``PowerEntry``。

字段依据 ``design/domain-model.md`` §4、§5、§6.2，速率口径依据 ``design/baseline-rules.md``
A-7（``每分钟配方次数 = 60 / 反应时间``，对**所有设备**普遍成立，多台线性叠加）。

两条必须守住的语义：

- ``inputs`` / ``outputs`` 允许为空数组，且**空数组的含义不同**：
  ``outputs = []`` 表示**销毁输入**（废水处理机，A-2）；``inputs = []`` 表示**外部来源/采集**；
- 催化剂按 **R-061 / A-3：每台设备固定 6/min** 记账，与配方数值和实际产率无关，
  源表 ``M`` 列的 6 只是这一常量的原始记录。
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping

from endfield.items import ItemKind, classify_kind, unit_for

#: R-061 / A-3：固气转化机 / 液气转化机每台固定消耗催化剂 6/min（与配方无关）。
CATALYST_PER_MINUTE: Fraction = Fraction(6)

#: 单格缓存上限（A-6 / R-045）。
MAX_STACK_PER_SLOT: int = 50

#: 缓存格数：反应池 5 / 扩容反应池 8 / 协议储存箱 6；其余设备 = 输入物料种类数（R-067）。
EXPLICIT_SLOT_COUNTS: Mapping[str, int] = {
    "反应池": 5,
    "扩容反应池": 8,
    "协议储存箱": 6,
}

#: 环境生成配方（用配方表描述环境生成的特例）：``outputs`` 收在 ``environment_produced``。
ENVIRONMENT_NAMES: tuple[str, ...] = ("稳定环境", "湿润环境", "酸性环境", "息壤环境")


@dataclass(frozen=True)
class Flow:
    """配方中的一个物料项（数量 + 物料名）。"""

    item: str
    quantity: Fraction

    @property
    def kind(self) -> ItemKind:
        return classify_kind(self.item)

    @property
    def unit(self) -> str:
        return unit_for(self.kind)

    def rate_per_minute(self, batches_per_minute: Fraction) -> Fraction:
        """精确速率：``数量 × 每分钟配方次数``。"""
        return self.quantity * batches_per_minute

    def as_dict(self) -> dict[str, object]:
        return {
            "item": self.item,
            "quantity": _fraction_dict(self.quantity),
            "kind": self.kind,
            "unit": self.unit,
        }


@dataclass(frozen=True)
class Recipe:
    """一条配方（``docs/产线配方.xlsx`` 的一行）。"""

    id: str
    source_row: int
    inputs: tuple[Flow, ...]
    outputs: tuple[Flow, ...]
    duration_seconds: Fraction
    device_raw_name: str
    device_canonical_name: str
    environment: str | None = None
    catalyst: str | None = None
    catalyst_per_minute: Fraction = Fraction(0)
    environment_produced: str | None = None
    source_columns: Mapping[str, str] | None = None

    @property
    def batches_per_minute(self) -> Fraction:
        """A-7：每分钟配方次数 = 60 / 反应时间。"""
        return Fraction(60) / self.duration_seconds

    @property
    def destroys_input(self) -> bool:
        """A-2：产物列为空 = 销毁输入。"""
        return not self.outputs and not self.environment_produced

    @property
    def is_environment_recipe(self) -> bool:
        """环境生成特例（气体散布机，源表第 126–129 行）。"""
        return self.environment_produced is not None

    @property
    def is_gathering(self) -> bool:
        """采集/开采配方：无输入（R-001 的设备在蓝图外）。"""
        return not self.inputs

    @property
    def slot_count(self) -> int:
        """R-067 缓存格数。"""
        explicit = EXPLICIT_SLOT_COUNTS.get(self.device_canonical_name)
        if explicit is not None:
            return explicit
        return len(self.inputs)

    @property
    def input_item_kinds(self) -> int:
        """并行配方需检查的「涉及的总物料种类」（R-062 / B-6）。"""
        return len({flow.item for flow in self.inputs})

    @property
    def input_overflow(self) -> bool:
        """一次配方的原料总量是否超过单格缓存上限 50（A-6：只约束补料节奏）。"""
        return sum(flow.quantity for flow in self.inputs) > MAX_STACK_PER_SLOT

    def out_rate_per_minute(self, item: str) -> Fraction:
        return sum((flow.rate_per_minute(self.batches_per_minute) for flow in self.outputs if flow.item == item), Fraction(0))

    def in_rate_per_minute(self, item: str) -> Fraction:
        return sum((flow.rate_per_minute(self.batches_per_minute) for flow in self.inputs if flow.item == item), Fraction(0))

    def label(self) -> str:
        ins = " + ".join(f"{_number(flow.quantity)}{flow.item}" for flow in self.inputs) or "（无输入）"
        if self.environment_produced:
            outs = f"（生成环境 {self.environment_produced}）"
        else:
            outs = " + ".join(f"{_number(flow.quantity)}{flow.item}" for flow in self.outputs) or "（销毁）"
        return f"行{self.source_row} {ins} → {outs} [{self.device_canonical_name} {_number(self.duration_seconds)}s]"

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "sourceRow": self.source_row,
            "inputs": [flow.as_dict() for flow in self.inputs],
            "outputs": [flow.as_dict() for flow in self.outputs],
            "environmentProduced": self.environment_produced,
            "durationSeconds": _fraction_dict(self.duration_seconds),
            "batchesPerMinute": _fraction_dict(self.batches_per_minute),
            "deviceRawName": self.device_raw_name,
            "deviceCanonicalName": self.device_canonical_name,
            "environment": self.environment,
            "catalyst": self.catalyst,
            "catalystPerMinute": _fraction_dict(self.catalyst_per_minute),
            "destroysInput": self.destroys_input,
            "slotCount": self.slot_count,
            "inputOverflow": self.input_overflow,
            "sourceColumns": dict(self.source_columns or {}),
        }


@dataclass(frozen=True)
class PowerEntry:
    """发电对照表的一行（``docs/发电对照.xlsx``）。"""

    id: str
    raw_name: str
    canonical_name: str
    quantity: Fraction
    burn_seconds: Fraction
    power_kw: Fraction
    source_row: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "rawName": self.raw_name,
            "canonicalName": self.canonical_name,
            "quantity": _fraction_dict(self.quantity),
            "burnSeconds": _fraction_dict(self.burn_seconds),
            "powerKw": _number(self.power_kw),
            "sourceRow": self.source_row,
        }


def _fraction_dict(value: Fraction) -> dict[str, object]:
    """把精确有理数序列化成 ``{num, den, value}``，避免浮点序列化破坏可重复性。"""
    return {"num": value.numerator, "den": value.denominator, "value": _number(value)}


def _number(value: Fraction | int | float) -> float | int:
    fraction = Fraction(value)
    if fraction.denominator == 1:
        return fraction.numerator
    return float(fraction)
