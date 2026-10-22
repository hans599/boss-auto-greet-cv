import os
import re
import time
import random
import cv2
import numpy as np
import mss
import pyautogui
import pygetwindow as gw

# ===== 配置区 =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_IMAGE = os.path.join(BASE_DIR, "imgs", "open-video.png")  # 图标截图放在脚本同目录下的imgs
WINDOW_TITLE = "VLC media player"   # 只要清洗后的窗口标题包含这段文字即可
CONFIDENCE = 0.8
CLICK_OFFSET_X = 0
CLICK_OFFSET_Y = 0
MAX_ATTEMPTS = 10
RETRY_INTERVAL = (0.8, 2.0)        
MOVE_DURATION = (0.3, 0.8)
CLICK_PAUSE = (1.0, 3.0)
WINDOW_WAIT_SECONDS = 60


def normalize(s):
    """去掉零宽字符、不间断空格等不可见字符，压缩空白，转小写。"""
    if not s:
        return ""
    s = s.replace("\u200b", "").replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


def get_window(title):
    """返回清洗后标题包含 title 的第一个窗口对象，找不到返回 None。"""
    key = normalize(title)
    if not key:
        return None
    for w in gw.getAllWindows():
        if w.title and key in normalize(w.title):
            return w
    return None


def wait_for_window(title, timeout=60):
    """循环等待窗口出现，最多等 timeout 秒。"""
    for i in range(timeout):
        win = get_window(title)
        if win is not None:
            print(f"找到窗口: {win.title!r}")
            return win
        print(f"[{i + 1}/{timeout}] 还没找到窗口，1 秒后重试...")
        time.sleep(1)
    return None


def ensure_window_active(win):
    """尽量把目标窗口切到前台。只在开始找图前调用一次。"""
    try:
        if not win.isActive:
            win.activate()
            time.sleep(0.5)
    except Exception:
        pass



# 模拟人点击，更拟人的话可以用 windmouse
def human_move_and_click(x, y):
    duration = random.uniform(*MOVE_DURATION) # 移动时长随机
    pyautogui.moveTo(x, y, duration=duration, tween=pyautogui.easeOutQuad)
    # 点击前后有随机停顿
    time.sleep(random.uniform(0.1, 0.3))
    pyautogui.click()
    time.sleep(random.uniform(*CLICK_PAUSE))


def grab_region(sct, region):
    """用 mss 截取指定区域，返回 BGR 格式的 numpy 数组。"""
    left, top, width, height = region
    monitor = {"left": left, "top": top, "width": width, "height": height}
    raw = sct.grab(monitor)
    img = np.array(raw)  # BGRA
    return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)


def find_template_in_region(sct, template, region, confidence):
    """在 region 内做模板匹配，返回 (屏幕绝对x, 屏幕绝对y, 匹配度)，找不到返回 None。"""
    if template is None:
        return None

    screen = grab_region(sct, region)
    if screen.size == 0:
        return None

    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val < confidence:
        return None

    th, tw = template.shape[:2]
    left, top, _, _ = region
    cx = left + max_loc[0] + tw // 2
    cy = top + max_loc[1] + th // 2
    return cx, cy, max_val


def find_and_click(sct, template, win, confidence=0.8):
    # 只在开头激活一次，循环内不再动窗口状态，避免坐标乱跳
    ensure_window_active(win)
    time.sleep(0.5)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        region = (win.left, win.top, win.width, win.height)
        print(f"[第 {attempt} 次] 正在查找目标图标，区域 {region} ...")

        found = find_template_in_region(sct, template, region, confidence)

        if found is not None:
            cx, cy, score = found
            x = cx + CLICK_OFFSET_X
            y = cy + CLICK_OFFSET_Y
            print(f"  找到图标，坐标 ({x}, {y})，匹配度 {score:.3f}，准备点击")
            human_move_and_click(x, y)
            return True

        wait = random.uniform(*RETRY_INTERVAL)
        print(f"  没找到，{wait:.1f} 秒后重试")
        time.sleep(wait)

    print("达到最大尝试次数，放弃")
    return False


if __name__ == "__main__":
    print("===== 当前所有窗口标题（含清洗后）=====")
    for i, t in enumerate(gw.getAllTitles()):
        if t.strip():
            print(f"[{i}] raw={t!r}  normalized={normalize(t)!r}")
    print("======================================")

    template = None
    if os.path.exists(TARGET_IMAGE):
        template = cv2.imdecode(np.fromfile(TARGET_IMAGE, dtype=np.uint8), cv2.IMREAD_COLOR)
        if template is not None:
            print(f"模板图加载成功，尺寸: {template.shape[1]}x{template.shape[0]}")
        else:
            print(f"模板图读取失败: {TARGET_IMAGE}")
    else:
        print(f"模板图不存在: {TARGET_IMAGE}")

    if template is None:
        print("没有可用的模板图，退出")
        exit(1)

    print(f"正在等待标题包含“{WINDOW_TITLE}”的窗口出现（最多 {WINDOW_WAIT_SECONDS} 秒）...")
    win = wait_for_window(WINDOW_TITLE, WINDOW_WAIT_SECONDS)
    if win is None:
        print("等待超时，退出")
        exit(1)

    ensure_window_active(win)
    time.sleep(0.5)

    with mss.mss() as sct:
        success = find_and_click(sct, template, win, CONFIDENCE)

    print("结果:", "成功" if success else "失败")