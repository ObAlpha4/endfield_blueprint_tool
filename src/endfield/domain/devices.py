"""设备与端口模型：``Marker`` / ``Face`` / ``Port`` / ``DeviceType`` / ``DeviceInstance``。

字段依据 ``design/domain-model.md`` §2、§3、§6.1、§6.2；端口格映射与面内排列方向依据
``design/baseline-rules.md`` §1.2：

- 面内标记排列方向：**北面东→西、南面西→东、西面北→南、东面南→北**，``ordinal`` 从 1 起；
- 未旋转局部格映射：北 ``(w-ordinal, h-1)``、南 ``(ordinal-1, 0)``、
  西 ``(0, h-ordinal)``、东 ``(w-1, ordinal-1)``；
- 每个出入口**占用完整网格格子**，不是边界上的点。

``协议核心`` 在本模型中按**特殊设备**处理：它有权威规格与端口，但不进蓝图设备列表
（``Blueprint.deviceInstances``），只出现在基地骨架里；每个基地必须有且只能有 1 个（R-006）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Literal, Mapping

from endfield.domain.geometry import Cell, Direction, GridRect, Rotation, rotate_local_cell

#: 源表四面接口串的列字母（内容决定）：北、南、西、东。
SOURCE_FACE_COLUMNS: tuple[str, ...] = ("D", "E", "F", "G")

#: 七种接口标记（``docs/设备概述.xlsx`` 的 ``标记对照`` 表）。
VALID_MARKERS: frozenset[str] = frozenset({"si", "so", "fi", "fo", "gi", "go", "n"})

PortDirection = Literal["in", "out", "none"]
MaterialKind = Literal["solid", "liquid", "gas", "none"]
PortRole = Literal[
    "input",
    "output",
    "filtered-input",
    "filtered-output",
    "branch",
    "merge",
    "pass-through",
    "none",
]

#: 端口在基地坐标系中的朝向（North/South 沿宽度、West/East 沿高度）。
FACE_DIRECTIONS: dict[str, Direction] = {
    "NORTH": Direction.NORTH,
    "SOUTH": Direction.SOUTH,
    "WEST": Direction.WEST,
    "EAST": Direction.EAST,
}

#: 端口局部格坐标的面内起点方向（沿该轴递增时 ``ordinal`` 增大）。
#: 北面东→西意味着 ordinal 越大 x 越小；南面西→东反之。
FACE_ORDINAL_AXIS: dict[str, str] = {
    "NORTH": "x-desc",
    "SOUTH": "x-asc",
    "WEST": "y-desc",
    "EAST": "y-asc",
}


class Face(Enum):
    """设备朝向面。枚举名与基地坐标系方向一致（未旋转时北面朝 +y）。"""

    NORTH = "NORTH"
    SOUTH = "SOUTH"
    WEST = "WEST"
    EAST = "EAST"

    @classmethod
    def from_column(cls, column: str) -> "Face":
        """源表列字母 → 面：``D=北``、``E=南``、``F=西``、``G=东``。"""
        return _FACE_BY_COLUMN[column.upper()]

    @classmethod
    def from_symbol(cls, symbol: str) -> "Face":
        """``N`` / ``S`` / ``W`` / ``E`` → 面。"""
        return _FACE_BY_SYMBOL[symbol.upper()]

    @property
    def direction(self) -> Direction:
        return FACE_DIRECTIONS[self.value]

    @property
    def opposite(self) -> "Face":
        return Face(self.direction.opposite.value)

    def rotated(self, rotation: Rotation) -> "Face":
        return Face(self.direction.rotated_by(rotation).value)

    @property
    def symbol(self) -> str:
        return {"NORTH": "N", "SOUTH": "S", "WEST": "W", "EAST": "E"}[self.value]


_FACE_BY_COLUMN: dict[str, Face] = dict(zip(SOURCE_FACE_COLUMNS, (Face.NORTH, Face.SOUTH, Face.WEST, Face.EAST)))
_FACE_BY_SYMBOL: dict[str, Face] = {face.symbol: face for face in Face}


@dataclass(frozen=True)
class Port:
    """已解析的接口标记（一个出入口占一个完整格子）。"""

    face: Face
    ordinal: int
    marker: str
    local_cell: tuple[int, int]
    direction: PortDirection
    material_kind: MaterialKind
    role: PortRole = "none"
    item_filter: str | None = None

    @property
    def is_io(self) -> bool:
        return self.direction != "none"

    def global_cell(self, origin: Cell, rotation: Rotation, width: int, height: int) -> Cell:
        """把端口格映射到基地坐标（``origin`` 为设备左下角，``width``/``height`` 为**未旋转**尺寸）。"""
        cx, cy = rotate_local_cell(self.local_cell[0], self.local_cell[1], width, height, rotation)
        return Cell(origin.x + cx, origin.y + cy)

    def global_face(self, rotation: Rotation) -> Face:
        return self.face.rotated(rotation)

    def as_dict(self) -> dict[str, object]:
        return {
            "face": self.face.value,
            "faceSymbol": self.face.symbol,
            "ordinal": self.ordinal,
            "marker": self.marker,
            "localCell": {"x": self.local_cell[0], "y": self.local_cell[1]},
            "direction": self.direction,
            "materialKind": self.material_kind,
            "role": self.role,
            "itemFilter": self.item_filter,
        }


@dataclass(frozen=True)
class DeviceSource:
    """一条设备规格的来源位置（原始值 / 规范值 / 来源行号三列分立）。"""

    file: str
    sheet: str
    row: int
    columns: Mapping[str, str]

    def as_dict(self) -> dict[str, object]:
        return {
            "file": self.file,
            "sheet": self.sheet,
            "row": self.row,
            "columns": dict(self.columns),
        }


@dataclass(frozen=True)
class DeviceType:
    """设备类型（``docs/设备概述.xlsx`` 的一行 + 规则文档给出的类别）。"""

    id: str
    raw_name: str
    canonical_name: str
    width: int
    height: int
    raw_faces: Mapping[str, str]
    ports: tuple[Port, ...]
    power_kw: float
    category: str
    source: DeviceSource | None = None
    special: bool = False
    notes: tuple[str, ...] = ()

    @property
    def io_ports(self) -> tuple[Port, ...]:
        return tuple(port for port in self.ports if port.is_io)

    @property
    def input_ports(self) -> tuple[Port, ...]:
        return tuple(port for port in self.ports if port.direction == "in")

    @property
    def output_ports(self) -> tuple[Port, ...]:
        return tuple(port for port in self.ports if port.direction == "out")

    def ports_on(self, face: Face) -> tuple[Port, ...]:
        return tuple(port for port in self.ports if port.face is face)

    def rect_at(self, origin: Cell, rotation: Rotation = Rotation.DEG_0) -> GridRect:
        """该设备在给定位置 / 旋转下的占地矩形。"""
        if rotation is Rotation.DEG_90 or rotation is Rotation.DEG_270:
            return GridRect(origin.x, origin.y, self.height, self.width)
        return GridRect(origin.x, origin.y, self.width, self.height)

    def port_global_cell(self, port: Port, origin: Cell, rotation: Rotation = Rotation.DEG_0) -> Cell:
        return port.global_cell(origin, rotation, self.width, self.height)

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "rawName": self.raw_name,
            "canonicalName": self.canonical_name,
            "width": self.width,
            "height": self.height,
            "rawFaces": dict(self.raw_faces),
            "ports": [port.as_dict() for port in self.ports],
            "powerKw": self.power_kw,
            "category": self.category,
            "special": self.special,
            "notes": list(self.notes),
            "source": self.source.as_dict() if self.source else None,
        }


@dataclass(frozen=True)
class DeviceInstance:
    """蓝图中的设备实例。"""

    id: str
    device_type_id: str
    position: Cell
    rotation: Rotation = Rotation.DEG_0
    recipe_id: str | None = None
    tags: tuple[str, ...] = ()
    module_id: str | None = None
    power_required_kw: float = 0.0
    source_ref: Mapping[str, object] | None = None

    def rect(self, device_type: DeviceType) -> GridRect:
        return device_type.rect_at(self.position, self.rotation)

    def port_global_cell(self, port: Port, device_type: DeviceType) -> Cell:
        return device_type.port_global_cell(port, self.position, self.rotation)

    def local_cell_of(self, cell: Cell) -> tuple[int, int]:
        """把基地坐标格换算成**未旋转**局部格坐标。"""
        return cell.x - self.position.x, cell.y - self.position.y

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "deviceTypeId": self.device_type_id,
            "position": {"x": self.position.x, "y": self.position.y},
            "rotation": self.rotation.degrees,
            "recipeId": self.recipe_id,
            "tags": list(self.tags),
            "moduleId": self.module_id,
            "powerRequiredKw": self.power_required_kw,
            "sourceRef": dict(self.source_ref) if self.source_ref else None,
        }


def marker_direction(marker: str) -> PortDirection:
    if marker == "n":
        return "none"
    return "in" if marker.endswith("i") else "out"


def marker_material_kind(marker: str) -> MaterialKind:
    if marker == "n":
        return "none"
    return {"s": "solid", "f": "liquid", "g": "gas"}[marker[0]]


def build_ports(width: int, height: int, face_strings: Mapping[str, str]) -> tuple[Port, ...]:
    """解析四面接口串为 ``Port`` 列表，并断言「分词格数 = 宽/高」。

    ``face_strings`` 的键为 ``NORTH`` / ``SOUTH`` / ``WEST`` / ``EAST``；
    北/南沿宽度展开，西/东沿高度展开。
    """
    ports: list[Port] = []
    expectations = {"NORTH": width, "SOUTH": width, "WEST": height, "EAST": height}
    for face_name, expected in expectations.items():
        raw = face_strings.get(face_name, "")
        tokens = tokenize_port_string(raw)
        if len(tokens) != expected:
            raise ValueError(
                f"{face_name} 面接口串 {raw!r} 分词 {len(tokens)} 格，应为 {expected} 格"
            )
        face = Face(face_name)
        for index, marker in enumerate(tokens, start=1):
            if marker not in VALID_MARKERS:
                raise ValueError(f"{face_name} 面接口串 {raw!r} 含非法标记 {marker!r}")
            ports.append(
                Port(
                    face=face,
                    ordinal=index,
                    marker=marker,
                    local_cell=local_cell_for(face, index, width, height),
                    direction=marker_direction(marker),
                    material_kind=marker_material_kind(marker),
                )
            )
    return tuple(ports)


def local_cell_for(face: Face, ordinal: int, width: int, height: int) -> tuple[int, int]:
    """未旋转时端口格的局部坐标（``design/domain-model.md`` §6.1）。"""
    if face is Face.NORTH:
        return width - ordinal, height - 1
    if face is Face.SOUTH:
        return ordinal - 1, 0
    if face is Face.WEST:
        return 0, height - ordinal
    return width - 1, ordinal - 1


def tokenize_port_string(port_string: str) -> list[str]:
    """端口串分词：``n`` 占 1 字符，其余标记占 2 字符（与 ``sources.ooxml.tokenize`` 同义）。"""
    tokens: list[str] = []
    index = 0
    while index < len(port_string):
        if port_string[index] == "n":
            tokens.append("n")
            index += 1
        else:
            tokens.append(port_string[index : index + 2])
            index += 2
    return tokens


def face_capacity(port_string: str) -> int:
    """接口串的格数（= 该面的设备边长）。"""
    return len(tokenize_port_string(port_string))


def ports_to_grid(ports: Iterable[Port]) -> dict[tuple[int, int], Port]:
    """把端口按局部格坐标索引，便于「格 → 端口」查询。"""
    return {port.local_cell: port for port in ports}


def device_reference_columns() -> tuple[str, ...]:
    """设备表引用的列字母（用于来源标注）。"""
    return ("A", "B", "C", "D", "E", "F", "G", "H")
