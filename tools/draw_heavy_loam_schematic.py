"""重息壤模拟产线示意图（SVG）。

按 `tools/plan_throughput.py` 的展开结果绘制，用来和实机产线做结构对比。
输出到 `tools/out/images/重息壤模拟产线.svg`。

诚实声明：图中台数来自**树形展开**，其物料平衡尚未闭合（见 `tools/out/plan_output.txt`
的审计：荞花 −21.00、气态赤铜 −15.00、砂叶 −7.00 /min）。因此本图是**结构示意图**，
不是可直接施工的蓝图。台数标注带 `~` 前缀。

用法：.venv\\Scripts\\python.exe tools\\draw_heavy_loam_schematic.py
"""

from __future__ import annotations

import sys
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent / "out" / "images"

W, H = 1820, 1330
BG = "#f8fafc"
GRID = "#e2e8f0"
BOX_FILL = "#ffffff"
BOX_STROKE = "#334155"
ACCENT = "#0369a1"      # 主物流
CATALYST = "#b45309"    # 催化剂
LOOP = "#b91c1c"        # 循环/未闭合
EXTERNAL = "#0f766e"    # 蓝图外来源
FINAL = "#7c3aed"

# name, row, device, units, x, y, w, h
NODES = [
    # 农业环（种植/采种自持）
    ("荞花/砂叶\n种植+采种环", "行61/63/67/69", "种植机+采种机", "~0.5", 60, 1035, 190, 86),
    ("荞花粉末", "行41", "粉碎机", "~1.9", 320, 940, 150, 70),
    ("砂叶粉末", "行43", "粉碎机", "~0.4", 320, 1120, 150, 70),
    ("细磨荞花粉末", "行109", "研磨机", "~1.4", 530, 940, 160, 70),
    ("致密碳粉末", "行32", "精炼炉", "~1.4", 750, 940, 150, 70),
    ("稳定碳块", "行18", "精炼炉", "~1.4", 960, 940, 150, 70),
    ("息壤", "行119", "天有洪炉", "~0.7", 1170, 940, 150, 70),
    ("液化息壤", "行113", "反应池", "~0.2", 1170, 1120, 150, 70),
    # 气相主干
    ("息壤气", "行6", "气体收集泵", "外部", 1170, 300, 150, 66),
    ("重息壤气", "行124", "提纯机（气体模式）", "1.00", 900, 300, 180, 74),
    ("重息壤", "行149", "固气转化机（固体产出）", "1.00", 560, 300, 210, 74),
    # 分离芯支链
    ("惰气", "行5", "气体收集泵", "外部", 60, 300, 150, 60),
    ("赤铜块", "行150", "固气转化机（固体产出）", "~0.5", 60, 420, 190, 70),
    ("赤铜耐压罐", "行60", "塑形机（气体模式）", "~0.5", 300, 420, 180, 70),
    ("分离芯", "行103", "封装机", "~0.5", 530, 420, 160, 70),
    # 气态赤铜回环
    ("气态赤铜", "行135", "液气转化机（气体产出）", "~0.5", 60, 620, 210, 70),
    ("赤铜溶液", "行141", "液气转化机（液体产出）", "~0.5", 320, 620, 210, 70),
]

FINAL_BOX = ("重息壤", "12/min → 赫铜/灼铜装备原件", 560, 200, 210, 74)


def esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def node_svg(name: str, row: str, device: str, units: str, x: int, y: int,
             w: int, h: int, stroke: str = BOX_STROKE, fill: str = BOX_FILL) -> str:
    parts = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="2"/>',
        f'<text x="{x + w / 2:.0f}" y="{y + 22}" text-anchor="middle" font-family="sans-serif" '
        f'font-size="15" font-weight="700" fill="#0f172a">{esc(name.splitlines()[0])}</text>',
    ]
    if "\n" in name:
        parts.append(
            f'<text x="{x + w / 2:.0f}" y="{y + 40}" text-anchor="middle" font-family="sans-serif" '
            f'font-size="13" font-weight="700" fill="#0f172a">{esc(name.splitlines()[1])}</text>'
        )
    offset = 56 if "\n" in name else 40
    parts.append(
        f'<text x="{x + w / 2:.0f}" y="{y + offset}" text-anchor="middle" font-family="sans-serif" '
        f'font-size="11.5" fill="#475569">{esc(device)}</text>'
    )
    parts.append(
        f'<text x="{x + w / 2:.0f}" y="{y + offset + 16}" text-anchor="middle" font-family="sans-serif" '
        f'font-size="11.5" fill="#64748b">{esc(row)} · {esc(units)} 台</text>'
    )
    return "".join(parts)


