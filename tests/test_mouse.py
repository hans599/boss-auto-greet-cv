import ctypes
import time
import pyautogui

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

print("PyAutoGUI:", pyautogui.__version__)
print("屏幕尺寸:", pyautogui.size())
print("初始位置:", get_pos())

print("\n测试一：PyAutoGUI")
pyautogui.moveTo(1000, 500, duration=0.5)
time.sleep(1)
print("结果:", get_pos())

print("\n测试二：Windows 原生 API")
result = user32.SetCursorPos(1200, 600)
time.sleep(1)
print("SetCursorPos 返回:", result)
print("结果:", get_pos())

input("回车退出")