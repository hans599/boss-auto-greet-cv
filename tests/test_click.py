import ctypes
import pyautogui
import pygetwindow as gw
import time

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

win = gw.getWindowsWithTitle("Chrome")[0]

if win.isMinimized:
    win.restore()

win.activate()
time.sleep(2)

x = win.left + 300
y = win.top + 300

print("目标坐标:", x, y)

pyautogui.moveTo(x, y, duration=0.5)

print("鼠标当前位置:", pyautogui.position())
print("5秒后自动点击，请不要操作鼠标键盘")

time.sleep(5)

pyautogui.click(x, y)

print("点击完成")