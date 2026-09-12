# M0：文件解析与领域建模设计

状态：**已确认**（原「待确认」条目已由 A 类、B 类与六轮问答逐条结案；取值以 `design/baseline-rules.md` 为准，未决参数见 `design/next-steps.md` §1）

本阶段定义四份输入文件的解析结果和领域模型。设备布局、物流布线、仿真与蓝图导出属于后续阶段；解析器已由 `tools/validate_sources.py` 先行验证「格数 = 宽/高」这一条不变量。

## 1. 输入文件与范围

| 文件 | 读取范围 | M0 结果 |
|---|---|---|
| `docs/设备概述.xlsx` | `设备列表`、`标记对照` | 设备类型、四面原始接口串、耗电功率、接口标记 |
| `docs/终末地产线限制.docx` | 正文规则 | 设备类别、基地/仓储/物流/暗管/供电/环境/缓存约束 |
| `docs/产线配方.xlsx` | `Sheet1` 第 2 至 152 行 | 配方的输入、输出、时间、设备、环境、催化剂 |
| `docs/发电对照.xlsx` | `Sheet1` | 燃料/电池、燃烧时间、发电功率 |

单位约定：时间使用秒；固体物品使用“个”；液体和气体使用“滴”；物流速率使用每分钟；发电和耗电功率使用 `kW`。

## 2. 设备实体清单

下面的四面接口仍是源表原始串，字段顺序固定为北、南、西、东。每个面的端口字符串排列方向已确认：北面从东向西，南面从西向东，西面从北向南，东面从南向北。所有设备和基地的坐标原点都是自身左下角；以基地坐标系判断，未旋转时设备北面朝基地 `y` 轴正方向，顺时针旋转 90 度后设备北面朝基地 `x` 轴正方向，之后按同一规则类推。

类别来自《终末地产线限制.docx》的六大类。规则提到但设备概述没有完整规格的传送带、分流器、汇流器、物流桥、物品准入口、管道、管道分流器、管道汇流器、管道桥、管道准入口、供电桩不在下表中补造规格。

