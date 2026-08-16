import request from './request'

/**
 * DSH 运行时管理相关 API
 * 后端契约：Django + DRF，前缀 /api
 */

// 获取运行时列表
export function getRuntimeList() {
  return request({
    url: '/runtimes/',
    method: 'get',
  })
}

// 探测环境（自动发现本机 DSH 运行时；含子进程调用，放宽超时）
export function detectRuntimes() {
  return request({
    url: '/runtimes/detect/',
    method: 'post',
    timeout: 45000,
  })
}

// 对指定运行时执行健康检查
export function healthCheckRuntime(id) {
  return request({
    url: `/runtimes/${id}/health_check/`,
    method: 'post',
    timeout: 45000,
  })
}

// 删除运行时
// physical: 是否物理删除 runtime 目录
// delete_home: 是否同时删除 DSH_HOME
export function deleteRuntime(id, { physical = false, delete_home = false } = {}) {
  const params = new URLSearchParams()
  if (physical) params.append('physical', 'true')
  if (delete_home) params.append('delete_home', 'true')
  const query = params.toString()

  return request({
    url: `/runtimes/${id}/${query ? '?' + query : ''}`,
    method: 'delete',
  })
}
