#!/usr/bin/env python3
from __future__ import print_function
try:
    import __builtin__ as builtins # type: ignore # Python 2
except ImportError:
    import builtins # Python 3

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

def num2byte(number):
    return bytearray.fromhex("{0:#0{1}x}".format(number,4)[2:])

config = configparser.ConfigParser()
config.read('./config.ini')

#------------------------------------------------------------- Log Files Loads ---------------------------------------------------------------------------

Chan_Hist = {}
Moni_Hist = {}
MHeard    = {}
LoraDB    = {}

MHeardPath = 'MHeard.pkl'
LoraDBPath = 'LoraDB.pkl'
MoniLogPath = 'MoniLog.pk1'
ChanLogPath = 'ChanLog.pk1'

MyCall = config.get('radio', 'mycall')
SendLengt = 127
MyPath = os.getcwd() + os.path.sep + 'txtfiles' + os.path.sep

monitorbuffer = []
channelbuffers = []

today_date = date.today()
time_now = datetime.now()

channels = config.get('tncinit', '3')
callsign = ""
polling = 1
channel_to_read_byte = b'x00'

pdelay = 0.0016

if os.path.exists(LoraDBPath):
    with open(LoraDBPath, 'rb') as f:
        LoraDB = pickle.load(f)

if os.path.exists(MHeardPath):
    with open(MHeardPath, 'rb') as f:
        MHeard = pickle.load(f)

if os.path.exists(MoniLogPath):
    with open(MoniLogPath, 'rb') as f:
        monitorbuffer = pickle.load(f)

if os.path.exists(ChanLogPath):
    with open(ChanLogPath, 'rb') as f:
        channelbuffers = pickle.load(f)

#------------------------------------------------------------- Websocket & HTTP ---------------------------------------------------------------------------

MYPORT = 8765
MIME_TYPES = {"html": "text/html", "js": "text/javascript", "css": "text/css", "json": "text/json"}
USERS = set()

async def process_request(sever_root, path, request_headers):
    if "Upgrade" in request_headers:
        return  # Probably a WebSocket connection

    if path == '/':
        path = '/index.html'

    full_path = os.path.realpath(os.path.join(sever_root, path[1:]))
    response_headers = [('Server', 'asyncio websocket server'), ('Connection', 'close')]

    if path != '/server.json':
        if os.path.commonpath((sever_root, full_path)) != sever_root or not os.path.exists(full_path) or not os.path.isfile(full_path):
            print("[Network]\33[1;31m HTTP GET {} 404 File not found".format(path) + "\33[0m")
            return HTTPStatus.NOT_FOUND, [], b'404 NOT FOUND'

    extension = full_path.split(".")[-1]
    mime_type = MIME_TYPES.get(extension, "application/octet-stream")
    response_headers.append(('Content-Type', mime_type))
    if path != '/server.json':
        body = open(full_path, 'rb').read()
    else:
        body = str('{"port": ' + str(MYPORT) + '}').encode()
    response_headers.append(('Content-Length', str(len(body))))
    return HTTPStatus.OK, response_headers, body

async def register(websocket):
    global USERS
    global tlast
    print("[Network]\33[32m New WebSocket connection from", str(websocket.remote_address)[1:-1].replace('\'','').replace(', ',':') + "\33[0m")
    USERS.add(websocket)
    await asyncio.sleep(0.22)
    ser.write(b'\x00\x01\x00\x4D')
    tmp = ser.readline()[2:-1].decode()
    await sendmsg(0,'cmd1','M:' + tmp)
    await asyncio.sleep(0.0016)
    ser.write(b'\x00\x01\x00\x49')
    tmp = ser.readline()[2:-1].decode()
    await sendmsg(0,'cmd1','I:' + tmp)
    await asyncio.sleep(0.0016)
    if monitorbuffer:
        for lines in monitorbuffer:
            await websocket.send(json.dumps(lines[0]).replace("\\n", "n"))
    await asyncio.sleep(0.1)
    if channelbuffers:
        for lines in channelbuffers:
            await websocket.send(json.dumps(lines[0]).replace("\\n", "n"))
    await asyncio.sleep(0.1)
    await websocket.send('{"cmd":"bulkdone"}')
    await websocket.send('{"cmd":"homepoint","station":"' + MyCall + '","lat":"' + str(config.get('radio', 'latitude')) + '","lon":"' + str(config.get('radio', 'longitude')) + '"}')
    await sendmsg(0,'cmd3',json.dumps(ACTCHANNELS).replace('\"','\\\"'))

async def unregister(websocket):
    global USERS
    print("[Network]\33[32m WebSocket connection closed for", str(websocket.remote_address)[1:-1].replace('\'','').replace(', ',':') + "\33[0m")
    USERS.remove(websocket)

OnLora = False

async def mysocket(websocket, path):
    global ACTIVECHAN
    global ACTCHANNELS
    global OnLora
    await register(websocket)
    try:
        async for message in websocket:
            if message[:1] == '@':
                if message[1:].isnumeric():
                    tmp2 = int(message[1:])
                    if tmp2 == 9:
                        # LoraNet
                        OnLora = True
                        print('Websocket on Lora Net')
                    elif tmp2 == 10:
                        # APRS
                        OnLora = False
                        print('Websocket on APRS Net')
                    else:
                        OnLora = False
                        ACTIVECHAN = num2byte(tmp2)
                        ser.write(ACTIVECHAN + b'\x01\x00\x49')
                        tmp = ser.readline()[2:-1].decode()
                        await sendmsg(tmp2,'cmd1','I:' + tmp)
                        # macybe send connected to name ?
                        ser.write(ACTIVECHAN + b'\x01\x00\x43')
                        # await sendmsg(int(message[1:]),'cmd3','C:' + tmp)
                        ACTCHANNELS[tmp2][1] = ser.readline()[2:-1].decode()
                        await sendmsg(tmp2,'cmd3',json.dumps(ACTCHANNELS).replace('\"','\\\"'))
            else:
                print("[Network] " + message + "\33[0m")
                # need know what channel we actually sennding on . . .
                if OnLora:
                    meshtastic_client.sendText(message)
                    await sendmsg(9,'echo',message)
                else:
                    ch = int(ACTIVECHAN.hex(), 16)
                    await sendmsg(ch,'echo',message)
                    sendqueue.append([ch,message])
    except Exception as e:
        print("[Network] \33[1;31m" + repr(e))
    finally:
        await unregister(websocket)

