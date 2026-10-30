import ctypes
import pyautogui
import mss
import time

user32 = ctypes.windll.user32

# Windows 显示器相关常量
SM_CXSCREEN = 0
SM_CYSCREEN = 1
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

print("========== 显示器坐标体系 ==========")

print("PyAutoGUI:", pyautogui.size())

print("Windows 主屏宽:", user32.GetSystemMetrics(SM_CXSCREEN))
print("Windows 主屏高:", user32.GetSystemMetrics(SM_CYSCREEN))

print("Windows 虚拟桌面 X:", user32.GetSystemMetrics(SM_XVIRTUALSCREEN))
print("Windows 虚拟桌面 Y:", user32.GetSystemMetrics(SM_YVIRTUALSCREEN))
print("Windows 虚拟桌面宽:", user32.GetSystemMetrics(SM_CXVIRTUALSCREEN))
print("Windows 虚拟桌面高:", user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))

with mss.MSS() as sct:
    print("MSS 虚拟桌面:", sct.monitors[0])
    for i, monitor in enumerate(sct.monitors[1:], 1):
        print(f"MSS 显示器 {i}:", monitor)

print("\n========== 鼠标移动测试 ==========")

for x, y in [
    (500, 300),
    (1000, 500),
    (1200, 600),
    (1710, 511)
]:
    ctypes.set_last_error(0)
    result = user32.SetCursorPos(x, y)
    error = ctypes.get_last_error()

    time.sleep(0.3)

    print(
        f"目标={(x, y)}, "
        f"返回={result}, "
        f"错误码={error}, "
        f"实际={pyautogui.position()}"
    )

input("按回车退出")