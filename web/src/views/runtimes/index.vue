<template>
  <div class="runtimes-page">
    <!-- 页面标题 -->
    <div class="page-title">
      <el-icon :size="22"><Setting /></el-icon>
      <span>配置中心</span>
    </div>

    <!-- DSH 环境大卡片 -->
    <el-card shadow="hover" class="dsh-card">
      <template #header>
        <div class="card-header">
          <span class="card-title"><el-icon><Cpu /></el-icon> DSH 环境</span>
          <div class="header-actions">
            <a
              href="https://github.com/liu-zq/dsh"
              target="_blank"
              rel="noopener noreferrer"
              class="github-link"
            >
              <el-icon><Link /></el-icon>
              <span>GitHub</span>
            </a>
            <el-button
              type="primary"
              :icon="Search"
              :loading="detecting"
              @click="handleDetect"
            >
              {{ detecting ? '检测中...' : '检测环境' }}
            </el-button>
            <el-button :icon="Refresh" circle @click="refreshAll" />
          </div>
        </div>
      </template>

      <div v-if="runtimeList.length" class="dsh-card-body">
        <div v-for="row in runtimeList" :key="row.id" class="dsh-env-item">
          <div class="dsh-main">
            <span class="dsh-name">{{ row.name }}</span>
            <el-tag v-if="row.is_default" type="primary" size="small" effect="light">默认</el-tag>
            <el-tag :type="statusTagType(row.status)" effect="light">
              {{ statusText(row.status) }}
            </el-tag>
          </div>
          <div class="dsh-meta">
            <span class="meta-item">版本：<b>{{ row.version || '—' }}</b></span>
            <span class="meta-item">来源：<b>{{ row.source || '—' }}</b></span>
            <span class="meta-item">DSH_HOME：<b class="mono">{{ row.home_dir || '—' }}</b></span>
            <span v-if="row.node_version" class="meta-item">Node：{{ row.node_version }}</span>
            <span v-if="row.profiles && row.profiles.length" class="meta-item">
              Profiles：
              <el-tag
                v-for="p in row.profiles"
                :key="p"
                size="small"
                type="info"
                effect="plain"
                class="profile-tag"
              >{{ p }}</el-tag>
            </span>
            <span v-if="row.last_check_at" class="meta-item">
              检查于 {{ formatTime(row.last_check_at) }}
            </span>
          </div>
          <div class="dsh-actions">
            <el-button
              type="primary"
              plain
              size="small"
              :icon="RefreshRight"
              :loading="healthCheckingId === row.id"
              @click="handleHealthCheck(row)"
            >
              健康检查
            </el-button>
            <el-button
              type="danger"
              plain
              size="small"
              :icon="Delete"
              @click="openDeleteDialog(row)"
            >
              删除
            </el-button>
          </div>
        </div>
      </div>
      <el-empty
        v-else
        description="尚未检测，点击【检测环境】开始发现本机 DSH 运行时"
        :image-size="90"
      >
        <el-button type="primary" :icon="Search" @click="handleDetect">检测环境</el-button>
      </el-empty>
    </el-card>

    <!-- 组件卡片网格 -->
    <el-card shadow="never" class="components-card">
      <template #header>
        <div class="card-header">
          <span class="card-title"><el-icon><Grid /></el-icon> 组件管理</span>
          <div class="header-actions">
            <el-text type="info" size="small">playwright / selenium / 系统浏览器 / chromium 通道</el-text>
            <el-button
              type="primary"
              plain
              size="small"
              :icon="Search"
              :loading="detectingComponents"
              @click="handleDetectComponents"
            >
              {{ detectingComponents ? '检测中...' : '检测' }}
            </el-button>
          </div>
        </div>
      </template>

      <div v-loading="componentsLoading" class="component-grid">
        <el-card
          v-for="comp in componentList"
          :key="comp.key"
          shadow="hover"
          class="component-card"
        >
          <div class="comp-head">
            <el-icon :size="22" :color="comp.installed ? '#67c23a' : '#909399'">
              <component :is="compIcon(comp.key)" />
            </el-icon>
            <span class="comp-name">{{ comp.name }}</span>
            <el-tag
              :type="comp.installed ? 'success' : 'info'"
              size="small"
              effect="light"
            >
              {{ comp.installed ? '已验证' : '未安装' }}
            </el-tag>
            <el-tag
              v-if="comp.op_status === 'running'"
              type="primary"
              size="small"
              effect="dark"
            >{{ comp.op === 'install' ? '安装中…' : '卸载中…' }}</el-tag>
          </div>
          <div class="comp-detail">
            <div v-if="comp.version" class="comp-version">v{{ comp.version }}</div>
            <div class="comp-desc">{{ comp.detail }}</div>
            <div v-if="comp.op_detail && comp.op_status === 'done'" class="comp-op-result">{{ comp.op_detail }}</div>
          </div>
          <div class="comp-actions">
            <el-button
              v-if="comp.installed"
              size="small"
              disabled
            >
              已安装
            </el-button>
            <el-button
              v-else-if="comp.actions.includes('install')"
              type="primary"
              size="small"
              :icon="Download"
              :loading="comp.op_status === 'running' && comp.op === 'install'"
              :disabled="comp.op_status === 'running'"
              @click="handleInstall(comp)"
            >
              安装
            </el-button>
            <el-button
              v-if="comp.actions.includes('delete')"
              type="danger"
              size="small"
              :icon="Delete"
              :loading="comp.op_status === 'running' && comp.op === 'delete'"
              :disabled="comp.op_status === 'running'"
              @click="handleDeleteComponent(comp)"
            >
              删除
            </el-button>
            <el-tooltip v-if="comp.install_hint && !comp.actions.includes('install')" :content="comp.install_hint" placement="top">
              <el-text type="info" size="small" class="hint-text">{{ comp.install_hint }}</el-text>
            </el-tooltip>
          </div>
        </el-card>
        <el-empty v-if="!componentsLoading && componentList.length === 0" description="无组件数据" :image-size="60" />
      </div>
    </el-card>

    <!-- 删除确认对话框（DSH 环境） -->
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
        <p class="warning-tip">⚠️ 勾选后相关目录及其所有内容将被永久删除，无法恢复。</p>
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
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Search, RefreshRight, Refresh, Delete, Cpu, Grid, Download, Setting,
  Monitor, ChromeFilled, Link, Picture,
} from '@element-plus/icons-vue'
import {
  getRuntimeList,
  detectRuntimes,
  healthCheckRuntime,
  deleteRuntime,
  getComponents,
  detectComponents,
  installComponent,
  deleteComponent,
} from '@/api/runtime'

