"""物品与品类（solid / liquid / gas）。

四份源文件里**没有物品表**，``Item.kind`` 无法从端口标记反推（同一种物料会同时出现在
固体端口与液体/气体端口上，例如 ``清水``、``赤铜块``、``息壤``）。因此本模块的品类
完全来自**用户确认的规则**（阶段 2 对话，原文）：

    清水、沉积酸、污水、壤晶废液、惰性壤晶废液、液化**、**溶液都是液体，
    **气、气态**都是气体

落地口径（机械可执行，无歧义）：

1. 命中**容器例外**名单 → ``solid``（装的液体是内容物，容器本身是物品）；
2. 否则命中显式液体名单，**或**名称包含 ``液化`` / ``溶液`` → ``liquid``；
3. 否则名称包含 ``气``（覆盖 ``气态``）→ ``gas``；
4. 否则 → ``solid``。

容器的口径由用户后续补充确认：**「容器名里含『溶液』的，本身属于固体（物品）」**。
源表里这类名字只有 4 个（`蓝铁瓶（装有芽针溶液）`、`蓝铁瓶（装有锦草溶液）`、
`赤铜瓶（装有芽针溶液）`、`赤铜瓶（装有锦草溶液）`），已逐一列为例外，
不依赖「瓶 / 罐」之类的关键词猜测（``紫晶质瓶``、``赤铜耐压罐`` 等不含关键词本来也是固体）。

覆盖自检见 ``endfield.items.self_check``：全量 111 个物料命中，
无任何物料同时命中液体与气体关键词；容器例外一律落在固体。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

ItemKind = Literal["solid", "liquid", "gas"]

#: 用户显式点名的液体（其余靠关键词 ``液化`` / ``溶液`` 覆盖）。
EXPLICIT_LIQUID_NAMES: frozenset[str] = frozenset(
    {"清水", "沉积酸", "污水", "壤晶废液", "惰性壤晶废液"}
)

#: 液体关键词。用户确认原文为「液化**、**溶液都是液体」，两个 ``**`` 标记的是
#: 「液化」「溶液」两个关键词。
LIQUID_KEYWORDS: tuple[str, ...] = ("液化", "溶液")

#: 气体关键词（``气`` 已覆盖 ``气态``；``水蒸气`` 由 ``气`` 命中）。
GAS_KEYWORDS: tuple[str, ...] = ("气",)

#: **容器例外**：名字里含 ``溶液``，但本体是装着液体的**固体物品**。
#: 用户确认（阶段 2 对话）：「容器名里含『溶液』的，本身属于固体（物品）」。
CONTAINER_EXCEPTIONS: frozenset[str] = frozenset(
    {
        "蓝铁瓶（装有芽针溶液）",
        "蓝铁瓶（装有锦草溶液）",
        "赤铜瓶（装有芽针溶液）",
        "赤铜瓶（装有锦草溶液）",
    }
)

#: 规则来源，随规范化数据一起落盘，便于追溯。
KIND_RULE_SOURCE = (
    "用户确认（阶段 2 对话）：清水/沉积酸/污水/壤晶废液/惰性壤晶废液/液化…/…溶液为液体；"
    "含“气”“气态”为气体；其余为固体。"
    "容器补充确认：名字含“溶液”的容器本身是固体（物品），已逐一列入容器例外名单"
)


def is_container_exception(name: str) -> bool:
    """该名字是否是「装溶液但仍为固体」的容器。"""
    return name in CONTAINER_EXCEPTIONS


def classify_kind(name: str) -> ItemKind:
    """按用户确认的规则（含容器例外）判定物料品类。"""
    if is_container_exception(name):
        return "solid"
    if name in EXPLICIT_LIQUID_NAMES or any(k in name for k in LIQUID_KEYWORDS):
        return "liquid"
    if any(k in name for k in GAS_KEYWORDS):
        return "gas"
    return "solid"


@dataclass(frozen=True)
class Item:
    """物料：原始名 / 规范名 / 品类 / 单位 / 来源。"""

    raw_name: str
    canonical_name: str
    kind: ItemKind
    unit: str  # "item"（个）或 "drop"（滴）
    source_refs: tuple[dict[str, object], ...] = ()
    kind_note: str | None = None

    @property
    def is_fluid(self) -> bool:
        return self.kind in ("liquid", "gas")

    @property
    def is_container(self) -> bool:
        return is_container_exception(self.canonical_name)

    def as_dict(self) -> dict[str, object]:
        return {
            "rawName": self.raw_name,
            "canonicalName": self.canonical_name,
            "kind": self.kind,
            "unit": self.unit,
            "kindNote": self.kind_note,
            "sourceRefs": [dict(ref) for ref in self.source_refs],
        }


def unit_for(kind: ItemKind) -> str:
    """固体用「个」，液体与气体用「滴」（``design/domain-model.md`` §1 单位约定）。"""
    return "item" if kind == "solid" else "drop"


def build_item(raw_name: str, canonical_name: str, source_refs: Iterable[dict[str, object]] = ()) -> Item:
    kind = classify_kind(canonical_name)
    note = None
    if is_container_exception(canonical_name):
        note = "容器例外：名字含“溶液”，但本体是固体物品（用户确认）"
    return Item(
        raw_name=raw_name,
        canonical_name=canonical_name,
        kind=kind,
        unit=unit_for(kind),
        source_refs=tuple(source_refs),
        kind_note=note,
    )


def self_check(names: Iterable[str]) -> dict[str, object]:
    """对给定物料名集合做品类自检，返回统计、容器例外与冲突项。"""
    name_list = sorted(set(names))
    buckets: dict[str, list[str]] = {"solid": [], "liquid": [], "gas": []}
    conflicts: list[str] = []
    containers: list[str] = []
    for name in name_list:
        if is_container_exception(name):
            containers.append(name)
        liquids = name in EXPLICIT_LIQUID_NAMES or any(k in name for k in LIQUID_KEYWORDS)
        gases = any(k in name for k in GAS_KEYWORDS)
        if liquids and gases and not is_container_exception(name):
            conflicts.append(name)
        buckets[classify_kind(name)].append(name)
    return {
        "counts": {kind: len(items) for kind, items in buckets.items()},
        "items": buckets,
        "conflicts": conflicts,
        "containerExceptions": containers,
    }
