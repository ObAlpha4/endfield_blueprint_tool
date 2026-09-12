"""配方图与产能核算器（第二版）。

从 `docs/` 原始数据构建生产图，做以产量为驱动的树展开，再按最终机组配置做
物料平衡审计。用于验证已确认的规则，不做布局与布线。

⚠ 已知缺陷（下一版必须替换，不要在树展开上打补丁）
--------------------------------------------------
树展开**无法闭合自持环**：遇到「荞花 → 荞花种子 → 荞花」这类回环时只能截断，
导致审计出假缺口。以「重息壤 12/min」为例，当前会报三处缺口：

    荞花 −21.00 /min、气态赤铜 −15.00 /min、砂叶 −7.00 /min

其余 18 种物料恰好平衡，说明展开的**结构是对的**，只是循环上的机组配比需要
重新解算。正解是**线性物料平衡求解**（以每条配方投用台数为变量、以物料产消
平衡为方程），见 `design/next-steps.md` 步骤 3。

已固化规则
----------
R-060 天有洪炉全局 ≤ 12 台
R-061 固气/液气转化机每台固定消耗催化剂 6/min，与配方和产率无关，按净额记账
R-067 缓存格数：反应池 5 / 扩容反应池 8 / 协议储存箱 6 / 其余 = 输入物料种类数
A-2   产物列为空 = 销毁输入
A-7   每分钟配方次数 = 60 / 反应时间；多台线性叠加
R-001 资源开采设备在蓝图外，视为外部来源

用法
----
    .venv\\Scripts\\python.exe tools\\plan_throughput.py 重息壤 12 [目标函数]
    .venv\\Scripts\\python.exe tools\\plan_throughput.py 水蒸气 100 min_power

目标函数：min_devices（默认）/ min_power。结果写入 `tools/out/plan_output.txt`。
"""

from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_sources import read_sheet, RECIPE_XLSX, DEVICE_XLSX

OUT_DIR = Path(__file__).resolve().parent / "out"

# ------------------------------------------------------------------ 常量与规则

EXPLICIT_SLOTS = {"反应池": 5, "扩容反应池": 8, "协议储存箱": 6}
FIXED_CATALYST_DEVICES = {
    "固气转化机（气体产出）", "固气转化机（固体产出）",
    "液气转化机（气体产出）", "液气转化机（液体产出）",
}
FIXED_CATALYST_RATE = 6.0
HEAVEN_FURNACE = "天有洪炉"
HEAVEN_FURNACE_LIMIT = 12
POWER_BASELINE_KW = 9600.0

# R-001：蓝图外开采/采集，可直接作为外部来源
EXTERNAL_SOURCE_DEVICES = {
    "电驱矿机", "二型电驱矿机", "水驱矿机", "水泵", "二型耐酸水泵", "气体收集泵",
}

MAX_DEPTH = 40


@dataclass
class ItemFlow:
    name: str
    quantity: float


@dataclass
class Recipe:
    row: int
    inputs: list[ItemFlow]
    outputs: list[ItemFlow]
    duration: float
    device: str
    environment: str = ""
    catalyst: str = ""
    catalyst_rate: float = 0.0

    @property
    def batches_per_minute(self) -> float:
        return 60.0 / self.duration  # A-7

    @property
    def destroys_input(self) -> bool:
        return not self.outputs  # A-2

    def out_rate(self, item: str) -> float:
        return sum(f.quantity * self.batches_per_minute for f in self.outputs if f.name == item)

    def in_rate(self, item: str) -> float:
        return sum(f.quantity * self.batches_per_minute for f in self.inputs if f.name == item)

    @property
    def catalyst_per_minute(self) -> float:
        if not self.catalyst:
            return 0.0
        if self.device in FIXED_CATALYST_DEVICES:
            return FIXED_CATALYST_RATE  # R-061：与配方、产率无关
        return self.catalyst_rate

    @property
    def slots(self) -> int:
        if self.device in EXPLICIT_SLOTS:
            return EXPLICIT_SLOTS[self.device]
        return len(self.inputs)  # R-067

    def label(self) -> str:
        ins = " + ".join(f"{f.quantity:g}{f.name}" for f in self.inputs) or "（无输入）"
        outs = " + ".join(f"{f.quantity:g}{f.name}" for f in self.outputs) or "（销毁）"
        return f"行{self.row} {ins} → {outs} [{self.device} {self.duration:g}s]"


