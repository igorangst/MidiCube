import bluetooth
import signal
import time
import re
import threading
import select
import logging

from threading import Timer

import sync
import command
import com

from util import *

class Listener (threading.Thread):
    def __init__(self, sock, address):
        threading.Thread.__init__(self)
        self.sock  = sock
        self.address = address
        self.ready = select.select([sock], [], [], 1)
        self.pendingMsg = ''
        self.watchdog = None
        self.alive = True

    def readSock(self):
        resp = self.pendingMsg
        while self.alive and not sync.terminate.isSet():
            pos = resp.find('\n')
            if pos > 0:
                if pos == len(resp) - 1:
                    self.pendingMsg = ''
                    return resp.strip()
                else:
                    prefix = resp[0:pos]
                    self.pendingMsg = resp[pos+1:]
                    return prefix.strip()
            try:
                data = self.sock.recv(1024)
            except:
                time.sleep(0.001)
                continue
            resp += data
        return None

    def die(self):
        self.alive = False
        cmd = (command.TRG_OFF, None)
        sync.putCommand(cmd)
        sync.disconnect.set()
        print "I'm dead :-("

    def live(self):
        if self.watchdog:
            self.watchdog.cancel()
        self.watchdog = Timer(0.5, self.die)
        self.watchdog.start()

    # def resurrect(self):
    #     while not sync.terminate.isSet():
    #         self.sock = com.connect(self.address)
    #         if self.sock:
    #             self.ready = select.select([sock], [], [], 1)
    #             com.startCube(self.sock)
    #             com.requestStatus(self.sock)
    #             print "I'm alive :-)"
    #             return 

    def dummyRead(self):
        time.sleep(0.5)
        return 'RUN OK'

    # def putCommand(self, cmd):
    #     sync.qLock.acquire()
    #     sync.queue.put(cmd)
    #     logging.debug("send command %s" % command.cmd2str(cmd))
    #     sync.qLock.release()
    #     sync.queueEvent.set()

    def run(self):
        print "starting bluetooth listener"
        while self.alive and not sync.terminate.isSet():
            msg = self.readSock()
            if msg is None:
                continue
            logging.debug("bluetooth message: %s" % msg)
            if msg == 'ALIVE':
                self.live()
                continue
            if msg == 'RUN OK':
                sync.runOK.set()
                continue
            if msg == 'STP OK':
                sync.stopOK.set()
                continue
            if msg == 'RST OK':
                sync.resetOK.set()
                continue
            if msg == 'TRG ON':
                cmd = (command.TRG_ON, None)
                sync.putCommand(cmd)
                continue
            if msg == 'TRG OFF':
                cmd = (command.TRG_OFF, None)
                sync.putCommand(cmd)
                continue            
            m = re.search('POT (\d+)', msg)
            if m:
                pot = int(m.group(1)); 
                cmd = (command.SET_POT, pot)
                sync.putCommand(cmd)
                continue
            logging.warning("illegal message  '%s'" % msg)
        print "stopping bluetooth listener"

