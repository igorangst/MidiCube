class Params:
    # global options
    scale = None       # restrict notes to scale 
    gliss = False      # glissando 
    quant = False      # quantise wrt MIDI clock (only arpeggio mode)
    arp   = False      # arpeggio mode
    pattern = 'up'     # arpeggiator pattern
    octaves = 1        # number of octaves spanned by a 90 degree movement
    note = 36          # fixed note
    
    # bluetooth and alsa com options
    btMAC = None
    btName = "MidiCube"
    alsaOut = None
    alsaIn = None
    midiChan = 1

    # behavior that can be enabled for the poti
    # one-shot mode and for rapid-fire mode
    setNote     = False
    setBend     = False
    setVelocity = False
    setSpeed    = False

    # controllers and LFOs associated to poti
    controllers = []
    lfos = []
