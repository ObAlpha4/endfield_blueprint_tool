"""端口格映射与面内排列方向（``design/domain-model.md`` §6.1、``baseline-rules.md`` §1.2）。

面内排列方向：北面东→西、南面西→东、西面北→南、东面南→北，``ordinal`` 从 1 起。
未旋转局部格映射：北 ``(w-ordinal, h-1)``、南 ``(ordinal-1, 0)``、
西 ``(0, h-ordinal)``、东 ``(w-1, ordinal-1)``。
"""

from __future__ import annotations

import unittest

from endfield.domain.devices import Face, build_ports, local_cell_for, marker_direction, marker_material_kind
from endfield.domain.geometry import Cell, Rotation


class PortMappingTests(unittest.TestCase):
    def test_north_face_runs_east_to_west(self) -> None:
        # 9 宽设备的北面：ordinal 1 在最东格 x=8，ordinal 9 在最西格 x=0。
        self.assertEqual(local_cell_for(Face.NORTH, 1, 9, 9), (8, 8))
        self.assertEqual(local_cell_for(Face.NORTH, 9, 9, 9), (0, 8))

    def test_south_face_runs_west_to_east(self) -> None:
        self.assertEqual(local_cell_for(Face.SOUTH, 1, 9, 9), (0, 0))
        self.assertEqual(local_cell_for(Face.SOUTH, 9, 9, 9), (8, 0))

    def test_west_face_runs_north_to_south(self) -> None:
        self.assertEqual(local_cell_for(Face.WEST, 1, 5, 5), (0, 4))
        self.assertEqual(local_cell_for(Face.WEST, 5, 5, 5), (0, 0))

    def test_east_face_runs_south_to_north(self) -> None:
        self.assertEqual(local_cell_for(Face.EAST, 1, 5, 5), (4, 0))
        self.assertEqual(local_cell_for(Face.EAST, 5, 5, 5), (4, 4))

    def test_dismantler_gas_mode_east_face(self) -> None:
        # 拆解机（气体模式）：6x4，东面 `nngon` → n, n, go, n；go 是第 3 个 ordinal。
        ports = build_ports(6, 4, {"NORTH": "sisisisisisi", "SOUTH": "sosososososo", "WEST": "nnnn", "EAST": "nngon"})
        east = [port for port in ports if port.face is Face.EAST]
        self.assertEqual([port.marker for port in east], ["n", "n", "go", "n"])
        go_port = next(port for port in east if port.marker == "go")
        self.assertEqual(go_port.ordinal, 3)
        # 东面从南向北：ordinal 1 → y=0，ordinal 3 → y=2，x 恒为 w-1=5。
        self.assertEqual(go_port.local_cell, (5, 2))

    def test_liquid_refinery_west_liquid_port(self) -> None:
        # 精炼炉（液体模式）：3x3，西面 `nfin` → n, fi, n；fi 的局部格是 (0, 1)。
        ports = build_ports(3, 3, {"NORTH": "sisisi", "SOUTH": "sososo", "WEST": "nfin", "EAST": "nfon"})
        liquid_in = next(port for port in ports if port.face is Face.WEST and port.marker == "fi")
        self.assertEqual(liquid_in.local_cell, (0, 1))
        self.assertEqual(liquid_in.material_kind, "liquid")
        self.assertEqual(liquid_in.direction, "in")

    def test_protocol_core_authoritative_values(self) -> None:
        # baseline §4.3：北/南 `nsisisisisisisin`（6 个 si），西/东 `nsonnsonnson`（3 个 so）。
        ports = build_ports(
            9,
            9,
            {
                "NORTH": "nsisisisisisisin",
                "SOUTH": "nsisisisisisisin",
                "WEST": "nsonnsonnson",
                "EAST": "nsonnsonnson",
            },
        )
        self.assertEqual(len(ports), 36)
        self.assertEqual(len([p for p in ports if p.marker == "si"]), 14)
        self.assertEqual(len([p for p in ports if p.marker == "so"]), 6)
        self.assertEqual(len([p for p in ports if p.direction == "none"]), 16)
    def test_cell_count_must_equal_side(self) -> None:
        with self.assertRaises(ValueError):
            build_ports(3, 3, {"NORTH": "nfnn", "SOUTH": "sososo", "WEST": "nnn", "EAST": "nnn"})
        with self.assertRaises(ValueError):
            build_ports(3, 3, {"NORTH": "sisi", "SOUTH": "sososo", "WEST": "nnn", "EAST": "nnn"})

    def test_marker_semantics(self) -> None:
        self.assertEqual(marker_direction("si"), "in")
        self.assertEqual(marker_direction("go"), "out")
        self.assertEqual(marker_direction("n"), "none")
        self.assertEqual(marker_material_kind("fi"), "liquid")
        self.assertEqual(marker_material_kind("go"), "gas")
        self.assertEqual(marker_material_kind("so"), "solid")
        self.assertEqual(marker_material_kind("n"), "none")

    def test_global_cell_with_rotation(self) -> None:
        # 反应池西面 ordinal 2 的 fi：3x3 局部格 (0, 1)。
        port = next(
            p for p in build_ports(5, 5, {"NORTH": "nsinsin", "SOUTH": "nsonson", "WEST": "nfinfin", "EAST": "nfonfon"})
            if p.face is Face.WEST and p.ordinal == 2
        )
        self.assertEqual(port.local_cell, (0, 3))
        origin = Cell(10, 20)
        self.assertEqual(port.global_cell(origin, Rotation.DEG_0, 5, 5), Cell(10, 23))
        # 顺时针 90 度：(0,3) → (3, 4)；占地宽高互换后不再占用原格。
        self.assertEqual(port.global_cell(origin, Rotation.DEG_90, 5, 5), Cell(13, 24))
        self.assertEqual(port.global_face(Rotation.DEG_90), Face.NORTH)


if __name__ == "__main__":
    unittest.main()