| 名称 | 宽 | 高 | 北面 | 南面 | 西面 | 东面 | 耗电功率 kW | 类别 |
|---|---:|---:|---|---|---|---|---:|---|
| 协议储存箱 | 3 | 3 | sisisi | sososo | nnn | nnn | 5 | 仓储存取 |
| 储液罐 | 3 | 3 | nnn | nnn | nfin | nfon | 0 | 仓储存取 |
| 储气罐 | 3 | 3 | nnn | nnn | ngin | ngon | 0 | 仓储存取 |
| 暗管入口（液体） | 3 | 3 | nnn | nnn | nfin | nnn | 0 | 仓储存取 |
| 暗管出口（液体） | 3 | 3 | nnn | nnn | nnn | nfon | 0 | 仓储存取 |
| 暗管入口（气体） | 3 | 3 | nnn | nnn | ngin | nnn | 0 | 仓储存取 |
| 暗管出口（气体） | 3 | 3 | nnn | nnn | nnn | ngon | 0 | 仓储存取 |
| 多口暗管入口（液体） | 3 | 5 | nnn | nnn | nfinfin | nnnnn | 0 | 仓储存取 |
| 多口暗管出口（液体） | 3 | 5 | nnn | nnn | nnnnn | nfonfon | 0 | 仓储存取 |
| 多口暗管入口（气体） | 3 | 5 | nnn | nnn | ngingin | nnnnn | 0 | 仓储存取 |
| 多口暗管出口（气体） | 3 | 5 | nnn | nnn | nnnnn | ngongon | 0 | 仓储存取 |
| 精炼炉 | 3 | 3 | sisisi | sososo | nnn | nnn | 5 | 基础生产 |
| 精炼炉（液体模式） | 3 | 3 | sisisi | sososo | nfin | nfon | 5 | 基础生产 |
| 粉碎机 | 3 | 3 | sisisi | sososo | nnn | nnn | 5 | 基础生产 |
| 配件机 | 3 | 3 | sisisi | sososo | nnn | nnn | 20 | 基础生产 |
| 塑形机 | 3 | 3 | sisisi | sososo | nnn | nnn | 10 | 基础生产 |
| 塑形机（气体模式） | 3 | 3 | sisisi | sososo | ngin | nnn | 10 | 基础生产 |
| 采种机 | 5 | 5 | sisisisisi | sososososo | nnnnn | nnnnn | 10 | 基础生产 |
| 种植机 | 5 | 5 | sisisisisi | sososososo | nnnnn | nnnnn | 20 | 基础生产 |
| 种植机（液体模式） | 5 | 5 | sisisisisi | sososososo | nnfinn | nnnnn | 20 | 基础生产 |
| 废水处理机 | 3 | 3 | nnn | nnn | nfin | nnn | 50 | 基础生产 |
| 装备原件机 | 6 | 4 | sisisisisisi | sosososososo | nnnn | nnnn | 10 | 合成制造 |
| 灌装机 | 6 | 4 | sisisisisisi | sosososososo | nnnn | nnnn | 20 | 合成制造 |
| 灌装机（液体模式） | 6 | 4 | sisisisisisi | sosososososo | nfinn | nnnn | 20 | 合成制造 |
| 灌装机（气体模式） | 6 | 4 | sisisisisisi | sosososososo | nginn | nnnn | 20 | 合成制造 |
| 封装机 | 6 | 4 | sisisisisisi | sosososososo | nnnn | nnnn | 20 | 合成制造 |
| 研磨机 | 6 | 4 | sisisisisisi | sosososososo | nnnn | nnnn | 50 | 合成制造 |
| 反应池 | 5 | 5 | nsinsin | nsonson | nfinfin | nfonfon | 50 | 合成制造 |
| 扩容反应池 | 6 | 5 | nsisisisin | nsosososon | nfinfin | nfonfon | 100 | 合成制造 |
| 天有洪炉 | 5 | 5 | sisisisisi | sososososo | nnfinn | nnnnn | 50 | 合成制造 |
| 提纯机（液体模式） | 5 | 5 | nnnnn | nnnnn | nfinfin | nfonfon | 50 | 合成制造 |
| 提纯机（气体模式） | 5 | 5 | sisisisisi | nnnnn | nnginn | ngongon | 50 | 合成制造 |
| 拆解机（液体模式） | 6 | 4 | sisisisisisi | sosososososo | nnnn | nnfon | 20 | 合成制造 |
| 拆解机（气体模式） | 6 | 4 | sisisisisisi | sosososososo | nnnn | nngon | 20 | 合成制造 |
| 液气转化机（气体产出） | 5 | 5 | nnfinn | nnnnn | nfinfin | ngongon | 50 | 合成制造 |
| 液气转化机（液体产出） | 5 | 5 | nnfinn | nnnnn | ngingin | nfonfon | 50 | 合成制造 |
| 固气转化机（气体产出） | 5 | 5 | nsigisin | nnnnn | nnnnn | ngongon | 50 | 合成制造 |
| 固气转化机（固体产出） | 5 | 5 | nnginn | nsonson | ngingin | nnnnn | 50 | 合成制造 |
| 气体散布机 | 3 | 3 | nnn | nnn | ngin | nnn | 0 | 合成制造 |
| 气体反应炉 | 5 | 5 | nnnnn | nnnnn | ngingin | ngongon | 50 | 合成制造 |
| 热能池 | 2 | 2 | sisi | nn | nn | nn | 0 | 电力供应 |
| 仓库存取线源桩 | 4 | 4 | nnnn | nnnn | nnnn | nnnn | 0 | 仓储存取 |
| 仓库存取线基段 | 8 | 4 | nnnnnnnn | nnnnnnnn | nnnn | nnnn | 0 | 仓储存取 |
| 仓库取货口 | 3 | 1 | nnn | nson | n | n | 0 | 仓储存取 |
| 仓库存货口 | 3 | 1 | nsin | nnn | n | n | 0 | 仓储存取 |
| 协议核心 | 9 | 9 | nsisisisisisisin | nsisisisisisisin | nsonnsonnson | nsonnsonnson | 0 | 仓储存取 |

