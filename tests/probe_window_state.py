# -*- coding: utf-8 -*-
"""提权下验证：程序是否会改变 Edge 的最大化状态。

不点击、不滚动，只做 记录状态 → 最小化 → 还原 → 检查是否仍最大化。
结果写到 tests/window_state_result.txt（提权进程看不到我们这个终端）。
"""
import ctypes
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import main
import config

u = ctypes.windll.user32
OUT = os.path.join(BASE, "tests", "window_state_result.txt")
lines = []


def rec(msg):
    lines.append(msg)


try:
    win = main.get_window(config.WINDOW_TITLE)
    if win is None:
        rec("找不到窗口")
        raise SystemExit
    h = win._hWnd
    rec(f"是否管理员: {main.is_elevated()}")
    rec(f"初始: IsZoomed={bool(u.IsZoomed(h))} IsIconic={bool(u.IsIconic(h))} "
        f"rect=({win.left},{win.top}) {win.width}x{win.height}")
    was_max = bool(u.IsZoomed(h))
    main.remember_window_state(win)
    rec(f"记录状态: maximized={main.WIN_STATE['maximized']}")

    # 1) 最小化再还原（这是程序唯一会调还原的场景）
    u.ShowWindow(h, 6)  # SW_MINIMIZE
    main.stop.sleep(0.8)
    rec(f"最小化后: IsZoomed={bool(u.IsZoomed(h))} IsIconic={bool(u.IsIconic(h))}")

    main.native_restore(win)
    main.stop.sleep(1.0)
    rec(f"native_restore 后: IsZoomed={bool(u.IsZoomed(h))} IsIconic={bool(u.IsIconic(h))} "
        f"rect=({win.left},{win.top}) {win.width}x{win.height}")

    # 2) ensure_window_active / ensure_window_state 是否动尺寸
    main.ensure_window_active(win)
    main.stop.sleep(0.5)
    rec(f"ensure_window_active 后: IsZoomed={bool(u.IsZoomed(h))} "
        f"rect=({win.left},{win.top}) {win.width}x{win.height}")

    main.ensure_window_state(win)
    main.stop.sleep(0.5)
    rec(f"ensure_window_state 后: IsZoomed={bool(u.IsZoomed(h))} "
        f"rect=({win.left},{win.top}) {win.width}x{win.height}")

    if was_max and not u.IsZoomed(h):
        rec("结论: ❌ 原本最大化，现在不是了")
        u.ShowWindow(h, 3)
        main.stop.sleep(0.6)
        rec(f"已恢复最大化: IsZoomed={bool(u.IsZoomed(h))}")
    else:
        rec("结论: ✅ 最大化状态保持住了（程序不改变窗口大小）")
except Exception as e:
    rec(f"异常: {e!r}")
finally:
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
