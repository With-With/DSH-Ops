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

/**
 * 触发任务集阶段（异步）
 * POST /tasksets/<id>/stages/ { stage: "extract" | "design" }
 * 返回 202 Accepted { id, status, current_stage }
 * 注意：axios 默认 2xx 都 resolve，202 不是错误，无需 validateStatus 配置
 * 超时 30s（提交动作本身很快，真正执行在后端异步）
 */
export function runStage(id, stage) {
  return request({
    url: `/tasksets/${id}/stages/`,
    method: 'post',
    data: { stage },
    timeout: 30000,
  })
}
