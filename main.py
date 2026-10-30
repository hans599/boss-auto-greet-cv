# -*- coding: utf-8 -*-
"""BOSS 直聘 - 自动打招呼

鼠标"不动也不点"的根因（2026-10-30 定位结论）：
    Edge 若以管理员身份运行（完整性 High），而本脚本是普通权限（Medium），
    Windows 的 UIPI 会拦截一切合成输入：
        · SetCursorPos() 直接返回失败，光标纹丝不动
        · SendInput()/mouse_event() 返回成功，但事件被静默丢弃
    表现为 pyautogui.moveTo() 静默失效，随后位置校验判定"偏移"而放弃点击。

本版修复：
    1. 输入层改成 SetCursorPos + SendInput 双通道，每步都校验真实光标位置；
    2. 启动即检测权限隔离，明确提示并可自动以管理员身份重启；
    3. 截图区域按显示器边界裁剪，修掉最大化窗口 -9/-7 隐形边框带来的坐标偏移；
    4. 点击失败区分"环境不可用"（立刻中止并说明）与"点空了"（重试/换人）。

DPI / 显示缩放（2026-10-30 补充）：
    · 进程声明为 Per-Monitor DPI Aware，所以"窗口矩形"和"截图"都是物理像素，坐标体系一致；
    · 但模板图是**物理像素**的：125% 下截的按钮就是 75x37，系统缩放一改按钮物理尺寸就变。
      实测缩放偏 10%，匹配分从 0.9997 掉到 0.62，直接判定"找不到按钮"；
    · 因此新增 calibrate_scale()：启动时扫一遍缩放比（用显示器 DPI 作搜索起点），
      之后复用；某一轮突然找不到按钮时会自动重算（兼容中途改缩放/换不同缩放的显示器）。
"""
import sys
import ctypes
import ctypes.wintypes as wintypes

# ---- DPI：必须在任何窗口/截图 API 之前，保证窗口矩形与截图同一坐标系（物理像素）----
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import os
import re
import time
import random
import threading

import cv2
import numpy as np
import mss
import pygetwindow as gw

import config

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)


# ======================================================================================
# 原生输入层
# ======================================================================================
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000

ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class _INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("mi", _MOUSEINPUT)]

    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


user32.GetCursorPos.argtypes = [ctypes.POINTER(_POINT)]
user32.GetCursorPos.restype = ctypes.c_bool
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SetCursorPos.restype = ctypes.c_bool
user32.SendInput.argtypes = [wintypes.UINT, ctypes.c_void_p, ctypes.c_int]
user32.SendInput.restype = wintypes.UINT


def cursor_pos():
    """真实光标坐标（物理像素）"""
    p = _POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def _near(cur, target, tol):
    return abs(cur[0] - target[0]) <= tol and abs(cur[1] - target[1]) <= tol


def _send_input(flags, dx=0, dy=0, data=0):
    inp = _INPUT()
    inp.type = INPUT_MOUSE
    inp.mi = _MOUSEINPUT(int(dx), int(dy), int(data), flags, 0, 0)
    return user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT)) == 1


def send_absolute(x, y):
    """SendInput 绝对定位（虚拟桌面坐标归一化）"""
    vsx, vsy = virtual_origin()
    vsw, vsh = virtual_size()
    nx = int(round((x - vsx) * 65535 / max(vsw - 1, 1)))
    ny = int(round((y - vsy) * 65535 / max(vsh - 1, 1)))
    return _send_input(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK, nx, ny)


def send_relative(dx, dy):
    return _send_input(MOUSEEVENTF_MOVE, int(dx), int(dy))


def virtual_origin():
    return user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)


def virtual_size():
    return user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)


def move_cursor(x, y, tol=None, verbose=False):
    """把光标移动到 (x, y)，逐级降级，最后校验真实位置。

    返回 True 表示光标确实落到了目标点。
    """
    x, y = int(round(float(x))), int(round(float(y)))
    tol = config.VERIFY_TOLERANCE if tol is None else tol
    target = (x, y)

    # 通道 1：SetCursorPos（最快，绝大多数情况一次成功）
    if user32.SetCursorPos(x, y):
        stop.sleep(0.02)
        if _near(cursor_pos(), target, tol):
            return True

    # 通道 2：SendInput 绝对移动
    if send_absolute(x, y):
        stop.sleep(0.03)
        if _near(cursor_pos(), target, tol):
            return True

    # 通道 3：相对位移补偿（部分环境只接受相对事件）
    for _ in range(3):
        cur = cursor_pos()
        if _near(cur, target, tol):
            return True
        send_relative(x - cur[0], y - cur[1])
        stop.sleep(0.04)

    ok = _near(cursor_pos(), target, max(tol, 8))
    if not ok and verbose:
        print(f"    ⚠️ 光标无法移动到 {(x, y)}，当前仍在 {cursor_pos()}")
    return ok


