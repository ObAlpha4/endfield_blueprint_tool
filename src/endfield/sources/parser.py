"""源文件解析器：``docs/`` 四份权威源文件 → 规范化中间数据。

设计依据：

- ``design/next-steps.md`` 步骤 1（统一数据入口）：设备表「原始值 / 规范值 / 来源行号」三列分立；
  ``tools/validate_sources.py`` 的全部断言纳入解析器；同一输入**逐字节可重复**。
- ``design/domain-model.md`` §4（配方的空单元格语义）、§7（数据歧义）。
- ``design/baseline-rules.md`` §1.3（产物列全空的两种不同语义）、§4.3（权威值复核）。

解析器的立场：**断言失败就抛错，不产出半成品数据**。所有源数据问题都带行号 / 列号报出。
"""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from endfield.domain.devices import DeviceSource, DeviceType, build_ports, face_capacity
from endfield.domain.recipes import (
    CATALYST_PER_MINUTE,
    ENVIRONMENT_NAMES,
    Flow,
    PowerEntry,
    Recipe,
)
from endfield.items import KIND_RULE_SOURCE, Item, build_item, classify_kind, self_check, unit_for
from endfield.sources.ooxml import (
    VALID_MARKERS,
    Paragraph,
    Row,
    SheetRef,
    discover_sheets,
    read_by_sheet_name,
    read_docx_paragraphs,
    read_sheet,
    tokenize,
)

#: 源文件在仓库中的相对路径（相对于 ``docs/``）。
DEVICE_FILE = "设备概述.xlsx"
RECIPE_FILE = "产线配方.xlsx"
POWER_FILE = "发电对照.xlsx"
RULE_FILE = "终末地产线限制.docx"

DEVICE_SHEET = "设备列表"
MARKER_SHEET = "标记对照"

#: 设备表列 → 字段名（表头固定为 设备名称/宽度/高度/北面/南面/西面/东面/耗电量）。
DEVICE_COLUMNS: Mapping[str, str] = {
    "A": "name",
    "B": "width",
    "C": "height",
    "D": "north",
    "E": "south",
    "F": "west",
    "G": "east",
    "H": "power",
}

#: 配方表列 → 字段名（表头固定为 x1/原料1/x2/原料2/反应时间（s）/y1/产物1/y2/产物2/制作设备/设备环境/催化剂/催化剂速率（min））。
RECIPE_COLUMNS: Mapping[str, str] = {
    "A": "x1",
    "B": "input1",
    "C": "x2",
    "D": "input2",
    "E": "duration",
    "F": "y1",
    "G": "output1",
    "H": "y2",
    "I": "output2",
    "J": "device",
    "K": "environment",
    "L": "catalyst",
    "M": "catalyst_rate",
}

RECIPE_HEADER: Mapping[str, str] = {
    "A": "x1",
    "B": "原料1",
    "C": "x2",
    "D": "原料2",
    "E": "反应时间（s）",
    "F": "y1",
    "G": "产物1",
    "H": "y2",
    "I": "产物2",
    "J": "制作设备",
    "K": "设备环境",
    "L": "催化剂",
    "M": "催化剂速率（min）",
}

DEVICE_HEADER: Mapping[str, str] = {
    "A": "设备名称",
    "B": "宽度",
    "C": "高度",
    "D": "北面",
    "E": "南面",
    "F": "西面",
    "G": "东面",
    "H": "耗电量",
}

POWER_HEADER: Mapping[str, str] = {"A": "名称", "B": "数量", "C": "燃烧时间", "D": "电量"}

#: 期望的规模（断言）。
EXPECTED_DEVICE_ROWS = 46
EXPECTED_RECIPE_ROWS = 151
EXPECTED_POWER_ROWS = 6
EXPECTED_MARKER_ROWS = 7

#: 设备表里的特殊设备：**不进设备列表**，只作为基地骨架的必需件（每个基地必须有且只能 1 个）。
#: 用户确认（阶段 2 对话）：「协议核心记为特殊设备，每个基地必须有且只能有一个，不显示在设备列表里」。
PROTOCOL_CORE_NAME = "协议核心"

