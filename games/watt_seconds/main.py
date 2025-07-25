from machine import Pin, SPI
import st7789
from time import sleep, ticks_us, ticks_diff
from atomic import Pressed, DrawText, RGBto565
from atomic import __version__ as atomic_version
import vga2_16x32 as font16
import vga2_8x16 as font8
import symbols_8x16 as fontSymbols #package this into atomic when complete

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
GREY  = RGBto565(207, 207, 207)

def LoadGameInfo():
    with open("info.info", "r") as f:
        return eval(f.read())

gameInfo = LoadGameInfo()
version = f"v{gameInfo['version']}"

framerate = 60
DEBUG = False ###

typeMults = {
    "hand crank": 1,
    "potato": 1.05,
    "nuclear": 1.1,
    "solar panel": 1.15,
    "wind turbine": 1.3,
    "burner": 1.5,
    "hydro dam": 2,
    "geothermal": 5,
    "tidal": 3,
    "generator": 1.5,
    "power plant": 1.5,
    "fuel cell": 1.2
}

class Generator:
    def __init__(self, name, baseCost, watts, genType):
        self.name = name
        self.baseCost = baseCost
        self.watts = watts
        self.costMult = typeMults.get(genType)
        self.count = 0
        self.upgrades = []
        self.type = genType

    def CurrentCost(self):
        return int(round(self.baseCost * (self.costMult ** self.count)))

    def TotalMultiplier(self):
        m = 1.0
        for u in self.upgrades:
            if u.bought:
                m *= u.GetMultiplier()
        return m

    def PowerOutput(self):
        return self.watts * self.count * self.TotalMultiplier()

class Upgrade:
    def __init__(self, name, costPercent, multPercent):
        self.name  = name
        self.costPercent  = costPercent  #percentage of base cost
        self.multPercent = multPercent   #percentage increase
        self.bought = False
    
    def GetCost(self, generatorBaseCost):
        return int(round(generatorBaseCost * self.costPercent / 100))
    
    def GetMultiplier(self):
        return 1 + (self.multPercent / 100)

# Game State - consolidate all global variables here
class GameState:
    def __init__(self):
        self.playerMoney = 0.05
        self.totalEarnings = 0.0
        self.prestigePoints = 0
        self.totalWatts = 0
        self.selectedIdx = 0
        self.scrollIdx = 0
        self.inUpgradeMode = False
        self.upgSelIdx = 0
        self.upgScrollIdx = 0
        self.gameState = "titlescreen"
        self.prestigeCount = 0
        # Prestige screen state
        self.inPrestigeMode = False
        self.prestigeCatIdx = 0
        self.prestigePerkIdx = 0
        self.prestigePerkScrollIdx = 0
        self.showFirstPrestigeIntro = False
        # Button timing for non-blocking debouncing
        self.lastButtonTime = {
            'up': 0, 'down': 0, 'left': 0, 'right': 0, 'a': 0, 'b': 0, 'x': 0, 'y': 0
        }

game = GameState()

# Button debouncing helper function
def CanPressButton(buttonName, minDelay=250):
    """Check if enough time has passed since last button press (in milliseconds)"""
    currentTime = ticks_us() // 1000  # Convert to milliseconds
    
    # Handle potential overflow by using ticks_diff
    if ticks_diff(currentTime * 1000, game.lastButtonTime[buttonName] * 1000) >= minDelay * 1000:
        game.lastButtonTime[buttonName] = currentTime
        return True
    return False

prestigeCategories = [
    {
        "name": "Research Lab",
        "perks": ["researchLab"]
    },
    {
        "name": "Type Boosts", 
        "perks": ["solarBoost"]
    },
    {
        "name": "Other",
        "perks": ["globalBoost", "startCash"]
    }
]

def GetAvailablePerks():
    """Return perks available based on prestige count"""
    if game.prestigeCount <= 1:
        return []  # No perks shown for first prestige (handled separately) or before any prestige
    else:
        # Show all perks except research lab after first prestige
        return [k for k in prestigePerks.keys() if k != "researchLab"]

def ApplyPerkBonuses():
    """Apply all purchased perk bonuses to generators"""
    # Apply solar boost
    solarMult = 1.0 + (prestigePerks["solarBoost"].bought * 10.0)  # 10x, 20x, 30x total
    
    # Apply global boost  
    globalMult = prestigePerks["globalBoost"].bought * 0.25  # 25% per purchase
    
    for gen in generators.values():
        if gen.type == "solar panel":
            gen.watts *= solarMult
        gen.watts *= (1.0 + globalMult)

def CalculateModifiedWatts(generator):
    """Calculate prestige-modified watts for a generator"""
    modifiedWatts = generator.watts
    
    # Apply solar boost if applicable
    if generator.type == "solar panel" and prestigePerks["solarBoost"].bought > 0:
        modifiedWatts *= (1.0 + prestigePerks["solarBoost"].bought * 10.0)
    
    # Apply global boost
    if prestigePerks["globalBoost"].bought > 0:
        modifiedWatts *= (1.0 + prestigePerks["globalBoost"].bought * 0.25)
    
    # Apply research lab multiplier
    if prestigePerks["researchLab"].bought:
        modifiedWatts *= 2
    
    return modifiedWatts

