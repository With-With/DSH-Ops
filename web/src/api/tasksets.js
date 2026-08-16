import request from './request'

/**
 * 任务集管理相关 API
 * 后端契约：Django + DRF，前缀 /api/tasksets/
 */

// 获取任务集列表（分页）
export function getTasksetList(params = {}) {
  const query = new URLSearchParams()
  if (params.page) query.append('page', params.page)
  if (params.page_size) query.append('page_size', params.page_size)
  const qs = query.toString()
  return request({
    url: `/tasksets/${qs ? '?' + qs : ''}`,
    method: 'get',
  })
}

// 获取任务集详情（含 stage_jobs）
export function getTasksetDetail(id) {
  return request({
    url: `/tasksets/${id}/`,
    method: 'get',
  })
}

// 新建任务集（同步执行回放，超时 120s）
export function createTaskset({ name, recording_id }) {
  return request({
    url: '/tasksets/',
    method: 'post',
    data: { name, recording_id },
    timeout: 120000,
  })
}
