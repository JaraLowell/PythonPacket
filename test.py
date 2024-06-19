import os
import time
from datetime import date, datetime
import sys
import gc
import re
import random

MHeard = []
MyCall = 'NL0MSK'
SendLengt = 251

def readfile(file):
    filetoread = os.getcwd() + os.path.sep + 'txtfiles' + os.path.sep + file
    contents = ''
    if os.path.isfile(filetoread):
        with open(filetoread, 'r') as f:
            contents = f.read()
        if contents != '':
            return contents
    return 'File `' + file + '` not found or empty.'

def textchunk(cnktext , chn, callsign):
    tmp = ''
    # Lets do some preg replacing to...
    sindex = cnktext.find('%')
    if sindex != -1:
        cnktext = cnktext.replace('%V', 'PyPacketRadio v1.1')                               # GP version number, in this case it is 1.61
        cnktext = cnktext.replace('%C', callsign)                                           # %c = The Call of the opposite Station
        if callsign in MHeard:
            if MHeard[callsign][0] != '':
                cnktext = cnktext.replace('%N', MHeard[callsign][0] + ' ()' + callsign + ')')   # The Name of the opposite Station
            else:
                cnktext = cnktext.replace('%N', callsign)
                tmp = 'Please register your name via //Name yourname'
        else:
            cnktext = cnktext.replace('%N', callsign)
        cnktext = cnktext.replace('%?', tmp)                                                # prompts the connected station to report its name if it has not yet included in the list of names (NAMES.GP)
        cnktext = cnktext.replace('%Y', MyCall)                                             # %y = One's own Call
        cnktext = cnktext.replace('%K', str(chn))                                           # %k = channel number on which the text will be broadcast
        cnktext = cnktext.replace('%T', time.strftime('%H:%M:%S'))                          # %t = T: current GP time in HH:MM:SS format, e.g. 10:41:32
        cnktext = cnktext.replace('%D', time.strftime("%d/%m/%Y"))                          # %d = current date eg: 25.03.1991
        # cnktext = cnktext.replace('%B', )                                                 # %b = Corresponds to the Bell Character (07h) we dont have this ?!
        tmp = ''
        if os.path.exists('txtfiles/news.txt'): tmp = 'There is news via //News'
        cnktext = cnktext.replace('%I', tmp)                                                # %i = is there new news? News
        cnktext = cnktext.replace('%Z', 'UTC' + datetime.now().astimezone().strftime("%z")) # %z = The Time Zone of the server
        cnktext = cnktext.replace('%_', '\r')                                               # %_: ends the line and moves the cursor to a new line
        cnktext = cnktext.replace('%>', 'to ' + MyCall + ' >')       # bit like a command prompt place holder at bottom of msg
        sindex = cnktext.find('%O')
        if sindex:
            lines = readfile('origin.txt').splitlines()
            myline = random.choice(lines)
            cnktext = cnktext.replace('%O', myline)                                         # %o = Reads a Line from ORIGIN.GPI (Chosen at Random)
        # cnktext = cnktext.replace('%%', '%')                                              # percent sign

    cnktext = re.sub(r'(\r\n|\n|\r)', '\n', cnktext)                                        # lets make sure we only use \n as enter
    cnktext = cnktext[:-1]


    # Next part we need is tring to parts if string longer then 7f (127) bytes (characters)
    while len(cnktext) > SendLengt:
        tmp = cnktext[0:SendLengt]
        cnktext = cnktext[SendLengt:]
        print('*' * 80)
        print(tmp) # sendqueue.append([chn,cnktext])
    #do we have left over?
    if len(cnktext) != 0:
        print('*' * 80)
        print(cnktext) # sendqueue.append([chn,cnktext])


textchunk(readfile('ctext.txt'),'1','NL1MSK')
print ('*' * 80)