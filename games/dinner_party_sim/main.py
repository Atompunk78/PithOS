# This program is ported from a normal python program I made a few years ago
# I made this in conjuction with textbox.py so I can easily port my text-based python games to the Pico

#TODO:
#screen slowly turns black when you pass out

from machine import Pin, SPI
import st7789
import vga2_8x16 as font8
from atomic import Pressed, CreateTextBox, Print, Flush

from random import random, choice, randint
from time import sleep

spi = SPI(1, baudrate=60000000, polarity=1, phase=1,
          sck=Pin(10), mosi=Pin(11))

display = st7789.ST7789(
    spi, 240, 240,
    reset=Pin(12, Pin.OUT),
    dc=Pin(8, Pin.OUT),
    cs=Pin(9, Pin.OUT),
    rotation=1
)

Pin(13, Pin.OUT).value(1) #backlight on

try:
    display.init()
except Exception as e:
    print(f"{e}\nSome systems don't require display.init() and crash when they see it, probably including yours, so I've skipped the line automatically and it should run normally now - if not, you will have to debug the error manually")

iUp     = Pin(2,  Pin.IN, Pin.PULL_UP)
iDown   = Pin(18, Pin.IN, Pin.PULL_UP)
iLeft   = Pin(16, Pin.IN, Pin.PULL_UP)
iRight  = Pin(20, Pin.IN, Pin.PULL_UP)
iCentre = Pin(3,  Pin.IN, Pin.PULL_UP)
iA      = Pin(15, Pin.IN, Pin.PULL_UP)
iB      = Pin(17, Pin.IN, Pin.PULL_UP)
iX      = Pin(19, Pin.IN, Pin.PULL_UP)
iY      = Pin(21, Pin.IN, Pin.PULL_UP)

BLACK = 0x0000
WHITE = 0xFFFF

display.fill(WHITE)
CreateTextBox(
    display=display,
    font=font8,
    startX=8,
    startY=8,
    widthChars=28,
    heightChars=13,
    fg=BLACK,
    bg=WHITE
)

devMode = False
finished = False

drunkenness = 0 #0 to 100, 0 is sober, 25 is tipsy, 50 is drunk, 75 is passing out, 100 is hospital
reputation = 50 #0 is everyone hates you, 50 is they kinda like you, 100 is everyone loves you
currentCourse = 1
courseCounter = 0
alcoholCounter = 0
letters = ['a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z']
names = ["Oliver", "George", "Henry", "Noah", "Jack", "Max", "Arthur", "Angus", "Oscar", "Charlie", "Olivia", "Amelia", "Emily", "Isabelle", "Alexandra", "Sophie", "Grace", "Mia", "Poppy", "Rosie"]
ages = ["19", "20", "21", "22", "23", "24"]
universities = ["Cambridge", "Oxford", "York", "Exeter", "Bristol", "Durham", "UEA", "Manchester", "Bath", "Loughborough"]
subjects = ["Computer Science", "Business Management", "Medicine", "Engineering", "Law", "Chemistry", "Psychology", "Environmental Science", "Economics", "Art History"]
currentGrades = ["4%", "19%", "22%", "31%", "46%", "55%", "63%", "71%", "87%", "98%"]

courses = [
    "Welcome Drinks",
    "Canapes",
    "Appetizer",
    "Soup Course",
    "Entree",
    "Main Course",
    "Cheese Course",
    "Dessert",
    "Tea & Coffee"
]

alcohols = [
    ["a glass of white wine", 8],
    ["a glass of rosé", 9],
    ["a glass of red wine", 10],
    ["a large glass of fine red wine", 17],
    ["a glass of champagne", 8],
    ["a small glass of port", 7],
    ["a shot of fine whisky", 9],
    ["a martini", 13],
    ["a gin and tonic", 13],
    ["a glass of brandy", 13],
    ["a glass of cognac", 13],
    ["a bottle of beer", 11],
    ["a margarita", 13],
    ["a rum and coke", 13],
    ["a glass of sherry", 8],
    ["a vodka tonic", 13],
    ["a glass of prosecco", 8],
    ["a mojito", 8],
    ["a bourbon on the rocks", 10],
    ["an old fashioned", 10],
    ["a glass of scotch", 10],
    ["a negroni", 13]
]

