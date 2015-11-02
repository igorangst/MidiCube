import time
import threading
import alsaseq
import sys

from threading import Timer
from numpy import interp
from alsamidi import *

import sync
import command

from util import *


class State:
    gyro      = [0.0, 0.0, 0.0] # x,y,z positions
    cc        = [0, 0]          # mapped y/z controller positions
    rapidFire = False           # 1 = single shot, 2 = rapid fire
    trigger   = False           # trigger is on
    lastNote  = None            # last note played
    bendOffs  = 0.0             # offset for pitch bend
    bend      = 8192            # pitch bend value
    bpm       = 120             # rapid fire speed

class Scheduler (threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.state = State()
        self.dispatcher = None
        self.lastStrike = None

    def pitch(self):
        if self.state.rapidFire:
            return 48   # MIDI value for C3
        else:
            loNote = 36 # MIDI value for C2
            hiNote = 60 # MIDI value for C4        
            return int(interp(cc[0], [-90,90], [loNote, hiNote]))

    def bend(self):
        if self.state.rapidFire:
            return 0
        else:
            centered = self.state.cc[0] - self.state.bendOffs
            return int(interp(centered, [-90,90], [0, 16383]))

    def printStatus(self):
        sys.stdout.write("[X:%6.1f Y:%6.1f Z:%6.1f]\r" 
                         % (self.state.gyro[0], 
                            self.state.gyro[1], 
                            self.state.gyro[2] ))
        sys.stdout.flush()

    def stopNote(self):
        if self.state.lastNote == None:
            return
        else:
            alsaseq.output(noteOffEvent(self.state.lastNote))

    def bpm(self):
        x = self.state.gyro[0]
        return int(interp(x, [-90,0,90], [60,120,480]))

    def playNote(self):
        if self.state.lastNote:
            self.stopNote()
        note = Note(self.pitch())
        alsaseq.output(noteOnEvent(note))
        self.lastStrike = time.time()
        self.state.lastNote = note
        if self.state.rapidFire and self.state.trigger: 
            duration = 60.0 / self.bpm()
            self.dispatcher = self.scheduleNote(duration)

    def setPos(self, x, y, z):
        self.state.gyro = [x, y, z]
        self.printStatus()
        if not self.state.rapidFire:
            newBend = self.bend()
            if self.state.bend <> newBend:
                self.state.bend = newBend
                alsaseq.output(pitchBendEvent(newBend))
        else:
            newBPM = self.bpm()
            if self.state.bpm <> newBPM:
                if self.dispatcher:
                    self.dispatcher.cancel()
                self.state.bpm = newBPM
                duration = 60.0 / newBPM
                now = time.time()
                elapsed = now - self.lastStrike
                if elapsed > duration: # preemption
                    self.playNote() 
                else:                  # delay next strike
                    rest = duration - elapsed
                    self.dispatcher = self.scheduleNote(rest)
        newCCy = int(interp(y, [-90, 90], [0, 127]))
        if newCCy <> self.state.cc[0]:
            self.state.cc[0] = newCCy
            alsaseq.output(ccEvent(3, newCCy))
        newCCz = int(interp(z, [-90, 90], [0, 127]))
        if newCCz <> self.state.cc[1]:
            self.state.cc[1] = newCCz
            alsaseq.output(ccEvent(4, newCCz))                   

    def scheduleNote(self, duration):
        timer = Timer(duration, self.playNote)
        timer.start()
        return timer

    def run(self):
        print "starting scheduler"
        while not sync.terminate.isSet():
            sync.queueEvent.wait()
            sync.queueEvent.clear()
            while not sync.queue.empty():
                sync.qLock.acquire()
                (cmd, params) = sync.queue.get()
                sync.qLock.release()
                if cmd == command.TRG_ON:
#                    print "scheduler: TRG_ON"
                    self.state.trigger = True
                    self.state.bendOffs = self.state.gyro[0]
                    self.playNote()                    
                elif cmd == command.TRG_OFF:
#                    print "scheduler: TRG_OFF"
                    self.state.trigger = False
                    if self.dispatcher:
                        self.dispatcher.cancel()
                    self.stopNote()                    
                elif cmd == command.RFI_ON:
#                    print "scheduler: RFI_ON"
                    self.state.rapidFire = True
                    if self.state.trigger:
                        self.playNote()
                elif cmd == command.RFI_OFF:
#                    print "scheduler: RFI_OFF"
                    self.state.rapidFire = False
                    if self.dispatcher:
                        self.dispatcher.cancel()
                    if self.state.trigger:
                        self.playNote()
                elif cmd == command.SET_POS:
#                    print "scheduler: SET_POS"
                    (x, y, z) = params
                    self.setPos(x, y, z)
                else:
                    print "Illegal command in queue"
        print "stopping scheduler"
