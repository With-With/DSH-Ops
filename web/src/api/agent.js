import request from './request'

/**
 * DSH 智能体调用日志相关 API（可选页 / 调试用）
 * 后端契约：前缀 /api/agent/
 */

// 获取智能体调用日志列表（分页）
export function getInvocationList(params = {}) {
  const query = new URLSearchParams()
  if (params.page) query.append('page', params.page)
  if (params.page_size) query.append('page_size', params.page_size)
  if (params.stage) query.append('stage', params.stage)
  if (params.status) query.append('status', params.status)
  const qs = query.toString()
  return request({
    url: `/agent/invocations/${qs ? '?' + qs : ''}`,
    method: 'get',
  })
}