# ------------------------------------------------------------------ 载入

def load_recipes() -> list[Recipe]:
    rows = read_sheet(RECIPE_XLSX, "xl/worksheets/sheet1.xml")
    out: list[Recipe] = []
    for rnum, v in rows:
        if rnum == 1 or not v.get("J"):
            continue

        def num(key: str) -> float:
            try:
                return float(v.get(key) or 0)
            except ValueError:
                return 0.0

        inputs = [ItemFlow(v[c].strip(), num(q))
                  for c, q in (("B", "A"), ("D", "C")) if v.get(c, "").strip()]
        outputs = [ItemFlow(v[c].strip(), num(q))
                   for c, q in (("G", "F"), ("I", "H")) if v.get(c, "").strip()]
        out.append(Recipe(
            row=rnum, inputs=inputs, outputs=outputs, duration=num("E") or 1.0,
            device=v.get("J", "").strip(), environment=v.get("K", "").strip(),
            catalyst=v.get("L", "").strip(), catalyst_rate=num("M"),
        ))
    return out


def load_device_power() -> dict[str, float]:
    rows = read_sheet(DEVICE_XLSX, "xl/worksheets/sheet1.xml")
    power: dict[str, float] = {}
    for rnum, v in rows:
        if rnum == 1:
            continue
        try:
            power[v.get("A", "").strip()] = float(v.get("H") or 0)
        except ValueError:
            power[v.get("A", "").strip()] = 0.0
    return power


# ------------------------------------------------------------------ 选择与展开

def choose(item: str, candidates: list[Recipe], objective: str,
           power: dict[str, float]) -> Recipe:
    """在候选配方中挑一条。优先选蓝图外来源（R-001），其次按目标函数。"""
    def external(recipe: Recipe) -> int:
        return 0 if recipe.device in EXTERNAL_SOURCE_DEVICES else 1

    def score(recipe: Recipe) -> tuple:
        per_machine = recipe.out_rate(item) or 1e-9
        machines = 1.0 / per_machine
        if objective == "min_power":
            return (external(recipe), machines * (power.get(recipe.device, 0.0) or 0.0), machines)
        return (external(recipe), machines, 0.0)

    return min(candidates, key=score)


@dataclass
class MachineUse:
    recipe: Recipe
    units: float


@dataclass
class Plan:
    target: str
    target_rate: float
    machines: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    recipe_units: dict[int, float] = field(default_factory=lambda: defaultdict(float))
    external: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    dissolved_cycles: list[tuple[str, str]] = field(default_factory=list)
    tree: list[str] = field(default_factory=list)


