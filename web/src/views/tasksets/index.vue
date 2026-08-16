<template>
  <div class="tasksets-page">
    <el-card shadow="never" class="main-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">任务集</span>
          <div class="header-actions">
            <el-button
              type="danger"
              plain
              :icon="Delete"
              :disabled="selectedRows.length === 0"
              @click="handleBulkDelete"
            >
              删除选中({{ selectedRows.length }})
            </el-button>
            <el-button type="primary" :icon="Plus" @click="openCreateDialog">新建任务集</el-button>
          </div>
        </div>
      </template>

      <el-table
        v-loading="loading"
        :data="tasksetList"
        stripe
        style="width: 100%"
        @selection-change="handleSelectionChange"
      >
        <template #empty>
          <el-empty description="暂无任务集，点击【新建任务集】创建第一个">
            <el-button type="primary" :icon="Plus" @click="openCreateDialog">新建任务集</el-button>
          </el-empty>
        </template>

        <el-table-column type="selection" width="42" />
        <el-table-column prop="name" label="名称" min-width="180" show-overflow-tooltip />
        <el-table-column label="录制 ID" width="120" align="center">
          <template #default="{ row }">
            <span v-if="row.recording_id">#{{ row.recording_id }}</span>
            <span v-else class="empty-tip">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="170" align="center">
          <template #default="{ row }">
            <div class="status-cell">
              <el-tag :type="statusTagType(row.status)" effect="light">
                {{ statusText(row.status) }}
              </el-tag>
              <el-tag
                v-if="row.cancel_requested"
                type="warning"
                effect="dark"
                size="small"
                class="in-progress-badge"
              >
                已请求终止
              </el-tag>
              <el-tag
                v-else-if="row.in_progress"
                type="primary"
                effect="dark"
                size="small"
                class="in-progress-badge"
              >
                <span class="pulse-dot"></span>进行中{{ row.current_stage ? '·' + row.current_stage : '' }}
              </el-tag>
            </div>
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

        <el-table-column label="操作" width="160" fixed="right" align="center">
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
            <el-button
              type="danger"
              link
              size="small"
              :icon="Delete"
              @click="handleDelete(row)"
            >
              删除
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
            <div class="detail-status">
              <el-tag :type="statusTagType(currentDetail.status)" effect="light">
                {{ statusText(currentDetail.status) }}
              </el-tag>
              <el-tag
                v-if="currentDetail.cancel_requested"
                type="warning"
                effect="dark"
                size="small"
                class="in-progress-badge"
              >
                已请求终止
              </el-tag>
              <el-tag
                v-else-if="currentDetail.in_progress"
                type="primary"
                effect="dark"
                size="small"
                class="in-progress-badge"
              >
                <span class="pulse-dot"></span>进行中{{ currentDetail.current_stage ? '·' + currentDetail.current_stage : '' }}
              </el-tag>
            </div>
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
          <h4 class="section-title">智能体流水线</h4>
          <div class="stage-actions">
            <el-button
              v-if="isInProgress"
              type="danger"
              :icon="CircleClose"
              :disabled="cancelRequested"
              @click="handleCancelPipeline"
            >
              {{ cancelRequested ? '已请求终止…' : '■ 终止流水线' }}
            </el-button>
            <el-button
              type="primary"
              :icon="CaretRight"
              :loading="pipelineRunning"
              :disabled="!canRunPipeline"
              @click="handleRunPipeline"
            >
              {{ pipelineRunning ? '流水线执行中…' : '▶ 一键流水线' }}
            </el-button>
            <el-button
              type="primary"
              plain
              :icon="MagicStick"
              :loading="stageRunning === 'extract'"
              :disabled="!canRunExtract"
              @click="handleRunStage('extract')"
            >
              {{ stageRunning === 'extract' ? '智能体执行中…' : 'A1 提取' }}
            </el-button>
            <el-button
              type="success"
              plain
              :icon="Share"
              :loading="stageRunning === 'design'"
              :disabled="!canRunDesign"
              @click="handleRunStage('design')"
            >
              {{ stageRunning === 'design' ? '智能体执行中…' : 'A2 设计' }}
            </el-button>
            <el-button
              type="warning"
              plain
              :icon="View"
              :loading="stageRunning === 'review'"
              :disabled="!canRunReview"
              @click="handleRunStage('review')"
            >
              {{ stageRunning === 'review' ? '智能体执行中…' : 'A3 评审' }}
            </el-button>
            <el-button
              type="danger"
              plain
              :icon="Document"
              :loading="stageRunning === 'generate'"
              :disabled="!canRunGenerate"
              @click="handleRunStage('generate')"
            >
              {{ stageRunning === 'generate' ? '智能体执行中…' : 'A4 生成' }}
            </el-button>
          </div>
          <div class="stage-hint">
            <el-text type="info" size="small">
              流水线顺序：回放 → A1 提取 → A2 设计 → A3 评审 → A4 生成+自修复；失败阶段可重试。
            </el-text>
          </div>
        </div>

        <!-- 五阶段全景 -->
        <div v-if="currentDetail.stage_jobs && currentDetail.stage_jobs.length" class="pipeline-steps-section">
          <h4 class="section-title">阶段全景</h4>
          <el-steps :active="pipelineActiveStep" align-center finish-status="success">
            <el-step
              v-for="s in PIPELINE_STAGES"
              :key="s.stage"
              :title="s.title"
              :status="stepStatus(s.stage)"
            />
          </el-steps>
        </div>

        <!-- A3 评审报告 -->
        <div v-if="reviewJob" class="review-section">
          <h4 class="section-title">A3 评审报告</h4>
          <el-alert
            :type="reviewJob.detail?.verdict === 'pass' ? 'success' : 'error'"
            :title="reviewJob.detail?.verdict === 'pass' ? '评审通过（自动门）' : '评审未通过（需人工处理）'"
            :closable="false"
            show-icon
          />
          <div v-if="reviewJob.detail?.blocking_issues?.length" class="review-block">
            <div class="review-label">阻塞性问题：</div>
            <ul class="review-list danger-list">
              <li v-for="(it, i) in reviewJob.detail.blocking_issues" :key="i">{{ it }}</li>
            </ul>
          </div>
          <div v-if="reviewJob.detail?.suggestions?.length" class="review-block">
            <div class="review-label">改进建议：</div>
            <ul class="review-list">
              <li v-for="(it, i) in reviewJob.detail.suggestions" :key="i">{{ it }}</li>
            </ul>
          </div>
        </div>

        <!-- A4 生成产物 -->
        <div class="generated-section">
          <h4 class="section-title">生成产物</h4>
          <el-empty
            v-if="!currentDetail.generated || currentDetail.generated.length === 0"
            description="暂无生成产物"
            :image-size="60"
          />
          <div v-else class="generated-list">
            <div
              v-for="gen in currentDetail.generated"
              :key="gen.id"
              class="generated-item"
            >
              <el-tag :type="gen.status === 'pass' ? 'success' : 'danger'" size="small" effect="dark">
                {{ gen.status === 'pass' ? '通过' : '失败' }}
              </el-tag>
              <span class="generated-file">{{ gen.script_file }}</span>
              <span class="generated-meta">{{ gen.rounds }} 轮自修复 · {{ formatDuration(gen.duration_ms) }}</span>
              <el-button size="small" link type="primary" @click="handleViewScript(gen)">查看脚本</el-button>
            </div>
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

    <!-- 生成脚本查看抽屉 -->
    <el-drawer
      v-model="scriptDrawerVisible"
      title="生成脚本"
      size="60%"
    >
      <div v-if="currentScript" class="script-content">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="状态">
            <el-tag :type="currentScript.status === 'pass' ? 'success' : 'danger'" size="small">
              {{ currentScript.status === 'pass' ? '通过' : '失败' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="自修复轮数">{{ currentScript.rounds }}</el-descriptions-item>
          <el-descriptions-item label="耗时">{{ formatDuration(currentScript.duration_ms) }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="currentScript.report?.summary" class="script-summary">
          <el-alert type="info" :title="currentScript.report.summary" :closable="false" show-icon />
        </div>
        <h4 class="section-title">脚本全文</h4>
        <pre class="script-block"><code>{{ currentScript.script_content || '（无脚本内容）' }}</code></pre>
        <div v-if="currentScript.report?.output_tail" class="script-summary">
          <h4 class="section-title">运行输出（尾部）</h4>
          <pre class="output-block"><code>{{ currentScript.report.output_tail }}</code></pre>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, View, MagicStick, Share, CircleCheck, CircleClose, CaretRight, Document, Delete } from '@element-plus/icons-vue'
import {
  getTasksetList,
  createTaskset,
  getTasksetDetail,
  runStage,
  runPipeline,
  cancelTaskset,
  deleteTaskset,
  bulkDeleteTasksets,
} from '@/api/tasksets'
import { getRecordingList } from '@/api/recording'
import { formatTime, formatDuration } from '@/utils/format'
import { createPoller } from '@/utils/polling'

// ---- state ----
const loading = ref(false)
const tasksetList = ref([])
const selectedRows = ref([])

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
const stageRunning = ref(null) // 'extract' | 'design' | 'review' | 'generate' | null
const pipelineRunning = ref(false)
let detailPoller = null

// 草案 JSON 抽屉
const draftJsonDrawerVisible = ref(false)
const currentDraft = ref(null)

// 生成脚本抽屉
const scriptDrawerVisible = ref(false)
const currentScript = ref(null)

// 流水线阶段定义（展示用）
const PIPELINE_STAGES = [
  { stage: 'replay', title: '回放' },
  { stage: 'extract', title: 'A1 提取' },
  { stage: 'design', title: 'A2 设计' },
  { stage: 'review', title: 'A3 评审' },
  { stage: 'generate', title: 'A4 生成' },
]

const STAGE_STATUS_TO_STEP = {
  replay: { running: 'replaying', done: 'replay_done' },
  extract: { running: 'extracting', done: 'extract_done' },
  design: { running: 'designing', done: 'design_done' },
  review: { running: 'reviewing', done: 'review_done' },
  generate: { running: 'generating', done: 'generate_done' },
}

// ---- 常量 / 工具 ----
const STATUS_MAP = {
  created:       { text: '已创建', type: 'info' },
  replaying:     { text: '回放中', type: 'primary' },
  replay_done:   { text: '回放完成', type: 'success' },
  extracting:    { text: '提取中', type: 'primary' },
  extract_done:  { text: '提取完成', type: 'success' },
  designing:     { text: '设计中', type: 'primary' },
  design_done:   { text: '设计完成', type: 'success' },
  reviewing:     { text: '评审中', type: 'primary' },
  review_done:   { text: '评审通过', type: 'success' },
  generating:    { text: '生成中', type: 'primary' },
  generate_done: { text: '生成完成', type: 'success' },
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
  if (stageRunning.value || pipelineRunning.value) return false
  return currentDetail.value.status === 'extract_done'
})

// 是否可执行 A3 评审：design_done 状态
const canRunReview = computed(() => {
  if (!currentDetail.value) return false
  if (stageRunning.value || pipelineRunning.value) return false
  return currentDetail.value.status === 'design_done'
})

// 是否可执行 A4 生成：review_done 状态
const canRunGenerate = computed(() => {
  if (!currentDetail.value) return false
  if (stageRunning.value || pipelineRunning.value) return false
  return currentDetail.value.status === 'review_done'
})

// 是否可一键流水线：created/replay_done/extract_done/design_done/review_done/failed
const canRunPipeline = computed(() => {
  if (!currentDetail.value) return false
  if (stageRunning.value || pipelineRunning.value) return false
  return ['created', 'replay_done', 'extract_done', 'design_done', 'review_done', 'failed'].includes(
    currentDetail.value.status
  )
})

// P4：是否正在进行中（可终止）
const isInProgress = computed(() => {
  const s = currentDetail.value?.status
  return ['replaying', 'extracting', 'designing', 'reviewing', 'generating'].includes(s)
})

const cancelRequested = computed(() => !!currentDetail.value?.cancel_requested)

// P4：请求终止流水线（协作式：当前阶段结束后停止）
async function handleCancelPipeline() {
  if (!currentDetail.value) return
  try {
    await ElMessageBox.confirm(
      '将在【当前阶段结束后】停止（AI 阶段无法中断），是否继续？',
      '终止流水线',
      { type: 'warning', confirmButtonText: '终止', cancelButtonText: '取消' },
    )
    await cancelTaskset(currentDetail.value.id)
    ElMessage.info('已请求终止，将在当前阶段结束后停止')
    // 立即本地置位，同步刷新列表
    currentDetail.value.cancel_requested = true
    fetchList()
  } catch (e) { /* 取消或 409 */ }
}

// 阶段全景：当前活跃步骤索引
const pipelineActiveStep = computed(() => {
  const s = currentDetail.value?.status || 'created'
  if (s === 'failed') return 0
  const runningIndex = PIPELINE_STAGES.findIndex(
    (p) => STAGE_STATUS_TO_STEP[p.stage].running === s
  )
  if (runningIndex >= 0) return runningIndex + 1
  let lastDone = -1
  PIPELINE_STAGES.forEach((p, i) => {
    if (STAGE_STATUS_TO_STEP[p.stage].done === s) lastDone = i + 1
  })
  if (s === 'generate_done') return 5
  return Math.max(lastDone, 0)
})

function stepStatus(stage) {
  const s = currentDetail.value?.status || 'created'
  const spec = STAGE_STATUS_TO_STEP[stage]
  if (s === spec.done) return 'success'
  if (s === spec.running) return 'process'
  if (s === 'failed') {
    // failed 时：最后一个非空 StageJob 的 stage 标记为 error
    const jobs = currentDetail.value?.stage_jobs || []
    const last = jobs[jobs.length - 1]
    if (last && last.stage === stage) return 'error'
    const stageDone = (st) => STAGE_STATUS_TO_STEP[st]?.done
    const order = PIPELINE_STAGES.map((p) => p.stage)
    return order.indexOf(stage) < order.indexOf(last?.stage || '') ? 'success' : 'wait'
  }
  return 'wait'
}

// A3 评审报告：取 review StageJob
const reviewJob = computed(() => {
  const jobs = currentDetail.value?.stage_jobs || []
  return jobs.find((j) => j.stage === 'review') || null
})

// ---- actions ----
function handleSelectionChange(rows) {
  selectedRows.value = rows
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确定要删除任务集「${row.name}」吗？此操作不可恢复。`,
      '删除任务集',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    await deleteTaskset(row.id)
    ElMessage.success('删除成功')
    fetchList()
  } catch (e) { /* 取消或失败 */ }
}

async function handleBulkDelete() {
  if (selectedRows.value.length === 0) return
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedRows.value.length} 个任务集吗？此操作不可恢复。`,
      '批量删除任务集',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    const ids = selectedRows.value.map((r) => r.id)
    const res = await bulkDeleteTasksets(ids)
    ElMessage.success(`已删除 ${res?.deleted ?? ids.length} 个任务集`)
    selectedRows.value = []
    fetchList()
  } catch (e) { /* 取消或失败 */ }
}

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
  pipelineRunning.value = false
}

