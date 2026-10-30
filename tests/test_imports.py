import os
import re
import time
import random
import cv2
import numpy as np
import mss
import pyautogui
import pygetwindow as gw
import config

import ctypes

user32 = ctypes.windll.user32

class POINT(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_long),
        ("y", ctypes.c_long)
    ]

def get_pos():
    p = POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y

def test():
    print("PID:", os.getpid())
    print("PyAutoGUI:", pyautogui.__file__)
    print("DPI 设置前后测试")
    print("屏幕:", pyautogui.size())

    print("设置 DPI 感知")
    result = user32.SetProcessDPIAware()
    print("SetProcessDPIAware:", result)

    print("主屏宽高:",
          user32.GetSystemMetrics(0),
          user32.GetSystemMetrics(1))

    print("虚拟桌面:",
          user32.GetSystemMetrics(78),
          user32.GetSystemMetrics(79))

    print("当前鼠标:", get_pos())

    print("\n测试 PyAutoGUI")
    pyautogui.moveTo(1000, 500, duration=0.5)
    time.sleep(1)
    print("PyAutoGUI:", pyautogui.position())
    print("Win32:", get_pos())

    print("\n测试 Windows API")
    result = user32.SetCursorPos(1710, 511)
    print("SetCursorPos:", result)
    time.sleep(1)
    print("最终位置:", get_pos())

if __name__ == "__main__":
    test()
    input("回车退出")