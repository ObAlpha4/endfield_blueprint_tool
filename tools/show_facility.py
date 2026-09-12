"""单设备接口示意图（SVG）。

数据来源改为**解析器产出的规范化中间数据**（``data/derived/sources.json``），
不再直接用 pandas 读 xlsx（技术债清理，见 ``design/next-steps.md`` §3）。

端口排列方向遵循已确认规则：北面东→西、南面西→东、西面北→南、东面南→北
（``design/baseline-rules.md`` §1.2）；端口标记对齐到对应网格单元中心。

生成物写入 ``tools/out/images/{设备名}.svg``。

用法（从仓库根目录运行）：

    .venv\\Scripts\\python.exe -m endfield.cli build          # 先生成 sources.json
    .venv\\Scripts\\python.exe tools\\show_facility.py         # 默认两台转化机
    .venv\\Scripts\\python.exe tools\\show_facility.py --all   # 全部 46 台设备
    .venv\\Scripts\\python.exe tools\\show_facility.py 协议核心
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from html import escape
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from endfield.sources import emit  # noqa: E402

SOURCES_JSON = REPO_ROOT / "data" / "derived" / "sources.json"

#: 标记含义 → 绘图颜色（与设计文档的端口配色一致）。
KIND_COLORS = {
    "固体": "#64748b",
    "液体": "#0284c7",
    "气体": "#ea580c",
    "普通": "#cbd5e1",
    "未知": "#dc2626",
}

#: 面 → 绘图方向；``reverse`` 表示该面的 ordinal 从东/南起算（北面东→西、东面南→北）。
FACE_LAYOUT: tuple[tuple[str, str, bool], ...] = (
    ("NORTH", "north", True),
    ("SOUTH", "south", False),
    ("WEST", "west", False),
    ("EAST", "east", True),
)


@dataclass(frozen=True)
class DeviceSpec:
    """绘图所需的设备规格（来自规范化数据，不是源表）。"""

    name: str
    width: int
    height: int
    faces: dict[str, str]
    power_kw: float
    category: str

    @property
    def is_special(self) -> bool:
        return False


def load_specs(sources_path: Path = SOURCES_JSON) -> tuple[dict[str, DeviceSpec], dict[str, str]]:
    """读规范化数据，返回 ``({设备名: 规格}, {标记: 含义})``。"""
    if not sources_path.exists():
        raise FileNotFoundError(f"未找到 {sources_path}，请先运行：python -m endfield.cli build")
    document = emit.load(sources_path)
    specs: dict[str, DeviceSpec] = {}
    for row in (*document["devices"], *document["specialDevices"]):
        specs[row["canonicalName"]] = DeviceSpec(
            name=row["canonicalName"],
            width=row["width"],
            height=row["height"],
            faces=dict(row["rawFaces"]),
            power_kw=float(row["powerKw"]),
            category=row["category"],
        )
    markers = {row["marker"]: row["meaning"] for row in document["markers"]}
    return specs, markers


def tokenize(port_string: str) -> list[str]:
    """端口串分词：``n`` 占 1 字符，其余标记占 2 字符（与解析器同规则）。"""
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


def port_color(mark: str, markers: dict[str, str]) -> tuple[str, str, str]:
    """返回 ``(含义, 类别, 颜色)``。"""
    meaning = markers.get(mark)
    if meaning is None:
        return "未知端口", "未知", KIND_COLORS["未知"]
    kind = next((name for name in KIND_COLORS if name in meaning), "普通")
    return meaning, kind, KIND_COLORS[kind]


def build_legend(marks: list[str], markers: dict[str, str]) -> list[tuple[str, str]]:
    """只为当前设备实际出现的端口生成图例。"""
    legend: list[tuple[str, str]] = []
    seen: set[str] = set()
    for mark in marks:
        if mark == "n" or mark in seen:
            continue
        seen.add(mark)
        legend.append((mark, port_color(mark, markers)[0]))
    return legend


def render_svg(spec: DeviceSpec, markers: dict[str, str], scale: int = 72) -> str:
    """按设备规格渲染 SVG 文本。"""
    width, height = spec.width, spec.height
    left = 3 * scale
    top = 1 * scale
    body_width = width * scale
    body_height = height * scale
    canvas_width = (width + 6) * scale
    canvas_height = (height + 4) * scale

    svg: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_width}" height="{canvas_height}" '
        f'viewBox="0 0 {canvas_width} {canvas_height}">',
        f'<defs><pattern id="grid" width="{scale}" height="{scale}" patternUnits="userSpaceOnUse">'
        f'<path d="M {scale} 0 L 0 0 0 {scale}" fill="none" stroke="#cbd5e1" stroke-width="1"/></pattern></defs>',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<rect width="100%" height="100%" fill="url(#grid)"/>',
        f'<rect x="{left}" y="{top}" width="{body_width}" height="{body_height}" rx="2" '
        f'fill="#ffffff" fill-opacity="0.88" stroke="#334155" stroke-width="3"/>',
        f'<text x="{left + body_width / 2:.0f}" y="{top + body_height / 2 - 8:.0f}" text-anchor="middle" '
        f'font-family="sans-serif" font-size="18" font-weight="700" fill="#0f172a">{escape(spec.name)}</text>',
        f'<text x="{left + body_width / 2:.0f}" y="{top + body_height / 2 + 18:.0f}" text-anchor="middle" '
        f'font-family="sans-serif" font-size="14" fill="#64748b">尺寸：{width} × {height}</text>',
    ]

    device_marks: list[str] = []
    for face_key, direction, reverse in FACE_LAYOUT:
        ports = tokenize(spec.faces.get(face_key, ""))
        device_marks.extend(mark for mark in ports if mark != "n")
        if not any(mark != "n" for mark in ports):
            continue
        count = len(ports)
        for index, mark in enumerate(ports):
            if mark == "n":
                continue
            _, _, color = port_color(mark, markers)
            fraction = (count - index - 0.5) / count if reverse else (index + 0.5) / count
            if direction == "north":
                x, y = left + body_width * fraction, top
                tx, ty, anchor = x, y - 30, "middle"
                line = f'<line x1="{x:.1f}" y1="{y}" x2="{x:.1f}" y2="{y - 13}" stroke="{color}" stroke-width="4"/>'
            elif direction == "south":
                x, y = left + body_width * fraction, top + body_height
                tx, ty, anchor = x, y + 30, "middle"
                line = f'<line x1="{x:.1f}" y1="{y}" x2="{x:.1f}" y2="{y + 13}" stroke="{color}" stroke-width="4"/>'
            elif direction == "west":
                x, y = left, top + body_height * fraction
                tx, ty, anchor = x - 17, y + 4, "end"
                line = f'<line x1="{x}" y1="{y:.1f}" x2="{x - 13}" y2="{y:.1f}" stroke="{color}" stroke-width="4"/>'
            else:
                x, y = left + body_width, top + body_height * fraction
                tx, ty, anchor = x + 17, y + 4, "start"
                line = f'<line x1="{x}" y1="{y:.1f}" x2="{x + 13}" y2="{y:.1f}" stroke="{color}" stroke-width="4"/>'
            svg.extend(
                [
                    line,
                    f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{color}" stroke="#ffffff" stroke-width="2"/>',
                    f'<text x="{tx:.1f}" y="{ty:.1f}" text-anchor="{anchor}" font-family="sans-serif" '
                    f'font-size="12" font-weight="700" fill="{color}">{escape(mark)}</text>',
                ]
            )

    legend_x = 18
    legend_y = canvas_height - 82
    svg.append(
        f'<text x="{legend_x}" y="{legend_y - 15}" font-family="sans-serif" font-size="13" '
        f'font-weight="700" fill="#334155">端口类型</text>'
    )
    for index, (mark, label) in enumerate(build_legend(device_marks, markers)):
        x = legend_x + index * 118
        _, _, color = port_color(mark, markers)
        svg.append(f'<circle cx="{x}" cy="{legend_y}" r="5" fill="{color}"/>')
        svg.append(
            f'<text x="{x + 10}" y="{legend_y + 4}" font-family="sans-serif" font-size="11" '
            f'fill="#475569">{mark}: {label}</text>'
        )
    svg.append("</svg>")
    return "".join(svg)


def write_device(name: str, specs: dict[str, DeviceSpec], markers: dict[str, str], out_dir: Path) -> Path:
    spec = specs.get(name)
    if spec is None:
        choices = "、".join(sorted(specs))
        raise ValueError(f"未找到设备“{name}”。可选设备：{choices}")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.svg"
    path.write_text(render_svg(spec, markers), encoding="utf-8")
    return path


def main(argv: list[str]) -> int:
    out_dir = REPO_ROOT / "tools" / "out" / "images"
    specs, markers = load_specs()
    if "--all" in argv:
        names = sorted(specs)
    else:
        names = [argument for argument in argv[1:] if not argument.startswith("-")]
        if not names:
            names = ["固气转化机（气体产出）", "固气转化机（固体产出）"]
    for name in names:
        path = write_device(name, specs, markers, out_dir)
        print(f"SVG 已保存：{path}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows 控制台默认 GBK
    sys.exit(main(sys.argv))
