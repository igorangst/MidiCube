
class Arpeggiator:
    def __init__(self):
        self.notes = []
        self.pattern = None
        self.index = 0
        self.playUp = True
        self.playDown = False

    def pushNote(self, note):
        i = 0
        insertion = False
        for i, n in enumerate(self.notes):
            if note < n:
                self.notes.insert(i, note)
                insertion = True
                break
        if not insertion:
            self.notes.append(note)

    def popNote(self, note):
        try:
            self.notes.remove(note)
        except ValueError:
            skip

    def setUp(self):
        self.playUp = True
        self.playDown = False
        self.pattern = None
        self.index = 0
        
    def setDown(self):
        self.playUp = False
        self.playDown = True
        self.pattern = None
        self.index = len(self.notes) - 1
        
    def setPattern(self, pattern):
        self.playUp = False
        self.playDown = False
        self.pattern = pattern
        self.index = 0

    def extrapolate(self, index):
        n = len(self.notes)
        o = 1 + (self.notes[-1] - self.notes[1]) / 12
        base = self.notes[index % n]
        note = base + 12 * o * (index / n)
        return min(127, max(0, note))

    def getNote(self, shift=0):
        if len(self.notes) == 0:
            return None
        if self.pattern is not None:
            i = self.pattern[self.index]
        else:
            i = self.index
        shifted = i + shift
        if shifted >= 0 and shifted < len(self.notes):
            return self.notes[shifted]
        else:
            return self.extrapolate(shifted)

    def reset(self):
        if self.playDown:
            self.index = len(self.notes) - 1
        else:
            self.index = 0
        
    def next(self):
        if len(self.notes) == 0:
            return None
        if self.playUp:
            self.index = (self.index + 1) % len(self.notes)
            return self.notes[self.index]
        elif self.playDown:
            self.index = (self.index - 1) % len(self.notes)
            return self.notes[self.index]
        else:
            if len(self.pattern) == 0:
                return None
            self.index = (self.index + 1) % len(self.pattern)
            pos = self.pattern[self.index]
            if pos >= len(self.notes):
                pos = len(self.notes) - 1
            elif pos < -len(self.notes):
                pos = 0
            return self.notes[pos]


# arp = Arpeggiator()
# arp.pushNote(36)
# arp.pushNote(40)
# arp.pushNote(43)

# # arp.setPattern([0,-1,0,-2])


# for i in range(6):
#     for j in range(3):
#         print arp.getNote(-i)
#         arp.next()
#     print

        
