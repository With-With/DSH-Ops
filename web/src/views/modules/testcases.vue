<template>
  <div class="testcases-page">
    <el-card shadow="never" class="main-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">用例管理</span>
          <div class="header-actions">
            <el-input
              v-model="searchKeyword"
              placeholder="搜索用例名称"
              clearable
              style="width: 220px"
              @keyup.enter="fetchList"
            >
              <template #append><el-button :icon="Search" @click="fetchList" /></template>
            </el-input>
            <el-button :icon="Refresh" circle @click="fetchList" />
            <el-button
              type="danger"
              :icon="Delete"
              :disabled="selectedIds.length === 0"
              @click="handleBulkDelete"
            >
              删除选中（{{ selectedIds.length }}）
            </el-button>
          </div>
        </div>
      </template>

      <el-alert
        type="info"
        :closable="false"
        show-icon
        class="intro-alert"
        title="用例来源：录制中心【AI 重组】自动生成 POM 页面对象化 pytest 脚本后自动入库"
      />

      <el-table
        v-loading="loading"
        :data="filteredList"
        stripe
        style="width: 100%"
        @selection-change="handleSelectionChange"
      >
        <template #empty>
          <el-empty description="暂无用例：录制中心对脚本执行【AI 重组】后自动生成">
            <el-text type="info" size="small">POM 脚手架：BasePage 基类 + 页面对象（每步一方法）+ pytest fixtures</el-text>
          </el-empty>
        </template>

        <el-table-column type="selection" width="50" />
        <el-table-column prop="name" label="用例名称" min-width="200" show-overflow-tooltip />
        <el-table-column label="来源" width="130" align="center">
          <template #default="{ row }">
            <el-tag :type="row.source === 'ai_normalized' ? 'success' : 'info'" size="small" effect="light">
              {{ row.source === 'ai_normalized' ? 'AI 重组' : '手动' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ready' ? 'success' : 'info'" size="small" effect="plain">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="来源录制" width="110" align="center">
          <template #default="{ row }">
            <span v-if="row.recording_id">#{{ row.recording_id }}</span>
            <span v-else class="empty-tip">—</span>
          </template>
        </el-table-column>
        <el-table-column label="标签" min-width="140">
          <template #default="{ row }">
            <el-tag
              v-for="t in (row.tags || [])"
              :key="t"
              size="small"
              effect="plain"
              class="tag-item"
            >{{ t }}</el-tag>
            <span v-if="!(row.tags || []).length" class="empty-tip">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            <span v-if="row.created_at">{{ formatTime(row.created_at) }}</span>
            <span v-else class="empty-tip">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link size="small" :icon="View" @click="handleViewScript(row)">
              查看脚本
            </el-button>
            <el-button type="danger" link size="small" :icon="Delete" @click="handleDeleteOne(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 脚本查看抽屉 -->
    <el-drawer v-model="scriptDrawerVisible" title="POM pytest 脚本" size="60%">
      <div v-if="currentScript" class="script-content">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="用例名称">{{ currentScript.name }}</el-descriptions-item>
          <el-descriptions-item label="来源">
            <el-tag :type="currentScript.source === 'ai_normalized' ? 'success' : 'info'" size="small">
              {{ currentScript.source === 'ai_normalized' ? 'AI 重组' : '手动' }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>
        <div class="pom-note">
          <el-alert
            type="success"
            :closable="false"
            show-icon
            title="POM 页面对象脚手架：BasePage 基类（独立）+ 页面对象类（每步一方法）+ pytest fixtures + 用例"
          />
        </div>
        <pre class="script-block"><code>{{ currentScript.content || '（无脚本内容）' }}</code></pre>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Delete, View } from '@element-plus/icons-vue'
import { getTestCaseList, deleteTestCase, bulkDeleteTestCases } from '@/api/testcases'
import { formatTime } from '@/utils/format'

const loading = ref(false)
const testCaseList = ref([])
const searchKeyword = ref('')
const selectedIds = ref([])

const scriptDrawerVisible = ref(false)
const currentScript = ref(null)

const STATUS_MAP = {
  draft: { text: '草稿', type: 'info' },
  ready: { text: '就绪', type: 'success' },
  archived: { text: '归档', type: 'warning' },
}
function statusText(s) { return STATUS_MAP[s]?.text || s || '未知' }

const filteredList = computed(() => {
  const kw = searchKeyword.value.trim().toLowerCase()
  if (!kw) return testCaseList.value
  return testCaseList.value.filter((t) => (t.name || '').toLowerCase().includes(kw))
})

function handleSelectionChange(rows) {
  selectedIds.value = rows.map((r) => r.id)
}

async function fetchList() {
  loading.value = true
  try {
    const data = await getTestCaseList()
    testCaseList.value = Array.isArray(data) ? data : (data?.results || [])
  } catch (e) {
    testCaseList.value = []
  } finally {
    loading.value = false
  }
}

function handleViewScript(row) {
  currentScript.value = row
  scriptDrawerVisible.value = true
}

async function handleDeleteOne(row) {
  try {
    await ElMessageBox.confirm(`确定删除用例「${row.name}」？`, '删除确认', { type: 'warning' })
    await deleteTestCase(row.id)
    ElMessage.success('已删除')
    fetchList()
  } catch (e) { /* 取消 */ }
}

async function handleBulkDelete() {
  if (!selectedIds.value.length) return
  try {
    await ElMessageBox.confirm(`确定删除选中的 ${selectedIds.value.length} 条用例？`, '批量删除', {
      type: 'warning', confirmButtonText: '删除',
    })
    const result = await bulkDeleteTestCases(selectedIds.value)
    ElMessage.success(`已删除 ${result.deleted} 条`)
    selectedIds.value = []
    fetchList()
  } catch (e) { /* 取消 */ }
}

onMounted(fetchList)
</script>

<style scoped>
.testcases-page { height: 100%; }
.main-card { height: 100%; border-radius: 8px; }
.card-header { display: flex; align-items: center; justify-content: space-between; }
.card-title { font-size: 16px; font-weight: 600; color: var(--do-fg); }
.header-actions { display: flex; align-items: center; gap: 10px; }
.intro-alert { margin-bottom: 16px; }
.empty-tip { color: var(--do-fg-tertiary); }
.tag-item { margin-right: 4px; }

.script-content { padding-right: 8px; }
.pom-note { margin: 14px 0; }
.script-block {
  background: #0d1117;
  color: #e6edf3;
  border-radius: 6px;
  padding: 14px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12.5px;
  line-height: 1.6;
  overflow: auto;
  max-height: 70vh;
  white-space: pre;
}
</style>
