# Skill: POM 提取（A1 元素提取器）

> P2 阶段启用的 DSH agent 技能。P0 先立骨架：输入输出契约已定，提示词在 P2 打磨。

## 职责

输入一个 workspace（含 codegen 脚本 + 解包后的 trace 快照），产出符合
`contracts/pom.schema.json` 的 `output/pom.json`。

## 输入（workspace 目录约定）

```
workspace/
├── input/
│   ├── recorded.py        # codegen 原始脚本
│   ├── trace/             # trace.zip 解包产物（含每步 DOM/aria 快照）
│   └── requirement.md     # 需求上下文（可空）
└── output/
    └── pom.json           # 产物（Django 侧用同版 schema 校验）
```

## 输出规则（关键）

1. **字面量上提**：脚本里的 `fill("admin123456")` 不允许内联在 action.value，
   必须上提为 `params[]` 并在 action.param_ref 引用；凭据类标 `secret: true`。
2. **多候选定位器**：每个元素至少给出 role/语义类候选，快照允许时补 css/xpath 候选，
   按健壮度标注 robustness。
3. **页面切分**：按 goto/popup 边界 + URL 模式切页面对象。
4. **search-first**：通过 MCP 工具 `query_elements` 先查元素仓；命中则
   `exists_in_repo: true` 且带 `matched_existing_page_id`，未命中才新建。
5. 版本号固定填 schema 的 `schema_version`，Django 侧不认旧版本。

## 校验

Django AgentGateway 用 `contracts/pom.schema.json`（同版本）校验，不合格自动重试 ≤2 次。