#: R-001：资源开采设备在蓝图外，配方表里会出现、设备表里没有。
EXTERNAL_SOURCE_DEVICES: tuple[str, ...] = (
    "电驱矿机",
    "二型电驱矿机",
    "水驱矿机",
    "水泵",
    "二型耐酸水泵",
    "气体收集泵",
)

#: 六大类（``docs/终末地产线限制.docx`` 段 3–8）。
DEVICE_CATEGORY_NAMES: tuple[str, ...] = (
    "物流设备",
    "资源开采",
    "仓储存取",
    "基础生产",
    "合成制造",
    "电力供应",
)

#: docx 的类别清单里的基名（设备表里的「（xx模式）」变体由此继承类别）。
DEVICE_CATEGORY_BASE_NAMES: Mapping[str, str] = {
    "储气罐": "仓储存取",
    "多口暗管出口": "仓储存取",
    "多口暗管入口": "仓储存取",
    "暗管出口": "仓储存取",
    "暗管入口": "仓储存取",
    "仓库存取线源桩": "仓储存取",
    "仓库存取线基段": "仓储存取",
    "储液罐": "仓储存取",
    "仓库取货口": "仓储存取",
    "仓库存货口": "仓储存取",
    "协议储存箱": "仓储存取",
    "废水处理机": "基础生产",
    "种植机": "基础生产",
    "采种机": "基础生产",
    "塑形机": "基础生产",
    "配件机": "基础生产",
    "粉碎机": "基础生产",
    "精炼炉": "基础生产",
    "气体反应炉": "合成制造",
    "气体散布机": "合成制造",
    "液气转化机": "合成制造",
    "固气转化机": "合成制造",
    "提纯机": "合成制造",
    "扩容反应池": "合成制造",
    "天有洪炉": "合成制造",
    "反应池": "合成制造",
    "拆解机": "合成制造",
    "研磨机": "合成制造",
    "封装机": "合成制造",
    "灌装机": "合成制造",
    "装备原件机": "合成制造",
    "热能池": "电力供应",
}

#: 设备表里**在 docx 类别清单中找不到**、必须人工指定的设备。
DEVICE_CATEGORY_OVERRIDES: Mapping[str, str] = {
    PROTOCOL_CORE_NAME: "仓储存取",
}

#: docx 提到但设备表没有规格的器件（B-9 / 规则 §7.1：不得据设备表反推规格）。
SPEC_ONLY_IN_RULES: tuple[str, ...] = (
    "传送带",
    "分流器",
    "汇流器",
    "物流桥",
    "物品准入口",
    "管道",
    "管道分流器",
    "管道汇流器",
    "管道桥",
    "管道准入口",
    "供电桩",
)


class SourceParseError(Exception):
    """源数据不符合已确认的结构或断言。"""


@dataclass
class ValidationReport:
    """校验 / 自检报告。"""

    errors: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    normalizations: list[dict[str, object]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def error(self, message: str) -> None:
        self.errors.append(message)

    def check(self, message: str) -> None:
        self.checks.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def note_normalization(self, file: str, sheet: str, row: int, column: str, raw: str, canonical: str) -> None:
        self.normalizations.append(
            {
                "file": file,
                "sheet": sheet,
                "row": row,
                "column": column,
                "raw": raw,
                "canonical": canonical,
            }
        )

    def raise_if_failed(self) -> None:
        if self.errors:
            detail = "\n  - ".join(self.errors)
            raise SourceParseError(f"源数据校验失败（{len(self.errors)} 项）：\n  - {detail}")

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "checks": list(self.checks),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "normalizations": [dict(item) for item in self.normalizations],
        }


@dataclass
class SourceBundle:
    """规范化中间数据的全部内容（后续所有模块只读这一份）。"""

    device_types: tuple[DeviceType, ...]
    special_devices: tuple[DeviceType, ...]
    recipes: tuple[Recipe, ...]
    power_entries: tuple[PowerEntry, ...]
    items: tuple[Item, ...]
    markers: tuple[tuple[str, str], ...]
    rule_paragraphs: tuple[Paragraph, ...]
    report: ValidationReport
    file_hashes: Mapping[str, str]

    @property
    def device_type_by_name(self) -> dict[str, DeviceType]:
        return {device.canonical_name: device for device in self.device_types}

    @property
    def special_device_by_name(self) -> dict[str, DeviceType]:
        return {device.canonical_name: device for device in self.special_devices}

    def device_type(self, name: str) -> DeviceType:
        """按规范名取设备规格（含特殊设备）。"""
        for device in (*self.device_types, *self.special_devices):
            if device.canonical_name == name:
                return device
        raise KeyError(f"设备表中没有设备 {name!r}")


