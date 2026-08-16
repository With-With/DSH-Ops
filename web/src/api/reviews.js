import request from './request'

/**
 * 评审中心相关 API
 * 后端契约：Django + DRF，前缀 /api/reviews/
 */

// 获取草案列表（分页，支持 kind / status 筛选）
export function getDraftList(params = {}) {
  const query = new URLSearchParams()
  if (params.kind) query.append('kind', params.kind)
  if (params.status) query.append('status', params.status)
  if (params.page) query.append('page', params.page)
  if (params.page_size) query.append('page_size', params.page_size)
  const qs = query.toString()
  return request({
    url: `/reviews/drafts/${qs ? '?' + qs : ''}`,
    method: 'get',
  })
}

// 获取单个草案详情
export function getDraftDetail(id) {
  return request({
    url: `/reviews/drafts/${id}/`,
    method: 'get',
  })
}

// 通过草案（可选 note）
export function approveDraft(id, note) {
  const data = note != null ? { note } : {}
  return request({
    url: `/reviews/drafts/${id}/approve/`,
    method: 'post',
    data,
  })
}

// 驳回草案（可选 note）
export function rejectDraft(id, note) {
  const data = note != null ? { note } : {}
  return request({
    url: `/reviews/drafts/${id}/reject/`,
    method: 'post',
    data,
  })
}
