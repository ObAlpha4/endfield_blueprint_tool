"""OOXML 读取内核（不依赖 pandas / openpyxl）。

直接解压 ``.xlsx`` / ``.docx`` 并解析 XML，保证：

- 得到的是**单元格原始字符串**，不经过任何中间转录（历史上多次出现长重复串掉字符）；
- **缺失单元格不伪造**：源表按「最多两种原料 / 两种产物」设计，空单元格有结构意义，
  因此缺失的列不写进字典，而不是填成空串或 ``"0"``；
- 工作表按 ``workbook.xml`` + ``workbook.xml.rels`` 动态发现，不硬编码文件名。

设计依据：``design/domain-model.md`` §4「数据表中的空单元格具有结构意义」。
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

#: 端口标记全集：`n` 占 1 个字符，其余六种占 2 个字符。
VALID_MARKERS: tuple[str, ...] = ("si", "so", "fi", "fo", "gi", "go", "n")

#: 行数据：``(excel 行号, {列字母: 单元格原始字符串})``；缺失的列不出现在字典里。
Row = tuple[int, dict[str, str]]


@dataclass(frozen=True)
class SheetRef:
    """工作表引用：显示名 + 包内路径。"""

    name: str
    path: str


def column_letters(cell_ref: str) -> str:
    """从单元格引用（如 ``AB12``）取出列字母。"""
    return "".join(ch for ch in cell_ref if ch.isalpha())


def read_sheet(path: Path, sheet_path: str) -> list[Row]:
    """读取一张工作表，返回 ``(行号, {列字母: 原始字符串})``。

    公式单元格取缓存值（``<v>``）；共享字符串经 ``sharedStrings.xml`` 还原。
    """
    with zipfile.ZipFile(path) as archive:
        shared = _read_shared_strings(archive)
        sheet = ET.fromstring(archive.read(sheet_path))

    rows: list[Row] = []
    for row in sheet.iter(MAIN_NS + "row"):
        values: dict[str, str] = {}
        for cell in row.iter(MAIN_NS + "c"):
            column = column_letters(cell.get("r", ""))
            if cell.get("t") == "inlineStr":
                # 内联字符串：值在 `<is>` 里，没有 `<v>`。
                inline = cell.find(MAIN_NS + "is")
                text = "" if inline is None else "".join(t.text or "" for t in inline.iter(MAIN_NS + "t"))
            else:
                node = cell.find(MAIN_NS + "v")
                if node is None:
                    # 空单元格（无值）与「列不存在」在源表里同构，一律不写进字典。
                    continue
                text = node.text or ""
                if cell.get("t") == "s":
                    text = shared[int(text)]
            values[column] = text
        rows.append((int(row.get("r")), values))
    return rows


def discover_sheets(path: Path) -> list[SheetRef]:
    """按 ``workbook.xml`` 的声明顺序返回工作表（名称 + 包内路径）。"""
    with zipfile.ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {rel.get("Id"): rel.get("Target", "") for rel in rels.iter(PKG_REL_NS + "Relationship")}

    sheets: list[SheetRef] = []
    for node in workbook.iter(MAIN_NS + "sheet"):
        target = targets.get(node.get(REL_NS + "id"), "")
        if target.startswith("/"):
            sheet_path = target.lstrip("/")
        elif target.startswith("xl/"):
            sheet_path = target
        else:
            sheet_path = "xl/" + target
        sheets.append(SheetRef(name=node.get("name", ""), path=sheet_path))
    return sheets


def read_by_sheet_name(path: Path, sheet_name: str) -> list[Row]:
    """按工作表名读取，避免硬编码 ``sheet1.xml``。"""
    for ref in discover_sheets(path):
        if ref.name == sheet_name:
            return read_sheet(path, ref.path)
    raise KeyError(f"{path.name} 中没有工作表 {sheet_name!r}（现有：{[r.name for r in discover_sheets(path)]}）")


@dataclass(frozen=True)
class Paragraph:
    """Word 段落：文本 + 段落样式 id + 段内文本 run 数。"""

    index: int
    text: str
    style: str


def read_docx_paragraphs(path: Path) -> list[Paragraph]:
    """读取 docx 正文段落（含样式 id），用于人工核对的规则元数据。"""
    with zipfile.ZipFile(path) as archive:
        document = ET.fromstring(archive.read("word/document.xml"))

    paragraphs: list[Paragraph] = []
    for index, node in enumerate(document.iter(WORD_NS + "p")):
        text = "".join(t.text or "" for t in node.iter(WORD_NS + "t"))
        style = ""
        properties = node.find(WORD_NS + "pPr")
        if properties is not None:
            style_node = properties.find(WORD_NS + "pStyle")
            if style_node is not None:
                style = style_node.get(WORD_NS + "val", "")
        paragraphs.append(Paragraph(index=index, text=text, style=style))
    return paragraphs


def tokenize(port_string: str) -> list[str]:
    """端口串分词：``n`` 占 1 个字符，其余标记占 2 个字符。

    必须逐字符判断，不能按固定 2 字符切分，否则 ``nfin`` 会被切成 ``nf`` / ``in``。
    例：``sisisi`` → 3 个 ``si``；``nfinfin`` → ``n, fi, n, fi, n``。
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


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    sst = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return [
        "".join(t.text or "" for t in si.iter(MAIN_NS + "t"))
        for si in sst.iter(MAIN_NS + "si")
    ]
