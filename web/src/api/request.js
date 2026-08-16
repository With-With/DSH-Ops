import axios from 'axios'
import { ElMessage } from 'element-plus'

// 创建 axios 实例
const request = axios.create({
  baseURL: '/api',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器
request.interceptors.request.use(
  (config) => {
    // 后续可在此处加 token、请求头等
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器 —— 统一错误提示
request.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    const status = error?.response?.status
    const data = error?.response?.data
    let message = error?.message || '请求失败'

    if (data?.detail) {
      message = data.detail
    } else if (data?.message) {
      message = data.message
    } else if (typeof data === 'string' && data) {
      message = data
    }

    switch (status) {
      case 400:
      case 401:
      case 403:
      case 404:
      case 500:
      case 502:
      case 503:
      case 504:
        message = `[${status}] ${message}`
        break
      default:
        if (!status) {
          message = `网络错误：${message}（后端可能未启动）`
        }
    }

    ElMessage.error(message)

    return Promise.reject(error)
  }
)

export default request
