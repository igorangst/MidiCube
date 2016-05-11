import signal
import time
import subprocess
import re

class TimeoutError(Exception):
    pass

class DisconnectError(Exception):
    pass

class timeout:
    def __init__(self, seconds=1, error_message='Timeout'):
        self.seconds = seconds
        self.error_message = error_message
    def handle_timeout(self, signum, frame):
        raise TimeoutError(self.error_message)
    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)
    def __exit__(self, type, value, traceback):
        signal.alarm(0)

class Note:
    def __init__(self, pitch, velocity=127):
        self.pitch = pitch
        self.velocity = velocity
    def __str__(self):
        return "(pitch:%i, vel:%i)" % (self.pitch, self.velocity)
    def valid(self):
        if self.pitch is None:
            return False
        if self.pitch < 0:
            return False
        if self.pitch > 127:
            return False
        return True

def ccEvent(cc, val, chan=1):
    return (10, 0, 0, 253, (0, 0), (0, 0), (0, 0), 
            (chan-1, 0, 0, 0, cc, val))

def noteOnEvent(note, chan=1):
    return (6, 0, 0, 253, (0, 0), (0, 0), (0, 0),
            (chan-1, note.pitch, note.velocity, 0, 0))

def noteOffEvent(note, chan=1):
    return (7, 0, 0, 253, (0, 0), (0, 0), (0, 0),
            (chan-1, note.pitch, note.velocity, 0, 0))

def pitchBendEvent(pitch, chan=1):
    return (13, 0, 0, 253, (0, 0), (0, 0), (0, 0), 
            (0, 61, 0, 0, 0, pitch-8192))

majorScale = [0, 2, 4, 5, 7, 9, 11]
minorScale = [0, 2, 3, 5, 7, 8, 10]

noteNames = ['c', 'c#', 'd', 'd#', 'e', 'f', 
             'f#', 'g', 'g#', 'a', 'a#', 'b']
basicNote = {'c' : 36,
             'c#': 37,
             'd' : 38,
             'd#': 39, 
             'e' : 40,
             'f' : 41,
             'f#': 42, 
             'g' : 43,
             'g#': 44,
             'a' : 45,
             'a#': 46,
             'b' : 47,
             'h' : 47}

# get MIDI code for a given note and octave
def getNote(note, octave):
    note = note.lower()
    base = basicNote.get(note, 36) - 36
    return base + 12*octave

# get MIDI code for a note restricted to a specific scale.
# note = 0 returns the basic note, negative and positive values 
# will move down and up on the scale
def noteOnScale(scale = None, note = 0):
    if scale is None:
        # chromatic scale
        return basicNote.get('c') + note

    isMajor = scale[0].isupper()
    scale = scale.lower()
    base = basicNote.get(scale, 36)
    baseOctave = base + 12 * (note / 7)
    def frameNote(x):
        return max(1, min(127, x))
    if isMajor:
        # major scale
        return frameNote(baseOctave + majorScale[note % 7])
    else:
        # minor scale
        return frameNote(baseOctave + minorScale[note % 7])



# get a dictionary of all active MIDI devices, mapping names to device numbers
def midiDevices():
    lines = subprocess.check_output(["aconnect", "-i"])
    for line in lines.split('\n'):
        m = re.search("client (\d+): '([a-zA-Z0-9\s]+)'", line)
        if m:
            print m.group(1) + " => " + m.group(2)
