<template>
  <div class="recorder-page">
    <!-- 上方：提交表单 -->
    <el-card shadow="never" class="form-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">提交录制脚本</span>
        </div>
      </template>

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
              :rows="10"
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
          <h4 class="section-title">原始脚本</h4>
          <pre class="code-block">{{ currentDetail.normalized_content || currentDetail.content || '—' }}</pre>
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
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Upload,
  Promotion,
  RefreshLeft,
  Refresh,
  View,
  Delete,
} from '@element-plus/icons-vue'
import {
  getRecordingList,
  createRecording,
  getRecordingDetail,
  deleteRecording,
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

const detailDrawerVisible = ref(false)
const currentDetail = ref(null)
const detailLoading = ref(false)

const deleteDialogVisible = ref(false)
const deletingRow = ref(null)
const deleting = ref(false)

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
