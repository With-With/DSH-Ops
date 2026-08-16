<template>
  <div class="ai-config-page">
    <el-card shadow="never" class="main-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">AI 配置</span>
          <el-button type="primary" :icon="Plus" @click="openCreate">新增配置</el-button>
        </div>
      </template>

      <el-alert
        class="intro-alert"
        type="info"
        :closable="false"
        show-icon
        title="平台 AI 阶段（A1-A4）的模型凭据入口"
        description="API Key 经 Fernet 加密落库，界面仅回显掩码。当前 DSH headless 默认继承用户 ~/.dsh 凭据；此配置为 gateway 直连 provider 预留，配置后可在各阶段调用前选择使用。"
      />

      <el-table v-loading="loading" :data="configList" stripe style="width: 100%">
        <template #empty>
          <el-empty description="暂无 AI 模型配置">
            <el-button type="primary" :icon="Plus" @click="openCreate">新增配置</el-button>
          </el-empty>
        </template>

        <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <el-icon v-if="row.is_default" color="#e6a23c" title="默认配置"><StarFilled /></el-icon>
            {{ row.name }}
          </template>
        </el-table-column>
        <el-table-column label="提供方" width="150">
          <template #default="{ row }">
            <el-tag :type="providerTagType(row.provider)" size="small" effect="light">
              {{ providerText(row.provider) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="model_name" label="模型" min-width="150" show-overflow-tooltip />
        <el-table-column prop="base_url" label="Base URL" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.base_url">{{ row.base_url }}</span>
            <span v-else class="empty-tip">-</span>
          </template>
        </el-table-column>
        <el-table-column label="API Key" width="150">
          <template #default="{ row }">
            <el-tooltip content="已加密存储，仅显示掩码" placement="top">
              <span class="key-mask"><el-icon><Lock /></el-icon> {{ row.api_key_mask || '未设置' }}</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="80" align="center">
          <template #default="{ row }">
            <el-switch v-model="row.enabled" @change="handleToggle(row)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="230" fixed="right" align="center">
          <template #default="{ row }">
            <el-button size="small" link type="success" :loading="testingId === row.id" @click="handleTest(row)">
              测试连通
            </el-button>
            <el-button size="small" link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="!row.is_default" size="small" link type="warning" @click="handleSetDefault(row)">
              设为默认
            </el-button>
            <el-button size="small" link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑配置' : '新增配置'"
      width="560px"
      :close-on-click-modal="false"
    >
      <el-form :model="form" label-width="100px">
        <el-form-item label="配置名称">
          <el-input v-model="form.name" placeholder="如 DeepSeek 主力" maxlength="64" />
        </el-form-item>
        <el-form-item label="提供方">
          <el-select v-model="form.provider" style="width: 100%">
            <el-option v-for="p in PROVIDERS" :key="p.value" :label="p.label" :value="p.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="Base URL">
          <el-input v-model="form.base_url" placeholder="https://api.deepseek.com/v1" />
        </el-form-item>
        <el-form-item label="模型名">
          <el-input v-model="form.model_name" placeholder="deepseek-chat" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input
            v-model="form.api_key"
            type="password"
            show-password
            :placeholder="editingId ? '留空表示不修改' : 'sk-...'"
          />
        </el-form-item>
        <el-form-item label="扩展参数">
          <el-input
            v-model="form.extra_raw"
            type="textarea"
            :rows="2"
            placeholder='{"temperature": 0.7, "max_tokens": 4096}'
          />
          <div v-if="extraError" class="extra-error">{{ extraError }}</div>
        </el-form-item>
        <el-form-item label="设为默认">
          <el-switch v-model="form.is_default" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">
          {{ submitting ? '保存中...' : '保存' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 测试结果 -->
    <el-dialog v-model="testResultVisible" title="连通性测试结果" width="420px">
      <div v-if="testResult">
        <el-result
          :icon="testResult.ok ? 'success' : 'error'"
          :title="testResult.ok ? '连通成功' : '连通失败'"
        >
          <template #sub-title>
            <p v-if="testResult.ok">延迟 {{ testResult.latency_ms }}ms（HTTP {{ testResult.status_code }}）</p>
            <p v-else class="test-error">{{ testResult.error }}</p>
            <p v-if="!testResult.ok" class="test-hint">
              排查建议：1) 检查 API Key 是否正确/未过期；2) 确认 base_url 是否含 /v1；
              3) 若为海外服务（如 OpenAI）需确认网络代理可达。
            </p>
          </template>
        </el-result>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Lock, StarFilled } from '@element-plus/icons-vue'
import {
  getAiConfigList,
  createAiConfig,
  updateAiConfig,
  deleteAiConfig,
  testAiConnection,
  setDefaultAiConfig,
} from '@/api/ai-config'

