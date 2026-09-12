"""旋转与整数格几何（``design/global-constraints.md`` G-001 / G-001.5）。

- 只允许顺时针 0 / 90 / 180 / 270 度，禁止镜像；
- 旋转锚点为**左下角**，旋转只交换宽高，不产生半格偏移；
- 设备边缘严格位于整数坐标的格线上、顶点严格位于整数坐标上；
- 连接判定 = 边贴边且共同长度 > 0（``design/logistics-and-storage-geometry.md`` §2.2）。
"""

from __future__ import annotations

import unittest

from endfield.domain.geometry import Cell, Direction, GridRect, Rotation, rotate_cell, rotate_local_cell


class RotationTests(unittest.TestCase):
    def test_only_four_angles_allowed(self) -> None:
        self.assertEqual(Rotation.of(0), Rotation.DEG_0)
        self.assertEqual(Rotation.of(270), Rotation.DEG_270)
        with self.assertRaises(ValueError):
            Rotation.of(45)
        with self.assertRaises(ValueError):
            Rotation.of(-90)

    def test_direction_rotates_clockwise(self) -> None:
        self.assertEqual(Direction.NORTH.rotated(1), Direction.EAST)
        self.assertEqual(Direction.EAST.rotated(1), Direction.SOUTH)
        self.assertEqual(Direction.SOUTH.rotated(1), Direction.WEST)
        self.assertEqual(Direction.WEST.rotated(1), Direction.NORTH)
        self.assertEqual(Direction.NORTH.rotated(2), Direction.SOUTH)
        self.assertEqual(Direction.EAST.opposite, Direction.WEST)
        self.assertEqual(Direction.NORTH.rotated_by(Rotation.DEG_270), Direction.WEST)

    def test_local_cell_rotation_matches_anchor_formula(self) -> None:
        # 5x5 设备的局部格 (0, 3)（西面第 2 格）。
        self.assertEqual(rotate_local_cell(0, 3, 5, 5, Rotation.DEG_0), (0, 3))
        self.assertEqual(rotate_local_cell(0, 3, 5, 5, Rotation.DEG_90), (3, 4))
        self.assertEqual(rotate_local_cell(0, 3, 5, 5, Rotation.DEG_180), (4, 1))
        self.assertEqual(rotate_local_cell(0, 3, 5, 5, Rotation.DEG_270), (1, 0))

    def test_rotation_is_left_bottom_anchored(self) -> None:
        # 世界坐标 (x+0, y+3) 绕左下角 (x, y) 顺时针 90 度 → (x+3, y+0)。
        self.assertEqual(rotate_cell(Cell(10, 23), Rotation.DEG_90, Cell(10, 20)), Cell(13, 20))
        self.assertEqual(rotate_cell(Cell(10, 23), Rotation.DEG_180, Cell(10, 20)), Cell(10, 17))
        self.assertEqual(rotate_cell(Cell(10, 23), Rotation.DEG_270, Cell(10, 20)), Cell(7, 20))

    def test_rect_rotation_swaps_size_and_stays_integer(self) -> None:
        rect = GridRect(10, 20, 5, 3)
        rotated = rect.rotated(Rotation.DEG_90, pivot=rect.origin)
        self.assertEqual((rotated.width, rotated.height), (3, 5))
        # 锚点保持不动，矩形从锚点向上 / 向右生长（左下角锚点方案 A）。
        self.assertEqual(rotated.origin, Cell(10, 20))
        self.assertEqual(rotated.cells(), GridRect(10, 20, 3, 5).cells())
        for cell in rotated.cells():
            self.assertIsInstance(cell.x, int)
            self.assertIsInstance(cell.y, int)

    def test_four_rotations_return_to_start(self) -> None:
        rect = GridRect(4, 7, 6, 2)
        current = rect
        for _ in range(4):
            current = current.rotated(Rotation.DEG_90, pivot=rect.origin)
        self.assertEqual(current, rect)

    def test_non_integer_coordinates_rejected(self) -> None:
        with self.assertRaises(TypeError):
            Cell(1.5, 3)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            GridRect(0, 0, 2.5, 2)  # type: ignore[arg-type]


class GridRectTests(unittest.TestCase):
    def test_cell_count_is_width_times_height(self) -> None:
        self.assertEqual(len(GridRect(0, 0, 9, 9).cells()), 81)
        self.assertEqual(len(GridRect(3, 4, 2, 5).cells()), 10)

    def test_overlap_is_integer_cell_intersection(self) -> None:
        a = GridRect(0, 0, 3, 3)
        b = GridRect(2, 2, 3, 3)
        self.assertTrue(a.overlaps(b))
        # 相切：格集合不相交，不算重叠。
        self.assertFalse(a.overlaps(GridRect(3, 0, 3, 3)))
        # 角点相触也不算。
        self.assertFalse(a.overlaps(GridRect(3, 3, 2, 2)))

    def test_edge_adjacency_requires_positive_shared_length(self) -> None:
        # 对应 design/logistics-and-storage-geometry.md §3 的用例 1 / 4 / 5 / 2。
        pile = GridRect(0, 0, 4, 4)  # 源桩 4x4
        segment = GridRect(1, 4, 8, 4)  # 用例 1：底边与源桩顶边部分搭接，共同长度 [1,4) = 3 格
        self.assertEqual(pile.shared_edge_length(segment), 3)
        self.assertTrue(pile.is_edge_adjacent_to(segment))

        overlap = GridRect(1, 3, 8, 4)  # 用例 4：重叠 1 格（不是边贴边）
        self.assertTrue(pile.overlaps(overlap))
        self.assertEqual(pile.shared_edge_length(overlap), 0)

        corner = GridRect(4, 4, 8, 4)  # 用例 5：仅角点相触
        self.assertEqual(pile.shared_edge_length(corner), 0)
        self.assertFalse(pile.is_edge_adjacent_to(corner))

        far = GridRect(20, 20, 8, 4)  # 用例 2：完全不相接
        self.assertEqual(pile.shared_edge_length(far), 0)

        full = GridRect(0, 4, 4, 4)  # 完全对齐的边贴边
        self.assertEqual(pile.shared_edge_length(full), 4)

    def test_contains_rect_is_closed(self) -> None:
        bounds = GridRect(0, 0, 80, 80)
        self.assertTrue(bounds.contains_rect(GridRect(0, 0, 80, 80)))
        self.assertTrue(bounds.contains_rect(GridRect(76, 76, 4, 4)))
        self.assertFalse(bounds.contains_rect(GridRect(77, 77, 4, 4)))

    def test_from_cells_rejects_non_rectangular(self) -> None:
        with self.assertRaises(ValueError):
            GridRect.from_cells([Cell(0, 0), Cell(1, 0), Cell(0, 1)])

    def test_cells_are_integers(self) -> None:
        for cell in GridRect(2, 3, 4, 5).cells():
            self.assertGreaterEqual(cell.x, 2)
            self.assertLess(cell.x, 6)
            self.assertGreaterEqual(cell.y, 3)
            self.assertLess(cell.y, 8)


if __name__ == "__main__":
    unittest.main()
