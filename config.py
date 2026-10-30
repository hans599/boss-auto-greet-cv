
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ===== 图片路径 =====
GREET_IMAGE = os.path.join(BASE_DIR, "imgs", "greet.png")
TUIJIAN_IMAGE = os.path.join(BASE_DIR, "imgs", "tuijian.png")
CONTINUE_IMAGE = os.path.join(BASE_DIR, "imgs", "continue.png")

# ===== 页面校验 =====
VERIFY_DELAY = 2.0

# ===== 窗口 =====
WINDOW_TITLE = "Microsoft Edge"
WINDOW_WAIT_SECONDS = 60

# ===== 模板匹配 =====
CONFIDENCE = 0.8

# ===== 坐标偏移 =====
CLICK_OFFSET_X = 0
CLICK_OFFSET_Y = 0

# ===== 鼠标移动参数 =====
MOVE_DURATION = (0.3, 0.8)
CLICK_PAUSE = (1.0, 3.0)

# ===== 滚动参数 =====
SCROLL_AMOUNT = -220
SCROLL_PAUSE = (1.5, 3.0)

# ===== 诊断参数 =====
DEBUG_SCREENSHOT = True
DEBUG_MATCH = True


MAX_GREETS = 50
MAX_CLICK_RETRIES = 3
MAX_EMPTY_SCROLLS = 5

GREET_INTERVAL = (3.0, 5.0)