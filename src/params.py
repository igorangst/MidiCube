X_AXIS  = 0
Y_AXIS  = 1
Z_AXIS  = 2
NO_AXIS = -1

OSM_MODE = 0
RFI_MODE = 1

CTRL_FREE   = 0
CTRL_CENTER = 1
CTRL_DRAG   = 2

class Params:
    # global options
    scale = None       # restrict notes to scale (in both modes)
    gliss = False      # glissando (only one-shot mode)
    quant = False      # quantise wrt MIDI clock (only rapid-fire mode)
    arpRFI = False     # arpeggio in rapid-fire mode
    arpOSM = False     # arpeggio in one-shot mode    
    pattern = 'up'     # arpeggiator pattern
    octaves = 1        # number of octaves spanned by a 90 degree movement
    
    # bluetooth and alsa com options
    btMAC = None
    btName = "LaserGun"
    alsaOut = None
    alsaIn = None
    midiChan = 1

    # exclusive behavior associated to at most one of the three axes, for
    # one-shot mode and for rapid-fire mode
    setNote     = [X_AXIS, Y_AXIS]
    setBend     = [NO_AXIS, NO_AXIS]
    setVelocity = [NO_AXIS, NO_AXIS]
    setSpeed    = X_AXIS

    # controllers associated to the axes, for one-shot and rapid-fire
    # mode each controller is associated with a controller reset mode,
    # which can be any of CTRL_FREE, CTRL_CENTER or CTRL_DRAG.
    # TODO: use negative controller ids for reverse sense
    controllersOSM     = [[], [], []]
    controllersRFI     = [[], [], []]

