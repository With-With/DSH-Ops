import request from './request'

/**
 * 元素资产管理相关 API
 * 后端契约：Django + DRF，前缀 /api/assets/
 */

// ===== Pages =====

// 获取页面列表
export function getPageList(params = {}) {
  const query = new URLSearchParams()
  if (params.page) query.append('page', params.page)
  if (params.page_size) query.append('page_size', params.page_size)
  const qs = query.toString()
  return request({
    url: `/assets/pages/${qs ? '?' + qs : ''}`,
    method: 'get',
  })
}

// 新建页面
export function createPage({ name, url_pattern, notes }) {
  return request({
    url: '/assets/pages/',
    method: 'post',
    data: { name, url_pattern, notes },
  })
}

// 删除页面（软删）
export function deletePage(id) {
  return request({
    url: `/assets/pages/${id}/`,
    method: 'delete',
  })
}

// ===== Elements =====

// 获取元素列表（支持 page_id 筛选和 search 搜索）
export function getElementList(params = {}) {
  const query = new URLSearchParams()
  if (params.page_id) query.append('page_id', params.page_id)
  if (params.search) query.append('search', params.search)
  if (params.page) query.append('page', params.page)
  if (params.page_size) query.append('page_size', params.page_size)
  const qs = query.toString()
  return request({
    url: `/assets/elements/${qs ? '?' + qs : ''}`,
    method: 'get',
  })
}

// 新建元素（含候选定位器列表）
export function createElement({ page_id, name, role, candidates, snapshot_hash, notes }) {
  const data = { page_id, name, role, candidates }
  if (snapshot_hash !== undefined && snapshot_hash !== null) {
    data.snapshot_hash = snapshot_hash
  }
  if (notes !== undefined && notes !== null) {
    data.notes = notes
  }
  return request({
    url: '/assets/elements/',
    method: 'post',
    data,
  })
}

// 删除元素（软删）
export function deleteElement(id) {
  return request({
    url: `/assets/elements/${id}/`,
    method: 'delete',
  })
}

// ===== Query（search-first 查询测试） =====

// 智能查询元素定位器匹配度
export function queryElement({ page_url, name, role, snapshot_hash }) {
  const data = { page_url, name, role }
  if (snapshot_hash !== undefined && snapshot_hash !== null) {
    data.snapshot_hash = snapshot_hash
  }
  return request({
    url: '/assets/elements/query/',
    method: 'post',
    data,
  })
}