注意：设备表中的个别接口串和名称存在录入显示差异，正式解析时必须保留原始值，同时生成规范化值并保留来源行号。

## 3. 标记含义

| 标记 | 含义 | 物料类别 |
|---|---|---|
| `si` | 固体入口 | 固体 |
| `so` | 固体出口 | 固体 |
| `fi` | 液体入口 | 液体 |
| `fo` | 液体出口 | 液体 |
| `gi` | 气体入口 | 气体 |
| `go` | 气体出口 | 气体 |
| `n` | 普通面 | 非物流端口 |

接口字符串解析必须使用最长标记匹配：先匹配六种二字符标记，再匹配单字符 `n`。例如 `sisisi` 是三个 `si`，`nfinfin` 是 `n`、`fi`、`n`、`fi`、`n`，`nnnnn` 是五个 `n`。

## 4. 配方实体

### 4.1 统一结构

每个配方实体对应《产线配方.xlsx》的一行，至少包含：

| 字段 | 类型/单位 | 说明 |
|---|---|---|
| `sourceRow` | 整数 | 源表行号，当前为 2-152 |
| `inputs` | 0-2 个物料项 | 每项包含名称、数量、物料类别；空单元格表示该输入不存在，必须保留其位置语义 |
| `outputs` | 0-2 个物料项 | 每项包含名称、数量、物料类别；空单元格表示该输出不存在，必须保留其位置语义 |
| `durationSeconds` | 秒 | 反应时间 |
| `deviceType` | 名称 | 制作设备 |
| `environment` | 可空枚举/名称 | 设备环境 |
| `catalyst` | 可空物料项 | 催化剂及固定消耗量 |
| `ratePerMinute` | 个/分钟或滴/分钟 | 由数量乘 60 除以秒数换算 |

### 4.2 配方覆盖

源表第 2-8 行是资源采集/流体采集，第 9-110 行覆盖精炼、粉碎、配件、塑形、种植、采种、灌装、封装和研磨，第 111-125 行覆盖反应、洪炉和提纯，第 126-129 行是环境提供配方，第 130-152 行覆盖气体反应、液气转换和固气转换。

配方实体必须保留双输入、双输出、副产物、环境和催化剂，不能只保存“主输入/主输出”。已确认：**催化剂按每台固气/液气转化机固定 6/min 记账，与配方和实际产率无关，且可按净额由本机产物自供（R-061）**；物品单位为个，液体和气体单位为滴；理论速率是 `数量 * 60 / 时间`。

典型配方结构：

- 单输入单输出：蓝铁矿 -> 蓝铁块，2 秒，精炼炉。
- 双输入单输出：蓝铁矿 + 清水 -> 赤铜块的液体模式示例，2 秒，精炼炉（液体模式）。
- 双输入双输出：赤铜矿 + 清水 -> 赤铜块 + 污水，2 秒。
- 环境配方：碳块 + 清水 -> 息壤，2 秒，天有洪炉，稳定环境。
- 催化剂配方：液气/固气转换配方记录催化剂种类；消耗量不取自配方表数值，按 R-061 固定为每台 6/min。

数据表中的空单元格具有结构意义：表格按最多两种原料和两种产物设计，因此单输入/单输出配方会在对应列留下空缺。M0 必须保留原始单元格状态，不能把空缺填成“无”、0 或其他物料。名称中的空格、换行和其他原始字符也必须保留在 `rawName` 中；只有得到确认后才能生成 `canonicalName`。

