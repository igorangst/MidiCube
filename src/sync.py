import threading
import Queue

#class Sync:
 
resetOK     = threading.Event()
stopOK      = threading.Event()
runOK       = threading.Event()
calibrateOK = threading.Event()
terminate   = threading.Event()
queueEvent  = threading.Event()

qLock       = threading.Lock()
queue       = Queue.Queue(100)
