import time
import threading
import alsaseq
import sys
import logging

from threading import Timer
from numpy import interp
from alsamidi import *

import sync
import command
import arpeg

from util import *
from params import *

class State:
    gyro      = [0.0, 0.0, 0.0] # x,y,z positions
    center    = [0.0, 0.0, 0.0] # x,y,z positions at last trigger time
    ccs       = {}              # mapped controller positions
    rapidFire = False           # 1 = single shot, 2 = rapid fire
    trigger   = False           # trigger is on
    lastNote  = None            # last note played
    bendOffs  = 0.0             # offset for pitch bend
    pitchOffs = 0.0             # offset for note pitch (reset on mode change)
    bend      = 8192            # pitch bend value
    bpm       = 120             # rapid fire speed
    def mode(self):
        if self.rapidFire:
            return 1
        else: 
            return 0
    
class Scheduler (threading.Thread):
    def __init__(self, params):
        threading.Thread.__init__(self)
        self.params = params
        self.dispatcher = None
        self.lastStrike = None
        self.state = State()
        self.arpeg = arpeg.Arpeggiator()
        ccs = []
        for i in range(0,3): # collect all controllers
            ccs += self.params.controllersOSM[i]
            ccs += self.params.controllersRFI[i]
        for k in ccs:
            self.state.ccs[k] = 64

    def printStatus(self):
        def bool2str(b):
            if b:
                return '*'
            else:
                return ' '
        sys.stdout.write("[X:%6.1f Y:%6.1f Z:%6.1f] [TRG: %s] [RFI: %s] [BEND: %5i]\r (Arp: %i)" 
                         % (self.state.gyro[0], 
                            self.state.gyro[1], 
                            self.state.gyro[2], 
                            bool2str(self.state.trigger),
                            bool2str(self.state.rapidFire),
                            self.state.bend, len(self.arpeg.notes)))
        sys.stdout.flush()

    def pitch(self):
        axis = self.params.setNote[self.state.mode()]                    
        if self.state.rapidFire and self.params.arpRFI:
            # Arpeggiator
            if axis != NO_AXIS:
                angle = self.state.gyro[axis] - self.state.pitchOffs
                shift = int(interp(angle, [-90,90], [-8,8]))
            else:
                shift = 0
            note = self.arpeg.getNote(shift)
            return note
        else:
            # Standard pitch select
            if self.params.scale is None:
                noteRange = 12 * self.params.octaves
            else:
                noteRange = 7 * self.params.octaves
            if axis == NO_AXIS:
                return 36   # MIDI value for C2
            else:
                angle = self.state.gyro[axis] - self.state.pitchOffs
                noteIndex = int(interp(angle, [-90,90], [-noteRange, noteRange]))
                return noteOnScale(self.params.scale, noteIndex)

    def centerPitch(self):
        axis = self.params.setNote[self.state.mode()]
        if axis == NO_AXIS:
            self.state.pitchOffs = 0.0
        else:
            self.state.pitchOffs = self.state.gyro[axis]

    def stopNote(self):        
        if self.state.lastNote is None:
            return
        else:
            alsaseq.output(noteOffEvent(self.state.lastNote))
            self.state.lastNote = None
            logging.debug("stop note %s" % str(self.state.lastNote))

    def playNote(self):
        if self.state.lastNote:
            self.stopNote()
            self.arpeg.next()
        note = Note(self.pitch())
        if note.valid():
            alsaseq.output(noteOnEvent(note))
            logging.debug("play note %s" % str(note))
            self.state.lastNote = note
        self.lastStrike = time.time()
        if self.state.rapidFire and self.state.trigger: 
            duration = 60.0 / self.bpm()
            self.dispatcher = self.scheduleNote(duration)

    def scheduleNote(self, duration):
        timer = Timer(duration, self.playNote)
        timer.start()
        logging.debug("dispatch note in %f s" % duration)
        return timer

    def bpm(self):
        axis = self.params.setSpeed
        if axis == NO_AXIS:
            return 120
        else:
            p = self.state.gyro[axis] - self.state.center[axis]
            return int(interp(p, [-90,0,90], [30,120,480]))

    def setBPM(self):
        newBPM = self.bpm()
        if self.state.bpm <> newBPM:
            if self.dispatcher:
                self.dispatcher.cancel()
                self.dispatcher = None
                logging.debug("cancel dispatched note")
            self.state.bpm = newBPM
            if self.state.trigger:
                duration = 60.0 / newBPM
                now = time.time()
                elapsed = now - self.lastStrike
                if elapsed > duration: # preemption
                    self.playNote() 
                else:                  # delay next strike
                    rest = duration - elapsed
                    self.dispatcher = self.scheduleNote(rest)        

    def bend(self):
        axis = self.params.setBend[self.state.mode()]
        if axis == NO_AXIS:
            return 8192
        else:
            centered = self.state.gyro[axis] - self.state.bendOffs
            return int(interp(centered, [-90,90], [0, 16383]))

    def setBend(self):
        newBend = self.bend()
        if self.state.bend != newBend:
            self.state.bend = newBend
            alsaseq.output(pitchBendEvent(newBend))        

    def resetBend(self):
        axis = self.params.setBend[self.state.mode()]
        if axis != NO_AXIS:
            self.state.bendOffs = self.state.gyro[axis]
            self.state.bend = 8192
            alsaseq.output(pitchBendEvent(self.state.bend))

    def setControllers(self):
        def setAxisControllers(axis):
            if self.state.rapidFire:
                ccs = self.params.controllersRFI[axis]
            else:
                ccs = self.params.controllersOSM[axis]
            centered = self.state.gyro[axis] - self.state.center[axis]
            newValue = int(interp(centered, [-90,90], [0,127]))
            for k in ccs:
                oldValue = self.state.ccs[k]
                if newValue != oldValue:
                    self.state.ccs[k] = newValue
                    alsaseq.output(ccEvent(k, newValue))
        for axis in range(0,3):
            setAxisControllers(axis)                                    

    def setPos(self, x, y, z):
        self.state.gyro = [x, y, z]
        self.printStatus()
        self.setBend()
        if self.state.rapidFire:
            self.setBPM()
        if self.state.trigger:
            self.setControllers()
            if not self.state.rapidFire and self.params.gliss:
                newPitch = self.pitch()
                if self.state.lastNote is not None:
                    if newPitch != self.state.lastNote.pitch:
                        self.stopNote()
                        self.resetBend()
                        self.playNote()                    

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
                    logging.debug("received TRG_ON")
                    if not self.state.trigger:
                        self.state.trigger = True
                        self.resetBend()
                        self.state.center = self.state.gyro # FIXME: reset controls?
                        self.arpeg.reset()
                        self.playNote()                    
                elif cmd == command.TRG_OFF:
                    logging.debug("received TRG_OFF")
                    if self.state.trigger:
                        self.state.trigger = False
                        if self.dispatcher:                        
                            self.dispatcher.cancel()
                            self.dispatcher = None
                            logging.debug("cancel dispatched note")
                        self.stopNote()                    
                elif cmd == command.RFI_ON:
                    logging.debug("received RFI_ON")
                    if not self.state.rapidFire:
                        self.state.rapidFire = True
                        # FIXME: recenter pitch on mode change for now
                        self.centerPitch()
                        if self.state.trigger:
                            self.arpeg.reset()
                            self.playNote()
                elif cmd == command.RFI_OFF:
                    logging.debug("received RFI_OFF")
                    if self.state.rapidFire:
                        self.state.rapidFire = False
                        # FIXME: recenter pitch on mode change for now
                        self.centerPitch()
                        if self.dispatcher:
                            self.dispatcher.cancel()
                            self.dispatcher = None
                            logging.debug("cancel dispatched note")
                        if self.state.trigger:
                            self.playNote()
                elif cmd == command.SET_POS:
                    logging.debug("received SET_POS")
                    (x, y, z) = params
                    self.setPos(x, y, z)
                elif cmd == command.PSH_NOTE:
                    self.arpeg.pushNote(params)
                    logging.debug("arpeggiator push note %i" % params)
                elif cmd == command.POP_NOTE:
                    self.arpeg.popNote(params)
                    logging.debug("arpeggiator pop note %i" % params)
                else:
                    logging.warning("Illegal command in queue")
        print "stopping scheduler"
