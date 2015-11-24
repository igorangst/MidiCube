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
                pitch = event[7][1]
                if event[0] == 6:   # note on event
                    cmd = (PSH_NOTE, pitch)
                elif event[0] == 7: # note off event
                    cmd = (POP_NOTE, pitch)
                else:
                    continue
                sync.qLock.acquire()
                sync.queue.put(cmd)
                logging.debug("send command %s" % cmd2str(cmd))
                sync.qLock.release()                
                sync.queueEvent.set()
            else:
                time.sleep(0.005)
                continue
        print "stopping alsa listener"