## 5. 发电实体

每行对应一个发电燃料或电池实体：

| 燃料/电池 | 数量 | 燃烧时间 | 发电功率 |
|---|---:|---:|---:|
| 源矿 | 1 | 8s | 50kW |
| 低容谷地电池 | 1 | 20s | 220kW |
| 中容谷地电池 | 1 | 20s | 420kW |
| 高容谷地电池 | 1 | 20s | 1100kW |
| 低容武陵电池 | 1 | 20s | 1600kW |
| 中容武陵电池 | 1 | 20s | 3200kW |

热能池本身耗电功率为 0，内部最多缓存 50 个同种类电池，且一次只能处理一种电池；消耗速率按本表燃烧时间执行。例如低容谷地电池每 20 秒消耗 1 个，并提供 220kW。发电功率和设备耗电功率都是瞬时功率，单位同为 `kW`，不累计建模电量。多种电池的调度由人工根据最终产线整体耗电量处理，规划阶段不考虑电力消耗。

## 6. 建议领域模型

### 6.1 基础值对象

#### 坐标和旋转

所有设备实例和基地使用基地坐标系，坐标原点为对象左下角。未旋转时设备北面朝 `+y`，顺时针 90 度后北面朝 `+x`，顺时针 180 度后朝 `-y`，顺时针 270 度后朝 `-x`。设备的 `rotation` 取 `0`、`90`、`180`、`270` 度，均表示顺时针角度；禁止镜像。旋转后宽、高和四面接口随设备姿态变换，设备仍占用完整的整数网格矩形。

#### `Face`

表示设备的朝向面：`NORTH`、`SOUTH`、`WEST`、`EAST`。除方向外，每个面有固定的端口字符串排列方向：北面东到西、南面西到东、西面北到南、东面南到北。

#### `Port`

表示已解析的接口标记，建议字段：`face`、`ordinal`、`marker`、`direction`（入口/出口/普通）、`materialKind`（solid/liquid/gas/none）、`localCell`。`ordinal` 从 1 开始，沿该面的规定排列方向计数：北面东到西、南面西到东、西面北到南、东面南到北。每个出入口端口占用一个完整网格格子，不能只作为边界上的点处理。

在未旋转的局部坐标中，宽为 `w`、高为 `h` 时，端口格映射为：北面 `localCell=(w-ordinal, h-1)`，南面 `localCell=(ordinal-1, 0)`，西面 `localCell=(0, h-ordinal)`，东面 `localCell=(w-1, ordinal-1)`。旋转后先变换设备占地矩形和面方向，再将端口格变换到基地坐标系。

例如，拆解机（气体模式）的东面原始串为 `nngon`，按东面从南向北解析为 `n`、`n`、`go`、`n`；因此 `go` 是从北向南观察时的第二格。

#### `Item`

表示物料名称和值域：`rawName`、`canonicalName`、`kind`（solid/liquid/gas）、`unit`（item/drop）、`sourceRefs`。物料类别不能只依赖名称推断，应优先由端口标记和已确认物料表确定。

### 6.2 设备和生产模型

#### `DeviceType`

表示设备概述中的类型：`id`、`rawName`、`canonicalName`、`width`、`height`、`faces`、`powerKw`、`category`、`sourceRef`。`faces` 保存四面原始接口串和解析后的 `Port[]`。

#### `DeviceInstance`

表示蓝图中的设备实例：`id`、`deviceTypeId`、`position`、`rotation`、`recipeId`、`tags`、`moduleId`、`powerRequiredKw`、`sourceRef`。`position` 是实例左下角的基地坐标；`rotation` 只允许顺时针 0/90/180/270 度，禁止镜像；设备模式由 `deviceTypeId` 对应的设备名称固定，不在实例中动态切换。

#### `Recipe`