async def sendmsg(chan, cmd, message):
    global USERS
    timenow = int(time.time())
    if USERS:
        try:
            for user in USERS:
                await user.send('{"time":' + str(timenow) + ',"chan":' + str(chan) + ',"cmd":"' + cmd + '","data":"' + message + '"}') # might need a replace \r for \n as well; needs see...
        except Exception as e:
            print("[Network] \33[1;31m" + repr(e))

    if cmd != 'cmd1' and cmd != 'cmd2' and cmd != 'cmd3' and cmd != 'cmd100' and cmd != 'loraHeard':
        tmp = {}
        tmp['time'] = timenow
        tmp['chan'] = chan
        tmp['cmd']  = cmd
        tmp['data'] = message;
        if chan == 0:
            monitorbuffer.append([tmp])
            if len(monitorbuffer) > 300:
                monitorbuffer.pop(0)
        else:
            if "deviceMetrics" not in message:
                channelbuffers.append([tmp]);
                if len(channelbuffers) > 500:
                    channelbuffers.pop(0)

#------------------------------------------------------------- Console Chat ---------------------------------------------------------------------------

async def main():
    if config.get('meshtastic', 'plugin_enable') == 'True':
        pub.subscribe(
            on_meshtastic_message, "meshtastic.receive", loop=asyncio.get_event_loop()
        )
        pub.subscribe(
            on_lost_meshtastic_connection,
            "meshtastic.connection.lost",
        )
    # Need add active channel here
    while True:
        text = await ainput("")
        await sendmsg(0,'echo',text[:-1])
        _print('\033[1A' + '\033[K', end='')
        print("[Console] " + text[:-1])
        sendqueue.append([0,text[:-1]])

async def ainput(string: str) -> str:
    await asyncio.get_event_loop().run_in_executor(
            None, lambda s=string: sys.stdout.write(s+' '))
    return await asyncio.get_event_loop().run_in_executor(
            None, sys.stdin.readline)

#----------------------------------------------------------- Meshtastic Lora Con ------------------------------------------------------------------------

import meshtastic.tcp_interface
import meshtastic.serial_interface
from pubsub import pub
meshtastic_client = None
lora_lastmsg = ''

def connect_meshtastic(force_connect=False):
    global meshtastic_client
    if meshtastic_client and not force_connect:
        return meshtastic_client
    meshtastic_client = None
    # Initialize Meshtastic interface
    retry_limit = 3
    attempts = 1
    successful = False
    target_host = config.get('meshtastic', 'host')
    comport = config.get('meshtastic', 'serial_port')
    cnto = target_host
    if config.get('meshtastic', 'interface') != 'tcp':
        cnto = comport
    print("[LoraNet] Connecting to meshtastic on " + cnto + "...")
    while not successful and attempts <= retry_limit:
        try:
            if config.get('meshtastic', 'interface') == 'tcp':
                meshtastic_client = meshtastic.tcp_interface.TCPInterface(hostname=target_host)
            else:
                meshtastic_client = meshtastic.serial_interface.SerialInterface(comport)
            successful = True
        except Exception as e:
            attempts += 1
            if attempts <= retry_limit:
                print("[LoraNet] Attempt #{attempts-1} failed. Retrying in {attempts} secs... {e}")
                time.sleep(attempts)
            else:
                print("[LoraNet] Could not connect: {e}")
                return None

    nodeInfo = meshtastic_client.getMyNodeInfo()
    print("[LoraNet] Connected to " + nodeInfo['user']['id'] + " > "  + nodeInfo['user']['shortName'] + " / " + nodeInfo['user']['longName'] + " using a " + nodeInfo['user']['hwModel'])
    logLora((nodeInfo['user']['id'])[1:], ['NODEINFO_APP', nodeInfo['user']['shortName'], nodeInfo['user']['longName'], nodeInfo['user']["macaddr"],nodeInfo['user']['hwModel']])
    updatesnodes()
    return meshtastic_client

def on_lost_meshtastic_connection(interface):
    print("[LoraNet] Lost connection. Reconnecting...")
    connect_meshtastic(force_connect=True)

def logLora(nodeID, info):
    tnow = int(time.time())
    if nodeID in LoraDB:
        LoraDB[nodeID][0] = tnow # time last seen
    else:
        LoraDB[nodeID] = [tnow, '', '', '', '', '', '', '', tnow, '', '', '']
        sendqueue.append([0,'[LoraNET] New lora station registered with station id !' + nodeID])
    if info[0] == 'NODEINFO_APP':
        LoraDB[nodeID][1] = info[1] # short name
        LoraDB[nodeID][2] = info[2] # long name
        LoraDB[nodeID][6] = info[3] # mac adress
        LoraDB[nodeID][7] = info[4] # hardware
    elif info[0] == 'POSITION_APP':
        LoraDB[nodeID][3] = info[1] # latitude
        LoraDB[nodeID][4] = info[2] # longitude
        LoraDB[nodeID][5] = info[3] # altitude
        LoraDB[nodeID][9] = LatLon2qth(info[1],info[2])

