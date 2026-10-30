import ctypes
import time

import pyautogui
import pygetwindow as gw

user32 = ctypes.windll.user32

class POINT(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_long),
        ("y", ctypes.c_long)
    ]

def get_native_position():
    p = POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y

win = gw.getWindowsWithTitle("BOSS直聘")[0]

print("窗口:", win.title)
print("PyAutoGUI:", pyautogui.size())

target_x = 1710
target_y = 511

print("移动前:", get_native_position())

pyautogui.moveTo(
    int(target_x),
    int(target_y),
    duration=0.5
)

time.sleep(0.5)

print("PyAutoGUI位置:", pyautogui.position())
print("Windows原生位置:", get_native_position())

input("按回车退出")