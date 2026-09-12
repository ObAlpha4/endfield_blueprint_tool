# 终末地产线规划器

输入「目标产物 + 目标产量 + 基地类型」，输出一份可直接复刻的**蓝图 JSON**（可视化交给下游前端）。

当前状态：**阶段 2（领域模型 + 解析器）已完成**，下一步进入线性物料平衡求解（第一部分）。

## 目录

| 目录 | 内容 |
|---|---|
| `docs/` | 四份权威源资料（设备概述 / 产线配方 / 发电对照 / 终末地产线限制）+ 规划思路参考 |
| `design/` | 当前有效的设计文档（项目总览、规则基线、领域模型、几何标定） |
| `src/endfield/` | **解析器与领域模型**（阶段 2 的代码资产） |
| `tests/` | 单元测试（标准库 `unittest`，83 项） |
| `tools/` | 可运行工具（源数据校验入口、设备接口示意图） |
| `data/derived/` | 解析器产出的规范化中间数据 `sources.json` |
| `.disable/` | 已停用文件的归档，含清单与停用原因；不再参与开发 |

## 从这里开始

1. **`design/PROJECT.md`** —— 项目目标、当前阶段、已完成、接下来做什么、怎么跑。
2. **`design/next-steps.md`** —— 施工单与未决项。
3. **`design/design-index.md`** —— 文档索引、阅读顺序、权威性边界。

## 快速验证

```powershell
# 让解析器 / 领域模型可被导入（仓库根目录执行一次）
$env:PYTHONPATH = "$PWD\src"

# 1) 源数据校验（46 行「分词格数 = 宽/高」等全部断言）
.venv\Scripts\python.exe tools\validate_sources.py

# 2) 生成规范化中间数据（逐字节可重复）
.venv\Scripts\python.exe -m endfield.cli build
.venv\Scripts\python.exe -m endfield.cli repeat

# 3) 单元测试
.venv\Scripts\python.exe -m unittest discover -s tests -t .

# 4) 单设备接口示意图（读 sources.json，不依赖 pandas）
.venv\Scripts\python.exe tools\show_facility.py
.venv\Scripts\python.exe tools\show_facility.py --all
```

`validate_sources.py` 应输出三张表全部通过；`endfield.cli build` 会写出
`data/derived/sources.json`（45 台常规设备 + 1 台特殊设备「协议核心」、151 条配方、
6 条发电、111 种物料、12 种物流元件），并对同一输入产生**逐字节一致**的结果。
