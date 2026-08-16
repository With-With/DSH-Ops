import request from './request'

/**
 * 用例管理 API（前缀 /api/testcases/）
 */

export function getTestCaseList(params = {}) {
  return request({ url: '/testcases/', method: 'get', params })
}

export function deleteTestCase(id) {
  return request({ url: '/testcases/' + id + '/', method: 'delete', timeout: 15000 })
}

export function bulkDeleteTestCases(ids) {
  return request({ url: '/testcases/bulk-delete/', method: 'post', data: { ids }, timeout: 30000 })
}
