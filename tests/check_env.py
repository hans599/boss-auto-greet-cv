# -*- coding: utf-8 -*-
"""环境自检：坐标体系 / 权限隔离 / 光标能否移动 / 模板能否匹配

用法：
    python tests/check_env.py
    python tests/check_env.py --move     # 额外做一次真实光标移动（会动鼠标）

任何时候脚本"鼠标不动或点不上"，先跑这个。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ctypes

import cv2
import mss

import config
import main

WINDOW = config.WINDOW_TITLE
DO_MOVE = "--move" in sys.argv

print("=" * 60)
print("1. 进程与权限")
print("=" * 60)
mine = main.process_integrity(main.kernel32.GetCurrentProcessId())
print(f"  急停快捷键: {config.STOP_HOTKEY}  "
      f"(mods={hex(main.stop.mods)}, vk={hex(main.stop.vk)})")
print(f"  脚本是否管理员: {main.is_elevated()}")
print(f"  脚本完整性级别: {main.integrity_name(mine)}")
print(f"  DPI 感知: {main.dpi_awareness()}  (0=不感知 1=系统级 2=每显示器)")
print(f"  虚拟桌面尺寸: {main.virtual_size()}")

print("\n" + "=" * 60)
print("2. 浏览器窗口")
print("=" * 60)
win = main.wait_for_window(WINDOW, 5)
if win is None:
    print("  ❌ 没找到窗口，请先打开浏览器并搜索 BOSS 直聘")
    sys.exit(1)

print(f"  标题: {win.title!r}")
print(f"  矩形: left={win.left} top={win.top} w={win.width} h={win.height}")
print(f"  是否前台: {main.foreground_is(win)}")
print(f"  本进程能否操作该窗口: {main.input_blocked_reason(win) or '可以'}")

print("\n" + "=" * 60)
print("3. 截图与模板匹配")
print("=" * 60)
greet = main.load_template(config.GREET_IMAGE)
cont = main.load_template(config.CONTINUE_IMAGE)
with mss.MSS() as sct:
    region = main.window_region(sct, win)
    print(f"  裁剪后截图区域: {region}")
    shot = main.grab_region(sct, region)
    if shot is None:
        print("  ❌ 截图失败")
        sys.exit(1)
    print(f"  截图尺寸: {shot.shape[1]}x{shot.shape[0]}")
    cv2.imwrite("debug_window.png", shot)

    for name, tpl in (("打招呼 greet", greet), ("继续沟通 continue", cont)):
        if tpl is None:
            print(f"  ❌ {name}: 模板图缺失")
            continue
        res = cv2.matchTemplate(shot, tpl, cv2.TM_CCOEFF_NORMED)
        _, best, _, loc = cv2.minMaxLoc(res)
        hit = main.find_all_templates_in_region(sct, tpl, region, config.CONFIDENCE)
        print(f"  {name}: 最高分={best:.4f} 位置={loc} 阈值={config.CONFIDENCE} "
              f"命中={hit[:2] if hit else '无'}")

    print("\n" + "=" * 60)
    print("4. 光标移动")
    print("=" * 60)
    print(f"  当前光标: {main.cursor_pos()}")
    if DO_MOVE:
        target = (region[0] + region[2] // 2, region[1] + region[3] // 2)
        ok = main.move_cursor(*target, verbose=True)
        print(f"  移动到窗口中心 {target}: {'✅ 成功' if ok else '❌ 被拦截'} 实际={main.cursor_pos()}")
    else:
        tx, ty = main.cursor_pos()
        ok = main.user32.SetCursorPos(tx, ty)
        print(f"  SetCursorPos 可用性: {'✅' if ok else '❌ 被系统拒绝'}")

print("\n完成")