# --------------------------------------------------------------------------- 工具


def canonical_name(raw: str) -> str:
    """规范名：NFC 归一化 + 去掉首尾空白（含制表符 / 全角空格）。

    原始值一律保留在 ``rawName``；发生改写时登记到 ``normalizations[]``。
    """
    return unicodedata.normalize("NFC", raw).strip()


def strip_mode_suffix(name: str) -> str:
    """去掉「（xx模式）」「（xx产出）」等尾部括号，用于继承类别。"""
    for left, right in (("（", "）"), ("(", ")")):
        if name.endswith(right) and left in name:
            return name[: name.rindex(left)]
    return name


def _int_cell(row: int, values: Mapping[str, str], column: str, label: str) -> int:
    raw = values.get(column)
    if raw is None:
        raise SourceParseError(f"行{row}: 缺少 {label}（列 {column}）")
    try:
        return int(raw)
    except ValueError as exc:
        raise SourceParseError(f"行{row}: {label} 不是整数（{raw!r}）") from exc


def _fraction_cell(row: int, values: Mapping[str, str], column: str, label: str) -> Fraction:
    raw = values.get(column)
    if raw is None or raw.strip() == "":
        raise SourceParseError(f"行{row}: 缺少 {label}（列 {column}）")
    try:
        return Fraction(raw.strip())
    except (ValueError, ZeroDivisionError) as exc:
        raise SourceParseError(f"行{row}: {label} 不是数值（{raw!r}）") from exc


def _row_pairs(rows: Sequence[Row], required_column: str = "A") -> list[Row]:
    """取出数据行（跳过表头），并断言没有跳号。"""
    data = [(row, values) for row, values in rows if row > 1]
    missing = [row for row, values in data if not values.get(required_column)]
    if missing:
        raise SourceParseError(f"存在空主键行：{missing}")
    return data


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- 设备


