# 终末地产线规划器

输入「目标产物 + 目标产量 + 基地类型」，输出一份可直接复刻的**蓝图 JSON**（可视化交给下游前端）。

当前状态：**阶段 1（需求与规则确认）已结案**，下一步进入解析器与领域模型实现。

## 目录

| 目录 | 内容 |
|---|---|
| `docs/` | 四份权威源资料（设备概述 / 产线配方 / 发电对照 / 终末地产线限制）+ 规划思路参考 |
| `design/` | 当前有效的设计文档（项目总览、规则基线、领域模型、几何标定） |
| `tools/` | 可运行工具（源数据校验、产能核算、示意图绘制），产出在 `tools/out/` |
| `.disable/` | 已停用文件的归档，含清单与停用原因；不再参与开发 |

## 从这里开始

1. **`design/PROJECT.md`** —— 项目目标、当前阶段、已完成、接下来做什么、怎么跑。
2. **`design/next-steps.md`** —— 施工单与未决项。
3. **`design/design-index.md`** —— 文档索引、阅读顺序、权威性边界。

## 快速验证

```powershell
.venv\Scripts\python.exe tools\validate_sources.py
.venv\Scripts\python.exe tools\plan_throughput.py 重息壤 12
```

`validate_sources.py` 应输出三张表全部通过；`plan_throughput.py` 会打印展开树、设备台数、物料平衡审计，并写入 `tools/out/plan_output.txt`（注意：当前审计会报三处自持环缺口，这是树展开的已知缺陷，将由线性物料平衡求解替换）。
