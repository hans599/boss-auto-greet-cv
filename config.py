
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

# ===== 模板缩放（DPI 自适应）=====
# 模板是"物理像素"图片：125% 下截的「打招呼」按钮是 75x37。
# 系统缩放一改（100%/150%），按钮物理尺寸跟着变，实测偏 10% 匹配分就从 0.99 掉到 0.62，
# 直接判定"找不到按钮"。所以默认启动时自动扫缩放比。
TEMPLATE_SCALE = None        # None=自动校准（推荐）；填 1.0/0.8/1.25 可强制指定

SCALE_SEARCH = (0.6, 2.0, 0.05)   # 自动校准的搜索范围与步长 (起, 止, 步长)

SCALE_REFERENCE_DPI = 120    # 模板截图时的显示器 DPI（120=125%），仅用于给搜索一个起点

# 点击后校验「继续沟通」的阈值。校验区域只有按钮大小(约 123x85)，
# 误报概率极低，但缩放校准后重采样会让分数略降（实测 125%→1.00x 是 1.000，
# 换成 100% 缩放后同模板只剩 0.90），所以这里比全局 CONFIDENCE 放宽一点。
VERIFY_CONFIDENCE = 0.72

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