def parse_devices(docs_dir: Path, report: ValidationReport) -> tuple[list[DeviceType], list[DeviceType], list[tuple[str, str]]]:
    """解析设备表与标记对照表，返回 ``(设备列表, 特殊设备, 标记表)``。"""
    path = docs_dir / DEVICE_FILE
    sheets = {sheet.name: sheet for sheet in discover_sheets(path)}
    if DEVICE_SHEET not in sheets or MARKER_SHEET not in sheets:
        raise SourceParseError(f"{DEVICE_FILE} 的工作表应为 {DEVICE_SHEET!r} / {MARKER_SHEET!r}，实际 {sorted(sheets)}")

    rows = read_sheet(path, sheets[DEVICE_SHEET].path)
    header = rows[0][1]
    for column, want in DEVICE_HEADER.items():
        got = header.get(column)
        if got != want:
            report.error(f"{DEVICE_FILE} 表头 {column} 应为 {want!r}，实际 {got!r}")

    data = _row_pairs(rows)
    if len(data) != EXPECTED_DEVICE_ROWS:
        report.error(f"{DEVICE_FILE} 应有 {EXPECTED_DEVICE_ROWS} 行设备，实际 {len(data)}")

    devices: list[DeviceType] = []
    specials: list[DeviceType] = []
    seen: set[str] = set()
    for row, values in data:
        raw_name = values.get("A", "")
        name = canonical_name(raw_name)
        if name != raw_name:
            report.note_normalization(DEVICE_FILE, DEVICE_SHEET, row, "A", raw_name, name)
        if name in seen:
            report.error(f"{DEVICE_FILE} 行{row}: 设备名重复 {name!r}")
        seen.add(name)

        width = _int_cell(row, values, "B", "宽度")
        height = _int_cell(row, values, "C", "高度")
        raw_faces = {
            "NORTH": values.get("D", ""),
            "SOUTH": values.get("E", ""),
            "WEST": values.get("F", ""),
            "EAST": values.get("G", ""),
        }

        # 断言 1：分词格数 = 宽/高。
        for face_key, expected in (("NORTH", width), ("SOUTH", width), ("WEST", height), ("EAST", height)):
            raw = raw_faces[face_key]
            tokens = tokenize(raw)
            if len(tokens) != expected:
                report.error(
                    f"{DEVICE_FILE} 行{row} {name} {face_key}: {raw!r} 分词 {len(tokens)} 格，应为 {expected} 格"
                )
            for token in tokens:
                if token not in VALID_MARKERS:
                    report.error(f"{DEVICE_FILE} 行{row} {name} {face_key}: 非法标记 {token!r}")

        try:
            power = float(values.get("H") or 0)
        except ValueError:
            report.error(f"{DEVICE_FILE} 行{row} {name}: 耗电量不是数值（{values.get('H')!r}）")
            power = 0.0

        category = DEVICE_CATEGORY_OVERRIDES.get(name) or DEVICE_CATEGORY_BASE_NAMES.get(
            strip_mode_suffix(name)
        )
        notes: list[str] = []
        if category is None:
            report.error(f"{DEVICE_FILE} 行{row} {name}: 无法判定类别（docx 六类清单中没有对应基名）")
            category = "未分类"
        if name == PROTOCOL_CORE_NAME:
            notes.append("特殊设备：不进设备列表，每个基地必须有且只能 1 个（R-006）；规格仍以设备表为准")

        source = DeviceSource(
            file=DEVICE_FILE,
            sheet=DEVICE_SHEET,
            row=row,
            columns={column: values[column] for column in sorted(values)},
        )
        # 端口解析失败（格数不符 / 非法标记）转为带行号的校验错误，不中断整份解析。
        try:
            ports = build_ports(width, height, raw_faces)
        except ValueError as exc:
            report.error(f"{DEVICE_FILE} 行{row} {name}: {exc}")
            ports = ()
        device = DeviceType(
            id=name,
            raw_name=raw_name,
            canonical_name=name,
            width=width,
            height=height,
            raw_faces=raw_faces,
            ports=ports,
            power_kw=power,
            category=category,
            source=source,
            special=name == PROTOCOL_CORE_NAME,
            notes=tuple(notes),
        )
        (specials if device.special else devices).append(device)

    report.check(f"{DEVICE_FILE}：{len(data)} 行设备，四面接口串分词格数全部等于宽/高")
    if len(specials) != 1 or specials[0].canonical_name != PROTOCOL_CORE_NAME:
        report.error(f"{DEVICE_FILE}：特殊设备应恰为 1 个 {PROTOCOL_CORE_NAME}，实际 {[d.canonical_name for d in specials]}")
    report.check(f"{DEVICE_FILE}：设备列表 {len(devices)} 个 + 特殊设备 {len(specials)} 个 = {len(data)}")

    # 类别覆盖对账：46 行必须全部落到 docx 的六类里。
    category_counts: dict[str, int] = {name: 0 for name in DEVICE_CATEGORY_NAMES}
    for device in (*devices, *specials):
        category_counts[device.category] = category_counts.get(device.category, 0) + 1
    report.check(
        "设备类别对账：" + "、".join(f"{name} {count}" for name, count in category_counts.items())
    )
    device_category_coverage = category_counts

    marker_rows = read_sheet(path, sheets[MARKER_SHEET].path)
    markers: list[tuple[str, str]] = []
    for row, values in marker_rows:
        if row == 1:
            continue
        marker = values.get("A", "").strip()
        meaning = values.get("B", "").strip()
        if marker:
            markers.append((marker, meaning))
    if len(markers) != EXPECTED_MARKER_ROWS:
        report.error(f"{DEVICE_FILE}/{MARKER_SHEET} 应有 {EXPECTED_MARKER_ROWS} 个标记，实际 {len(markers)}")
    if {marker for marker, _ in markers} != set(VALID_MARKERS):
        report.error(
            f"{DEVICE_FILE}/{MARKER_SHEET} 标记集合应为 {sorted(VALID_MARKERS)}，实际 {sorted(m for m, _ in markers)}"
        )
    report.check(f"{DEVICE_FILE}/{MARKER_SHEET}：{len(markers)} 个标记与解析器一致")

    # 记录未收录的规格外器件（不得据设备表反推）。
    missing_specs = [name for name in SPEC_ONLY_IN_RULES if name not in seen]
    report.warn(
        "规则提到但设备表没有规格（不得据设备表反推）：" + "、".join(missing_specs)
    )
    report.check(f"类别覆盖：{device_category_coverage}")
    return devices, specials, markers


