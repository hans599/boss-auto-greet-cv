
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

# ===== 输入校验 =====
# 光标落点允许误差(px)。超过就认为"移动失败"，换用 SendInput / 相对位移重试
VERIFY_TOLERANCE = 2

# 检测到"浏览器权限比脚本高"（UIPI 会拦截鼠标输入）时，自动以管理员身份重启。
# 设为 False 则只打印提示不重启。
AUTO_ELEVATE = True

# ===== 人工急停（全局快捷键，随便按一下就停）=====
# 支持写法：ctrl+alt+q / f9 / esc / ctrl+shift+f12 ...
# 建议用带修饰键的组合，避免误触。
STOP_HOTKEY = "ctrl+alt+q"

# 按键轮询间隔(秒)。快捷键注册失败（被其它软件占用）时靠轮询兜底。
STOP_POLL_INTERVAL = 0.05

# ===== 滚动参数 =====
SCROLL_AMOUNT = -220
SCROLL_PAUSE = (1.5, 3.0)

# 一次滚动最多在几个横向位置尝试（鼠标可能停在不可滚动的侧栏/聊天面板上）
SCROLL_TRIES = 3

# 连续多少次"滚动后页面毫无变化"才判定走到尽头。单次失败只是抖动，不该直接结束。
MAX_SCROLL_STUCK = 3

# 判定"页面有变化"的像素比例阈值（变化像素占比）。比重整屏灰度均值稳定得多。
CHANGE_RATIO = 0.002

# ===== 诊断参数 =====
DEBUG_SCREENSHOT = True
DEBUG_MATCH = True


MAX_GREETS = 50
MAX_CLICK_RETRIES = 3
MAX_EMPTY_SCROLLS = 5

# 运行日志（每轮为什么结束都会写进去，排查"只打一次就停"就看它）
LOG_FILE = os.path.join(BASE_DIR, "run.log")

GREET_INTERVAL = (3.0, 5.0)