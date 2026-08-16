/**
 * 通用格式化工具函数
 */

// 补零
function pad(n) {
  return String(n).padStart(2, '0')
}

/**
 * 格式化 ISO 时间字符串为 YYYY-MM-DD HH:mm:ss
 * @param {string|Date} iso - ISO 时间字符串或 Date 对象
 * @returns {string} 格式化后的时间，输入无效时返回原值
 */
export function formatTime(iso) {
  if (!iso) return ''
  const d = iso instanceof Date ? iso : new Date(iso)
  if (isNaN(d.getTime())) return String(iso)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

/**
 * 格式化耗时（毫秒）为友好显示
 * @param {number} ms - 毫秒数
 * @returns {string} 如 "1.23s"、"45.6s"、"2m 30s"
 */
export function formatDuration(ms) {
  if (ms == null || isNaN(ms)) return '—'
  if (ms < 1000) return `${ms}ms`
  const totalSec = ms / 1000
  if (totalSec < 60) return `${totalSec.toFixed(totalSec < 10 ? 2 : 1)}s`
  const min = Math.floor(totalSec / 60)
  const sec = Math.floor(totalSec % 60)
  return `${min}m ${sec}s`
}

/**
 * 截断字符串并添加省略号
 * @param {string} str - 原字符串
 * @param {number} len - 最大长度
 * @returns {string}
 */
export function truncate(str, len = 8) {
  if (!str) return ''
  const s = String(str)
  return s.length > len ? s.slice(0, len) + '…' : s
}
