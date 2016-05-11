TRG_ON    = 1  # trigger has been pressed
TRG_OFF   = 2  # trigger has been released
SET_POT   = 5  # update gyroscope positions

def cmd2str(cmd):
    return {
        TRG_ON  : 'TRG_ON',
        TRG_OFF : 'TRG_OFF',
        SET_POT : 'SET_POS',
    }.get(cmd, 'UNKNOWN COMMAND')