memory = { #checking memory adds a small amount of extra rudeness for taking too long to respond
    "Name": choice(names),
    "Age": choice(ages),
    "University": choice(universities), #maybe add another category for what to do after uni
    "Subject": choice(subjects),
    "Current Grade": choice(currentGrades)
}

names.remove(memory["Name"]) #remove correct answers from list
ages.remove(memory["Age"])
universities.remove(memory["University"])
subjects.remove(memory["Subject"])
currentGrades.remove(memory["Current Grade"])

goodReactions = [
    "Delightful!",
    "Wonderful.",
    f"Oh, how wonderful, {memory['Name']}!",
    "Splendid!",
    "Absolutely marvelous.",
    "That's just brilliant!",
    "Exquisite!",
    "Oh, splendid! You do go on!",
    f"How insightful, {memory['Name']}!",
    "Perfect, just perfect.",
    "Magnificent!",
    f"You're quite something, {memory['Name']}!",
    "How charming indeed!",
    "That's the spirit!",
    f"Bravo! I'm so glad {memory['Name']}.",
    "Couldn't have said it better myself!"
]

badReactions = [
    "Right...",
    "Ah, oh dear",
    "I see...",
    f"Well, that's one way to look at it {memory['Name']}",
    "Indeed?",
    "Are you quite sure about that?",
    "That's certainly an interesting take...",
    "Oh, really?",
    "I suppose everyone is entitled to their thoughts...",
    "Perhaps that might seem so to some...",
    "Oh, I hadn't quite thought of it like that...",
    f"Mmm, if you say so {memory['Name']}...",
    "Is that so?",
    "One might wonder about that...",
    "Not the conclusion I'd have reached, but there you are",
    "A curious perspective, indeed..."
]

