<template>
  <div class="runtimes-page">
    <el-card shadow="never" class="main-card">
      <!-- 工具栏 -->
      <template #header>
        <div class="card-header">
          <span class="card-title">DSH 运行时管理</span>
          <el-button
            type="primary"
            :icon="Search"
            :loading="detecting"
            @click="handleDetect"
          >
            {{ detecting ? '检测中...' : '检测环境' }}
          </el-button>
        </div>
      </template>

      <!-- 表格 -->
      <el-table
        v-loading="loading"
        :data="runtimeList"
        stripe
        style="width: 100%"
      >
        <template #empty>
          <el-empty description="尚未检测，点击【检测环境】开始发现本机 DSH 运行时">
            <el-button type="primary" :icon="Search" @click="handleDetect">检测环境</el-button>
          </el-empty>
        </template>

        <el-table-column prop="name" label="名称" min-width="140">
          <template #default="{ row }">
            <div class="name-cell">
              <span>{{ row.name }}</span>
              <el-tag
                v-if="row.is_default"
                type="primary"
                size="small"
                effect="light"
                class="default-tag"
              >
                默认
              </el-tag>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="version" label="版本" min-width="120" />
        <el-table-column prop="node_version" label="Node 版本" min-width="120" />

        <el-table-column prop="status" label="状态" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" effect="light">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="home_dir" label="DSH_HOME" min-width="220" show-overflow-tooltip />

        <el-table-column prop="profiles" label="Profiles" min-width="180">
          <template #default="{ row }">
            <el-tag
              v-for="p in (row.profiles || [])"
              :key="p"
              size="small"
              type="info"
              effect="plain"
              class="profile-tag"
            >
              {{ p }}
            </el-tag>
            <span v-if="!row.profiles || row.profiles.length === 0" class="empty-tip">—</span>
          </template>
        </el-table-column>

        <el-table-column prop="last_check_at" label="最后检查时间" min-width="180">
          <template #default="{ row }">
            <span v-if="row.last_check_at">{{ formatTime(row.last_check_at) }}</span>
            <span v-else class="empty-tip">—</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <el-button
              type="primary"
              link
              size="small"
              :icon="RefreshRight"
              @click="handleHealthCheck(row)"
            >
              健康检查
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

    <!-- 删除确认对话框（自定义） -->
    <el-dialog
      v-model="deleteDialogVisible"
      title="删除确认"
      width="480px"
      :close-on-click-modal="false"
    >
      <div class="delete-dialog-body">
        <el-alert
          :title="`确定要删除运行时「${deletingRow?.name || ''}」吗？`"
          type="warning"
          show-icon
          :closable="false"
        />
        <div class="delete-options">
          <el-checkbox v-model="deleteOptions.physical">
            物理删除 runtime 目录（dsh_bin_path 所在目录）
          </el-checkbox>
          <el-checkbox v-model="deleteOptions.deleteHome">
            同时删除 DSH_HOME 目录
          </el-checkbox>
        </div>
        <p class="warning-tip">
          ⚠️ 勾选后相关目录及其所有内容将被永久删除，无法恢复。
        </p>
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
import { Search, RefreshRight, Delete } from '@element-plus/icons-vue'
import {
  getRuntimeList,
  detectRuntimes,
  healthCheckRuntime,
  deleteRuntime,
} from '@/api/runtime'

// ---- state ----
const loading = ref(false)
const detecting = ref(false)
const runtimeList = ref([])

const deleteDialogVisible = ref(false)
const deletingRow = ref(null)
const deleting = ref(false)
const deleteOptions = reactive({
  physical: false,
  deleteHome: false,
})

// ---- 常量 / 工具 ----
const STATUS_MAP = {
  healthy: { text: '健康', type: 'success' },
  warning: { text: '警告', type: 'warning' },
  error:   { text: '异常', type: 'danger' },
  unknown: { text: '未知', type: 'info' },
}

function statusTagType(status) {
  return STATUS_MAP[status]?.type || 'info'
}
function statusText(status) {
  return STATUS_MAP[status]?.text || status || '未知'
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

// ---- actions ----
async function fetchList() {
  loading.value = true
  try {
    const data = await getRuntimeList()
    runtimeList.value = Array.isArray(data) ? data : (data?.results || [])
  } catch (err) {
    // 拦截器已弹 ElMessage，这里仅重置
    runtimeList.value = []
  } finally {
    loading.value = false
  }
}

async function handleDetect() {
  detecting.value = true
  try {
    await detectRuntimes()
    ElMessage.success('环境检测完成')
    await fetchList()
  } catch (err) {
    // 拦截器已提示
  } finally {
    detecting.value = false
  }
}

async function handleHealthCheck(row) {
  try {
    const updated = await healthCheckRuntime(row.id)
    // 用后端返回的实例替换本地数据
    const idx = runtimeList.value.findIndex((r) => r.id === row.id)
    if (idx > -1 && updated) {
      runtimeList.value.splice(idx, 1, updated)
    }
    ElMessage.success('健康检查完成')
  } catch (err) {
    // 拦截器已提示
  }
}

function handleDelete(row) {
  deletingRow.value = row
  deleteOptions.physical = false
  deleteOptions.deleteHome = false
  deleteDialogVisible.value = true
}

async function confirmDelete() {
  if (!deletingRow.value) return
  deleting.value = true
  try {
    await deleteRuntime(deletingRow.value.id, {
      physical: deleteOptions.physical,
      delete_home: deleteOptions.deleteHome,
    })
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
.runtimes-page {
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

.name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.profile-tag {
  margin-right: 4px;
  margin-bottom: 4px;
}

.empty-tip {
  color: var(--do-fg-tertiary);
}

.delete-dialog-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.delete-options {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 0 4px;
}

.warning-tip {
  margin: 0;
  font-size: 12px;
  color: var(--do-warning);
}
</style>
