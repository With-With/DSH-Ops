<template>
  <div class="replay-page">
    <el-card shadow="never" class="main-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">回放中心</span>
          <div class="toolbar">
            <el-select
              v-model="selectedRecordingId"
              placeholder="选择录制脚本"
              filterable
              style="width: 280px"
              :loading="recordingsLoading"
              @change="handleRecordingChange"
            >
              <el-option
                v-for="item in recordingOptions"
                :key="item.id"
                :label="item.name"
                :value="item.id"
              />
            </el-select>
            <el-button
              type="primary"
              :icon="VideoPlay"
              :loading="replaying"
              :disabled="!selectedRecordingId"
              @click="handleStartReplay"
            >
              {{ replaying ? '回放执行中...' : '开始回放' }}
            </el-button>
          </div>
        </div>
      </template>

      <el-table
        v-loading="loading"
        :data="replayList"
        stripe
        style="width: 100%"
      >
        <template #empty>
          <el-empty description="暂无回放记录，选择脚本并点击【开始回放】">
            <el-button type="primary" :icon="VideoPlay" @click="scrollToTop">开始回放</el-button>
          </el-empty>
        </template>

        <el-table-column prop="id" label="ID" width="80" align="center" />

        <el-table-column label="所属录制" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <span>{{ row.recording?.name || row.recording_id || '—' }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="status" label="状态" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" effect="light">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="耗时" width="120" align="center">
          <template #default="{ row }">
            <span v-if="row.duration_ms != null">{{ formatDuration(row.duration_ms) }}</span>
            <span v-else class="empty-tip">—</span>
          </template>
        </el-table-column>

        <el-table-column label="步骤通过" width="140" align="center">
          <template #default="{ row }">
            <span v-if="row.steps_total != null">
              <span class="passed">{{ row.steps_passed ?? 0 }}</span>
              <span class="total"> / {{ row.steps_total }}</span>
            </span>
            <span v-else class="empty-tip">—</span>
          </template>
        </el-table-column>

        <el-table-column label="Trace" width="100" align="center">
          <template #default="{ row }">
            <el-tag
              v-if="row.trace_available"
              type="success"
              size="small"
              effect="plain"
            >
              可用
            </el-tag>
            <span v-else class="empty-tip">—</span>
          </template>
        </el-table-column>

        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            <span v-if="row.created_at">{{ formatTime(row.created_at) }}</span>
            <span v-else class="empty-tip">—</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <el-button
              type="primary"
              link
              size="small"
              :icon="Download"
              :disabled="!row.trace_available"
              @click="handleDownloadTrace(row)"
            >
              下载 Trace
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
          </template>
        </el-table-column>

        <!-- 失败错误展开行 -->
        <el-table-column type="expand" v-if="hasFailedRecords">
          <template #default="{ row }">
            <div v-if="row.status === 'failed' && row.error" class="error-expand">
              <div class="error-label">错误信息：</div>
              <pre class="error-content">{{ row.error }}</pre>
            </div>
            <div v-else class="empty-tip">无详细错误信息</div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 详情抽屉 -->
    <el-drawer
      v-model="detailDrawerVisible"
      title="回放详情"
      size="50%"
    >
      <div v-if="currentDetail" class="detail-content">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="回放 ID">{{ currentDetail.id }}</el-descriptions-item>
          <el-descriptions-item label="所属录制">
            {{ currentDetail.recording?.name || currentDetail.recording_id || '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTagType(currentDetail.status)" effect="light">
              {{ statusText(currentDetail.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="耗时">
            {{ currentDetail.duration_ms != null ? formatDuration(currentDetail.duration_ms) : '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="步骤通过">
            {{ currentDetail.steps_passed ?? 0 }} / {{ currentDetail.steps_total ?? '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="Trace">
            <el-tag v-if="currentDetail.trace_available" type="success" size="small" effect="plain">可用</el-tag>
            <span v-else>不可用</span>
          </el-descriptions-item>
        </el-descriptions>

        <div v-if="currentDetail.error" class="error-section">
          <h4 class="section-title">错误详情</h4>
          <pre class="error-block">{{ currentDetail.error }}</pre>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  VideoPlay,
  Download,
  View,
} from '@element-plus/icons-vue'
import {
  getReplayList,
  startReplay,
  getReplayDetail,
} from '@/api/replay'
import { getRecordingList } from '@/api/recording'
import { formatTime, formatDuration } from '@/utils/format'

// ---- state ----
const loading = ref(false)
const replaying = ref(false)
const replayList = ref([])

const recordingsLoading = ref(false)
const recordingOptions = ref([])
const selectedRecordingId = ref(null)

const detailDrawerVisible = ref(false)
const currentDetail = ref(null)

// ---- 常量 / 工具 ----
const STATUS_MAP = {
  success: { text: '成功', type: 'success' },
  failed:  { text: '失败', type: 'danger' },
  running: { text: '执行中', type: 'primary' },
  pending: { text: '等待中', type: 'info' },
}

function statusTagType(status) {
  return STATUS_MAP[status]?.type || 'info'
}
function statusText(status) {
  return STATUS_MAP[status]?.text || status || '未知'
}

const hasFailedRecords = computed(() =>
  replayList.value.some((r) => r.status === 'failed')
)

// ---- actions ----
async function fetchList() {
  loading.value = true
  try {
    const data = await getReplayList()
    replayList.value = Array.isArray(data) ? data : (data?.results || [])
  } catch (err) {
    replayList.value = []
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

function handleRecordingChange() {
  // 仅做选择，不自动触发
}

async function handleStartReplay() {
  if (!selectedRecordingId.value) {
    ElMessage.warning('请先选择录制脚本')
    return
  }
  replaying.value = true
  try {
    const result = await startReplay(selectedRecordingId.value)
    if (result?.status === 'success') {
      ElMessage.success('回放执行成功')
    } else if (result?.status === 'failed') {
      ElMessage.error('回放执行失败')
    } else {
      ElMessage.success('回放任务已提交')
    }
    await fetchList()
  } catch (err) {
    // 拦截器已提示
  } finally {
    replaying.value = false
  }
}

function handleDownloadTrace(row) {
  if (!row.trace_available) {
    ElMessage.warning('Trace 不可用')
    return
  }
  const url = row.trace_url || `/api/replays/${row.id}/trace/download/`
  window.open(url, '_blank')
}

async function handleViewDetail(row) {
  detailDrawerVisible.value = true
  currentDetail.value = null
  try {
    const detail = await getReplayDetail(row.id)
    currentDetail.value = detail
  } catch (err) {
    // 拦截器已提示
    detailDrawerVisible.value = false
  }
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

// ---- 生命周期 ----
onMounted(() => {
  fetchList()
  fetchRecordings()
})
</script>

<style scoped>
.replay-page {
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

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
}

.passed {
  color: var(--do-success);
  font-weight: 600;
}

.total {
  color: var(--do-fg-tertiary);
}

.empty-tip {
  color: var(--do-fg-tertiary);
}

.error-expand {
  padding: 0 20px 12px 20px;
}

.error-label {
  font-size: 12px;
  color: var(--do-fg-secondary);
  margin-bottom: 6px;
}

.error-content {
  margin: 0;
  padding: 10px 12px;
  background: #fef0f0;
  border: 1px solid #fbc4c4;
  border-radius: 4px;
  color: #f56c6c;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow: auto;
}

.detail-content {
  padding-right: 8px;
}

.error-section {
  margin-top: 20px;
}

.section-title {
  margin: 0 0 10px 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--do-fg);
}

.error-block {
  margin: 0;
  padding: 12px;
  background: #fef0f0;
  border: 1px solid #fbc4c4;
  border-radius: 4px;
  color: #f56c6c;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow: auto;
}
</style>
