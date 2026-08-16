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
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, View } from '@element-plus/icons-vue'
import {
  getTasksetList,
  createTaskset,
  getTasksetDetail,
} from '@/api/tasksets'
import { getRecordingList } from '@/api/recording'
import { formatTime } from '@/utils/format'

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

// ---- 常量 / 工具 ----
const STATUS_MAP = {
  created:     { text: '已创建', type: 'info' },
  replaying:   { text: '回放中', type: 'primary' },
  replay_done: { text: '回放完成', type: 'success' },
  failed:      { text: '失败', type: 'danger' },
  success:     { text: '成功', type: 'success' },
  running:     { text: '执行中', type: 'primary' },
  pending:     { text: '等待中', type: 'info' },
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
    failed: 'danger',
    replaying: 'primary',
    running: 'primary',
    created: 'info',
    pending: 'info',
  }
  return typeMap[status] || 'info'
}

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

// ---- 生命周期 ----
onMounted(() => {
  fetchList()
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

.timeline-section {
  margin-top: 24px;
}

.section-title {
  margin: 0 0 16px 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--do-fg);
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
