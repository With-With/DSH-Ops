# DSH-Ops 部署与启动指南（P0）

> 适用：Windows 开发机。生产部署（Linux）在 P2 后补充。

## 前置要求

| 组件 | 版本要求 | 检查命令 |
|---|---|---|
| Python | ≥ 3.11（本库在 3.13 验证） | `python --version` |
| Node.js | ≥ 20 且 < 25（本库在 24 验证） | `node -v` |
| Git | 任意较新版本 | `git --version` |

不需要全局安装 DeepSeek Harness——平台自带一套锁版本的局部安装（见 `agent/README.md`）。
如果机器上恰好全局装了 dsh，RuntimeMgr 检测会把它作为回退来源，但两套互不影响。

## 一、首次安装（一条命令）

```powershell
cd D:\AI-soft\AI-TESTHUB\DSH-Ops
powershell -ExecutionPolicy Bypass -File scripts\install_all.ps1
```

脚本做五件事：建 venv → 装后端依赖 → 数据库迁移（默认 SQLite，零配置）→ 前端 npm install →
平台专用 DSH 运行时安装（锁 0.1.0-rc.6）。

## 二、日常启动（两个终端）

```powershell
# 终端 1：后端 :8000
powershell -ExecutionPolicy Bypass -File scripts\start_backend.ps1

# 终端 2：前端 :5173（/api 自动代理到 8000）
powershell -ExecutionPolicy Bypass -File scripts\start_frontend.ps1
```

浏览器打开 **http://localhost:5173** → 左侧菜单「运行时管理」→ 点 **【检测环境】**：

- 平台局部运行时（`agent/runtime`）会被检测出，显示版本 0.1.0-rc.6；
- 若检测到版本与 `contracts/version.json` 锁定版本不一致，状态显示为 warning（版本漂移告警）；
- 行内 **【健康检查】** 会以平台 DSH_HOME 跑 `dsh --dump-default-config` 验证可用性；
- **【删除】**：默认软删（数据库层面）；勾选"物理删除"才真正删目录，且写审计日志。

Django admin：http://localhost:8001/api/admin/（首次自行 `manage.py createsuperuser`）。

## 三、目录与环境变量速查

| 变量 | 默认 | 说明 |
|---|---|---|
| `DSHOPS_SECRET_KEY` | dev 固定值 | 生产必换 |
| `DSHOPS_DEBUG` | 1 | 生产置 0 |
| `DSHOPS_DB` | 空(sqlite) | `mysql` 时读 DB_NAME/DB_USER/DB_PASSWORD/DB_HOST/DB_PORT |
| `DSHOPS_DSH_HOME` | `<仓库>/agent/home` | 平台 DSH_HOME 覆盖 |

关键目录：`agent/home`（平台 DSH 会话/凭据，已 gitignore）、`docs/skills-local/`（本地模块
skill 文档，**按团队约定不入库**）、`contracts/`（双端共享 JSON Schema，改动需双端同步）。

## 四、测试

```powershell
cd D:\AI-soft\AI-TESTHUB\DSH-Ops\server
..\venv\Scripts\python.exe manage.py test apps.runtime_mgr
# P1 全链冒烟（录制->解析->trace回放->元素先搜后建->任务集，需真实浏览器）
powershell -ExecutionPolicy Bypass -File ..\scripts\smoke_p1.ps1
```

## 四B、P1 补充说明（录制/回放/元素仓/任务集）

1. **Playwright 浏览器通道**：回放默认 `channel=msedge`（Windows 自带 Edge，**免下载**）。
   如需换：环境变量 `DSHOPS_BROWSER_CHANNEL=chromium|chrome|firefox|msedge`；用 chromium 需先
   `..\venv\Scripts\python.exe -m playwright install chromium`。
2. **回放产物**：trace.zip 存于 `server/artifacts/traces/replay_<id>/`（已 gitignore），
   可在「回放中心」页面直接下载，或用 `npx playwright show-trace <文件>` 本地打开。
3. **演示登录页**：`/api/demo/login/`（平台自带），配套金样本脚本 `scripts/demo_login_recorded.py`，
   供录制/回放链路自包含验证。
4. **回放接口默认同步执行**（30~90s），前端已设 120s 超时；P2 起支持可选异步（见四C-3）。
5. **requirements.txt**：`pip install -r server\requirements.txt`（P1 起含 playwright，P2 起含
   jsonschema/mcp）。国内网络若超时（files.pythonhosted.org 不通），加清华镜像：
   `pip install -r server\requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`。