# import yaml
def on_meshtastic_message(packet, loop=None):
    # print(yaml.dump(meshtastic_client.nodes))
    global lora_lastmsg
    donoting = True
    if "decoded" in packet:
        data = packet["decoded"]
        text_from  = packet["fromId"][1:]
        text_mqtt = ''
        text_msgs = ''
        fromraw = text_from
        if text_from in LoraDB:
            if LoraDB[text_from][1] != '':
                text_from = LoraDB[text_from][1] + " (" + LoraDB[text_from][2] + ")"
        else:
            updatesnodes()

        if "viaMqtt" in packet:
            text_mqtt = ' via mqtt'

        # Lets Work the Msgs
        if data["portnum"] == "TELEMETRY_APP":
            if "deviceMetrics" in  data["telemetry"]:
                text = data["telemetry"]["deviceMetrics"]
                if "voltage" in text and "batteryLevel" in text:
                    sendqueue.append([9,'deviceMetrics:{\\"id\\":\\"' + packet["fromId"][1:] + '\\",\\"v\\":' + str(round(text["voltage"],2)) + ',\\"b\\":' + str(text["batteryLevel"]) + '}'])
            donoting = True
        if data["portnum"] == "NEIGHBORINFO_APP":
            donoting = True
        if data["portnum"] == "ROUTING_APP":
            donoting = True
        if data["portnum"] == "POSITION_APP":
            text = data["position"]
            if "altitude" in text:
                text_msgs = "Position beacon: "
                if "latitude" in text:
                    text_msgs += "latitude " + str(round(text["latitude"],4)) + " "
                if "longitude" in text:
                    text_msgs += "longitude " + str(round(text["longitude"],4)) + " "
                    qth = LatLon2qth(round(text["latitude"],6), round(text["longitude"],6))
                    # text_msgs += "(" + qth + ") "
                if "altitude" in text:
                    text_msgs += "altitude " + str(text["altitude"]) + "meter"

                # if not is_hour_between(1, 10) and "viaMqtt" not in packet:
                #     sendqueue.append([0,'[LoraNET] Position beacon from ' + text_from + ' QTH ' + qth[:-2]])
                text_raws = text_msgs
                # sendqueue.append([9,text_from + text_mqtt + '&#13;' + text_msgs])
                logLora(packet["fromId"][1:], ['POSITION_APP', text["latitude"], text["longitude"], text["altitude"]])
                # ["latitudeI"] ["longitude"] ["altitude"] ["time"] ["precisionBits"]
                donoting = True
        if data["portnum"] == "NODEINFO_APP":
            text = data["user"]
            if "shortName" in text:
                lora_sn = str(text["shortName"].encode('ascii', 'xmlcharrefreplace')).replace('b\'', '')[:-1]
                lora_ln = str(text["longName"].encode('ascii', 'xmlcharrefreplace')).replace('b\'', '')[:-1]
                lora_mc = text["macaddr"]
                lora_mo = text["hwModel"]
                logLora(packet["fromId"][1:], ['NODEINFO_APP', lora_sn, lora_ln, lora_mc, lora_mo])
                text_raws = "NodeInfo beacon using hardware " + lora_mo
                text_from = LoraDB[packet["fromId"][1:]][1] + " (" + LoraDB[packet["fromId"][1:]][2] + ")"
                sendqueue.append([9,text_from + text_mqtt + '&#13;' + text_raws])
                donoting = False
        if data["portnum"] == "TEXT_MESSAGE_APP" and "text" in data:
            text_msgs = str(data["text"].encode('ascii', 'xmlcharrefreplace')).replace('b\'', '')[:-1]
            text_raws = data["text"]
            text_chns = '0'
            if "channel" in packet:
                text_chns = str(packet["channel"])
            sendqueue.append([9,text_from + text_mqtt + ' on Channel ' + text_chns + '&#10;' + text_msgs])
            sendqueue.append([0,'[LoraNET] [Ch ' + text_chns + '] ' + text_from + text_mqtt + ': ' + text_msgs])
            donoting = False

        if donoting == True:
            logLora(packet["fromId"][1:],['UPDATETIME'])

        if "viaMqtt" in packet:
            LoraDB[fromraw][10] = ' via mqtt'
        else:
            LoraDB[fromraw][10] = ''

        if donoting == False and text_raws != '' and lora_lastmsg != text_raws:
            lora_lastmsg = text_raws
            print("[LoraNet]\33[0;37m mqtt " + text_from + LoraDB[fromraw][10] + "\33[0m")
            _print('\33[0;32m' + (' ' * 21) + text_raws + '\33[0m')

def updatesnodes():
    info = ''
    for nodes, info in meshtastic_client.nodes.items():
        nodeID = str(info['user']['id'])[1:]
        nodeLast = 0
        if "lastHeard" in info and info["lastHeard"] is not None:
            nodeLast = info['lastHeard']
        if nodeID in LoraDB:
            LoraDB[nodeID][0] = nodeLast
        else:
            LoraDB[nodeID] = [nodeLast, '', '', '', '', '', '', '', nodeLast, '', '', '']

        if "user" in info:                
            LoraDB[nodeID][1] = str(info['user']['shortName'])
            LoraDB[nodeID][2] = str(info['user']['longName'])
            LoraDB[nodeID][6] = str(info['user']['macaddr'])
            LoraDB[nodeID][7] = str(info['user']['hwModel'])
        if "position" in info:
            tmp = info['position']
            if "latitude" in tmp and "longitude" in tmp:
                LoraDB[nodeID][3] = tmp['latitude']
                LoraDB[nodeID][4] = tmp['longitude']
                LoraDB[nodeID][9] = LatLon2qth(tmp['latitude'],tmp['longitude'])
            if "altitude" in tmp:
                LoraDB[nodeID][5] = tmp['altitude']
        if "viaMqtt" in info:
            LoraDB[nodeID][10] = ' via mqtt'
        if "snr" in info and info['snr'] is not None:
            LoraDB[nodeID][11] = str(info['snr']) + 'dB'

#-------------------------------------------------------------- TNC WA8DED ---------------------------------------------------------------------------
BEACONDELAY = int(config.get('radio', 'beacon_time'))
BEACONTEXT = config.get('radio', 'beacon_text')
ACTIVECHAN = num2byte(0)
ACTCHANNELS = {0: ['CQ','',0]}
#             Chn:[My call, Remote call, in/out]
sendqueue = []
channels = config.get('tncinit', '3')
polling = 1
channel_to_read_byte = b'x00'
tlast = 0