const STAGE_LABEL = {
  extract: 'A1 提取',
  design: 'A2 设计',
  review: 'A3 评审',
  generate: 'A4 生成',
}

// 执行单个智能体阶段（A1/A2/A3/A4）
async function handleRunStage(stage) {
  if (!currentDetail.value) return
  stageRunning.value = stage
  try {
    // 提交阶段任务，后端返回 202
    await runStage(currentDetail.value.id, stage)
    const label = STAGE_LABEL[stage] || stage
    ElMessage.info(`${label}任务已提交，智能体执行中…`)

    const spec = STAGE_STATUS_TO_STEP[stage]
    const targetRunningStatus = spec.running
    const targetDoneStatus = spec.done

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
          ElMessage.success(`${label}执行成功`)
        } else if (data.status === 'failed') {
          ElMessage.error(`${label}执行失败`)
        } else {
          ElMessage.info(`状态已更新：${statusText(data.status)}`)
        }
        fetchList()
      },
      onError: () => {
        stageRunning.value = null
      },
    })
    detailPoller.start()
  } catch (err) {
    stageRunning.value = null
  }
}

// 一键流水线（replay -> extract -> design -> review -> generate）
async function handleRunPipeline() {
  if (!currentDetail.value) return
  pipelineRunning.value = true
  try {
    await runPipeline(currentDetail.value.id)
    ElMessage.info('流水线已启动，按阶段顺序执行中…')

    detailPoller = createPoller({
      fetchFn: () => getTasksetDetail(currentDetail.value.id),
      interval: 3000,
      // 终态才停：generate_done（成功）或 failed（中断）
      isDone: (data) => data.status === 'generate_done' || data.status === 'failed',
      onTick: (data) => {
        currentDetail.value = data
      },
      onDone: (data) => {
        currentDetail.value = data
        pipelineRunning.value = false
        if (data.status === 'generate_done') {
          ElMessage.success('流水线全部完成：脚本已生成并跑通')
        } else if (data.status === 'failed') {
          ElMessage.error(`流水线中断：${data.error || '某阶段失败'}`)
        } else {
          ElMessage.info(`流水线状态：${statusText(data.status)}`)
        }
        fetchList()
      },
      onError: () => {
        pipelineRunning.value = false
      },
    })
    detailPoller.start()
  } catch (err) {
    pipelineRunning.value = false
  }
}

