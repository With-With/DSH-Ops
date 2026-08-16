<template>
  <div class="assets-page">
    <el-card shadow="never" class="main-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">元素管理</span>
          <el-button type="primary" :icon="Search" @click="queryDialogVisible = true">
            search-first 查询测试
          </el-button>
        </div>
      </template>

      <el-tabs v-model="activeTab" class="assets-tabs">
        <!-- Pages 页签 -->
        <el-tab-pane label="Pages" name="pages">
          <div class="tab-toolbar">
            <el-button type="primary" :icon="Plus" @click="openPageDialog">新建页面</el-button>
          </div>

          <el-table v-loading="pagesLoading" :data="pageList" stripe style="width: 100%">
            <template #empty>
              <el-empty description="暂无页面对象，点击【新建页面】开始创建">
                <el-button type="primary" :icon="Plus" @click="openPageDialog">新建页面</el-button>
              </el-empty>
            </template>

            <el-table-column prop="name" label="名称" min-width="160" show-overflow-tooltip />
            <el-table-column prop="url_pattern" label="URL Pattern" min-width="260" show-overflow-tooltip />
            <el-table-column prop="notes" label="备注" min-width="200" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="row.notes">{{ row.notes }}</span>
                <span v-else class="empty-tip">—</span>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="180">
              <template #default="{ row }">
                <span v-if="row.created_at">{{ formatTime(row.created_at) }}</span>
                <span v-else class="empty-tip">—</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right" align="center">
              <template #default="{ row }">
                <el-button
                  type="danger"
                  link
                  size="small"
                  :icon="Delete"
                  @click="handleDeletePage(row)"
                >
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- Elements 页签 -->
        <el-tab-pane label="Elements" name="elements">
          <div class="tab-toolbar">
            <div class="filter-row">
              <el-select
                v-model="elementFilter.page_id"
                placeholder="选择页面"
                clearable
                style="width: 200px"
                @change="fetchElements"
              >
                <el-option
                  v-for="p in pageList"
                  :key="p.id"
                  :label="p.name"
                  :value="p.id"
                />
              </el-select>
              <el-input
                v-model="elementFilter.search"
                placeholder="搜索名称 / role"
                clearable
                style="width: 240px"
                @keyup.enter="fetchElements"
              >
                <template #append>
                  <el-button :icon="Search" @click="fetchElements" />
                </template>
              </el-input>
            </div>
            <el-button type="primary" :icon="Plus" @click="openElementDialog">新建元素</el-button>
          </div>

          <el-table v-loading="elementsLoading" :data="elementList" stripe style="width: 100%">
            <template #empty>
              <el-empty description="暂无元素，切换页面筛选或点击【新建元素】">
                <el-button type="primary" :icon="Plus" @click="openElementDialog">新建元素</el-button>
              </el-empty>
            </template>

            <el-table-column label="所属页" min-width="140" show-overflow-tooltip>
              <template #default="{ row }">
                <span>{{ getPageName(row.page_id) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="name" label="名称" min-width="160" show-overflow-tooltip />
            <el-table-column prop="role" label="Role" width="120" />
            <el-table-column label="候选定位器数" width="120" align="center">
              <template #default="{ row }">
                <el-tag size="small" effect="plain">{{ (row.candidates || []).length }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="snapshot_hash" width="120" align="center">
              <template #default="{ row }">
                <span v-if="row.snapshot_hash" class="hash-text">
                  {{ row.snapshot_hash.slice(0, 8) }}
                </span>
                <span v-else class="empty-tip">—</span>
              </template>
            </el-table-column>
            <el-table-column prop="source" label="来源" width="100">
              <template #default="{ row }">
                <span v-if="row.source">{{ row.source }}</span>
                <span v-else class="empty-tip">—</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right" align="center">
              <template #default="{ row }">
                <el-button
                  type="danger"
                  link
                  size="small"
                  :icon="Delete"
                  @click="handleDeleteElement(row)"
                >
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 新建页面对话框 -->
    <el-dialog
      v-model="pageDialogVisible"
      title="新建页面"
      width="520px"
      :close-on-click-modal="false"
    >
      <el-form :model="pageForm" label-width="100px">
        <el-form-item label="页面名称">
          <el-input v-model="pageForm.name" placeholder="如：登录页" maxlength="100" show-word-limit />
        </el-form-item>
        <el-form-item label="URL Pattern">
          <el-input v-model="pageForm.url_pattern" placeholder="如：/login、https://example.com/*" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="pageForm.notes" type="textarea" :rows="3" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pageDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="pageSubmitting" @click="handleCreatePage">
          {{ pageSubmitting ? '提交中...' : '确认创建' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 新建元素对话框 -->
    <el-dialog
      v-model="elementDialogVisible"
      title="新建元素"
      width="720px"
      :close-on-click-modal="false"
    >
      <el-form :model="elementForm" label-width="100px">
        <el-form-item label="所属页面">
          <el-select v-model="elementForm.page_id" placeholder="请选择页面" filterable style="width: 100%">
            <el-option
              v-for="p in pageList"
              :key="p.id"
              :label="p.name"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="元素名称">
          <el-input v-model="elementForm.name" placeholder="如：提交按钮" maxlength="100" />
        </el-form-item>
        <el-form-item label="Role">
          <el-select v-model="elementForm.role" placeholder="请选择 role" style="width: 100%">
            <el-option label="button" value="button" />
            <el-option label="link" value="link" />
            <el-option label="input" value="input" />
            <el-option label="textbox" value="textbox" />
            <el-option label="checkbox" value="checkbox" />
            <el-option label="radio" value="radio" />
            <el-option label="heading" value="heading" />
            <el-option label="img" value="img" />
            <el-option label="select" value="select" />
            <el-option label="table" value="table" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>

        <el-form-item label="候选定位器">
          <div class="candidates-wrapper">
            <div
              v-for="(cand, idx) in elementForm.candidates"
              :key="idx"
              class="candidate-row"
            >
              <el-select v-model="cand.type" placeholder="类型" style="width: 140px">
                <el-option label="css" value="css" />
                <el-option label="xpath" value="xpath" />
                <el-option label="id" value="id" />
                <el-option label="name" value="name" />
                <el-option label="text" value="text" />
                <el-option label="placeholder" value="placeholder" />
                <el-option label="testid" value="testid" />
              </el-select>
              <el-input v-model="cand.value" placeholder="定位器值" style="flex: 1" />
              <el-input-number v-model="cand.priority" :min="1" :max="99" controls-position="right" style="width: 100px" />
              <el-select v-model="cand.robustness" placeholder="健壮性" style="width: 110px">
                <el-option label="high" value="high" />
                <el-option label="medium" value="medium" />
                <el-option label="low" value="low" />
              </el-select>
              <el-button
                type="danger"
                link
                :icon="Delete"
                :disabled="elementForm.candidates.length <= 1"
                @click="removeCandidate(idx)"
              >
                删除
              </el-button>
            </div>
            <el-button type="primary" plain :icon="Plus" @click="addCandidate">
              添加候选定位器
            </el-button>
          </div>
        </el-form-item>

        <el-form-item label="snapshot_hash">
          <el-input v-model="elementForm.snapshot_hash" placeholder="可选，页面快照哈希" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="elementForm.notes" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="elementDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="elementSubmitting" @click="handleCreateElement">
          {{ elementSubmitting ? '提交中...' : '确认创建' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- search-first 查询测试对话框 -->
    <el-dialog
      v-model="queryDialogVisible"
      title="search-first 查询测试"
      width="640px"
      :close-on-click-modal="false"
      @closed="resetQueryForm"
    >
      <el-form :model="queryForm" label-width="120px">
        <el-form-item label="页面 URL">
          <el-input v-model="queryForm.page_url" placeholder="如：https://example.com/login" />
        </el-form-item>
        <el-form-item label="元素名称">
          <el-input v-model="queryForm.name" placeholder="如：登录按钮" />
        </el-form-item>
        <el-form-item label="Role">
          <el-select v-model="queryForm.role" placeholder="请选择 role" filterable allow-create style="width: 100%">
            <el-option label="button" value="button" />
            <el-option label="link" value="link" />
            <el-option label="input" value="input" />
            <el-option label="textbox" value="textbox" />
            <el-option label="checkbox" value="checkbox" />
            <el-option label="heading" value="heading" />
          </el-select>
        </el-form-item>
        <el-form-item label="snapshot_hash">
          <el-input v-model="queryForm.snapshot_hash" placeholder="可选" />
        </el-form-item>
      </el-form>

      <div class="query-actions">
        <el-button type="primary" :loading="querySubmitting" :icon="Search" @click="handleQuery">
          {{ querySubmitting ? '查询中...' : '提交查询' }}
        </el-button>
      </div>

      <!-- 查询结果 -->
      <div v-if="queryResult" class="query-result">
        <el-divider>查询结果</el-divider>

        <div class="result-section">
          <div class="result-label">置信度</div>
          <el-tag :type="confidenceTagType(queryResult.confidence)" effect="light" size="large">
            {{ confidenceText(queryResult.confidence) }}
          </el-tag>
        </div>

        <div v-if="queryResult.reason" class="result-section">
          <div class="result-label">说明</div>
          <div class="result-text">{{ queryResult.reason }}</div>
        </div>

        <div v-if="queryResult.match" class="result-section">
          <div class="result-label">最佳匹配</div>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="名称">{{ queryResult.match.name || '—' }}</el-descriptions-item>
            <el-descriptions-item label="Role">{{ queryResult.match.role || '—' }}</el-descriptions-item>
            <el-descriptions-item label="页面">{{ queryResult.match.page_name || queryResult.match.page_id || '—' }}</el-descriptions-item>
            <el-descriptions-item v-if="queryResult.match.confidence" label="匹配度">
              {{ queryResult.match.confidence }}
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <div v-if="queryResult.similar && queryResult.similar.length > 0" class="result-section">
          <div class="result-label">相似元素（{{ queryResult.similar.length }}）</div>
          <el-table :data="queryResult.similar" size="small" stripe>
            <el-table-column prop="name" label="名称" min-width="120" />
            <el-table-column prop="role" label="Role" width="100" />
            <el-table-column prop="confidence" label="相似度" width="100" />
          </el-table>
        </div>
      </div>

      <template #footer>
        <el-button @click="queryDialogVisible = false">关闭</el-button>
      </template>
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
          :title="deleteDialogTitle"
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
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Search,
  Plus,
  Delete,
} from '@element-plus/icons-vue'
import {
  getPageList,
  createPage,
  deletePage,
  getElementList,
  createElement,
  deleteElement,
  queryElement,
} from '@/api/assets'
import { formatTime } from '@/utils/format'

// ---- state ----
const activeTab = ref('pages')

// Pages
const pagesLoading = ref(false)
const pageList = ref([])
const pageDialogVisible = ref(false)
const pageSubmitting = ref(false)
const pageForm = reactive({ name: '', url_pattern: '', notes: '' })

// Elements
const elementsLoading = ref(false)
const elementList = ref([])
const elementFilter = reactive({ page_id: null, search: '' })
const elementDialogVisible = ref(false)
const elementSubmitting = ref(false)
const elementForm = reactive({
  page_id: null,
  name: '',
  role: '',
  candidates: [{ type: 'css', value: '', priority: 1, robustness: 'high' }],
  snapshot_hash: '',
  notes: '',
})

// Query
const queryDialogVisible = ref(false)
const querySubmitting = ref(false)
const queryForm = reactive({
  page_url: '',
  name: '',
  role: '',
  snapshot_hash: '',
})
const queryResult = ref(null)

// Delete
const deleteDialogVisible = ref(false)
const deleting = ref(false)
const deleteTarget = ref(null) // { type: 'page'|'element', row }

// ---- 常量 / 工具 ----
const CONFIDENCE_MAP = {
  high:   { text: '高', type: 'success' },
  medium: { text: '中', type: 'warning' },
  none:   { text: '无匹配', type: 'info' },
}

function confidenceTagType(conf) {
  return CONFIDENCE_MAP[conf]?.type || 'info'
}
function confidenceText(conf) {
  return CONFIDENCE_MAP[conf]?.text || conf || '未知'
}

function getPageName(pageId) {
  const p = pageList.value.find((item) => item.id === pageId)
  return p ? p.name : '—'
}

const deleteDialogTitle = computed(() => {
  if (!deleteTarget.value) return ''
  const { type, row } = deleteTarget.value
  if (type === 'page') return `确定要删除页面「${row.name || ''}」吗？`
  if (type === 'element') return `确定要删除元素「${row.name || ''}」吗？`
  return '确定删除吗？'
})

// ---- Pages actions ----
async function fetchPages() {
  pagesLoading.value = true
  try {
    const data = await getPageList()
    pageList.value = Array.isArray(data) ? data : (data?.results || [])
  } catch (err) {
    pageList.value = []
  } finally {
    pagesLoading.value = false
  }
}

function openPageDialog() {
  pageForm.name = ''
  pageForm.url_pattern = ''
  pageForm.notes = ''
  pageDialogVisible.value = true
}

async function handleCreatePage() {
  if (!pageForm.name.trim()) {
    ElMessage.warning('请输入页面名称')
    return
  }
  if (!pageForm.url_pattern.trim()) {
    ElMessage.warning('请输入 URL Pattern')
    return
  }
  pageSubmitting.value = true
  try {
    await createPage({
      name: pageForm.name.trim(),
      url_pattern: pageForm.url_pattern.trim(),
      notes: pageForm.notes.trim() || undefined,
    })
    ElMessage.success('页面创建成功')
    pageDialogVisible.value = false
    fetchPages()
  } catch (err) {
    // 拦截器已提示
  } finally {
    pageSubmitting.value = false
  }
}

function handleDeletePage(row) {
  deleteTarget.value = { type: 'page', row }
  deleteDialogVisible.value = true
}

// ---- Elements actions ----
async function fetchElements() {
  elementsLoading.value = true
  try {
    const params = {}
    if (elementFilter.page_id) params.page_id = elementFilter.page_id
    if (elementFilter.search) params.search = elementFilter.search
    const data = await getElementList(params)
    elementList.value = Array.isArray(data) ? data : (data?.results || [])
  } catch (err) {
    elementList.value = []
  } finally {
    elementsLoading.value = false
  }
}

function openElementDialog() {
  elementForm.page_id = elementFilter.page_id || (pageList.value[0]?.id ?? null)
  elementForm.name = ''
  elementForm.role = ''
  elementForm.candidates = [{ type: 'css', value: '', priority: 1, robustness: 'high' }]
  elementForm.snapshot_hash = ''
  elementForm.notes = ''
  elementDialogVisible.value = true
}

function addCandidate() {
  elementForm.candidates.push({ type: 'css', value: '', priority: elementForm.candidates.length + 1, robustness: 'medium' })
}

function removeCandidate(idx) {
  if (elementForm.candidates.length <= 1) return
  elementForm.candidates.splice(idx, 1)
}

async function handleCreateElement() {
  if (!elementForm.page_id) {
    ElMessage.warning('请选择所属页面')
    return
  }
  if (!elementForm.name.trim()) {
    ElMessage.warning('请输入元素名称')
    return
  }
  if (!elementForm.role) {
    ElMessage.warning('请选择 role')
    return
  }
  // 校验候选定位器
  const validCandidates = elementForm.candidates.filter((c) => c.type && c.value)
  if (validCandidates.length === 0) {
    ElMessage.warning('请至少填写一个有效的候选定位器')
    return
  }
  elementSubmitting.value = true
  try {
    await createElement({
      page_id: elementForm.page_id,
      name: elementForm.name.trim(),
      role: elementForm.role,
      candidates: validCandidates,
      snapshot_hash: elementForm.snapshot_hash.trim() || undefined,
      notes: elementForm.notes.trim() || undefined,
    })
    ElMessage.success('元素创建成功')
    elementDialogVisible.value = false
    fetchElements()
  } catch (err) {
    // 拦截器已提示
  } finally {
    elementSubmitting.value = false
  }
}

function handleDeleteElement(row) {
  deleteTarget.value = { type: 'element', row }
  deleteDialogVisible.value = true
}

// ---- Query actions ----
async function handleQuery() {
  if (!queryForm.page_url.trim()) {
    ElMessage.warning('请输入页面 URL')
    return
  }
  if (!queryForm.name.trim()) {
    ElMessage.warning('请输入元素名称')
    return
  }
  querySubmitting.value = true
  queryResult.value = null
  try {
    const data = {
      page_url: queryForm.page_url.trim(),
      name: queryForm.name.trim(),
    }
    if (queryForm.role) data.role = queryForm.role
    if (queryForm.snapshot_hash.trim()) data.snapshot_hash = queryForm.snapshot_hash.trim()
    const result = await queryElement(data)
    queryResult.value = result
  } catch (err) {
    // 拦截器已提示
  } finally {
    querySubmitting.value = false
  }
}

function resetQueryForm() {
  queryForm.page_url = ''
  queryForm.name = ''
  queryForm.role = ''
  queryForm.snapshot_hash = ''
  queryResult.value = null
}

// ---- Delete confirm ----
async function confirmDelete() {
  if (!deleteTarget.value) return
  const { type, row } = deleteTarget.value
  deleting.value = true
  try {
    if (type === 'page') {
      await deletePage(row.id)
      ElMessage.success('页面删除成功')
      fetchPages()
    } else if (type === 'element') {
      await deleteElement(row.id)
      ElMessage.success('元素删除成功')
      fetchElements()
    }
    deleteDialogVisible.value = false
  } catch (err) {
    // 拦截器已提示
  } finally {
    deleting.value = false
  }
}

// ---- 生命周期 ----
onMounted(async () => {
  await fetchPages()
  fetchElements()
})
</script>

<style scoped>
.assets-page {
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

.assets-tabs {
  height: calc(100% - 60px);
}

.assets-tabs :deep(.el-tabs__content) {
  height: calc(100% - 50px);
  overflow: hidden;
}

.assets-tabs :deep(.el-tab-pane) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.tab-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.empty-tip {
  color: var(--do-fg-tertiary);
}

.hash-text {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  color: var(--do-fg-secondary);
}

.candidates-wrapper {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.candidate-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.query-actions {
  display: flex;
  justify-content: center;
  margin: 16px 0;
}

.query-result {
  margin-top: 8px;
}

.result-section {
  margin-bottom: 16px;
}

.result-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--do-fg-secondary);
  margin-bottom: 8px;
}

.result-text {
  padding: 10px 12px;
  background: var(--do-bg, #f5f7fa);
  border-radius: 4px;
  font-size: 13px;
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