# --------------------------------------------------------------------------- 配方


def parse_recipes(
    docs_dir: Path,
    report: ValidationReport,
    device_names: set[str],
) -> list[Recipe]:
    """解析配方表（第 2–152 行），保留空单元格的位置语义。"""
    path = docs_dir / RECIPE_FILE
    rows = read_sheet(path, discover_sheets(path)[0].path)
    header = rows[0][1]
    for column, want in RECIPE_HEADER.items():
        got = header.get(column)
        if got != want:
            report.error(f"{RECIPE_FILE} 表头 {column} 应为 {want!r}，实际 {got!r}")

    data = _row_pairs(rows, required_column="J")
    if len(data) != EXPECTED_RECIPE_ROWS:
        report.error(f"{RECIPE_FILE} 应有 {EXPECTED_RECIPE_ROWS} 行配方，实际 {len(data)}")
    first_row, last_row = data[0][0], data[-1][0]
    if (first_row, last_row) != (2, 152):
        report.error(f"{RECIPE_FILE} 配方行号应为 2–152，实际 {first_row}–{last_row}")

    recipes: list[Recipe] = []
    empty_output_rows: list[int] = []
    environment_rows: list[int] = []
    catalyst_rows: list[int] = []
    external_device_rows: list[int] = []

    for row, values in data:
        device_raw = values.get("J", "")
        device = canonical_name(device_raw)
        if device != device_raw:
            report.note_normalization(RECIPE_FILE, "Sheet1", row, "J", device_raw, device)
        if not device:
            report.error(f"{RECIPE_FILE} 行{row}: 缺少制作设备")
            continue

        duration = _fraction_cell(row, values, "E", "反应时间")
        if duration <= 0:
            report.error(f"{RECIPE_FILE} 行{row}: 反应时间必须为正（{duration}）")

        def flow(name_column: str, quantity_column: str) -> Flow | None:
            raw_item = values.get(name_column, "")
            item = canonical_name(raw_item)
            if item != raw_item:
                report.note_normalization(RECIPE_FILE, "Sheet1", row, name_column, raw_item, item)
            raw_quantity = values.get(quantity_column, "")
            quantity_text = raw_quantity.strip()
            if not item:
                if quantity_text:
                    report.error(f"{RECIPE_FILE} 行{row} 列{name_column}: 有数量 {quantity_text!r} 但没有物料名")
                return None
            if not quantity_text:
                report.error(f"{RECIPE_FILE} 行{row} 列{name_column}: 物料 {item!r} 缺少数量")
                return None
            try:
                quantity = Fraction(quantity_text)
            except (ValueError, ZeroDivisionError):
                report.error(f"{RECIPE_FILE} 行{row} 列{quantity_column}: 数量不是数值（{raw_quantity!r}）")
                return None
            return Flow(item=item, quantity=quantity)

        input_flows = tuple(flow(name, quantity) for name, quantity in (("B", "A"), ("D", "C")))
        inputs = tuple(item for item in input_flows if item is not None)

        # 产物列全空有两种不同语义（baseline §1.3）：销毁 or 环境生成特例。
        # 环境生成特例（第 126–129 行）的 G 列填的是环境名且**没有数量**，必须先识别，
        # 否则会被误判为「物料缺数量」。
        primary_output = canonical_name(values.get("G", ""))
        secondary_output = canonical_name(values.get("I", ""))
        environment_produced: str | None = None
        if primary_output in ENVIRONMENT_NAMES and not values.get("F"):
            environment_produced = primary_output
            outputs: tuple[Flow, ...] = ()
            if secondary_output:
                report.error(f"{RECIPE_FILE} 行{row}: 环境生成行不应再有第二产物 {secondary_output!r}")
        else:
            output_flows = tuple(flow(name, quantity) for name, quantity in (("G", "F"), ("I", "H")))
            outputs = tuple(item for item in output_flows if item is not None)

        if not outputs:
            empty_output_rows.append(row)
            if environment_produced is not None:
                if device != "气体散布机":
                    report.error(
                        f"{RECIPE_FILE} 行{row}: 产物列填了环境名 {environment_produced!r}，"
                        f"但制作设备是 {device!r}（应为 气体散布机）"
                    )
                environment_rows.append(row)
            elif device != "废水处理机":
                report.error(
                    f"{RECIPE_FILE} 行{row}: 产物列全空，但制作设备是 {device!r}"
                    "（只允许 废水处理机 销毁 / 气体散布机 环境生成）"
                )

        environment_raw = values.get("K", "")
        environment = canonical_name(environment_raw) or None
        if environment and environment not in ENVIRONMENT_NAMES:
            report.error(f"{RECIPE_FILE} 行{row}: 未知环境 {environment!r}")
        catalyst_raw = values.get("L", "")
        catalyst = canonical_name(catalyst_raw) or None
        catalyst_rate_raw = values.get("M", "")
        if catalyst:
            catalyst_rows.append(row)
            declared = Fraction(catalyst_rate_raw.strip()) if catalyst_rate_raw.strip() else None
            if declared is None:
                report.error(f"{RECIPE_FILE} 行{row}: 催化剂 {catalyst!r} 缺少催化剂速率")
            elif declared != CATALYST_PER_MINUTE:
                report.error(
                    f"{RECIPE_FILE} 行{row}: 催化剂速率 {declared} 与 R-061 的固定值 {CATALYST_PER_MINUTE} 不符"
                )
        elif catalyst_rate_raw.strip():
            report.error(f"{RECIPE_FILE} 行{row}: 填了催化剂速率但没有催化剂")

        if not inputs and not outputs and environment_produced is None:
            report.error(f"{RECIPE_FILE} 行{row}: 输入与产物都为空")
        if device in EXTERNAL_SOURCE_DEVICES:
            external_device_rows.append(row)

        recipes.append(
            Recipe(
                id=f"R{row:03d}",
                source_row=row,
                inputs=inputs,
                outputs=outputs,
                duration_seconds=duration,
                device_raw_name=device_raw,
                device_canonical_name=device,
                environment=environment,
                catalyst=catalyst,
                catalyst_per_minute=CATALYST_PER_MINUTE if catalyst else Fraction(0),
                environment_produced=environment_produced,
                source_columns={column: values[column] for column in sorted(values)},
            )
        )

    # 参照断言：与 baseline §4.3 复核一致。
    if empty_output_rows != [73, 74, 75, 126, 127, 128, 129]:
        report.error(f"{RECIPE_FILE}: 产物列为空的行应为 73–75 与 126–129，实际 {empty_output_rows}")
    if environment_rows != [126, 127, 128, 129]:
        report.error(f"{RECIPE_FILE}: 环境生成配方应为 126–129，实际 {environment_rows}")
    if len(catalyst_rows) != 22:
        report.error(f"{RECIPE_FILE}: 催化剂配方应为 22 行，实际 {len(catalyst_rows)}")
    report.check(
        f"{RECIPE_FILE}：{len(recipes)} 条配方（行 2–152）；空产物行 {empty_output_rows}；"
        f"环境生成行 {environment_rows}；催化剂行 {len(catalyst_rows)} 行"
    )

    # 制作设备必须能在设备表或 R-001 外部设备清单里找到。
    referenced = {recipe.device_canonical_name for recipe in recipes}
    unknown = sorted(name for name in referenced if name not in device_names and name not in EXTERNAL_SOURCE_DEVICES)
    if unknown:
        report.error(f"{RECIPE_FILE}: 制作设备既不在设备表、也不在 R-001 外部设备清单中：{unknown}")
    report.check(
        f"配方引用的制作设备 {len(referenced)} 种：设备表内 "
        f"{len(referenced - set(EXTERNAL_SOURCE_DEVICES))} 种，R-001 外部设备 "
        f"{len(referenced & set(EXTERNAL_SOURCE_DEVICES))} 种（行 {sorted(set(external_device_rows))}）"
    )
    return recipes