表示配方行：`id`、`sourceRow`、`inputs[]`、`outputs[]`、`durationSeconds`、`deviceTypeId`、`environment`、`catalyst`、`ratesPerMinute`。

#### `Module`

表示后续布局阶段可复用的生产模块。本阶段只定义接口，不生成模块：`id`、`name`、`deviceInstances[]`、`inputPorts[]`、`outputPorts[]`、`powerDemandKw`、`environmentRequirements[]`、`sourceRefs`。

### 6.3 蓝图和物流模型

#### `Conveyor`

表示固体物流路径或物流元件集合：`id`、`segments[]`、`continuousPartLength`、`direction`、`speedPerMinute`、`itemFilter`、`junctions[]`、`bridges[]`、`sourcePort`、`targetPort`。长度按连续部分计量；被准入口、分流器、汇流器或物流桥断开后重新计算。M0 不决定路径算法，也不定义桥的几何细节。

#### `Pipe`

表示液体/气体物流路径：`id`、`mediumKind`、`segments[]`、`continuousPartLength`、`direction`、`speedPerMinute`、`fluidFilter`、`junctions[]`、`bridges[]`、`breakpoints[]`、`sourcePort`、`targetPort`。长度按连续部分计量；被准入口、分流器、汇流器或管道桥断开后重新计算。混流的断开条件和优先级留给规则验证阶段。

#### `PowerPole`

表示供电桩实例：`id`、`position`、`rotation`、`coverage`、`coverageBoundary`（exclusive）、`sourceRef`。覆盖范围是外框且不包含边界；设备是否被覆盖由验证器计算，不由 M0 直接判定。

#### `GasDiffuser`

表示气体散布机及其环境类型：`id`、`position`、`rotation`、`environmentType`、`coverage`、`coverageBoundary`（exclusive）、`environmentPersistence`、`sourceRef`。覆盖范围是外框且不包含边界；输入不断供且速率不低于 6/min 时，产生的环境持续存在，设备进入环境范围后立即生效。名称统一使用 `GasDiffuser`，但源文档“气体散布机”和规则正文可能出现“气体扩散机”，规范名称仍需确认。

#### `StorageLine`

表示仓储存取骨架：`id`、`baseType`（主基地/副基地）、`sourcePiles[]`、`segments[]`、`pickupPorts[]`、`returnPorts[]`、`protocolCoreId`、`protocolStorageIds[]`、`sourceRefs`。

#### `Blueprint`

表示最终蓝图的领域容器，但 M0 只定义结构边界：`id`、`baseType`、`bounds`、`origin`、`devices[]`、`modules[]`、`conveyors[]`、`pipes[]`、`powerPoles[]`、`gasDiffusers[]`、`storageLine`、`externalInterfaces[]`、`ruleRefs`、`sourceRefs`。基地坐标原点为基地左下角；建造顺序、材料清单、仿真结果和导出字符串不在 M0 实现。

## 7. 规则和数据歧义