ser = serial.Serial()
ser.port = config.get('intertnc', 'serial_port')
ser.baudrate = config.get('intertnc', 'serial_baud')
ser.bytesize = serial.EIGHTBITS     # number of bits per bytes
ser.parity = serial.PARITY_NONE     # set parity check: no parity
ser.stopbits = serial.STOPBITS_ONE  # number of stop bits
# ser.timeout = None                # block read
ser.timeout = 0.05                  # non blocking read
ser.xonxoff = False                 # disable software flow control
ser.rtscts = False                  # disable hardware (RTS/CTS) flow control
ser.dsrdtr = False                  # disable hardware (DSR/DTR) flow control
ser.writeTimeout = 2                # timeout for write

def logheard(call, cmd, info):
    tnow = int(time.time())

    # Remove the -Channel if present
    sindex = call.find('-')
    if sindex > 1:
        call = call[:sindex]

    # 'callsign' = ['name','jo locator if known',first heard,last heard,heard count,first connect, last connect, connect count];
    #                  0              1              2           3           4           5             6             7
    if cmd == 5:
        if call in MHeard:
            MHeard[call][3] = tnow
            MHeard[call][4] += 1
        else:
            MHeard[call] = ['', '', tnow, tnow, 1, 0, 0, 0]
            if MyCall == call:
                MHeard[call][0] = config.get('radio', 'sysop')
            else:
                sendqueue.append([0,'New station registered with station call ' + call])
    elif cmd == 6:
        if call in MHeard:
            if len(info) >= len(MHeard[call][1]) and str(info) != '':
                MHeard[call][1] = str(info)
        else:
            MHeard[call] = ['', str(info), tnow, tnow, 1, 0, 0, 0]
        MHeard[call][4] += 1
        MHeard[call][3] = tnow
    elif cmd == 3:
        if call in MHeard:
            MHeard[call][6] = tnow
            MHeard[call][4] += 1
            MHeard[call][7] += 1
            if MHeard[call][5] == 0:
                MHeard[call][5] = tnow

# Set TNC in WA8DED Hostmode
def init_tncinWa8ded():
    try:
        ser.open()
    except Exception as e:
        print("[Serial!] \33[1;31m" + repr(e))
        sys.exit()
    ser.write(b'\x11\x18\x1b')
    ser.readline()
    ser.write(b'\x4a\x48\x4f\x53\x54\x31\x0d')
    print('\33[0;33mSetting TNC in hostmode...\33[0m')
    print("[ DEBUG ] " + ser.readline().decode())

def send_init_tnc(command, chan, cmd):
    length_command = len(command) - 1
    if length_command < 10:
        hex_length_command = '0' + str(length_command)
    else:
        hex_length_command = str(length_command)

    start_hex = '%02d' % (chan,) + '%02d' % (cmd,)
    bytes_command = bytearray(command, 'utf-8')
    hex_begin_bytes = bytearray.fromhex(start_hex)
    hex_length_bytes = bytearray.fromhex(hex_length_command)
    start_bytes = hex_begin_bytes + hex_length_bytes
    all_bytes = start_bytes + bytes_command
    return all_bytes

def send_tnc(command, channel):
    allbytes = []
    allbytes.append('%02d' % channel)
    allbytes.append('%02d' % 0)  # Info/CMD
    txt_len = int(len(command) - 1)
    allbytes.append(hex(txt_len)[2:].zfill(2))
    for char in command:
        ascii_val = ord(char)
        allbytes.append(hex(ascii_val)[2:].zfill(2))
    return bytearray.fromhex(''.join(allbytes))

def send_tncC(command, channel):
    allbytes = []
    allbytes.append('%02d' % channel)
    allbytes.append('%02d' % 1)  # Info/CMD
    txt_len = int(len(command) - 1)
    allbytes.append(hex(txt_len)[2:].zfill(2))
    for char in command:
        ascii_val = ord(char)
        allbytes.append(hex(ascii_val)[2:].zfill(2))
    return bytearray.fromhex(''.join(allbytes))

def init_tncConfig():
    global ACTCHANNELS
    ACTCHANNELS = {}
    x = 0
    for x in range(1, 18):
        if x == 2:
            ACTCHANNELS[0] = [config.get('tncinit', '2')[2:], '', 0]
        if x == 3:
            all_bytes = send_init_tnc(config.get('tncinit', str(x)),0,1)
            ser.write(all_bytes)
            ser.readline()
            # Set Callsign I for every channel Y
            callsign_str = 'I ' + MyCall
            callsign_len = len(callsign_str)
            callsign_len_hex = '0' + str(callsign_len -1)
            callsign_len_byte = bytearray.fromhex(callsign_len_hex)
            callsign_in_bytes = bytearray(callsign_str, 'utf-8')
            chan_i = 0
            for x in range(1, int(channels[2:]) + 1):
                chan_i = chan_i + 1
                incremented_hex_value = num2byte(chan_i)
                ser.write(incremented_hex_value + b'\x01' + callsign_len_byte + callsign_in_bytes)
                ser.readline()
                ser.write(incremented_hex_value + b'\x01\x00\x43')
                tmp = (ser.readline())[2:-1].decode()
                print('[Chan %02d' % (chan_i,) + '] ' + callsign_str + ' > ' + tmp)
                ACTCHANNELS[chan_i] = [callsign_str[2:],tmp,0]
        elif x == 6:
            # Set date for K
            date_string = today_date.strftime("%m/%d/%y")
            date_today = send_init_tnc("K " + date_string,0,1)
            ser.write(date_today)
            ser.readline()
        elif x == 7:
            # Set time for K
            time_string = time_now.strftime('%H:%M:%S')
            now_time = send_init_tnc("K " + time_string,0,1)
            ser.write(now_time)
            ser.readline()
        else:
            if x == 17:
                all_bytes = send_init_tnc('I ' + MyCall,0,1)
            else:
                all_bytes = send_init_tnc(config.get('tncinit', str(x)),0,1)
            ser.write(all_bytes)
            ser.readline()
    print('\33[0;33mTNC Active and listening...\33[0m')
    sendqueue.append([0,BEACONTEXT + ' @ ' + time.strftime("%H:%M", time.localtime())])