function handleViewScript(gen) {
  currentScript.value = gen
  scriptDrawerVisible.value = true
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

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
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

.status-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.detail-status {
  display: flex;
  align-items: center;
  gap: 6px;
}

.in-progress-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.pulse-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #fff;
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.2; }
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

/* P3：流水线全景 / 评审报告 / 生成产物 */
.pipeline-steps-section {
  margin-top: 24px;
}

.review-section {
  margin-top: 24px;
}

.review-block {
  margin-top: 12px;
}

.review-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--do-fg);
  margin-bottom: 4px;
}

.review-list {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  color: var(--do-fg-secondary);
  line-height: 1.7;
}

.danger-list {
  color: var(--do-danger);
}

.generated-section {
  margin-top: 24px;
}

.generated-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.generated-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: var(--do-bg);
  border-radius: 6px;
  border: 1px solid var(--do-border, #e4e7ed);
}

.generated-file {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  color: var(--do-fg);
}

.generated-meta {
  flex: 1;
  font-size: 12px;
  color: var(--do-fg-tertiary);
}

.script-content {
  padding-right: 8px;
}

.script-summary {
  margin-top: 16px;
}

.script-block {
  background: #0d1117;
  color: #e6edf3;
  border-radius: 6px;
  padding: 14px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12.5px;
  line-height: 1.6;
  overflow: auto;
  max-height: 480px;
  white-space: pre;
}

.output-block {
  background: var(--do-bg);
  border: 1px solid var(--do-border, #e4e7ed);
  border-radius: 6px;
  padding: 12px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  line-height: 1.6;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