def human_move(x, y):
    """带缓动 + 抖动的人手化移动，落点仍用 move_cursor 精确校正"""
    sx, sy = cursor_pos()
    x, y = int(x), int(y)
    steps = random.randint(12, 20)
    for i in range(1, steps + 1):
        t = i / steps
        e = t * t * (3 - 2 * t)  # smoothstep
        nx = int(sx + (x - sx) * e + random.uniform(-1.2, 1.2))
        ny = int(sy + (y - sy) * e + random.uniform(-1.2, 1.2))
        user32.SetCursorPos(nx, ny)
        stop.sleep(random.uniform(0.008, 0.018))
        if i == 3 and max(abs(cursor_pos()[0] - sx), abs(cursor_pos()[1] - sy)) == 0:
            break  # 光标完全没动 → 输入被拦截，别浪费 20 步
    return move_cursor(x, y)


def release_mouse_buttons():
    """兜底：松开可能被按住的鼠标键（急停时尤其重要，避免留下"按住拖动"状态）"""
    for flag in (MOUSEEVENTF_LEFTUP, MOUSEEVENTF_RIGHTUP, MOUSEEVENTF_MIDDLEUP):
        try:
            _send_input(flag)
        except Exception:
            pass


def click_at(x, y):
    """先精确移动，再按下/抬起。返回是否成功把点击事件发出去。"""
    if not human_move(x, y):
        return False
    if not _near(cursor_pos(), (int(x), int(y)), max(config.VERIFY_TOLERANCE, 6)):
        return False
    stop.sleep(random.uniform(0.04, 0.12))
    try:
        ok_down = _send_input(MOUSEEVENTF_LEFTDOWN)
        stop.sleep(random.uniform(0.04, 0.09))
        ok_up = _send_input(MOUSEEVENTF_LEFTUP)
    except StopRequested:
        _send_input(MOUSEEVENTF_LEFTUP)  # 别让左键卡在按下状态
        raise
    return ok_down and ok_up


def send_wheel(amount):
    return _send_input(MOUSEEVENTF_WHEEL, 0, 0, int(amount) & 0xFFFFFFFF)


# ======================================================================================
# 人工急停：全局快捷键（默认 Ctrl+Alt+Q）
# ======================================================================================
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

WM_HOTKEY = 0x0312
VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_MENU = 0x12          # Alt
VK_LWIN = 0x5B

_VK_NAMES = {
    "esc": 0x1B, "escape": 0x1B, "space": 0x20, "tab": 0x09,
    "enter": 0x0D, "return": 0x0D, "backspace": 0x08, "pause": 0x13,
    "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22, "up": 0x26, "down": 0x28,
    "left": 0x25, "right": 0x27,
}
for _i in range(1, 25):
    _VK_NAMES[f"f{_i}"] = 0x6F + _i           # F1=0x70
for _c in "abcdefghijklmnopqrstuvwxyz":
    _VK_NAMES[_c] = ord(_c.upper())
for _d in "0123456789":
    _VK_NAMES[_d] = ord(_d)


class StopRequested(Exception):
    """用户按下急停快捷键"""


def parse_hotkey(spec):
    """'ctrl+alt+q' -> (mods, vk)"""
    mods, vk = 0, None
    for part in re.split(r"\s*\+\s*", str(spec).strip().lower()):
        if not part:
            continue
        if part in ("ctrl", "control"):
            mods |= MOD_CONTROL
        elif part == "alt":
            mods |= MOD_ALT
        elif part == "shift":
            mods |= MOD_SHIFT
        elif part in ("win", "cmd", "super"):
            mods |= MOD_WIN
        elif part in _VK_NAMES:
            if vk is not None:
                raise ValueError("只能有一个主键")
            vk = _VK_NAMES[part]
        else:
            raise ValueError(f"无法识别的按键 {part!r}")
    if vk is None:
        raise ValueError("缺少主键，例如 ctrl+alt+q")
    return mods, vk


