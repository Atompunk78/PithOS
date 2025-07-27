import micropython
from random import random

@micropython.native
def Pressed(pin) -> bool:
    return not pin.value()

def DrawText(display, font, msg, x, y, fg, bg, jx=0, jy=0):
    w  = len(msg) * font.WIDTH
    h  = font.HEIGHT
    ax = int(x - w * jx)
    ay = int(y - h * jy)
    display.text(font, msg, ax, ay, fg, bg)

@micropython.native
def WrapText(msg: str, maxChars: int) -> list:
    lines   = []
    pending = ""

    for paragraph in msg.split("\n"):
        words = paragraph.split(" ")
        for word in words:
            if not word:
                continue
            if not pending:
                pending = word
            elif len(pending) + 1 + len(word) <= maxChars:
                pending += " " + word
            else:
                lines.append(pending)
                pending = word

        lines.append(pending)
        pending = ""

    if pending:
        lines.append(pending)

    return lines

def BellCurve(mean: float, sigma: float = 1.0, lo: float = None, hi: float = None) -> float:
    z = sum(random() for _ in range(12)) - 6
    val = mean + sigma * z
    if lo is not None and val < lo: val = lo
    if hi is not None and val > hi: val = hi
    return val
