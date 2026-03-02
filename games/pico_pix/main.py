from machine import Pin, SPI
import st7789
import vga2_8x16 as font8
from time import sleep, ticks_ms
import os
import struct
import utime
import gc
import micropython

from atomic import graphics, utilities
from atomic import Pressed

spi = SPI(1, baudrate=60000000, polarity=1, phase=1,
          sck=Pin(10), mosi=Pin(11))

display = st7789.ST7789(
    spi, 240, 240,
    reset=Pin(12, Pin.OUT),
    dc=Pin(8, Pin.OUT),
    cs=Pin(9, Pin.OUT),
    rotation=1
)

Pin(13, Pin.OUT).value(1)

try:
    display.init()
except Exception as e:
    print(f"{e}\nSome systems don't require display.init() and crash when they see it, including yours, so I've skipped the line automatically and it should run normally now - if not, you will have to debug the error manually")

iUp     = Pin(2,  Pin.IN, Pin.PULL_UP)
iDown   = Pin(18, Pin.IN, Pin.PULL_UP)
iLeft   = Pin(16, Pin.IN, Pin.PULL_UP)
iRight  = Pin(20, Pin.IN, Pin.PULL_UP)
iCentre = Pin(3,  Pin.IN, Pin.PULL_UP)
iA      = Pin(15, Pin.IN, Pin.PULL_UP)
iB      = Pin(17, Pin.IN, Pin.PULL_UP)
iX      = Pin(19, Pin.IN, Pin.PULL_UP)
iY      = Pin(21, Pin.IN, Pin.PULL_UP)

BLACK = graphics.RGBto565(0, 0, 0)
WHITE = graphics.RGBto565(255, 255, 255)

MAGIC = b"PICO"
FMT_MONO1 = 0
FMT_RGB565 = 1

# Header (16 bytes):
# 0..3   "PICO"
# 4..5   w (uint16 LE)
# 6..7   h (uint16 LE)
# 8      fmt (uint8)
# 9..12  unixTs (uint32 LE)
# 13..15 reserved (3 bytes)

UNIX_EPOCH_OFFSET_2000 = 946684800  # seconds between 1970-01-01 and 2000-01-01

BAYER_4X4 = (
    (0,  8,  2, 10),
    (12, 4, 14,  6),
    (3, 11,  1,  9),
    (15, 7, 13,  5),
)

# Fast MONO1 -> RGB565 row expansion
@micropython.viper
def _mono_expand_row(out_buf: ptr8, row_buf: ptr8,
                        full_bytes: int, rem_bits: int, invert: int,
                        w_hi: int, w_lo: int, b_hi: int, b_lo: int):
    out_i = 0
    j = 0
    while j < full_bytes:
        b = row_buf[j]
        if invert:
            b ^= 0xFF
        # Bits 7..0
        k = 7
        while k >= 0:
            if (b >> k) & 1:
                out_buf[out_i] = w_hi
                out_buf[out_i + 1] = w_lo
            else:
                out_buf[out_i] = b_hi
                out_buf[out_i + 1] = b_lo
            out_i += 2
            k -= 1
        j += 1

    if rem_bits:
        b = row_buf[full_bytes]
        if invert:
            b ^= 0xFF
        k = 7
        # take only rem_bits from MSB downward
        while (7 - k) < rem_bits:
            if (b >> k) & 1:
                out_buf[out_i] = w_hi
                out_buf[out_i + 1] = w_lo
            else:
                out_buf[out_i] = b_hi
                out_buf[out_i + 1] = b_lo
            out_i += 2
            k -= 1

# Expand 1 MONO1 byte (8 pixels) to 16 bytes of RGB565 using a LUT
def _BuildMonoLut(white565, black565):
    whi = white565 >> 8; wlo = white565 & 0xFF
    bhi = black565 >> 8; blo = black565 & 0xFF
    table = []
    for b in range(256):
        row = bytearray(16)
        k = 0
        for bitpos in range(7, -1, -1):
            if (b >> bitpos) & 1:
                row[k] = whi; row[k+1] = wlo
            else:
                row[k] = bhi; row[k+1] = blo
            k += 2
        table.append(bytes(row))
    return tuple(table)

