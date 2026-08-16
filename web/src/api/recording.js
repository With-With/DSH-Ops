import request from './request'

/**
 * 录制脚本管理相关 API
 * 后端契约：Django + DRF，前缀 /api/recordings/
 */

// 获取录制脚本列表（分页）
export function getRecordingList(params = {}) {
  const query = new URLSearchParams()
  if (params.page) query.append('page', params.page)
  if (params.page_size) query.append('page_size', params.page_size)
  const qs = query.toString()
  return request({
    url: `/recordings/${qs ? '?' + qs : ''}`,
    method: 'get',
  })
}

// 获取单个录制脚本详情（含 normalized_content 和 actions）
export function getRecordingDetail(id) {
  return request({
    url: `/recordings/${id}/`,
    method: 'get',
  })
}

// 提交新的录制脚本
export function createRecording({ name, content }) {
  return request({
    url: '/recordings/',
    method: 'post',
    data: { name, content },
  })
}

// 软删除录制脚本
export function deleteRecording(id) {
  return request({
    url: `/recordings/${id}/`,
    method: 'delete',
  })
}

// 批量删除（逐条调用单条删除，返回成功数）
export async function deleteRecordings(ids) {
  if (!Array.isArray(ids) || ids.length === 0) return 0
  const results = await Promise.allSettled(
    ids.map((id) => deleteRecording(id))
  )
  const successCount = results.filter((r) => r.status === 'fulfilled').length
  return successCount
}

// ---- P4：codegen 浏览器录制 ----

// 开始录制（打开浏览器）
export function startCodegen({ name = '', start_url = '' }) {
  return request({
    url: '/recordings/codegen/start/',
    method: 'post',
    data: { name, start_url },
    timeout: 30000,
  })
}

// 录制会话状态
export function getCodegenStatus() {
  return request({
    url: '/recordings/codegen/status/',
    method: 'get',
    timeout: 15000,
  })
}

// 结束录制并保存（auto_analyze: 是否自动 AI 重组）
export function stopCodegen({ session_id = '', auto_analyze = false }) {
  return request({
    url: '/recordings/codegen/stop/',
    method: 'post',
    data: { session_id, auto_analyze },
    timeout: 30000,
  })
}

// ---- P4：AI 重组（标准化脚本） ----

// 触发 AI 重组（异步 202）
export function normalizeRecording(id) {
  return request({
    url: `/recordings/${id}/normalize/`,
    method: 'post',
    data: {},
    timeout: 30000,
  })
}