class StopController:
    """急停开关：注册全局热键（立即响应）+ 按键轮询（兜底）

    所有等待都走 sleep()，所以按下去最迟 STOP_POLL_INTERVAL 秒就会中断。
    """

    def __init__(self, spec):
        self.label = str(spec).strip().upper()
        try:
            self.mods, self.vk = parse_hotkey(spec)
        except Exception as e:
            print(f"⚠️ 急停快捷键 {spec!r} 配置无效（{e}），回退为 ESC")
            self.mods, self.vk, self.label = 0, 0x1B, "ESC"
        self._event = threading.Event()
        self._hotkey_ok = False

    # ---------- 注册 ----------
    def start(self):
        t = threading.Thread(target=self._hotkey_loop, name="stop-hotkey", daemon=True)
        t.start()
        time.sleep(0.15)  # 等注册结果，好把提示打准
        if self._hotkey_ok:
            print(f"⌨️  急停快捷键已就绪：按住 {self.label} 可立即终止")
        else:
            print(f"⌨️  急停快捷键注册失败（可能被其它软件占用），"
                  f"已启用轮询兜底：按住 {self.label} 依然能停")

    def _hotkey_loop(self):
        # RegisterHotKey 必须在有消息循环的线程里注册
        if not user32.RegisterHotKey(None, 1, self.mods | 0x4000, self.vk):  # MOD_NOREPEAT
            return
        self._hotkey_ok = True
        msg = wintypes.MSG()
        while not self._event.is_set():
            r = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if r in (0, -1):
                return
            if msg.message == WM_HOTKEY:
                print("\n🛑 检测到急停快捷键！")
                self._event.set()
                return

    # ---------- 查询 ----------
    def _down(self, vk):
        return bool(user32.GetAsyncKeyState(vk) & 0x8000)

    def requested(self):
        if self._event.is_set():
            return True
        if self.mods & MOD_CONTROL and not self._down(VK_CONTROL):
            return False
        if self.mods & MOD_ALT and not self._down(VK_MENU):
            return False
        if self.mods & MOD_SHIFT and not self._down(VK_SHIFT):
            return False
        if self.mods & MOD_WIN and not self._down(VK_LWIN):
            return False
        return self._down(self.vk)

    def check(self):
        if self.requested():
            self._event.set()
            raise StopRequested()

    # ---------- 可中断的等待 ----------
    def sleep(self, seconds):
        end = time.monotonic() + float(seconds)
        while True:
            self.check()
            left = end - time.monotonic()
            if left <= 0:
                return
            time.sleep(min(left, config.STOP_POLL_INTERVAL))


stop = StopController(getattr(config, "STOP_HOTKEY", "ctrl+alt+q"))


# ======================================================================================
# 权限（UIPI）检测
# ======================================================================================
_INTEGRITY = {0x0000: "Untrusted", 0x1000: "Low", 0x2000: "Medium",
              0x2100: "MediumPlus", 0x3000: "High", 0x4000: "System"}


class _SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]


class _TOKEN_MANDATORY_LABEL(ctypes.Structure):
    _fields_ = [("Label", _SID_AND_ATTRIBUTES)]


advapi32.GetSidSubAuthorityCount.argtypes = [ctypes.c_void_p]
advapi32.GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_ubyte)
advapi32.GetSidSubAuthority.argtypes = [ctypes.c_void_p, wintypes.DWORD]
advapi32.GetSidSubAuthority.restype = ctypes.POINTER(wintypes.DWORD)


def is_elevated():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def integrity_name(rid):
    return _INTEGRITY.get(rid, hex(rid) if rid is not None else "未知")


def dpi_awareness():
    """0=不感知 1=系统级 2=每显示器"""
    try:
        val = ctypes.c_int(-1)
        ctypes.windll.shcore.GetProcessDpiAwareness(None, ctypes.byref(val))
        return val.value
    except Exception:
        return -1


def monitor_dpi(x, y):
    """(x, y) 所在显示器的实际 DPI。96 = 100%，120 = 125%，144 = 150%"""
    try:
        hmon = user32.MonitorFromPoint(wintypes.POINT(int(x), int(y)), 2)  # NEAREST
        dx, dy = wintypes.UINT(), wintypes.UINT()
        if ctypes.windll.shcore.GetDpiForMonitor(hmon, 0, ctypes.byref(dx), ctypes.byref(dy)) == 0:
            return int(dx.value)
    except Exception:
        pass
    try:
        return int(user32.GetDpiForSystem())
    except Exception:
        return 96


def process_integrity(pid):
    """返回进程完整性 RID（0x1000=Low 0x2000=Medium 0x3000=High），失败返回 None"""
    if not pid:
        return None
    h = kernel32.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return None
    try:
        tok = wintypes.HANDLE()
        if not advapi32.OpenProcessToken(h, 0x0008, ctypes.byref(tok)):
            return None
        try:
            size = wintypes.DWORD(0)
            advapi32.GetTokenInformation(tok, 25, None, 0, ctypes.byref(size))
            buf = ctypes.create_string_buffer(max(size.value, 16))
            if not advapi32.GetTokenInformation(tok, 25, buf, size, ctypes.byref(size)):
                return None
            label = ctypes.cast(buf, ctypes.POINTER(_TOKEN_MANDATORY_LABEL)).contents
            cnt = advapi32.GetSidSubAuthorityCount(label.Label.Sid)[0]
            return int(advapi32.GetSidSubAuthority(label.Label.Sid, cnt - 1)[0])
        finally:
            kernel32.CloseHandle(tok)
    finally:
        kernel32.CloseHandle(h)


def window_pid(win):
    try:
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(win._hWnd, ctypes.byref(pid))
        return pid.value
    except Exception:
        return None


