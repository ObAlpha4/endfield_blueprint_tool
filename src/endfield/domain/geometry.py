"""几何值对象：方向、整数格、矩形、旋转。

依据 ``design/global-constraints.md``（G-001）与 ``design/domain-model.md`` §6.1：

- 所有对象的坐标原点都是**自身左下角**，``position`` 为整数格坐标；
- 设备边缘严格位于整数坐标的格线上、顶点严格位于整数坐标上；
- 只允许**顺时针** 0 / 90 / 180 / 270 度，**禁止镜像**；
- 旋转锚点为左下角，旋转只交换宽高，不产生半格偏移。

坐标口径（``design/coverage-geometry.md`` §2.1）：``x`` 向右增、``y`` 向上增，
格 ``(i, j)`` 占据平面区域 ``[i, i+1] × [j, j+1]``。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Iterator

#: 未旋转时每个面朝向的基地坐标轴方向：北 +y、南 −y、西 −x、东 +x。
DIRECTION_VECTORS: dict[str, tuple[int, int]] = {
    "NORTH": (0, 1),
    "EAST": (1, 0),
    "SOUTH": (0, -1),
    "WEST": (-1, 0),
}


class Direction(Enum):
    """设备侧面的朝向（基地坐标系）。顺时针顺序：北 → 东 → 南 → 西。"""

    NORTH = "NORTH"
    EAST = "EAST"
    SOUTH = "SOUTH"
    WEST = "WEST"

    @property
    def vector(self) -> tuple[int, int]:
        """该朝向的单位向量（基地坐标系，y 向上）。"""
        return DIRECTION_VECTORS[self.value]

    @property
    def opposite(self) -> "Direction":
        return self.rotated(2)

    def rotated(self, steps: int) -> "Direction":
        """顺时针旋转 ``steps`` 个 90 度。"""
        order = (Direction.NORTH, Direction.EAST, Direction.SOUTH, Direction.WEST)
        return order[(order.index(self) + steps) % 4]

    def rotated_by(self, rotation: "Rotation") -> "Direction":
        return self.rotated(rotation.quarter_turns)


class Rotation(Enum):
    """顺时针旋转角度。只允许 0 / 90 / 180 / 270，禁止镜像。"""

    DEG_0 = 0
    DEG_90 = 90
    DEG_180 = 180
    DEG_270 = 270

    @property
    def degrees(self) -> int:
        return self.value

    @property
    def quarter_turns(self) -> int:
        """顺时针 90 度的个数（0..3）。"""
        return self.value // 90

    @classmethod
    def of(cls, degrees: int) -> "Rotation":
        try:
            return cls(degrees)
        except ValueError as exc:  # pragma: no cover - 防御性分支
            raise ValueError(f"旋转只能是 0/90/180/270 度，收到 {degrees!r}") from exc


@dataclass(frozen=True, order=True)
class Cell:
    """一个整数格，坐标为其左下角顶点。"""

    x: int
    y: int

    def __post_init__(self) -> None:
        if not isinstance(self.x, int) or not isinstance(self.y, int):
            raise TypeError(f"格坐标必须是整数（G-001）：{self!r}")

    def offset(self, dx: int, dy: int) -> "Cell":
        return Cell(self.x + dx, self.y + dy)

    def step(self, direction: Direction) -> "Cell":
        dx, dy = direction.vector
        return Cell(self.x + dx, self.y + dy)

    def neighbors4(self) -> Iterator["Cell"]:
        for direction in Direction:
            yield self.step(direction)

    def is_adjacent_to(self, other: "Cell") -> bool:
        return abs(self.x - other.x) + abs(self.y - other.y) == 1


@dataclass(frozen=True)
class GridRect:
    """整数格矩形（含左下角起点、宽、高），对应一个设备 / 覆盖范围的占地。"""

    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        for field_name in ("x", "y", "width", "height"):
            value = getattr(self, field_name)
            if not isinstance(value, int):
                raise TypeError(f"{field_name} 必须是整数（G-001）：{value!r}")
        if self.width <= 0 or self.height <= 0:
            raise ValueError(f"宽高必须为正：{self!r}")

    @property
    def origin(self) -> Cell:
        return Cell(self.x, self.y)

    @property
    def width_units(self) -> int:
        return self.width

    def cells(self) -> frozenset[Cell]:
        """占地的整数格集合（格数 = 宽 × 高）。"""
        return frozenset(
            Cell(self.x + dx, self.y + dy)
            for dx in range(self.width)
            for dy in range(self.height)
        )

    def contains_cell(self, cell: Cell) -> bool:
        return self.x <= cell.x < self.x + self.width and self.y <= cell.y < self.y + self.height

    def contains_rect(self, other: "GridRect") -> bool:
        return (
            self.x <= other.x
            and self.y <= other.y
            and other.x + other.width <= self.x + self.width
            and other.y + other.height <= self.y + self.height
        )

    def overlaps(self, other: "GridRect") -> bool:
        """整数格集合相交（不是几何面积的相交）。"""
        return not self.cells().isdisjoint(other.cells())

    def is_edge_adjacent_to(self, other: "GridRect") -> bool:
        """边贴边：沿一条边接触且不重叠。"""
        return self.shared_edge_length(other) > 0

    def shared_edge_length(self, other: "GridRect") -> int:
        """共享边的**格数**；不共享边（含角点相触、有间隙、重叠）时为 0。

        用于 R-004 / R-005 的「连接 = 边贴边且共同长度 > 0」判定
        （见 ``design/logistics-and-storage-geometry.md`` §2.2）：两个设备「相连」当且仅当
        占地矩形**边贴边**（沿一条边接触、不重叠），且该边上的共同长度 > 0。
        """
        if self.overlaps(other):
            return 0
        span_x = min(self.x + self.width, other.x + other.width) - max(self.x, other.x)
        span_y = min(self.y + self.height, other.y + other.height) - max(self.y, other.y)
        # 左右相贴：x 方向正好衔接，共同长度取 y 方向的重叠格数。
        if self.x + self.width == other.x or other.x + other.width == self.x:
            return max(span_y, 0)
        # 上下相贴：y 方向正好衔接，共同长度取 x 方向的重叠格数。
        if self.y + self.height == other.y or other.y + other.height == self.y:
            return max(span_x, 0)
        return 0

    def intersects_edge_of(self, other: "GridRect") -> bool:
        """是否与另一矩形共享一条完整的格边界线（相切，格集合不相交）。"""
        return self.shared_edge_length(other) > 0

    def rotated(self, rotation: Rotation, pivot: Cell | None = None) -> "GridRect":
        """绕锚点（默认自身左下角）顺时针旋转，返回新的占地矩形。

        已确认口径（``design/global-constraints.md`` G-001.5 方案 A）：**旋转锚点为左下角**，
        旋转只交换宽高，不产生半格偏移。因此旋转后的矩形仍然是
        「左下角落在锚点上、宽高互换」的那个矩形——等价于把旋转结果平移回锚点。
        """
        anchor = pivot or self.origin
        if rotation is Rotation.DEG_0:
            return self
        rotated_cells = {rotate_cell(cell, rotation, anchor) for cell in self.cells()}
        bounding = GridRect.from_cells(rotated_cells)
        dx = anchor.x - bounding.x
        dy = anchor.y - bounding.y
        return GridRect(anchor.x, anchor.y, bounding.width, bounding.height) if (dx or dy) else bounding

    @classmethod
    def from_cells(cls, cells: Iterable[Cell]) -> "GridRect":
        cell_set = list(cells)
        if not cell_set:
            raise ValueError("空格集合无法构成矩形")
        x0 = min(c.x for c in cell_set)
        y0 = min(c.y for c in cell_set)
        x1 = max(c.x for c in cell_set)
        y1 = max(c.y for c in cell_set)
        rect = cls(x0, y0, x1 - x0 + 1, y1 - y0 + 1)
        if rect.cells() != frozenset(cell_set):
            raise ValueError("格集合不是完整的整数格矩形")
        return rect

    @classmethod
    def of_size(cls, origin: Cell, width: int, height: int) -> "GridRect":
        return cls(origin.x, origin.y, width, height)

    def as_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


def rotate_cell(cell: Cell, rotation: Rotation, anchor: Cell) -> Cell:
    """以 ``anchor`` 为锚点，把格 ``cell`` 顺时针旋转 ``rotation``。"""
    if rotation is Rotation.DEG_0:
        return cell
    dx = cell.x - anchor.x
    dy = cell.y - anchor.y
    if rotation is Rotation.DEG_90:
        nx, ny = dy, -dx
    elif rotation is Rotation.DEG_180:
        nx, ny = -dx, -dy
    else:  # DEG_270
        nx, ny = -dy, dx
    return Cell(anchor.x + nx, anchor.y + ny)


def rotate_local_cell(cx: int, cy: int, width: int, height: int, rotation: Rotation) -> tuple[int, int]:
    """把设备**局部格** ``(cx, cy)`` 顺时针旋转，返回新占地内的局部格。

    ``width`` / ``height`` 是**旋转前**的尺寸。旋转后宽高互换，公式为
    ``(cx, cy) → (cy, width - 1 - cx)``（见 ``design/domain-model.md`` §6.1 端口格映射）。
    """
    if rotation is Rotation.DEG_0:
        return cx, cy
    if rotation is Rotation.DEG_90:
        return cy, width - 1 - cx
    if rotation is Rotation.DEG_180:
        return width - 1 - cx, height - 1 - cy
    return height - 1 - cy, cx
