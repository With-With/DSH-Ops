import request from './request'

/**
 * AI 配置 API（前缀 /api/ai-configs/）
 * 注意：api_key 只写不读，后端仅回掩码。
 * 注意：URL 用字符串拼接（避免模板字面量污染），id 为数字。
 */

export function getAiConfigList(params = {}) {
  return request({ url: '/ai-configs/', method: 'get', params })
}

export function createAiConfig(data) {
  return request({ url: '/ai-configs/', method: 'post', data, timeout: 15000 })
}

export function updateAiConfig(id, data) {
  return request({ url: '/ai-configs/' + id + '/', method: 'patch', data, timeout: 15000 })
}

export function deleteAiConfig(id) {
  return request({ url: '/ai-configs/' + id + '/', method: 'delete', timeout: 15000 })
}

export function testAiConnection(id) {
  return request({ url: '/ai-configs/' + id + '/test/', method: 'post', timeout: 30000 })
}

export function setDefaultAiConfig(id) {
  return request({ url: '/ai-configs/' + id + '/set-default/', method: 'post', timeout: 15000 })
}