MONO_LUT = _BuildMonoLut(WHITE, BLACK)

# Flattened 256x16-byte LUT for fast Viper copying
MONO_LUT_BYTES = b"".join(MONO_LUT)

# Fast multi-row MONO1 -> RGB565 expansion using flattened LUT
@micropython.viper
def _mono_expand_rows_lut(out_buf: ptr8, in_buf: ptr8,
                          stride: int, rows: int,
                          full_bytes: int, rem_bits: int, invert: int,
                          lut: ptr8):
    out_i = 0
    row_i = 0
    r = 0
    while r < rows:
        j = 0
        while j < full_bytes:
            b = in_buf[row_i + j]
            if invert:
                b ^= 0xFF
            lut_i = b << 4  # *16
            k = 0
            while k < 16:
                out_buf[out_i] = lut[lut_i + k]
                out_i += 1
                k += 1
            j += 1

        if rem_bits:
            b = in_buf[row_i + full_bytes]
            if invert:
                b ^= 0xFF
            lut_i = b << 4
            need = rem_bits << 1
            k = 0
            while k < need:
                out_buf[out_i] = lut[lut_i + k]
                out_i += 1
                k += 1

        row_i += stride
        r += 1


def EnsureExt(path, ext):
    if path.lower().endswith(ext):
        return path
    return path + ext

def ReadExact(f, buf, nBytes):
    view = memoryview(buf)
    got = 0
    while got < nBytes:
        n = f.readinto(view[got:nBytes])
        if n is None:
            n = 0
        if n == 0:
            raise ValueError("Unexpected EOF")
        got += n

def UnpackHeader16(h16):
    if len(h16) != 16:
        raise ValueError("Header must be 16 bytes")
    magic, w, h, fmt, unixTs = struct.unpack("<4sHHBI", h16[:13])
    return magic, w, h, fmt, unixTs

def PackHeader16(w, h, fmt, unixTs):
    return struct.pack("<4sHHBI", MAGIC, w, h, fmt, unixTs) + (b"\x00" * 3)

def GetUnixTimeOrZero():
    try:
        t2000 = utime.time()
        if t2000 < 365 * 24 * 60 * 60:
            return 0
        return t2000 + UNIX_EPOCH_OFFSET_2000
    except:
        return 0

def Rgb565BeToLuma8(hb, lb):
    c = (hb << 8) | lb

    r5 = (c >> 11) & 31
    g6 = (c >> 5) & 63
    b5 = c & 31

    r = (r5 * 255) // 31
    g = (g6 * 255) // 63
    b = (b5 * 255) // 31

    return (77 * r + 150 * g + 29 * b) >> 8

def Rgb565To1Bit(inPath, outPath, copyTimestamp=True):
    with open(inPath, "rb") as fin:
        header = fin.read(16)
        magic, width, height, fmt, unixTsIn = UnpackHeader16(header)

        if magic != MAGIC:
            raise ValueError("Unable to open file (incorrect format)")
        if fmt != FMT_RGB565:
            raise ValueError("Unable to open file (it is not RGB565)")

        stride = (width + 7) >> 3
        rowBytes = width << 1

        rowBuf = bytearray(rowBytes)
        outRow = bytearray(stride)

        if copyTimestamp:
            unixTsOut = unixTsIn
        else:
            unixTsOut = GetUnixTimeOrZero()

        # If input timestamp missing, but Pico time exists, use it
        if unixTsOut == 0:
            maybe = GetUnixTimeOrZero()
            if maybe != 0:
                unixTsOut = maybe

        outHeader = PackHeader16(width, height, FMT_MONO1, unixTsOut)

        with open(outPath, "wb") as fout:
            fout.write(outHeader)

            for y in range(height):
                ReadExact(fin, rowBuf, rowBytes)

                # Clear outRow
                for j in range(stride):
                    outRow[j] = 0

                i = 0
                yMod = y & 3

                for x in range(width):
                    hb = rowBuf[i]
                    lb = rowBuf[i + 1]
                    i += 2

                    L = Rgb565BeToLuma8(hb, lb)

                    mv = BAYER_4X4[yMod][x & 3]
                    threshold = mv << 4  # *16

                    if L > threshold:
                        bytePos = x >> 3
                        bitPos = 7 - (x & 7)
                        outRow[bytePos] |= (1 << bitPos)

                fout.write(outRow)

