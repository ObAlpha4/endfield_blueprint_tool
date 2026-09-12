"""蓝图容器：``Blueprint`` / ``Module`` / ``StorageLine`` / ``PathSpec`` / ``ChainPlan``。

阶段 2 只定义**结构与字段**（``design/domain-model.md`` §6.2、§6.3）：

- 不做布局求解、不做布线算法、不做规则判定（步骤 4 的验证器负责）；
- ``ChainPlan`` 只作为第一部分（链路求解）与第二部分（蓝图搭建）之间的契约结构，
  本阶段**不实现求解**（步骤 3 才做）。

两条已定稿的口径在这里落实：

- **C-3**：``Blueprint.bounds`` 直接取基地矩形（主基地 80×80、副基地 50×50）；
- **C-4**：物流长度只算**连续段**，断开元件（准入口 / 分流器 / 汇流器 / 物流桥 / 管道桥）
  自身占格但**不计长**，按「连续段长度 ≤ 80」逐段校验。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction
from typing import Iterable, Mapping, Sequence

from endfield.domain.devices import DeviceInstance
from endfield.domain.geometry import Cell, GridRect, Rotation
from endfield.domain.logistics import LogisticsElement

#: C-4 / R-010 / R-020：物流最大长度（按连续段计）。
MAX_PATH_LENGTH: int = 80


class BaseType(Enum):
    """基地类型（C-3）。"""

    MAIN = "主基地"
    SECONDARY = "副基地"

    @property
    def size(self) -> tuple[int, int]:
        """C-3：主基地 80×80、副基地 50×50（坐标原点为基地左下角，边界闭合）。"""
        return (80, 80) if self is BaseType.MAIN else (50, 50)

    @property
    def base_segment_limit(self) -> int:
        """R-003：主基地最多 5 个基段、副基地最多 12 个基段。"""
        return 5 if self is BaseType.MAIN else 12

    @property
    def required_role(self) -> "BaseRole":
        return BaseRole.MAIN if self is BaseType.MAIN else BaseRole.SECONDARY


class BaseRole(Enum):
    """基地在整线中的角色（1 主基地 + 最多 3 副基地，共用电量基准 R-069）。"""

    MAIN = "主"
    SECONDARY = "副"


@dataclass(frozen=True)
class PathSpec:
    """一条物流路径：连续段 + 断开元件，用于 C-4 的逐段计长。

    ``breakpoints`` 是 ``{段索引: 断开元件}``：断开元件接在**该索引的连续段之后**，
    元件自身占 1 格但**不计入长度**（C-4 / R-016 / R-024 / R-013 / R-014）。
    """

    id: str
    family: str  # "item"（传送带族）或 "fluid"（管道族）
    segments: tuple[Cell, ...] = ()
    breakpoints: Mapping[int, LogisticsElement] = field(default_factory=dict)
    source_ref: Mapping[str, object] | None = None

    def continuous_runs(self) -> list[tuple[Cell, ...]]:
        """把路径切成被断开元件隔开的**连续段**（断开元件自身不计长）。"""
        runs: list[tuple[Cell, ...]] = []
        current: list[Cell] = []
        for index, segment in enumerate(self.segments):
            current.append(segment)
            if index in self.breakpoints:
                runs.append(tuple(current))
                current = []
        if current:
            runs.append(tuple(current))
        return runs

    def run_lengths(self) -> list[int]:
        return [len(run) for run in self.continuous_runs()]

    def overloaded_runs(self) -> list[int]:
        """超过 80 的连续段长度（空表示合法）。"""
        return [length for length in self.run_lengths() if length > MAX_PATH_LENGTH]

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "family": self.family,
            "segments": [{"x": cell.x, "y": cell.y} for cell in self.segments],
            "breakpoints": [
                {"segmentIndex": index, **element.as_dict()}
                for index, element in sorted(self.breakpoints.items())
            ],
            "continuousRunLengths": self.run_lengths(),
            "maxPathLength": MAX_PATH_LENGTH,
        }


@dataclass(frozen=True)
class Module:
    """可复用的生产模块（步骤 5 才生成，本阶段只定义接口）。"""

    id: str
    name: str
    device_instances: tuple[DeviceInstance, ...] = ()
    input_ports: tuple[str, ...] = ()
    output_ports: tuple[str, ...] = ()
    power_demand_kw: Fraction = Fraction(0)
    environment_requirements: tuple[str, ...] = ()
    source_refs: tuple[Mapping[str, object], ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "deviceInstances": [instance.as_dict() for instance in self.device_instances],
            "inputPorts": list(self.input_ports),
            "outputPorts": list(self.output_ports),
            "powerDemandKw": float(self.power_demand_kw),
            "environmentRequirements": list(self.environment_requirements),
            "sourceRefs": [dict(ref) for ref in self.source_refs],
        }


@dataclass(frozen=True)
class ExternalInterface:
    """外部接口：起始产物边界（§1A）与 R-001 外部资源。

    ``kind``：
    ``pickup``（仓库取货口，30/min/口，R-007）、
    ``return``（仓库存货口，30/min，R-008）、
    ``pump``（水泵，清水/沉积酸）、
    ``gas_collector``（气体收集泵，惰气/息壤气）、
    ``sewage``（净水节点暗管接口，R-053）。
    """

    id: str
    kind: str
    item: str | None = None
    position: Cell | None = None
    rotation: Rotation = Rotation.DEG_0
    rate_limit_per_minute: Fraction = Fraction(30)
    note: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind,
            "item": self.item,
            "position": {"x": self.position.x, "y": self.position.y} if self.position else None,
            "rotation": self.rotation.degrees,
            "rateLimitPerMinute": float(self.rate_limit_per_minute),
            "note": self.note,
        }


@dataclass(frozen=True)
class StorageLine:
    """仓储存取骨架（R-002~R-008、B-10）。"""

    id: str
    base_type: BaseType
    source_piles: tuple[Cell, ...] = ()
    segments: tuple[Cell, ...] = ()
    pickup_ports: tuple[Mapping[str, object], ...] = ()
    return_ports: tuple[Mapping[str, object], ...] = ()
    protocol_core_id: str | None = None
    protocol_storage_ids: tuple[str, ...] = ()
    source_refs: tuple[Mapping[str, object], ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "baseType": self.base_type.value,
            "sourcePiles": [{"x": cell.x, "y": cell.y} for cell in self.source_piles],
            "segments": [{"x": cell.x, "y": cell.y} for cell in self.segments],
            "pickupPorts": [dict(port) for port in self.pickup_ports],
            "returnPorts": [dict(port) for port in self.return_ports],
            "protocolCoreId": self.protocol_core_id,
            "protocolStorageIds": list(self.protocol_storage_ids),
            "sourceRefs": [dict(ref) for ref in self.source_refs],
        }


@dataclass
class Blueprint:
    """蓝图领域容器。``bounds`` 即基地矩形（C-3），坐标原点为基地左下角。"""

    id: str
    base_type: BaseType
    device_instances: list[DeviceInstance] = field(default_factory=list)
    modules: list[Module] = field(default_factory=list)
    paths: list[PathSpec] = field(default_factory=list)
    power_poles: list[Mapping[str, object]] = field(default_factory=list)
    gas_diffusers: list[Mapping[str, object]] = field(default_factory=list)
    storage_line: StorageLine | None = None
    external_interfaces: list[ExternalInterface] = field(default_factory=list)
    rule_refs: list[str] = field(default_factory=list)
    source_refs: list[Mapping[str, object]] = field(default_factory=list)

    @property
    def bounds(self) -> GridRect:
        width, height = self.base_type.size
        return GridRect(0, 0, width, height)

    @property
    def origin(self) -> Cell:
        return Cell(0, 0)

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "baseType": self.base_type.value,
            "bounds": self.bounds.as_dict(),
            "origin": {"x": self.origin.x, "y": self.origin.y},
            "deviceInstances": [instance.as_dict() for instance in self.device_instances],
            "modules": [module.as_dict() for module in self.modules],
            "paths": [path.as_dict() for path in self.paths],
            "powerPoles": [dict(pole) for pole in self.power_poles],
            "gasDiffusers": [dict(diffuser) for diffuser in self.gas_diffusers],
            "storageLine": self.storage_line.as_dict() if self.storage_line else None,
            "externalInterfaces": [interface.as_dict() for interface in self.external_interfaces],
            "ruleRefs": list(self.rule_refs),
            "sourceRefs": [dict(ref) for ref in self.source_refs],
        }


@dataclass
class ChainPlan:
    """第一部分（链路求解）与第二部分（蓝图搭建）之间的契约。

    本阶段**只定义结构**，求解在步骤 3 实现。字段见 ``design/domain-model.md`` §6.2。
    """

    target_product: str
    target_rate_per_minute: Fraction
    start_products: tuple[str, ...] = ()
    recipe_usage: list[Mapping[str, object]] = field(default_factory=list)
    material_balance: list[Mapping[str, object]] = field(default_factory=list)
    catalyst_totals: list[Mapping[str, object]] = field(default_factory=list)
    external_inputs: list[Mapping[str, object]] = field(default_factory=list)
    external_outputs: list[Mapping[str, object]] = field(default_factory=list)
    waste_edges: list[Mapping[str, object]] = field(default_factory=list)
    edges: list[Mapping[str, object]] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "targetProduct": self.target_product,
            "targetRatePerMinute": float(self.target_rate_per_minute),
            "startProducts": list(self.start_products),
            "recipeUsage": [dict(row) for row in self.recipe_usage],
            "materialBalance": [dict(row) for row in self.material_balance],
            "catalystTotals": [dict(row) for row in self.catalyst_totals],
            "externalInputs": [dict(row) for row in self.external_inputs],
            "externalOutputs": [dict(row) for row in self.external_outputs],
            "wasteEdges": [dict(row) for row in self.waste_edges],
            "edges": [dict(row) for row in self.edges],
        }


def total_power_kw(instances: Iterable[DeviceInstance], power_by_type: Mapping[str, float]) -> float:
    """设备总耗电（瞬时功率，``design/baseline-rules.md`` A-5）。"""
    return sum(power_by_type.get(instance.device_type_id, 0.0) for instance in instances)


def elements_in_order(elements: Sequence[LogisticsElement]) -> tuple[LogisticsElement, ...]:
    """按坐标稳定排序，便于确定性输出。"""
    return tuple(sorted(elements, key=lambda element: (element.position.x, element.position.y, element.element_type.value)))