1. 规则提及的传送带、分流器、汇流器、桥、准入口和供电桩没有完整设备规格，不能在 M0 补造尺寸/接口。
2. 传送带和管道最大长度 80 按连续部分计量；被物品/管道准入口、分流器、汇流器、物流桥或管道桥断开后重新计算。各类断开元件的具体端点归属仍需在规则验证阶段明确。
3. 传送带/管道桥附近一格的“方向保持不变”如何作用于多格设备接口和转弯，几何判定未定义。
4. 管道混流需要每隔 1 或 2 单位用准入口断开，但选择条件、断开语义、桥断开语义和恢复连接规则未定义。
5. 管道汇流器入口优先级的先接顺序，以及增加分流器后降低/提高优先级的精确拓扑未定义。
6. 设备、物流设备、准入口和暗管必须端口类型匹配；普通面不参与连接，但暗管与设备端口的具体连接拓扑仍未完整定义。
7. 主基地为 80x80，副基地为 50x50；边界是否闭合仍需定义，坐标原点已确定为基地左下角。
8. 供电桩 12x12 和气体散布机 13x13 的范围指外框且不包含边界；外框相对于设备左下角的具体坐标计算仍需定义。
9. 气体散布机输入不断供且速率不低于 6/min 时，产生的环境持续存在；设备进入环境范围后环境判定立即生效。环境失效的精确时间点和多个散布机的独立环境状态仍需验证。
10. 反应池/扩容反应池多配方并行时，配方槽、缓存格绑定和输出选择未定义。
11. 废水处理机源表行只有输入和时间没有输出；它与可选净水节点的关系未定义。
12. 设备模式由设备名称对应固定模式，不在实例中动态切换；同名设备别名和名称规范仍需确认。
13. 数据表中的空格和空单元格具有结构意义；单输入/单输出配方因表格按双输入/双输出设计而留下空缺，解析时不能清除或填充。名称规范化规则仍需确认。
14. 发电功率和耗电功率均为瞬时功率 `kW`，不建模累计电量。热能池只能处理一种电池；多种电池的调度由人工根据最终产线整体耗电量处理，规划阶段不考虑电力消耗。
15. 协议核心、取货口、存货口的具体端口编号、贴靠位置和连接方向未定义。
16. `Module` 的模板参数、`Blueprint` 的导出格式、建造顺序和材料清单字段不属于本阶段。

## 8. M0 验收标准与测试方法

### 验收标准

- 四份文件的来源、单位和行号可追溯。
- 基地和设备均使用左下角原点；未旋转北面朝基地 `+y`，顺时针 90 度后朝 `+x`，端口占用完整格子。
- 连接只允许端口类型匹配，普通面不参与连接；物流连续部分被断开元件切分并独立计长。
- 覆盖范围按不含边界的外框处理，气体环境的持续和立即生效条件被记录。
- 设备表中的名称、尺寸、四面接口串、耗电功率和类别均被保留；源值和规范值不混淆。
- 七种接口标记的含义和最长匹配分词规则明确。
- 配方模型支持 0-2 个输入、0-2 个输出、副产物、环境、固定催化剂和源表行号。
- 发电模型支持燃料/电池、数量、燃烧时间、瞬时发电功率；热能池单电池类型缓存规则被记录，规划阶段不计算电力消耗。
- 指定的 13 类领域对象均有职责、最小字段和未决边界：`DeviceType`、`DeviceInstance`、`Face`、`Port`、`Recipe`、`Item`、`Module`、`Blueprint`、`Conveyor`、`Pipe`、`PowerPole`、`GasDiffuser`、`StorageLine`。
- 没有引入布局坐标求解、布线算法或自动补全源文件缺失规格的实现假设。

### 测试方法

本阶段的验收已由两部分承担：

- **自动化**：`tools/validate_sources.py` 从原始 OOXML 直接断言「四面接口串分词格数 = 宽/高」（46 行 0 错）以及配方表结构、发电表数值。
- **人工抽查**：设备表的名称/尺寸/耗电/类别；用 `sisisi`、`nfinfin`、`nnnnn`、`nsisisisisisisin` 核对分词；抽查单输入/双输入、单输出/双输出、环境与催化剂配方的单位与源行号；抽查 6 个发电实体（含低容谷地电池 20 秒 / 220kW 示例）。
- **实现期**：未在本文件冻结的语义（端口连接的几何细节、模块模板、导出格式）一律作为 Schema 评审问题，确认前禁止转化为硬编码规则。

## 9. 下一步建议

本文件已可转为实现：按 §6 的实体与字段落地领域模型，并复用 `tools/validate_sources.py` 的 `read_sheet` / `tokenize` 作为解析内核。实现顺序与验收标准见 `design/next-steps.md` 步骤 1、步骤 2；其中最关键的算法缺口是**线性物料平衡求解**（替换当前树展开，闭合自持环），见该文件步骤 3。