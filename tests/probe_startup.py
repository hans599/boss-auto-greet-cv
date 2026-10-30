# -*- coding: utf-8 -*-
"""启动流程逐步体检：每一步后打印 Edge 是否仍最大化。

用来定位"程序一启动 Edge 就从最大化变回普通窗口"是哪一步干的。
只读取状态，不主动改窗口（除非发现被缩小了会尝试说明）。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ctypes
import mss

import main
import config

u = ctypes.windll.user32


def snap(tag):
    win = main.get_window(config.WINDOW_TITLE)
    if win is None:
        print(f"  [{tag}] 窗口不见了")
        return None
    h = win._hWnd
    print(f"  [{tag}] IsZoomed={bool(u.IsZoomed(h))} IsIconic={bool(u.IsIconic(h))} "
          f"rect=({win.left},{win.top}) {win.width}x{win.height} "
          f"前台={bool(main.foreground_is(win))}")
    return win


print("初始状态")
win = snap("before")
zoomed0 = bool(u.IsZoomed(win._hWnd)) if win else None

print("\n1) 加载模板")
g = main.load_template(config.GREET_IMAGE)
c = main.load_template(config.CONTINUE_IMAGE)
snap("load_template")

print("\n2) wait_for_window / get_window")
w2 = main.wait_for_window(config.WINDOW_TITLE, 3)
snap("wait_for_window")

print("\n3) input_blocked_reason")
main.input_blocked_reason(w2)
snap("input_blocked_reason")

print("\n4) ensure_window_active")
main.ensure_window_active(w2)
snap("ensure_window_active")

print("\n5) calibrate_scale")
with mss.MSS() as sct:
    main.calibrate_scale(sct, w2, g)
    snap("calibrate_scale")

    print("\n6) 一轮检测（不点击）")
    r = main.find_all_templates_in_region(sct, g, main.window_region(sct, w2), config.CONFIDENCE)
    print("   检测结果:", r[:2] if r else "无")
    snap("detect")

    print("\n7) stop.start() 注册热键")
    main.stop.start()
    snap("stop.start")

print("\n7) win.activate()")
try:
    main.get_window(config.WINDOW_TITLE).activate()
except Exception as e:
    print("   activate 抛异常:", e)
snap("activate")

print("\n最终")
win = main.get_window(config.WINDOW_TITLE)
if win and zoomed0 and not u.IsZoomed(win._hWnd):
    print("  ⚠️ 原本最大化，现在不是了 → 上面某一步是元凶")
else:
    print("  窗口最大化状态没变")
