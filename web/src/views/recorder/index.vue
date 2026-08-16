<template>
  <div class="recorder-page">
    <!-- 顶部：操作按钮 + 搜索刷新 -->
    <div class="top-bar">
      <div class="top-bar-left">
        <el-button type="primary" :icon="VideoCamera" @click="activeSections = ['browser', 'list']">
          🎥 浏览器录制
        </el-button>
        <el-button :icon="Document" @click="openManualDialog">
          📄 手动录制
        </el-button>
      </div>
      <div class="top-bar-right">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索名称 / 起始 URL"
          clearable
          style="width: 260px"
          :prefix-icon="Search"
        />
        <el-button :icon="Refresh" @click="fetchList">刷新</el-button>
      </div>
    </div>

    <!-- 三个可折叠区块 -->
    <el-collapse v-model="activeSections" class="page-collapse">
      <!-- 区块一：浏览器录制 -->
      <el-collapse-item name="browser">
        <template #title>
          <span class="collapse-title">
            <el-icon><VideoCamera /></el-icon>
            浏览器录制
            <el-tag v-if="codegenActive" type="danger" effect="dark" size="small" class="title-tag">
              <span class="rec-dot"></span> 录制中
            </el-tag>
          </span>
        </template>

        <el-card shadow="never" class="codegen-card">
          <div class="codegen-body">
            <el-form :inline="true" :model="codegenForm" @submit.prevent>
              <el-form-item label="录制名称">
                <el-input
                  v-model="codegenForm.name"
                  placeholder="请输入录制名称"
                  style="width: 220px"
                  maxlength="120"
                />
              </el-form-item>
              <el-form-item label="起始 URL">
                <el-input
                  v-model="codegenForm.start_url"
                  placeholder="http://127.0.0.1:8001/api/demo/login/"
                  style="width: 320px"
                />
              </el-form-item>
              <el-form-item label="自动 AI 分析">
                <el-switch v-model="codegenForm.auto_analyze" />
                <el-text v-if="codegenForm.auto_analyze" type="success" size="small" class="auto-tip">
                  结束后自动重组为标准脚本
                </el-text>
              </el-form-item>
              <el-form-item>
                <el-button
                  v-if="!codegenActive"
                  type="primary"
                  :icon="VideoPlay"
                  :loading="codegenStarting"
                  :disabled="!codegenForm.name.trim()"
                  @click="handleStartCodegen"
                >
                  开始录制
                </el-button>
                <el-button
                  v-else
                  type="success"
                  :icon="VideoPause"
                  :loading="codegenStopping"
                  @click="handleStopCodegen"
                >
                  结束并保存
                </el-button>
              </el-form-item>
            </el-form>
            <el-alert
              v-if="codegenActive"
              type="warning"
              :closable="false"
              show-icon
              :title="`浏览器已打开（${codegenStartedAt}），请在浏览器中操作页面完成录制，然后点击【结束并保存】`"
            />
          </div>
        </el-card>
      </el-collapse-item>

      <!-- 区块二：已解析脚本 -->
      <el-collapse-item name="list">
        <template #title>
          <span class="collapse-title">
            <el-icon><List /></el-icon>
            已解析脚本
            <el-tag size="small" effect="plain" class="title-tag">
              {{ filteredList.length }} / {{ recordingList.length }}
            </el-tag>
          </span>
        </template>

        <el-card shadow="never" class="list-card">
          <!-- 列表工具栏：批量删除 -->
          <div class="list-toolbar">
            <div class="toolbar-left">
              <el-button
                type="danger"
                :icon="Delete"
                :disabled="selectedIds.length === 0"
                @click="handleBatchDelete"
              >
                删除选中 ({{ selectedIds.length }})
              </el-button>
            </div>
          </div>

          <el-table
            v-loading="loading"
            :data="filteredList"
            stripe
            style="width: 100%"
            @selection-change="handleSelectionChange"
            ref="tableRef"
          >
            <template #empty>
              <el-empty description="暂无录制脚本">
                <el-button type="primary" :icon="Promotion" @click="activeSections = ['browser', 'list']">
                  开始录制
                </el-button>
              </el-empty>
            </template>

            <el-table-column type="selection" width="50" align="center" />
            <el-table-column prop="name" label="名称" min-width="180" show-overflow-tooltip />
            <el-table-column prop="start_url" label="起始 URL" min-width="220" show-overflow-tooltip />
            <el-table-column prop="locators_count" label="定位器数" width="100" align="center" />
            <el-table-column prop="actions_count" label="动作数" width="90" align="center" />
            <el-table-column label="警告数" width="90" align="center">
              <template #default="{ row }">
                <el-tag
                  v-if="row.warnings && row.warnings.length > 0"
                  size="small"
                  type="warning"
                  effect="light"
                >
                  {{ row.warnings.length }}
                </el-tag>
                <span v-else class="empty-tip">0</span>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="180">
              <template #default="{ row }">
                <span v-if="row.created_at">{{ formatTime(row.created_at) }}</span>
                <span v-else class="empty-tip">—</span>
              </template>
            </el-table-column>

            <el-table-column label="操作" width="300" fixed="right" align="center">
              <template #default="{ row }">
                <el-button
                  type="success"
                  link
                  size="small"
                  :icon="VideoPlay"
                  @click="handleReplay(row)"
                >
                  回放
                </el-button>
                <el-button
                  type="primary"
                  link
                  size="small"
                  :icon="MagicStick"
                  :loading="normalizeRunningId === row.id"
                  :disabled="row.normalize_status === 'running' || normalizeRunningId === row.id"
                  @click="handleNormalize(row)"
                >
                  AI 重组
                </el-button>
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
      </el-collapse-item>
    </el-collapse>

    <!-- 手动录制弹窗 -->
    <el-dialog
      v-model="manualDialogVisible"
      title="手动录制"
      width="720px"
      :close-on-click-modal="false"
      destroy-on-close
      class="manual-dialog"
    >
      <div class="manual-dialog-body">
        <div class="form-section">
          <div class="section-label">
            <span class="label-text">脚本名称</span>
            <span class="label-required">*</span>
          </div>
          <el-input
            v-model="manualForm.name"
            placeholder="请输入脚本名称，如：登录流程_v1"
            maxlength="120"
            show-word-limit
            size="large"
          />
        </div>

        <div class="form-section">
          <div class="section-label-row">
            <div class="section-label">
              <span class="label-text">脚本内容</span>
              <span class="label-required">*</span>
            </div>
            <el-upload
              :show-file-list="false"
              :before-upload="handleManualBeforeUpload"
              accept=".py,.txt"
            >
              <el-button type="primary" link :icon="Upload" size="small">
                上传 .py / .txt 文件
              </el-button>
            </el-upload>
          </div>
          <el-input
            v-model="manualForm.content"
            type="textarea"
            :rows="14"
            placeholder="在此粘贴 Playwright / Selenium 等录制生成的 Python 脚本，提交后将自动解析动作与定位器..."
            class="content-textarea"
          />
          <div class="textarea-hint">
            <el-icon><InfoFilled /></el-icon>
            <span>支持 Python 脚本，上传文件会自动填入上方文本框</span>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button size="large" @click="manualDialogVisible = false">取消</el-button>
        <el-button type="primary" size="large" :icon="Promotion" :loading="manualSubmitting" @click="handleManualSubmit">
          {{ manualSubmitting ? '解析提交中...' : '提交解析' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 详情抽屉 -->
    <el-drawer
      v-model="detailDrawerVisible"
      title="脚本详情"
      size="60%"
      :with-header="true"
    >
      <div v-if="currentDetail" class="detail-content">
        <el-collapse v-model="detailSections" class="detail-collapse">
          <!-- 基本信息 -->
          <el-collapse-item name="basic" title="基本信息">
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="名称">{{ currentDetail.name }}</el-descriptions-item>
              <el-descriptions-item label="语言">{{ currentDetail.language || '—' }}</el-descriptions-item>
              <el-descriptions-item label="起始 URL">{{ currentDetail.start_url || '—' }}</el-descriptions-item>
              <el-descriptions-item label="框架">{{ currentDetail.framework || '—' }}</el-descriptions-item>
              <el-descriptions-item label="定位器数">{{ currentDetail.locators_count ?? '—' }}</el-descriptions-item>
              <el-descriptions-item label="动作数">{{ currentDetail.actions_count ?? '—' }}</el-descriptions-item>
              <el-descriptions-item label="创建时间">{{ formatTime(currentDetail.created_at) || '—' }}</el-descriptions-item>
            </el-descriptions>
          </el-collapse-item>

          <!-- 警告列表：无警告时整个区块隐藏 -->
          <el-collapse-item
            v-if="currentDetail.warnings && currentDetail.warnings.length > 0"
            name="warnings"
            :title="`警告列表（${currentDetail.warnings.length}）`"
          >
            <el-alert
              v-for="(warn, idx) in currentDetail.warnings"
              :key="idx"
              :title="warn"
              type="warning"
              :closable="false"
              show-icon
              class="warn-item"
            />
          </el-collapse-item>

          <!-- 动作列表 -->
          <el-collapse-item name="actions" title="动作列表">
            <el-table
              :data="currentDetail.actions || []"
              stripe
              size="small"
              max-height="320"
              empty-text="该脚本未解析出动作（可能为手动导入的非常规脚本）"
            >
              <el-table-column type="index" label="#" width="55" align="center" />
              <el-table-column prop="type" label="动作类型" min-width="100" />
              <el-table-column label="目标元素" min-width="220" show-overflow-tooltip>
                <template #default="{ row }">
                  <span v-if="row.name">{{ row.name }}</span>
                  <code v-if="row.locator_value" class="action-locator">{{ row.locator_value }}</code>
                  <span v-else-if="!row.name" class="empty-tip">—</span>
                </template>
              </el-table-column>
              <el-table-column label="值" min-width="140" show-overflow-tooltip>
                <template #default="{ row }">
                  <code v-if="row.value != null" class="action-value">{{ row.value }}</code>
                  <span v-else class="empty-tip">—</span>
                </template>
              </el-table-column>
              <el-table-column label="原始行" min-width="220" show-overflow-tooltip>
                <template #default="{ row }">
                  <code class="action-raw">{{ row.raw || '—' }}</code>
                </template>
              </el-table-column>
            </el-table>
          </el-collapse-item>

          <!-- 脚本内容 -->
          <el-collapse-item name="script" title="脚本内容">
            <el-tabs v-model="scriptTab">
              <el-tab-pane label="原始脚本" name="raw">
                <pre class="code-block">{{ currentDetail.raw_content || '—' }}</pre>
              </el-tab-pane>
              <el-tab-pane label="标准化脚本（AI 重组）" name="normalized">
                <div v-if="currentDetail.normalized_content" class="norm-header">
                  <el-tag type="success" size="small" effect="light">已重组</el-tag>
                  <span class="norm-tip">通过默认脚手架重组的标准稳定脚本</span>
                </div>
                <pre v-if="currentDetail.normalized_content" class="code-block">{{ currentDetail.normalized_content }}</pre>
                <el-empty v-else description="尚未 AI 重组：点击列表中的【AI 重组】生成" :image-size="70" />
              </el-tab-pane>
            </el-tabs>
          </el-collapse-item>
        </el-collapse>
      </div>
    </el-drawer>

    <!-- 回放查看弹窗（P4：录制中心内嵌，不跳转） -->
    <el-dialog
      v-model="replayDialogVisible"
      :title="replayDialogTitle"
      width="780px"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <div v-loading="replayListLoading" class="replay-dialog-body">
        <div class="replay-toolbar">
          <el-text type="info" size="small">
            自动加载本脚本最近的回放视频（保存录制时会自动回放生成）
          </el-text>
        </div>

        <el-empty
          v-if="!replayListLoading && replayRuns.length === 0"
          description="暂无回放记录：重新录制并保存后会自动生成回放视频"
          :image-size="70"
        />

        <!-- 回放记录列表 -->
        <el-table v-else :data="replayRuns" stripe size="small" highlight-current-row @current-change="handleReplayRowChange">
          <el-table-column prop="id" label="ID" width="70" align="center" />
          <el-table-column label="状态" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)" size="small" effect="light">
                {{ statusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="步骤" width="100" align="center">
            <template #default="{ row }">
              {{ row.steps_passed ?? 0 }}/{{ row.steps_total ?? '—' }}
            </template>
          </el-table-column>
          <el-table-column label="视频" width="80" align="center">
            <template #default="{ row }">
              <el-icon :color="row.video_available ? '#67c23a' : '#c0c4cc'" :size="16">
                <VideoCamera />
              </el-icon>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="时间" min-width="160">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="90" align="center">
            <template #default="{ row }">
              <el-button
                type="success"
                link
                size="small"
                :icon="VideoPlay"
                :disabled="!row.video_available"
                @click="handlePlayThis(row)"
              >
                播放
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 视频播放（全屏用播放器原生控件按钮，P4：去除重复全屏入口） -->
        <div v-if="currentReplayVideoUrl" class="replay-video-box">
          <video
            :src="currentReplayVideoUrl"
            controls
            autoplay
            style="width: 100%; border-radius: 6px; background: #000"
          />
        </div>
        <el-alert
          v-else-if="replayRuns.length > 0"
          type="info"
          :closable="false"
          show-icon
          title="选中一条有视频的回放记录即可播放；无录像记录说明回放时未生成视频"
          class="replay-video-tip"
        />
      </div>
    </el-dialog>

    <!-- 删除确认对话框 -->
    <el-dialog
      v-model="deleteDialogVisible"
      title="删除确认"
      width="420px"
      :close-on-click-modal="false"
    >
      <div class="delete-dialog-body">
        <el-alert
          :title="`确定要删除脚本「${deletingRow?.name || ''}」吗？`"
          type="warning"
          show-icon
          :closable="false"
        />
      </div>
      <template #footer>
        <el-button @click="deleteDialogVisible = false">取消</el-button>
        <el-button type="danger" :loading="deleting" @click="confirmDelete">
          {{ deleting ? '删除中...' : '确认删除' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Upload,
  Promotion,
  Refresh,
  View,
  Delete,
  VideoCamera,
  VideoPlay,
  VideoPause,
  MagicStick,
  Document,
  Search,
  List,
  InfoFilled,
} from '@element-plus/icons-vue'
import {
  getRecordingList,
  createRecording,
  getRecordingDetail,
  deleteRecording,
  deleteRecordings,
  startCodegen,
  getCodegenStatus,
  stopCodegen,
  normalizeRecording,
} from '@/api/recording'
import { getReplayList } from '@/api/replay'
import { formatTime } from '@/utils/format'

// ---- state ----
const loading = ref(false)
const recordingList = ref([])
const tableRef = ref(null)

// 折叠区块
const activeSections = ref(['browser', 'list'])

// 搜索
const searchKeyword = ref('')

// 批量选择
const selectedIds = ref([])
const selectedRows = ref([])

// ---- P4：codegen 录制 ----
const codegenForm = reactive({
  name: '',
  start_url: 'http://127.0.0.1:8001/api/demo/login/',
  auto_analyze: false,  // P4 #3：默认关闭自动 AI 分析
})
const codegenActive = ref(false)
const codegenStarting = ref(false)
const codegenStopping = ref(false)
const codegenStartedAt = ref('')
let codegenPollTimer = null

// ---- P4：AI 重组 ----
const normalizeRunningId = ref(null)
let normalizePollTimer = null

// ---- 手动录制弹窗 ----
const manualDialogVisible = ref(false)
const manualSubmitting = ref(false)
const manualForm = reactive({
  name: '',
  content: '',
})

const detailDrawerVisible = ref(false)
const currentDetail = ref(null)
const detailLoading = ref(false)
const scriptTab = ref('raw')
const detailSections = ref(['basic', 'actions', 'script'])

// ---- P4：回放内嵌查看 ----
const replayDialogVisible = ref(false)
const replayDialogTitle = ref('回放')
const replayDialogRecordingId = ref(null)
const replayListLoading = ref(false)
const replayRuns = ref([])
const currentReplayVideoUrl = ref('')
let replayPollTimer = null

const deleteDialogVisible = ref(false)
const deletingRow = ref(null)
const deleting = ref(false)

// ---- 计算 ----
const filteredList = computed(() => {
  const kw = searchKeyword.value.trim().toLowerCase()
  if (!kw) return recordingList.value
  return recordingList.value.filter((item) => {
    const name = (item.name || '').toLowerCase()
    const url = (item.start_url || '').toLowerCase()
    return name.includes(kw) || url.includes(kw)
  })
})

// ---- 工具 ----
const NORMALIZE_MAP = {
  idle: { text: '未重组', type: 'info' },
  running: { text: '重组中…', type: 'primary' },
  done: { text: '已重组', type: 'success' },
  failed: { text: '失败', type: 'danger' },
}

function normalizeTagType(s) { return NORMALIZE_MAP[s]?.type || 'info' }
function normalizeText(s) { return NORMALIZE_MAP[s]?.text || s || '未重组' }

// 回放状态
const REPLAY_STATUS_MAP = {
  success: { text: '成功', type: 'success' },
  failed: { text: '失败', type: 'danger' },
  running: { text: '执行中', type: 'primary' },
}
function statusTagType(s) { return REPLAY_STATUS_MAP[s]?.type || 'info' }
function statusText(s) { return REPLAY_STATUS_MAP[s]?.text || s || '未知' }

// ---- actions ----
async function fetchList() {
  loading.value = true
  try {
    const data = await getRecordingList()
    recordingList.value = Array.isArray(data) ? data : (data?.results || [])
  } catch (err) {
    recordingList.value = []
  } finally {
    loading.value = false
  }
}

// ---- 选择变化 ----
function handleSelectionChange(rows) {
  selectedRows.value = rows
  selectedIds.value = rows.map((r) => r.id)
}

// ---- codegen ----
async function pollCodegenStatus() {
  try {
    const s = await getCodegenStatus()
    codegenActive.value = !!s.active
    if (s.active) {
      codegenStartedAt.value = formatTime(s.started_at)
    }
  } catch (e) { /* 拦截器已提示 */ }
}

async function handleStartCodegen() {
  if (!codegenForm.name.trim()) {
    ElMessage.warning('请先填写录制名称')
    return
  }
  codegenStarting.value = true
  try {
    await startCodegen({
      name: codegenForm.name.trim(),
      start_url: codegenForm.start_url || '',
    })
    codegenActive.value = true
    ElMessage.success('浏览器已打开，请操作页面完成录制')
    codegenPollTimer = setInterval(pollCodegenStatus, 3000)
  } catch (err) {
    // 拦截器已提示
  } finally {
    codegenStarting.value = false
  }
}

async function handleStopCodegen() {
  codegenStopping.value = true
  try {
    const result = await stopCodegen({
      session_id: '', // 后端取当前活跃会话（单会话语义）
      auto_analyze: codegenForm.auto_analyze,
    })
    codegenActive.value = false
    if (codegenPollTimer) {
      clearInterval(codegenPollTimer)
      codegenPollTimer = null
    }
    if (result.ok) {
      ElMessage.success(
        `录制已保存：${result.name}（${result.actions_count} 个动作），` +
        (result.auto_replay ? '自动回放生成视频中…' : '') +
        (result.auto_analyze ? '，AI 重组已启动' : '')
      )
      await fetchList()
      if (result.auto_analyze && result.recording_id) {
        pollNormalizeUntilDone(result.recording_id)
      }
    } else {
      ElMessage.warning(result.detail || '录制产物为空')
    }
  } catch (err) {
    // 拦截器已提示
  } finally {
    codegenStopping.value = false
  }
}

// ---- AI 重组 ----
function pollNormalizeUntilDone(recordingId) {
  normalizeRunningId.value = recordingId
  let rounds = 0
  normalizePollTimer = setInterval(async () => {
    rounds += 1
    try {
      const detail = await getRecordingDetail(recordingId)
      const st = detail.normalize_status
      if (st === 'done' || st === 'failed' || rounds > 60) {
        clearInterval(normalizePollTimer)
        normalizePollTimer = null
        normalizeRunningId.value = null
        ElMessage[st === 'done' ? 'success' : 'warning'](
          st === 'done' ? 'AI 重组完成：标准化脚本已生成' : 'AI 重组失败，详见详情警告'
        )
        fetchList()
      }
    } catch (e) {
      clearInterval(normalizePollTimer)
      normalizePollTimer = null
      normalizeRunningId.value = null
    }
  }, 3000)
}

async function handleNormalize(row) {
  try {
    await normalizeRecording(row.id)
    ElMessage.info('AI 重组已启动，标准化脚本生成中…')
    pollNormalizeUntilDone(row.id)
  } catch (err) {
    // 拦截器已提示
  }
}

// ---- 回放（录制中心内嵌查看，不跳转） ----
async function handleReplay(row) {
  replayDialogRecordingId.value = row.id
  replayDialogTitle.value = `回放 - ${row.name}`
  replayDialogVisible.value = true
  currentReplayVideoUrl.value = ''
  replayRuns.value = []
  await loadReplayRuns(row.id)
}

async function loadReplayRuns(recordingId) {
  replayListLoading.value = true
  try {
    const data = await getReplayList({ recording_id: recordingId })
    replayRuns.value = Array.isArray(data) ? data : (data?.results || [])
    // 自动选中第一条有视频的记录
    const withVideo = replayRuns.value.find((r) => r.video_available)
    if (withVideo) {
      currentReplayVideoUrl.value = withVideo.video_url || ''
    }
    // 有回放仍在执行（保存后自动回放）则轮询直到终态
    const anyRunning = replayRuns.value.some((r) => r.status === 'running')
    if (anyRunning) {
      startReplayPolling(recordingId)
    }
  } catch (e) {
    replayRuns.value = []
  } finally {
    replayListLoading.value = false
  }
}

// 自动回放轮询：running -> 终态后刷新列表并自动加载视频
function startReplayPolling(recordingId) {
  if (replayPollTimer) clearInterval(replayPollTimer)
  let rounds = 0
  replayPollTimer = setInterval(async () => {
    rounds += 1
    try {
      const data = await getReplayList({ recording_id: recordingId })
      const runs = Array.isArray(data) ? data : (data?.results || [])
      replayRuns.value = runs
      const anyRunning = runs.some((r) => r.status === 'running')
      if (!anyRunning || rounds > 60) {
        clearInterval(replayPollTimer)
        replayPollTimer = null
        ElMessage.success('回放完成，视频已就绪')
        const withVideo = runs.find((r) => r.video_available)
        if (withVideo) currentReplayVideoUrl.value = withVideo.video_url || ''
      }
    } catch (e) {
      clearInterval(replayPollTimer)
      replayPollTimer = null
    }
  }, 3000)
}

function handleReplayRowChange(row) {
  if (!row) return
  currentReplayVideoUrl.value = row.video_available ? (row.video_url || '') : ''
}

// 行内【播放】：明确选择该条回放并播放其视频
function handlePlayThis(row) {
  currentReplayVideoUrl.value = row.video_available ? (row.video_url || '') : ''
  if (!currentReplayVideoUrl.value) {
    ElMessage.warning('该回放记录无视频')
  }
}

async function handleTriggerReplay() {
  // 已移除【执行回放】按钮（保存录制时自动回放）；保留空实现防引用残留
}

// ---- 手动录制弹窗 ----
function openManualDialog() {
  manualForm.name = ''
  manualForm.content = ''
  manualDialogVisible.value = true
}

function handleManualBeforeUpload(file) {
  const reader = new FileReader()
  reader.onload = (e) => {
    manualForm.content = e.target?.result || ''
    if (!manualForm.name) {
      const name = file.name.replace(/\.[^.]+$/, '')
      manualForm.name = name
    }
    ElMessage.success(`已读取文件：${file.name}`)
  }
  reader.onerror = () => {
    ElMessage.error('文件读取失败')
  }
  reader.readAsText(file)
  return false // 阻止自动上传
}

async function handleManualSubmit() {
  if (!manualForm.name.trim()) {
    ElMessage.warning('请输入脚本名称')
    return
  }
  if (!manualForm.content.trim()) {
    ElMessage.warning('请输入或上传脚本内容')
    return
  }
  manualSubmitting.value = true
  try {
    await createRecording({ name: manualForm.name.trim(), content: manualForm.content })
    ElMessage.success('脚本解析成功')
    manualDialogVisible.value = false
    await fetchList()
  } catch (err) {
    // 拦截器已提示
  } finally {
    manualSubmitting.value = false
  }
}

async function handleViewDetail(row) {
  detailDrawerVisible.value = true
  currentDetail.value = null
  detailLoading.value = true
  try {
    const detail = await getRecordingDetail(row.id)
    currentDetail.value = detail
  } catch (err) {
    // 拦截器已提示
  } finally {
    detailLoading.value = false
  }
}

function handleDelete(row) {
  deletingRow.value = row
  deleteDialogVisible.value = true
}

async function confirmDelete() {
  if (!deletingRow.value) return
  deleting.value = true
  try {
    await deleteRecording(deletingRow.value.id)
    ElMessage.success('删除成功')
    deleteDialogVisible.value = false
    fetchList()
  } catch (err) {
    // 拦截器已提示
  } finally {
    deleting.value = false
  }
}

// ---- 批量删除 ----
async function handleBatchDelete() {
  if (selectedIds.value.length === 0) return
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedIds.value.length} 条脚本吗？`,
      '批量删除确认',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
  } catch {
    return
  }

  deleting.value = true
  try {
    const successCount = await deleteRecordings(selectedIds.value)
    const total = selectedIds.value.length
    if (successCount === total) {
      ElMessage.success(`成功删除 ${successCount} 条脚本`)
    } else {
      ElMessage.warning(`删除完成：成功 ${successCount} 条，失败 ${total - successCount} 条`)
    }
    // 清空选择
    if (tableRef.value && tableRef.value.clearSelection) {
      tableRef.value.clearSelection()
    }
    selectedIds.value = []
    selectedRows.value = []
    fetchList()
  } catch (err) {
    ElMessage.error('批量删除失败')
  } finally {
    deleting.value = false
  }
}

// ---- 生命周期 ----
onMounted(() => {
  fetchList()
  pollCodegenStatus()
})

onBeforeUnmount(() => {
  if (codegenPollTimer) clearInterval(codegenPollTimer)
  if (normalizePollTimer) clearInterval(normalizePollTimer)
  if (replayPollTimer) clearInterval(replayPollTimer)
})
</script>

<style scoped>
.recorder-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
  overflow-y: auto;
  padding-right: 4px;
}

/* 顶部栏 */
.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 2px;
}

.top-bar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.top-bar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 折叠区块 */
.page-collapse {
  border: none;
  background: transparent;
}

.page-collapse :deep(.el-collapse-item__header) {
  padding: 0 8px;
  border-radius: 8px;
  background: var(--do-bg-soft, #fafafa);
  margin-bottom: 8px;
  font-weight: 600;
  font-size: 14px;
  height: 46px;
  line-height: 46px;
  color: var(--do-fg);
}

.page-collapse :deep(.el-collapse-item__wrap) {
  border-bottom: none;
  margin-bottom: 8px;
}

.page-collapse :deep(.el-collapse-item__content) {
  padding-bottom: 8px;
}

.collapse-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.title-tag {
  margin-left: 8px;
}

.rec-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #fff;
  margin-right: 3px;
  animation: recPulse 1s ease-in-out infinite;
}

@keyframes recPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.2; }
}

.codegen-card {
  border-radius: 8px;
}

.codegen-body {
  padding: 4px 0;
}

.auto-tip {
  margin-left: 8px;
}

/* 列表卡片 */
.list-card {
  border-radius: 8px;
}

.list-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.toolbar-left {
  display: flex;
  gap: 8px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.textarea-wrapper {
  width: 100%;
}

.upload-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
}

.upload-tip {
  font-size: 12px;
  color: var(--do-fg-tertiary);
}

/* 手动录制弹窗 */
.manual-dialog :deep(.el-dialog__body) {
  padding: 20px 24px 16px;
}

.manual-dialog :deep(.el-dialog__footer) {
  padding: 14px 24px 20px;
}

.manual-dialog-body {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.section-label {
  display: flex;
  align-items: center;
  gap: 4px;
}

.label-text {
  font-size: 14px;
  font-weight: 500;
  color: var(--do-fg, #303133);
}

.label-required {
  color: var(--el-color-danger, #f56c6c);
  font-size: 14px;
  line-height: 1;
}

.content-textarea :deep(.el-textarea__inner) {
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  padding: 12px 14px;
  border-radius: 6px;
  background: var(--do-bg-soft, #fafafa);
}

.textarea-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
  font-size: 12.5px;
  color: var(--do-fg-tertiary, #909399);
}

.textarea-hint .el-icon {
  font-size: 14px;
  color: var(--do-primary-soft, #79bbff);
}

.empty-tip {
  color: var(--do-fg-tertiary);
}

.detail-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding-right: 8px;
}

.section-title {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--do-fg);
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-tag {
  margin-left: 4px;
}

.warn-item {
  margin-bottom: 8px;
}

.code-block {
  margin: 0;
  padding: 12px;
  background: var(--do-bg, #f5f7fa);
  border: 1px solid var(--do-border-light, #e4e7ed);
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 400px;
  overflow: auto;
  color: var(--do-fg);
}

.norm-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.norm-tip {
  font-size: 12.5px;
  color: var(--do-fg-tertiary);
}

/* P4：详情折叠 + 动作列表 + 回放弹窗 */
.detail-collapse {
  border: none;
}

.detail-collapse :deep(.el-collapse-item__header) {
  font-weight: 600;
  color: var(--do-fg);
}

.action-locator,
.action-value,
.action-raw {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  color: var(--do-primary);
  word-break: break-all;
}

.action-value { color: var(--do-success); }
.action-raw { color: var(--do-fg-tertiary); }

.replay-dialog-body {
  min-height: 120px;
}

.replay-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.replay-video-box {
  margin-top: 14px;
}

.replay-video-tip {
  margin-top: 14px;
}

.delete-dialog-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.warning-tip {
  margin: 0;
  font-size: 12px;
  color: var(--do-warning);
}
</style>