// ---- DSH 环境 ----
const loading = ref(false)
const detecting = ref(false)
const runtimeList = ref([])
const healthCheckingId = ref(null)

const deleteDialogVisible = ref(false)
const deletingRow = ref(null)
const deleting = ref(false)
const deleteOptions = reactive({ physical: false, deleteHome: false })

// ---- 组件 ----
const componentsLoading = ref(false)
const componentList = ref([])
const detectingComponents = ref(false)

const STATUS_MAP = {
  healthy: { text: '健康', type: 'success' },
  warning: { text: '警告', type: 'warning' },
  error:   { text: '异常', type: 'danger' },
  unknown: { text: '未知', type: 'info' },
}

function statusTagType(status) { return STATUS_MAP[status]?.type || 'info' }
function statusText(status) { return STATUS_MAP[status]?.text || status || '未知' }

function compIcon(key) {
  if (key === 'playwright') return Link
  if (key === 'selenium') return Link
  if (key === 'browser-msedge') return Monitor
  if (key === 'browser-chrome') return ChromeFilled
  if (key === 'pw-chromium') return Picture
  return Grid
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
    runtimeList.value = []
  } finally {
    loading.value = false
  }
}

async function handleDetect() {
  detecting.value = true
  try {
    await detectRuntimes()
    ElMessage.success('检测完成')
    await Promise.all([fetchList(), fetchComponents()])
  } catch (err) {
    // 拦截器已提示
  } finally {
    detecting.value = false
  }
}

async function handleHealthCheck(row) {
  healthCheckingId.value = row.id
  try {
    const result = await healthCheckRuntime(row.id)
    if (result.passed) {
      const profile = result.detail?.profile_used
      ElMessage.success(profile ? `健康检查通过（${profile}）` : '健康检查通过')
    } else {
      ElMessage.error(`健康检查失败：${result.error || '未知原因'}`)
    }
  } catch (err) {
    // 拦截器已提示
  } finally {
    healthCheckingId.value = null
  }
}

function openDeleteDialog(row) {
  deletingRow.value = row
  deleteOptions.physical = false
  deleteOptions.deleteHome = false
  deleteDialogVisible.value = true
}