def input_blocked_reason(win):
    """若合成输入会被系统拦截，返回原因字符串；否则返回 None"""
    mine = process_integrity(kernel32.GetCurrentProcessId())
    theirs = process_integrity(window_pid(win))
    if mine is None or theirs is None:
        # 打不开对方令牌本身就是"它比我权限高"的强信号
        if theirs is None and not is_elevated():
            return (f"无法读取窗口进程的权限信息（通常是它比脚本权限更高），"
                    f"当前脚本完整性={_INTEGRITY.get(mine, mine)}")
        return None
    if theirs > mine:
        return (f"窗口进程完整性={_INTEGRITY.get(theirs, hex(theirs))}，"
                f"脚本完整性={_INTEGRITY.get(mine, hex(mine))}")
    return None


def relaunch_as_admin():
    """以管理员身份重启自己（会弹 UAC）"""
    exe = sys.executable
    params = " ".join(f'"{a}"' for a in [os.path.abspath(__file__)] + sys.argv[1:])
    try:
        rc = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", exe, params, os.path.dirname(os.path.abspath(__file__)), 1)
        return rc > 32
    except Exception as e:
        print("提权失败:", e)
        return False


# ======================================================================================
# 窗口 / 截图
# ======================================================================================
def normalize(s):
    if not s:
        return ""
    s = s.replace("\u200b", "").replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


def get_window(title):
    key = normalize(title)
    if not key:
        return None
    for w in gw.getAllWindows():
        if w.title and key in normalize(w.title):
            return w
    return None


def wait_for_window(title, timeout=60):
    for _ in range(timeout):
        win = get_window(title)
        if win is not None:
            print(f"找到窗口: {win.title!r}")
            return win
        stop.sleep(1)
    return None


SW_RESTORE = 9
SW_SHOW = 5
SW_MAXIMIZE = 3
WM_SYSCOMMAND = 0x0112
SC_RESTORE = 0xF120

# 记录窗口启动时的显示状态，用来保证"原来最大化就一直最大化"
WIN_STATE = {"hwnd": None, "maximized": None}


def remember_window_state(win):
    try:
        hwnd = win._hWnd
        WIN_STATE["hwnd"] = hwnd
        WIN_STATE["maximized"] = bool(user32.IsZoomed(hwnd))
    except Exception:
        pass
    return WIN_STATE["maximized"]


def native_restore(win):
    """把窗口唤到前台，但**绝不改变它的尺寸/最大化状态**。

    实测：
      · Edge 最小化后 ShowWindow(SW_RESTORE) / ShowWindowAsync / SetWindowPos 全部无效
        （rect 一直停在 -32000,-32000），只有 SendMessage(WM_SYSCOMMAND, SC_RESTORE) 能还原；
      · 但对"已经最大化"的窗口调用 SW_RESTORE / SW_SHOW 有把它变回普通窗口的风险，
        所以这里只对最小化的窗口做还原，其余情况一律不动尺寸，只 SetForegroundWindow。
    """
    try:
        hwnd = win._hWnd
        if user32.IsIconic(hwnd):
            user32.SendMessageW(hwnd, WM_SYSCOMMAND, SC_RESTORE, 0)
            # 最小化前是最大化 → 还原后必须还是最大化
            if WIN_STATE.get("maximized") and not user32.IsZoomed(hwnd):
                user32.ShowWindow(hwnd, SW_MAXIMIZE)
        user32.SetForegroundWindow(hwnd)
        return True
    except Exception:
        return False


def ensure_window_state(win, verbose=True):
    """保证窗口保持启动时的显示状态（默认"原来最大化就一直最大化"）。
    程序只负责把窗口唤到前台，绝不缩小它。"""
    try:
        hwnd = win._hWnd
        if WIN_STATE.get("hwnd") != hwnd:
            remember_window_state(win)
            return
        if not getattr(config, "KEEP_MAXIMIZED", True) or not WIN_STATE.get("maximized"):
            return
        if user32.IsIconic(hwnd):
            return  # 最小化由 native_restore 处理
        if not user32.IsZoomed(hwnd):
            user32.ShowWindow(hwnd, SW_MAXIMIZE)
            if verbose:
                log("🔲 窗口不再是最大化，已恢复最大化（程序不会把窗口改小）")
    except Exception:
        pass


def ensure_window_active(win, sct=None, tries=3):
    """把浏览器切到前台。成功返回 True。不会改变窗口大小。"""
    if WIN_STATE.get("hwnd") != win._hWnd:
        remember_window_state(win)

    for i in range(tries):
        try:
            if win.isActive:
                ensure_window_state(win, verbose=False)
                return True
        except Exception:
            pass
        native_restore(win)
        stop.sleep(0.6)
        try:
            if win.isActive:
                return True
        except Exception:
            pass

    ok = foreground_is(win)
    print("  " + ("窗口已在前台" if ok else "⚠️ 无法把浏览器切到前台，请手动点一下浏览器窗口"))
    return ok


def foreground_is(win):
    try:
        fg = user32.GetForegroundWindow()
        return fg == win._hWnd
    except Exception:
        return False