def RenderPicToDisplay(path, invertMono=False, x0=0, y0=0, max_w=240, max_h=200):
    with open(path, "rb") as f:
        header = f.read(16)
        magic, w, h, fmt, unixTs = UnpackHeader16(header)

        if magic != MAGIC:
            raise ValueError("Unable to open file (incorrect format)")

        w_lim = w if w <= max_w else max_w
        h_lim = h if h <= max_h else max_h

        if fmt == FMT_RGB565:
            # Full-image buffer when no cropping; otherwise per-row crop
            rowBytes = w << 1
            if w_lim == w:
                need = rowBytes * h_lim
                buf = bytearray(need)
                ReadExact(f, buf, need)
                display.blit_buffer(buf, x0, y0, w_lim, h_lim)
                # Skip remaining rows if needed
                if h > h_lim:
                    to_skip = (h - h_lim) * rowBytes
                    while to_skip > 0:
                        n = f.read(min(2048, to_skip))
                        if not n:
                            break
                        to_skip -= len(n)
            else:
                # Crop width by packing a contiguous buffer, then single blit
                rowBuf = bytearray(rowBytes)
                wlimBytes = w_lim << 1
                out = bytearray(wlimBytes * h_lim)
                ov = memoryview(out)
                for y in range(h_lim):
                    ReadExact(f, rowBuf, rowBytes)
                    start = y * wlimBytes
                    ov[start:start + wlimBytes] = rowBuf[:wlimBytes]
                display.blit_buffer(out, x0, y0, w_lim, h_lim)
                # Skip remaining rows if needed
                if h > h_lim:
                    to_skip = (h - h_lim) * rowBytes
                    while to_skip > 0:
                        n = f.read(min(2048, to_skip))
                        if not n:
                            break
                        to_skip -= len(n)

        elif fmt == FMT_MONO1:
            # Full-image mono read for max performance, then expand in one call
            stride = (w + 7) >> 3
            full_bytes = w_lim >> 3
            rem_bits = w_lim & 7

            need_in = stride * h_lim
            inAll = bytearray(need_in)
            ReadExact(f, inAll, need_in)

            outAll = bytearray((w_lim << 1) * h_lim)
            _mono_expand_rows_lut(memoryview(outAll), memoryview(inAll),
                                  stride, h_lim, full_bytes, rem_bits,
                                  1 if invertMono else 0, memoryview(MONO_LUT_BYTES))

            display.blit_buffer(outAll, x0, y0, w_lim, h_lim)

            # Consume remaining rows beyond crop, if any
            if h > h_lim:
                to_skip = (h - h_lim) * stride
                skipBuf = bytearray(min(2048, stride * 8))
                while to_skip > 0:
                    n = f.readinto(skipBuf)
                    if not n:
                        break
                    to_skip -= n

        else:
            raise ValueError("Unable to open file (incorrect format)")