questions = [ #["question", [[answer 1, reputation change], [answer 2, reputation change], [answer 3, reputation change]]]
    ["So remind me, what was your name again?", [[f"{memory["Name"]}.", 1], [f"{choice(names)}.", -10], [f"{choice(names)}.", -10]]],
    ["And what would your name be?", [[f"{memory["Name"]}.", 1], [f"{choice(names)}.", -10], [f"{choice(names)}.", -10]]],
    ["Good evening, what is your name?", [[f"{memory["Name"]}.", 1], [f"{choice(names)}.", -10], [f"{choice(names)}.", -10]]],
    ["How old were you again?", [[f"{memory["Age"]}.", 1], [f"{choice(ages)}.", -7], [f"{choice(ages)}.", -7]]],
    ["Which university is it you attend? Not one of those 'contemporary' ones is it?", [[f"{memory["University"]}.", 3], [f"{choice(universities)}.", -7], [f"{choice(universities)}.", -7]]],
    ["So where do you study?", [[f"{memory["University"]}.", 3], [f"{choice(universities)}.", -7], [f"{choice(universities)}.", -7]]],
    ["So tell me, what are you reading?", [[f"{memory["Subject"]}.", 3], [f"{choice(subjects)}.", -7], [f"{choice(subjects)}.", -7]]],
    ["What is it you study?", [[f"{memory["Subject"]}.", 3], [f"{choice(subjects)}.", -7], [f"{choice(subjects)}.", -7]]],
    ["What takes your interest then, at university?", [[f"{memory["Subject"]}.", 3], [f"{choice(subjects)}.", -7], [f"{choice(subjects)}.", -7]]],
    ["And how are things going at university? Surely you must be top of your class with all those brains, or are we still 'finding our feet'?", [[f"{memory["Current Grade"]}.", 2], [f"{choice(currentGrades)}.", -5], [f"{choice(currentGrades)}.", -5]]],
    ["So what do you think of the latest Conservative policy?", [["Pretty good I think", 2], ["It's brilliant, as expected of course.", 4], ["I'm not too sure...", -5]]],
    ["Last time we spoke you mentioned your course... remind me, dear, how are you planning to use that degree in the real world?", [["Well, helping people I guess!", 1], ["It'll help me when I take over the business I reckon.", 3], ["I'm not really sure to be honest.", -5]]],
    ["Do you enjoy the cultural life here? Have you been to any good exhibitions or performances recently?", [["Oh, absolutely, the art scene here is vibrant!", 2], ["I haven't really had the time, unfortunately.", -3], ["Yes, I regularly attend events at the gallery.", 4]]],
    ["How do you manage stress with such a demanding schedule?", [["Regular exercise and a good diet keep me balanced.", 3], ["It's tough, but I'm managing somehow.", -1], ["Stress? What stress?", -2]]],
    ["With your background, have you considered entering politics or social service?", [["Yes, I've thought about it quite seriously.", 2], ["Politics isn't really for me, I'm afraid.", -2], ["I'm more interested in private sector opportunities.", 1]]],
    ["What are your thoughts on austerity?", [["It was a necessary evil.", 2], ["Just wasted potential.", -2], ["Economics isn't really my cup of tea.", -5]]],
    ["Have you picked up any hobbies recently?", [["Yes, I've started painting. It's quite relaxing.", 1], ["Trying to find the time between studies is hard.", -3], ["I dabble in a bit of cooking. Keeps me grounded.", 3]]],
    ["What's your stance on the recent global environmental issues?", [["We need to act now, every small effort helps.", 0], ["It's all a bit exaggerated, isn't it?", 1], ["I try to stay informed, but it's overwhelming.", -3]]],
    ["Are you planning to travel this summer?", [["Yes, exploring new cultures is enriching.", 2], ["No plans yet, I might just visit family.", -1], ["Travel? I wish, my schedule is packed.", -3]]],
    ["What's your favorite cuisine? Have you tried making any dishes yourself?", [["I love Italian food and often make pasta at home.", 1], ["I prefer ordering in, less hassle.", -3], ["I'm adventurous. I try to cook different cuisines when I can.", 3]]],
    ["Can you believe the news this week?", [["Absolutely shocking, isn't it?", 1], ["I try to stay away from the news. Too depressing.", -2], ["It's hard to keep up with everything.", -1]]],
    ["Do you enjoy attending events like this?", [["Of course, it's always a pleasure to meet interesting people.", 2], ["They're alright, a bit too formal sometimes.", -4], ["I love these gatherings! Great food, great company!", 3]]],
    ["Who's the most interesting person you've met here tonight?", [["Everyone's been charming in their own way.", 2], ["I haven't really mingled much yet.", -8], ["You are, without a doubt!", 2]]],
    ["Any recent books you'd recommend?", [["I just finished a fascinating book on history. Would highly recommend.", 2], ["Not much of a reader, to be honest.", -2], ["There are a few, let me write them down for you later.", 1]]],
    ["What's your take on modern art?", [["It's an exciting evolution of expression.", 2], ["To be honest, I don't really get it.", -4], ["Some pieces are profound, others... not so much.", -1]]],
    ["Do you prefer vintage or modern wine?", [["There's nothing like a vintage wine.", 2], ["Modern wines are often underrated.", 1], ["I don't drink wine, actually.", -3]]],
    ["What's your opinion on the rise of digital currencies?", [["It's the future of finance.", 1], ["Far too volatile and risky.", 1], ["I really don't understand them.", -1]]],
    ["What historical period do you find most fascinating?", [["The Victorian era, such elegance and progress.", 2], ["The ancient civilizations hold my interest.", 1], ["Really I prefer to focus on the future.", -2]]],
    ["What genre of literature do you prefer?", [["Classics, they never go out of style.", 2], ["I love a good thriller novel.", -2], ["Reading isn't really my thing.", -7]]],
    ["What's your view on maintaining traditional values in modern times?", [["Absolutely crucial, we must uphold our traditions.", 2], ["Some adaptation is necessary, we must evolve.", 0], ["Traditions are often barriers to progress.", -4]]],
    ["Do you have a preferred season or time of year?", [["Spring, when everything is blooming.", 1], ["Winter, perfect for a bit of skiing.", 2], ["I'm not affected by the seasons much.", -1]]],
    ["Who is your favorite playwright or dramatist?", [["Shakespeare, without a doubt.", 1], ["I'm quite fond of Chekhov.", 2], ["Drama isn't really my scene.", -4]]],
    ["How do you keep informed about current events?", [["Newspapers and the internet normally.", 3], ["I catch up through social media.", -5], ["I prefer not to dwell on the news, too depressing.", -3]]],
    ["Do you play any sports?", [["I love football. It's a great way to connect with friends.", -2], ["Not really into sports, I'm more into other hobbies.", 0], ["Cricket! It has to be.", 3]]],
    ["How do you usually unwind after a long week?", [["A good book and a quiet room.", 1], ["Social gatherings like this one!", 3], ["Honestly, just catching up on sleep.", -3]]],
    ["Have any career aspirations you're willing to share?", [["I'm aiming for a leadership role in my field.", 2], ["Still exploring my options.", -2], ["I'd like to start my own business someday.", 2]]],
    ["What changes would you like to see in your field?", [["More innovation and less bureaucracy.", 2], ["Greater emphasis on practical skills.", 2], ["It's pretty good as it is, not much to change.", -2]]],
    ["What are your views on the monarchy's role in modern society?", [["Absolutely vital for our culture.", 3], ["It's an outdated institution.", -5], ["They're a great symbol of continuity.", 2]]],
    ["May I enquire, which club do you frequent for a touch of civilised company?", [["The Cavalry and Guards Club, naturally.", 3], ["Boodle's has always suited me well.", 1], ["I'm afraid I don't frequent clubs.", -5]]],
    ["Do you partake in the hunt when the season is upon us, or do you prefer to leave such pursuits to others?", [["Yes, I never miss the season.", 2], ["Occasionally, when invited.", 1], ["No, it's not really for me.", -3]]],
    ["How is your experience with pheasant shooting?", [["Absolutely, it's a family tradition.", 2], ["I've been a few times, always enjoyable.", 1], ["No, I don't participate in shoots.", -3]]],
    ["Did you make it to the Henley Royal Regatta this year? It's the highlight of the summer social calendar.", [["Of course, it's a highlight of the summer.", 2], ["Not this year, but I hope to next time.", 0], ["I'm afraid rowing isn't really my scene.", -3]]],
    ["Did you have the pleasure of attending Royal Ascot this season? The royal enclosure of course.", [["Yes, it was simply marvellous.", 2], ["Sadly, I couldn't make it this year.", 0], ["No, horse racing isn't my interest.", -3]]],
    ["Do you find yourself drawn to the ballet?", [["The ballet is always enchanting.", 2], ["I appreciate it on occasion.", 1], ["I'm not fond of ballet, to be honest.", -3]]],
    ["Have you any thoughts on the latest exhibition at the Royal Academy?", [["It was a triumph of contemporary art.", 2], ["Some pieces were quite striking, others less so.", 0], ["I must admit, I did not attend.", -2]]],
    ["Do you keep up with the goings-on at the House of Lords?", [["Naturally, one must remain informed.", 2], ["From time to time, when matters of interest arise.", 1], ["Politics rather bores me, I confess.", -2]]],
    ["Are you fond of yachting, or do you prefer more terrestrial pursuits?", [["Yachting is a family tradition, nothing compares.", 2], ["I enjoy it on occasion, but prefer the countryside.", 1], ["I have little interest in nautical activities.", -2]]],
    ["Do you enjoy a spot of croquet or perhaps prefer tennis on the lawn?", [["Croquet is a delightful way to spend an afternoon.", 2], ["I am partial to tennis, especially during the summer months.", 1], ["Neither sport has ever truly appealed to me.", -2]]],
]

