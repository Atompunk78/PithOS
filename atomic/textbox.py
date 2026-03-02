# NB this module was written primarily by ChatGPT
from atomic.utilities import DrawText

_textBox = None

class TextBox:
    def __init__(self, display, font,
                 startX, startY, widthChars, heightChars,
                 fg, bg):

        self.display = display
        self.font = font
        self.charW = font.WIDTH
        self.charH = font.HEIGHT

        self.startX = startX
        self.startY = startY
        self.widthChars = widthChars
        self.heightChars = heightChars

        self.widthPx = widthChars * self.charW
        self.heightPx = heightChars * self.charH

        self.fg = fg
        self.bg = bg

        self.lines = [""] * heightChars
        self.didScroll = True

        self.curRow = 0
        self.curCol = 0

        self.dirtyRow = 0
        self.dirtyFrom = 0
        self.dirtyTo = 0


    def Clear(self):
        for i in range(self.heightChars):
            self.lines[i] = ""

        self.display.fill_rect(
            self.startX,
            self.startY,
            self.widthPx,
            self.heightPx,
            self.bg
        )

        self.didScroll = False
        self.curRow = 0
        self.curCol = 0
        self.dirtyRow = 0
        self.dirtyFrom = 0
        self.dirtyTo = 0

    def Write(self, text, wrapWords=True):
        s = str(text)

        if not wrapWords:
            # Original behaviour: character-based wrapping
            for ch in s:
                if ch == "\n":
                    self._NewLine()
                elif ch == "\t":
                    self._WriteChars("    ")
                elif ch != "\r":
                    self._WriteChars(ch)
            return

        # Word-wrapping behaviour:
        token = ""
        for ch in s:
            if ch == "\n":
                if token:
                    self._WriteToken(token)
                    token = ""
                self._NewLine()
            elif ch == "\t":
                if token:
                    self._WriteToken(token)
                    token = ""
                self._WriteToken("    ")
            elif ch == " ":
                if token:
                    self._WriteToken(token)
                    token = ""
                self._WriteToken(" ")
            elif ch == "\r":
                pass
            else:
                token += ch

        if token:
            self._WriteToken(token)


    def _WriteToken(self, token):
        # Avoid starting a new line with spaces
        if token == " " and self.curCol == 0:
            return

        # If a non-space token won't fit on this line, newline first
        if token != " " and self.curCol != 0 and (self.curCol + len(token) > self.widthChars):
            self._NewLine()

        # If a single token is longer than a line, fall back to char-writing
        if len(token) > self.widthChars:
            self._WriteChars(token)
            return

        self._WriteChars(token)

    def _WriteChars(self, chars):
        for ch in chars:

            # Soft wrap
            if self.curCol >= self.widthChars:
                self._NewLine()

            line = self.lines[self.curRow]

            # Ensure line is long enough (normally it will be)
            if len(line) < self.curCol:
                line = line + (" " * (self.curCol - len(line)))

            # Append or overwrite at cursor
            if len(line) == self.curCol:
                line = line + ch
            else:
                line = line[:self.curCol] + ch + line[self.curCol + 1:]

            # Clamp line length
            if len(line) > self.widthChars:
                line = line[:self.widthChars]

            self.lines[self.curRow] = line

            self.curCol += 1
            if self.curRow < self.dirtyFrom:
                self.dirtyFrom = self.curRow
            if self.curRow > self.dirtyTo:
                self.dirtyTo = self.curRow

    def Flush(self):
        self._Redraw()

    def _NewLine(self):
        self.curCol = 0

        # Move down if we can
        if self.curRow < self.heightChars - 1:
            oldRow = self.curRow
            self.curRow += 1

            # Mark the row we just finished writing as dirty
            if oldRow < self.dirtyFrom:
                self.dirtyFrom = oldRow
            if oldRow > self.dirtyTo:
                self.dirtyTo = oldRow

            return

        # Otherwise scroll
        for r in range(self.heightChars - 1):
            self.lines[r] = self.lines[r + 1]

        self.lines[self.heightChars - 1] = ""
        self.didScroll = True

        # After a scroll we do a full redraw, so dirty range doesn't matter much,
        # but keep it sane anyway.
        self.dirtyFrom = 0
        self.dirtyTo = self.heightChars - 1

    def _Redraw(self):
        disp = self.display
        font = self.font
        fg = self.fg
        bg = self.bg

        startX = self.startX
        startY = self.startY
        widthPx = self.widthPx
        heightPx = self.heightPx
        charH = self.charH

        if self.didScroll:
            # Full redraw of textbox region
            disp.fill_rect(startX, startY, widthPx, heightPx, bg)

            for r in range(self.heightChars):
                line = self.lines[r]
                if line:
                    DrawText(disp, font, line, startX, startY + r * charH, fg, bg, 0, 0)

            self.didScroll = False

            # Reset dirty range
            self.dirtyFrom = self.curRow
            self.dirtyTo = self.curRow
            return

        # Redraw only the rows that changed
        r0 = self.dirtyFrom
        r1 = self.dirtyTo

        # Clamp (safety)
        if r0 < 0:
            r0 = 0
        if r1 >= self.heightChars:
            r1 = self.heightChars - 1
        if r1 < r0:
            r0 = r1 = self.curRow

        for r in range(r0, r1 + 1):
            rowY = startY + r * charH
            disp.fill_rect(startX, rowY, widthPx, charH, bg)

            line = self.lines[r]
            if line:
                DrawText(disp, font, line, startX, rowY, fg, bg, 0, 0)

        # Reset dirty range
        self.dirtyFrom = self.curRow
        self.dirtyTo = self.curRow


def CreateTextBox(display, font,
                  startX, startY,
                  widthChars, heightChars,
                  fg, bg):
    global _textBox

    _textBox = TextBox(
        display, font,
        startX, startY, widthChars, heightChars,
        fg, bg
    )

    _textBox.Clear()

def Print(*args, sep=" ", end="\n", flush=True, wrapWords=True):
    global _textBox
    text = sep.join(map(str, args)) + str(end)
    _textBox.Write(text, wrapWords=wrapWords)

    if flush:
        _textBox.Flush()

def Flush():
    global _textBox
    if _textBox:
        _textBox.Flush()
