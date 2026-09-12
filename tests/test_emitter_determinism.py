"""确定性序列化与蓝图容器（``design/next-steps.md`` 步骤 1 验收「逐字节一致」；C-3 / C-4）。"""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from endfield.domain.blueprint import BaseType, Blueprint, ChainPlan, ExternalInterface, PathSpec
from endfield.domain.devices import DeviceInstance
from endfield.domain.geometry import Cell
from endfield.domain.logistics import LogisticsElement, LogisticsElementType
from endfield.sources import emit
from endfield.sources.parser import parse_sources

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"


class EmitterDeterminismTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = parse_sources(DOCS_DIR)

    def test_two_parses_produce_identical_bytes(self) -> None:
        first = emit.dumps(emit.build_document(parse_sources(DOCS_DIR)))
        second = emit.dumps(emit.build_document(parse_sources(DOCS_DIR)))
        self.assertEqual(first, second)
        self.assertEqual(
            hashlib.sha256(first.encode("utf-8")).hexdigest(),
            hashlib.sha256(second.encode("utf-8")).hexdigest(),
        )

    def test_write_is_byte_identical_and_parses_back(self) -> None:
        document = emit.build_document(self.bundle)
        with tempfile.TemporaryDirectory() as tmp:
            first_path = Path(tmp) / "a" / "sources.json"
            second_path = Path(tmp) / "b" / "sources.json"
            digest_a, size_a = emit.write(document, first_path)
            digest_b, size_b = emit.write(emit.build_document(self.bundle), second_path)
            self.assertEqual(digest_a, digest_b)
            self.assertEqual(size_a, size_b)
            self.assertEqual(first_path.read_bytes(), second_path.read_bytes())
            payload = first_path.read_bytes()
            self.assertFalse(payload.startswith(b"\xef\xbb\xbf"), "不得写 BOM")
            self.assertTrue(payload.endswith(b"\n"))
            loaded = emit.load(first_path)
            self.assertEqual(loaded["schema"], emit.SCHEMA_ID)

    def test_document_is_sorted_and_has_no_timestamp(self) -> None:
        text = emit.dumps(emit.build_document(self.bundle))
        self.assertNotIn("timestamp", text)
        self.assertNotIn("generatedAt", text)
        document = json.loads(text)
        self.assertEqual(document["schema"], emit.SCHEMA_ID)
        self.assertEqual(document["schemaVersion"], emit.SCHEMA_VERSION)

    def test_exact_rationals_are_serialized(self) -> None:
        document = emit.build_document(self.bundle)
        recipe = next(row for row in document["recipes"] if row["sourceRow"] == 102)
        self.assertEqual(recipe["batchesPerMinute"], {"num": 6, "den": 1, "value": 6})
        self.assertEqual(recipe["durationSeconds"], {"num": 10, "den": 1, "value": 10})

    def test_device_and_recipe_counts_in_document(self) -> None:
        document = emit.build_document(self.bundle)
        self.assertEqual(len(document["devices"]), 45)
        self.assertEqual(len(document["specialDevices"]), 1)
        self.assertEqual(len(document["recipes"]), 151)
        self.assertEqual(len(document["items"]), 111)
        self.assertEqual(len(document["logisticsElements"]), 12)
        self.assertTrue(document["validation"]["ok"])

    def test_logistics_elements_have_no_fixed_face_strings(self) -> None:
        document = emit.build_document(self.bundle)
        for row in document["logisticsElements"]:
            self.assertNotIn("rawFaces", row)
            self.assertEqual(row["footprint"], {"width": 1, "height": 1})
            self.assertIn(row["portCount"], (2, 3, 4))


class BlueprintSkeletonTests(unittest.TestCase):
    def test_bounds_equal_base_rectangle(self) -> None:
        main = Blueprint(id="B1", base_type=BaseType.MAIN)
        self.assertEqual(main.bounds.as_dict(), {"x": 0, "y": 0, "width": 80, "height": 80})
        secondary = Blueprint(id="B2", base_type=BaseType.SECONDARY)
        self.assertEqual(secondary.bounds.as_dict(), {"x": 0, "y": 0, "width": 50, "height": 50})
        self.assertEqual(main.origin, Cell(0, 0))

    def test_base_segment_limits(self) -> None:
        self.assertEqual(BaseType.MAIN.base_segment_limit, 5)
        self.assertEqual(BaseType.SECONDARY.base_segment_limit, 12)

    def test_path_length_counts_only_continuous_runs(self) -> None:
        # C-4：断开元件自身不计长，逐段校验 ≤ 80。
        gate = LogisticsElement(id="g1", element_type=LogisticsElementType.ITEM_GATE, position=Cell(80, 0), item_filter="赤铜块")
        bridge = LogisticsElement(id="g2", element_type=LogisticsElementType.ITEM_BRIDGE, position=Cell(170, 0))
        segments = tuple(Cell(x, 0) for x in range(180))
        # 断开元件接在第 79 / 165 段之后：三段长度为 80 / 86 / 14，元件自身不计长。
        path = PathSpec(id="P1", family="item", segments=segments, breakpoints={79: gate, 165: bridge})
        runs = path.continuous_runs()
        self.assertEqual(len(runs), 3)
        self.assertEqual(path.run_lengths(), [80, 86, 14])
        self.assertEqual(path.overloaded_runs(), [86])

    def test_path_without_breakpoints_is_one_run(self) -> None:
        path = PathSpec(id="P2", family="fluid", segments=tuple(Cell(x, 0) for x in range(80)))
        self.assertEqual(path.run_lengths(), [80])
        self.assertEqual(path.overloaded_runs(), [])

    def test_max_path_length_is_eighty(self) -> None:
        exact = PathSpec(id="P3", family="item", segments=tuple(Cell(x, 0) for x in range(80)))
        over = PathSpec(id="P4", family="item", segments=tuple(Cell(x, 0) for x in range(81)))
        self.assertEqual(exact.overloaded_runs(), [])
        self.assertEqual(over.overloaded_runs(), [81])

    def test_blueprint_serializes_device_instances(self) -> None:
        blueprint = Blueprint(id="B1", base_type=BaseType.MAIN)
        blueprint.device_instances.append(
            DeviceInstance(id="D1", device_type_id="封装机", position=Cell(4, 5), recipe_id="R102")
        )
        blueprint.external_interfaces.append(ExternalInterface(id="E1", kind="pickup", item="息壤"))
        payload = blueprint.as_dict()
        self.assertEqual(payload["deviceInstances"][0]["position"], {"x": 4, "y": 5})
        self.assertEqual(payload["deviceInstances"][0]["rotation"], 0)
        self.assertEqual(payload["deviceInstances"][0]["recipeId"], "R102")
        self.assertEqual(payload["externalInterfaces"][0]["item"], "息壤")

    def test_chain_plan_is_structure_only(self) -> None:
        plan = ChainPlan(target_product="重息壤", target_rate_per_minute=12)
        payload = plan.as_dict()
        self.assertEqual(payload["targetProduct"], "重息壤")
        self.assertEqual(payload["startProducts"], [])
        self.assertEqual(payload["recipeUsage"], [])


if __name__ == "__main__":
    unittest.main()