alcoholQuestions = [
    "So how about ALCOHOL?",
    "Now, would you like ALCOHOL?",
    f"{memory['Name']}, could I get you ALCOHOL?",
    "How about I get you ALCOHOL?",
    "Here, have ALCOHOL!",
    "Would ALCOHOL interest you this evening?",
    "May I tempt you with ALCOHOL?",
    "Can I offer you ALCOHOL?",
    "What do you say to ALCOHOL?",
    "Can I get you ALCOHOL? It's quite splendid tonight.",
    f"Do you care for some ALCOHOL, {memory['Name']}?",
    "I insist you try the ALCOHOL, it's excellent.",
    "Might I suggest we toast with ALCOHOL?",
    "Is ALCOHOL to your liking tonight?",
    "Would ALCOHOL complement your meal?",
    "Care to join me in ALCOHOL?",
    "Feeling like ALCOHOL? It pairs wonderfully."
]

intervalPhrases = [
    "A stocky middle-aged lady turns to you to speak:",
    "They leave just as a tall, slim man grabs your attention:",
    "As they're turning away, a scruffy teenage girl approaches you:",
    "An elderly gentleman with a sharp gaze approaches, clearing his throat:",
    "A distinguished woman in an elegant gown gestures you closer:",
    "As some laughter grows and fades, a young man in a crisp suit leans in to chat:",
    "As they turn away, a charismatic lady with a bright smile engages you in conversation:",
    "A reserved academic from a nearby table strikes up a discussion:",
    "A poised young lady with a soft voice politely asks for your attention:",
    "The sound of clinking glasses precedes a charming old lady who beckons you over:",
    "A jovial man with a booming voice calls out to you from across the table:",
    "A broad-shouldered man with a military bearing turns to face you:",
    "A sharply dressed gentleman with an immaculate moustache inclines his head:",
    "A red-faced man smelling faintly of port squints at you:",
    "A distant cousin you barely recognise catches your eye expectantly:",
]

