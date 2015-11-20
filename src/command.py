TRG_ON   = 1
TRG_OFF  = 2
RFI_ON   = 3
RFI_OFF  = 4
SET_POS  = 5

def cmd2str(cmd):
    return {
        TRG_ON : 'TRG_ON',
        TRG_OFF: 'TRG_OFF',
        RFI_ON : 'RFI_ON',
        RFI_OFF: 'RFI_OFF',
        SET_POS: 'SET_POS'
    }.get(cmd, 'UNKNOWN COMMAND')