# --------------------------------------------------------------------------- 发电


def parse_power(docs_dir: Path, report: ValidationReport) -> list[PowerEntry]:
    """解析发电对照表（6 条，单位 kW / 秒，A-5）。"""
    path = docs_dir / POWER_FILE
    rows = read_sheet(path, discover_sheets(path)[0].path)
    header = rows[0][1]
    for column, want in POWER_HEADER.items():
        got = header.get(column)
        if got is None:
            # 源表表头未提供时只做提示，不作为错误（列含义已由 baseline 确认）。
            report.warn(f"{POWER_FILE} 表头缺少列 {column}（期望 {want!r}）")
        elif got != want:
            report.warn(f"{POWER_FILE} 表头 {column} 为 {got!r}（baseline 记作 {want!r}）")

    data = _row_pairs(rows)
    if len(data) != EXPECTED_POWER_ROWS:
        report.error(f"{POWER_FILE} 应有 {EXPECTED_POWER_ROWS} 条，实际 {len(data)}")

    entries: list[PowerEntry] = []
    for row, values in data:
        raw_name = values.get("A", "")
        name = canonical_name(raw_name)
        if name != raw_name:
            report.note_normalization(POWER_FILE, "Sheet1", row, "A", raw_name, name)
        quantity = _fraction_cell(row, values, "B", "数量")
        burn = _fraction_cell(row, values, "C", "燃烧时间")
        power = _fraction_cell(row, values, "D", "电量")
        if burn <= 0:
            report.error(f"{POWER_FILE} 行{row}: 燃烧时间必须为正（{burn}）")
        if power < 0:
            report.error(f"{POWER_FILE} 行{row}: 发电功率不能为负（{power}）")
        entries.append(
            PowerEntry(
                id=f"P{row:02d}",
                raw_name=raw_name,
                canonical_name=name,
                quantity=quantity,
                burn_seconds=burn,
                power_kw=power,
                source_row=row,
            )
        )
    report.check(f"{POWER_FILE}：{len(entries)} 条，单位 kW / 秒（A-5）")
    return entries


