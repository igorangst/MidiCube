import alsaseq
import threading
import sync
import time
import logging

from command import *

class alsaInput (threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        print "starting alsa listener"
        while not sync.terminate.isSet():
            if alsaseq.inputpending():
                event = alsaseq.input()
                evtype = event[0]
                pitch = event[7][1]
                if evtype == alsaseq.SND_SEQ_EVENT_NOTEON:   
                    cmd = (PSH_NOTE, pitch)
                elif evtype == alsaseq.SND_SEQ_EVENT_NOTEOFF:
                    cmd = (POP_NOTE, pitch)
                elif evtype == alsaseq.SND_SEQ_EVENT_START:
                    cmd = (TRP_START, None)
                elif evtype == alsaseq.SND_SEQ_EVENT_STOP:
                    cmd = (TRP_STOP, None)
                elif evtype == alsaseq.SND_SEQ_EVENT_CLOCK:
                    cmd = (TRP_TICK, None)
                else:
                    continue
                sync.putCommand(cmd)
            else:
                time.sleep(0.005)
                continue
        print "stopping alsa listener"