def arrow(x1: int, y1: int, x2: int, y2: int, color: str = ACCENT,
          dash: str = "", label: str = "") -> str:
    d = f' stroke-dasharray="{dash}"' if dash else ""
    parts = [
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
        f'stroke-width="2.4" marker-end="url(#arrow)"{d}/>'
    ]
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        parts.append(
            f'<text x="{mx:.0f}" y="{my - 6:.0f}" text-anchor="middle" font-family="sans-serif" '
            f'font-size="11.5" font-weight="700" fill="{color}">{esc(label)}</text>'
        )
    return "".join(parts)


def build() -> str:
    svg: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}">',
        '<defs>',
        '<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        'markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{ACCENT}"/></marker>',
        '<marker id="arrow-red" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        'markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{LOOP}"/></marker>',
        '<marker id="arrow-amber" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        'markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{CATALYST}"/></marker>',
        f'<pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">'
        f'<path d="M 20 0 L 0 0 0 20" fill="none" stroke="{GRID}" stroke-width="1"/></pattern>',
        '</defs>',
        f'<rect width="100%" height="100%" fill="{BG}"/>',
        '<rect width="100%" height="100%" fill="url(#grid)"/>',
        # 标题
        '<text x="40" y="46" font-family="sans-serif" font-size="26" font-weight="700" '
        'fill="#0f172a">重息壤模拟产线（结构示意）</text>',
        '<text x="40" y="72" font-family="sans-serif" font-size="14" fill="#475569">'
        '目标 重息壤 12/min ｜ 台数来自树形展开（带 ~ 表示尚未重平衡）｜ '
        '总额定功率 ~375 kW，天有洪炉 ~0.7 台</text>',
        '<text x="40" y="94" font-family="sans-serif" font-size="13" fill="#b91c1c">'
        '注意：本图是结构示意，不是可施工蓝图 —— 三个自持环的机组配比尚未由线性平衡求解确定</text>',
    ]

    # 分区底纹
    svg.append(f'<rect x="40" y="270" width="1740" height="260" rx="6" fill="#eef2ff" '
               f'fill-opacity="0.5" stroke="#c7d2fe"/>')
    svg.append(f'<text x="56" y="292" font-family="sans-serif" font-size="13" font-weight="700" '
               f'fill="#4338ca">气相主干（无天有洪炉参与产重息壤）</text>')
    svg.append(f'<rect x="40" y="580" width="1740" height="180" rx="6" fill="#fef3c7" '
               f'fill-opacity="0.45" stroke="#fcd34d"/>')
    svg.append(f'<text x="56" y="602" font-family="sans-serif" font-size="13" font-weight="700" '
               f'fill="#92400e">气态赤铜回环（气液双向，需闭环求解）</text>')
    svg.append(f'<rect x="40" y="900" width="1740" height="320" rx="6" fill="#dcfce7" '
               f'fill-opacity="0.45" stroke="#86efac"/>')
    svg.append(f'<text x="56" y="922" font-family="sans-serif" font-size="13" font-weight="700" '
               f'fill="#166534">植物与碳链（种植↔采种自持环）</text>')

    boxes = {n[0]: n for n in NODES}
    for name, row, device, units, x, y, w, h in NODES:
        stroke = BOX_STROKE
        if units == "外部":
            stroke = EXTERNAL
        svg.append(node_svg(name, row, device, units, x, y, w, h, stroke=stroke))

    # 最终产物
    _, label, fx, fy, fw, fh = FINAL_BOX
    svg.append(f'<rect x="{fx}" y="{fy}" width="{fw}" height="{fh}" rx="4" fill="#ede9fe" '
               f'stroke="{FINAL}" stroke-width="3"/>')
    svg.append(f'<text x="{fx + fw / 2:.0f}" y="{fy + 30}" text-anchor="middle" '
               f'font-family="sans-serif" font-size="17" font-weight="700" fill="#4c1d95">重息壤</text>')
    svg.append(f'<text x="{fx + fw / 2:.0f}" y="{fy + 52}" text-anchor="middle" '
               f'font-family="sans-serif" font-size="12" fill="#5b21b6">{esc(label)}</text>')

    # ---- 主物流箭头 ----
    # 气相主干：气体收集泵 → 提纯机 → 固气转化机（自右向左）
    svg.append(arrow(1170, 333, 1080, 333, ACCENT, label="息壤气 60/min"))
    svg.append(arrow(900, 337, 770, 337, ACCENT, label="重息壤气 30/min"))
    svg.append(arrow(560, 337, 470, 337, ACCENT, label="12/min"))
    svg.append(arrow(470, 337, 400, 337, FINAL))

    # 分离芯支链
    svg.append(arrow(250, 455, 300, 455, ACCENT, label="赤铜块 30/min"))
    svg.append(arrow(480, 455, 530, 455, ACCENT, label="赤铜耐压罐 15/min"))
    svg.append(arrow(530, 420, 610, 374, ACCENT, label="分离芯 30/min"))

    # 气态赤铜回环
    svg.append(arrow(270, 655, 320, 655, ACCENT, label="气态赤铜 15/min"))
    svg.append(arrow(320, 620, 250, 555, ACCENT, label="赤铜溶液 30/min"))
    svg.append(arrow(165, 620, 165, 490, LOOP, dash="6 4", label="−15/min 缺口"))
    svg.append(arrow(60, 420, 60, 300, ACCENT, label="惰气 15/min"))

    # 植物与碳链
    svg.append(arrow(250, 1078, 320, 1000, ACCENT, label="荞花 30/min"))
    svg.append(arrow(395, 1010, 530, 975, ACCENT, label="荞花粉末 60/min"))
    svg.append(arrow(690, 975, 750, 975, ACCENT, label="细磨荞花粉末 30/min"))
    svg.append(arrow(900, 975, 960, 975, ACCENT, label="致密碳粉末 30/min"))
    svg.append(arrow(1110, 975, 1170, 975, ACCENT, label="稳定碳块 30/min"))
    svg.append(arrow(1245, 1010, 1245, 1120, ACCENT, label="息壤 15/min"))
    svg.append(arrow(250, 1120, 320, 1155, ACCENT, label="砂叶 10/min"))
    svg.append(arrow(395, 1155, 630, 1010, ACCENT, label="砂叶粉末 30/min"))
    svg.append(arrow(1245, 940, 1245, 420, ACCENT, label="息壤气 → 见上"))
    svg.append(arrow(1245, 1120, 1400, 1120, CATALYST, label="催化剂 6/min"))

    # 自持环回箭头
    svg.append(arrow(155, 1121, 155, 1090, LOOP, dash="6 4", label="−7/min"))
    svg.append(arrow(155, 1035, 155, 1000, LOOP, dash="6 4", label="−21/min"))

    # 催化剂标注
    svg.append(arrow(1080, 300, 990, 380, CATALYST, dash="4 3", label="催化剂 6/min"))
    svg.append(arrow(1170, 1100, 1080, 1050, CATALYST, dash="4 3", label="催化剂 6/min"))

    # 图例
    lx, ly = 1400, 950
    svg.append(f'<rect x="{lx}" y="{ly}" width="330" height="200" rx="6" fill="#ffffff" '
               f'stroke="#cbd5e1"/>')
    svg.append(f'<text x="{lx + 16}" y="{ly + 26}" font-family="sans-serif" font-size="14" '
               f'font-weight="700" fill="#0f172a">图例</text>')
    items = [
        (ACCENT, "", "主物料流（实线）"),
        (CATALYST, "4 3", "催化剂 6/min·台（R-061）"),
        (LOOP, "6 4", "自持环缺口，待线性平衡重算"),
        (EXTERNAL, "", "蓝图外来源（R-001）"),
    ]
    for i, (color, dash, text) in enumerate(items):
        yy = ly + 54 + i * 30
        d = f' stroke-dasharray="{dash}"' if dash else ""
        svg.append(f'<line x1="{lx + 16}" y1="{yy}" x2="{lx + 56}" y2="{yy}" stroke="{color}" '
                   f'stroke-width="2.6"{d}/>')
        svg.append(f'<text x="{lx + 66}" y="{yy + 5}" font-family="sans-serif" font-size="12" '
                   f'fill="#334155">{esc(text)}</text>')

    # 已知缺口说明
    svg.append(f'<rect x="{lx}" y="{ly + 215}" width="330" height="150" rx="6" fill="#fef2f2" '
               f'stroke="#fca5a5"/>')
    svg.append(f'<text x="{lx + 16}" y="{ly + 241}" font-family="sans-serif" font-size="13" '
               f'font-weight="700" fill="#991b1b">审计出的净缺口</text>')
    for i, line in enumerate(["荞花　　−21.00 /min", "气态赤铜　−15.00 /min", "砂叶　　−7.00 /min"]):
        svg.append(f'<text x="{lx + 16}" y="{ly + 266 + i * 22}" font-family="monospace" '
                   f'font-size="12.5" fill="#7f1d1d">{esc(line)}</text>')
    svg.append(f'<text x="{lx + 16}" y="{ly + 340}" font-family="sans-serif" font-size="11" '
               f'fill="#991b1b">其余 18 种物料已恰好平衡</text>')

    svg.append("</svg>")
    return "".join(svg)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "重息壤模拟产线.svg"
    out_path.write_text(build(), encoding="utf-8")
    print(f"SVG 已保存：{out_path}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
