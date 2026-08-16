# DSH-Ops

以 DeepSeek Harness（DSH）为 AI Agent 运行时的测试自动化平台：录制 -> trace 回放 -> AI 提取元素/POM -> AI 场景矩阵 -> AI 生成并自修复脚本 -> 入库 -> 确定性回归执行。

## 仓库结构

```
DSH-Ops/
├── server/          # Django 5 + DRF + Celery：任务集状态机、元素仓、评审、RuntimeMgr、AI 配置中心
│   └── apps/
│       ├── core/            # 公共基类（BaseModel：软删 + 审计字段）
│       ├── runtime_mgr/     # M1  DSH 环境检测/版本/健康检查/删除
│       ├── recorder/        # M3  录制接收（P1）
│       ├── replay/          # M3  trace 回放（P1）
│       ├── agent_runtime/   # M8  AgentGateway：dsh 子进程管理（P2）
│       ├── asset_repo/      # M4  元素仓/POM/场景矩阵，先搜后建（P1）
│       ├── tasksets/        # M6  任务集状态机（P1）
│       ├── reviews/         # M6  评审收件箱（P2）
│       ├── themes/          # M2  多皮肤（P1）
│       ├── ai_config/       # M8  AI 配置中心（P3）
│       ├── testdata/        # M9  参数化/SQL数据源/数据驱动/Mock（P1-P3）
│       ├── obs_center/      # M10 Allure/日志/飞书/邮件通知（P1-P3）
│       └── mcp/             #     MCP server：query_elements 等（P2）
├── agent/           # DSH 侧资产（源码零改动）
│   ├── runtime/     #   平台专用 dsh 局部安装（package.json 锁版本；node_modules 不入库）
│   ├── home/        #   平台专用 DSH_HOME（凭据/会话，不入库）
│   └── skills/      #   tester.md / tester_pro.md 等 agent 技能（入库）
├── web/             # Vue3 + Vite + Element Plus + amis：状态板/评审收件箱/RuntimeMgr
├── contracts/       # JSON Schema 单一真相源：pom / matrix / report / mock / version
├── docs/            # 项目文档（docs/skills-local/ 为本地私有模块 skill 文档，不入库）
└── scripts/         # 启动/部署脚本
```

## 快速启动（开发）

见 `docs/DEPLOY.md`。

## 核心原则

1. **AI 只进工厂和分诊室，不进回归线**：生成阶段用 DSH agent，执行阶段纯确定性。
2. **contracts/ 是唯一接口真相**：Django 校验 DSH 输出、DSH skill 说明输出格式，都引用同一份 schema。
3. **先搜后建**：元素/知识先进仓检索，未命中才让 LLM 新建（省 token）。
4. **DSH 源码零改动**：平台扩展只通过 profile / skills / MCP，不做 fork。
5. **所有业务表**：软删 + created_at/updated_at/created_by/updated_by。