def expand(target: str, rate: float, producers: dict[str, list[Recipe]],
           objective: str, power: dict[str, float]) -> Plan:
    """先做树形展开得到初始机组配置，并记录被截断的循环依赖。"""
    plan = Plan(target=target, target_rate=rate)
    chosen: dict[str, Recipe] = {}

    def walk(item: str, need: float, path: tuple[str, ...], depth: int) -> None:
        indent = "  " * depth
        candidates = [r for r in producers.get(item, []) if not r.destroys_input]
        if not candidates:
            plan.external[item] += need
            plan.tree.append(f"{indent}{item} {need:.1f}/min ← 外部来源（R-001）")
            return

        recipe = chosen.get(item) or choose(item, candidates, objective, power)
        chosen[item] = recipe
        per_machine = recipe.out_rate(item) or 1e-9
        units = need / per_machine
        plan.machines[recipe.device] += units
        plan.recipe_units[recipe.row] += units
        plan.tree.append(f"{indent}{item} {need:.1f}/min ← {recipe.label()} ×{units:.2f}台")

        if depth >= MAX_DEPTH:
            plan.tree.append(f"{indent}  …（达到最大深度，停止展开）")
            return

        for flow in recipe.inputs:
            child_need = units * flow.quantity * recipe.batches_per_minute
            if flow.name in path:
                # 循环依赖：先记账，稍后由回路补偿处理
                plan.dissolved_cycles.append((item, flow.name))
                plan.tree.append(
                    f"{indent}  {flow.name} {child_need:.1f}/min [循环依赖，留待回路补偿]"
                )
                continue
            walk(flow.name, child_need, path + (item,), depth + 1)

        # R-061 催化剂
        cat_rate = recipe.catalyst_per_minute
        if recipe.catalyst and cat_rate:
            total = units * cat_rate
            plan.tree.append(
                f"{indent}  催化剂 {recipe.catalyst} {total:.1f}/min"
                f"（每台固定 {cat_rate:g}/min，R-061）"
            )
            if recipe.catalyst in path:
                plan.dissolved_cycles.append((item, recipe.catalyst))
                plan.tree.append(f"{indent}    [循环依赖，留待回路补偿]")
            else:
                walk(recipe.catalyst, total, path + (item,), depth + 1)

    walk(target, rate, (), 0)
    return plan


def classify_sources(plan: Plan, recipes: list[Recipe]) -> None:
    """把外部需求分成「真正的净进口」与「本链内可自产」。

    判据：若某物品存在非外部的生产者，则它不该被当作外部需求，
    而应由回路补偿重新分配。这里先识别出来供报告使用。
    """
    producers: dict[str, list[Recipe]] = defaultdict(list)
    for recipe in recipes:
        for flow in recipe.outputs:
            producers[flow.name].append(recipe)

    internally_producible = {
        item for item, rs in producers.items()
        if any(r.device not in EXTERNAL_SOURCE_DEVICES for r in rs)
    }
    plan.internal_candidates = sorted(
        item for item in plan.external if item in internally_producible
    )


def audit_mass_balance(plan: Plan, recipes: list[Recipe]) -> tuple[dict[str, float], list[str]]:
    """对树展开得到的机组配置做全物料平衡审计。

    树展开会**重复计算共享输入**、并且**不闭合循环**，所以它的「外部需求」
    不可信。这里按最终的设备台数重新统计每种物料的产消差：

        净额 = Σ(产) − Σ(消) − 目标出口

    净额为负 = 缺口（需要进口），为正 = 盈余（需要有出路）。
    这是下一版线性平衡求解器的输入。
    """
    net: dict[str, float] = defaultdict(float)
    for row, units in plan.recipe_units.items():
        recipe = next(r for r in recipes if r.row == row)
        for flow in recipe.outputs:
            # A-2：无产物即销毁，只记消耗不记产出
            net[flow.name] += flow.quantity * recipe.batches_per_minute * units
        for flow in recipe.inputs:
            net[flow.name] -= flow.quantity * recipe.batches_per_minute * units
        cat_rate = recipe.catalyst_per_minute
        if recipe.catalyst and cat_rate:
            net[recipe.catalyst] -= cat_rate * units  # R-061

    net[plan.target] -= plan.target_rate

    lines: list[str] = []
    deficit = {k: -v for k, v in net.items() if v < -1e-6}
    surplus = {k: v for k, v in net.items() if v > 1e-6}
    balanced = [k for k, v in net.items() if abs(v) <= 1e-6]

    if deficit:
        lines.append("  缺口（净额为负，需进口或增加上游设备）：")
        for item, qty in sorted(deficit.items(), key=lambda kv: -kv[1]):
            lines.append(f"    {item:<20} {qty:9.2f} /min")
    if surplus:
        lines.append("  盈余（净额为正，需有出路）：")
        for item, qty in sorted(surplus.items(), key=lambda kv: -kv[1]):
            lines.append(f"    {item:<20} {qty:9.2f} /min")
    if balanced:
        lines.append("  恰好平衡：" + "、".join(sorted(balanced)))
    if not deficit and not surplus:
        lines.append("  全部物料恰好平衡。")
    return deficit, lines


