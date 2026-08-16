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
