
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
            # skip

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

    def getNote(self):
        if self.pattern is not None:
            i = self.pattern[self.index]
        else:
            i = self.index
        return self.notes[min(i, len(self.notes)-1)]

    def nextNote(self):
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


arp = Arpeggiator()
arp.pushNote(1)
arp.pushNote(22)
arp.pushNote(333)
arp.pushNote(4444)

arp.setPattern([0,-1,0,-2])

for i in range(20):
    print arp.getNote()
    arp.nextNote()
