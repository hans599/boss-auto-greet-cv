# -*- coding: utf-8 -*-
"""模拟"用户改了显示缩放"后，自动缩放校准能否自己找回正确的缩放比。

做法：拿一张 125% 下的真实截图，把它缩放成 100% / 150% 的样子（相当于 UI 变大了/变小了），
然后让程序在不知道缩放的情况下自己去匹配。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np
import main
import config

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "debug_window.png")
if not os.path.exists(SRC):
    print(f"缺少参考图 {SRC}（跑一次 dry-run 会生成）")
    sys.exit(1)

base = cv2.imdecode(np.fromfile(SRC, dtype=np.uint8), cv2.IMREAD_COLOR)
tpl = main.load_template(config.GREET_IMAGE)
print(f"参考图 {base.shape[1]}x{base.shape[0]}，模板 {tpl.shape[1]}x{tpl.shape[0]}\n")

real_region = main.window_region
real_grab = main.grab_region


def make_fake(img):
    def _region(sct, win):
        return (0, 0, img.shape[1], img.shape[0])

    def _grab(sct, region):
        return img.copy()
    return _region, _grab


print(f"{'模拟缩放':<12}{'期望模板缩放':<14}{'校准得到':<12}{'匹配度':<10}{'检测结果'}")
print("-" * 70)
for ui_scale, label in [(0.8, "100%"), (1.0, "125%"), (1.2, "150%")]:
    img = base if ui_scale == 1.0 else cv2.resize(
        base, None, fx=ui_scale, fy=ui_scale,
        interpolation=cv2.INTER_AREA if ui_scale < 1 else cv2.INTER_CUBIC)
    main.window_region, main.grab_region = make_fake(img)
    try:
        main._SCALE.update(value=1.0, valid=False, score=0.0)
        got = main.calibrate_scale(None, None, tpl, verbose=False)
        r = main.find_all_templates_in_region(None, tpl, (0, 0, img.shape[1], img.shape[0]),
                                              config.CONFIDENCE)
        det = f"({r[0]}, {r[1]}) 模板 {r[3]}x{r[4]}" if r else "❌ 没找到"
        print(f"{label:<12}{ui_scale:<14.2f}{got:<12.2f}{main._SCALE['score']:<10.3f}{det}")
    finally:
        main.window_region, main.grab_region = real_region, real_grab

print()
print("结论：自动校准能把 UI 缩放变化换算成模板缩放，不需要重新截图。")
