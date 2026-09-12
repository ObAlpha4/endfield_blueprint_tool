# .disable —— 已停用文件归档

本目录存放**从活跃工作区移出**的文件。它们**没有被删除**，随时可以移回去；但**不再参与开发，也不再是权威**。

停用判据只有三类：

1. **内容已被取代**：结论已并入 `design/` 的当前文档，原文只作历史留痕。
2. **非设计产物**：对话导出等过程记录，不是可执行的规则或模型。
3. **构建残留**：可重复生成的产物（`__pycache__` 等，已随目录清理删除）。

> 维护约定：只进不出。如果某份文件需要重新启用，移回 `design/` 并在 `design/design-index.md` 里登记它的边界（同一主题只能有一个权威文档）。
>
> **注意**：本目录内文档正文中出现的路径，写的是**当时的目录结构**（`agents/…`、`tests/…`、`workflow.md`），重组后已不再成立，不要照着它们去找文件。当时的对照关系：
>
> | 文中的旧路径 | 现在的位置 |
> |---|---|
> | `agents/phase-01-*.md`（结论类） | 结论已并入 `design/baseline-rules.md` 等文档；原文在 `.disable/history/` |
| `agents/phase-01-6-b-class-resolutions.md` | `.disable/history/round2-b-class-resolutions.md` |
> | `agents/m0-file-parsing-domain-model.md` | **仍在活跃区**：`design/domain-model.md`（本轮就地更名，未归档） |
> | `agents/phase-01-source-summary.md`、`agents/phase-01-10-*.md` | `.disable/superseded/` |
> | `agents/*.json` | `.disable/conversation-exports/` |
> | `workflow.md` | `docs/planning-workflow.md` |
> | `tests/*.py` | `tools/` |
> | `tests/images/*.svg` | `tools/out/images/` |

---

## 1. `conversation-exports/` —— 早期对话导出（非设计产物）

| 文件 | 大小 | 内容 | 停用原因 |
|---|---:|---|---|
| `产线规划工具设计总结.json` | 2.2 MB | 与 Copilot 的 1 轮总要求 + 6 轮确认对话导出 | 全部结论已抽取并并入 `design/baseline-rules.md`；保留原文会让后来者误把旧对话当规则 |
| `设备示例图绘制功能.json` | 2.0 MB | 设备示例图绘制功能的对话导出 | 对应代码为 `scripts/show_facility.py`，对话过程无残留结论 |

## 2. `superseded/` —— 被取代的文档

| 文件 | 原位置 | 内容 | 被谁取代 |
|---|---|---|---|
| `m0-file-parsing-domain-model.md` | `agents/` | 最早的 M0 解析与领域模型设计（含 8 处设备表转录错误） | `design/domain-model.md`（已按原始 XML 复核修正转录错误） |
| `phase-01-source-summary.md` | `agents/` | 阶段 1 源资料阅读摘要 + 16 条歧义点 | 歧义点已由 A/B 类与六轮问答逐条结案，结论并入 `design/baseline-rules.md` |
| `phase-01-10-open-questions-round2.md` | `agents/` | 第二轮待澄清清单（Q1–Q12） | Q1–Q12 已在第三至六轮全部答复，结论并入 `design/baseline-rules.md` 的 R-060~R-069 |

## 3. `history/` —— 六轮问答原始记录

| 文件 | 轮次 | 主要内容 | 结论去向 |
|---|---|---|---|
| `round2-b-class-resolutions.md` | 第二轮（B 类） | B-1 气体散布机定位、B-5 净水节点决策链、B-6 反应池缓存格、B-7 覆盖几何、B-8 供气区间、B-9 物流设备占地、B-10 存取线连接、B-11 协议核心取货口 | B 类结论 → `design/baseline-rules.md` §3；几何细节 → `design/coverage-geometry.md`、`design/logistics-and-storage-geometry.md` |
| `round3-objectives-and-architecture.md` | 第三轮 | Q1 设备无限供应 + 天有洪炉 ≤ 12、Q2 只输出 JSON（方案 A）、Q5 优化目标由用户选 | → R-060；`design/PROJECT.md` §1、§3.2 |
| `round4-goals-and-catalyst.md` | 第四轮 | Q13 催化剂每台固定 6/min（R-061）、Q4 算法选优路径、Q7 循环闭合、Q12 基地层/模块层分层 | → R-061；`design/baseline-rules.md` §1.4 |
| `round5-rules.md` | 第五轮 | Q4 自动选配方（R-062）、Q12 基地层校验（R-063）、Q3 混管（R-064）、Q10 环境单值（R-065）、Q8 暗管（R-066）、Q9 缓存格（R-067）、Q6 污水（R-068）、Q11 热能池（R-069） | → R-062~R-069 |
| `round6-heavy-loam.md` | 第六轮 | R-064 定稿按 A、Q12 协议核心软硬要求、Q11 电力基准、Q4 反应池出口语义、重息壤链路核算 | → R-064/R-069 定稿；重息壤结论 → `design/PROJECT.md` §3.4 |

**重新启用时的注意**：这些文档里的**早期说法有已知订正**，直接引用会踩坑。典型例子：

- 「桥 = 2 端口」**作废** → 桥是 **4 端口**（两条正交线各占 2 口）。
- 「催化剂 = 每次配方固定消耗 6 滴」**作废** → **每台设备固定 6/min**，且与气体散布机的 6/min **无关**。
- 「材料清单需要建造材料数据」**作废** → 设备无限供应，材料成本不进目标函数。
- `FILL_SPACE`（占满空地）目标**作废**。
- M0 文档中的设备表有 **8 处转录错误**（长重复串掉字符、`nnfinn` 被压成 `nfnn`），已由 `scripts/validate_sources.py` 的断言守住。

---

## 4. 未归档但仍需注意的生成物

以下文件**保留在活跃区**，因为它们是可复现的工具产出：

- `scripts/out/plan_output.txt` —— `scripts/plan_throughput.py` 每次运行都会重写。
- `scripts/out/images/*.svg` —— 由 `draw_heavy_loam_schematic.py` 与 `show_facility.py` 生成。

若确定不再需要纳入版本管理，可加入 `.gitignore`。
