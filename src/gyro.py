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


# logging.basicConfig(filename='debug.log',level=logging.DEBUG)

def terminate():
    print 'Interrupted'
    try:
        com.stopGun(sock)
    except:
        logging.error('could not shut down laser gun properly, connection failed');
    sync.qLock.acquire()
    sync.queue.put( (command.TRG_OFF, None) )
    sync.qLock.release()
    sync.terminate.set()     
    sync.queueEvent.set()
    scheduler.join()
    listener.join()
    alsain.join()
    sys.exit(0)

def usage():
    print """gyro.py [options]
Global options:
-m --mac              bluetooth device address of laser gun
   --midiout <id:p>   connect to midi client id on input port p
   --midiin  <id:p>   connect to midi client id on output port p 
-c --chan <i>         MIDI output channel (default: 1)

Options for mapping the axes to behavior:
-x -y -z   adds behavior in one-shot mode
-X -Y -Z   adds behavior in rapid-fire mode
    
These can be combined with any of the following values:
note    select pitch of played note
bend    pitch bend control
cc<i>   MIDI controller #i 
vel     velocity of played note
speed   set speed for rapid fire 
    
Further options that control the behavior:
-s --scale 'D#' restricts played notes to the D# major scale
-g --gliss      in one-shot mode, plays a new note once the  
                associated axis moves by a sufficient angle
-a --arp        arpeggio in one-shot mode
-A --Arp        arpeggio in rapid-fire mode
-q --quant      use MIDI clock input for quantization (this 
                only affects rapid fire mode)
-o --oct <k>    number of octaves spanned by 90 degrees 
"""

def parseArgs(argv):
    p = Params()
    def setNote(mode, axis):
        p.setNote[mode] = axis
    def setBend(mode, axis):
        p.setBend[mode] = axis
    def setVelocity(mode, axis):
        p.setVelocity[mode] = axis
    def setSpeed(axis):
        p.setSpeed = axis
    def setBehavior(mode, axis, beh):
        if beh == 'note':
            setNote(mode, axis)
        elif beh == 'bend':
            setBend(mode, axis)
        elif beh == 'speed':
            # FIXME: speed makes only sense in RFI mode
            setSpeed(axis)
        elif beh == 'vel':
            setVelocity(mode, axis)
        else:
            m = re.match('cc(\d+)', beh)
            if m:
                cc = int(m.group(1))
                if mode == 0:
                    p.controllersOSM[axis].append(cc)
                else:
                    p.controllersRFI[axis].append(cc)
            else:
                usage()
                exit(2)
    shortOpts = "x:y:z:X:Y:Z:s:gqaAo:m:c:"
    longOpts = ["x=","y=","z=","X=","Y=","Z=","scale=", "chan=", "quant",
                "gliss","arp","Arp","oct=","mac=","midiout=","midiin="]
    try:
        opts, args = getopt.getopt(argv, shortOpts, longOpts)
    except getopt.GetoptError:
        usage()
        exit(2)
    for opt,arg in opts:
        if opt in ["-g", "--gliss"]:
            p.gliss = True
        elif opt in ["-a", "--arp"]:
            p.arpOSM = True
        elif opt in ["-A", "--Arp"]:
            p.arpRFI = True
        elif opt in ["-q", "--quant"]:
            p.quant = True
        elif opt in ["-o", "--oct"]:
            p.octaves = int(arg)
        elif opt in ["-s", "--scale"]:
            p.scale = str(arg)
        elif opt in ["-x", "--x"]:
            setBehavior(OSM_MODE, X_AXIS, arg)
        elif opt in ["-X", "--X"]:
            setBehavior(RFI_MODE, X_AXIS, arg)
        elif opt in ["-y", "-y"]:
            setBehavior(OSM_MODE, Y_AXIS, arg)
        elif opt in ["-Y", "--Y"]:
            setBehavior(RFI_MODE, Y_AXIS, arg)
        elif opt in ["-z", "--z"]:
            setBehavior(OSM_MODE, Z_AXIS, arg)
        elif opt in ["-Z", "--Z"]:
            setBehavior(RFI_MODE, Z_AXIS, arg)        
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
args.append('20:14:12:17:01:67')
params = parseArgs(args)

# initialize ALSA 
alsaseq.client( 'LaserGun', 1, 1, False )
if params.alsaOut is not None:
    (client, port) = params.alsaOut
    alsaseq.connectto(0, client, port)
if params.alsaIn is not None:
    (client, port) = params.alsaIn
    alsaseq.connectfrom(0, client, port)

# connect to bluetooth device
sock = com.connect(params.btMAC)
if not sock:
    logging.error('connection to laser gun failed')
    exit(-1)

listener = Listener(sock)
scheduler = Scheduler(params)
alsain = alsaInput()

scheduler.start()
listener.start()
alsain.start()
time.sleep(1)

com.stopGun(sock)
if not com.resetGun(sock):
    terminate()
if not com.calibrateGun(sock):
    terminate()
if not com.startGun(sock):
    terminate()

try:
    while True:
        time.sleep(1)
except:
    terminate()



