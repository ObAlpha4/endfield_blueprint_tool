"""12 种物流元件：端口实例化与占格模型。

依据 ``design/global-constraints.md`` §2（B-9 收尾）：

- 全部 1×1（供电桩 2×2 是唯一例外，不属于物流元件）；
- **桥是 4 个端口**，让两条正交的线互不干扰地交叉；
- 直段 / 弯段 / 准入口 = 2 端口；分流器 / 汇流器 = 3 或 4 端口；
- 这 12 种元件不套用「北/南/西/东固定接口串」；
- 读数 = 规则段 2 的 10 种器件 + 物品弯段 + 管道弯段（用户确认：**两种弯段分开计算**）。
"""

from __future__ import annotations

import unittest

from endfield.domain.devices import Face
from endfield.domain.geometry import Cell, Rotation
from endfield.domain.logistics import (
    BASE_PORT_SPECS,
    BRIDGE_LINE_PAIRS,
    LOGISTICS_FOOTPRINT,
    LogisticsElement,
    LogisticsElementType,
)


class LogisticsElementTests(unittest.TestCase):
    def test_twelve_types(self) -> None:
        # 规则段 2 列出 10 种器件，加上物品弯段与管道弯段两种形态，共 12 种。
        expected = {
            "传送带直段",
            "物品弯段",
            "物品准入口",
            "分流器",
            "汇流器",
            "物流桥",
            "管道直段",
            "管道弯段",
            "管道准入口",
            "管道分流器",
            "管道汇流器",
            "管道桥",
        }
        names = {element.value for element in LogisticsElementType}
        self.assertEqual(names, expected)
        self.assertEqual(len(names), 12)
        self.assertEqual(len(LogisticsElementType), 12)

    def test_two_curve_types_are_counted_separately(self) -> None:
        # 用户确认：物品弯段与管道弯段分开计算，各自成一种元件。
        item_curve = LogisticsElementType.ITEM_CURVE
        pipe_curve = LogisticsElementType.PIPE_CURVE
        self.assertNotEqual(item_curve, pipe_curve)
        self.assertEqual(item_curve.family, "item")
        self.assertEqual(pipe_curve.family, "fluid")
        self.assertIn(item_curve, BASE_PORT_SPECS)
        self.assertIn(pipe_curve, BASE_PORT_SPECS)

    def test_footprint_is_one_by_one(self) -> None:
        self.assertEqual(LOGISTICS_FOOTPRINT, 1)
        for element_type in LogisticsElementType:
            element = LogisticsElement(id="e", element_type=element_type, position=Cell(3, 4))
            self.assertEqual(len(element.rect.cells()), 1)
            self.assertEqual(element.rect.cells(), {Cell(3, 4)})

    def test_port_counts_per_type(self) -> None:
        expected = {
            LogisticsElementType.CONVEYOR_STRAIGHT: 2,
            LogisticsElementType.ITEM_CURVE: 2,
            LogisticsElementType.ITEM_GATE: 2,
            LogisticsElementType.ITEM_SPLITTER: 4,
            LogisticsElementType.ITEM_MERGER: 4,
            LogisticsElementType.ITEM_BRIDGE: 4,
            LogisticsElementType.PIPE_STRAIGHT: 2,
            LogisticsElementType.PIPE_CURVE: 2,
            LogisticsElementType.PIPE_GATE: 2,
            LogisticsElementType.PIPE_SPLITTER: 4,
            LogisticsElementType.PIPE_MERGER: 4,
            LogisticsElementType.PIPE_BRIDGE: 4,
        }
        for element_type, count in expected.items():
            element = LogisticsElement(id="e", element_type=element_type, position=Cell(0, 0))
            self.assertEqual(element.port_count, count, element_type.value)
            self.assertEqual(len(element.ports), count, element_type.value)

    def test_bridge_has_four_ports_on_four_faces_and_two_orthogonal_lines(self) -> None:
        bridge = LogisticsElement(id="b", element_type=LogisticsElementType.ITEM_BRIDGE, position=Cell(0, 0))
        faces = {port.face for port in bridge.ports}
        self.assertEqual(faces, {Face.NORTH, Face.SOUTH, Face.WEST, Face.EAST})
        for first, second in BRIDGE_LINE_PAIRS:
            line = [port for port in bridge.ports if port.face in (first, second)]
            self.assertEqual(len(line), 2, f"桥的 {first}/{second} 线应占 2 口")
        # 两条线不共享流量：端口按面两两分组，互不重叠。
        self.assertEqual(len({id(port) for port in bridge.ports}), 4)

    def test_straight_uses_opposite_faces_curve_uses_adjacent(self) -> None:
        straight = LogisticsElement(id="s", element_type=LogisticsElementType.CONVEYOR_STRAIGHT, position=Cell(0, 0))
        self.assertEqual({port.face for port in straight.ports}, {Face.WEST, Face.EAST})
        for curve_type in (LogisticsElementType.ITEM_CURVE, LogisticsElementType.PIPE_CURVE):
            curve = LogisticsElement(id="c", element_type=curve_type, position=Cell(0, 0))
            faces = {port.face for port in curve.ports}
            self.assertEqual(len(faces), 2)
            self.assertNotEqual(faces, {Face.WEST, Face.EAST})
            self.assertNotEqual(faces, {Face.NORTH, Face.SOUTH})

    def test_curves_differ_only_by_network(self) -> None:
        # 两种弯段端口形态相同（西进北出），只有所属网络与材质不同。
        item_curve = LogisticsElement(id="c1", element_type=LogisticsElementType.ITEM_CURVE, position=Cell(0, 0))
        pipe_curve = LogisticsElement(id="c2", element_type=LogisticsElementType.PIPE_CURVE, position=Cell(0, 0))
        item_shape = [(port.face, port.direction, port.role) for port in item_curve.ports]
        pipe_shape = [(port.face, port.direction, port.role) for port in pipe_curve.ports]
        self.assertEqual(item_shape, pipe_shape)
        self.assertEqual({port.material_kind for port in item_curve.ports}, {"solid"})
        self.assertEqual({port.material_kind for port in pipe_curve.ports}, {"liquid"})

    def test_splitter_is_one_in_many_out_merger_is_many_in_one_out(self) -> None:
        for element_type in (LogisticsElementType.ITEM_SPLITTER, LogisticsElementType.PIPE_SPLITTER):
            element = LogisticsElement(id="x", element_type=element_type, position=Cell(0, 0))
            self.assertEqual(len([p for p in element.ports if p.direction == "in"]), 1)
            self.assertEqual(len([p for p in element.ports if p.direction == "out"]), 3)
        for element_type in (LogisticsElementType.ITEM_MERGER, LogisticsElementType.PIPE_MERGER):
            element = LogisticsElement(id="x", element_type=element_type, position=Cell(0, 0))
            self.assertEqual(len([p for p in element.ports if p.direction == "in"]), 3)
            self.assertEqual(len([p for p in element.ports if p.direction == "out"]), 1)

    def test_rotation_moves_ports_clockwise(self) -> None:
        straight = LogisticsElement(
            id="s", element_type=LogisticsElementType.CONVEYOR_STRAIGHT, position=Cell(0, 0), rotation=Rotation.DEG_90
        )
        self.assertEqual({port.face for port in straight.ports}, {Face.NORTH, Face.SOUTH})
        curve = LogisticsElement(
            id="c", element_type=LogisticsElementType.ITEM_CURVE, position=Cell(0, 0), rotation=Rotation.DEG_90
        )
        # 弯段基准为西→北，转 90 度后为北→东。
        self.assertEqual({port.face: port.direction for port in curve.ports}, {Face.NORTH: "in", Face.EAST: "out"})

    def test_family_separates_item_and_pipe_networks(self) -> None:
        self.assertEqual(LogisticsElementType.CONVEYOR_STRAIGHT.family, "item")
        self.assertEqual(LogisticsElementType.ITEM_BRIDGE.family, "item")
        self.assertEqual(LogisticsElementType.PIPE_STRAIGHT.family, "fluid")
        self.assertEqual(LogisticsElementType.PIPE_BRIDGE.family, "fluid")
        for element_type in LogisticsElementType:
            element = LogisticsElement(id="e", element_type=element_type, position=Cell(0, 0))
            kinds = {port.material_kind for port in element.ports}
            self.assertEqual(len(kinds), 1)
            self.assertEqual(kinds.pop(), "solid" if element_type.family == "item" else "liquid")

    def test_rate_limits(self) -> None:
        self.assertEqual(LogisticsElementType.CONVEYOR_STRAIGHT.max_rate_per_minute, 30)
        self.assertEqual(LogisticsElementType.PIPE_STRAIGHT.max_rate_per_minute, 120)
        gate_item = LogisticsElement(id="g", element_type=LogisticsElementType.ITEM_GATE, position=Cell(0, 0))
        gate_pipe = LogisticsElement(id="g", element_type=LogisticsElementType.PIPE_GATE, position=Cell(0, 0))
        self.assertEqual(gate_item.speed_limit_upper_bound, 30)
        self.assertEqual(gate_pipe.speed_limit_upper_bound, 60)
        self.assertEqual(LogisticsElementType.ITEM_GATE.speed_step_per_minute, 6)

    def test_gate_requires_item_filter_and_speed_step(self) -> None:
        gate = LogisticsElement(id="g", element_type=LogisticsElementType.ITEM_GATE, position=Cell(0, 0))
        problems = gate.validate()
        self.assertTrue(any("必须标记" in problem for problem in problems))

        good = LogisticsElement(
            id="g",
            element_type=LogisticsElementType.ITEM_GATE,
            position=Cell(0, 0),
            item_filter="赤铜块",
            speed_limit_per_minute=24,
        )
        self.assertEqual(good.validate(), [])
        self.assertEqual(good.ports[0].item_filter, "赤铜块")

        bad_step = LogisticsElement(
            id="g",
            element_type=LogisticsElementType.ITEM_GATE,
            position=Cell(0, 0),
            item_filter="赤铜块",
            speed_limit_per_minute=25,
        )
        self.assertTrue(any("整数倍" in problem for problem in bad_step.validate()))

    def test_base_specs_cover_all_types(self) -> None:
        self.assertEqual(set(BASE_PORT_SPECS), set(LogisticsElementType))


if __name__ == "__main__":
    unittest.main()