def DecodePicToRgb565(path, invertMono=False, max_w=240, max_h=200):
    """
    Fully decode picture into an RGB565 bytearray (row-major), cropped to max_w x max_h.
    Returns (w_lim, h_lim, buf).
    """
    with open(path, "rb") as f:
        header = f.read(16)
        magic, w, h, fmt, unixTs = UnpackHeader16(header)
        if magic != MAGIC:
            raise ValueError("Unable to open file (incorrect format)")

        w_lim = w if w <= max_w else max_w
        h_lim = h if h <= max_h else max_h
        buf = bytearray(w_lim * h_lim * 2)
        bv = memoryview(buf)

        if fmt == FMT_RGB565:
            rowBytes = w << 1
            rowBuf = bytearray(rowBytes)
            for y in range(h_lim):
                ReadExact(f, rowBuf, rowBytes)
                start = y * (w_lim << 1)
                bv[start:start + (w_lim << 1)] = rowBuf[: (w_lim << 1)]
            # Skip extra rows if any
            if h > h_lim:
                to_skip = (h - h_lim) * rowBytes
                while to_skip > 0:
                    n = f.read(min(512, to_skip))
                    if not n:
                        break
                    to_skip -= len(n)

        elif fmt == FMT_MONO1:
            stride = (w + 7) >> 3
            row = bytearray(stride)

            full_bytes = w_lim >> 3
            rem_bits = w_lim & 7
            for y in range(h_lim):
                ReadExact(f, row, stride)
                line_off = y * (w_lim << 1)
                out_idx = line_off

                # Expand 8 pixels at a time
                for j in range(full_bytes):
                    b = row[j]
                    if invertMono:
                        b ^= 0xFF
                    chunk = MONO_LUT[b]
                    bv[out_idx: out_idx + 16] = chunk
                    out_idx += 16

                if rem_bits:
                    b = row[full_bytes]
                    if invertMono:
                        b ^= 0xFF
                    chunk = MONO_LUT[b]
                    need = rem_bits << 1
                    bv[out_idx: out_idx + need] = chunk[:need]

            # Consume remaining rows if any
            if h > h_lim:
                for _ in range(h - h_lim):
                    ReadExact(f, row, stride)

        else:
            raise ValueError("Unable to open file (incorrect format)")

        return w_lim, h_lim, buf

def _basename(p):
    try:
        i = p.rfind('/')
        return p[i+1:] if i >= 0 else p
    except Exception:
        return p

def DrawBottomUI(filename: str, showCompress: bool, leftOverride: str = None):
    # White 240x40 bar with black text
    display.fill_rect(0, 200, 240, 40, WHITE)
    if not font8:
        return
    try:
        name = filename or ""
        utilities.DrawText(display, font8, name, 10, 204, BLACK, WHITE, 0, 0)
        if leftOverride is not None:
            utilities.DrawText(display, font8, leftOverride, 10, 220, BLACK, WHITE, 0, 0)
        elif showCompress:
            utilities.DrawText(display, font8, "A: Compress", 10, 220, BLACK, WHITE, 0, 0)
        utilities.DrawText(display, font8, "B: Delete", 230, 220, BLACK, WHITE, 1, 0)
    except Exception:
        pass

def GetPicFormat(path):
    try:
        with open(path, "rb") as f:
            h = f.read(16)
        magic, w, hgt, fmt, ts = UnpackHeader16(h)
        if magic != MAGIC:
            return -1
        return fmt
    except Exception:
        return -1

def ConvertRgb565ToMonoInPlace(path: str) -> bool:
    try:
        fmt = GetPicFormat(path)
        if fmt != FMT_RGB565:
            return False
        tmp = path + ".tmp"
        Rgb565To1Bit(path, tmp, copyTimestamp=True)
        try:
            os.remove(path)
        except Exception:
            pass
        try:
            os.rename(tmp, path)
        except Exception:
            with open(tmp, 'rb') as fi, open(path, 'wb') as fo:
                while True:
                    b = fi.read(2048)
                    if not b:
                        break
                    fo.write(b)
            try:
                os.remove(tmp)
            except Exception:
                pass
        return True
    except Exception as e:
        print("compress failed:", e)
        try:
            os.remove(path + ".tmp")
        except Exception:
            pass
        return False

def GetPicDims(path):
    try:
        with open(path, "rb") as f:
            h = f.read(16)
        magic, w, hgt, fmt, ts = UnpackHeader16(h)
        if magic != MAGIC:
            return 0, 0
        return w, hgt
    except Exception:
        return 0, 0

def IsCropped(path, max_w=240, max_h=200):
    w, h = GetPicDims(path)
    return (w > max_w) or (h > max_h)

def GetPicTimestamp(path):
    try:
        with open(path, "rb") as f:
            header = f.read(16)
            magic, w, h, fmt, unixTs = UnpackHeader16(header)
            if magic != MAGIC:
                return 0
            return unixTs or 0
    except Exception:
        try:
            st = os.stat(path)
            return st[8] if len(st) > 8 else 0
        except Exception:
            return 0