const PROVIDERS = [
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'volcark', label: '火山方舟 Ark' },
  { value: 'openai_compatible', label: 'OpenAI 兼容接口' },
  { value: 'ollama', label: 'Ollama' },
  { value: 'custom', label: '自定义' },
]

const loading = ref(false)
const configList = ref([])
const dialogVisible = ref(false)
const submitting = ref(false)
const editingId = ref(null)
const testingId = ref(null)
const testResult = ref(null)
const testResultVisible = ref(false)
const extraError = ref('')

const form = reactive({
  name: '', provider: 'deepseek', base_url: '', model_name: '',
  api_key: '', extra_raw: '', is_default: false, remark: '',
})

function providerTagType(p) {
  return { deepseek: 'primary', volcark: 'warning', openai_compatible: 'success', ollama: 'info', custom: 'info' }[p] || 'info'
}
function providerText(p) {
  return PROVIDERS.find(x => x.value === p)?.label || p
}

async function fetchList() {
  loading.value = true
  try {
    const data = await getAiConfigList()
    configList.value = Array.isArray(data) ? data : (data?.results || [])
  } catch (e) {
    configList.value = []
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  Object.assign(form, {
    name: '', provider: 'deepseek', base_url: '', model_name: '',
    api_key: '', extra_raw: '', is_default: configList.value.length === 0, remark: '',
  })
  extraError.value = ''
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  Object.assign(form, {
    name: row.name,
    provider: row.provider,
    base_url: row.base_url,
    model_name: row.model_name,
    api_key: '',
    extra_raw: row.extra && Object.keys(row.extra).length ? JSON.stringify(row.extra) : '',
    is_default: row.is_default,
    remark: row.remark || '',
  })
  extraError.value = ''
  dialogVisible.value = true
}

function parseExtra() {
  extraError.value = ''
  if (!form.extra_raw.trim()) return {}
  try {
    const obj = JSON.parse(form.extra_raw)
    if (typeof obj !== 'object' || Array.isArray(obj)) throw new Error('须为 JSON 对象')
    return obj
  } catch (e) {
    extraError.value = `扩展参数格式错误: ${e.message}`
    return null
  }
}

async function handleSubmit() {
  if (!form.name.trim()) return ElMessage.warning('请输入配置名称')
  if (!form.model_name.trim()) return ElMessage.warning('请输入模型名')
  const extra = parseExtra()
  if (extra === null) return

  submitting.value = true
  try {
    const payload = {
      name: form.name.trim(),
      provider: form.provider,
      base_url: form.base_url.trim(),
      model_name: form.model_name.trim(),
      is_default: form.is_default,
      extra,
      remark: form.remark,
    }
    if (form.api_key) payload.api_key = form.api_key
    if (editingId.value) {
      await updateAiConfig(editingId.value, payload)
      ElMessage.success('配置已更新')
    } else {
      await createAiConfig(payload)
      ElMessage.success('配置已创建')
    }
    dialogVisible.value = false
    fetchList()
  } catch (e) {
    // 拦截器已提示
  } finally {
    submitting.value = false
  }
}

async function handleToggle(row) {
  try {
    await updateAiConfig(row.id, { enabled: row.enabled })
    ElMessage.success(row.enabled ? '已启用' : '已停用')
  } catch (e) {
    fetchList()
  }
}

async function handleTest(row) {
  testingId.value = row.id
  try {
    const result = await testAiConnection(row.id)
    testResult.value = result
    testResultVisible.value = true
  } catch (e) {
    // 拦截器已提示
  } finally {
    testingId.value = null
  }
}

async function handleSetDefault(row) {
  try {
    await setDefaultAiConfig(row.id)
    ElMessage.success(`已将「${row.name}」设为默认`)
    fetchList()
  } catch (e) { /* 拦截器已提示 */ }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除配置「${row.name}」？（软删除，可恢复）`, '删除确认', { type: 'warning' })
    await deleteAiConfig(row.id)
    ElMessage.success('已删除')
    fetchList()
  } catch (e) { /* 取消 */ }
}

onMounted(fetchList)
</script>

<style scoped>
.ai-config-page {
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

.intro-alert {
  margin-bottom: 16px;
}

.empty-tip {
  color: var(--do-fg-tertiary);
}

.key-mask {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--do-fg-secondary);
}

.extra-error {
  color: var(--do-danger);
  font-size: 12px;
  margin-top: 4px;
}

.test-error {
  word-break: break-all;
  color: var(--do-danger);
}

.test-hint {
  margin-top: 6px;
  font-size: 12px;
  color: var(--do-fg-tertiary);
  text-align: left;
  line-height: 1.7;
}
</style>
