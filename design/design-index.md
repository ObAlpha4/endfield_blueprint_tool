# 设计文档索引

`design/` 只保留**当前有效**的文档。六轮问答的原始记录、被替代的旧文档全部归档在 `.disable/`（见 `.disable/README.md`），它们不再是权威。

## 建议阅读顺序

| 顺序 | 文档 | 读它的目的 |
|---:|---|---|
| 1 | `PROJECT.md` | 项目目标、两段式系统结构、当前阶段、已完成、下一步、怎么跑 |
| 2 | `next-steps.md` | 两段式结构与起始产物约定（§1A）、手头要做的事、参数状态（已清零） |
| 3 | `baseline-rules.md` | 全部已确认规则：单位 / 速率 / A 类 / B 类 / R-001~R-069 / 覆盖几何结论 / 物流与边界口径 / 转化机催化剂供料 |
| 4 | `domain-model.md` | 实体、字段、坐标与旋转、配方与发电模型 |
| 5 | `global-constraints.md` | G-001 整数对齐（边缘在格线上、顶点在整数坐标）、旋转锚点、物流元件端口模型 |
| 6 | `coverage-geometry.md` | 覆盖判定（整数格集合、居中偏移、12x12 / 13x13） |
| 7 | `logistics-and-storage-geometry.md` | 物流元件建模方式、存取线连接判定 |

## 文档边界（避免重复与漂移）

| 主题 | 权威文档 | 其他文档中的处理 |
|---|---|---|
| 规则编号与取值口径 | `baseline-rules.md` | 其他文档只引用编号，不复制取值 |
| 两段式结构与起始产物 | `next-steps.md` §1A | `PROJECT.md` 只写结论与输入输出清单 |
| 实体与字段 | `domain-model.md` | 其他文档只引用字段名 |
| 坐标 / 旋转 / 整数对齐 | `global-constraints.md` | `domain-model.md` 只做交叉引用 |
| 覆盖判定几何 | `coverage-geometry.md` | `baseline-rules.md` 只写结论 |
| 物流元件与存取线连接 | `logistics-and-storage-geometry.md` | 同上 |
| 进度与路线 | `PROJECT.md` + `next-steps.md` | 其他文档不写进度 |

## 来源与权威性

```
docs/*.xlsx, docs/*.docx      ← 唯一权威来源（用户提供，不得臆造）
        │  （解析、复核、确认）
        ▼
design/baseline-rules.md      ← 经用户确认的基线（源文件事实 / 用户确认 / 设计推测 三种来源已标注）
        │
        ▼
design/domain-model.md 等     ← 设计产物，实现时必须回到基线核对
```

`docs/planning-workflow.md` 是早期规划思路参考（分层规划 + 约束验证 + 模块化模板），**不是**设备、配方或规则的权威来源；只用于确认整体路线（解析器 → 模块库 → 布线 → 仿真 → 导出）。

## 命名约定

- 规则编号 `R-###`：项目内部引用号，**不是**源文档编号（源文档没有编号）。
- 全局约束 `G-###`：适用于所有对象的约束。
- 处置编号 `A-#` / `B-#` / `Q#` / `C-#` / `D-#`：确认过程中的问题条目，结论已并入基线，原始记录在 `.disable/history/`。