def window_region(sct, win):
    """窗口截图区域：裁剪到窗口所在的那块显示器。
    最大化窗口的矩形常是 (-9,-9,1938,1048)，越界那几像素截到的是邻居显示器的内容，
    不裁剪会让后续"匹配坐标 ↔ 屏幕坐标"整体偏移。
    """
    left, top = int(win.left), int(win.top)
    width, height = int(win.width), int(win.height)
    mon = monitor_at(sct, left + width // 2, top + height // 2)
    return clip_region(mon, (left, top, width, height), min_size=100)


def monitor_at(sct, x, y):
    for m in sct.monitors[1:]:
        if m["left"] <= x < m["left"] + m["width"] and m["top"] <= y < m["top"] + m["height"]:
            return m
    return sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]


def clip_region(mon, region, min_size=8):
    """把区域裁剪到 mon 范围内。返回裁剪后的区域；太小则返回 None。"""
    left, top, width, height = (int(v) for v in region)
    right = min(left + width, mon["left"] + mon["width"])
    bottom = min(top + height, mon["top"] + mon["height"])
    left = max(left, mon["left"])
    top = max(top, mon["top"])
    width = right - left
    height = bottom - top
    if width < min_size or height < min_size:
        return None
    return (left, top, width, height)


def grab_region(sct, region):
    """截图（region 必须已裁剪到屏幕内），返回 BGR 图"""
    if region is None:
        return None
    left, top, width, height = (int(v) for v in region)
    if width <= 0 or height <= 0:
        return None
    raw = sct.grab({"left": left, "top": top, "width": width, "height": height})
    return cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)


# --------------------------------------------------------------------------------------
# 模板缩放自适应（应对系统缩放/DPI 与截图时不一致）
#   模板是"物理像素"图片，125% 下截的按钮就是 75x37。
#   实测：缩放偏 10% 匹配分就从 0.99 掉到 0.62，直接判定"找不到按钮"。
#   所以启动时先扫一遍缩放，求出当前真实的缩放比，之后复用；中途改缩放会自动重算。
# --------------------------------------------------------------------------------------
_SCALE = {"value": 1.0, "valid": False, "score": 0.0}


def reset_template_scale():
    _SCALE["valid"] = False


def _scale_template(tpl, s):
    if abs(s - 1.0) < 1e-3:
        return tpl
    interp = cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC
    return cv2.resize(tpl, None, fx=s, fy=s, interpolation=interp)


def _best_score(screen, tpl):
    th, tw = tpl.shape[:2]
    if screen is None or screen.size == 0:
        return -1.0
    if screen.shape[0] < th or screen.shape[1] < tw:
        return -1.0
    return float(cv2.matchTemplate(screen, tpl, cv2.TM_CCOEFF_NORMED).max())


def calibrate_scale(sct, win, template, verbose=True):
    """在当前画面上求出模板的真实缩放比，写入 _SCALE 缓存。"""
    region = window_region(sct, win)
    screen = grab_region(sct, region)
    if screen is None or template is None:
        return _SCALE["value"]
    if config.TEMPLATE_SCALE is not None:          # 用户手工指定，跳过搜索
        _SCALE.update(value=float(config.TEMPLATE_SCALE), valid=True, score=1.0)
        if verbose:
            log(f"🎚️ 模板缩放：手动指定 {_SCALE['value']:.2f}x")
        return _SCALE["value"]

    lo, hi, step = config.SCALE_SEARCH
    # 用 DPI 给一个搜索起点：模板大概是按 SCALE_REFERENCE_DPI 截的
    dpi = monitor_dpi(region[0] + region[2] // 2, region[1] + region[3] // 2)
    hint = dpi / max(config.SCALE_REFERENCE_DPI, 1)

    # 先把提示点附近搜一遍，命中就不必全范围扫
    near = sorted({round(max(lo, min(hi, hint + d)), 3)
                   for d in (0, -0.05, 0.05, -0.1, 0.1, -0.15, 0.15, -0.2, 0.2)})
    best_s, best_score = None, -1.0
    for s in near:
        sc = _best_score(screen, _scale_template(template, s))
        if sc > best_score:
            best_s, best_score = s, sc
        if sc >= 0.93:
            break
    # 没命中再全范围粗扫
    if best_score < 0.9:
        s = lo
        while s <= hi + 1e-6:
            sc = _best_score(screen, _scale_template(template, s))
            if sc > best_score:
                best_s, best_score = s, sc
            s = round(s + step, 4)

    if best_score >= 0.7:
        _SCALE.update(value=float(best_s), valid=True, score=best_score)
        if verbose:
            log(f"🎚️ 模板缩放自动校准：{best_s:.2f}x（匹配度 {best_score:.3f}，"
                f"显示器 DPI={dpi} 即 {dpi / 96:.0%}）")
    else:
        _SCALE.update(value=1.0, valid=False, score=best_score)
        if verbose:
            log(f"🎚️ 模板缩放校准未命中（最高 {best_score:.3f}，DPI={dpi}），"
                f"暂用 1.00x；找不到按钮时会再校准一次")
    return _SCALE["value"]


def find_all_templates_in_region(sct, template, region, confidence, scale=None):
    """返回最上面一个匹配 (中心x, 中心y, 分数, w, h)，w/h 是缩放后的真实尺寸"""
    if template is None or region is None:
        return None
    screen = grab_region(sct, region)
    if screen is None or screen.size == 0:
        return None

    s = scale if scale is not None else _SCALE["value"]
    tpl = _scale_template(template, s)
    th, tw = tpl.shape[:2]
    if screen.shape[0] < th or screen.shape[1] < tw:
        return None

    result = cv2.matchTemplate(screen, tpl, cv2.TM_CCOEFF_NORMED)
    ys, xs = np.where(result >= confidence)
    if len(xs) == 0:
        return None

    left, top = int(region[0]), int(region[1])
    matches = []
    for px, py in zip(xs, ys):
        matches.append((left + int(px) + tw // 2,
                        top + int(py) + th // 2,
                        float(result[py, px]), tw, th))

    matches.sort(key=lambda m: (m[1], m[0]))
    unique = []
    for m in matches:
        if all(abs(m[0] - u[0]) >= tw * 0.5 or abs(m[1] - u[1]) >= th * 0.5 for u in unique):
            unique.append(m)
    return unique[0]


def verify_click(sct, continue_tpl, target_x, target_y, tw, th):
    """点击后校验：该位置是否变成了"继续沟通" """
    margin = 24
    mon = monitor_at(sct, int(target_x), int(target_y))
    region = clip_region(mon, (int(target_x) - tw // 2 - margin,
                              int(target_y) - th // 2 - margin,
                              tw + margin * 2,
                              th + margin * 2))
    stop.sleep(config.VERIFY_DELAY)
    return find_all_templates_in_region(
        sct, continue_tpl, region, config.VERIFY_CONFIDENCE) is not None


def load_template(path):
    if not os.path.exists(path):
        print(f"❌ 找不到图片: {path}")
        return None
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)


