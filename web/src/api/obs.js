import request from './request'

/**
 * 观测中心 API
 * 后端契约：前缀 /api/obs/
 */

// 总览统计
export function getOverview() {
  return request({
    url: '/obs/overview/',
    method: 'get',
    timeout: 15000,
  })
}

// 最近活动流
export function getActivity(limit = 50) {
  return request({
    url: `/obs/activity/?limit=${limit}`,
    method: 'get',
    timeout: 15000,
  })
}
