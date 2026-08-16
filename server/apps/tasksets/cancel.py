"""
任务集协作式取消机制（P4 #6）。

语义：不杀线程/子进程；流水线与单阶段在**阶段边界**检查取消标志，
当前阶段（尤其 A4 的 DSH 会话）跑完后停止。事件用于进程内快速检查，
DB 标志用于跨请求/跨进程可见。
"""
import threading

from .models import TaskSet

_CANCEL_EVENTS: dict[int, threading.Event] = {}
_events_lock = threading.Lock()


def _event_for(task_set_id: int) -> threading.Event:
    with _events_lock:
        return _CANCEL_EVENTS.setdefault(task_set_id, threading.Event())


def request_cancel(task_set_id: int) -> None:
    """置取消标志（幂等）：Event 置位 + DB 标志落库。"""
    _event_for(task_set_id).set()
    TaskSet.objects.filter(pk=task_set_id).update(cancel_requested=True)


def clear_cancel(task_set_id: int) -> None:
    """清取消标志（新一轮执行前/结束后调用，防残留污染下次）。"""
    with _events_lock:
        ev = _CANCEL_EVENTS.get(task_set_id)
        if ev is not None:
            ev.clear()
    TaskSet.objects.filter(pk=task_set_id).update(cancel_requested=False)


def is_cancelled(task_set_id: int) -> bool:
    """是否已请求取消：Event 优先（进程内即时），DB 兜底。"""
    ev = _CANCEL_EVENTS.get(task_set_id)
    if ev is not None and ev.is_set():
        return True
    # DB 兜底（跨进程请求取消时 Event 不可见）
    return TaskSet.objects.filter(pk=task_set_id, cancel_requested=True).exists()