async def go_serial():
    # serial port stuff here
    global polling
    global ACTIVECHAN
    global tlast
    polling = 1
    queing = 0
    sendbuffs = 0
    x = 0
    while True:
        for x in range(6):
            if polling == 1:
                await asyncio.sleep(pdelay)
                ser.write(b'\xff\x01\x00G')
                polling_data = ser.readline()
                # print('IS 0000 > ' + polling_data.hex())

            data_hex = polling_data.hex()
            if data_hex != 'ff0100':
                polling = 0

                if data_hex == '': data_hex = '0000'

                # ff 01 02 00
                if len(data_hex) > 4:
                    chan_i = int(data_hex[4:6].upper(), 16) - 1
                else:
                    chan_i = int(data_hex[2:4].upper(), 16) # ?? should need be [0:2]

                # these two cases should not happen but happen... 
                if chan_i > 10 and chan_i < 255 or chan_i < 0:
                    chan_i = 0
                poll_byte = num2byte(chan_i)

                await asyncio.sleep(pdelay)
                ser.write(poll_byte + b'\x01\x00G')
                data = ser.readline()
                data_hex = data.hex()

                if data_hex == '': data_hex = '0000'

                data_int = int(data_hex[2:4].upper(), 16)
                namechan = '[Monitor]'
                if chan_i != 0:
                    namechan = '[Chan %02d]' % (chan_i,)

                if data_int == 0:
                    # print("Status : Succes with NoInfo")
                    polling = 1
                elif data_int == 1:
                    # print("Succes with Messages")
                    data_decode = (codecs.decode(data, 'cp850')[1:])
                    print(namechan + " [1] \33[1;32m" + data_decode + "\33[0m")
                    await sendmsg(chan_i,'cmd1',"OK: " + data_decode)
                elif data_int == 2:
                    # print("Failure with Messages")
                    data_decode = (codecs.decode(data, 'cp850')[2:])
                    print(namechan + " [2] \33[1;31m" + data_decode + "\33[0m")
                    await sendmsg(chan_i,'cmd2',"Error: " + data_decode)
                elif data_int == 3:
                    # print("Link Status")
                    data_decode = (codecs.decode(data, 'cp850')[2:][:-1])
                    if 'DISCONNECTED' in data_decode:
                        # Channel chan_i got disconected
                        ACTCHANNELS[chan_i][1] = 'CHANNEL NOT CONNECTED'
                        ACTCHANNELS[chan_i][2] = 0
                        await sendmsg(0,'cmd3',json.dumps(ACTCHANNELS).replace('\"','\\\"'))
                    elif 'CONNECTED' in data_decode:
                        # Channel chan_i got disconected
                        remote_station = data_decode.split(" ")[3]
                        logheard(remote_station, 3, '')
                        if ACTCHANNELS[chan_i][1] != remote_station:
                            print('we are here?')
                            ctext_file = 'ctext-' + remote_station + '.txt'
                            if os.path.isfile(MyPath + ctext_file):
                                # We got a personal ctext send it...
                                textchunk(readfile(ctext_file),chan_i,remote_station)
                            elif os.path.isfile(MyPath + 'ctext.txt'):
                                # Send default ctext.txt
                                textchunk(readfile('ctext.txt'),chan_i,remote_station)
                            else:
                                print('[ DEBUG ] No ctext.txt file in txtfiles folder!')
                        ACTCHANNELS[chan_i][1] = remote_station
                        ACTCHANNELS[chan_i][2] = 2
                        await sendmsg(0,'cmd3',json.dumps(ACTCHANNELS).replace('\"','\\\"'))

                    print(namechan + " \33[0;37m" + data_decode + "\33[0m")
                    await sendmsg(chan_i,'chat',data_decode)
                elif data_int == 4:
                    # print("Monitor Header NoInfo")
                    print(namechan + " \33[1;37m" + data.decode()[2:] + "\33[0m")
                    await sendmsg(chan_i,'cmd4',data.decode()[2:-1])
                elif data_int == 5:
                    # print("Monitor Header With Info")
                    data_decode = (codecs.decode(data, 'cp850')[2:])

                    #need check mheard if new or not and appent to msg *NEW*
                    callsign = data_decode.split(" ")[1]
                    sindex = callsign.find('-')
                    if sindex > 1:
                        callsign = callsign[:sindex]
                    
                    heardnew = ''
                    if callsign not in MHeard:
                        heardnew = ' * NEW *'

                    logheard(callsign, 5, '');
                    print(namechan + " \33[1;37m" + data_decode + heardnew + "\33[0m")
                    await sendmsg(chan_i,'cmd5',data_decode[:-1] + heardnew)
                    heardnew = callsign
                elif data_int == 6:
                    data_decode = (codecs.decode(data, 'cp850')[3:])
                    data_out = data_decode.splitlines()
                    sendtext = ''
                    _print('\33[1;36m', end='')
                    for lines in data_out:
                        _print((' ' * 21) + lines)
                        sendtext += lines + '\r'
                    _print('\33[0m', end='')

                    # grr = str(sendtext[:-1].encode('ascii', 'xmlcharrefreplace')).replace('b\'', '')[:-1]
                    sendtext = re.sub(r'(\r\n|\n|\r)', '\n', sendtext[:-1])
                    sendtext = sendtext.replace('\"','&quot;')
                    await sendmsg(chan_i,'warn',str(sendtext.encode('ascii', 'xmlcharrefreplace')).replace('b\'', '')[:-1])

                    locator = re.findall(r'[A-R]{2}[0-9]{2}[A-Z]{2}[0-9]{2}', data_decode.upper())
                    if not locator:
                        locator = re.findall(r'[A-R]{2}[0-9]{2}[A-Z]{2}', data_decode.upper())

                    # APRS Location to locator (hopfully) apparently we off by like 5km.. or so
                    if not locator:
                        if len(data_decode) >= 20:
                            ymp = str(re.findall(r'[0-9]{4}[.][0-9]{2}[N,S]/.[0-9]{4}[.][0-9]{2}[E,W]', data_decode))
                            # we get as example ['5303.96N/00700.39E']
                            if len(ymp) == 22:
                                direction = {'N':1, 'S':-1, 'E': 1, 'W':-1}
                                new = (ymp[2:4] + ' ' + ymp[4:6] + ' ' + ymp[7:9] + ' ' + ymp[9:10]).split()
                                new_dir = new.pop()
                                new.extend([0,0,0])
                                lat = (int(new[0])+int(new[1])/60.0+int(new[2])/3600.0) * direction[new_dir]
                                new = (ymp[12:14] + ' ' + ymp[14:16] + ' ' + ymp[17:19] + ' ' + ymp[19:20]).split()
                                new_dir = new.pop()
                                new.extend([0,0,0])
                                lon = (int(new[0])+int(new[1])/60.0+int(new[2])/3600.0) * direction[new_dir]
                                locator = [LatLon2qth(lat, lon)[:-2],12]

                    if not locator:
                         logheard(callsign, 6, '')
                    else:
                         logheard(callsign, 6, locator[0])
                    
                    heardnew = ''
                elif data_int == 7:
                    # print("Connect information")
                    # This should not be on monitor
                    data_decode = (codecs.decode(data, 'cp850')[3:])
                    data_out = data_decode.splitlines()
                    numlines = 0
                    _print('\33[1;30m', end='')
                    sendtext = ''
                    for lines in data_out:
                        _print((' ' * 21) + lines)
                        sendtext += lines + '\r'
                        numlines += 1
                    _print('\33[0m', end='')
                    # grr = str(sendtext[:-1].encode('ascii', 'xmlcharrefreplace')).replace('b\'', '')[:-1]
                    sendtext = re.sub(r'(\r\n|\n|\r)', '\n', sendtext[:-1])
                    sendtext = sendtext.replace('\"','&quot;')
                    await sendmsg(chan_i,'chat',str(sendtext.encode('ascii', 'xmlcharrefreplace')).replace('b\'', '')[:-1])
                    # deal weith incomming // commands. 
                    donoting = False
                    if '//' in sendtext and numlines == 1 and ACTCHANNELS[chan_i][1] != 'CHANNEL NOT CONNECTED':
                        reqcmd = sendtext[2:3].upper()
                        if   reqcmd == 'H':
                            # send ./txtfiles/help.txt
                            textchunk(readfile('help.txt'),chan_i,ACTCHANNELS[chan_i][1])
                        elif reqcmd == 'M':
                            donoting = True # send mHeard info...
                        elif reqcmd == 'N':
                            if sendtext[2:6].upper() == 'NEWS':
                                # send ./txtfiles/news.txt
                                textchunk(readfile('news.txt'),chan_i,str(ACTCHANNELS[chan_i][1]))
                            else:
                                MHeard[str(ACTCHANNELS[chan_i][1])][0] = sendtext[7:]
                                textchunk('Thank you ' + sendtext[7:] + ',recored your sysop name in database.',chan_i,str(ACTCHANNELS[chan_i][1]))
                        elif reqcmd == 'I':
                            # send ./txtfiles/info.txt
                            textchunk(readfile('info.txt'),chan_i,str(ACTCHANNELS[chan_i][1]))
                        elif reqcmd == 'W':
                            # send ./txtfiles/weather.txt (weer.txt)
                            textchunk(readfile('weer.txt'),chan_i,str(ACTCHANNELS[chan_i][1]))
                        elif reqcmd == 'Q':
                            # send 'Totziens maar weer!'
                            textchunk(readfile('qrt.txt'),chan_i,str(ACTCHANNELS[chan_i][1]))
                            all_bytes = send_tncC('D', chan_i)
                            ser.write(all_bytes)
                            tmp = ser.readline()[2:-1].decode()
                        elif reqcmd == 'V':
                            # send 'Totziens maar weer!'
                            textchunk(readfile('version.txt'),chan_i,str(ACTCHANNELS[chan_i][1]))
                        else:
                            # send 'ehh what moet dat nu? // whaaa?'
                            textchunk('ehh what moet dat nu? // whaaa?',chan_i,str(ACTCHANNELS[chan_i][1]))
                else:
                    print('[ DEBUG ]\33[0;33m Stage Get CMD Unknown : "' + data_hex + '"')
                    # pass
            x += 1
        else:
            x = 0
            queing += 1
            if queing == 1:
                chan_i = int(ACTIVECHAN.hex(), 16)
                ser.write(ACTIVECHAN + b'\x01\x01\x40\x42')
                tmp = ser.readline()[2:-1].decode()
                await sendmsg(chan_i,'cmd1','@B:' + tmp)
                await asyncio.sleep(pdelay)
            elif queing == 2:
                ser.write(ACTIVECHAN + b'\x01\x00\x4C')
                tmp = ser.readline()[2:-1].decode()
                await sendmsg(chan_i,'cmd1','L:' + tmp)
                tmp = int(psutil.Process(os.getpid()).memory_info().rss)
                await sendmsg(chan_i,'cmd1','@MEM:' + str(tmp))
                await asyncio.sleep(pdelay)
            elif queing == 3:
                # Lets check if we have a queue to send and if so, send it
                if len(sendqueue) > 0:
                    todo = (sendqueue[0])
                    sendqueue.pop(0)
                    if todo[0] == 9 or todo[0] == 10:
                        await sendmsg(todo[0],'cmd4',todo[1])
                    elif todo[0] > 19:
                        beacon = send_tnc(todo[1], todo[0] - 20)
                        ser.write(beacon)
                        tmp = ser.readline().decode()
                        await asyncio.sleep(pdelay)                       
                    else:
                        beacon = send_tnc(todo[1] + '\r', todo[0])
                        ser.write(beacon)
                        tmp = ser.readline().decode()
                        await asyncio.sleep(pdelay)
                queing = 0
            # And because we need to, send the mheard ever 15 full sec?
            tnow = int(time.time())
            if tnow > tlast + 6:
                tlast = tnow
                sendbuffs += 1
                if sendbuffs == 1:
                    await sendmsg(100,'cmd100',json.dumps(MHeard).replace('\"','\\\"'))
                else:
                    await sendmsg(100,'loraHeard',json.dumps(LoraDB).replace('\"','\\\"'))
                    sendbuffs = 0

