import mss
import pyautogui
import pygetwindow as gw

with mss.MSS() as sct:
    print("PyAutoGUI:", pyautogui.size())
    print("MSS:", sct.monitors)

    win = gw.getWindowsWithTitle("BOSS直聘")[0]

    print("Edge窗口:")
    print("left:", win.left)
    print("top:", win.top)
    print("width:", win.width)
    print("height:", win.height)

    print("当前鼠标:", pyautogui.position())