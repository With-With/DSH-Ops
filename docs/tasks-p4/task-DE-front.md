# P4 任务 DE-前端：任务集终止/进行中 + 回放视频/批量删除（前端部分）

> 你是一个独立主会话，负责 DSH-Ops P4 的两个前端增强。
> 仓库：`D:\AI-soft\AI-TESTHUB\DSH-Ops`（Vue3+Element Plus，`web/` 目录）。
> **git 纪律：不要执行任何 git 命令**。另有会话在改后端与其他前端页，只碰本任务书列出的文件。

## 后端契约（已实现/即将实现，按此对接）

**任务集（后端已完成）**：
- `GET /api/tasksets/<id>/` 与列表 `GET /api/tasksets/` 均含 `in_progress: bool`、`cancel_requested: bool`
- `POST /api/tasksets/<id>/cancel/` -> 202 {detail, status}（进行中）；409（终态且未请求）；幂等

**回放（后端实现中，契约如下）**：
- `GET /api/replays/` 列表每条含 `video_available: bool`、`video_url: str|null`
- `GET /api/replays/<id>/video/` -> webm 视频流（内嵌播放）
- `POST /api/replays/bulk-delete/` {ids: [1,2]} -> 200 {deleted: n}；空 ids 400

## 改动文件（只许碰这些）
- `web/src/views/tasksets/index.vue`
- `web/src/api/tasksets.js`
- `web/src/views/replay/index.vue`
- `web/src/api/replay.js`

## 任务集页（views/tasksets/index.vue）
1. **列表"状态"列增强**：`row.in_progress === true` 时在状态 tag 旁加一个蓝色小徽章"进行中"（闪烁动画可选，文字用 `row.current_stage || 'pipeline'` 如"进行中·extract"）
2. **详情抽屉按钮区**：
   - 任一进行中状态（replaying/extracting/designing/reviewing/generating）时显示红色【■ 终止流水线】按钮；点击 ElMessageBox.confirm 文案："将在**当前阶段结束后**停止（AI 阶段无法中断），是否继续？" -> `POST cancel` -> 成功 ElMessage + 按钮变"已请求终止"禁用态 + 重新拉详情
   - 一键流水线/单阶段按钮已有；进行中时原按钮已 disabled（逻辑已存在），新增终止按钮即可
   - api/tasksets.js 增 `cancelTaskset(id)`（timeout 30000）
3. 现有 3s 轮询逻辑复用（详情抽屉打开时轮询），终止后轮询到 failed（error 含"终止"）时提示"流水线已终止"

## 回放页（views/replay/index.vue）
1. **批量删除**：表格加 selection 列（el-table-column type=selection）；工具栏加【删除选中 n 条】（有选中才可点；confirm 后 POST bulk-delete，成功 ElMessage"已删除 n 条"+刷新列表）；行操作加单条【删除】（confirm）
2. **视频查看**：表格加"视频"列（video_available 绿点可用/灰不可用）；行操作加【查看视频】（video_available 才可点）-> 对话框/抽屉内嵌 `<video :src="row.video_url" controls style="width:100%">`（标题含 run id）；video 播放器样式自适应
3. api/replay.js 增 `bulkDeleteReplays(ids)`（timeout 30000）；video_url 直接用后端返回的（前端不加拼）

## 验收（全过后才算完成）
1. `cd web; npm run build` 成功（0 error）
2. `npm run dev` 起后 `Invoke-WebRequest http://localhost:5173/tasksets` 与 `/replay` 页面源 200（验完杀）
3. 若后端可用（127.0.0.1:8000）则连真实 API 冒烟：GET /api/tasksets/ 看到 in_progress 字段；POST cancel 对终态返回 409；GET /api/replays/ 看到 video_available 字段；bulk-delete 空 ids 400

完成后报告：文件清单、build 结果、冒烟结果、遗留。