#-------------------------------------------------------------- Side Functions ---------------------------------------------------------------------------

def LatLon2qth(latitude, longitude):
    A = ord('A')
    a = divmod(longitude + 180, 20)
    b = divmod(latitude + 90, 10)
    locator = chr(A + int(a[0])) + chr(A + int(b[0]))
    lon = a[1] / 2.0
    lat = b[1]
    i = 1
    while i < 5:
        i += 1
        a = divmod(lon, 1)
        b = divmod(lat, 1)
        if not (i % 2):
            locator += str(int(a[0])) + str(int(b[0]))
            lon = 24 * a[1]
            lat = 24 * b[1]
        else:
            locator += chr(A + int(a[0])) + chr(A + int(b[0]))
            lon = 10 * a[1]
            lat = 10 * b[1]
    return locator

def locator2deg(locator):
    if len(locator) == 6:
        locator += "55AA"
    if len(locator) == 7:
        locator += "LL"

    loca = [ord(char) - 65 for char in locator]
    loca[2] += 17
    loca[3] += 17
    loca[6] += 17
    loca[7] += 17
    lon = (loca[0] * 20 + loca[2] * 2 + loca[4] / 12 + loca[6] / 120 + loca[8] / 2880 - 180)
    lat = (loca[1] * 10 + loca[3] + loca[5] / 24 + loca[7] / 240 + loca[9] / 5760 - 90)
    return {'latitude': lat, 'longitude': lon}

