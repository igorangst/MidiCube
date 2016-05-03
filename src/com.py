import bluetooth
import logging

from util import *

import sync

# target_name = "LaserGun"
# target_address = '20:14:12:17:01:67'

def connect(address = None, name = "LaserGun"):
    if address is None:
        logging.info("scanning for nearby devices...")
        try:
            nearby_devices = bluetooth.discover_devices()
        except bluetooth.btcommon.BluetoothError:
            logging.error("error accessing bluetooth device")
            return None
        for bdaddr in nearby_devices:
            if name == bluetooth.lookup_name( bdaddr ):
                address = bdaddr
                break
        if address is not None:
            logging.info("found laser gun with address %i" % address)
        else:
            print "could not find laser gun nearby"
            return None
    
    logging.info("connecting to device...")
    port = 1    
    sock = bluetooth.BluetoothSocket( bluetooth.RFCOMM )
    
    with timeout(seconds = 10):
        try:
            sock.connect((address, port))
        except TimeoutError:
            sock.close()
            logging.error("connection timed out :-(")
            return None
        except bluetooth.btcommon.BluetoothError as e:
            logging.error(str(e))
            return None            
    logging.info("connection to laser gun established")

    sock.setblocking(0)
    return sock


def handShake(sock, msg, okEvent, errorMsg="response timed out", succMsg=None):
    sock.send(msg)
    time.sleep(0.01)
    if okEvent.wait(1):
        okEvent.clear()
        if succMsg is not None:
            logging.info(succMsg)
        return True
    else:
        logging.error(errorMsg)
        return False

def resetGun(sock):
    return handShake(sock, "RST\n", sync.resetOK, succMsg="[*] Reset OK")

def calibrateGun(sock):
    return handShake(sock, "CAL\n", sync.calibrateOK, succMsg="[*] Calibrate OK")

def startGun(sock):
    return handShake(sock, "RUN\n", sync.runOK, succMsg="[*] Start OK")

def stopGun(sock):
    return handShake(sock, "STP\n", sync.stopOK, succMsg="[*] Stop OK")

def requestStatus(sock):
    sock.send("GET\n")
    return True
