"""物流元件：12 种「按类型 + 旋转生成端口」的 1×1 器件。

依据 ``design/global-constraints.md`` §2 与 ``design/logistics-and-storage-geometry.md`` §1：
这些元件**在设备概述表里没有规格**（B-9：全部 1×1，供电桩 2×2 是唯一例外），
因此不能套用「四面固定接口串」的表结构，必须**按类型 + 旋转生成端口**。

读数：规则段 2 列出 10 种器件，加上物品弯段与管道弯段两种形态 = **12 种**
（用户已确认：物品弯段与管道弯段分开计算）。

端口数与语义（已确认）：

| 类型 | 端口数 | 端口所在面 | 语义 |
|---|---:|---|---|
| 直段（传送带 / 管道） | 2 | 一组相对面 | 一进一出 |
| 弯段（物品 / 管道） | 2 | 一组相邻面 | 一进一出 |
| 准入口（物品 / 管道） | 2 | 一组相对面 | 一进一出，带物品/流体标记与限速 |
| 桥（物流桥 / 管道桥） | **4** | 四个面 | 两条**正交**线各占 2 口，互不干扰、不混流 |
| 分流器 | 3 或 4 | 1 面进 + 2~3 面出 | 一发散 |
| 汇流器 | 3 或 4 | 2~3 面进 + 1 面出 | 一收拢 |

本模块只做**占格模型 + 端口实例化**；几何判定（长度、同格、连接）属于步骤 4 的验证器。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal, Mapping

from endfield.domain.devices import Face, MaterialKind, Port, PortDirection, PortRole
from endfield.domain.geometry import Cell, GridRect, Rotation, rotate_local_cell

NetworkFamily = Literal["item", "fluid"]

#: B-9：这批物流元件全部占 1×1。
LOGISTICS_FOOTPRINT: int = 1

_ITEM: MaterialKind = "solid"
_FLUID: MaterialKind = "liquid"


class LogisticsElementType(Enum):
    """12 种物流元件。

    读数：规则段 2 列出 10 种器件（传送带、分流器、汇流器、物流桥、物品准入口、
    管道、管道分流器、管道汇流器、管道桥、管道准入口），加上物品弯段与管道弯段
    两种**形态**，共 12 种。用户已确认：**物品弯段与管道弯段分开计算**
    （它们是两张独立网络上的元件，各自成一种）。
    """

    CONVEYOR_STRAIGHT = "传送带直段"
    ITEM_CURVE = "物品弯段"
    ITEM_GATE = "物品准入口"
    ITEM_SPLITTER = "分流器"
    ITEM_MERGER = "汇流器"
    ITEM_BRIDGE = "物流桥"
    PIPE_STRAIGHT = "管道直段"
    PIPE_CURVE = "管道弯段"
    PIPE_GATE = "管道准入口"
    PIPE_SPLITTER = "管道分流器"
    PIPE_MERGER = "管道汇流器"
    PIPE_BRIDGE = "管道桥"

    @property
    def family(self) -> NetworkFamily:
        """物品网或管道网；由名字前缀决定（``管道`` / ``传送带`` / ``物品`` 归物品网）。"""
        return "fluid" if self.value.startswith("管道") else "item"

    @property
    def is_bridge(self) -> bool:
        return self in (LogisticsElementType.ITEM_BRIDGE, LogisticsElementType.PIPE_BRIDGE)

    @property
    def is_gate(self) -> bool:
        """准入口：可标记物品/流体并限速（R-016 / R-024）。"""
        return self in (LogisticsElementType.ITEM_GATE, LogisticsElementType.PIPE_GATE)

    @property
    def max_rate_per_minute(self) -> int:
        """R-012 / R-020：传送带族 30/min、管道族 120/min。"""
        return 120 if self.family == "fluid" else 30

    @property
    def speed_step_per_minute(self) -> int:
        """R-016 步长 6/min（0~30 闭合）；R-024 步长 6/min（0~60 闭合）。"""
        return 6


@dataclass(frozen=True)
class PortSpec:
    """物流元件的一个端口：面 + 该面上的格 + 语义。"""

    face: Face
    ordinal: int
    direction: PortDirection
    role: PortRole
    local_cell: tuple[int, int]
    material_kind: MaterialKind

    def rotated(self, rotation: Rotation) -> "PortSpec":
        cx, cy = rotate_local_cell(self.local_cell[0], self.local_cell[1], 1, 1, rotation)
        return PortSpec(
            face=self.face.rotated(rotation),
            ordinal=self.ordinal,
            direction=self.direction,
            role=self.role,
            local_cell=(cx, cy),
            material_kind=self.material_kind,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "face": self.face.value,
            "faceSymbol": self.face.symbol,
            "ordinal": self.ordinal,
            "direction": self.direction,
            "role": self.role,
            "localCell": {"x": self.local_cell[0], "y": self.local_cell[1]},
            "materialKind": self.material_kind,
        }


#: 基准朝向（``rotation = 0``）的端口定义。
#: 局部格口径与设备一致：``local_cell = (rotate 前 cx, cy)``，单格元件恒为 ``(0, 0)``。
#: 面顺序沿用已确认的排列方向（北东→西、南西→东、西→南、东南→北）。
BASE_PORT_SPECS: Mapping[LogisticsElementType, tuple[PortSpec, ...]] = {
    LogisticsElementType.CONVEYOR_STRAIGHT: (
        PortSpec(Face.WEST, 1, "in", "input", (0, 0), _ITEM),
        PortSpec(Face.EAST, 1, "out", "output", (0, 0), _ITEM),
    ),
    LogisticsElementType.ITEM_CURVE: (
        PortSpec(Face.WEST, 1, "in", "input", (0, 0), _ITEM),
        PortSpec(Face.NORTH, 1, "out", "output", (0, 0), _ITEM),
    ),
    LogisticsElementType.ITEM_GATE: (
        PortSpec(Face.WEST, 1, "in", "filtered-input", (0, 0), _ITEM),
        PortSpec(Face.EAST, 1, "out", "filtered-output", (0, 0), _ITEM),
    ),
    LogisticsElementType.ITEM_SPLITTER: (
        PortSpec(Face.WEST, 1, "in", "input", (0, 0), _ITEM),
        PortSpec(Face.EAST, 1, "out", "branch", (0, 0), _ITEM),
        PortSpec(Face.NORTH, 1, "out", "branch", (0, 0), _ITEM),
        PortSpec(Face.SOUTH, 1, "out", "branch", (0, 0), _ITEM),
    ),
    LogisticsElementType.ITEM_MERGER: (
        PortSpec(Face.EAST, 1, "out", "output", (0, 0), _ITEM),
        PortSpec(Face.WEST, 1, "in", "merge", (0, 0), _ITEM),
        PortSpec(Face.NORTH, 1, "in", "merge", (0, 0), _ITEM),
        PortSpec(Face.SOUTH, 1, "in", "merge", (0, 0), _ITEM),
    ),
    LogisticsElementType.ITEM_BRIDGE: (
        PortSpec(Face.WEST, 1, "in", "pass-through", (0, 0), _ITEM),
        PortSpec(Face.EAST, 1, "out", "pass-through", (0, 0), _ITEM),
        PortSpec(Face.SOUTH, 2, "in", "pass-through", (0, 0), _ITEM),
        PortSpec(Face.NORTH, 2, "out", "pass-through", (0, 0), _ITEM),
    ),
    LogisticsElementType.PIPE_STRAIGHT: (
        PortSpec(Face.WEST, 1, "in", "input", (0, 0), _FLUID),
        PortSpec(Face.EAST, 1, "out", "output", (0, 0), _FLUID),
    ),
    LogisticsElementType.PIPE_CURVE: (
        PortSpec(Face.WEST, 1, "in", "input", (0, 0), _FLUID),
        PortSpec(Face.NORTH, 1, "out", "output", (0, 0), _FLUID),
    ),
    LogisticsElementType.PIPE_GATE: (
        PortSpec(Face.WEST, 1, "in", "filtered-input", (0, 0), _FLUID),
        PortSpec(Face.EAST, 1, "out", "filtered-output", (0, 0), _FLUID),
    ),
    LogisticsElementType.PIPE_SPLITTER: (
        PortSpec(Face.WEST, 1, "in", "input", (0, 0), _FLUID),
        PortSpec(Face.EAST, 1, "out", "branch", (0, 0), _FLUID),
        PortSpec(Face.NORTH, 1, "out", "branch", (0, 0), _FLUID),
        PortSpec(Face.SOUTH, 1, "out", "branch", (0, 0), _FLUID),
    ),
    LogisticsElementType.PIPE_MERGER: (
        PortSpec(Face.EAST, 1, "out", "output", (0, 0), _FLUID),
        PortSpec(Face.WEST, 1, "in", "merge", (0, 0), _FLUID),
        PortSpec(Face.NORTH, 1, "in", "merge", (0, 0), _FLUID),
        PortSpec(Face.SOUTH, 1, "in", "merge", (0, 0), _FLUID),
    ),
    LogisticsElementType.PIPE_BRIDGE: (
        PortSpec(Face.WEST, 1, "in", "pass-through", (0, 0), _FLUID),
        PortSpec(Face.EAST, 1, "out", "pass-through", (0, 0), _FLUID),
        PortSpec(Face.SOUTH, 2, "in", "pass-through", (0, 0), _FLUID),
        PortSpec(Face.NORTH, 2, "out", "pass-through", (0, 0), _FLUID),
    ),
}

#: 桥的两条正交线：水平线（西↔东）与垂直线（南↔北）。
BRIDGE_LINE_PAIRS: tuple[tuple[Face, Face], ...] = ((Face.WEST, Face.EAST), (Face.SOUTH, Face.NORTH))


@dataclass(frozen=True)
class LogisticsElement:
    """物流元件实例：类型 + 位置 + 旋转。"""

    id: str
    element_type: LogisticsElementType
    position: Cell
    rotation: Rotation = Rotation.DEG_0
    item_filter: str | None = None
    speed_limit_per_minute: int | None = None

    @property
    def rect(self) -> GridRect:
        return GridRect(self.position.x, self.position.y, LOGISTICS_FOOTPRINT, LOGISTICS_FOOTPRINT)

    @property
    def ports(self) -> tuple[Port, ...]:
        """按当前旋转实例化的端口（``local_cell`` 为 1×1 内的格，恒为 ``(0, 0)``）。"""
        specs = BASE_PORT_SPECS[self.element_type]
        if self.rotation is Rotation.DEG_0:
            rotated_specs = specs
        else:
            rotated_specs = tuple(spec.rotated(self.rotation) for spec in specs)
        return tuple(
            Port(
                face=spec.face,
                ordinal=spec.ordinal,
                marker=_marker_for(spec),
                local_cell=spec.local_cell,
                direction=spec.direction,
                material_kind=spec.material_kind,
                role=spec.role,
                item_filter=self.item_filter if spec.role.startswith("filtered") else None,
            )
            for spec in rotated_specs
        )

    @property
    def port_count(self) -> int:
        return len(BASE_PORT_SPECS[self.element_type])

    @property
    def speed_limit_upper_bound(self) -> int:
        """R-016 / R-024 的限速上限：物品准入口 30/min、管道准入口 60/min。"""
        if self.element_type is LogisticsElementType.ITEM_GATE:
            return 30
        if self.element_type is LogisticsElementType.PIPE_GATE:
            return 60
        return self.element_type.max_rate_per_minute

    def validate(self) -> list[str]:
        """本元件自身的合法性（不含与其他元件/设备的几何判定）。"""
        problems: list[str] = []
        if self.speed_limit_per_minute is not None:
            if not 0 <= self.speed_limit_per_minute <= self.speed_limit_upper_bound:
                problems.append(
                    f"{self.element_type.value}: 限速 {self.speed_limit_per_minute} 超出 0~{self.speed_limit_upper_bound}/min"
                )
            elif self.speed_limit_per_minute % self.element_type.speed_step_per_minute:
                problems.append(
                    f"{self.element_type.value}: 限速 {self.speed_limit_per_minute} 不是 {self.element_type.speed_step_per_minute}/min 的整数倍"
                )
        if self.element_type.is_gate and self.item_filter is None:
            problems.append(f"{self.element_type.value}: 准入口必须标记一种物品/流体（R-016 / R-024）")
        if not self.element_type.is_gate and self.speed_limit_per_minute is not None:
            problems.append(f"{self.element_type.value}: 只有准入口可以限速")
        return problems

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "elementType": self.element_type.value,
            "family": self.element_type.family,
            "position": {"x": self.position.x, "y": self.position.y},
            "rotation": self.rotation.degrees,
            "footprint": {"width": LOGISTICS_FOOTPRINT, "height": LOGISTICS_FOOTPRINT},
            "ports": [port.as_dict() for port in self.ports],
            "itemFilter": self.item_filter,
            "speedLimitPerMinute": self.speed_limit_per_minute,
            "maxRatePerMinute": self.element_type.max_rate_per_minute,
        }


def _marker_for(spec: PortSpec) -> str:
    """物流元件的端口标记（沿用七种标记体系）：物品用 ``si``/``so``、流体用 ``fi``/``fo``。"""
    prefix = "s" if spec.material_kind == "solid" else "f"
    if spec.direction == "in":
        return prefix + "i"
    if spec.direction == "out":
        return prefix + "o"
    return "n"


def base_ports(element_type: LogisticsElementType) -> tuple[PortSpec, ...]:
    return BASE_PORT_SPECS[element_type]


def all_element_types() -> tuple[LogisticsElementType, ...]:
    return tuple(LogisticsElementType)