def calc_gc(lat1, lon1, lat2, lon2):
    d = math.acos(math.sin(lat1) * math.sin(lat2) + math.cos(lat1) * math.cos(lat2) * math.cos(lon1 - lon2))
    gc_d = round(((180.0 / math.pi) * d) * 60 * 10) / 10
    gc_dm = round(1.852 * gc_d * 10) / 10

    if math.sin(lon2 - lon1) < 0:
        tc = math.acos((math.sin(lat2) - math.sin(lat1) * math.cos(d)) / (math.sin(d) * math.cos(lat1)))
    elif lon2 - lon1 == 0:
        if lat2 < lat1:
            tc = (math.pi / 180) * 180
        else:
            tc = 0
    else:
        tc = 2 * math.pi - math.acos((math.sin(lat2) - math.sin(lat1) * math.cos(d)) / (math.sin(d) * math.cos(lat1)))

    gc_tc = round(tc * (180.0 / math.pi) * 10) / 10
    winddir = ['N', 'NNO', 'NO', 'ONO', 'O', 'OZO', 'ZO', 'ZZO', 'Z', 'ZZW', 'ZW', 'WZW', 'W', 'WNW', 'NW', 'NNW', 'N']
    wtet = winddir[round(gc_tc * 16 / 360)]
    return f"{gc_dm}Km {wtet} ({gc_tc})"

def is_hour_between(start, end):
    now = datetime.now().hour
    is_between = False
    is_between |= start <= now <= end
    is_between |= end < start and (start <= now or now <= end)
    return is_between

import urllib.request
weatherbeacon = True
myqth = 'JO32'

async def cleaner():
    global weatherbeacon
    while True:
        await asyncio.sleep(60 * BEACONDELAY)
        # no beacon between 1 & 10
        if not is_hour_between(1, 10):
            if weatherbeacon == False:
                sendqueue.append([0,BEACONTEXT + ' @ ' + time.strftime("%H:%M", time.localtime())])
                weatherbeacon = True
            else:
                weatherurl = config.get('radio', 'weatherjson')
                if weatherurl != '' and config.get('radio', 'weatherbeacon') == 'True':
                    try:
                        url = urllib.request.urlopen(weatherurl)
                        wjson = json.load(url)
                        winddir = ['N','NNO','NO','ONO','O','OZO','ZO','ZZO','Z','ZZW','ZW','WZW','W','WNW','NW','NNW','N']
                        wtet  = winddir[round(int(wjson['winddir_avg10m'])*16/360)]
                        sendqueue.append([0,'Weather at ' + myqth[:-2] + ', Wind ' + wtet + ' ' + str(wjson['windspeedbf_avg10m']) + 'bf, Temp ' + str(round(wjson['tempc'])) + 'C, Hum ' + str(wjson['humidity']) + '%, Baro ' + str(round(wjson['baromabshpa'])) + 'hpa @ ' + time.strftime("%H:%M", time.localtime())])
                    except:
                        print('[ DEBUG ] Weather Grab from ' + weatherurl + ' Failed!')
                        sendqueue.append([0,BEACONTEXT + ' @ ' + time.strftime("%H:%M", time.localtime())])
                else:
                    sendqueue.append([0,BEACONTEXT + ' @ ' + time.strftime("%H:%M", time.localtime())])
                weatherbeacon = False
        # Save Databases...
        with open(LoraDBPath, 'wb') as f:
            pickle.dump(LoraDB, f)
        with open(MHeardPath, 'wb') as f:
            pickle.dump(MHeard, f)
        # Save Monitor and Channels
        with open(MoniLogPath, 'wb') as f:
            pickle.dump(monitorbuffer, f)
        with open(ChanLogPath, 'wb') as f:
            pickle.dump(channelbuffers, f)
        # Memory Cleaner...
        gc.collect()

def readfile(file):
    filetoread = MyPath + file
    contents = ''
    if os.path.isfile(filetoread):
        with open(filetoread, 'r') as f:
            contents = f.read()
        if contents != '':
            return contents
    return 'File `' + file + '` not found or empty.'

