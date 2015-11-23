X_AXIS  = 0
Y_AXIS  = 1
Z_AXIS  = 2
NO_AXIS = -1

OSM_MODE = 0
RFI_MODE = 1

class Params:
    # global options
    scale = None       # restrict notes to scale (in both modes)
    gliss = False      # glissando (only in one-shot mode)
    arpRFI = False     # arpeggio in rapid-fire mode
    arpOSM = False     # arpeggio in one-shot mode
    octaves = 1        # number of octaves spanned by a 90 degree movement
    
    # bluetooth and alsa com options
    btMAC = None
    btName = "LaserGun"
    alsaOut = None

    # exclusive behavior associated to at most one of the three axes, for
    # one-shot mode and for rapid-fire mode
    setNote     = [X_AXIS, NO_AXIS]
    setBend     = [X_AXIS, NO_AXIS]
    setVelocity = [NO_AXIS, NO_AXIS]
    setSpeed    = X_AXIS

    # controllers associated to the axes, for one-shot and rapid-fire mode
    # TODO: use negative controller ids for reverse sense
    controllersOSM = [[],[2],[3]]
    controllersRFI = [[],[2],[3]]