acceptPhrases = [
    "Of course!",
    "Yes, please!",
    "Excellent",
    "My favourite!",
    "Quite right",
]

declinePhrases = [
    "No thank you.",
    "I'll pass for now",
    "I shouldn't",
    "After this course",
    "I'll abstain for now",
]


def ps(x):
    Print(Scramble(x))

def s(x):
    if not devMode:
        sleep(x)

def Shuffle(x):
    for i in range(len(x) - 1, 0, -1):
        j = randint(0, i)
        x[i], x[j] = x[j], x[i]

def Scramble(text):
    global drunkenness; global letters
    new_sentence = ""
    for char in text:
        if char.isalpha():
            if random() < (0.667 * drunkenness) / 100:
                new_char = choice(letters)
                new_sentence += new_char.lower() if char.islower() else new_char.upper()
            else:
                new_sentence += char.lower() if char.islower() else char.upper()
        else:
            new_sentence += char
    return new_sentence

def AskQuestion():
    global reputation, courseCounter, alcoholCounter

    courseCounter += 1
    alcoholCounter += 1

    question = choice(questions)
    Shuffle(question[1])

    ps(question[0])
    s(5)

    buttonLabels = ["A", "B", "X"]

    Print("", flush=False)
    for i, option in enumerate(question[1]):
        Print(f"{buttonLabels[i]}: {Scramble(option[0])}", flush=False)
    Flush()

    oldReputation = reputation

    selectedIndex = None
    prevA = prevB = prevX = False

    while selectedIndex is None:
        curA = Pressed(iA)
        curB = Pressed(iB)
        curX = Pressed(iX)

        if curA and not prevA:
            selectedIndex = 0
        elif curB and not prevB:
            selectedIndex = 1
        elif curX and not prevX:
            selectedIndex = 2

        prevA = curA
        prevB = curB
        prevX = curX

        sleep(0.01)

    reputation += question[1][selectedIndex][1]
    s(2)

    if reputation > oldReputation:
        Print(flush=False)
        ps(choice(goodReactions))
    else:
        Print(flush=False)
        ps(choice(badReactions))

