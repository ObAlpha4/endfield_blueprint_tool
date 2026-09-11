"""源数据校验器：把"格数 = 宽/高"断言固化成可重复运行的检查。

背景：此前多轮 agent 在转录设备表时把长重复串（`soso…`）掉了一个字符，
导致协议核心等设备的接口格数与 9x9 对不上。此脚本直接读取 xlsx 原始 XML，
不经过任何中间转录，用来守住"格数 = 宽/高"这条不变量。

用法：
    python tests/validate_sources.py          # 从仓库根目录运行
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
VALID_MARKERS = {"si", "so", "fi", "fo", "gi", "go", "n"}

REPO_ROOT = Path(__file__).resolve().parent.parent
DEVICE_XLSX = REPO_ROOT / "docs" / "设备概述.xlsx"
RECIPE_XLSX = REPO_ROOT / "docs" / "产线配方.xlsx"
POWER_XLSX = REPO_ROOT / "docs" / "发电对照.xlsx"


def read_sheet(path: Path, sheet_file: str) -> list[tuple[int, dict[str, str]]]:
    """按行返回 {列字母: 单元格原始字符串}，直接解析 OOXML，不依赖 pandas/openpyxl。"""
    with zipfile.ZipFile(path) as z:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            sst = ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared = [
                "".join(t.text or "" for t in si.iter(MAIN + "t"))
                for si in sst.iter(MAIN + "si")
            ]
        sheet = ET.fromstring(z.read(sheet_file))

    rows: list[tuple[int, dict[str, str]]] = []
    for row in sheet.iter(MAIN + "row"):
        values: dict[str, str] = {}
        for cell in row.iter(MAIN + "c"):
            column = "".join(ch for ch in cell.get("r", "") if ch.isalpha())
            node = cell.find(MAIN + "v")
            if node is None:
                values[column] = ""
                continue
            text = node.text or ""
            if cell.get("t") == "s":
                text = shared[int(text)]
            values[column] = text
        rows.append((int(row.get("r")), values))
    return rows


def tokenize(port_string: str) -> list[str]:
    """端口分词：`n` 占 1 个字符，其余标记占 2 个字符。

    必须逐个判断，不能按固定 2 字符切分，否则 `nfin` 会被切成 `nf`、`in`。
    """
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


def check_devices() -> list[str]:
    """校验设备表：46 行，四面接口分词格数 = 宽/高，标记合法。"""
    errors: list[str] = []
    rows = read_sheet(DEVICE_XLSX, "xl/worksheets/sheet1.xml")
    data = [(r, v) for r, v in rows if r > 1 and v.get("A")]
    if len(data) != 46:
        errors.append(f"设备行数应为 46，实际 {len(data)}")

    for rnum, v in data:
        name = v.get("A", f"<row{rnum}>")
        try:
            width, height = int(v["B"]), int(v["C"])
        except (KeyError, ValueError):
            errors.append(f"row{rnum} {name}: 宽/高不是整数（{v.get('B')!r}, {v.get('C')!r}）")
            continue

        # 北/南面沿宽度展开，西/东面沿高度展开。
        for column, face, expected in (
            ("D", "北面", width),
            ("E", "南面", width),
            ("F", "西面", height),
            ("G", "东面", height),
        ):
            raw = v.get(column, "")
            tokens = tokenize(raw)
            if len(tokens) != expected:
                errors.append(
                    f"row{rnum} {name} {face}: {raw!r} 分词 {len(tokens)} 格，应为 {expected} 格"
                )
            for token in tokens:
                if token not in VALID_MARKERS:
                    errors.append(f"row{rnum} {name} {face}: 非法标记 {token!r}")
    return errors


def check_recipes() -> list[str]:
    """校验配方表：列结构、反应时间、设备名、空产物行的语义。"""
    errors: list[str] = []
    rows = read_sheet(RECIPE_XLSX, "xl/worksheets/sheet1.xml")
    header, data = rows[0][1], [(r, v) for r, v in rows if r > 1]

    expected_header = {
        "A": "x1", "B": "原料1", "C": "x2", "D": "原料2", "E": "反应时间（s）",
        "F": "y1", "G": "产物1", "H": "y2", "I": "产物2", "J": "制作设备",
        "K": "设备环境", "L": "催化剂", "M": "催化剂速率（min）",
    }
    for column, want in expected_header.items():
        if header.get(column) != want:
            errors.append(f"配方表表头 {column} 应为 {want!r}，实际 {header.get(column)!r}")

    # 已确认：产物列全空只允许出现在废水处理机（销毁）与气体散布机（环境）两类配方上。
    allowed_empty_product = {"废水处理机", "气体散布机"}
    for rnum, v in data:
        if not v.get("E"):
            errors.append(f"row{rnum}: 缺少反应时间")
        if not v.get("J"):
            errors.append(f"row{rnum}: 缺少制作设备")
        if not v.get("F") and not v.get("H"):
            device = v.get("J", "")
            if device not in allowed_empty_product:
                errors.append(f"row{rnum}: 产物列全空，但制作设备是 {device!r}")
        # 输入名与产物名同名会形成自循环边，历史上第 58 行出过这个问题。
        if v.get("B") and v.get("G") and v["B"].strip() == v["G"].strip() and not v.get("D"):
            errors.append(f"row{rnum}: 输入1 与 产物1 同名（{v['B']!r}），疑似录入错误")
    return errors


def check_power() -> list[str]:
    """校验发电表：6 条、单位数值可解析。"""
    errors: list[str] = []
    rows = read_sheet(POWER_XLSX, "xl/worksheets/sheet1.xml")
    data = [(r, v) for r, v in rows if r > 1 and v.get("A")]
    if len(data) != 6:
        errors.append(f"发电行数应为 6，实际 {len(data)}")
    for rnum, v in data:
        for column, label in (("B", "数量"), ("C", "燃烧时间"), ("D", "电量")):
            try:
                float(v[column])
            except (KeyError, ValueError):
                errors.append(f"row{rnum} {v.get('A')}: {label} 不是数值（{v.get(column)!r}）")
    return errors


def main() -> int:
    sections = (
        ("设备表 docs/设备概述.xlsx", check_devices),
        ("配方表 docs/产线配方.xlsx", check_recipes),
        ("发电表 docs/发电对照.xlsx", check_power),
    )

    total = 0
    for title, check in sections:
        errors = check()
        total += len(errors)
        if errors:
            print(f"[FAIL] {title}")
            for error in errors:
                print(f"       - {error}")
        else:
            print(f"[ OK ] {title}")

    if total:
        print(f"\n合计 {total} 项问题。")
        return 1
    print("\n全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
