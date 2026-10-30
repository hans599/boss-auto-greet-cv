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

pyautogui.FAILSAFE = False


def normalize(s):
    if not s: return ""
    s = s.replace("\u200b", "").replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


def get_window(title):
    key = normalize(title)
    if not key: return None
    for w in gw.getAllWindows():
        if w.title and key in normalize(w.title):
            return w
    return None


def wait_for_window(title, timeout=60):
    for i in range(timeout):
        win = get_window(title)
        if win is not None:
            print(f"找到窗口: {win.title!r}")
            return win
        time.sleep(1)
    return None


def ensure_window_active(win):
    """只激活窗口"""
    try:
        if not win.isActive:
            win.activate()
            time.sleep(0.5)
    except Exception:
        pass


def grab_region(sct, region):
    """用 MSS 截取指定区域，强转 int 防止双屏浮点数报错"""
    left, top, width, height = [int(v) for v in region]
    if width <= 0 or height <= 0: return None
    
    # 双屏安全限制：防止截图区域超出物理显示器范围导致报错
    monitor = {"left": left, "top": top, "width": width, "height": height}
    try:
        raw = sct.grab(monitor)
        img = np.array(raw)
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    except Exception as e:
        print(f"MSS 截图异常 (可能是副屏坐标越界): {e}")
        return None


def find_all_templates_in_region(sct, template, region, confidence):
    """寻找所有匹配项，返回最上面那一个 (x, y, score, w, h)"""
    if template is None: return None
    screen = grab_region(sct, region)
    if screen is None or screen.size == 0: return None

    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    locations = np.where(result >= confidence)
    
    matches = []
    th, tw = template.shape[:2]
    left, top, _, _ = region

    for pt in zip(*locations[::-1]):
        match_x = left + pt[0] + tw // 2
        match_y = top + pt[1] + th // 2
        score = result[pt[1], pt[0]]
        matches.append((match_x, match_y, score, tw, th))
        
    if not matches: return None

    # 按 Y 坐标从上到下排序
    matches.sort(key=lambda m: (m[1], m[0]))
    unique_matches = []
    for m in matches:
        is_duplicate = False
        for u in unique_matches:
            if abs(m[0] - u[0]) < tw * 0.5 and abs(m[1] - u[1]) < th * 0.5:
                is_duplicate = True
                break
        if not is_duplicate:
            unique_matches.append(m)

    return unique_matches[0]


def verify_click(sct, continue_tpl, target_x, target_y, tw, th):
    """校验刚才点击的位置是否变成了继续沟通"""
    margin = 20
    check_region = (
        target_x - tw // 2 - margin,
        target_y - th // 2 - margin,
        tw + margin * 2,
        th + margin * 2
    )
    time.sleep(config.VERIFY_DELAY)
    found = find_all_templates_in_region(sct, continue_tpl, check_region, config.CONFIDENCE)
    return found is not None


def load_template(path):
    if not os.path.exists(path):
        print(f"❌ 找不到图片: {path}")
        return None
    template = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    return template


def human_move_and_click(x, y, win):
    """物理级坐标点击：修复双屏坐标系偏移"""
    ensure_window_active(win)
    
    x, y = int(x), int(y)

    # === 双屏坐标安全检查 ===
    # 如果算出来的坐标在极其遥远的地方（比如副屏偏移导致的异常值），直接终止
    if not (-10000 < x < 10000 and -10000 < y < 10000):
        print(f"⚠️ 坐标异常 ({x}, {y})，取消点击")
        return False

    print(f"  [移动鼠标] 目标物理坐标: ({x}, {y})")
    duration = random.uniform(*config.MOVE_DURATION)
    
    # 移动鼠标
    pyautogui.moveTo(x, y, duration=duration, tween=pyautogui.easeInOutQuad)
    time.sleep(random.uniform(0.2, 0.4))

    # 检查鼠标是否被系统弹回
    actual_x, actual_y = pyautogui.position()
    if abs(actual_x - x) > 5 or abs(actual_y - y) > 5:
        print(f"⚠️ 鼠标位置偏移！期望({x},{y}) 实际({actual_x},{actual_y})")
        return False

    pyautogui.click()
    return True


