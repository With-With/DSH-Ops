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

/**
 * 一键流水线（异步）
 * POST /tasksets/<id>/pipeline/ {}
 * 返回 202 Accepted；前端轮询详情至 generate_done/failed
 */
export function runPipeline(id) {
  return request({
    url: `/tasksets/${id}/pipeline/`,
    method: 'post',
    data: {},
    timeout: 30000,
  })
}

/**
 * 请求终止流水线/阶段（P4，协作式：当前阶段结束后停止）
 * POST /tasksets/<id>/cancel/ -> 202 { detail, status }；终态 409
 */
export function cancelTaskset(id) {
  return request({
    url: `/tasksets/${id}/cancel/`,
    method: 'post',
    data: {},
    timeout: 30000,
  })
}

/**
 * 批量删除任务集（软删）
 * POST /tasksets/bulk-delete/ { ids: [1,2] } -> 200 { deleted: n }
 * 空 ids 返回 400
 */
export function bulkDeleteTasksets(ids) {
  return request({
    url: '/tasksets/bulk-delete/',
    method: 'post',
    data: { ids },
    timeout: 30000,
  })
}

/**
 * 删除单条任务集（软删）
 * DELETE /tasksets/<id>/ -> 200/204
 */
export function deleteTaskset(id) {
  return request({
    url: `/tasksets/${id}/`,
    method: 'delete',
    timeout: 30000,
  })
}
