import request from './request'

/**
 * 回放管理相关 API
 * 后端契约：Django + DRF，前缀 /api/replays/
 */

// 获取回放记录列表（分页）
export function getReplayList(params = {}) {
  const query = new URLSearchParams()
  if (params.page) query.append('page', params.page)
  if (params.page_size) query.append('page_size', params.page_size)
  if (params.recording_id) query.append('recording_id', params.recording_id)
  const qs = query.toString()
  return request({
    url: `/replays/${qs ? '?' + qs : ''}`,
    method: 'get',
  })
}

// 获取单个回放详情
export function getReplayDetail(id) {
  return request({
    url: `/replays/${id}/`,
    method: 'get',
  })
}

// 开始回放（同步执行，30~90s，超时设 120s）
export function startReplay(recordingId) {
  return request({
    url: '/replays/',
    method: 'post',
    data: { recording_id: recordingId },
    timeout: 120000,
  })
}

// 下载回放 trace 文件
// 注意：返回文件流，直接用 window.open 访问 trace_url 即可
export function getReplayTraceUrl(id) {
  return `/api/replays/${id}/trace/download/`
}
