# -*- coding: utf-8 -*-
"""只检测 + 滚动，不点击。用来验证主循环能不能持续找到「打招呼」，
以及滚动判定是否靠谱。跑完把页面滚回原位（滚轮反向）。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mss
import main
import config

greet = main.load_template(config.GREET_IMAGE)
cont = main.load_template(config.CONTINUE_IMAGE)
if greet is None or cont is None:
    print("模板缺失")
    sys.exit(1)

win = main.get_window(config.WINDOW_TITLE)
if win is None:
    print("没找到浏览器窗口")
    sys.exit(1)
print(f"窗口: {win.title!r} rect=({win.left},{win.top},{win.width},{win.height})")

with mss.MSS() as sct:
    region = main.window_region(sct, win)
    print("截图区域:", region)

    for r in range(1, 5):
        print(f"\n----- 第 {r} 轮 -----")
        region = main.window_region(sct, win)
        g = main.find_all_templates_in_region(sct, greet, region, config.CONFIDENCE)
        c = main.find_all_templates_in_region(sct, cont, region, config.CONFIDENCE)
        print(f"  打招呼按钮: {g}")
        print(f"  继续沟通按钮: {c}")
        if g is None:
            before = main.grab_region(sct, region)
            path = main.save_debug(sct, region, "probe_nogreet")
            print(f"  现场图: {path}")
            ok = main.scroll_down(sct, win, config.SCROLL_AMOUNT)
            print(f"  滚动结果: {ok}")
        else:
            # 验证"变化检测"对滚动是否敏感（滚了再滚回来）
            before = main.grab_region(sct, region)
            main.move_cursor(region[0] + region[2] // 2, region[1] + region[3] // 2)
            main.send_wheel(-60)
            main.stop.sleep(0.8)
            ratio = main.change_ratio(before, main.grab_region(sct, region))
            print(f"  小幅滚动(-60)后变化像素占比: {ratio:.4f}  (阈值 {config.CHANGE_RATIO})")
            main.send_wheel(60)
            main.stop.sleep(0.8)

print("\n完成（未点击任何按钮）")
