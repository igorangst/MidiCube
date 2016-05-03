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

class Controller:
    def __init__(self, axis=NO_AXIS, cc=0, mode=CTRL_CENTER):
        self.axis = axis
        self.cc = cc
        self.mode = mode
        self.center = 0.0
        self.value = -1

    # set center position depending on controller mode
    def recenter(self, pos):
        if self.mode == CTRL_CENTER:
            self.center = pos
        elif self.mode == CTRL_DRAG:
            self.center = pos - interp(self.value, [0,127], [-90,90])

    # set to new position, returns True if value changed, False otherwise
    def update(self, pos):
        angle = pos - self.center
        if self.mode == CTRL_FREE:
            if angle > 90:
                self.center = pos - 90
            elif angle < -90:
                self.center = pos + 90
        newvalue = int(interp(angle, [-90,90], [0,127]))
        if newvalue != self.value:
            self.value = newvalue
            return True
        else:
            return False

class State:
    gyro      = [0.0, 0.0, 0.0] # x,y,z positions
    center    = [0.0, 0.0, 0.0] # x,y,z positions at last trigger time
    ccs       = [[],[]]         # controllers in one shot and rapid fire mode
    rapidFire = False           # 1 = single shot, 2 = rapid fire
    trigger   = False           # trigger is on
    lastNote  = None            # last note played
    bendOffs  = 0.0             # offset for pitch bend
    pitchOffs = 0.0             # offset for note pitch (reset on mode change)
    bend      = 8192            # pitch bend value
    bpm       = 120             # rapid fire speed (free-wheeling)
    tickMod   = 12              # rapid fire speed (quantised)
    ticks     = 0               # MIDI ticks since transport start
    running   = False           # MIDI transport status    
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
        self.arpeg = arpeg.Arpeggiator(params.pattern)
        for axis in range(0,3): # collect all controllers
            for (k,m) in self.params.controllersOSM[axis]:
                cc = Controller(axis=axis, cc=k, mode=m)
                self.state.ccs[0].append(cc)
            for (k,m) in self.params.controllersRFI[axis]:
                cc = Controller(axis=axis, cc=k, mode=m)
                self.state.ccs[1].append(cc)

    def printStatus(self):
        def bool2str(b):
            if b:
                return '*'
            else:
                return ' '
        sys.stdout.write("[X:%6.1f Y:%6.1f Z:%6.1f] [TRG: %s] [RFI: %s] [BEND: %5i] [ARP: %i] [Pitch center: %6.1f]\r" 
                         % (self.state.gyro[0], 
                            self.state.gyro[1], 
                            self.state.gyro[2], 
                            bool2str(self.state.trigger),
                            bool2str(self.state.rapidFire),
                            self.state.bend, len(self.arpeg.notes), self.state.pitchOffs))
        sys.stdout.flush()

    def pitch(self):
        axis = self.params.setNote[self.state.mode()]                    
        if self.state.rapidFire and self.params.arpRFI:
            # Arpeggiator
            if axis != NO_AXIS:
                self.reframePitch()
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
                self.reframePitch()
                angle = self.state.gyro[axis] - self.state.pitchOffs
                noteIndex = int(interp(angle, [-90,90], [-noteRange, noteRange]))
                return noteOnScale(self.params.scale, noteIndex)

    # check if pitch axis is out of [-90,90] range and recenter if necessary
    def reframePitch(self):
        axis = self.params.setNote[self.state.mode()]
        if axis != NO_AXIS:
            angle = self.state.gyro[axis] - self.state.pitchOffs
            if angle > 90:
                self.state.pitchOffs = self.state.gyro[axis] - 90
            elif angle < -90:
                self.state.pitchOffs = self.state.gyro[axis] + 90

    # set center pitch to current gyro position
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
            alsaseq.output(noteOnEvent(note, chan=self.params.midiChan))
            logging.debug("play note %s" % str(note))
            self.state.lastNote = note
        self.lastStrike = time.time()
        if not self.params.quant and self.state.rapidFire and self.state.trigger: 
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

    def setQuantisation(self):
        axis = self.params.setSpeed
        mods = [48, 36, 32, 24, 18, 16, 12, 8, 6, 4, 3, 2]
        mod = 12
        if axis <> NO_AXIS:
            p = self.state.gyro[axis] - self.state.center[axis]
            i = int(interp(p, [-90,0,90], [0,6,11]))
            mod = mods[i]
        self.state.tickMod = mod

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
            alsaseq.output(pitchBendEvent(newBend, chan=self.params.midiChan))

    def resetBend(self):
        axis = self.params.setBend[self.state.mode()]
        if axis != NO_AXIS:
            self.state.bendOffs = self.state.gyro[axis]
            self.state.bend = 8192
            alsaseq.output(pitchBendEvent(self.state.bend, chan=self.params.midiChan))
    
    def centerControllers(self):
        ccs = self.state.ccs[self.state.mode()]
        for cc in ccs:
            cc.recenter(self.state.gyro[cc.axis])        

    def setControllers(self):
        ccs = self.state.ccs[self.state.mode()]
        for cc in ccs:
            if cc.update(self.state.gyro[cc.axis]):
                alsaseq.output(ccEvent(cc.cc, cc.value, chan=self.params.midiChan))

    def setPos(self, x, y, z):
        self.state.gyro = [x, y, z]
        self.printStatus()
        self.setBend()
        if self.state.rapidFire:
            if self.params.quant:
                self.setQuantisation()
            else:
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
                        self.state.center = self.state.gyro 
                        self.centerControllers()
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
                        self.centerPitch()
                        if self.state.trigger:
                            self.centerControllers()
                            self.arpeg.reset()
                            self.playNote()
                elif cmd == command.RFI_OFF:
                    logging.debug("received RFI_OFF")
                    if self.state.rapidFire:
                        self.state.rapidFire = False
                        self.centerPitch()
                        if self.dispatcher:
                            self.dispatcher.cancel()
                            self.dispatcher = None
                            logging.debug("cancel dispatched note")
                        if self.state.trigger:
                            self.centerControllers()
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
                elif cmd == command.TRP_START:
                    self.state.running = True
                    self.state.ticks = 0
                    if self.state.rapidFire and self.params.quant and self.state.trigger:
                        self.arpeg.reset()
                        self.playNote()
                    logging.debug("transport start")
                elif cmd == command.TRP_STOP:
                    self.state.running = False
                    logging.debug("transport stop")
                elif cmd == command.TRP_TICK:
                    self.state.ticks = self.state.ticks + 1
                    if self.state.trigger and self.state.rapidFire and self.params.quant and (self.state.ticks % self.state.tickMod == 0):
                        self.playNote()
                else:
                    logging.warning("Illegal command in queue")
        print "stopping scheduler"
