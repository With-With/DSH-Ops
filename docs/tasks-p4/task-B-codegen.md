# P4 任务 B：录制中心改造（codegen 浏览器录制 + AI 重组）

> 你是一个独立的主会话，负责 DSH-Ops 平台的 P4 改造任务 B。
> 仓库：`D:\AI-soft\AI-TESTHUB\DSH-Ops`（Django 5.2+DRF / Vue3+Element Plus，venv 在仓库根，playwright 已装）。
> **git 纪律：不要执行任何 git 命令**。
> 并行提示：另有 4 个会话在改其他模块，遇 `database is locked` 等 30 秒重试。

## 需求（用户原话）
"录制中心，并非是提交脚本，而是调用 Playwright codegen 自带的录制功能打开浏览器，通过浏览器的方式进行自行操作浏览器的方式进行录制；3.1 录制中心新增项，是否录制结束后自动AI分析；3.2 AI针对录制脚本分析，通过默认脚手架的方式对流程进行重新组装，形成一个标准稳定的UI自动化脚本"

## 边界（严格遵守）
- 只改：`server/apps/recorder/`、`web/src/views/recorder/index.vue`、`web/src/api/recording.js`
- **禁止改**：`server/config/`、router/layout、其他 app（**尤其不许改 agent_runtime 的 gateway mock 映射**）
- gateway 接口（lazy import 用）：`from apps.agent_runtime.gateway import AgentGateway`，`run_stage(stage, instruction, task_set_id=None, recording_id=None, timeout=None, input_files=None) -> AgentInvocation`（`.status/.parsed_json/.error/.id`）
- env `DSHOPS_AGENT_MODE=mock` 时 gateway 对未知 stage 返回 {ack:True}--所以你的 AI 重组服务**自己做 mock 分支**（mock 时本地模板拼装，real 才走 gateway，stage 名 `codegen_normalize`）
- 保留既有"提交脚本"能力（折叠为"手动导入"区）

## 后端设计
1. **codegen 会话** `apps/recorder/codegen.py`：
   - `POST /recordings/codegen/start/` {name?, start_url?}（默认 http://127.0.0.1:8000/api/demo/login/）-> 202 {session_id}：起子进程 `python -m playwright codegen --target python --browser chromium -o server/artifacts/codegen/<session_id>/raw_script.py <start_url>`（DETACHED 记 PID，模块级会话表；目录随建）
   - `GET /recordings/codegen/status/` -> {active, session_id, started_at, pid}
   - `POST /recordings/codegen/stop/` {session_id, auto_analyze?}：kill PID 树（taskkill /T /F）-> 轮询产物文件≤10s -> 空则返回提示不建 Recording；有则创建 Recording（raw_content=脚本，复用既有 parse）-> auto_analyze=true 时线程触发 AI 重组 -> 返回 {recording_id, actions_count}
   - 重复 start 409；stop 幂等
2. **AI 重组** `apps/recorder/normalizer.py`：
   - 内置 `SCAFFOLD_TEMPLATE`（标准 pytest+playwright 脚手架：fixture、test_main、`# STEP: <index> <action>` 注释区、断言占位、channel="chromium" 启动、异常截图钩子）
   - `normalize_recording(recording) -> Recording`（幂等）：mock=模板拼装动作；real=指令（pom-extraction SKILL + 脚手架全文 + 动作 JSON + raw 脚本，要求"组装进脚手架，只输出一个 ```python 围栏"）-> gateway(`codegen_normalize`, timeout 300) -> 剥围栏写 normalized_content；失败 warnings 追加
   - `POST /recordings/<id>/normalize/` -> 202（线程）；状态查询走详情（normalized_content + 模块级 running 表）
3. 单测：会话表状态机（409/幂等/stop 空产物提示）；normalizer mock 产出（含 SCAFFOLD 标记、动作数、幂等）；API 校验。**测试不真起浏览器**

## 前端设计（views/recorder/index.vue）
- 顶部"浏览器录制"卡：URL+名称+自动AI分析开关（el-switch）+【开始录制】（提示浏览器已开）+ 录制中状态条（红点+时长）+【结束并保存】（结果摘要）；3s 轮 status
- 列表加列：AI 重组状态徽章（idle/running/done/failed）+【AI 重组】+【查看脚本】抽屉双 tab（原始/标准化）
- 手动导入折叠区（el-collapse）
- api/recording.js 增 startCodegen/statusCodegen/stopCodegen/normalizeRecording

## 验收
1. `manage.py test apps.recorder` 全绿（既有测试不破坏）
2. `manage.py check` + `npm run build`
3. 实测：起后端（:8001 --noreload 验完杀）-> codegen/start -> sleep 5 -> stop（无头环境产物空，应返回明确提示不建记录、不 500）

完成后输出报告：文件清单、测试数、build、实测、遗留。
