import time
import threading
import alsaseq
import sys
import logging

from threading import Timer
from numpy import interp,sin
from math import pi
from alsamidi import *

import sync
import command
import arpeg

from util import *
from params import *

class LFO:
    def __init__(self, cc, wav, params):
        self.wav = wav         # Waveform
        self.cc = cc           # index of MIDI controller to write
        self.params = params   # global parameters
        self.value = 0         # current value of MIDI cc
        self.freq = 1.0        # LFO frequency in Hz
        self.amplitude = 1.0   # LFO amplitude
        self.rate = 67         # sample rate
        self.period = 1.0 / self.rate # sample period
        self.resolution = 256  # samples per period
        self.tick = 0.0        # local time measure (once per sample)
        self.dispatcher = None # timer to trigger value changes
        self.initSamples(wav)

    def initSamples(self, wav):
        self.samples = []
        if wav in ['sin', 'wah']:
            step = 2*pi / self.resolution
            def makeSample(x):
                return int(interp(sin(x*step), [-1,1], [0,127]))
            self.samples = map(makeSample, range(0, self.resolution))
            if wav == 'wah':
                self.amplitude = 0.0
        elif wav == 'tri':
            xkeys = [0, 0.25*self.resolution, 0.75*self.resolution, self.resolution]
            ykeys = [64, 127, 0, 64]
            def makeSample(x):
                return int(interp(x, xkeys, ykeys))
            self.samples = map(makeSample, range(0, self.resolution))
        elif wav == 'saw':
            def makeSample(x):
                return (64 + int(interp(x, [0, self.resolution], [0, 127]))) % 128
            self.samples = map(makeSample, range(0, self.resolution))
        elif wav == 'sqr':
            def makeSample(x):
                if x < 0.5*self.resolution:
                    return 127
                else:
                    return 0
            self.samples = map(makeSample, range(0, self.resolution))
        else:
            self.samples = [0]*self.resolution

    def stop(self):
        if self.dispatcher:
            self.dispatcher.cancel()
            self.dispatcher = None

    def sample(self):
        # increase time wrt last sample time
        self.tick = (self.tick + self.period * self.resolution * self.freq) % self.resolution
        newValue = 64 + int(self.amplitude * (self.samples[int(self.tick)] - 64))
        if self.value <> newValue:
            self.value = newValue
            alsaseq.output(ccEvent(self.cc, self.value, chan=self.params.midiChan))
        self.dispatcher = Timer(self.period, self.sample)
        self.dispatcher.start()

    def start(self):
        self.sample()

    def setFrequency(self, f):
        self.freq = f

    def setAmplitude(self, a):
        self.amplitude = a

class State:
    pot       = 0               # poti position
    cc        = 64              # mapped cc position
    lfos      = []              # low frequency oscillators
    trigger   = False           # trigger is on
    bendOffs  = 0.0             # offset for pitch bend
    bend      = 8192            # pitch bend value
    bpm       = 120             # rapid fire speed (free-wheeling)
    tickMod   = 12              # rapid fire speed (quantised)
    ticks     = 0               # MIDI ticks since transport start
    running   = False           # MIDI transport status    
    
