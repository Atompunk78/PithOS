from machine import Pin, SPI
import st7789
import os, sys, gc
from time import sleep, ticks_ms
import vga2_16x32 as font16
import vga2_8x16 as font8

from atomic import utilities, Pressed, RGBto565
from atomic import __version__ as atomicVersion

spi = SPI(1, baudrate=60000000, polarity=1, phase=1,
          sck=Pin(10), mosi=Pin(11))

display = st7789.ST7789(
    spi, 240, 240,
    reset=Pin(12, Pin.OUT),
    dc=Pin(8,  Pin.OUT),
    cs=Pin(9,  Pin.OUT),
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

BLACK = RGBto565(0, 0, 0)
WHITE = RGBto565(255, 255, 255)
GREY  = RGBto565(215, 215, 215)

# Copyright (c) 2025 Henry Gurney
# Licensed under CC BY-NC-ND 4.0

sys.path.append("/")
version = "v1.2"
frameRate = 60

lastButtonTime = {
    'up': 0, 'down': 0, 'a': 0
}

def CanPressButton(buttonName, minDelay=250):
    currentTime = ticks_ms()
    if currentTime - lastButtonTime[buttonName] >= minDelay:
        lastButtonTime[buttonName] = currentTime
        return True
    return False

def Text16(msg, x, y, jx=0, jy=0, fg=BLACK, bg=WHITE):
    utilities.DrawText(display, font16, msg, x, y, fg, bg, jx, jy)

def Text8(msg, x, y, jx=0, jy=0, fg=BLACK, bg=WHITE):
    utilities.DrawText(display, font8, msg, x, y, fg, bg, jx, jy)

def CenterX(w):
    return (240 - w) // 2

def CompareVersions(installed, required):
    if not required or not installed:
        return True
    
    installedParts = [int(x) for x in installed.split('.')]
    requiredParts = [int(x) for x in required.split('.')]
    
    # Pad shorter version with zeros
    maxLen = max(len(installedParts), len(requiredParts))
    installedParts += [0] * (maxLen - len(installedParts))
    requiredParts += [0] * (maxLen - len(requiredParts))
    
    # Compare each part individually
    for i in range(maxLen):
        if installedParts[i] > requiredParts[i]:
            return True  # Installed version is higher
        elif installedParts[i] < requiredParts[i]:
            return False  # Installed version is lower
    
    return True  # Versions are equal

def LoadGames(base="games"):    
    games = []
    for entry in os.listdir(base):
        fullPath = f"{base}/{entry}"
        try:
            stat = os.stat(fullPath)[0]
        except:
            continue

        if stat & 0x4000 and "main.py" in os.listdir(fullPath):
            title, desc, gameVersion, reqAtomic, priority = entry, "", "", "", 0
            infoPath = f"{fullPath}/info.info"
            if "info.info" in os.listdir(fullPath):
                try:
                    meta = eval(open(infoPath).read())
                    title = meta.get("title", title)
                    desc  = meta.get("description", "")
                    gameVersion = meta.get("version", "")
                    reqAtomic = meta.get("reqAtomic", "")
                    priority = int(meta.get("priority", 1))
                except:
                    title, desc, gameVersion, reqAtomic, priority = "ERROR", "Error loading game information", "", "", 0
            else:
                title, desc, gameVersion, reqAtomic, priority = "ERROR", "No game information found", "", "", 0
            games.append((title, desc, gameVersion, reqAtomic, f"{fullPath}/main.py", priority))
    return sorted(games, key=lambda g: (-g[5], g[0].lower()))

boxW          = 224
boxH          = 96
leftX         = 8
startY        = 16
paddingY      = 16
maxVisible    = 2
titleOffset   = 8
descOffset    = 44

def DrawMenu(games, sel, scroll):
    display.fill(WHITE)
    visible = games[scroll:scroll + maxVisible]
    y = startY
    for localIdx, (title, desc, gameVersion, reqAtomic, _, priority) in enumerate(visible):
        realIdx = scroll + localIdx
        highlighted = (realIdx == sel)

        if highlighted:
            display.fill_rect(leftX, y, boxW, boxH, GREY)
        display.rect(leftX, y, boxW, boxH, BLACK)

        Text16(title[:12], 120, y + titleOffset, jx=0.5, jy=0,
              fg=BLACK, bg=GREY if highlighted else WHITE)

        versionOk = CompareVersions(atomicVersion, reqAtomic)
        
        if not versionOk and reqAtomic:
            # Show error message on separate lines
            Text8(f"Requires Atomic v{reqAtomic}", 120, y + descOffset, jx=0.5, jy=0,
                  fg=BLACK, bg=GREY if highlighted else WHITE)
            Text8(f"Installed: v{atomicVersion}", 120, y + descOffset + 16, jx=0.5, jy=0,
                  fg=BLACK, bg=GREY if highlighted else WHITE)
        else:
            # description (wrap to lines of max 26 chars, word-aware)
            descLines = []
            words = desc.split()
            currentLine = ""
            
            for word in words:
                if len(currentLine + word) <= 26:
                    currentLine += word + " "
                else:
                    if currentLine:
                        descLines.append(currentLine.strip())
                    currentLine = word + " "
            
            if currentLine:
                descLines.append(currentLine.strip())
            
            for j, line in enumerate(descLines[:2]):
                Text8(line, 120, y + descOffset + j*16, jx=0.5, jy=0,
                     fg=BLACK, bg=GREY if highlighted else WHITE)

        if gameVersion:
            Text8(f"v{gameVersion}", leftX + 6, y + boxH - 3, jx=0, jy=1,
                  fg=BLACK, bg=GREY if highlighted else WHITE)

        Text8(f"MAIN", (240-leftX) - 6, y + boxH - 3, jx=1, jy=1, #or 'SD' if loaded from the SD card
                  fg=BLACK, bg=GREY if highlighted else WHITE)

        y += boxH + paddingY

def RunMenu(games):
    sel = 0
    scroll = 0
    prevUp = prevDown = prevA = False
    DrawMenu(games, sel, scroll)

    while True:
        moved = False
        
        if Pressed(iDown):
            if not prevDown and CanPressButton('down'):
                sel = (sel + 1) % len(games)
                moved = True
        elif Pressed(iUp):
            if not prevUp and CanPressButton('up'):
                sel = (sel - 1) % len(games)
                moved = True
        elif Pressed(iA):
            if not prevA and CanPressButton('a'):
                return games[sel][4]  # Game path is now at index 4
        
        prevUp = Pressed(iUp)
        prevDown = Pressed(iDown)
        prevA = Pressed(iA)

        if moved:
            if sel < scroll:
                scroll = sel
            elif sel >= scroll + maxVisible:
                scroll = sel - maxVisible + 1
            DrawMenu(games, sel, scroll)

        sleep(0.01)

def Launch(path): 
    # Clean up launcher memory before starting game
    global gameList  # This could all be made more efficient with less overhead if needed
    del gameList  # Free the games list
    gc.collect()  # Clean up memory
    
    try:
        gameDir = "/".join(path.split("/")[:-1])
        originalDir = os.getcwd()
        os.chdir(gameDir)
        
        # Execute directly without storing code string in memory
        with open("main.py") as f:
            exec(f.read(), {})
        
        os.chdir(originalDir)
    except Exception as e:
        display.fill(WHITE)
        Text8("Error:", 120, 100, jx=0.5)
        Text8(str(e)[:240], 120, 116, jx=0.5)
        while True:
            sleep(1)

def ShowTitleScreen():
    display.fill(WHITE)
    Text16("PithOS", 120, 120, 0.5, 0.5) #change this to a better font
    Text8(version, 8, 5, 0, 0)
    Text8("by Henry Gurney", 120, 235, 0.5, 1)
    sleep(2)

ShowTitleScreen()
display.fill(WHITE)
gameList = LoadGames()
selectedGame = RunMenu(gameList)
Launch(selectedGame)

#TODO
#add SD card support (and wire up the SD card reciever)
#add a way to exit games and return to the menu