def log(msg):
    """同时打印到终端和 run.log（排查"跑一个就停"时看日志）"""
    print(msg)
    try:
        with open(config.LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except Exception:
        pass


def save_debug(sct, region, tag):
    """保存现场截图，方便事后看"为什么没找到按钮"""
    try:
        shot = grab_region(sct, region)
        if shot is not None:
            path = os.path.join(config.BASE_DIR, f"debug_{tag}.png")
            cv2.imwrite(path, shot)
            return path
    except Exception:
        pass
    return None


def change_ratio(before, after):
    """两张同尺寸图的"变化像素占比"。区域大小不同也稳定可比。"""
    if before is None or after is None or before.shape != after.shape:
        return 1.0
    d = cv2.absdiff(cv2.cvtColor(before, cv2.COLOR_BGR2GRAY),
                    cv2.cvtColor(after, cv2.COLOR_BGR2GRAY))
    return float((d > 12).mean())


def screen_changed(sct, region, before, ratio_threshold=None):
    """比较区域是否发生可视变化（用于校验滚动/点击是否真的生效）"""
    threshold = config.CHANGE_RATIO if ratio_threshold is None else ratio_threshold
    return change_ratio(before, grab_region(sct, region)) > threshold


def scroll_down(sct, win, amount, tries=None):
    """在窗口内滚动并校验页面是否真的动了。

    关键点：鼠标停在哪块区域决定了滚轮滚谁。
    推荐牛人页的窗口中心有时落在不可滚动的侧栏/聊天面板上，滚轮就完全没反应，
    所以这里换几个横向位置各试一次；只有全部无效才算真的滚不动。
    """
    region = window_region(sct, win)
    if region is None:
        return False
    tries = config.SCROLL_TRIES if tries is None else tries
    fractions = [0.55, 0.68, 0.40, 0.80]

    for i in range(tries):
        fx = fractions[i % len(fractions)]
        before = grab_region(sct, region)
        cx = region[0] + int(region[2] * fx)
        cy = region[1] + int(region[3] * 0.55)
        if not move_cursor(cx, cy):
            log("    ⚠️ 光标无法移动，滚动无法执行")
            return False
        send_wheel(amount)
        stop.sleep(random.uniform(*config.SCROLL_PAUSE))
        if screen_changed(sct, region, before):
            return True
        log(f"    ⚠️ 在 {int(fx * 100)}% 宽度处滚动，页面无变化（{i + 1}/{tries}）")

    log("    ⚠️ 多个位置滚动都无反应")
    return False


# ======================================================================================
# 主流程
# ======================================================================================
STATS = {"greeted": 0}  # 记录成功数，急停时也能报出来


def run_automation(sct, win, greet_tpl, continue_tpl, dry_run=False, max_greets=None):
    ensure_window_active(win, sct)
    stop.sleep(1.0)

    limit = config.MAX_GREETS if max_greets is None else max_greets
    greeted = 0
    empty_scrolls = 0     # 连续"没找到按钮"的次数
    stuck = 0             # 连续"滚动后页面毫无变化"的次数
    last_point = None     # 上次成功点击的位置，用来识别"界面没刷新"
    recalibrated = False  # 本轮是否已因"找不到按钮"重算过缩放
    exit_reason = "达到上限"

    log(f"===== 开始执行（目标 {limit} 个）=====")
    calibrate_scale(sct, win, greet_tpl)   # 先按当前 DPI 校准模板缩放

    while greeted < limit:
        stop.check()  # 每轮开始前响应急停
        if not foreground_is(win):
            ensure_window_active(win, sct)
        else:
            ensure_window_state(win)   # 每轮确认窗口还是最大化，程序不会把它改小

        region = window_region(sct, win)
        if region is None:
            stuck += 1
            log(f"⚠️ 窗口不在可见区域（被最小化或移出屏幕），尝试还原"
                f"（{stuck}/{config.MAX_SCROLL_STUCK}）")
            native_restore(win)
            stop.sleep(0.8)
            if stuck >= config.MAX_SCROLL_STUCK:
                exit_reason = "浏览器窗口不可见（最小化或被移到屏幕外）"
                break
            continue

        found = find_all_templates_in_region(sct, greet_tpl, region, config.CONFIDENCE)

        # ---------- 本屏没找到「打招呼」 ----------
        if found is not None:
            recalibrated = False

        if found is None and not recalibrated:
            # 可能中途改了显示缩放/把窗口拖到了另一块不同缩放的显示器 → 重算缩放再找一次
            recalibrated = True
            log("🎚️ 没找到「打招呼」，先按当前画面重算一次模板缩放"
                "（支持中途改显示缩放/换显示器）...")
            calibrate_scale(sct, win, greet_tpl)
            region = window_region(sct, win)
            found = find_all_templates_in_region(sct, greet_tpl, region, config.CONFIDENCE)
            if found is not None:
                log(f"   重算后命中，当前缩放 {_SCALE['value']:.2f}x")

        if found is None:
            empty_scrolls += 1
            path = save_debug(sct, region, "nogreet")
            log(f"🔍 视口内没找到「打招呼」按钮（第 {empty_scrolls}/{config.MAX_EMPTY_SCROLLS} 次）"
                + (f"  现场图: {os.path.basename(path)}" if path else ""))
            if empty_scrolls > config.MAX_EMPTY_SCROLLS:
                exit_reason = "连续多次滚动仍找不到「打招呼」（到底了，或页面结构变了）"
                break
            if scroll_down(sct, win, config.SCROLL_AMOUNT):
                stuck = 0
                continue
            stuck += 1
            log(f"⚠️ 滚动没有让页面变化（{stuck}/{config.MAX_SCROLL_STUCK}）")
            if stuck >= config.MAX_SCROLL_STUCK:
                exit_reason = "连续滚动无效（可能已到底，或浏览器/弹窗挡住了页面）"
                break
            stop.sleep(1.0)
            continue

        empty_scrolls = 0
        cx, cy, score, tw, th = found
        x = int(cx + config.CLICK_OFFSET_X)
        y = int(cy + config.CLICK_OFFSET_Y)

        # 上一轮刚点成功、这轮又定位到同一个点 → 界面没刷新，硬点会白费次数
        if last_point and abs(x - last_point[0]) <= 15 and abs(y - last_point[1]) <= 15:
            log("⚠️ 又定位到刚点过的同一个按钮（界面可能没刷新），滚一下再找")
            last_point = None
            if not scroll_down(sct, win, config.SCROLL_AMOUNT):
                stuck += 1
                if stuck >= config.MAX_SCROLL_STUCK:
                    exit_reason = "界面卡在同一个按钮上，滚动也无效"
                    break
            continue

        log(f"🎯 最上面的打招呼按钮：({x}, {y}) 匹配度 {score:.2f}")

        if dry_run:
            shot = grab_region(sct, region)
            if shot is not None:
                cv2.circle(shot, (x - region[0], y - region[1]), 12, (0, 0, 255), 2)
                cv2.imwrite("debug_match.png", shot)
                log("   [dry-run] 只定位不点击，标注图存 debug_match.png")
            # 顺便验证输入通道是否可用（不点击，只移动光标）
            if move_cursor(x, y):
                log(f"   [dry-run] 光标可以移动到 ({x}, {y}) → 输入通道正常")
            else:
                log(f"   [dry-run] ❌ 光标无法移动到 ({x}, {y}) → 输入被拦截")
            exit_reason = "dry-run 只跑一轮"
            break

        clicked = False
        for attempt in range(1, config.MAX_CLICK_RETRIES + 1):
            log(f"  [尝试 {attempt}/{config.MAX_CLICK_RETRIES}] 移动到 ({x}, {y}) 并点击...")
            if not click_at(x, y):
                reason = input_blocked_reason(win)
                log("  ❌ 鼠标无法移动/点击 —— 合成输入被系统拦截。")
                if reason:
                    log(f"     原因：{reason}")
                    log("     → 请右键终端「以管理员身份运行」，或让浏览器用普通权限启动。")
                else:
                    log("     → 检查是否有安全软件/远控软件占用鼠标，或浏览器窗口是否被遮挡。")
                exit_reason = "输入被系统拦截（权限隔离）"
                log(f"🏁 结束原因：{exit_reason}")
                return greeted

            if verify_click(sct, continue_tpl, x, y, tw, th):
                log("  ✅ 已变为「继续沟通」，打招呼成功")
                clicked = True
                break

            log("  ⚠️ 状态未变，可能点空了，重新定位后重试...")
            stop.sleep(random.uniform(0.8, 1.5))
            again = find_all_templates_in_region(sct, greet_tpl, window_region(sct, win),
                                                 config.CONFIDENCE)
            if again is None:
                log("  该按钮已消失（可能已打过招呼），继续下一个")
                break
            cx, cy, _, tw, th = again
            x = int(cx + config.CLICK_OFFSET_X)
            y = int(cy + config.CLICK_OFFSET_Y)

        if clicked:
            greeted += 1
            STATS["greeted"] = greeted
            last_point = (x, y)
            stuck = 0
            log(f"✅ 已打招呼 {greeted}/{limit}")
            stop.sleep(random.uniform(*config.GREET_INTERVAL))
            # 这里不滚动：同一屏通常还有下一个「打招呼」，先让下一轮在视口内继续找，
            # 盲目滚动容易把下一个候选人直接滚出视野。
            continue

        # 本屏没点成功 → 换下一个
        last_point = None
        log("↕️ 本次没点成功，向下滚动换人...")
        if not scroll_down(sct, win, config.SCROLL_AMOUNT):
            stuck += 1
            log(f"⚠️ 滚动无效（{stuck}/{config.MAX_SCROLL_STUCK}）")
            if stuck >= config.MAX_SCROLL_STUCK:
                exit_reason = "连续滚动无效"
                break
        else:
            stuck = 0

    log(f"🏁 结束原因：{exit_reason}")
    return greeted


def parse_args(argv):
    opts = {"dry_run": False, "no_elevate": False, "max_greets": None}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--dry-run":
            opts["dry_run"] = True
        elif a == "--no-elevate":
            opts["no_elevate"] = True
        elif a == "--max-greets":
            i += 1
            if i < len(argv) and argv[i].isdigit():
                opts["max_greets"] = int(argv[i])
        elif a.startswith("--max-greets="):
            v = a.split("=", 1)[1]
            if v.isdigit():
                opts["max_greets"] = int(v)
        i += 1
    return opts


def main():
    opts = parse_args(sys.argv[1:])

    stop.start()  # 尽早挂上急停键，等待窗口/提权时也能随时停

    # 每次运行清空日志，只保留本次
    try:
        with open(config.LOG_FILE, "w", encoding="utf-8") as f:
            f.write(f"=== 运行开始 {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
    except Exception:
        pass

    code = 0
    try:
        code = _run(opts)
    except StopRequested:
        print("\n🛑 已急停，自动化立即终止。")
        code = 130
    except KeyboardInterrupt:
        print("\n🛑 Ctrl+C 终止。")
        code = 130
    finally:
        release_mouse_buttons()  # 兜底松开鼠标键，避免留下"按住"状态
        print(f"🏁 本次共打招呼 {STATS['greeted']} 个。")
    return code


def _run(opts):
    dry_run = opts.get("dry_run", False)
    no_elevate = opts.get("no_elevate", False)
    max_greets = opts.get("max_greets")

    print("===== 加载模板 =====")
    greet_tpl = load_template(config.GREET_IMAGE)
    cont_tpl = load_template(config.CONTINUE_IMAGE)
    if greet_tpl is None or cont_tpl is None:
        print("模板图缺失，退出。")
        return 1

    print("\n===== 定位浏览器窗口 =====")
    win = wait_for_window(config.WINDOW_TITLE, config.WINDOW_WAIT_SECONDS)
    if win is None:
        print(f"等待窗口「{config.WINDOW_TITLE}」超时，退出。")
        return 1

    maximized = remember_window_state(win)
    print(f"   窗口状态：{'最大化' if maximized else '普通大小'}（程序只置前，不会改变窗口大小）")

    reason = input_blocked_reason(win)
    if reason:
        print("\n⚠️ 权限隔离：合成鼠标输入会被系统丢弃")
        print(f"   {reason}")
        if config.AUTO_ELEVATE and not no_elevate and not is_elevated():
            print("   正在以管理员身份重启脚本（请在弹出的 UAC 窗口点“是”）...")
            if relaunch_as_admin():
                return 0
        print("   请右键终端/IDE 选择「以管理员身份运行」后重试。")
        return 1

    print("\n===== 开始执行 =====")
    with mss.MSS() as sct:
        run_automation(sct, win, greet_tpl, cont_tpl, dry_run=dry_run, max_greets=max_greets)
    return 0


if __name__ == "__main__":
    sys.exit(main())
