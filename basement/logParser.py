import json
import time

MHeard = {}
Mon = {}
Chan = {}

class logParser:
    def __init__(self) -> None:
        pass
    
    def loadJson(file, type):
        if type == 'MH':
            MHeard = json.load(open(file))
            return MHeard
        elif type == 'MON':
            Mon = json.load(open(file))
            return Mon
        elif type == 'CHAN':
            Chan = json.load(open(file))
            return Chan
        
    def saveJson(file, data, type):
        if type == 'MH':
            with open(file, 'w') as MHeardf:
                json.dump(data, MHeardf)
        elif type == 'MON':
            with open(file, 'w') as Monf:
                json.dump(data, Monf)
        elif type == 'CHAN':
            with open(file, 'w') as Chanf:
                json.dump(data, Chanf)
                
    def updateJson(data, type):
        pass
                
    def logMheard(callsign, status, locator):
        timenow =  int(time.time())
        
        