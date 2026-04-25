from __future__ import annotations

from queue import Empty, Queue
from threading import Thread
from typing import Any, Callable


class Chan:
    def __init__(self, cap: int = 0) -> None:
        self.q: Queue[Any] = Queue(maxsize=max(cap, 0))


def rt_chan_new(cap: int) -> Chan:
    return Chan(cap)


def rt_chan_send(ch: Chan, value: Any) -> None:
    ch.q.put(value)


def rt_chan_recv(ch: Chan) -> Any:
    return ch.q.get()


def rt_select_recv(channels: list[Chan], default: Any | None = None) -> Any:
    for ch in channels:
        try:
            return ch.q.get_nowait()
        except Empty:
            continue
    if default is not None:
        return default
    return channels[0].q.get()


def rt_spawn(fn: Callable[..., Any], *args: Any) -> Thread:
    t = Thread(target=fn, args=args, daemon=True)
    t.start()
    return t


def rt_print_i32(v: int) -> None:
    print(v)


def rt_print_str(v: str) -> None:
    print(v)


def rt_panic(msg: str) -> None:
    raise RuntimeError(msg)


def rt_chan_ready(ch: Chan) -> int:
    return 0 if ch.q.empty() else 1