## 四C、P2 补充说明（DSH 智能体阶段 A1/A2 + 草案评审）

1. **AgentGateway 运行模式**：环境变量 `DSHOPS_AGENT_MODE`
   - `mock`（测试默认）：不调 LLM，返回 `apps/agent_runtime/fixtures/` 金样本（POM/matrix）；
   - `real`（默认）：经平台 dsh（`agent/runtime/`，锁 0.1.0-rc.6）以 `--profile headless` 执行阶段指令，
     stdout 取最终回答并解析 JSON。超时 `DSHOPS_AGENT_TIMEOUT`（默认 300s）。
   - **指令传递**：完整指令写入工作区 `task.md`，命令行只传短指令（Windows cmd.exe
     命令行 8191 字符上限，A1 指令含 schema 全文实测 9807 字符必超；智能体读取工作区文件执行）。
2. **DSH_HOME 与凭据**：默认**继承用户全局 `~/.dsh`**（本机已可用的凭据直接生效）；
   隔离模式设 `DSHOPS_AGENT_HOME=<目录>` 后需自行在该 home 配置模型凭据。
3. **A1/A2 异步语义**：`POST /api/tasksets/<id>/stages/` {stage: extract|design} 返回 202，
   前端轮询任务集详情（extracting/designing -> 终态）；守卫失败 409。
   回放可选异步：`POST /api/replays/?async=1` 立即返回 running。
4. **元素并入**：A1 产出的 POM 元素经 search-first 三级匹配后并入元素仓（high 复用 / none 新建，
   source=recording），不会重复建档。
5. **草案评审**：A1/A2 产出 pom/matrix 草案（经 contracts JSON Schema 校验），
   在「评审中心」通过/驳回（终态不可改，重评 409）。
6. **MCP server**（elements query 工具，供 DSH 智能体调用）：
   `..\venv\Scripts\python.exe manage.py run_mcp_server`（stdio 协议；
   注册进 dsh profile 的方式见 `docs/skills-local/backend-agent-runtime/SKILL.md`）。
7. **P2 冒烟**：`powershell -ExecutionPolicy Bypass -File scripts\smoke_p2.ps1`（mock 全链）；
   真实链路加 `-Real`（会真实调用 DSH，耗时约 1-3 分钟/阶段）。

## 四D、P3 补充说明（A3 评审 / A4 生成自修复 / 一键流水线 / 观测中心）

1. **一键流水线**：`POST /api/tasksets/<id>/pipeline/`（202 异步）顺序执行
   replay → A1 提取 → A2 设计 → A3 评审 → A4 生成+自修复，任一步失败即停；
   前端任务集详情页【▶ 一键流水线】按钮 + 五阶段全景步骤条。
2. **A4 生成闭环**：智能体在独立工作区读 matrix/pom/elements 输入文件，生成 pytest 脚本、
   用 `venv\Scripts\python.exe -m pytest` 运行、读错自修（≤3 轮）；
   产物 `GeneratedRun` 含脚本全文，页面可直接查看/复用。
3. **A3 自动门**：verdict=pass 才放行；否则任务集 failed（评审报告在任务集详情可见）。
4. **testhub profile 说明**：`dsh plugin` 建自定义 profile 被 DSH workspace 私有包阻塞
   （npm 双源 404 `@deepseek-ai/dsh-code-runtime-worker`）。
   **平台实际使用隔离 home（agent/home）的 headless profile**，能力等价；
   凭据已复制为 `agent/home/.credentials.yaml`（隔离部署请自行配置该文件）。
5. **观测中心**：`/api/obs/overview/`（调用/回放/阶段/生成统计）+
   `/api/obs/activity/`（活动流）；前端「观测中心」页（统计卡 + CSS 分布图 + 活动表）。
6. **P3 冒烟**：`powershell -ExecutionPolicy Bypass -File scripts\smoke_p3.ps1`（mock，
   秒级）；真实链路 `-Real`（全链约 6-10 分钟，A4 阶段含真实浏览器生成运行）。

## 五、常见问题

1. **检测不到运行时**：确认 `agent/runtime/node_modules/.bin/dsh.cmd` 存在（没跑过 install_all），
   检测会回退找全局 dsh（`where dsh`）。
2. **健康检查失败**：先看 RuntimeMgr 页的报错摘要；多为 DSH_HOME 目录缺失或 node 版本不符。
3. **前端连不上后端**：确认 8000 已起；Vite 代理只对 `/api` 前缀生效。