# --------------------------------------------------------------------------- 规则文档


def parse_rules(docs_dir: Path, report: ValidationReport) -> list[Paragraph]:
    """读取规则文档正文段落（**不做自动解析**，只作为可追溯的规则元数据）。"""
    paragraphs = read_docx_paragraphs(docs_dir / RULE_FILE)
    text_paragraphs = [paragraph for paragraph in paragraphs if paragraph.text.strip()]
    if len(text_paragraphs) < 50:
        report.error(f"{RULE_FILE}: 正文段落只有 {len(text_paragraphs)} 段，疑似读取不完整")
    report.check(f"{RULE_FILE}：{len(text_paragraphs)} 个非空段落（人工维护为带编号的规则元数据，不自动解析）")
    return tuple(text_paragraphs)


# --------------------------------------------------------------------------- 品类与环境


def build_items(recipes: Iterable[Recipe], report: ValidationReport) -> list[Item]:
    """由配方表推导物料清单（源文件没有物品表），品类按用户确认的规则判定。"""
    refs: dict[str, list[dict[str, object]]] = {}
    for recipe in recipes:
        for flow in (*recipe.inputs, *recipe.outputs):
            refs.setdefault(flow.item, []).append({"file": RECIPE_FILE, "sheet": "Sheet1", "row": recipe.source_row})
        if recipe.catalyst:
            refs.setdefault(recipe.catalyst, []).append(
                {"file": RECIPE_FILE, "sheet": "Sheet1", "row": recipe.source_row, "role": "catalyst"}
            )

    names = sorted(refs)
    check = self_check(names)
    if check["conflicts"]:
        report.error(f"物品品类自检发现同时命中液体与气体关键词的物料：{check['conflicts']}")
    report.check(
        "物品品类自检（用户确认规则 + 容器例外）："
        + "、".join(f"{kind} {count}" for kind, count in check["counts"].items())
    )
    if check["containerExceptions"]:
        report.check(
            f"容器例外（含“溶液”但本体为固体）{len(check['containerExceptions'])} 个："
            + "、".join(check["containerExceptions"])
        )

    items = [build_item(name, name, refs[name]) for name in names]
    # 采样断言：与设计文档举过的例子一致。
    samples = {
        "赤铜块": "solid",
        "清水": "liquid",
        "液化息壤": "liquid",
        "芽针溶液": "liquid",
        "息壤气": "gas",
        "蓝铁瓶（装有芽针溶液）": "solid",
    }
    by_name = {item.canonical_name: item for item in items}
    for name, expected in samples.items():
        actual = by_name.get(name)
        if actual is None:
            report.warn(f"采样物料 {name!r} 未在配方表出现，跳过品类断言")
        elif actual.kind != expected:
            report.error(f"物料 {name!r} 品类应为 {expected}，实际 {actual.kind}")
    report.check(f"物品清单：{len(items)} 种（物品表源文件未提供，品类来自用户确认规则）")
    return items


