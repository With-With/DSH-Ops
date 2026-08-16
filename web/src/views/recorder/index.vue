<template>
  <div class="recorder-page">
    <!-- P4：浏览器录制（playwright codegen） -->
    <el-card shadow="never" class="codegen-card">
      <template #header>
        <div class="card-header">
          <span class="card-title"><el-icon><VideoCamera /></el-icon> 浏览器录制</span>
          <el-tag v-if="codegenActive" type="danger" effect="dark" size="small">
            <span class="rec-dot"></span> 录制中
          </el-tag>
        </div>
      </template>

      <div class="codegen-body">
        <el-form :inline="true" :model="codegenForm" @submit.prevent>
          <el-form-item label="录制名称">
            <el-input v-model="codegenForm.name" placeholder="留空自动命名" style="width: 200px" maxlength="120" />
          </el-form-item>
          <el-form-item label="起始 URL">
            <el-input
              v-model="codegenForm.start_url"
              placeholder="http://127.0.0.1:8000/api/demo/login/"
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
        <el-alert
          v-else
          type="info"
          :closable="false"
          show-icon
          title="点击【开始录制】将打开 Playwright 录制器浏览器：页面操作会被自动录制为脚本，结束后保存到录制列表"
        />
      </div>
    </el-card>

    <!-- 手动导入（可选） -->
    <el-collapse class="import-collapse">
      <el-collapse-item title="手动导入脚本（可选：粘贴 / 上传已有脚本）" name="import">
        <el-card shadow="never" class="form-card" style="border: none">
          <el-form :model="form" label-width="80px" @submit.prevent>
            <el-form-item label="脚本名称">
              <el-input
                v-model="form.name"
                placeholder="请输入脚本名称，如：登录流程_v1"
                maxlength="120"
                show-word-limit
              />
            </el-form-item>

            <el-form-item label="脚本内容">
              <div class="textarea-wrapper">
                <el-input
                  v-model="form.content"
                  type="textarea"
                  :rows="8"
                  placeholder="粘贴录制生成的 Python 脚本，或上传 .py 文件..."
                />
                <div class="upload-row">
                  <el-upload
                    :show-file-list="false"
                    :before-upload="handleBeforeUpload"
                    accept=".py,.txt"
                  >
                    <el-button :icon="Upload">上传 .py 文件</el-button>
                  </el-upload>
                  <span class="upload-tip">支持 .py / .txt 文件，内容将填入上方文本框</span>
                </div>
              </div>
            </el-form-item>

            <el-form-item>
              <el-button
                type="primary"
                :icon="Promotion"
                :loading="submitting"
                @click="handleSubmit"
              >
                {{ submitting ? '解析提交中...' : '提交解析' }}
              </el-button>
              <el-button :icon="RefreshLeft" @click="handleReset">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-collapse-item>
    </el-collapse>

    <!-- 下方：脚本列表 -->
    <el-card shadow="never" class="list-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">已解析脚本</span>
          <el-button :icon="Refresh" @click="fetchList">刷新</el-button>
        </div>
      </template>

      <el-table
        v-loading="loading"
        :data="recordingList"
        stripe
        style="width: 100%"
      >
        <template #empty>
          <el-empty description="暂无录制脚本，在上方提交第一个脚本开始">
            <el-button type="primary" :icon="Promotion" @click="scrollToForm">提交脚本</el-button>
          </el-empty>
        </template>

        <el-table-column prop="name" label="名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="language" label="语言" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.language" size="small" effect="plain">{{ row.language }}</el-tag>
            <span v-else class="empty-tip">—</span>
          </template>
        </el-table-column>
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
        <el-table-column label="AI 重组" width="110" align="center">
          <template #default="{ row }">
            <el-tag
              :type="normalizeTagType(row.normalize_status)"
              size="small"
              effect="light"
            >
              {{ normalizeText(row.normalize_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            <span v-if="row.created_at">{{ formatTime(row.created_at) }}</span>
            <span v-else class="empty-tip">—</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="230" fixed="right" align="center">
          <template #default="{ row }">
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

    <!-- 详情抽屉 -->
    <el-drawer
      v-model="detailDrawerVisible"
      title="脚本详情"
      size="60%"
      :with-header="true"
    >
      <div v-if="currentDetail" class="detail-content">
        <div class="detail-section">
          <h4 class="section-title">基本信息</h4>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="名称">{{ currentDetail.name }}</el-descriptions-item>
            <el-descriptions-item label="语言">{{ currentDetail.language || '—' }}</el-descriptions-item>
            <el-descriptions-item label="起始 URL">{{ currentDetail.start_url || '—' }}</el-descriptions-item>
            <el-descriptions-item label="框架">{{ currentDetail.framework || '—' }}</el-descriptions-item>
            <el-descriptions-item label="定位器数">{{ currentDetail.locators_count ?? '—' }}</el-descriptions-item>
            <el-descriptions-item label="动作数">{{ currentDetail.actions_count ?? '—' }}</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatTime(currentDetail.created_at) || '—' }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="detail-section">
          <h4 class="section-title">
            警告列表
            <el-tag v-if="currentDetail.warnings && currentDetail.warnings.length > 0" size="small" type="warning" effect="light" class="section-tag">
              {{ currentDetail.warnings.length }}
            </el-tag>
          </h4>
          <el-empty v-if="!currentDetail.warnings || currentDetail.warnings.length === 0" description="无警告" :image-size="60" />
          <el-alert
            v-for="(warn, idx) in (currentDetail.warnings || [])"
            :key="idx"
            :title="warn"
            type="warning"
            :closable="false"
            show-icon
            class="warn-item"
          />
        </div>

        <div class="detail-section">
          <h4 class="section-title">动作列表</h4>
          <el-table :data="currentDetail.actions || []" stripe size="small" max-height="300">
            <el-table-column type="index" label="#" width="60" align="center" />
            <el-table-column prop="action_type" label="动作类型" min-width="120" />
            <el-table-column prop="target" label="目标" min-width="200" show-overflow-tooltip />
            <el-table-column prop="value" label="值" min-width="160" show-overflow-tooltip />
          </el-table>
        </div>

        <div class="detail-section">
          <h4 class="section-title">脚本内容</h4>
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
        </div>
      </div>
    </el-drawer>

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
        <p class="warning-tip">⚠️ 删除后无法恢复，请谨慎操作。</p>
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
import { ref, reactive, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Upload,
  Promotion,
  RefreshLeft,
  Refresh,
  View,
  Delete,
  VideoCamera,
  VideoPlay,
  VideoPause,
  MagicStick,
} from '@element-plus/icons-vue'
import {
  getRecordingList,
  createRecording,
  getRecordingDetail,
  deleteRecording,
  startCodegen,
  getCodegenStatus,
  stopCodegen,
  normalizeRecording,
} from '@/api/recording'
import { formatTime } from '@/utils/format'

// ---- state ----
const loading = ref(false)
const submitting = ref(false)
const recordingList = ref([])

const form = reactive({
  name: '',
  content: '',
})

// ---- P4：codegen 录制 ----
const codegenForm = reactive({
  name: '',
  start_url: 'http://127.0.0.1:8000/api/demo/login/',
  auto_analyze: true,
})
const codegenActive = ref(false)
const codegenStarting = ref(false)
const codegenStopping = ref(false)
const codegenStartedAt = ref('')
let codegenPollTimer = null

// ---- P4：AI 重组 ----
const normalizeRunningId = ref(null)
let normalizePollTimer = null

const detailDrawerVisible = ref(false)
const currentDetail = ref(null)
const detailLoading = ref(false)
const scriptTab = ref('raw')

const deleteDialogVisible = ref(false)
const deletingRow = ref(null)
const deleting = ref(false)

// ---- 工具 ----
const NORMALIZE_MAP = {
  idle: { text: '未重组', type: 'info' },
  running: { text: '重组中…', type: 'primary' },
  done: { text: '已重组', type: 'success' },
  failed: { text: '失败', type: 'danger' },
}

function normalizeTagType(s) { return NORMALIZE_MAP[s]?.type || 'info' }
function normalizeText(s) { return NORMALIZE_MAP[s]?.text || s || '未重组' }

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
  codegenStarting.value = true
  try {
    await startCodegen({
      name: codegenForm.name || '',
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
        `录制已保存：${result.name}（${result.actions_count} 个动作）` +
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

function handleBeforeUpload(file) {
  const reader = new FileReader()
  reader.onload = (e) => {
    form.content = e.target?.result || ''
    if (!form.name) {
      // 自动用文件名（去后缀）填充名称
      const name = file.name.replace(/\.[^.]+$/, '')
      form.name = name
    }
    ElMessage.success(`已读取文件：${file.name}`)
  }
  reader.onerror = () => {
    ElMessage.error('文件读取失败')
  }
  reader.readAsText(file)
  return false // 阻止自动上传
}

async function handleSubmit() {
  if (!form.name.trim()) {
    ElMessage.warning('请输入脚本名称')
    return
  }
  if (!form.content.trim()) {
    ElMessage.warning('请输入或上传脚本内容')
    return
  }
  submitting.value = true
  try {
    await createRecording({ name: form.name.trim(), content: form.content })
    ElMessage.success('脚本解析成功')
    form.name = ''
    form.content = ''
    await fetchList()
  } catch (err) {
    // 拦截器已提示
  } finally {
    submitting.value = false
  }
}

function handleReset() {
  form.name = ''
  form.content = ''
}

function scrollToForm() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
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

// ---- 生命周期 ----
onMounted(() => {
  fetchList()
  pollCodegenStatus()
})

onBeforeUnmount(() => {
  if (codegenPollTimer) clearInterval(codegenPollTimer)
  if (normalizePollTimer) clearInterval(normalizePollTimer)
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

.codegen-card {
  border-radius: 8px;
}

.card-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 16px;
  font-weight: 600;
  color: var(--do-fg);
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

.codegen-body {
  padding: 4px 0;
}

.auto-tip {
  margin-left: 8px;
}

.import-collapse {
  border: none;
  background: transparent;
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

.form-card,
.list-card {
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
