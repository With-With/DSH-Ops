/**
 * 通用轮询器封装
 *
 * 用法：
 *   const poller = createPoller({
 *     fetchFn: () => getTasksetDetail(id),
 *     interval: 3000,
 *     isDone: (data) => data.status !== 'extracting',
 *     onDone: (data) => { ... },
 *     onError: (err) => { ... },
 *   })
 *   poller.start()
 *   // 组件卸载时：poller.stop()
 */

export function createPoller({ fetchFn, interval = 3000, isDone, onDone, onError, onTick }) {
  let timer = null
  let stopped = false

  async function tick() {
    if (stopped) return
    try {
      const data = await fetchFn()
      if (onTick) onTick(data)
      if (isDone && isDone(data)) {
        stop()
        if (onDone) onDone(data)
        return
      }
      schedule()
    } catch (err) {
      stop()
      if (onError) onError(err)
    }
  }

  function schedule() {
    if (stopped) return
    timer = setTimeout(tick, interval)
  }

  function start() {
    stopped = false
    if (timer) return
    // 第一次立即执行
    tick()
  }

  function stop() {
    stopped = true
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  return { start, stop, isRunning: () => !stopped && timer !== null }
}

/**
 * 简单版：启动一个轮询，返回 stop 函数
 * @param {Function} fetchFn 每次轮询调用的异步函数
 * @param {Function} isDone 判断是否结束的函数 (data) => boolean
 * @param {object} opts { interval, onDone, onError, onTick }
 * @returns {Function} stop 函数
 */
export function startPolling(fetchFn, isDone, opts = {}) {
  const poller = createPoller({
    fetchFn,
    isDone,
    interval: opts.interval || 3000,
    onDone: opts.onDone,
    onError: opts.onError,
    onTick: opts.onTick,
  })
  poller.start()
  return poller.stop
}