def report(plan: Plan, power: dict[str, float], recipes: list[Recipe]) -> str:
    lines: list[str] = []
    lines.append(f"配方数 {len(recipes)}；目标 {plan.target} {plan.target_rate}/min\n")

    lines.append("=== 展开树 ===")
    lines.extend(plan.tree)

    lines.append("\n=== 设备台数 ===")
    total_power = 0.0
    for dev, units in sorted(plan.machines.items(), key=lambda kv: -kv[1]):
        kw = power.get(dev, 0.0)
        total_power += units * kw
        lines.append(f"  {dev:<26} {units:7.2f} 台   {kw:>6.0f} kW/台   合计 {units * kw:>8.0f} kW")

    lines.append("\n=== 外部需求 ===")
    for item, qty in sorted(plan.external.items()):
        tag = ""
        if item in getattr(plan, "internal_candidates", []):
            tag = "  ⚠ 本链内可自产，需回路补偿"
        lines.append(f"  {item:<20} {qty:9.1f} /min{tag}")

    if plan.dissolved_cycles:
        lines.append("\n=== 检测到的循环依赖 ===")
        for src, dst in plan.dissolved_cycles:
            lines.append(f"  {src} → {dst}")

    lines.append("\n=== 物料平衡审计（按最终机组配置重算） ===")
    lines.append("  说明：树展开会重复计算共享输入且不闭合循环，")
    lines.append("        因此这里的净额才是可信的数字，也是下一版线性平衡求解器的输入。")
    _, audit_lines = audit_mass_balance(plan, recipes)
    lines.extend(audit_lines)

    lines.append("\n=== 校验 ===")
    problems: list[str] = []
    furnace = plan.machines.get(HEAVEN_FURNACE, 0.0)
    if furnace > HEAVEN_FURNACE_LIMIT:
        problems.append(
            f"R-060：需要 {furnace:.2f} 台天有洪炉，超过全局上限 {HEAVEN_FURNACE_LIMIT} 台")
    for row, units in plan.recipe_units.items():
        recipe = next(r for r in recipes if r.row == row)
        if units > 0 and recipe.slots < len(recipe.inputs):
            problems.append(f"R-067：行{row} 输入种类多于缓存格数")
    if problems:
        lines.extend("  [FAIL] " + p for p in problems)
    else:
        lines.append("  [ OK ] 未发现规则冲突")

    lines.append(f"\n总额定功率 {total_power:.0f} kW"
                 f"（基准 {POWER_BASELINE_KW:.0f} kW，R-069）"
                 f" → {'超出基准' if total_power > POWER_BASELINE_KW else '在基准内'}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    target, rate = argv[1], float(argv[2])
    objective = argv[3] if len(argv) > 3 else "min_devices"

    recipes = load_recipes()
    power = load_device_power()
    producers: dict[str, list[Recipe]] = defaultdict(list)
    for recipe in recipes:
        for flow in recipe.outputs:
            producers[flow.name].append(recipe)

    plan = expand(target, rate, producers, objective, power)
    classify_sources(plan, recipes)

    text = report(plan, power, recipes)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "plan_output.txt"
    out_path.write_text(text, encoding="utf-8")
    print(f"已写入 {out_path}")
    print(text)
    return 0


if __name__ == "__main__":
    # Windows 控制台默认 GBK，中文输出会乱码，这里统一切到 UTF-8。
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv))
