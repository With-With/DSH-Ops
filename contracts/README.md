# DSH-Ops Contracts 契约目录

本目录是 **Django 后端** 与 **Agent 侧** 共享的 JSON Schema 单一真相源（Single Source of Truth）。

- Django 侧用这些 schema 校验 agent 产出物的合法性，并存入数据库。
- Agent 侧（各 skill）引用这些 schema 描述自己的输出格式，确保双端一致。
- 所有 schema 使用 [JSON Schema draft 2020-12](https://json-schema.org/draft/2020-12/release-notes)。

---

## 文件清单

| 文件 | 说明 |
|------|------|
| `pom.schema.json` | A1 POM 提取产物 |
| `matrix.schema.json` | A2 场景矩阵 |
| `report.schema.json` | A4/A5 生成/自修复会话报告 |
| `mock.schema.json` | Mock 规则集 |
| `version.json` | 契约版本信息 |
| `README.md` | 本文件 |

---

## 1. pom.schema.json（POM 提取产物）

### 阶段与角色

- **产出阶段**：A1 Agent 从 Playwright 录制脚本 + trace 回放中提取。
- **生产者**：A1 Agent（POM 提取 Skill）。
- **消费者/校验方**：
  - Django 侧（`ui_automation` 模块）：校验合法后入库元素仓和页面库。
  - A2 Agent：消费 POM 生成场景矩阵。
  - A4/A5 Agent：消费 POM 生成 pytest 脚本。

### 关键字段设计意图

#### `element.exists_in_repo` / `page.matched_existing_page_id`（search-first）

A1 在提取元素时，先去元素仓（Element Repository）中按快照 hash 或定位器相似度搜索已有元素。若命中，则：

- `exists_in_repo = true`
- 可直接复用已有元素的 ID 和定位策略

**为什么这样设计？**

- 减少重复提取，避免元素仓膨胀。
- 保证同一物理元素在不同录制中复用同一身份，便于统一维护。
- 配合 `matched_existing_page_id` 实现页面级复用。

#### `action.param_ref` + `params[]`（字面量上提 / Literal Hoisting）

录制脚本中的输入值（如用户名、密码）都是字面量。A1 将其抽取为命名参数并存入 `params[]`，动作中的值通过 `param_ref` 引用。

**为什么这样设计？**

- **数据驱动**：A2 生成矩阵时可直接复用参数名，构造不同数据行。
- **Secret 管理**：密码、Token 等敏感值标记为 `secret: true`，不会出现在日志、报告、trace 中，运行时从密钥管理服务读取。
- **可维护性**：参数值变更时只改一处，不用在脚本里搜替换。

#### `element.candidates[]`（多定位器候选 + 健壮性分级）

每个元素提供多种定位方式（role、testid、css、xpath 等），按 `priority` 排序，各有 `robustness` 评级。

**为什么这样设计？**

- **健壮性**：强定位器（testid、aria role）失效时，自动降级到弱定位器，减少脚本维护成本。
- **自修复依据**：A5 自修复时可根据 `robustness` 和 `snapshot_hash` 判断是定位器问题还是 UI 真的变了。

---

## 2. matrix.schema.json（场景矩阵）

### 阶段与角色

- **产出阶段**：A2 Agent 基于 POM 做测试用例设计，生成场景矩阵。
- **生产者**：A2 Agent（场景矩阵生成 Skill）。
- **消费者/校验方**：
  - Django 侧：校验合法后入库 `testcases` 模块，供人工评审。
  - A4/A5 Agent：消费矩阵行生成 pytest 脚本。

### 关键字段设计意图

#### `classification`（data_driven vs separate_flow）

- **`data_driven`**：同一流程、不同数据。多个数据行折叠为 **1 个脚本 + N 行数据**（pytest parametrize）。
- **`separate_flow`**：每个场景独立流程，各生成独立脚本。

**为什么这样设计？**

- **省 Token**：data_driven 场景只需生成一次脚本框架，不用重复生成相似代码，大幅降低 A4/A5 的 token 消耗。
- **代码复用**：同一流程的测试逻辑只维护一份。
- **人工评审高效**：评审时一眼看出哪些是数据变体、哪些是真正的不同流程。

#### `params` 中 secret 的 `${secret:参数名}` 占位符约定

所有标记为 secret 的参数（如密码、Token），其值不得出现明文，必须使用 `${secret:参数名}` 占位符。运行时由测试框架从密钥管理服务解析替换。

> 注：JSON Schema 中通过约定（convention）而非强制 pattern 校验实现，因为 param 值在运行时才解析，schema 层面做全量校验复杂度较高。各 Agent skill 需自行遵守此约定。

#### `flow` 字段（action index 数组 / 文字描述）

优先使用 POM action index 数组，精确对应录制动作序列；当场景跨页面或有复杂逻辑时，可用文字描述兜底。

---

## 3. report.schema.json（会话报告）

### 阶段与角色

- **产出阶段**：A4（生成）+ A5（自修复）完成后，输出本次会话报告。
- **生产者**：A4/A5 Agent。
- **消费者/校验方**：
  - Django 侧：校验合法后入库，用于效果统计、质量看板、成本分析。

### 关键字段设计意图

#### `status` + `fix_rounds` + `self_heal_events[]`

完整记录一次生成/修复过程的最终状态、修复轮次和每轮的失败原因与修复动作。

**为什么这样设计？**

- **质量度量**：统计自修复成功率、平均修复轮次，评估 A5 能力。
- **问题归因**：`failure_summary` 可分类统计（定位器问题/选择器问题/环境问题等），指导产品改进。
- **审计追溯**：每一步修复动作都有记录，便于人工复核。

#### `model_usage`

记录本次会话累计消耗的 token，便于成本核算。

---

## 4. mock.schema.json（Mock 规则）

### 阶段与角色

- **产出阶段**：A2 识别需要 mock 的场景时生成，或人工在平台配置。
- **生产者**：A2 Agent / 人工配置。
- **消费者/校验方**：
  - Django 侧：存储和管理 Mock 规则。
  - A4/A5 Agent：生成 pytest 脚本时引用 mock 规则，使用相应的 mock 框架（如 pytest-mock、responses）。
  - 测试执行引擎：按规则匹配请求并返回 mock 响应。

### 关键字段设计意图

#### `scope`（case / taskset / global）

三级作用域，灵活控制 Mock 规则的生效范围，避免全局 mock 影响其他测试。

#### `priority` + 多规则匹配

多条规则都匹配时，按 `priority` 数值大者优先，便于覆盖默认规则。

---

## 版本化规则

本目录遵循 **语义化版本（SemVer）**：

- **Major 升级**：破坏性变更 —— 删除字段、修改字段类型、收紧 required 列表、修改字段语义。双端必须同步升级，旧产物不再兼容。
- **Minor 升级**：向下兼容的新增 —— 新增可选字段、新增枚举值、补充描述。旧产物仍然合法。
- **Patch 升级**：文档/注释修复、描述修正，不影响校验结果。

### 改契约的流程

1. 修改 schema 文件，更新 `schema_version`（每个 schema 独立版本号）和 `version.json` 中的 `contracts` 版本。
2. 同步更新 Django 侧的校验逻辑和 Agent 侧 skill 文档中的输出格式描述。
3. 在 `contracts/tests/` 中补充测试用例（正例 + 反例），确保双端行为一致。
4. 提交 MR，双端负责人共同评审。

### 版本文件

`version.json` 记录：

```json
{
  "contracts": "0.1.0",
  "dsh_pinned": "0.1.0-rc.6",
  "notes": "P0 草案；semver：破坏性变更升 major"
}
```

- `contracts`：本目录所有契约的整体版本号。
- `dsh_pinned`：当前配套的 DSH 平台版本。
- `notes`：备注信息。
