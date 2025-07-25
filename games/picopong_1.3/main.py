from machine import Pin, SPI
from time import sleep, ticks_us
import st7789
import vga2_16x32 as font16
import vga2_8x16 as font8
from random import randint, choice

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

def color565(r, g, b):
    return ((r & 0xf8) << 8) | ((g & 0xfc) << 3) | (b >> 3)

iUp     = Pin(2,  Pin.IN, Pin.PULL_UP)
iDown   = Pin(18, Pin.IN, Pin.PULL_UP)
iLeft   = Pin(16, Pin.IN, Pin.PULL_UP)
iRight  = Pin(20, Pin.IN, Pin.PULL_UP)
iCentre = Pin(3,  Pin.IN, Pin.PULL_UP)
iA      = Pin(15, Pin.IN, Pin.PULL_UP)
iB      = Pin(17, Pin.IN, Pin.PULL_UP)
iX      = Pin(19, Pin.IN, Pin.PULL_UP)
iY      = Pin(21, Pin.IN, Pin.PULL_UP)

BLACK  = color565(0, 0, 0)
WHITE  = color565(255, 255, 255)
RED    = color565(255, 0, 0)
BLUE   = color565(0, 0, 255)
PURPLE = color565(79, 0, 191)

def LoadGameInfo():
    with open("info.info", "r") as f:
        return eval(f.read())

gameInfo = LoadGameInfo()
version = f"v{gameInfo['version']}"

def Pressed(pin):
    return pin.value() == 0

def DrawText(font_module, msg, x, y, colour, jx=0, jy=0):
    w = len(msg) * font_module.WIDTH
    h = font_module.HEIGHT
    ax = int(x - w * jx)
    ay = int(y - h * jy)
    display.text(font_module, msg, ax, ay, colour)

class Object: #square object with position, size, speed, and subpixel pos, in each dimension
    def __init__(self, x, y, rx, ry, dx, dy):
        self.x = x #pixel position; int
        self.y = y
        self.rx = rx #radius; int
        self.ry = ry
        self.dx = dx #speed; float
        self.dy = dy
        self.sx = x #subpixel pos; float
        self.sy = y

class Mode:
    def __init__(self, name, ballSize, paddleSize, ballSpeed, paddleSpeed, 
                 ballSpeedIncrease, paddleSpeedIncrease, scoreIncrease, colour):
        self.name = name
        self.ballSize = ballSize
        self.paddleSize = paddleSize
        self.ballSpeed = ballSpeed
        self.paddleSpeed = paddleSpeed
        self.ballSpeedIncrease = ballSpeedIncrease
        self.paddleSpeedIncrease = paddleSpeedIncrease
        self.scoreIncrease = scoreIncrease
        self.colour = colour #currently unused

def CheckPaddle(paddle):
    if not (Pressed(iLeft) == Pressed(iRight)):
        if Pressed(iLeft):
            paddle.dx = -mode.paddleSpeed
        if Pressed(iRight):
            paddle.dx = mode.paddleSpeed
    else:
        paddle.dx = 0

def MoveObject(obj):
    obj.sx += obj.dx
    obj.sy += obj.dy
    obj.x = int(obj.sx)
    obj.y = int(obj.sy)
    
def Bounce(obj):
    if obj == paddle:
        if paddle.sx < paddle.rx:
            paddle.sx = paddle.rx
            paddle.x = paddle.rx
        elif paddle.sx > 240-paddle.rx:
            paddle.sx = 240-paddle.rx
            paddle.x = 240-paddle.rx
    else:
        if ball.x <= ball.rx or ball.x >= 240-ball.rx:
            ball.dx = -ball.dx
        if ball.y <= ball.ry or ball.y >= 240-ball.ry:
            ball.dy = -ball.dy

def CheckDeath(ball):
    if ball.y >= 240-ball.ry:
        return "Game Over"
    else:
        return "Main"

