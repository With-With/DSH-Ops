# P4 任务 A：运行时管理卡片化 + 组件安装/删除

> 你是一个独立的主会话，负责 DSH-Ops 平台的 P4 改造任务 A。
> 仓库：`D:\AI-soft\AI-TESTHUB\DSH-Ops`（Django 5.2+DRF 后端 / Vue3+Element Plus 前端，venv 在仓库根）。
> **git 纪律：不要执行任何 git 命令**（集成者统一提交）。
> 并行提示：另有 4 个会话在改其他模块，遇 `database is locked` 等 30 秒重试。

## 需求（用户原话）
"运行时管理标签，按卡片方式显示，DSH 的环境是否正常，playwright selenium Edge chrome 同样是卡片式，支持删除与安装"

## 边界（严格遵守，其他会话在改别的目录）
- 只改：`server/apps/runtime_mgr/`（后端）、`web/src/views/runtimes/index.vue` + `web/src/api/runtime.js`（前端）
- **禁止改**：`server/config/`、其他 app、`web/src/router/`、`web/src/layout/`、git
- 模型继承 `apps.core.models.BaseModel`（软删规范）；已有 Runtime 模型与 detect_runtime/health_check/delete_runtime 服务在 services.py，可参考复用

## 后端设计
新增"组件管理"能力（与既有 DSH 环境检测并存）：

1. **组件清单与检测** `apps/runtime_mgr/components.py`：
   - 检测四类组件：
     - `dsh`：平台 dsh（复用既有 detect_runtime 逻辑；安装=返回指引不自动装；删除走既有 delete_runtime）
     - `playwright`：`importlib.util.find_spec("playwright")` + 浏览器通道检测（chromium/msedge/chrome/firefox）
     - `selenium`：find_spec("selenium")
     - `browsers`：Edge/Chrome 系统安装检测（注册表 `HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe` / `chrome.exe`，用 winreg，失败则常见路径探测）
   - `detect_components() -> list[dict]`：每项 {key, name, kind, installed, version, detail, actions, install_hint}
2. **安装/删除 API**（挂 RuntimeViewSet 的 action 或独立路径均可，路由不加 api/ 前缀）：
   - `GET /runtimes/components/` -> 组件状态列表
   - `POST /runtimes/components/install/` {key} -> 202，线程执行：pip install selenium / pip install playwright / playwright install chromium（env 加 PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright/）；系统 Edge/Chrome 不可安装只回提示
   - `POST /runtimes/components/delete/` {key, confirm: true} -> 线程 pip uninstall -y；confirm 缺失 400
   - 模块级字典记进行中任务 {key: {op, started_at}}；同 key 进行中再触发 409
   - 写 AuditLog（apps.core.models.AuditLog，action/detail）
3. 单测：检测函数（mock find_spec/winreg）、API 参数校验、409 防重入；**既有 19 个测试不得破坏**

## 前端设计（views/runtimes/index.vue 重写为卡片布局）
- 顶部 DSH 环境大卡片（版本/来源/状态徽章 + 健康检查/删除按钮，数据走既有 /api/runtimes/）
- 下方组件卡片网格（playwright/selenium/Edge/Chrome/chromium通道）：图标+名称+状态（已安装绿/未安装灰/操作中蓝）+版本+【安装】/【删除】（确认弹窗、进行中 loading）；3s 轮询（有进行中任务时）
- api/runtime.js 增 getComponents/installComponent/deleteComponent（timeout 30000）

## 验收（全过后才算完成）
1. `cd server; ..\venv\Scripts\python.exe manage.py test apps.runtime_mgr` 全绿
2. `..\venv\Scripts\python.exe manage.py check` 通过
3. `cd web; npm run build` 成功
4. 起后端（manage.py runserver 127.0.0.1:8001 --noreload，验完杀掉）curl 实测 GET /api/runtimes/components/ 返回四类组件真实状态

完成后输出报告：文件清单、测试数、build 结果、组件检测结果示例、遗留问题。
