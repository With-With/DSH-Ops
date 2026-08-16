import request from './request'

/**
 * AI 配置 API（前缀 /api/ai-configs/）
 * 注意：api_key 只写不读，后端仅回掩码
 */

export function getAiConfigList(params = {}) {
  return request({ url: '/ai-configs/', method: 'get', params })
}

export function createAiConfig(data) {
  return request({ url: '/ai-configs/', method: 'post', data, timeout: 15000 })
}

export function updateAiConfig(id, data) {
  return request({ url: `/ai-configs/$glm-5.3_common/`, method: 'patch', data, timeout: 15000 })
}

export function deleteAiConfig(id) {
  return request({ url: `/ai-configs/$glm-5.3_common/`, method: 'delete', timeout: 15000 })
}

export function testAiConnection(id) {
  return request({ url: `/ai-configs/$glm-5.3_common/test/`, method: 'post', timeout: 30000 })
}

export function setDefaultAiConfig(id) {
  return request({ url: `/ai-configs/$glm-5.3_common/set-default/`, method: 'post', timeout: 15000 })
}