def PaddleCollision(ball, paddle):
    if (
        ball.dy > 0 and #ball is moving down
        abs(ball.x - paddle.x) < ball.rx + paddle.rx and #X overlap
        ball.y + ball.ry >= paddle.y - paddle.ry and #ball bottom is below paddle top
        ball.y - ball.ry <= paddle.y - paddle.ry #ball top is above paddle top
    ):
        ball.dx += mode.ballSpeedIncrease * (1 if ball.dx >= 0 else -1)
        ball.dy = -abs(ball.dy + mode.ballSpeedIncrease)
        mode.paddleSpeed += mode.paddleSpeedIncrease
        return mode.scoreIncrease
    else:
        return 0

def DrawObject(obj, colour=WHITE):
    display.fill_rect(obj.x-obj.rx, obj.y-obj.ry, obj.rx * 2, obj.ry * 2, colour)

def ShowFPS(lastFrameStart):
    frametime = ticks_us() - lastFrameStart
    DrawText(font8, str("{:.2f}ms".format(frametime/1000)), 236, 2, WHITE, 1, 0)

def DetermineMode(btn):
    global mode
    if btn == iA: #name, ball size, paddle width, ball speed, paddle speed, ball speed increase, paddle speed increase, score increase, colour
        mode = Mode("Normal", 4, 20, 1, 2, 0.1, 0.05, 10, "WHITE")
    elif btn == iB:
        mode = Mode("Hard", 4, 16, 1.5, 2.25, 0.2, 0.1, 20, "RED")
    elif btn == iX:
        mode = Mode("Insane", 4, 12, 2, 2, 0.2, 0.2, 30, "PURPLE")
    elif btn == iY:
        mode = Mode("Endurance", 4, 20, 2, 2.5, 0.025, 0.0125, 5, "BLUE")
    return mode


scene = "Start"
gameTime = ticks_us()
targetFps = 60
display.fill(BLACK)

while True:
    frameStart = ticks_us()
    if scene == "Start":
        DrawText(font16, "PicoPong", 120, 108, WHITE, 0.5, 0.5)
        DrawText(font8, "Press A to Start", 120, 144, WHITE, 0.5, 0.5)
        DrawText(font8, version, 4, 2, WHITE, 0, 0)
        for btn in [iA, iB, iX, iY]:
            if Pressed(btn):
                pressedButton = btn
                mode = DetermineMode(btn)
                ball = Object(randint(40, 200), 40, mode.ballSize, mode.ballSize, choice([-mode.ballSpeed,mode.ballSpeed]), choice([-mode.ballSpeed,mode.ballSpeed]))
                paddle = Object(120, 200, mode.paddleSize, mode.ballSize, 0, 0)
                points = 0
                while Pressed(pressedButton):
                    sleep(0.001)
                scene = "Main"
                display.fill(BLACK)

    elif scene == "Main":
        CheckPaddle(paddle)
        DrawObject(ball, BLACK) #draw over the previous positions in black to erase
        DrawObject(paddle, BLACK)
        MoveObject(ball)
        MoveObject(paddle)
        scene = CheckDeath(ball) #must be put between moving and edge-checking
        Bounce(ball)
        Bounce(paddle)
        points += PaddleCollision(ball, paddle)
        DrawObject(ball)
        DrawObject(paddle)
        DrawText(font8, str(points), 4, 2, WHITE)
        #ShowFPS(frameStart) #optional for debug
        if scene == "Game Over":
            display.fill(BLACK)
        
    elif scene == "Game Over":
        DrawText(font16, "GAME OVER", 120, 80, WHITE, 0.5, 0.5) #colour is unused for visual style reasons
        DrawText(font16, "Score", 120, 124, WHITE, 0.5, 0.5)
        DrawText(font16, str(points), 120, 160, WHITE, 0.5, 0.5)
        DrawText(font8, mode.name+" mode", 120, 238, WHITE, 0.5, 1)
        for btn in [iA, iB, iX, iY]:
            if Pressed(btn):
                while Pressed(btn):
                    sleep(0.001)
                scene = "Start"
                display.fill(BLACK)

    sleep(max(0, ((1000000/targetFps) - (ticks_us() - frameStart)) / 1000000))
