import os
import time
from datetime import date, datetime
import sys
import asyncio
import gc
import re
import math

# psutil and websockets needs pip install (and maybe codecs as well?)
import psutil
import websockets
import codecs
import functools
import json
from http import HTTPStatus
import random

# Next two are for the radio side of things
import serial
import configparser

import pickle 

MHeard = []
MyCall = 'NL0MSK'
SendLengt = 251

MHeardPath = 'MHeard.pkl'

if os.path.exists(MHeardPath):
    with open(MHeardPath, 'rb') as f:
        MHeard = pickle.load(f)

def send_mh():
    send_me = ''
    tn = int(time.time())
    listme = []
    for k in MHeard:
        v = MHeard[k]
        send_me = ''
        if (tn - v[3]) < 43200:
            send_me += f' {k} ' + ' ' * (8 - len(k)) + v[0] + ' ' * (10 - len(v[0])) + v[1] + ' ' * (14 - len(v[1])) + ez_date(v[3]) + ' ago\n'
            listme.append({'txt': send_me, 'time':v[3]})
    listme = sorted(listme, key=lambda d: d['time'], reverse=True)
    send_me = 'NL0MSK Heard-list\r Station  Sysop     Locator       Last\n' + '-' * 55 + '\n'
    for k in listme:
        send_me += k['txt']
    send_me += '\nGenerated on ' + time.strftime("%d/%m/%Y") +' at ' + time.strftime('%H:%M:%S') + ' Local time\n'
    return send_me

def ez_date(d):
    ts = math.floor(int(time.time()) - d)
    if ts > 31536000:
        temp = int(round(ts / 31536000, 0))
        val = f"{temp} year{'s' if temp > 1 else ''}"
    elif ts > 2419200:
        temp = int(round(ts / 2419200, 0))
        val = f"{temp} month{'s' if temp > 1 else ''}"
    elif ts > 604800:
        temp = int(round(ts / 604800, 0))
        val = f"{temp} week{'s' if temp > 1 else ''}"
    elif ts > 86400:
        temp = int(round(ts / 86400, 0))
        val = f"{temp} day{'s' if temp > 1 else ''}"
    elif ts > 3600:
        temp = int(round(ts / 3600, 0))
        val = f"{temp} hour{'s' if temp > 1 else ''}"
    elif ts > 60:
        temp = int(round(ts / 60, 0))
        val = f"{temp} minute{'s' if temp > 1 else ''}"
    else:
        temp = int(ts)
        val = "a few second's"
    return val


wssend = bytearray()
tmp = send_mh()
wssend.extend(map(ord, tmp))


wssend = wssend.decode('ascii', 'xmlcharrefreplace')

print(wssend)