# Prestige helper functions - consolidate prestige operations
def ResetAllGenerators():
    """Reset all generators and upgrades to initial state"""
    for gen in generators.values():
        gen.count = 0
        for upgrade in gen.upgrades:
            upgrade.bought = False

def ApplyStartingCash():
    """Apply starting cash bonus from prestige perks"""
    startCash = 0 + (prestigePerks["startCash"].bought * 10_000_000)
    game.playerMoney = startCash
    game.totalEarnings = startCash

def ResetGameState():
    """Reset game state indices and totals"""
    game.totalWatts = 0
    game.selectedIdx = 0
    game.scrollIdx = 0

def DoPrestige():
    """Perform prestige reset"""
    game.prestigeCount += 1
    
    if game.prestigeCount == 1:
        # First prestige - show intro screen, give 0 PC
        game.showFirstPrestigeIntro = True
        display.fill(WHITE)
        DrawFirstPrestigeIntro()
        return
    
    # Second+ prestige - normal prestige flow
    game.inPrestigeMode = True
    game.prestigeCatIdx = -1  # Start in category selection mode
    game.prestigePerkIdx = 0
    game.prestigePerkScrollIdx = 0
    
    game.prestigePoints += 1
    
    # Use helper functions for cleaner prestige logic
    ResetAllGenerators()
    ApplyStartingCash()
    ResetGameState()
    ApplyPerkBonuses()

def DrawFirstPrestigeIntro():
    display.fill(WHITE)

    intro_text = """Congratulations!

Premstimge

Press X to continue..."""
    
    lines = intro_text.split('\n')
    y = 20
    for line in lines:
        Txt(line, 8, y, 0, 0)
        y += 12

