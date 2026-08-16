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

Django admin：http://localhost:8000/api/admin/（首次自行 `manage.py createsuperuser`）。

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
4. **回放接口为同步执行**（30~90s），前端已设 120s 超时；P2 引入 Celery 后改异步。
5. **requirements.txt**：`pip install -r server\requirements.txt`（P1 起新增 playwright）。
   国内网络若超时（files.pythonhosted.org 不通），加清华镜像：
   `pip install -r server\requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`。

## 五、常见问题

1. **检测不到运行时**：确认 `agent/runtime/node_modules/.bin/dsh.cmd` 存在（没跑过 install_all），
   检测会回退找全局 dsh（`where dsh`）。
2. **健康检查失败**：先看 RuntimeMgr 页的报错摘要；多为 DSH_HOME 目录缺失或 node 版本不符。
3. **前端连不上后端**：确认 8000 已起；Vite 代理只对 `/api` 前缀生效。