def OfferAlcohol():
    global reputation, drunkenness, courseCounter, alcoholCounter
    courseCounter += 1
    alcoholCounter = 0

    currentAlcohol = choice(alcohols)
    ps(choice(alcoholQuestions).replace("ALCOHOL", currentAlcohol[0]))
    sleep(3)
    Print("", flush=False)
    Print(f"A: {choice(acceptPhrases)}", flush=False)
    Print(f"B: {choice(declinePhrases)}")

    selectedYes = None
    prevA = prevB = False

    while selectedYes is None:
        curA = Pressed(iA)
        curB = Pressed(iB)

        if curA and not prevA:
            selectedYes = True
        elif curB and not prevB:
            selectedYes = False

        prevA = curA
        prevB = curB
        sleep(0.01)
    s(2)

    if selectedYes:
        Print(flush=False)
        ps(choice(goodReactions))
        reputation += 2
        drunkenness += currentAlcohol[1]
    else:
        Print(flush=False)
        ps(choice(badReactions))
        reputation -= 8

def NextCourse():
    global courses; global currentCourse; global courseCounter; global alcoholCounter
    courseCounter = 0
    alcoholCounter += 1
    currentCourse += 1
    if random() > 0.75: #sometimes skip a course; skipping it here rather than earlier avoids index error
        currentCourse += 1
    if currentCourse-1 <= len(courses):
        s(2)
        try:
            ps(f"\nA new course is arriving: {courses[currentCourse-1]}")
        except IndexError:
            EndGame()
    else:
        EndGame()

def EndGame():
    global reputation; global finished; global drunkenness
    finished = True
    Print(flush=False)
    drunkenness *= 0.25
    s(3)
    ps("Finally the party ends")
    s(3)
    ps("You see you father just before you go off to bed:")
    s(4)
    if reputation >= 100:
        ps(f"'I'm proud of you {memory["Name"]}, you did really well'")
    elif reputation >= 85:
        ps(f"'Well done {memory["Name"]}, you really made a great impression'")
    elif reputation >= 65:
        ps(f"'Well done {memory["Name"]}, you did a good job'")
    elif reputation >= 50:
        ps(f"'Well done {memory["Name"]}, you did fine'")
    elif reputation >= 35:
        ps(f"'Thanks for coming {memory["Name"]}'")
    elif reputation >= 15:
        ps(f"'I know you're better than this {memory["Name"]}'")
    elif reputation >= 1:
        ps(f"'What the fuck were you thinking {memory["Name"]}?'")
    else:
        ps(f"'Go home {memory["Name"]}, you're not welcome here'")
    s(5)
    Print(flush=False)
    Print(f"Your final score is: {reputation}")

def Hospitalised():
    global finished
    Print(flush=False)
    s(5)
    Print("You collapsed from alcohol poisoning and were taken to hospital")
    s(3)
    Print("You embarrassed yourself and your parents more than they even thought possible")
    s(5)
    Print(flush=False)
    Print("You lose")
    Print(flush=False)
    s(3)
    finished = True

Print("You promised your father you'd see him again soon")
s(2.5)
Print("Of course you had to let him choose the occasion")
s(2.5)
Print("So here you are, at a black-tie dinner party")
s(2.5)
Print("You've been given one simple instruction:")
s(2.5)
Print("Don't embarrass yourself")
s(2.5)
Print("Regardless, you've just arrived home")
s(2.5)
Print("You brace yourself for the questions, reminding yourself of anything anyone might ask you:\n")
s(4)
ps(f"Name: {memory["Name"]}\nAge: {memory["Age"]}\nUniversity: {memory["University"]}\nSubject: {memory["Subject"]}\nCurrent Grade: {memory["Current Grade"]}")
s(10)
Print("\nThe guests start to arrive...")
s(3)

ps(f"It's time for the welcome drinks\n")
s(3)
ps(choice(intervalPhrases))

if random() < 0.75:
    AskQuestion()
else:
    OfferAlcohol()
s(1)

while not finished:
    if randint(3,5) >= courseCounter: #slowly increases the chance there will be a new course for every time that isn't chosen
        if random() < 0.25:
            Print(flush=False)
            ps(choice(intervalPhrases))
        if randint(1,4) >= alcoholCounter:
            AskQuestion()
        else:
            OfferAlcohol()
    else:
        NextCourse()
    
    if drunkenness >= 100:
        reputation = 0
        Hospitalised()
    s(1)
