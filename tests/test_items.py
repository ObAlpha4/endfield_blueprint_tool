"""物品品类（用户确认的规则）与单位。

源文件没有物品表，``Item.kind`` 来自用户确认的规则：

    清水、沉积酸、污水、壤晶废液、惰性壤晶废液、液化**、**溶液都是液体，
    **气、气态**都是气体

其中「液化**」与「**溶液」的两个 ``**`` 是被强调的「液化 / 溶液」字样，
落地为：显式液体名单 ∪ 含 ``液化`` → 液体；含 ``气``（覆盖 ``气态``）→ 气体；其余固体。
"""

from __future__ import annotations

import unittest

from endfield.items import (
    CONTAINER_EXCEPTIONS,
    EXPLICIT_LIQUID_NAMES,
    classify_kind,
    is_container_exception,
    self_check,
    unit_for,
)


class ItemKindRuleTests(unittest.TestCase):
    def test_explicit_liquids(self) -> None:
        for name in ("清水", "沉积酸", "污水", "壤晶废液", "惰性壤晶废液"):
            self.assertEqual(classify_kind(name), "liquid", name)
            self.assertIn(name, EXPLICIT_LIQUID_NAMES)

    def test_liquefied_names_are_liquid(self) -> None:
        self.assertEqual(classify_kind("液化息壤"), "liquid")
        self.assertEqual(classify_kind("液化重息壤"), "liquid")
        # 源表第 139 行的产物「液化重息壤」与「重息壤」是两个不同物料。
        self.assertEqual(classify_kind("重息壤"), "solid")

    def test_gas_names(self) -> None:
        for name in ("惰气", "酸气", "水蒸气", "息壤气", "重息壤气", "气态赤铜", "气态赫铜", "气态灼铜"):
            self.assertEqual(classify_kind(name), "gas", name)

    def test_solutions_are_liquid_and_their_containers_are_solid(self) -> None:
        # 用户确认原文：「液化**、**溶液都是液体」。
        self.assertEqual(classify_kind("芽针溶液"), "liquid")
        self.assertEqual(classify_kind("锦草溶液"), "liquid")
        self.assertEqual(classify_kind("赤铜溶液"), "liquid")
        self.assertEqual(classify_kind("赫铜溶液"), "liquid")

    def test_container_exceptions_are_solid_items(self) -> None:
        # 用户补充确认：「容器名里含『溶液』的，本身属于固体（物品）」。
        containers = [
            "蓝铁瓶（装有芽针溶液）",
            "蓝铁瓶（装有锦草溶液）",
            "赤铜瓶（装有芽针溶液）",
            "赤铜瓶（装有锦草溶液）",
        ]
        for name in containers:
            self.assertTrue(is_container_exception(name), name)
            self.assertEqual(classify_kind(name), "solid", name)
            self.assertEqual(unit_for(classify_kind(name)), "item", name)
        self.assertEqual(set(containers), set(CONTAINER_EXCEPTIONS))
        # 不含关键词的同类容器本来就判为固体，不必进例外名单。
        for name in ("紫晶质瓶", "赤铜耐压罐", "钢质瓶", "高晶质瓶", "蓝铁瓶", "赤铜瓶", "赫铜瓶"):
            self.assertFalse(is_container_exception(name), name)
            self.assertEqual(classify_kind(name), "solid", name)

    def test_solids(self) -> None:
        for name in ("赤铜块", "息壤", "重息壤", "壤晶", "分离芯", "碳块", "中容武陵电池"):
            self.assertEqual(classify_kind(name), "solid", name)

    def test_units(self) -> None:
        self.assertEqual(unit_for("solid"), "item")
        self.assertEqual(unit_for("liquid"), "drop")
        self.assertEqual(unit_for("gas"), "drop")

    def test_self_check_is_conflict_free(self) -> None:
        names = ["清水", "液化息壤", "息壤气", "水蒸气", "赤铜块", "壤晶", "蓝铁瓶（装有芽针溶液）"]
        result = self_check(names)
        self.assertEqual(result["conflicts"], [])
        self.assertEqual(result["counts"]["liquid"], 2)
        self.assertEqual(result["counts"]["gas"], 2)
        # 赤铜块 / 壤晶 / 蓝铁瓶（装有芽针溶液）→ 3 个固体
        self.assertEqual(result["counts"]["solid"], 3)
        self.assertEqual(result["containerExceptions"], ["蓝铁瓶（装有芽针溶液）"])


if __name__ == "__main__":
    unittest.main()
