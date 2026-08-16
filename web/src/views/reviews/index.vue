<template>
  <div class="reviews-page">
    <!-- 顶部说明卡 -->
    <el-alert
      type="info"
      :closable="false"
      show-icon
      class="intro-alert"
    >
      <template #title>
        <span class="alert-title">评审中心</span>
      </template>
      <template #default>
        <p class="alert-desc">
          这里汇聚 DSH 智能体 A1（提取）和 A2（设计）阶段产出的 POM 草案与矩阵草案。
          评审通过后，草案将进入 P3 生成阶段，用于自动生成测试用例与自动化脚本。
        </p>
        <div class="alert-legend">
          <el-tag size="small" type="info" effect="plain">草稿</el-tag>
          <span class="legend-arrow">→</span>
          <el-tag size="small" type="success" effect="plain">已通过</el-tag>
          <span class="legend-sep">/</span>
          <el-tag size="small" type="danger" effect="plain">已驳回</el-tag>
        </div>
      </template>
    </el-alert>

    <el-card shadow="never" class="main-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">草案列表</span>
          <div class="toolbar">
            <el-select
              v-model="filterKind"
              placeholder="类型筛选"
              clearable
              style="width: 140px"
              @change="handleFilterChange"
            >
              <el-option label="POM 草案" value="pom" />
              <el-option label="矩阵草案" value="matrix" />
            </el-select>
            <el-select
              v-model="filterStatus"
              placeholder="状态筛选"
              clearable
              style="width: 140px"
              @change="handleFilterChange"
            >
              <el-option label="草稿" value="draft" />
              <el-option label="已通过" value="approved" />
              <el-option label="已驳回" value="rejected" />
            </el-select>
            <el-button :icon="Refresh" @click="fetchList">刷新</el-button>
            <el-button :icon="Monitor" @click="openInvocationDrawer">调用日志</el-button>
          </div>
        </div>
      </template>

      <el-table
        v-loading="loading"
        :data="draftList"
        stripe
        style="width: 100%"
      >
        <template #empty>
          <el-empty description="暂无待评审草案" />
        </template>

        <el-table-column label="类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="kindTagType(row.kind)" effect="dark" size="small">
              {{ row.kind === 'pom' ? 'POM' : '矩阵' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="所属任务集" width="120" align="center">
          <template #default="{ row }">
            <span v-if="row.task_set_id">#{{ row.task_set_id }}</span>
            <span v-else class="empty-tip">—</span>
          </template>
        </el-table-column>

        <el-table-column label="校验" width="80" align="center">
          <template #default="{ row }">
            <el-tooltip :content="row.valid ? '校验通过' : '校验未通过'" placement="top">
              <el-icon :class="['valid-icon', row.valid ? 'valid' : 'invalid']">
                <CircleCheck v-if="row.valid" />
                <CircleClose v-else />
              </el-icon>
            </el-tooltip>
          </template>
        </el-table-column>

        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" effect="light" size="small">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="schema_version" label="版本" width="80" align="center">
          <template #default="{ row }">v{{ row.schema_version }}</template>
        </el-table-column>

        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">
            <span v-if="row.created_at">{{ formatTime(row.created_at) }}</span>
            <span v-else class="empty-tip">—</span>
          </template>
        </el-table-column>

        <el-table-column prop="reviewed_at" label="评审时间" width="170">
          <template #default="{ row }">
            <span v-if="row.reviewed_at">{{ formatTime(row.reviewed_at) }}</span>
            <span v-else class="empty-tip">—</span>
          </template>
        </el-table-column>

        <el-table-column label="评审备注" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.review_note">{{ row.review_note }}</span>
            <span v-else class="empty-tip">—</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="220" fixed="right" align="center">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'draft'"
              type="success"
              link
              size="small"
              :icon="Check"
              @click="handleApprove(row)"
            >
              通过
            </el-button>
            <el-button
              v-if="row.status === 'draft'"
              type="danger"
              link
              size="small"
              :icon="Close"
              @click="handleReject(row)"
            >
              驳回
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
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @size-change="handlePageChange"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <!-- 详情抽屉 -->
    <el-drawer
      v-model="detailDrawerVisible"
      title="草案详情"
      size="45%"
    >
      <div v-if="currentDetail" class="detail-content">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="类型">
            <el-tag :type="kindTagType(currentDetail.kind)" effect="dark" size="small">
              {{ currentDetail.kind === 'pom' ? 'POM 草案' : '矩阵草案' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="所属任务集">
            #{{ currentDetail.task_set_id || '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTagType(currentDetail.status)" effect="light" size="small">
              {{ statusText(currentDetail.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="校验">
            <el-tag :type="currentDetail.valid ? 'success' : 'danger'" effect="plain" size="small">
              {{ currentDetail.valid ? '通过' : '未通过' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="schema_version">v{{ currentDetail.schema_version }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatTime(currentDetail.created_at) || '—' }}</el-descriptions-item>
          <el-descriptions-item v-if="currentDetail.reviewed_at" label="评审时间">
            {{ formatTime(currentDetail.reviewed_at) }}
          </el-descriptions-item>
          <el-descriptions-item v-if="currentDetail.review_note" label="评审备注">
            {{ currentDetail.review_note }}
          </el-descriptions-item>
        </el-descriptions>

        <!-- validation_errors 红色列出 -->
        <div v-if="currentDetail.validation_errors && currentDetail.validation_errors.length > 0" class="validation-section">
          <h4 class="section-title">
            <el-icon><WarningFilled /></el-icon>
            校验错误
          </h4>
          <ul class="validation-list">
            <li v-for="(err, idx) in currentDetail.validation_errors" :key="idx" class="validation-item">
              {{ err }}
            </li>
          </ul>
        </div>

        <!-- content JSON 展示 -->
        <div class="json-section">
          <h4 class="section-title">JSON 内容</h4>
          <pre class="json-block"><code>{{ formatJson(currentDetail.content) }}</code></pre>
        </div>

        <!-- 底部操作按钮（仅草稿状态可评审） -->
        <div v-if="currentDetail.status === 'draft'" class="detail-actions">
          <el-button type="success" :icon="Check" @click="handleApprove(currentDetail)">
            通过草案
          </el-button>
          <el-button type="danger" :icon="Close" @click="handleReject(currentDetail)">
            驳回草案
          </el-button>
        </div>
      </div>
    </el-drawer>

    <!-- 调用日志抽屉（可选加分） -->
    <el-drawer
      v-model="invocationDrawerVisible"
      title="智能体调用日志"
      size="40%"
      direction="rtl"
    >
      <div class="invocation-content">
        <div class="invocation-toolbar">
          <el-select
            v-model="invFilter.stage"
            placeholder="阶段筛选"
            clearable
            style="width: 140px"
            @change="fetchInvocations"
          >
            <el-option label="提取" value="extract" />
            <el-option label="设计" value="design" />
          </el-select>
          <el-select
            v-model="invFilter.status"
            placeholder="状态筛选"
            clearable
            style="width: 140px"
            @change="fetchInvocations"
          >
            <el-option label="成功" value="success" />
            <el-option label="失败" value="failed" />
            <el-option label="运行中" value="running" />
          </el-select>
          <el-button :icon="Refresh" size="small" @click="fetchInvocations">刷新</el-button>
        </div>

        <el-table
          v-loading="invLoading"
          :data="invocationList"
          stripe
          size="small"
          style="width: 100%"
        >
          <template #empty>
            <el-empty description="暂无调用日志" :image-size="60" />
          </template>

          <el-table-column prop="stage" label="阶段" width="80" />
          <el-table-column prop="status" label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="invStatusTagType(row.status)" size="small" effect="light">
                {{ row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="Mock" width="70" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.mock" type="warning" size="small">mock</el-tag>
              <span v-else class="empty-tip">—</span>
            </template>
          </el-table-column>
          <el-table-column label="耗时" width="90" align="right">
            <template #default="{ row }">
              <span v-if="row.duration_ms != null">{{ formatDuration(row.duration_ms) }}</span>
              <span v-else class="empty-tip">—</span>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="时间" width="160">
            <template #default="{ row }">
              <span v-if="row.created_at">{{ formatTime(row.created_at) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="error" label="错误" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.error" class="error-text">{{ row.error }}</span>
              <span v-else class="empty-tip">—</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Refresh,
  View,
  Check,
  Close,
  CircleCheck,
  CircleClose,
  Monitor,
  WarningFilled,
} from '@element-plus/icons-vue'
import {
  getDraftList,
  approveDraft,
  rejectDraft,
} from '@/api/reviews'
import { getInvocationList } from '@/api/agent'
import { formatTime, formatDuration } from '@/utils/format'

// ---- state ----
const loading = ref(false)
const draftList = ref([])
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

const filterKind = ref('')
const filterStatus = ref('')

const detailDrawerVisible = ref(false)
const currentDetail = ref(null)

// 调用日志抽屉
const invocationDrawerVisible = ref(false)
const invLoading = ref(false)
const invocationList = ref([])
const invFilter = reactive({
  stage: '',
  status: '',
})

// ---- 常量 / 工具 ----
function kindTagType(kind) {
  return kind === 'pom' ? 'purple' : 'cyan'
}

const STATUS_MAP = {
  draft:    { text: '草稿', type: 'info' },
  approved: { text: '已通过', type: 'success' },
  rejected: { text: '已驳回', type: 'danger' },
}

function statusTagType(status) {
  return STATUS_MAP[status]?.type || 'info'
}
function statusText(status) {
  return STATUS_MAP[status]?.text || status || '未知'
}

function invStatusTagType(status) {
  const map = {
    success: 'success',
    failed: 'danger',
    running: 'primary',
  }
  return map[status] || 'info'
}

function formatJson(obj) {
  if (obj == null) return ''
  try {
    return JSON.stringify(obj, null, 2)
  } catch (e) {
    return String(obj)
  }
}

// ---- actions ----
async function fetchList() {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
    }
    if (filterKind.value) params.kind = filterKind.value
    if (filterStatus.value) params.status = filterStatus.value

    const data = await getDraftList(params)
    draftList.value = Array.isArray(data) ? data : (data?.results || [])
    total.value = data?.count || draftList.value.length
  } catch (err) {
    draftList.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function handleFilterChange() {
  currentPage.value = 1
  fetchList()
}

function handlePageChange() {
  fetchList()
}

async function handleApprove(row) {
  try {
    const { value: note } = await ElMessageBox.prompt(
      '请输入评审意见（可选）',
      '通过草案',
      {
        confirmButtonText: '确认通过',
        cancelButtonText: '取消',
        inputPlaceholder: '可填写通过说明',
        inputType: 'textarea',
        inputValidator: () => true,
      }
    )
    await approveDraft(row.id, note || undefined)
    ElMessage.success('草案已通过')
    fetchList()
    if (detailDrawerVisible.value && currentDetail.value?.id === row.id) {
      currentDetail.value = { ...currentDetail.value, status: 'approved', review_note: note }
    }
  } catch (err) {
    if (err !== 'cancel') {
      // 409 等错误已由拦截器提示
    }
  }
}

async function handleReject(row) {
  try {
    const { value: note } = await ElMessageBox.prompt(
      '请输入驳回理由（可选）',
      '驳回草案',
      {
        confirmButtonText: '确认驳回',
        cancelButtonText: '取消',
        inputPlaceholder: '可填写驳回原因',
        inputType: 'textarea',
        inputValidator: () => true,
        type: 'warning',
      }
    )
    await rejectDraft(row.id, note || undefined)
    ElMessage.success('草案已驳回')
    fetchList()
    if (detailDrawerVisible.value && currentDetail.value?.id === row.id) {
      currentDetail.value = { ...currentDetail.value, status: 'rejected', review_note: note }
    }
  } catch (err) {
    if (err !== 'cancel') {
      // 409 等错误已由拦截器提示
    }
  }
}

function handleViewDetail(row) {
  currentDetail.value = row
  detailDrawerVisible.value = true
}

// ---- 调用日志 ----
function openInvocationDrawer() {
  invocationDrawerVisible.value = true
  if (!invocationList.value.length) {
    fetchInvocations()
  }
}

async function fetchInvocations() {
  invLoading.value = true
  try {
    const params = {}
    if (invFilter.stage) params.stage = invFilter.stage
    if (invFilter.status) params.status = invFilter.status
    const data = await getInvocationList(params)
    invocationList.value = Array.isArray(data) ? data : (data?.results || [])
  } catch (err) {
    invocationList.value = []
  } finally {
    invLoading.value = false
  }
}

// ---- 生命周期 ----
onMounted(() => {
  fetchList()
})
</script>

<style scoped>
.reviews-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 顶部说明卡 */
.intro-alert {
  flex-shrink: 0;
}

.alert-title {
  font-weight: 600;
  color: var(--do-fg);
}

.alert-desc {
  margin: 6px 0 10px 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--do-fg-secondary);
}

.alert-legend {
  display: flex;
  align-items: center;
  gap: 8px;
}

.legend-arrow {
  color: var(--do-fg-tertiary);
}

.legend-sep {
  color: var(--do-fg-tertiary);
  margin: 0 4px;
}

/* 主卡片 */
.main-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  border-radius: 8px;
  overflow: hidden;
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
  gap: 10px;
}

.empty-tip {
  color: var(--do-fg-tertiary);
}

.valid-icon {
  font-size: 18px;
}

.valid-icon.valid {
  color: var(--do-success, #67c23a);
}

.valid-icon.invalid {
  color: var(--do-danger, #f56c6c);
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  padding-top: 16px;
  flex-shrink: 0;
}

/* 详情抽屉 */
.detail-content {
  padding-right: 8px;
}

.section-title {
  margin: 0 0 10px 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--do-fg);
  display: flex;
  align-items: center;
  gap: 6px;
}

/* 校验错误 */
.validation-section {
  margin-top: 20px;
}

.validation-list {
  margin: 0;
  padding: 10px 12px 10px 28px;
  background: #fef0f0;
  border: 1px solid #fbc4c4;
  border-radius: 4px;
  color: #f56c6c;
}

.validation-item {
  font-size: 13px;
  line-height: 1.8;
  word-break: break-all;
}

/* JSON 内容 */
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
  max-height: 50vh;
  overflow: auto;
  color: var(--do-fg);
}

.detail-actions {
  position: sticky;
  bottom: 0;
  padding: 16px 0 0 0;
  margin-top: 20px;
  display: flex;
  gap: 12px;
  background: var(--do-bg-page);
  border-top: 1px solid var(--do-border, #e4e7ed);
  padding-top: 16px;
}

.error-text {
  color: var(--do-danger, #f56c6c);
  font-size: 12px;
}

/* 调用日志抽屉 */
.invocation-content {
  padding-right: 8px;
}

.invocation-toolbar {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
</style>
