import signal
import time

class TimeoutError(Exception):
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
