import bluetooth

from util import *

import sync

# target_name = "LaserGun"
# target_address = '20:14:12:17:01:67'

def connect(address = None, name = "LaserGun"):
    if address is None:
        print "scanning for nearby devices..."
        try:
            nearby_devices = bluetooth.discover_devices()
        except bluetooth.btcommon.BluetoothError:
            print "error accessing bluetooth device"
            return None
        for bdaddr in nearby_devices:
            if name == bluetooth.lookup_name( bdaddr ):
                address = bdaddr
                break
        if address is not None:
            print "found laser gun with address ", address
        else:
            print "could not find laser gun nearby"
            return None
    
    print "connecting to device..."
    sock = bluetooth.BluetoothSocket( bluetooth.RFCOMM )
    port = 1
    
    with timeout(seconds = 5):
        try:
            sock.connect((address, port))
        except TimeoutError:
            sock.close()
            print "connection timed out :-("
            return None
    print "connection to laser gun established"

    sock.setblocking(0)
    return sock


def handShake(sock, msg, okEvent, errorMsg="response timed out", succMsg=None):
    sock.send(msg)
    time.sleep(0.01)
    if okEvent.wait(1):
        okEvent.clear()
        if succMsg is not None:
            print succMsg
        return True
    else:
        print errorMsg
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