def textchunk(cnktext , chn, call):
    tmp = ''
    # Lets do some preg replacing to...
    if '%' in cnktext:
        cnktext = cnktext.replace('%V', 'PyPacketRadio v1.1')                               # GP version number, in this case it is 1.61
        cnktext = cnktext.replace('%C', call)                                               # %c = The Call of the opposite Station
        if call in MHeard:
            if MHeard[call][0] != '':
                cnktext = cnktext.replace('%N', MHeard[call][0] + ' (' + call + ')')        # The Name of the opposite Station
            else:
                cnktext = cnktext.replace('%N', call)
                tmp = 'Please register your name via //N yourname'
        else:
            cnktext = cnktext.replace('%N', call)
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
        cnktext = cnktext.replace('%>', 'to ' + MyCall + ' >')                              # bit like a command prompt place holder at bottom of msg
        sindex = cnktext.find('%O')
        if sindex:
            lines = readfile('origin.txt').splitlines()
            myline = random.choice(lines)
            cnktext = cnktext.replace('%O', myline)                                         # %o = Reads a Line from ORIGIN.GPI (Chosen at Random)
        # cnktext = cnktext.replace('%%', '%')                                              # percent sign

    cnktext = re.sub(r'(\r\n|\n|\r)', '\r', cnktext)                                        # lets make sure we only use \n as enter
    cnktext = cnktext.rstrip()
    cnktext = cnktext + '\r'
    # Next part we need is tring to parts if string longer then 7f (127) bytes (characters)
    if len(cnktext) > 253:
        while len(cnktext) > 253:
            tmp = cnktext[0:253]
            cnktext = cnktext[253:]
            # sendqueue.append([chn + 20,tmp])
            print('[ DEBUG ] >>> ' + tmp)
            beacon = send_tnc(tmp, chn)
            ser.write(beacon)
            tmp = ser.readline().decode()
        if len(cnktext) > 0:
            beacon = send_tnc(cnktext, chn)
            ser.write(beacon)
            tmp = ser.readline().decode()
    else:
        # sendqueue.append([chn + 20,cnktext])
        beacon = send_tnc(cnktext, chn)
        ser.write(beacon)
        tmp = ser.readline().decode()

#---------------------------------------------------------------- Start Mains -----------------------------------------------------------------------------

if __name__ == "__main__":
    os.system("")
    print("\33[0;36m _____       _   _                   _____           _        _   _____           _ _")
    print("|  __ \\     | | | |                 |  __ \\         | |      | | |  __ \\         | (_)")
    print("| |__) |   _| |_| |__   ___  _ __   | |__) |_ _  ___| | _____| |_| |__) |__ _  __| |_  ___")
    print("|  ___/ | | | __| '_ \\ / _ \\| '_ \\  |  ___/ _` |/ __| |/ / _ \\ __|  _  // _` |/ _` | |/ _ \\")
    print("| |   | |_| | |_| | | | (_) | | | |_| |  | (_| | (__|   <  __/ |_| | \\ \\ (_| | (_| | | (_) |")
    print("|_|    \\__, |\\__|_| |_|\\___/|_| |_(_)_|   \\__,_|\\___|_|\\_\\___|\\__|_|  \\_\\__,_|\\__,_|_|\\___(_)")
    print("\33[0;36m        __/ | \33[0;32m  An open source Python 3.10 WS Packet server V1.1ß             Created By")
    print("\33[0;36m       |___/\33[0;32m  For WA8DED Modems that support HostMode                JaraLowell & MichTronics\33[0m\n")

    # Replacing the pring function to always add time
    _print = print # keep a local copy of the original print
    builtins.print = lambda *args, **kwargs: _print("\r\33[K\33[1;30m[" + time.strftime("%H:%M:%S", time.localtime()) + "]", *args, **kwargs)

    handler = functools.partial(process_request, os.getcwd() + os.path.sep + 'www')
    start_server = websockets.serve(mysocket, '0.0.0.0', MYPORT, process_request=handler, ping_interval=None)
    print("\33[0;33mStarting up HTTP server at http://localhost:%d/" % MYPORT)
    print("\33[0;33mWeb server files home folder set to " + os.getcwd() + os.path.sep + "www\33[0m")

    init_tncinWa8ded()
    init_tncConfig()

    if config.get('radio', 'latitude') != '' and config.get('radio', 'longitude') != '':
        myqth = LatLon2qth(float(config.get('radio', 'latitude')),float(config.get('radio', 'longitude')))[:-2]
        print("\33[0;33mRadio QTH set to " + myqth)

    if config.get('meshtastic', 'plugin_enable') == 'True':
        print("\33[0;33mLoading meshtastic plugin...")
        meshtastic_interface = connect_meshtastic()
        # need do a meshtastic_interface.nodes
        # this reurns an list of node's known to the device

    try:
        loop = asyncio.get_event_loop()
        asyncio.ensure_future(go_serial())

        loop.run_until_complete(start_server)
        loop.create_task(main())
        loop.create_task(cleaner())
        loop.run_forever()
    except KeyboardInterrupt:
        # Databases...
        with open(LoraDBPath, 'wb') as f:
            pickle.dump(LoraDB, f)
        with open(MHeardPath, 'wb') as f:
            pickle.dump(MHeard, f)
        # Channel Logs..
        with open(MoniLogPath, 'wb') as f:
            pickle.dump(monitorbuffer, f)
        with open(ChanLogPath, 'wb') as f:
            pickle.dump(channelbuffers, f)
        print('Saved Databases')
        print("\33[0;33mPut TNC in Un-attended mode...\33[1;37m\33[0m")
        ser.write(b'\x00\x01\x01\x4d\x4e') # ^MN
        ser.readline()
        ser.write(b'\x00\x01\x06\x55\x31\x41\x77\x61\x79\x21') # U1 Away!
        ser.readline()
        ser.write(b'\x00\x01\x01\x4b\x32') # ^K2
        ser.readline()
        ser.write(b'\x00\x01\x05\x4a\x48\x4f\x53\x54\x30') # JHOST0
        ser.readline()
        ser.close()
        sys.exit()
    except Exception as e:
        print("\33[0;31m " + repr(e) + "\33[1;37m\33[0m")