class Scheduler (threading.Thread):
    def __init__(self, params):
        threading.Thread.__init__(self)
        self.params = params
        self.params = params
        self.dispatcher = None
        self.lastStrike = None
        self.lastNote   = None
        self.state = State()
        self.arpeg = arpeg.Arpeggiator(params.pattern)
        for lfo in params.lfos:
            cc, wav = lfo
            self.state.lfos.append(LFO(cc, wav, params))

    def printStatus(self):
        def bool2str(b):
            if b:
                return '*'
            else:
                return ' '
        sys.stdout.write("[POT:%4i] [TRG: %s]\r" 
                         % (self.state.pot, self.state.trigger))
        sys.stdout.flush()

    def pitch(self):
        if self.params.arp:
            if self.params.setNote:
                shift = int(interp(self.state.pot, [0,1023], [-8,8]))
            else:
                shift = 0
            note = self.arpeg.getNote(shift)
            return note
        else:
            if self.params.scale is None:
                noteRange = 12 * self.params.octaves
            else:
                noteRange = 7 * self.params.octaves
            if self.params.setNote:
                if self.params.rang:
                    return int(interp(self.state.pot, [0, 1023], [self.params.rang[0], self.params.rang[1]]))
                else:
                    noteIndex = int(interp(self.state.pot, [0,1023], [-noteRange,noteRange]))
                    return noteOnScale(self.params.scale, noteIndex)
            else:
                return self.params.note

    def stopNote(self):        
        if self.lastNote is None:
            return
        else:
            alsaseq.output(noteOffEvent(self.lastNote, chan=self.params.midiChan))
            self.lastNote = None
            for cc in self.params.triggerCCs:
                alsaseq.output(ccEvent(cc, 0, chan=self.params.midiChan))
            logging.debug("stop note %s" % str(self.lastNote))

    def playNote(self):
        if self.lastNote:
            self.arpeg.next()
        if not self.params.legato: 
            self.stopNote()
        note = Note(self.pitch())
        if note.valid():
            alsaseq.output(noteOnEvent(note, chan=self.params.midiChan))
            for cc in self.params.triggerCCs:
                alsaseq.output(ccEvent(cc, 127, chan=self.params.midiChan))
            logging.debug("play note %s" % str(note))
            if (self.params.legato):
                self.stopNote()
            self.lastNote = note
        self.lastStrike = time.time()
        if not self.params.quant and self.params.arp: 
            duration = 60.0 / self.bpm()
            self.dispatcher = self.scheduleNote(duration)

    def scheduleNote(self, duration):
        timer = Timer(duration, self.playNote)
        timer.start()
        logging.debug("dispatch note in %f s" % duration)
        return timer

    def bpm(self):
        if not self.params.setSpeed:
            return 120
        else:
            return int(interp(self.state.pot, [0,512,1023], [30,120,480]))

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
        mods = [48, 36, 32, 24, 18, 16, 12, 8, 6, 4, 3, 2]
        mod = 12
        if self.params.setSpeed:
            p = self.state.pot
            i = int(interp(p, [0,512,1023], [0,6,11]))
            mod = mods[i]
        self.state.tickMod = mod

    def bend(self):
        if not self.params.setBend:
            return 8192
        else:
            centered = self.state.pot - self.state.bendOffs
            return int(interp(centered, [-1023,1023], [0, 16383]))

    def setBend(self):
        newBend = self.bend()
        if self.state.bend != newBend:
            self.state.bend = newBend
            alsaseq.output(pitchBendEvent(newBend, chan=self.params.midiChan))

    def resetBend(self):
        if self.params.setBend:
            self.state.bendOffs = self.state.pot
            self.state.bend = 8192
            alsaseq.output(pitchBendEvent(self.state.bend, chan=self.params.midiChan))

    def setControllers(self):
        newCC = int(interp(self.state.pot, [0,1023], [0,127]))
        if newCC <> self.state.cc:
            self.state.cc = newCC
            for cc in self.params.controllers:
                alsaseq.output(ccEvent(cc, newCC, chan=self.params.midiChan))

    def setFreq(self):
        freq = interp(self.state.pot, [0,1023], [0.1, 8])
        for lfo in self.state.lfos:
            lfo.setFrequency(freq)
            if lfo.wav == 'wah':
                amp = interp(self.state.pot, [0,1023], [0.0, 1.0])
                lfo.setAmplitude(amp)

    # Gamma correction
    def curve(self, pot):
        if not self.params.gamma:
            return pot
        else:
            return int((pot/1023.0)**self.params.gamma * 1023)

    def setPoti(self, x):
        self.state.pot = self.curve(x)
        self.printStatus()
        self.setBend()
        self.setFreq()
        if self.params.arp:
            if self.params.quant:
                self.setQuantisation()
            else:
                self.setBPM()
        if self.state.trigger:
            self.setControllers()
            if self.params.gliss:
                newPitch = self.pitch()
                if self.lastNote is not None:
                    if newPitch != self.lastNote.pitch:
                        self.resetBend()
                        self.playNote()                    

    def run(self):
        print "starting scheduler"
        for lfo in self.state.lfos:
            lfo.start()
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
                elif cmd == command.SET_POT:
                    logging.debug("received SET_POS")
                    x = params
                    self.setPoti(x)
                elif cmd == command.PSH_NOTE:
                    self.arpeg.pushNote(params)
                    logging.debug("arpeggiator push note %i" % params)
                elif cmd == command.POP_NOTE:
                    self.arpeg.popNote(params)
                    logging.debug("arpeggiator pop note %i" % params)
                elif cmd == command.TRP_START:
                    self.state.running = True
                    self.state.ticks = 0
                    if self.params.arp and self.params.quant and self.state.trigger:
                        self.arpeg.reset()
                        self.playNote()
                    logging.debug("transport start")
                elif cmd == command.TRP_STOP:
                    self.state.running = False
                    logging.debug("transport stop")
                elif cmd == command.TRP_TICK:
                    self.state.ticks = self.state.ticks + 1
                    if self.state.trigger and self.params.arp and self.params.quant and (self.state.ticks % self.state.tickMod == 0):
                        self.playNote()
                else:
                    logging.warning("Illegal command in queue")
        print "stopping scheduler"
        for lfo in self.state.lfos:
            lfo.stop()

