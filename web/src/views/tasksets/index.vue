<template>
  <div class="tasksets-page">
    <el-card shadow="never" class="main-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">任务集</span>
          <el-button type="primary" :icon="Plus" @click="openCreateDialog">新建任务集</el-button>
        </div>
      </template>

      <el-table
        v-loading="loading"
        :data="tasksetList"
        stripe
        style="width: 100%"
      >
        <template #empty>
          <el-empty description="暂无任务集，点击【新建任务集】创建第一个">
            <el-button type="primary" :icon="Plus" @click="openCreateDialog">新建任务集</el-button>
          </el-empty>
        </template>

        <el-table-column prop="name" label="名称" min-width="180" show-overflow-tooltip />
        <el-table-column label="录制 ID" width="120" align="center">
          <template #default="{ row }">
            <span v-if="row.recording_id">#{{ row.recording_id }}</span>
            <span v-else class="empty-tip">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" effect="light">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="current_stage" label="当前阶段" width="140">
          <template #default="{ row }">
            <span v-if="row.current_stage">{{ row.current_stage }}</span>
            <span v-else class="empty-tip">—</span>
          </template>
        </el-table-column>
        <el-table-column label="correlation_uuid" width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.correlation_uuid" class="uuid-text" :title="row.correlation_uuid">
              {{ row.correlation_uuid.slice(0, 8) }}…
            </span>
            <span v-else class="empty-tip">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            <span v-if="row.created_at">{{ formatTime(row.created_at) }}</span>
            <span v-else class="empty-tip">—</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="100" fixed="right" align="center">
          <template #default="{ row }">
            <el-button
              type="primary"
              link
              size="small"
              :icon="View"
              @click="handleViewDetail(row)"
            >
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建任务集对话框 -->
    <el-dialog
      v-model="createDialogVisible"
      title="新建任务集"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="任务集名称">
          <el-input v-model="createForm.name" placeholder="请输入任务集名称" maxlength="120" show-word-limit />
        </el-form-item>
        <el-form-item label="录制脚本">
          <el-select
            v-model="createForm.recording_id"
            placeholder="请选择录制脚本"
            filterable
            style="width: 100%"
            :loading="recordingsLoading"
          >
            <el-option
              v-for="item in recordingOptions"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <div class="form-tip">
          <el-alert
            title="提交后将同步执行回放，耗时约 30~90 秒"
            type="info"
            :closable="false"
            show-icon
            size="small"
          />
        </div>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="creating"
          @click="handleCreate"
        >
          {{ creating ? '执行中...' : '确认创建' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 详情抽屉 -->
    <el-drawer
      v-model="detailDrawerVisible"
      title="任务集详情"
      size="50%"
      @close="handleDetailClose"
    >
      <div v-if="currentDetail" class="detail-content">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="名称">{{ currentDetail.name }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTagType(currentDetail.status)" effect="light">
              {{ statusText(currentDetail.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="当前阶段">{{ currentDetail.current_stage || '—' }}</el-descriptions-item>
          <el-descriptions-item label="correlation_uuid">{{ currentDetail.correlation_uuid || '—' }}</el-descriptions-item>
          <el-descriptions-item label="录制 ID">{{ currentDetail.recording_id || '—' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatTime(currentDetail.created_at) || '—' }}</el-descriptions-item>
          <el-descriptions-item v-if="currentDetail.error" label="错误信息">
            <span class="error-text">{{ currentDetail.error }}</span>
          </el-descriptions-item>
        </el-descriptions>

        <!-- 智能体阶段操作区 -->
        <div class="stage-actions-section">
          <h4 class="section-title">智能体阶段</h4>
          <div class="stage-actions">
            <el-button
              type="primary"
              :icon="MagicStick"
              :loading="stageRunning === 'extract'"
              :disabled="!canRunExtract"
              @click="handleRunStage('extract')"
            >
              {{ stageRunning === 'extract' ? '智能体执行中…' : 'A1 提取' }}
            </el-button>
            <el-button
              type="success"
              :icon="Share"
              :loading="stageRunning === 'design'"
              :disabled="!canRunDesign"
              @click="handleRunStage('design')"
            >
              {{ stageRunning === 'design' ? '智能体执行中…' : 'A2 设计' }}
            </el-button>
          </div>
          <div v-if="!canRunExtract && !canRunDesign && currentDetail.status !== 'failed'" class="stage-hint">
            <el-text type="info" size="small">
              提示：回放完成后可执行 A1 提取，提取完成后可执行 A2 设计。
            </el-text>
          </div>
          <div v-if="currentDetail.status === 'failed'" class="stage-hint">
            <el-text type="warning" size="small">
              当前状态为失败，可重新触发 A1 提取。
            </el-text>
          </div>
        </div>

        <!-- 草案列表 -->
        <div class="drafts-section">
          <h4 class="section-title">草案列表</h4>
          <el-empty
            v-if="!currentDetail.drafts || currentDetail.drafts.length === 0"
            description="暂无草案"
            :image-size="60"
          />
          <div v-else class="draft-list">
            <div
              v-for="draft in currentDetail.drafts"
              :key="draft.id"
              class="draft-item"
            >
              <div class="draft-main">
                <el-tag
                  :type="draftKindTagType(draft.kind)"
                  effect="dark"
                  size="small"
                  class="draft-kind"
                >
                  {{ draft.kind === 'pom' ? 'POM' : '矩阵' }}
                </el-tag>
                <el-tooltip :content="draft.valid ? '校验通过' : '校验未通过'" placement="top">
                  <el-icon
                    :class="['draft-valid-icon', draft.valid ? 'valid' : 'invalid']"
                  >
                    <CircleCheck v-if="draft.valid" />
                    <CircleClose v-else />
                  </el-icon>
                </el-tooltip>
                <el-tag
                  :type="draftStatusTagType(draft.status)"
                  effect="light"
                  size="small"
                >
                  {{ draftStatusText(draft.status) }}
                </el-tag>
                <span class="draft-version">v{{ draft.schema_version }}</span>
                <span class="draft-time">{{ formatTime(draft.created_at) }}</span>
              </div>
              <div class="draft-actions">
                <el-button
                  size="small"
                  link
                  type="primary"
                  @click="handleViewDraftJson(draft)"
                >
                  查看 JSON
                </el-button>
              </div>
            </div>
          </div>
        </div>

        <!-- 阶段时间线 -->
        <div class="timeline-section">
          <h4 class="section-title">阶段执行时间线</h4>
          <el-empty
            v-if="!currentDetail.stage_jobs || currentDetail.stage_jobs.length === 0"
            description="暂无阶段数据"
            :image-size="60"
          />
          <el-timeline v-else>
            <el-timeline-item
              v-for="(job, idx) in currentDetail.stage_jobs"
              :key="idx"
              :timestamp="formatTime(job.finished_at || job.started_at) || '—'"
              placement="top"
              :type="timelineItemType(job.status)"
              :hollow="job.status === 'running' || job.status === 'created'"
            >
              <div class="timeline-content">
                <div class="timeline-header">
                  <span class="stage-name">{{ job.stage }}</span>
                  <el-tag :type="statusTagType(job.status)" size="small" effect="light">
                    {{ statusText(job.status) }}
                  </el-tag>
                </div>
                <div v-if="job.detail" class="timeline-detail" :title="job.detail">
                  {{ typeof job.detail === 'string' ? job.detail : JSON.stringify(job.detail) }}
                </div>
                <div v-if="job.external_ref" class="timeline-ref">
                  <span class="ref-label">外部引用：</span>
                  <span class="ref-value">{{ job.external_ref }}</span>
                </div>
              </div>
            </el-timeline-item>
          </el-timeline>
        </div>
      </div>
    </el-drawer>

    <!-- 草案 JSON 查看抽屉 -->
    <el-drawer
      v-model="draftJsonDrawerVisible"
      title="草案详情"
      size="40%"
    >
      <div v-if="currentDraft" class="draft-json-content">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="类型">
            <el-tag :type="draftKindTagType(currentDraft.kind)" effect="dark" size="small">
              {{ currentDraft.kind === 'pom' ? 'POM' : '矩阵' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="draftStatusTagType(currentDraft.status)" effect="light" size="small">
              {{ draftStatusText(currentDraft.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="schema_version">v{{ currentDraft.schema_version }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatTime(currentDraft.created_at) }}</el-descriptions-item>
        </el-descriptions>

        <div class="json-section">
          <h4 class="section-title">JSON 内容</h4>
          <pre class="json-block"><code>{{ formatJson(currentDraft.content) }}</code></pre>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, View, MagicStick, Share, CircleCheck, CircleClose } from '@element-plus/icons-vue'
import {
  getTasksetList,
  createTaskset,
  getTasksetDetail,
  runStage,
} from '@/api/tasksets'
import { getRecordingList } from '@/api/recording'
import { formatTime } from '@/utils/format'
import { createPoller } from '@/utils/polling'

// ---- state ----
const loading = ref(false)
const tasksetList = ref([])

const createDialogVisible = ref(false)
const creating = ref(false)
const createForm = reactive({
  name: '',
  recording_id: null,
})

const recordingsLoading = ref(false)
const recordingOptions = ref([])

const detailDrawerVisible = ref(false)
const currentDetail = ref(null)
const detailLoading = ref(false)

// 阶段执行状态
const stageRunning = ref(null) // 'extract' | 'design' | null
let detailPoller = null

// 草案 JSON 抽屉
const draftJsonDrawerVisible = ref(false)
const currentDraft = ref(null)

// ---- 常量 / 工具 ----
const STATUS_MAP = {
  created:       { text: '已创建', type: 'info' },
  replaying:     { text: '回放中', type: 'primary' },
  replay_done:   { text: '回放完成', type: 'success' },
  extracting:    { text: '提取中', type: 'primary' },
  extract_done:  { text: '提取完成', type: 'success' },
  designing:     { text: '设计中', type: 'primary' },
  design_done:   { text: '设计完成', type: 'success' },
  failed:        { text: '失败', type: 'danger' },
  success:       { text: '成功', type: 'success' },
  running:       { text: '执行中', type: 'primary' },
  pending:       { text: '等待中', type: 'info' },
}

function statusTagType(status) {
  return STATUS_MAP[status]?.type || 'info'
}
function statusText(status) {
  return STATUS_MAP[status]?.text || status || '未知'
}

function timelineItemType(status) {
  const typeMap = {
    success: 'success',
    replay_done: 'success',
    extract_done: 'success',
    design_done: 'success',
    failed: 'danger',
    replaying: 'primary',
    extracting: 'primary',
    designing: 'primary',
    running: 'primary',
    created: 'info',
    pending: 'info',
  }
  return typeMap[status] || 'info'
}

// 草案相关
function draftKindTagType(kind) {
  return kind === 'pom' ? 'purple' : 'cyan'
}

const DRAFT_STATUS_MAP = {
  draft:    { text: '草稿', type: 'info' },
  approved: { text: '已通过', type: 'success' },
  rejected: { text: '已驳回', type: 'danger' },
}

function draftStatusTagType(status) {
  return DRAFT_STATUS_MAP[status]?.type || 'info'
}
function draftStatusText(status) {
  return DRAFT_STATUS_MAP[status]?.text || status || '未知'
}

function formatJson(obj) {
  if (obj == null) return ''
  try {
    return JSON.stringify(obj, null, 2)
  } catch (e) {
    return String(obj)
  }
}

// 是否可执行 A1 提取：replay_done 或 failed 状态
const canRunExtract = computed(() => {
  if (!currentDetail.value) return false
  if (stageRunning.value) return false
  const s = currentDetail.value.status
  return s === 'replay_done' || s === 'failed'
})

// 是否可执行 A2 设计：extract_done 状态
const canRunDesign = computed(() => {
  if (!currentDetail.value) return false
  if (stageRunning.value) return false
  return currentDetail.value.status === 'extract_done'
})

// ---- actions ----
async function fetchList() {
  loading.value = true
  try {
    const data = await getTasksetList()
    tasksetList.value = Array.isArray(data) ? data : (data?.results || [])
  } catch (err) {
    tasksetList.value = []
  } finally {
    loading.value = false
  }
}

async function fetchRecordings() {
  recordingsLoading.value = true
  try {
    const data = await getRecordingList()
    recordingOptions.value = Array.isArray(data) ? data : (data?.results || [])
  } catch (err) {
    recordingOptions.value = []
  } finally {
    recordingsLoading.value = false
  }
}

function openCreateDialog() {
  createForm.name = ''
  createForm.recording_id = null
  createDialogVisible.value = true
  fetchRecordings()
}

async function handleCreate() {
  if (!createForm.name.trim()) {
    ElMessage.warning('请输入任务集名称')
    return
  }
  if (!createForm.recording_id) {
    ElMessage.warning('请选择录制脚本')
    return
  }
  creating.value = true
  try {
    await createTaskset({
      name: createForm.name.trim(),
      recording_id: createForm.recording_id,
    })
    ElMessage.success('任务集创建并执行完成')
    createDialogVisible.value = false
    fetchList()
  } catch (err) {
    // 拦截器已提示
  } finally {
    creating.value = false
  }
}

async function handleViewDetail(row) {
  detailDrawerVisible.value = true
  currentDetail.value = null
  detailLoading.value = true
  try {
    const detail = await getTasksetDetail(row.id)
    currentDetail.value = detail
  } catch (err) {
    // 拦截器已提示
  } finally {
    detailLoading.value = false
  }
}

function stopDetailPoller() {
  if (detailPoller) {
    detailPoller.stop()
    detailPoller = null
  }
}

function handleDetailClose() {
  stopDetailPoller()
  stageRunning.value = null
}

// 执行阶段（A1 提取 / A2 设计）
async function handleRunStage(stage) {
  if (!currentDetail.value) return
  stageRunning.value = stage
  try {
    // 提交阶段任务，后端返回 202
    await runStage(currentDetail.value.id, stage)
    ElMessage.info(`${stage === 'extract' ? 'A1 提取' : 'A2 设计'}任务已提交，智能体执行中…`)

    // 开始轮询详情
    const pollStage = stage
    const targetRunningStatus = pollStage === 'extract' ? 'extracting' : 'designing'
    const targetDoneStatus = pollStage === 'extract' ? 'extract_done' : 'design_done'

    detailPoller = createPoller({
      fetchFn: () => getTasksetDetail(currentDetail.value.id),
      interval: 3000,
      isDone: (data) => data.status !== targetRunningStatus,
      onTick: (data) => {
        currentDetail.value = data
      },
      onDone: (data) => {
        currentDetail.value = data
        stageRunning.value = null
        if (data.status === targetDoneStatus) {
          ElMessage.success(`${pollStage === 'extract' ? 'A1 提取' : 'A2 设计'}执行成功`)
        } else if (data.status === 'failed') {
          ElMessage.error(`${pollStage === 'extract' ? 'A1 提取' : 'A2 设计'}执行失败`)
        } else {
          ElMessage.info(`状态已更新：${statusText(data.status)}`)
        }
        fetchList()
      },
      onError: () => {
        stageRunning.value = null
        // 错误已由拦截器提示
      },
    })
    detailPoller.start()
  } catch (err) {
    stageRunning.value = null
    // 409 等错误已由拦截器提示
  }
}

function handleViewDraftJson(draft) {
  currentDraft.value = draft
  draftJsonDrawerVisible.value = true
}

// ---- 生命周期 ----
onMounted(() => {
  fetchList()
})

onBeforeUnmount(() => {
  stopDetailPoller()
})
</script>

<style scoped>
.tasksets-page {
  height: 100%;
}

.main-card {
  height: 100%;
  border-radius: 8px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--do-fg);
}

.empty-tip {
  color: var(--do-fg-tertiary);
}

.uuid-text {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  color: var(--do-fg-secondary);
}

.form-tip {
  margin-top: 8px;
}

.detail-content {
  padding-right: 8px;
}

.error-text {
  color: var(--do-danger);
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
}

/* 智能体阶段操作区 */
.stage-actions-section {
  margin-top: 24px;
}

.stage-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.stage-hint {
  margin-top: 10px;
}

.section-title {
  margin: 0 0 16px 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--do-fg);
}

/* 草案列表 */
.drafts-section {
  margin-top: 24px;
}

.draft-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.draft-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: var(--do-bg);
  border-radius: 6px;
  border: 1px solid var(--do-border, #e4e7ed);
}

.draft-main {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.draft-kind {
  font-weight: 600;
}

.draft-valid-icon {
  font-size: 18px;
}

.draft-valid-icon.valid {
  color: var(--do-success, #67c23a);
}

.draft-valid-icon.invalid {
  color: var(--do-danger, #f56c6c);
}

.draft-version {
  font-size: 12px;
  color: var(--do-fg-secondary);
  font-family: 'Consolas', 'Monaco', monospace;
}

.draft-time {
  font-size: 12px;
  color: var(--do-fg-tertiary);
}

/* 草案 JSON 内容 */
.draft-json-content {
  padding-right: 8px;
}

.json-section {
  margin-top: 20px;
}

.json-block {
  margin: 0;
  padding: 12px;
  background: var(--do-bg);
  border: 1px solid var(--do-border, #e4e7ed);
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 60vh;
  overflow: auto;
  color: var(--do-fg);
}

/* 时间线 */
.timeline-section {
  margin-top: 24px;
}

.timeline-content {
  padding: 4px 0;
}

.timeline-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}

.stage-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--do-fg);
}

.timeline-detail {
  font-size: 12px;
  color: var(--do-fg-secondary);
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  margin-bottom: 4px;
}

.timeline-ref {
  font-size: 12px;
  color: var(--do-fg-tertiary);
}

.ref-label {
  color: var(--do-fg-tertiary);
}

.ref-value {
  font-family: 'Consolas', 'Monaco', monospace;
  color: var(--do-primary);
}
</style>
