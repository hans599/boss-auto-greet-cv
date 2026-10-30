# -*- coding: utf-8 -*-
"""DPI / 显示缩放自检：确认模板缩放自动校准是否生效。

只截图和匹配，不点击、不移动鼠标。窗口最小化时会自动还原。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mss
import main
import config

print("=" * 62)
print("1. DPI / 缩放")
print("=" * 62)
names = {0: "不感知 DPI（会被系统拉伸，坐标会错）", 1: "系统级 DPI 感知", 2: "每显示器 DPI 感知"}
print(f"  进程 DPI 感知: {main.dpi_awareness()} = {names.get(main.dpi_awareness(), '未知')}")
print(f"  系统 DPI: {main.user32.GetDpiForSystem()}")

win = main.get_window(config.WINDOW_TITLE)
if win is None:
    print(f"  ❌ 没找到窗口「{config.WINDOW_TITLE}」，请先打开 BOSS 直聘页面")
    sys.exit(1)

main.ensure_window_active(win)
main.stop.sleep(0.5)

with mss.MSS() as sct:
    region = main.window_region(sct, win)
    print(f"  窗口: {win.title!r}")
    print(f"  窗口 rect: ({win.left},{win.top}) {win.width}x{win.height}")
    print(f"  截图区域: {region}")
    if region is None:
        print("  ❌ 窗口不可见（最小化/移出屏幕），请手动点开浏览器窗口后重试")
        sys.exit(1)
    dpi = main.monitor_dpi(region[0] + region[2] // 2, region[1] + region[3] // 2)
    print(f"  该显示器 DPI: {dpi}  →  缩放 {dpi / 96:.0%}")

    print()
    print("=" * 62)
    print("2. 模板缩放自动校准")
    print("=" * 62)
    greet = main.load_template(config.GREET_IMAGE)
    cont = main.load_template(config.CONTINUE_IMAGE)
    gs = greet.shape[1], greet.shape[0]
    cs = cont.shape[1], cont.shape[0]
    print(f"  模板原始尺寸: greet {gs[0]}x{gs[1]}  continue {cs[0]}x{cs[1]}")

    scale = main.calibrate_scale(sct, win, greet)
    print(f"  校准结果: {scale:.2f}x")

    print()
    print("=" * 62)
    print("3. 用不同缩放去匹配（验证「差一点就匹配不到」）")
    print("=" * 62)
    screen = main.grab_region(sct, main.window_region(sct, win))
    tpl = main.load_template(config.GREET_IMAGE)
    for s in (0.8, 0.9, 1.0, 1.1, 1.25, 1.5):
        t = main._scale_template(tpl, s)
        score = main._best_score(screen, t)
        flag = "命中" if score >= config.CONFIDENCE else "匹配失败"
        print(f"  {s:.2f}x → 模板 {t.shape[1]:>3}x{t.shape[0]:<3} 分数 {score:.4f}  {flag}")

    print()
    print("=" * 62)
    print("4. 校准后实际检测")
    print("=" * 62)
    for name, tpl in (("打招呼", greet), ("继续沟通", cont)):
        r = main.find_all_templates_in_region(sct, tpl, main.window_region(sct, win), config.CONFIDENCE)
        if r is None:
            print(f"  {name}: 未检测到（页面上可能没有这个按钮）")
        else:
            print(f"  {name}: ({r[0]}, {r[1]}) 分数 {r[2]:.4f} 尺寸 {r[3]}x{r[4]}")

    print()
    print("=" * 62)
    print("5. 强制用错误缩放（模拟改了 DPI 但没重算）")
    print("=" * 62)
    wrong = 0.8 if abs(scale - 0.8) > 0.05 else 1.25
    r = main.find_all_templates_in_region(sct, greet, main.window_region(sct, win),
                                          config.CONFIDENCE, scale=wrong)
    print(f"  用 {wrong:.2f}x 去匹配: {'居然命中了 ' + str(r[:2]) if r else '找不到（符合预期，这正是自动校准要解决的问题）'}")
