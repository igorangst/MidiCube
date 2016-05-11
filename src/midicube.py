#!/usr/bin/python

import time
import sys
import signal
import alsaseq
import logging
import getopt
import re

from listener import Listener
from scheduler import Scheduler
from alsain import alsaInput
from params import *

import sync
import com
import command
import util


# logging.basicConfig(filename='debug.log',level=logging.DEBUG)

def terminate():
    print 'Interrupted'
    try:
        com.stopCube(sock)
    except:
        logging.error('could not shut down MIDI cube properly, connection failed');
    sync.qLock.acquire()
    sync.queue.put( (command.TRG_OFF, None) )
    sync.qLock.release()
    sync.terminate.set()     
    sync.queueEvent.set()
    scheduler.join()
    listener.join()
    sys.exit(0)

def usage():
    print """gyro.py [options]
Global options:
-m --mac              bluetooth device address of MIDI cube
   --midiout <id:p>   connect to midi client id on input port p
-c --chan <i>         MIDI output channel (default: 1)

Behavior control:
-b <beh> --behavior add behavior to poti, where <beh> can be any of the following: 
    
note       select pitch of played note
bend       pitch bend control
cc<i>      MIDI controller #i 
lfo<i>     Low frequency oscillator on MIDI controller #i
vel        velocity of played note
speed      set speed for arpeggiator
    
Further options that control the behavior:
-s --scale 'D#' restricts played notes to the D# major scale
-n --note C2    fixed note (overwritten by note behavior), can be either a
                MIDI note number (like 36) or a string like 'F#3' 
-g --gliss      plays a new note once the poti moves by a sufficient angle
-a --arp        arpeggio on incoming notes
-p --pattern    arpeggiator pattern, can be 'up', 'down', 'random' or
                a pattern of note positions separated by colons, like
                for example 1:3:5:2:4
-q --quant      use MIDI clock input for quantization (this 
                only affects arpeggio mode)
-o --oct <k>    number of octaves spanned by the poti
"""

def parseArgs(argv):
    p = Params()
    def addBehavior(beh):
        if beh == 'note':
            p.setNote = True
        elif beh == 'bend':
            p.setBend = True
        elif beh == 'speed':
            p.setSpeed = True 
        elif beh == 'vel':
            p.setVelocity = True
        else:
            m = re.match('^cc(\d+)$', beh)
            if m:
                cc = int(m.group(1))
                p.controllers.append(cc)
                return
            m = re.match('^lfo(\d+)$', beh)
            if m:
                cc = int(m.group(1))
                p.lfos.append(cc)
                return
            usage()
            exit(2)
    def setNote(s):
        m = re.match('^(\d+)$', s)
        if m:
            p.note = int(s)
            return
        m =re.match('^([a-hA-H]#?)(\d)$',s)
        if m:
            n = m.group(1)
            o = int(m.group(2))
            p.note = util.getNote(n,o)
            return
        usage()
        exit(2)
    shortOpts = "b:s:gqao:n:m:c:p:"
    longOpts = ["behavior=","scale=", "chan=", "quant", "note=", 
                "gliss","arp","oct=","mac=","midiout=","midiin=", "pattern="]
    try:
        opts, args = getopt.getopt(argv, shortOpts, longOpts)
    except getopt.GetoptError:
        usage()
        exit(2)
    for opt,arg in opts:
        if opt in ["-g", "--gliss"]:
            p.gliss = True
        elif opt in ["-a", "--arp"]:
            p.arp = True
        elif opt in ["-p", "--pattern"]:
            p.pattern = arg
        elif opt in ["-q", "--quant"]:
            p.quant = True
        elif opt in ["-o", "--oct"]:
            p.octaves = int(arg)
        elif opt in ["-s", "--scale"]:
            p.scale = str(arg)
        elif opt in ["-n", "--note"]:
            setNote(arg)
        elif opt in ["-b", "--behavior"]:
            addBehavior(arg)        
        elif opt in ["-m", "--mac"]:
            p.btMAC = arg
        elif opt in ["-c", "--chan"]:
            p.midiChan = int(arg)
        elif opt == "--midiout":
            m = re.match('(\d+):(\d+)', arg)
            if m:
                p.alsaOut = (int(m.group(1)), int(m.group(2)))
            else:
                usage()
                exit(2)
        elif opt == "--midiin":
            m = re.match('(\d+):(\d+)', arg)
            if m:
                p.alsaIn = (int(m.group(1)), int(m.group(2)))
            else:
                usage()
                exit(2)
        else:
            usage()
            exit(2)
    return p

# ============================================================================

args = sys.argv[1:]
args.append("-m")
# args.append('20:14:12:17:01:67')
args.append('20:14:12:17:02:47')
params = parseArgs(args)

# initialize ALSA 
alsaseq.client( 'MidiCube', 1, 1, False )
if params.alsaOut is not None:
    (client, port) = params.alsaOut
    alsaseq.connectto(0, client, port)
if params.alsaIn is not None:
    (client, port) = params.alsaIn
    alsaseq.connectfrom(0, client, port)

# connect to bluetooth device
sock = com.connect(params.btMAC)
if not sock:
    logging.error('connection to MIDI cube failed')
    exit(-1)

listener = Listener(sock, params.btMAC)
scheduler = Scheduler(params)
alsain = alsaInput()

scheduler.start()
listener.start()
time.sleep(1)

com.stopCube(sock)
if not com.startCube(sock):
    terminate()

try:
    while True:
        time.sleep(1)
        if sync.disconnect.isSet():
            print "disconnected :-("
            sock.close()
            terminate()
            # while True:
            #     print "trying to reconnect..."
            #     sock = com.connect(params.btMAC)
            #     if sock:
            #         listener = Listener(sock, params.btMAC)
            #         listener.start()
            #         sync.disconnect.clear()
            #         print "reconnected :-)"
            #         break

except:
    terminate()



