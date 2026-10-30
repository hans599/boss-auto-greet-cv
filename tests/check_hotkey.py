# -*- coding: utf-8 -*-
"""验证急停快捷键：脚本自己模拟按下 Ctrl+Alt+Q，看能否立即中断等待"""
import ctypes
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import main

user32 = ctypes.windll.user32
VK_CONTROL, VK_MENU = 0x11, 0x12
KEYEVENTF_KEYUP = 0x0002

print("快捷键配置:", config.STOP_HOTKEY)
print("解析结果 mods/vk:", hex(main.stop.mods), hex(main.stop.vk))

main.stop.start()
print("热键注册成功:", main.stop._hotkey_ok)


def press_combo():
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_MENU, 0, 0, 0)
    user32.keybd_event(ord("Q"), 0, 0, 0)
    time.sleep(0.12)
    user32.keybd_event(ord("Q"), 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)


print("\n模拟按下 Ctrl+Alt+Q，然后进入一个 10 秒的可中断等待...")
press_combo()

t0 = time.monotonic()
try:
    main.stop.sleep(10)
    print("❌ 没有被中断（急停失效）")
except main.StopRequested:
    print(f"✅ 在 {time.monotonic() - t0:.2f} 秒内被中断，急停有效")
finally:
    main.release_mouse_buttons()
