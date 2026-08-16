# DSH-Ops 架构决策记录（ADR 摘要）

> 本文记录 P0 阶段定型的高层设计决策及其理由。改架构先读这里。

## 1. 平台定位：Django 当导演，DSH 当 AI 演员

- **确定性世界**（任务集状态机、评审、元素仓、执行线、报告通知）在 Django/Celery；
- **AI 阶段**（A1 提取 / A2 设计 / A4+A5 生成自修复）每阶段一次 `dsh --profile testhub --cwd <workspace> headless "<指令>"` 子进程调用；
- **workspace 目录即接口**：Django 写 `input/`，agent 写 `output/*.json`，产物用 `contracts/` 的 schema 双端校验；
- **AI 只进工厂和分诊室，不进回归线**：夜间回归零 LLM 依赖、零 token、确定性。

## 2. Agent 拓扑：3 个起步、5 个封顶，导演是代码不是 LLM

| 编号 | 角色 | 阶段 | 上下文 |
|---|---|---|---|
| A1 | 元素提取器 | trace+脚本 -> pom.json | DOM/aria 快照（不喂给下游） |
| A2 | 用例设计师 | POM+需求 -> 场景矩阵 | 干净操作流+需求规则（不看原始 DOM） |
| A3 | 评审员（自动门） | 矩阵质检 | tester_pro.md 人设 |
| A4+A5 | 生成+自修复 | 矩阵+POM -> pytest 跑通 | **一个 DSH 会话内闭环**（生成->跑->读错->修，≤N 轮） |

拆分单位 = 任务类型（上下文异构才拆），不是子项；并发单位 = 任务实例（场景/模块），
agent 角色之间是依赖链不并发。**A4+A5 是 DSH 的核心价值点**（原生 coding agent 循环）。

## 3. 元素仓 search-first（省 token 的根本机制）

LLM 只处理"新知识"，检索交给数据库：A1 产出候选 -> MCP `query_elements` 三级匹配
（URL 归一化 -> role+name -> 快照相似度）-> 高置信复用 / 中置信进评审 / 未命中才新建。
跨任务集强制合并去重（场景 2 复用场景 1 的 3/4 页面），元素仓是自愈的地基：一处修复处处生效。

## 4. 数据驱动折叠（M9）

A2 对场景做分类：**同流程不同数据 -> classification=data_driven，折叠为 1 脚本 + N 数据行**
（`@pytest.mark.parametrize`）；不同流程才独立脚本。录制中的字面量（fill("admin123")）
必须"上提"为参数（`param_ref`），凭据型标 secret、全链路脱敏、仅存引用。

## 5. DSH 集成纪律（源码零改动）

- 平台运行时：`agent/runtime/` 局部 npm 安装，版本锁死（`0.1.0-rc.6`），升级=显式 bump+冒烟；
- 平台 DSH_HOME：`agent/home/`，与开发者个人 `~/.dsh` 完全隔离（凭据/会话/配置/版本四隔离）；
- 扩展只走三条路：skills（知识包）/ MCP（平台能力桥）/ 自有插件包（需要自定义工具时）；
- **绝不 fork DSH 内核**：三问自检（要改 loop 吗？业务数据进 Node 吗？养得起 TS 内核吗？）。

## 6. 数据与安全底线

- 所有业务表：软删 + created_at/updated_at/created_by/updated_by（`apps/core/BaseModel`）；
- 密钥（AI provider / SMTP / 飞书 / SQL 数据源）Fernet 加密落库，API 只回掩码；
- SQL 数据源三闸：只读强制、SELECT 白名单、行数上限+超时；
- A4/A5 跑 shell 的沙箱：低权限账户 + workspace 路径 confinement（P3 前上线）；
- ID 关联链贯穿全程：recording -> trace -> taskset -> stage_job -> execution_run -> case -> data_row。

## 7. 与旧 TestHub 的关系

旧平台（`../testhub_platform`）不再演进，仅作零件库：已移植 `code_parser.py`、
`tester.md/tester_pro.md` 提示词；P1 将移植 `ui_flow_runner.py`（加 tracing）与
`AIModelConfig` 多 provider 模式。