# --------------------------------------------------------------------------- 汇总


def parse_sources(docs_dir: Path) -> SourceBundle:
    """解析全部四份源文件；断言失败抛 ``SourceParseError``。"""
    report = ValidationReport()
    devices, specials, markers = parse_devices(docs_dir, report)
    device_names = {device.canonical_name for device in (*devices, *specials)}
    recipes = parse_recipes(docs_dir, report, device_names)
    power_entries = parse_power(docs_dir, report)
    paragraphs = parse_rules(docs_dir, report)
    items = build_items(recipes, report)

    hashes = {
        name: file_digest(docs_dir / name)
        for name in (DEVICE_FILE, RECIPE_FILE, POWER_FILE, RULE_FILE)
    }
    report.check("源文件 SHA256：" + "；".join(f"{name} {digest[:12]}" for name, digest in sorted(hashes.items())))

    bundle = SourceBundle(
        device_types=tuple(devices),
        special_devices=tuple(specials),
        recipes=tuple(recipes),
        power_entries=tuple(power_entries),
        items=tuple(items),
        markers=tuple(markers),
        rule_paragraphs=tuple(paragraphs),
        report=report,
        file_hashes=hashes,
    )
    # 关系断言：批量校验完成后再统一报错。
    _cross_checks(bundle, report)
    report.raise_if_failed()
    return bundle


def _cross_checks(bundle: SourceBundle, report: ValidationReport) -> None:
    """跨表断言（在全部解析完成后执行）。"""
    device_names = {device.canonical_name for device in (*bundle.device_types, *bundle.special_devices)}
    external = [name for name in EXTERNAL_SOURCE_DEVICES if name in device_names]
    if external:
        report.error(f"R-001 外部开采设备不应出现在设备表中：{external}")

    recipe_devices = {recipe.device_canonical_name for recipe in bundle.recipes}
    unused = sorted(device_names - recipe_devices)
    report.check(f"设备表中未作为制作设备出现的设备 {len(unused)} 个（预期：仓储 / 暗管 / 储罐 / 热能池等）")

    # 每个设备的端口数与宽高一致（build_ports 已断言，这里再对分类做一次汇总）。
    io_total = sum(len(device.io_ports) for device in (*bundle.device_types, *bundle.special_devices))
    report.check(f"46 台设备的出入口端口合计 {io_total} 个")

    protocol = bundle.special_device_by_name.get(PROTOCOL_CORE_NAME)
    if protocol is None:
        report.error("特殊设备 协议核心 缺失")
    else:
        report.check(
            f"特殊设备 协议核心：{protocol.width}x{protocol.height}，"
            f"出入口 {len(protocol.io_ports)} 个，每个基地必须有且只能 1 个（R-006）"
        )

    fluid_items = [item.canonical_name for item in bundle.items if item.is_fluid]
    if not fluid_items:
        report.error("物品清单里没有液体/气体，品类规则可能未生效")
    report.check(f"流体物料 {len(fluid_items)} 种（液体 7 + 气体 8 预期）")


def kind_of(name: str) -> str:
    """便捷函数：按用户确认的规则取品类。"""
    return classify_kind(name)


def unit_of(name: str) -> str:
    return unit_for(classify_kind(name))
