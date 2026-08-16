<template>
  <div class="obs-page">
    <el-card shadow="never" class="main-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">观测中心</span>
          <div class="header-actions">
            <el-switch v-model="autoRefresh" active-text="自动刷新(3s)" size="small" />
            <el-button :icon="Refresh" circle size="small" @click="fetchAll" />
          </div>
        </div>
      </template>

      <!-- 统计卡 -->
      <div v-loading="loading" class="stat-grid">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">Agent 调用</div>
          <div class="stat-value">{{ overview?.invocations?.total ?? '—' }}</div>
          <div class="stat-sub">
            真实 {{ overview?.invocations?.total - (overview?.invocations?.mock_count ?? 0) }} ·
            mock {{ overview?.invocations?.mock_count ?? 0 }} ·
            平均 {{ formatDuration(overview?.invocations?.avg_duration_ms) }}
          </div>
        </el-card>
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">回放</div>
          <div class="stat-value">{{ overview?.replays?.total ?? '—' }}</div>
          <div class="stat-sub">平均 {{ formatDuration(overview?.replays?.avg_duration_ms) }}</div>
        </el-card>
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">阶段作业</div>
          <div class="stat-value">{{ overview?.stages?.total ?? '—' }}</div>
          <div class="stat-sub">
            <template v-if="overview?.stages?.by_stage">
              <span v-for="(v, k) in overview.stages.by_stage" :key="k" class="stat-chip">{{ k }}:{{ v }}</span>
            </template>
          </div>
        </el-card>
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">生成通过率</div>
          <div class="stat-value">{{ overview?.generated?.pass_rate != null ? overview.generated.pass_rate + '%' : '—' }}</div>
          <div class="stat-sub">共 {{ overview?.generated?.total ?? 0 }} 次生成</div>
        </el-card>
      </div>

      <!-- 调用分布 -->
      <div class="chart-row">
        <el-card shadow="never" class="chart-card">
          <template #header><span class="card-title">Agent 调用按阶段</span></template>
          <div v-if="stageBars.length" class="bar-list">
            <div v-for="b in stageBars" :key="b.key" class="bar-row">
              <span class="bar-label">{{ b.key }}</span>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: b.pct + '%' }"></div>
              </div>
              <span class="bar-value">{{ b.value }}</span>
            </div>
          </div>
          <el-empty v-else description="暂无数据" :image-size="50" />
        </el-card>
        <el-card shadow="never" class="chart-card">
          <template #header><span class="card-title">调用状态分布</span></template>
          <div v-if="statusBars.length" class="bar-list">
            <div v-for="b in statusBars" :key="b.key" class="bar-row">
              <span class="bar-label">{{ b.key }}</span>
              <div class="bar-track">
                <div class="bar-fill" :class="statusColorClass(b.key)" :style="{ width: b.pct + '%' }"></div>
              </div>
              <span class="bar-value">{{ b.value }}</span>
            </div>
          </div>
          <el-empty v-else description="暂无数据" :image-size="50" />
        </el-card>
      </div>

      <!-- 活动流 -->
      <div class="activity-section">
        <h4 class="section-title">最近活动</h4>
        <el-table :data="activity" stripe size="small" style="width: 100%">
          <el-table-column label="时间" width="180">
            <template #default="{ row }">{{ formatTime(row.at) }}</template>
          </el-table-column>
          <el-table-column label="类型" width="110">
            <template #default="{ row }">
              <el-tag :type="typeTagType(row.type)" size="small" effect="light">{{ typeText(row.type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="阶段" width="100">
            <template #default="{ row }">{{ row.stage || '—' }}</template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)" size="small" effect="plain">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="detail" label="详情" min-width="260" show-overflow-tooltip />
          <el-table-column label="引用" width="90" align="center">
            <template #default="{ row }">#{{ row.ref_id }}</template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!loading && activity.length === 0" description="暂无活动" :image-size="50" />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { getOverview, getActivity } from '@/api/obs'
import { formatTime, formatDuration } from '@/utils/format'

const loading = ref(false)
const overview = ref(null)
const activity = ref([])
const autoRefresh = ref(false)

let timer = null

function typeTagType(t) {
  return { invocation: 'purple', replay: 'cyan', stage: 'primary', generated: 'success' }[t] || 'info'
}
function typeText(t) {
  return { invocation: '调用', replay: '回放', stage: '阶段', generated: '生成' }[t] || t
}
function statusTagType(s) {
  const m = { success: 'success', pass: 'success', running: 'primary', failed: 'danger', fail: 'danger', timeout: 'warning', error: 'danger', replay_done: 'success', extract_done: 'success', design_done: 'success', review_done: 'success', generate_done: 'success' }
  return m[s] || 'info'
}
function statusColorClass(s) {
  const m = { success: 'ok', pass: 'ok', failed: 'bad', fail: 'bad', timeout: 'warn', error: 'bad', running: 'run' }
  return m[s] || ''
}

const stageBars = computed(() => {
  const m = overview.value?.invocations?.by_stage || {}
  const entries = Object.entries(m)
  const max = Math.max(1, ...entries.map(([, v]) => v))
  return entries.map(([k, v]) => ({ key: k, value: v, pct: Math.round((v / max) * 100) }))
})

const statusBars = computed(() => {
  const m = overview.value?.invocations?.by_status || {}
  const entries = Object.entries(m)
  const max = Math.max(1, ...entries.map(([, v]) => v))
  return entries.map(([k, v]) => ({ key: k, value: v, pct: Math.round((v / max) * 100) }))
})

async function fetchAll() {
  loading.value = true
  try {
    const [ov, act] = await Promise.all([getOverview(), getActivity(50)])
    overview.value = ov
    activity.value = Array.isArray(act) ? act : (act?.results || [])
  } catch (err) {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchAll()
  timer = setInterval(() => {
    if (autoRefresh.value) fetchAll()
  }, 3000)
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.obs-page {
  height: 100%;
}

.main-card {
  border-radius: 8px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--do-fg);
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.stat-card {
  border-radius: 8px;
}

.stat-label {
  font-size: 13px;
  color: var(--do-fg-tertiary);
}

.stat-value {
  font-size: 30px;
  font-weight: 700;
  margin: 6px 0;
  color: var(--do-fg);
  font-variant-numeric: tabular-nums;
}

.stat-sub {
  font-size: 12px;
  color: var(--do-fg-secondary);
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.stat-chip {
  background: var(--do-bg);
  border: 1px solid var(--do-border, #e4e7ed);
  border-radius: 4px;
  padding: 1px 6px;
  font-size: 11px;
}

.chart-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-top: 16px;
}

.chart-card {
  border-radius: 8px;
}

.bar-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.bar-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.bar-label {
  width: 110px;
  font-size: 12.5px;
  color: var(--do-fg-secondary);
  font-family: 'Consolas', 'Monaco', monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.bar-track {
  flex: 1;
  height: 14px;
  background: var(--do-bg);
  border-radius: 4px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background: var(--do-primary);
  border-radius: 4px;
  transition: width 0.4s ease;
}

.bar-fill.ok { background: #67c23a; }
.bar-fill.bad { background: #f56c6c; }
.bar-fill.warn { background: #e6a23c; }
.bar-fill.run { background: #409eff; }

.bar-value {
  width: 36px;
  text-align: right;
  font-size: 12.5px;
  color: var(--do-fg);
  font-variant-numeric: tabular-nums;
}

.activity-section {
  margin-top: 24px;
}

.section-title {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--do-fg);
}
</style>