async function confirmDelete() {
  deleting.value = true
  try {
    await deleteRuntime(deletingRow.value.id, {
      confirm_physical: deleteOptions.physical,
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

// ---- 组件 ----
async function fetchComponents() {
  componentsLoading.value = true
  try {
    const data = await getComponents()
    componentList.value = Array.isArray(data) ? data : (data?.results || [])
  } catch (err) {
    componentList.value = []
  } finally {
    componentsLoading.value = false
  }
}

async function handleDetectComponents() {
  detectingComponents.value = true
  try {
    await detectComponents()
    ElMessage.success('组件检测完成')
    await fetchComponents()
  } catch (err) {
    // 拦截器已提示
  } finally {
    detectingComponents.value = false
  }
}

async function handleInstall(comp) {
  try {
    await installComponent(comp.key)
    ElMessage.info(`「${comp.name}」安装任务已启动（${comp.install_hint}）`)
    setTimeout(fetchComponents, 2000)
    startComponentPolling()
  } catch (err) { /* 拦截器已提示 */ }
}

async function handleDeleteComponent(comp) {
  try {
    await ElMessageBox.confirm(`确定删除组件「${comp.name}」？`, '删除组件', {
      type: 'warning',
      confirmButtonText: '删除',
    })
    await deleteComponent(comp.key)
    ElMessage.info(`「${comp.name}」卸载任务已启动`)
    setTimeout(fetchComponents, 2000)
    startComponentPolling()
  } catch (e) { /* 取消 */ }
}

// 有进行中任务时 3s 轮询组件状态
let compTimer = null
function startComponentPolling() {
  if (compTimer) return
  compTimer = setInterval(async () => {
    await fetchComponents()
    const anyRunning = componentList.value.some((c) => c.op_status === 'running')
    if (!anyRunning) {
      clearInterval(compTimer)
      compTimer = null
    }
  }, 3000)
}

async function refreshAll() {
  await Promise.all([fetchList(), fetchComponents()])
}

onMounted(() => {
  fetchList()
  fetchComponents()
})

onBeforeUnmount(() => {
  if (compTimer) {
    clearInterval(compTimer)
    compTimer = null
  }
})
</script>

<style scoped>
.runtimes-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
  overflow: auto;
  padding-right: 2px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 20px;
  font-weight: 700;
  color: var(--do-fg);
  padding: 2px 4px 4px;
}

.dsh-card, .components-card {
  border-radius: 8px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 16px;
  font-weight: 600;
  color: var(--do-fg);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.github-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--do-fg-secondary);
  font-size: 13px;
  text-decoration: none;
  transition: color 0.2s;
}

.github-link:hover {
  color: var(--do-primary);
}

.dsh-env-item {
  padding: 14px 16px;
  border: 1px solid var(--do-border-light, #e4e7ed);
  border-radius: 8px;
  margin-bottom: 12px;
  background: var(--do-bg-page, #fff);
}

.dsh-env-item:last-child { margin-bottom: 0; }

.dsh-main {
  display: flex;
  align-items: center;
  gap: 10px;
}

.dsh-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--do-fg);
}

.dsh-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 20px;
  margin-top: 10px;
  font-size: 13px;
  color: var(--do-fg-secondary);
}

.meta-item b { color: var(--do-fg); font-weight: 600; }
.meta-item .mono { font-family: 'Consolas', 'Monaco', monospace; font-size: 12px; }

.dsh-actions {
  margin-top: 12px;
  display: flex;
  gap: 8px;
}

.profile-tag { margin-right: 4px; }

.component-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
  min-height: 100px;
}

.component-card {
  border-radius: 8px;
}

.comp-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.comp-name {
  flex: 1;
  font-size: 14px;
  font-weight: 600;
  color: var(--do-fg);
}

.comp-detail {
  margin-top: 10px;
  font-size: 12.5px;
  color: var(--do-fg-secondary);
  line-height: 1.6;
}

.comp-version {
  font-family: 'Consolas', 'Monaco', monospace;
  color: var(--do-success);
  margin-bottom: 4px;
}

.comp-op-result {
  margin-top: 6px;
  color: var(--do-primary);
  font-size: 12px;
}

.comp-actions {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.hint-text {
  line-height: 1.5;
}

.delete-options {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.warning-tip {
  margin: 12px 0 0 0;
  font-size: 12.5px;
  color: var(--do-danger);
}
</style>