def ListPicsSorted(baseDir="assets"):
    try:
        names = os.listdir(baseDir)
    except Exception:
        names = []

    pics = []
    for n in names:
        if not n.lower().endswith(".pic"):
            continue
        p = baseDir + "/" + n
        ts = GetPicTimestamp(p)
        pics.append((p, ts))

    # Oldest first; alphabetical by name when timestamps equal
    pics.sort(key=lambda t: (t[1], t[0].lower()))
    return [p for p, _ in pics]


def ShowImage(path):
    # Clear image area (top 240x200)
    display.fill_rect(0, 0, 240, 200, WHITE)
    try:
        # Stream directly to display so content appears progressively
        RenderPicToDisplay(path, invertMono=False, x0=0, y0=0, max_w=240, max_h=200)
    except Exception as e:
        display.fill_rect(0, 0, 240, 200, WHITE)
        print("pico_pix render error:", e)
    finally:
        gc.collect()


# Entry flow in module scope (no Run wrapper)
files = ListPicsSorted("assets")

if not files:
    # Nothing to show; keep screen blanked image area and draw UI
    display.fill_rect(0, 0, 240, 200, WHITE)
    DrawBottomUI("No images", False)
else:
    idx = 0
    ShowImage(files[idx])
    fname = _basename(files[idx]) + (" (cropped)" if IsCropped(files[idx]) else "")
    DrawBottomUI(fname, GetPicFormat(files[idx]) == FMT_RGB565)

    prevLeft = False
    prevRight = False
    prevA = False
    prevB = False

    while True:
        r = Pressed(iRight)
        l = Pressed(iLeft)
        a = Pressed(iA)
        b = Pressed(iB)

        if r and not prevRight:
            idx = (idx + 1) % len(files)
            fname = _basename(files[idx]) + (" (cropped)" if IsCropped(files[idx]) else "")
            DrawBottomUI(fname, GetPicFormat(files[idx]) == FMT_RGB565)
            ShowImage(files[idx])
        elif l and not prevLeft:
            idx = (idx - 1) % len(files)
            fname = _basename(files[idx]) + (" (cropped)" if IsCropped(files[idx]) else "")
            DrawBottomUI(fname, GetPicFormat(files[idx]) == FMT_RGB565)
            ShowImage(files[idx])

        if a and not prevA:
            # Compress current if RGB565
            p = files[idx]
            if GetPicFormat(p) == FMT_RGB565:
                # Show immediate UI feedback
                fname_disp = _basename(p) + (" (cropped)" if IsCropped(p) else "")
                DrawBottomUI(fname_disp, True, leftOverride="Compressing...")
                if ConvertRgb565ToMonoInPlace(p):
                    fname = _basename(p) + (" (cropped)" if IsCropped(p) else "")
                    DrawBottomUI(fname, GetPicFormat(p) == FMT_RGB565)
                    ShowImage(p)
                else:
                    fname = _basename(p) + (" (cropped)" if IsCropped(p) else "")
                    DrawBottomUI(fname, GetPicFormat(p) == FMT_RGB565)
                    ShowImage(p)

        if b and not prevB:
            # Delete current and move to next
            p = files[idx]
            try:
                os.remove(p)
            except Exception as e:
                print("delete failed:", e)
            # Update list
            try:
                files.pop(idx)
            except Exception:
                # Rebuild as fallback
                files = ListPicsSorted("assets")
                if idx >= len(files):
                    idx = 0
            if not files:
                display.fill_rect(0, 0, 240, 200, WHITE)
                DrawBottomUI("No images", False)
            else:
                if idx >= len(files):
                    idx = 0
                    fname = _basename(files[idx]) + (" (cropped)" if IsCropped(files[idx]) else "")
                    DrawBottomUI(fname, GetPicFormat(files[idx]) == FMT_RGB565)
                    ShowImage(files[idx])

        prevRight = r
        prevLeft = l
        prevA = a
        prevB = b
        sleep(0.02)
