"""解析器断言：把 ``tools/validate_sources.py`` 的历史不变量固化下来。

覆盖：

- 「四面接口串分词格数 = 宽/高」（46 行 0 错）；
- 配方表结构（151 行、行号 2–152）；
- 产物列全空的**两种不同语义**（销毁 vs 环境生成）；
- 发电表 6 条；
- 规范化值（第 37/48 行尾随制表符）；
- **负向测试**：掉字符 / ``nnfinn``→``nfnn`` 必须被捕获。
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from endfield.domain.devices import Face
from endfield.domain.recipes import CATALYST_PER_MINUTE
from endfield.sources.ooxml import discover_sheets, read_sheet, tokenize
from endfield.sources.parser import (
    DEVICE_FILE,
    EXPECTED_DEVICE_ROWS,
    EXPECTED_POWER_ROWS,
    EXPECTED_RECIPE_ROWS,
    PROTOCOL_CORE_NAME,
    SourceParseError,
    parse_sources,
)

MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"


class ParserAssertionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = parse_sources(DOCS_DIR)

    def test_device_count_and_categories(self) -> None:
        total = len(self.bundle.device_types) + len(self.bundle.special_devices)
        self.assertEqual(total, EXPECTED_DEVICE_ROWS)
        self.assertEqual(len(self.bundle.special_devices), 1)
        self.assertEqual(self.bundle.special_devices[0].canonical_name, PROTOCOL_CORE_NAME)
        categories = {device.category for device in (*self.bundle.device_types, *self.bundle.special_devices)}
        self.assertEqual(categories, {"仓储存取", "基础生产", "合成制造", "电力供应"})

    def test_protocol_core_is_not_in_device_list(self) -> None:
        names = {device.canonical_name for device in self.bundle.device_types}
        self.assertNotIn(PROTOCOL_CORE_NAME, names)
        core = self.bundle.special_device_by_name[PROTOCOL_CORE_NAME]
        self.assertEqual((core.width, core.height), (9, 9))
        self.assertEqual(len(core.io_ports), 20)
        self.assertTrue(core.special)
        self.assertTrue(any("R-006" in note for note in core.notes))

    def test_every_device_has_ports_matching_its_size(self) -> None:
        for device in (*self.bundle.device_types, *self.bundle.special_devices):
            for face, expected in (
                (Face.NORTH, device.width),
                (Face.SOUTH, device.width),
                (Face.WEST, device.height),
                (Face.EAST, device.height),
            ):
                self.assertEqual(len(device.ports_on(face)), expected, f"{device.canonical_name} {face.value}")

    def test_recipe_count_and_rows(self) -> None:
        self.assertEqual(len(self.bundle.recipes), EXPECTED_RECIPE_ROWS)
        self.assertEqual(self.bundle.recipes[0].source_row, 2)
        self.assertEqual(self.bundle.recipes[-1].source_row, 152)

    def test_empty_output_rows_split_into_two_semantics(self) -> None:
        destroy = [r.source_row for r in self.bundle.recipes if r.destroys_input]
        environment = [r.source_row for r in self.bundle.recipes if r.is_environment_recipe]
        self.assertEqual(destroy, [73, 74, 75])
        self.assertEqual(environment, [126, 127, 128, 129])
        expected_pairs = {
            126: ("惰气", "稳定环境"),
            127: ("水蒸气", "湿润环境"),
            128: ("酸气", "酸性环境"),
            129: ("息壤气", "息壤环境"),
        }
        for recipe in self.bundle.recipes:
            if recipe.is_environment_recipe:
                self.assertEqual(recipe.device_canonical_name, "气体散布机")
                self.assertEqual(len(recipe.inputs), 1)
                self.assertEqual(recipe.duration_seconds, 60)
                self.assertEqual(recipe.inputs[0].quantity, 6)
                self.assertEqual(
                    (recipe.inputs[0].item, recipe.environment_produced),
                    expected_pairs[recipe.source_row],
                )
                # 环境生成行的 G 列是环境名、没有数量；与环境字段 `K` 不是一回事。
                self.assertIsNone(recipe.environment)
            if recipe.destroys_input:
                self.assertEqual(recipe.device_canonical_name, "废水处理机")

    def test_catalyst_is_fixed_six_per_minute(self) -> None:
        catalyst_recipes = [recipe for recipe in self.bundle.recipes if recipe.catalyst]
        self.assertEqual(len(catalyst_recipes), 22)
        for recipe in catalyst_recipes:
            self.assertEqual(recipe.catalyst_per_minute, CATALYST_PER_MINUTE)
            self.assertGreaterEqual(recipe.source_row, 131)
            self.assertLessEqual(recipe.source_row, 152)

    def test_rates_are_exact_rationals(self) -> None:
        # 第 102 行：5 壤晶 + 20 致密源石粉末 → 1 中容武陵电池，10s ⇒ 6 次/分钟。
        recipe = next(r for r in self.bundle.recipes if r.source_row == 102)
        self.assertEqual(recipe.batches_per_minute, 6)
        self.assertEqual(recipe.out_rate_per_minute("中容武陵电池"), 6)
        self.assertEqual(recipe.in_rate_per_minute("壤晶"), 30)
        self.assertEqual(recipe.in_rate_per_minute("致密源石粉末"), 120)

    def test_environment_column_is_separate_from_environment_recipe(self) -> None:
        environments = {recipe.environment for recipe in self.bundle.recipes if recipe.environment}
        self.assertEqual(environments, {"稳定环境", "酸性环境"})
        produced = {recipe.environment_produced for recipe in self.bundle.recipes if recipe.environment_produced}
        self.assertEqual(produced, {"稳定环境", "湿润环境", "酸性环境", "息壤环境"})

    def test_power_entries(self) -> None:
        self.assertEqual(len(self.bundle.power_entries), EXPECTED_POWER_ROWS)
        by_name = {entry.canonical_name: entry for entry in self.bundle.power_entries}
        self.assertEqual(by_name["中容武陵电池"].power_kw, 3200)
        self.assertEqual(by_name["低容谷地电池"].burn_seconds, 20)
        self.assertEqual(by_name["低容谷地电池"].power_kw, 220)
        self.assertEqual(by_name["源矿"].burn_seconds, 8)
        self.assertEqual(by_name["源矿"].power_kw, 50)

    def test_external_source_devices_are_outside_the_blueprint(self) -> None:
        device_names = {device.canonical_name for device in self.bundle.device_types}
        external = {"电驱矿机", "二型电驱矿机", "水驱矿机", "水泵", "二型耐酸水泵", "气体收集泵"}
        self.assertFalse(external & device_names)
        referenced = {recipe.device_canonical_name for recipe in self.bundle.recipes}
        self.assertTrue(external <= referenced)

    def test_trailing_tab_is_normalized_with_source_ref(self) -> None:
        raw_cells = [
            (item["row"], item["column"], item["raw"], item["canonical"])
            for item in self.bundle.report.normalizations
        ]
        self.assertIn((37, "B", "紫晶纤维\t", "紫晶纤维"), raw_cells)
        self.assertIn((48, "B", "紫晶纤维\t", "紫晶纤维"), raw_cells)

    def test_items_are_derived_from_recipes(self) -> None:
        self.assertEqual(len(self.bundle.items), 111)
        kinds: dict[str, int] = {}
        for item in self.bundle.items:
            kinds[item.kind] = kinds.get(item.kind, 0) + 1
        # 另有 4 个「X瓶（装有Y溶液）」容器按用户补充确认判为固体。
        self.assertEqual(kinds, {"solid": 92, "liquid": 11, "gas": 8})
        containers = sorted(item.canonical_name for item in self.bundle.items if item.is_container)
        self.assertEqual(
            containers,
            [
                "蓝铁瓶（装有芽针溶液）",
                "蓝铁瓶（装有锦草溶液）",
                "赤铜瓶（装有芽针溶液）",
                "赤铜瓶（装有锦草溶液）",
            ],
        )
        for item in self.bundle.items:
            if item.is_container:
                self.assertEqual(item.kind, "solid")
                self.assertEqual(item.unit, "item")
                self.assertIsNotNone(item.kind_note)

    def test_slot_counts_follow_r067(self) -> None:
        by_row = {recipe.source_row: recipe for recipe in self.bundle.recipes}
        self.assertEqual(by_row[113].slot_count, 5)  # 反应池
        self.assertEqual(by_row[113].device_canonical_name, "反应池")
        # 其余设备 = 输入物料种类数
        self.assertEqual(by_row[102].slot_count, 2)  # 封装机：壤晶 + 致密源石粉末
        self.assertEqual(by_row[7].slot_count, 0)  # 水泵：无输入
        # 第 79 行 10 + 10 = 20，未超过单格 50
        self.assertFalse(by_row[79].input_overflow)

    def test_report_is_clean(self) -> None:
        self.assertTrue(self.bundle.report.ok, self.bundle.report.errors)
        self.assertEqual(self.bundle.report.errors, [])
        self.assertGreaterEqual(len(self.bundle.report.checks), 10)


class NegativeParserTests(unittest.TestCase):
    """负向测试：损坏的源数据必须被断言拦住。

    设备表的端口串存放在 ``sharedStrings.xml`` 里、由单元格的共享字符串索引引用，
    因此这里把目标单元格改写成**内联字符串**，其余部分保持原样，
    失败的只会是「格数 = 宽/高」这一条断言。
    """

    def _corrupt_device_cells(self, tmp: str, cells: dict[str, str]) -> Path:
        docs = Path(tmp) / "docs"
        shutil.copytree(DOCS_DIR, docs)
        path = docs / DEVICE_FILE
        with zipfile.ZipFile(path) as archive:
            parts = {name: archive.read(name) for name in archive.namelist()}
        sheet = ET.fromstring(parts["xl/worksheets/sheet1.xml"])
        replaced: set[str] = set()
        for row in sheet.iter(MAIN_NS + "row"):
            for cell in row.iter(MAIN_NS + "c"):
                reference = cell.get("r", "")
                if reference in cells:
                    # 先写内联字符串再清掉旧的共享字符串引用，保证 `is` 出现在 `v` 之前。
                    cell.set("t", "inlineStr")
                    inline = ET.SubElement(cell, MAIN_NS + "is")
                    text = ET.SubElement(inline, MAIN_NS + "t")
                    text.text = cells[reference]
                    for child in list(cell):
                        if child.tag != MAIN_NS + "is":
                            cell.remove(child)
                    replaced.add(reference)
        self.assertEqual(replaced, set(cells), f"未找到待改写的单元格：{sorted(set(cells) - replaced)}")
        parts["xl/worksheets/sheet1.xml"] = ET.tostring(sheet, encoding="utf-8", xml_declaration=True)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, content in parts.items():
                archive.writestr(name, content)
        return docs

    def test_dropped_character_is_caught(self) -> None:
        # 协议储存箱（第 2 行）北面 `sisisi` 多补一个 `si` → `sisisisi`（4 格，应为 3 格）。
        # 这是历史缺陷「长重复串掉/多字符」的同类形态：标记本身合法，只有格数能发现。
        self.assertEqual(self._device_cell("D2"), "sisisi")
        with tempfile.TemporaryDirectory() as tmp:
            docs = self._corrupt_device_cells(tmp, {"D2": "sisisisi"})
            with self.assertRaises(SourceParseError) as context:
                parse_sources(docs)
        self.assertIn("分词 4 格，应为 3 格", str(context.exception))

    def test_truncated_port_string_is_caught(self) -> None:
        # `sisisi` 掉一个字符 → `sisis`：既格数不符，也会出现非法标记 `s`。
        with tempfile.TemporaryDirectory() as tmp:
            docs = self._corrupt_device_cells(tmp, {"D2": "sisis"})
            with self.assertRaises(SourceParseError) as context:
                parse_sources(docs)
        message = str(context.exception)
        self.assertTrue("分词 2 格，应为 3 格" in message or "非法标记" in message, message)

    def test_collapsed_nnfinn_is_caught(self) -> None:
        # 种植机（液体模式）西面 F21 `nnfinn`（5 格）被压成 `nfnn`（3 格）。
        self.assertEqual(self._device_cell("F21"), "nnfinn")
        with tempfile.TemporaryDirectory() as tmp:
            docs = self._corrupt_device_cells(tmp, {"F21": "nfnn"})
            with self.assertRaises(SourceParseError) as context:
                parse_sources(docs)
        self.assertIn("分词 3 格，应为 5 格", str(context.exception))

    def test_unknown_marker_is_caught(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docs = self._corrupt_device_cells(tmp, {"D2": "sixixi"})
            with self.assertRaises(SourceParseError) as context:
                parse_sources(docs)
        self.assertIn("非法标记", str(context.exception))

    @staticmethod
    def _device_cell(reference: str) -> str:
        target = next(sheet for sheet in discover_sheets(DOCS_DIR / DEVICE_FILE) if sheet.name == "设备列表")
        rows = read_sheet(DOCS_DIR / DEVICE_FILE, target.path)
        column = "".join(ch for ch in reference if ch.isalpha())
        row_number = int("".join(ch for ch in reference if ch.isdigit()))
        for row, values in rows:
            if row == row_number:
                return values.get(column, "")
        raise AssertionError(f"未找到单元格 {reference}")


class SheetStructureTests(unittest.TestCase):
    def _sheet_names(self) -> list[str]:
        sheets = discover_sheets(DOCS_DIR / DEVICE_FILE)
        return [sheet.name for sheet in sheets]

    def test_sheet_names_are_discovered_not_hardcoded(self) -> None:
        # 设备表的第二张表是 `标记对照`，解析器通过 workbook.xml 发现它。
        self.assertEqual(self._sheet_names(), ["设备列表", "标记对照"])
        bundle = parse_sources(DOCS_DIR)
        self.assertEqual(len(bundle.markers), 7)
        self.assertEqual(bundle.markers[0], ("si", "固体入口"))

    def test_marker_sheet_content_matches_parser(self) -> None:
        target = next(sheet for sheet in discover_sheets(DOCS_DIR / DEVICE_FILE) if sheet.name == "标记对照")
        rows = read_sheet(DOCS_DIR / DEVICE_FILE, target.path)
        markers = {values.get("A") for row, values in rows if row > 1}
        self.assertEqual(markers, {"si", "so", "fi", "fo", "gi", "go", "n"})

    def test_device_sheet_has_46_data_rows(self) -> None:
        with zipfile.ZipFile(DOCS_DIR / DEVICE_FILE) as archive:
            sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        rows = list(sheet.iter(MAIN_NS + "row"))
        self.assertEqual(len(rows), EXPECTED_DEVICE_ROWS + 1)
        self.assertEqual(len(tokenize("nsisisisisisisin")), 9)


if __name__ == "__main__":
    unittest.main()