def DrawPrestigeUI():
    display.fill_rect(0, topH, 240, 240 - topH, WHITE)
    
    availablePerks = GetAvailablePerks()
    if not availablePerks:
        # No perks available yet
        Txt("No perks available", 120, 120, 0.5, 0.5)
        return
    
    # Check if we're in category selection mode or perk selection mode
    if game.prestigeCatIdx == -1:
        # Draw categories full-width (like generators)
        availableCategories = [cat for cat in prestigeCategories 
                              if any(p in availablePerks for p in cat["perks"])]
        
        if not availableCategories:
            return
            
        y = topStart
        visibleCats = availableCategories[game.prestigePerkScrollIdx : game.prestigePerkScrollIdx + 4]
        
        for idx, cat in enumerate(visibleCats):
            realIdx = game.prestigePerkScrollIdx + idx
            isSel = (realIdx == game.prestigePerkIdx)
            
            if isSel:
                display.fill_rect(leftX, y, boxW, boxH, GREY)
            
            display.rect(leftX, y, boxW, boxH, BLACK)
            Txt(cat["name"], 120, y + 4, 0.5, 0)
            Txt("Enter →", leftX + boxW - 4, y + boxH - 3, 1, 1)
            
            if idx > 0:
                display.line(leftX + boxW // 2, y + boxH, leftX + boxW // 2, y + boxH + spacing, BLACK)
            
            y -= spacing + boxH
    else:
        # Draw perks full-width (like upgrades)
        availableCategories = [cat for cat in prestigeCategories 
                              if any(p in availablePerks for p in cat["perks"])]
        
        if game.prestigeCatIdx >= len(availableCategories):
            return
            
        currentCat = availableCategories[game.prestigeCatIdx]
        catPerks = [p for p in currentCat["perks"] if p in availablePerks]
        
        y = topStart
        visiblePerks = catPerks[game.prestigePerkScrollIdx : game.prestigePerkScrollIdx + 4]
        
        for idx, perkKey in enumerate(visiblePerks):
            realIdx = game.prestigePerkScrollIdx + idx
            isSel = (realIdx == game.prestigePerkIdx)
            perk = prestigePerks[perkKey]
            
            if isSel:
                display.fill_rect(leftX, y, boxW, boxH, GREY)
            
            display.rect(leftX, y, boxW, boxH, BLACK)
            
            # Perk name
            nameDisplay = perk.name
            
            # Cost display
            if perk.maxBuy and perk.bought >= perk.maxBuy:
                costDisplay = "MAX"
            else:
                costDisplay = f"{perk.NextCost()} PC"
            
            # Effect display
            if perkKey == "solarBoost":
                effectDisplay = f"{(perk.bought + 1) * 10}x"
            elif perkKey == "globalBoost":
                effectDisplay = f"+{(perk.bought + 1) * 25}%"
            elif perkKey == "startCash":
                effectDisplay = f"${FormatMoney((perk.bought + 1) * 10_000_000)}"
            else:
                effectDisplay = "Unlock"
            
            Txt(nameDisplay, 120, y + 4, 0.5, 0)
            Txt(costDisplay, leftX + 4, y + boxH - 3, 0, 1)
            Txt(effectDisplay, leftX + boxW - 4, y + boxH - 3, 1, 1)
            
            # Connection line to category list (like upgrades)
            if realIdx == 0:
                display.line(0, y + boxH // 2, leftX, y + boxH // 2, BLACK)
            
            if idx > 0:
                display.line(leftX + boxW // 2, y + boxH, leftX + boxW // 2, y + boxH + spacing, BLACK)
            
            y -= spacing + boxH

def DrawPrestigeStatsBar():
    display.fill_rect(0, 0, 240, topH, WHITE)
    
    Txt(f"{game.prestigePoints} PC", 6, topH // 2, 0, 0.5)
    
    # Show restart instruction
    Txt("Press X to Restart", 120, topH // 2, 0.5, 0.5)

def CanShowPrestigeButton():
    return generators["largeNuke"].count > 0

def DrawPrestigeButton():
    if CanShowPrestigeButton():
        Txt("X: PRESTIGE", 120, topH // 2, 0.5, 0.5)

# Remove duplicate global variables - these are now in GameState class

# Game state handlers - modularize the main game loop
def HandleFirstPrestigeIntro(prevX):
    """Handle first prestige intro screen input"""
    if Pressed(iX):
        if not prevX and CanPressButton('x'):
            # Complete first prestige
            game.showFirstPrestigeIntro = False
            game.prestigePoints += 0  # First prestige gives 0 PC
            prestigePerks["researchLab"].bought = 1  # Auto-unlock research lab
            
            # Use helper functions for cleaner prestige logic
            ResetAllGenerators()
            game.playerMoney = 0
            game.totalEarnings = 0
            ResetGameState()
            ApplyPerkBonuses()
            
            # Redraw game screen
            display.fill(WHITE)
            DrawStatsBar(game.totalWatts, game.playerMoney)
            DrawGeneratorUI()
        prevX = Pressed(iX)

def HandlePrestigeMode(prevUp, prevDown, prevA, prevX):
    """Handle prestige screen navigation and purchases"""
    availablePerks = GetAvailablePerks()
    if not availablePerks:
        # Only allow restart if no perks available
        if Pressed(iX):
            if not prevX and CanPressButton('x'):
                game.inPrestigeMode = False
                game.selectedIdx = 0
                game.scrollIdx = 0
                game.inUpgradeMode = False
                display.fill(WHITE)
                DrawStatsBar(game.totalWatts, game.playerMoney)
                DrawGeneratorUI()
            prevX = Pressed(iX)
        return
    
    availableCategories = [cat for cat in prestigeCategories 
                          if any(p in availablePerks for p in cat["perks"])]
    
    # If we're in category selection mode (prestigeCatIdx == -1)
    if game.prestigeCatIdx == -1:
        # Navigate categories like generators
        if Pressed(iUp):
            if not prevUp and CanPressButton('up'):
                if game.prestigePerkIdx < len(availableCategories) - 1:
                    game.prestigePerkIdx += 1
                    if game.prestigePerkIdx >= game.prestigePerkScrollIdx + 4:
                        game.prestigePerkScrollIdx += 1
                    DrawPrestigeUI()
            prevUp = Pressed(iUp)
        elif Pressed(iDown):
            if not prevDown and CanPressButton('down'):
                if game.prestigePerkIdx > 0:
                    game.prestigePerkIdx -= 1
                    if game.prestigePerkIdx < game.prestigePerkScrollIdx:
                        game.prestigePerkScrollIdx -= 1
                    DrawPrestigeUI()
            prevDown = Pressed(iDown)
        # Enter category with right arrow (like entering upgrades)
        elif Pressed(iRight):
            if CanPressButton('right'):
                game.prestigeCatIdx = game.prestigePerkIdx
                game.prestigePerkIdx = 0
                game.prestigePerkScrollIdx = 0
                DrawPrestigeUI()
    else:
        # We're in perk selection mode - navigate like upgrades
        if game.prestigeCatIdx < len(availableCategories):
            currentCat = availableCategories[game.prestigeCatIdx]
            catPerks = [p for p in currentCat["perks"] if p in availablePerks]
            
            if Pressed(iUp):
                if not prevUp and CanPressButton('up'):
                    if game.prestigePerkIdx < len(catPerks) - 1:
                        game.prestigePerkIdx += 1
                        if game.prestigePerkIdx >= game.prestigePerkScrollIdx + 4:
                            game.prestigePerkScrollIdx += 1
                        DrawPrestigeUI()
                prevUp = Pressed(iUp)
            elif Pressed(iDown):
                if not prevDown and CanPressButton('down'):
                    if game.prestigePerkIdx > 0:
                        game.prestigePerkIdx -= 1
                        if game.prestigePerkIdx < game.prestigePerkScrollIdx:
                            game.prestigePerkScrollIdx -= 1
                        DrawPrestigeUI()
                prevDown = Pressed(iDown)
            # Buy perk with A button
            elif Pressed(iA):
                if not prevA and CanPressButton('a'):
                    if game.prestigePerkIdx < len(catPerks):
                        perkKey = catPerks[game.prestigePerkIdx]
                        perk = prestigePerks[perkKey]
                        
                        if perk.CanBuy(game.prestigePoints):
                            game.prestigePoints -= perk.NextCost()
                            perk.Buy()
                            DrawPrestigeUI()
                            DrawPrestigeStatsBar()
                prevA = Pressed(iA)
            # Go back to categories with left arrow
            elif Pressed(iLeft):
                if CanPressButton('left'):
                    game.prestigeCatIdx = -1
                    game.prestigePerkIdx = 0
                    game.prestigePerkScrollIdx = 0
                    DrawPrestigeUI()
    
    # Restart game with X
    if Pressed(iX):
        if not prevX and CanPressButton('x'):
            # Reset all prestige state and UI
            game.inPrestigeMode = False
            game.selectedIdx = 0
            game.scrollIdx = 0
            game.inUpgradeMode = False
            game.upgSelIdx = 0
            game.upgScrollIdx = 0
            
            # Clear entire screen to remove any leftover prestige text
            display.fill(WHITE)
            DrawStatsBar(game.totalWatts, game.playerMoney)
            DrawGeneratorUI()
        prevX = Pressed(iX)

    DrawPrestigeStatsBar()

def HandleGeneratorNavigation(prevUp, prevDown, prevA, prevX):
    """Handle main generator screen navigation and purchases"""
    # Enter prestige mode
    if Pressed(iX):
        if not prevX and CanShowPrestigeButton() and CanPressButton('x'):
            DoPrestige()
            if game.inPrestigeMode:  # Only if not first prestige
                display.fill_rect(0, 0, 240, topH, WHITE)
                DrawPrestigeUI()
                DrawPrestigeStatsBar()
        prevX = Pressed(iX)
    
    #generator list navigation
    elif Pressed(iUp):
        if not prevUp and CanPressButton('up'):
            availableGens = GetAvailableGenerators()
            if game.selectedIdx < len(availableGens) - 1:
                game.selectedIdx += 1
                if game.selectedIdx >= game.scrollIdx + 4:
                    game.scrollIdx += 1
                DrawGeneratorUI()
        prevUp = Pressed(iUp)
    elif Pressed(iDown):
        if not prevDown and CanPressButton('down'):
            if game.selectedIdx > 0:
                game.selectedIdx -= 1
                if game.selectedIdx < game.scrollIdx:
                    game.scrollIdx -= 1
                DrawGeneratorUI()
        prevDown = Pressed(iDown)
            
    #enter upgrade mode with right button
    elif Pressed(iRight):
        if CanPressButton('right'):
            availableGens = GetAvailableGenerators()
            if game.selectedIdx < len(availableGens):
                gen = availableGens[game.selectedIdx]
                if gen.upgrades and gen.count > 0:  # only allow if generator has been bought
                    game.inUpgradeMode = True
                    game.upgSelIdx = game.upgScrollIdx = 0
                    DrawUpgradeUI(gen)
    
    #buy generator or use hand crank
    elif Pressed(iA):
        if not prevA and CanPressButton('a', 500):
            availableGens = GetAvailableGenerators()
            if game.selectedIdx < len(availableGens):
                selectedGen = availableGens[game.selectedIdx]
                if selectedGen is generators["manualCrank"]:
                    # Hand crank operation
                    moneyGain = CalculateModifiedWatts(generators["manualCrank"])
                    game.playerMoney += moneyGain
                    game.totalEarnings += moneyGain
                else:
                    # Buy generator
                    cost = selectedGen.CurrentCost()
                    if game.playerMoney >= cost:
                        game.playerMoney -= cost
                        selectedGen.count += 1
                        DrawGeneratorUI()
        prevA = Pressed(iA)

def HandleUpgradeMode(prevUp, prevDown, prevA):
    """Handle upgrade screen navigation and purchases"""
    gen = genOrder[game.selectedIdx]
    if Pressed(iUp):
        if not prevUp and CanPressButton('up'):
            if game.upgSelIdx < len(gen.upgrades) - 1:
                game.upgSelIdx += 1
                if game.upgSelIdx >= game.upgScrollIdx + 4:
                    game.upgScrollIdx += 1
                DrawUpgradeUI(gen)
        prevUp = Pressed(iUp)
    elif Pressed(iDown):
        if not prevDown and CanPressButton('down'):
            if game.upgSelIdx > 0:
                game.upgSelIdx -= 1
                if game.upgSelIdx < game.upgScrollIdx:
                    game.upgScrollIdx -= 1
                DrawUpgradeUI(gen)
        prevDown = Pressed(iDown)

    #buy upgrade
    elif Pressed(iA):
        if not prevA and CanPressButton('a'):
            upg = gen.upgrades[game.upgSelIdx]
            upgradeCost = upg.GetCost(gen.baseCost)
            if (not upg.bought) and game.playerMoney >= upgradeCost:
                game.playerMoney -= upgradeCost
                upg.bought = True
                DrawUpgradeUI(gen)  # refresh the upgrade screen after purchase
        prevA = Pressed(iA)
    elif Pressed(iLeft):
        if CanPressButton('left'):
            game.inUpgradeMode = False
            DrawGeneratorUI()

class Perk:
    def __init__(self, key, name, baseCost, effect, maxBuy=None):
        self.key       = key
        self.name      = name
        self.baseCost  = baseCost      # PCs
        self.effect    = effect        # dict of modifiers
        self.maxBuy    = maxBuy        # None or integer cap
        self.bought    = 0             # times purchased so far

    def NextCost(self) -> int:
        return self.baseCost * (self.bought + 1)

    def CanBuy(self, availablePc: int) -> bool:
        if self.maxBuy is not None and self.bought >= self.maxBuy:
            return False
        return availablePc >= self.NextCost()

    def Buy(self):
        if self.maxBuy is None or self.bought < self.maxBuy:
            self.bought += 1

generators = {               #name                              cost             watts           type
    "manualCrank": Generator("Hand Crank",                      0,               0.05,           "hand crank"),
    "potato":      Generator("Potato Battery",                  1,               0.1,            "potato"),
    "windHand":    Generator("Handheld Wind Turbine",           10,              1,              "wind turbine"),
    "solarHand":   Generator("Portable Solar Panel",            100,             2,              "solar panel"),
    "alcoholTEG":  Generator("Alcohol Burner w TEG",            250,             5,              "burner"),
    "smallWind":   Generator("Small Wind Turbine",              800,             10,             "wind turbine"),
    "keroseneTEG": Generator("Kerosene Burner w TEG",           1_100,           22,             "burner"),
    "medSolar":    Generator("Medium Solar Panel",              3_500,           70,             "solar panel"),
    "fuelCell":    Generator("Methanol Fuel Cell",              4_500,           80,             "fuel cell"),
    "medWind":     Generator("Medium Wind Turbine",             28_000,          225,            "wind turbine"),
    "smallArray":  Generator("Small Solar Array",               35_000,          500,            "solar panel"),
    "microHydro":  Generator("Stream Hydro Dam",                55_000,          900,            "hydro dam"),
    "portableGen": Generator("Portable Generator",              125_000,         1_100,          "generator"),
    "medArray":    Generator("Medium Solar Array",              300_000,         2_500,          "solar panel"),
    "bigWind":     Generator("Large Wind Turbine",              400_000,         4_500,          "wind turbine"),
    "propaneGen":  Generator("Propane Generator",               800_000,         7_500,          "generator"),
    "smallHydro":  Generator("Small Hydro Dam",                 1_300_000,       11_000,         "hydro dam"),
    "largeArray":  Generator("Large Solar Array",               2_200_000,       18_000,         "solar panel"),
    "biogasGen":   Generator("Biogas Generator",                4_000_000,       30_000,         "generator"),
    "hugeWind":    Generator("Huge Wind Turbine",               6_000_000,       80_000,         "wind turbine"),
    "dieselGen":   Generator("Large Diesel Generator",          25_000_000,      200_000,        "generator"),
    "solarFarmS":  Generator("Small Solar Farm",                65_000_000,      500_000,        "solar panel"),
    "landfillGas": Generator("Landfill-Gas Engine",             100_000_000,     600_000,        "power plant"),
    "onSWind":     Generator("Onshore Wind Turbine",            150_000_000,     700_000,        "wind turbine"),
    "tinyNuke":    Generator("Tiny Nuclear Reactor",            250_000_000,     1_000_000,      "nuclear"),
    "offSWind":    Generator("Offshore Wind Turbine",           400_000_000,     1_500_000,      "wind turbine"),
    "solarFarmL":  Generator("Large Solar Farm",                650_000_000,     3_000_000,      "solar panel"),
    "tidalArray":  Generator("Tidal Turbine Array",           1_500_000_000,     6_000_000,      "tidal"),
    "geoPlant":    Generator("Geothermal Power Plant",        2_500_000_000,     8_000_000,      "geothermal"),
    "biomass":     Generator("Biomass Power Plant",           5_000_000_000,    25_000_000,      "power plant"),
    "mediumHydro": Generator("Medium Hydro Dam",             12_000_000_000,    50_000_000,      "hydro dam"),
    "smallNuke":   Generator("Small Nuclear Reactor",        30_000_000_000,    80_000_000,      "nuclear"),
    "gasTurbine":  Generator("Gas Turbine Plant",            65_000_000_000,   250_000_000,      "power plant"),
    "coalPlant":   Generator("Coal Power Station",          200_000_000_000,   500_000_000,      "power plant"),
    "largeHydro":  Generator("Large Hydro Dam",             500_000_000_000, 1_200_000_000,      "hydro dam"),
    "largeNuke":   Generator("Large Nuclear Reactor",     1_000_000_000_000, 2_500_000_000,      "nuclear"), #end of base game; you're forced to prestige here to progress
    "test":        Generator("Test",                      1_111_000_000_000, 2_525_000_000,      "potato"), #test
}

typeUpgrades = {
    "hand crank": [],
    "potato": [
        Upgrade("Yukon Gold Potato",        100,  50),
        Upgrade("Magnesium Electrode",      250, 100)
    ],
    "wind turbine": [
        Upgrade("Taller Mast",               50,  15),
        Upgrade("Smart Inverter",            80,  10),
        Upgrade("Carbon Blades",            120,  20),
        Upgrade("Variable Pitch Blades",    150,  35)
    ],
    "solar panel": [
        Upgrade("Low-Resistance Cabling",    50,  10),
        Upgrade("Autocleaning",              65,  10),
        Upgrade("Bifacial Cells",           125,  20),
        Upgrade("Sun Tracking",             200,  50)
    ],
    "burner": [
        Upgrade("Improved Nozzle",           30,  10),
        Upgrade("Exhaust Heat Recovery",     50,  10),
        Upgrade("Heat Pipes",                90,  25)
    ],
    "fuel cell": [
        Upgrade("Water Recycling Loop",      50,  10),
        Upgrade("High-Efficiency Membrane",  60,  10),
        Upgrade("High-Quality Fuel",         80,  15),
        Upgrade("Platinum Catalyst",        150,  25)
    ],
    "hydro dam": [
        Upgrade("Water Filtration",          25,   5),
        Upgrade("Improved Turbine",          60,  15),
        Upgrade("Variable-Speed Generator", 125,  20)
    ],
    "generator": [
        Upgrade("Low-Friction Oil",          20,   5),
        Upgrade("Improved ECU",              35,  10),
        Upgrade("Fuel Injection",            60,  15),
        Upgrade("Turbocharging",            150,  35)
    ],
    "power plant": [
        Upgrade("Improved Heat Recovery",    35,  10),
        Upgrade("Advanced Turbine Blades",   60,  15),
        Upgrade("Combined Cycle Add-on",    100,  20),
        Upgrade("Supercritical Steam",      150,  40)
    ],
    "nuclear": [
        Upgrade("Richer Fuel Rods",         100,  15),
        Upgrade("Molten Salt Loop",         500,  75)
    ],
    "geothermal": [
        Upgrade("Anti-Scale Protection",     30,   5),
        Upgrade("Reinjection Loop",          80,  10),
        Upgrade("Deeper Reservoirs",        200,  25)
    ],
    "tidal": [
        Upgrade("Corrosion-Proof Blades",     50,  5),
        Upgrade("Gearless Generator",        150, 15),
        Upgrade("Optimised Blade Profile",   200, 25)
    ]
}

introText = f"""Decades have passed and
the grid has collapsed.
Electricity now costs $1
per watt-second...
a 1,400,000,000% increase.

You have no money, no job,
and no other way to earn.

You have just a hand crank,
turn it & sell those watts!

Press A to Crank..."""

prestigePerks = {
    # one-time unlock that reveals all near-future generators
    "researchLab": Perk(
        key="researchLab",
        name="Research Lab (unlock)",
        baseCost=1,                    # 1 PC
        effect={"labUnlocked": True},  # flag your shop UI can check
        maxBuy=1                       # single purchase
    ),

    # repeatable +100 % solar output (doubles each time you buy it)
    "solarBoost": Perk(
        key="solarBoost",
        name="Solar Output +100%",
        baseCost=1,                    # 1 PC first, 2 PC second, etc.
        effect={"solarMult": 2.0}      # multiply solar by 2^n
    ),

    # repeatable +25 % to *all* generator types
    "globalBoost": Perk(
        key="globalBoost",
        name="All Output +25%",
        baseCost=2,                    # 2 PC, then 4 PC, 6 PC…
        effect={"globalMult": 1.25}    # multiply total output by 1.25^n
    ),

    # repeatable starting-cash bump of $50 M per purchase
    "startCash": Perk(
        key="startCash",
        name="Start Cash +$10 M",
        baseCost=1,                    # 1 PC, then 2 PC, 3 PC…
        effect={"startCash": 10_000_000}
    )
}

#bind upgrades to generators based on their type (create separate instances)
for gen in generators.values():
    if gen.type in typeUpgrades:
        gen.upgrades = []
        for upgrade_template in typeUpgrades[gen.type]:
            #create a new copy of each upgrade for this generator
            new_upgrade = Upgrade(upgrade_template.name, upgrade_template.costPercent, upgrade_template.multPercent)
            gen.upgrades.append(new_upgrade)

# Debug mode setup
if DEBUG:
    generators["largeHydro"].count = 1

def Txt(msg, x, y, jx=0, jy=0):
    DrawText(display, font8, msg, x, y, BLACK, WHITE, jx, jy)

# UI Constants
topH     = 20
boxH     = 40
boxW     = 220
spacing  = 10
leftX    = 10
topStart = 190

# Utility functions for formatting
def FormatPower(p, stripZeros=True):
    units = ("W", "kW", "MW", "GW", "TW", "PW", "EW")
    mag = 0

    while p >= 1000 and mag < len(units) - 1:
        p /= 1000
        mag += 1

    if stripZeros:
        s = f"{p:.3g}"
    else:
        if p >= 100:
            s = f"{p:3.0f}"
        elif p >= 10:
            s = f"{p:3.1f}"
        else:
            s = f"{p:3.2f}"

    return s + units[mag]

def FormatMoney(m, stripZeros=True):
    units = ("", "k", "M", "B", "T", "Qa", "Qi", "Sx", "Sp", "Oc", "No", "Dc")
    mag = 0

    while m >= 1000 and mag < len(units) - 1:
        m /= 1000
        mag += 1

    if stripZeros:
        s = f"{m:.3g}"
    else:
        if m >= 100:
            s = f"{m:3.0f}"
        elif m >= 10:
            s = f"{m:3.1f}"
        else:
            s = f"{m:3.2f}"

    return f"${s}{units[mag]}"

# UI Drawing Functions - grouped together for clarity
def DrawStatsBar(totalWatts, money):
    global prevWatts, prevMoney
    if totalWatts != prevWatts:
        Txt(f"     ", 234, topH // 2, 1, 0.5)
        Txt(FormatPower(totalWatts, False), 234, topH // 2, 1, 0.5)
        prevWatts = totalWatts
    if money != prevMoney:
        Txt(f"          ", 6, topH // 2, 0, 0.5)
        Txt(FormatMoney(money, False), 6, topH // 2, 0, 0.5)
        prevMoney = money
    
    # Show PC count after first prestige (to the right of money)
    if game.prestigeCount >= 1:
        pcText = f"{game.prestigePoints:.3g} PC"
        Txt(pcText, 6 + len(FormatMoney(money, False)) * 8 + 10, topH // 2, 0, 0.5)
    
    # Show prestige button if available
    if not game.inPrestigeMode and not game.showFirstPrestigeIntro:
        DrawPrestigeButton()

def DrawTitleScreen():
    display.fill(WHITE)
    Txt(version, 6, 6, 0, 0)
    #Txt(f"a{atomic_version}", 234, 6, 1, 0)
    DrawText(display, font16, "Watt Seconds", 120, 110, BLACK, WHITE, 0.5, 0.5)
    Txt("Press A to Start", 120, 135, 0.5, 0)
    Txt("by Henry Gurney", 120, 220, 0.5, 0)

def DrawIntro():
    display.fill(WHITE)
    lines = introText.split('\n')
    y = 16
    for line in lines:
        Txt(line, 8, y, 0, 0)
        y += 16

def DrawGeneratorUI():
    display.fill_rect(0, topH, 240, 240 - topH, WHITE)
    
    availableGens = GetAvailableGenerators()
    
    bestBoughtIndex = -1
    for i, g in enumerate(availableGens):
        if g.count > 0:
            bestBoughtIndex = i

    y = topStart
    visibleGens = availableGens[game.scrollIdx : game.scrollIdx + 4]

    for idx, gen in enumerate(visibleGens):
        realIdx = game.scrollIdx + idx
        isSel = (realIdx == game.selectedIdx)

        if isSel:
            display.fill_rect(leftX, y, boxW, boxH, GREY)

        display.rect(leftX, y, boxW, boxH, BLACK)

        if realIdx > bestBoughtIndex + 2 and (gen.name != "Potato Battery" and gen.name != "Handheld Wind Turbine"):
            nameDisplay = "????????"
            costDisplay = "???"
            wattDisplay = "???"
        else:
            nameDisplay = gen.name
            if gen.name == "Hand Crank":
                # Apply prestige bonuses to hand crank display
                modifiedWatts = CalculateModifiedWatts(gen)
                wattDisplay = FormatPower(modifiedWatts)
                costDisplay = f""
            else:
                costDisplay = FormatMoney(gen.CurrentCost())
                if gen.count > 0:
                    # Calculate prestige-modified watts for owned generators
                    modifiedWatts = CalculateModifiedWatts(gen)
                    perGenWatts = modifiedWatts * gen.TotalMultiplier()
                    totalOutput = perGenWatts * gen.count
                    wattDisplay = f"{FormatPower(totalOutput)} +{FormatPower(perGenWatts)}"
                else:
                    # Show prestige-modified base watts for unowned generators
                    modifiedWatts = CalculateModifiedWatts(gen)
                    perGenWatts = modifiedWatts * gen.TotalMultiplier()
                    wattDisplay = f"({FormatPower(perGenWatts)})"

        Txt(nameDisplay, 120, y + 4, 0.5, 0)
        Txt(costDisplay, leftX + 4, y + boxH - 3, 0, 1)
        Txt(wattDisplay, leftX + boxW - 4, y + boxH - 3, 1, 1)

        #add line to upgrades
        if gen.name != "Hand Crank":
            display.line(leftX + boxW, y + boxH // 2, 240, y + boxH // 2, BLACK)

        if idx > 0:
            display.line(leftX + boxW // 2, y + boxH,
                         leftX + boxW // 2, y + boxH + spacing, BLACK)

        y -= spacing + boxH

def DrawUpgradeUI(gen):
    display.fill_rect(0, topH, 240, 240 - topH, WHITE)

    upgrades = gen.upgrades
    y = topStart
    vis = upgrades[game.upgScrollIdx : game.upgScrollIdx + 4]

    for i, upg in enumerate(vis):
        realIdx = game.upgScrollIdx + i
        isSel   = (realIdx == game.upgSelIdx)

        if isSel:
            display.fill_rect(leftX, y, boxW, boxH, GREY)
        display.rect(leftX, y, boxW, boxH, BLACK)

        name  = upg.name
        cost  = "BOUGHT" if upg.bought else FormatMoney(upg.GetCost(gen.baseCost))
        mult  = f"+{upg.multPercent}%"

        Txt(name, 120, y + 4, 0.5, 0)
        Txt(cost, leftX + 4, y + boxH - 3, 0, 1)
        Txt(mult, leftX + boxW - 4, y + boxH - 3, 1, 1)

        if realIdx == 0:
            display.line(0, y + boxH // 2, leftX, y + boxH // 2, BLACK)

        y -= spacing + boxH

# Game Logic Functions - separate from UI drawing
def GetAvailableGenerators():
    """Return generators that should be visible based on research lab unlock"""
    availableGens = []
    largeNukeFound = False
    
    for gen in genOrder:
        if gen.name == "Large Nuclear Reactor":
            availableGens.append(gen)
            largeNukeFound = True
        elif not largeNukeFound or prestigePerks["researchLab"].bought:
            availableGens.append(gen)
    
    return availableGens

# Initialization functions - separate setup from main loop
def InitializeGame():
    """Initialize game variables and setup"""
    global genOrder, prevUp, prevDown, prevA, prevX, prevWatts, prevMoney
    
    genOrder = sorted([g for g in generators.values()], key=lambda g: g.baseCost)
    
    # Initialize UI state variables
    game.selectedIdx = 0
    game.scrollIdx = 0
    prevUp = prevDown = prevA = prevX = False
    prevWatts = -1
    prevMoney = -1
    
    game.inUpgradeMode = False
    game.upgSelIdx = 0
    game.upgScrollIdx = 0
    
    # Debug mode: start cursor on Large Hydro Dam
    if DEBUG:
        for i, gen in enumerate(genOrder):
            if gen.name == "Large Hydro Dam":
                game.selectedIdx = i
                game.scrollIdx = max(0, i - 2)  # Center it in view
                break

def RunTitleScreenLoop():
    """Handle title screen loop"""
    global prevUp
    DrawTitleScreen()
    
    while game.gameState == "titlescreen":
        if Pressed(iA) and not prevUp:
            game.gameState = "intro"
            DrawIntro()
            while Pressed(iA):
                sleep(1 / framerate)
        sleep(1 / framerate)

def RunIntroLoop():
    """Handle intro screen loop"""
    while game.gameState == "intro":
        if Pressed(iA):
            game.gameState = "game"
            display.fill_rect(0, 0, 240, topH, WHITE)
            DrawStatsBar(game.totalWatts, game.playerMoney)
            DrawGeneratorUI()
            while Pressed(iA):
                sleep(1 / framerate)
        sleep(1 / framerate)

def RunMainGameLoop():
    """Handle main game loop with all state management"""
    global prevUp, prevDown, prevA, prevX
    lastUpdate = ticks_us()
    
    while game.gameState == "game":
        dt = ticks_diff(ticks_us(), lastUpdate) / 1000000
        lastUpdate = ticks_us()
        
        # Check for first prestige intro
        if game.showFirstPrestigeIntro:
            HandleFirstPrestigeIntro(prevX)
        # Check for prestige mode
        elif game.inPrestigeMode:
            HandlePrestigeMode(prevUp, prevDown, prevA, prevX)
        elif not game.inUpgradeMode:
            HandleGeneratorNavigation(prevUp, prevDown, prevA, prevX)
        else:
            HandleUpgradeMode(prevUp, prevDown, prevA)
        
        if not game.inPrestigeMode:
            # Debug mode: Y button gives 1 trillion dollars
            if DEBUG and Pressed(iY):
                game.playerMoney += 1_000_000_000_000
                game.totalEarnings += 1_000_000_000_000
                    
            game.totalWatts = sum(g.PowerOutput() for g in generators.values())
            
            # Apply research lab money generation multiplier
            moneyGain = game.totalWatts * dt
            if prestigePerks["researchLab"].bought:
                moneyGain *= 2
            game.playerMoney += moneyGain
            game.totalEarnings += moneyGain
            DrawStatsBar(game.totalWatts, game.playerMoney)
        
        sleep(1 / framerate)

if DEBUG:
    # Debug statistics - analyze generator progression
    keys = sorted(generators, key=lambda k: generators[k].baseCost)
    for i in range(2, len(keys)):
        prev = generators[keys[i-1]]
        cur  = generators[keys[i]]
        pricePct = ((cur.baseCost - prev.baseCost) / prev.baseCost) * 100
        wattPct = ((cur.watts - prev.watts) / prev.watts) * 100
        income = 2 * prev.watts
        seconds = cur.baseCost / income if income else 0.0
        ratio = (cur.watts / cur.baseCost) * 100
        print(f"to {cur.name:<22} - "
                f"{pricePct:3.0f}% cost - {wattPct:3.0f}% power - "
                f"{ratio:2.1f} ratio - {seconds:3.0f} seconds")

# Initialize game state
InitializeGame()

# Run game state loops in sequence
RunTitleScreenLoop()
RunIntroLoop() 
RunMainGameLoop()