def scroll_down(win, amount):
    center_x = win.left + win.width // 2
    center_y = win.top + win.height // 2
    pyautogui.moveTo(center_x, center_y, duration=0.2)
    pyautogui.scroll(amount)
    time.sleep(random.uniform(*config.SCROLL_PAUSE))


def run_automation(sct, win, greet_tpl, continue_tpl):
    ensure_window_active(win)
    time.sleep(1.0)

    greeted_count = 0
    empty_scrolls = 0

    while greeted_count < config.MAX_GREETS:
        if not win.isActive:
            ensure_window_active(win)
            time.sleep(0.5)

        region = (win.left, win.top, win.width, win.height)
        found_greet = find_all_templates_in_region(sct, greet_tpl, region, config.CONFIDENCE)

        if found_greet is not None:
            empty_scrolls = 0
            cx, cy, score, tw, th = found_greet
            x = cx + config.CLICK_OFFSET_X
            y = cy + config.CLICK_OFFSET_Y

            print(f"🎯 找到最上面的打招呼按钮 (匹配度 {score:.2f})，坐标 ({x}, {y})")

            clicked_success = False
            for retry in range(config.MAX_CLICK_RETRIES):
                print(f"  [尝试 {retry+1}/{config.MAX_CLICK_RETRIES}] 鼠标移动并点击...")
                click_result = human_move_and_click(x, y, win)

                if not click_result:
                    print("  点击动作被拦截或坐标异常。")
                    break
                
                print(f"  等待 {config.VERIFY_DELAY} 秒校验状态...")
                if verify_click(sct, continue_tpl, cx, cy, tw, th):
                    print(f"  ✅ 状态已变为“继续沟通”，打招呼成功！")
                    clicked_success = True
                    break
                else:
                    print(f"  ⚠️ 状态未变，可能被遮挡，准备重试...")
                    time.sleep(random.uniform(1.0, 2.0))

            if clicked_success:
                greeted_count += 1
                print(f"✅ 已打招呼 {greeted_count}/{config.MAX_GREETS}")
                time.sleep(random.uniform(*config.GREET_INTERVAL))
                scroll_down(win, config.SCROLL_AMOUNT)
            else:
                print(f"❌ 连续 {config.MAX_CLICK_RETRIES} 次点击均未生效，跳过此人。")
                scroll_down(win, config.SCROLL_AMOUNT)

        else:
            empty_scrolls += 1
            print(f"🔍 没找到，尝试向下滚动寻找（连续 {empty_scrolls}/{config.MAX_EMPTY_SCROLLS} 次）...")

            if empty_scrolls >= config.MAX_EMPTY_SCROLLS:
                print(f"⚠️ 连续 {config.MAX_EMPTY_SCROLLS} 次没找到打招呼按钮，停止运行。")
                break

            scroll_down(win, config.SCROLL_AMOUNT)

    print(f"🏁 脚本结束，共打招呼 {greeted_count} 个。")


if __name__ == "__main__":
    print("===== 加载模板图 =====")
    greet_template = load_template(config.GREET_IMAGE)
    continue_template = load_template(config.CONTINUE_IMAGE)

    if greet_template is None:
        print("缺少打招呼模板图，退出。")
        exit(1)
    if continue_template is None:
        print("缺少继续沟通模板图，将无法校验是否成功，退出。")
        exit(1)

    print(f"\n===== 正在寻找浏览器窗口 =====")
    win = wait_for_window(config.WINDOW_TITLE, config.WINDOW_WAIT_SECONDS)
    if win is None:
        print("等待窗口超时，退出")
        exit(1)

    print("\n===== 开始执行自动化 =====")
    with mss.MSS() as sct:
        run_automation(sct, win, greet_template, continue_template)