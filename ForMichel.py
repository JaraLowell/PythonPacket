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

# psutil and websockets needs pip install (and maybe codecs as well?)
import psutil
import websockets
import codecs
import functools
import json
from http import HTTPStatus

# Next two are for the radio side of things
import serial
import configparser

def num2byte(number):
    return bytearray.fromhex("{0:#0{1}x}".format(number,4)[2:])

MYPORT = 8765
MIME_TYPES = {"html": "text/html", "js": "text/javascript", "css": "text/css", "json": "text/json"}
USERS = set()
BEACONDELAY = 30
ACTIVECHAN = num2byte(0)
ACTCHANNELS = {0: 'CQ'}

Chan_Hist = {}
Moni_Hist = {}
MHeard    = {}

today_date = date.today()
time_now = datetime.now()

config = configparser.ConfigParser()
config.read('./config.ini')

channels = config.get('tncinit', '3')
callsign = ""
x = 0
polling = 1
channel_to_read_byte = b'x00'

ser = serial.Serial()
ser.port = 'COM8'
ser.baudrate = 9600
ser.bytesize = serial.EIGHTBITS     # number of bits per bytes
ser.parity = serial.PARITY_NONE     # set parity check: no parity
ser.stopbits = serial.STOPBITS_ONE  # number of stop bits
# ser.timeout = None                # block read
ser.timeout = 0.05                  # non blocking read
ser.xonxoff = False                 # disable software flow control
ser.rtscts = False                  # disable hardware (RTS/CTS) flow control
ser.dsrdtr = False                  # disable hardware (DSR/DTR) flow control
ser.writeTimeout = 2                # timeout for write

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
    print("[Network]\33[32m New WebSocket connection from", str(websocket.remote_address)[1:-1].replace('\'','').replace(', ',':') + "\33[0m")
    USERS.add(websocket)
    ser.write(b'\x00\x01\x00\x4D')
    tmp = ser.readline()[2:-1].decode()
    await sendmsg(0,'cmd1','M:' + tmp)
    ser.write(b'\x00\x01\x00\x49')
    tmp = ser.readline()[2:-1].decode()
    await sendmsg(0,'cmd1','I:' + tmp)

async def unregister(websocket):
    global ACTIVECHAN
    global USERS
    print("[Network]\33[32m WebSocket connection closed for", str(websocket.remote_address)[1:-1].replace('\'','').replace(', ',':') + "\33[0m")
    USERS.remove(websocket)
    ACTIVECHAN = num2byte(0)

async def mysocket(websocket, path):
    global ACTIVECHAN
    global ACTCHANNELS
    await register(websocket)
    try:
        async for message in websocket:
            if message[:1] == '@':
                if message[1:].isnumeric():
                    tmp2 = int(message[1:])
                    ACTIVECHAN = num2byte(tmp2)
                    ser.write(ACTIVECHAN + b'\x01\x00\x49')
                    tmp = ser.readline()[2:-1].decode()
                    await sendmsg(tmp2,'cmd1','I:' + tmp)
                    # macybe send connected to name ?
                    ser.write(ACTIVECHAN + b'\x01\x00\x43')
                    # await sendmsg(int(message[1:]),'cmd3','C:' + tmp)
                    ACTCHANNELS[tmp2] = ser.readline()[2:-1].decode()
                    await sendmsg(tmp2,'cmd3',json.dumps(ACTCHANNELS).replace('\"','\\\"'))
            else:
                print("[Network] " + message + "\33[0m")
                await sendmsg(0,'echo',message)
                beacon = send_tnc(message + '\r', 0)
                ser.write(beacon)
                ser.readline()
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
                await user.send('{"time":' + str(timenow) + ',"chan":' + str(chan) + ',"cmd":"' + cmd + '","data":"' + message + '"}')
        except Exception as e:
            print("[Network] \33[1;31m" + repr(e))

async def main():
    global ACTIVECHAN
    while True:
        text = await ainput("")
        await sendmsg(0,'echo',text[:-1])
        _print('\033[1A' + '\033[K', end='')
        print("[Console] " + text[:-1])
        beacon = send_tnc(text[:-1], 0)
        ser.write(beacon)
        ser.readline()

async def ainput(string: str) -> str:
    await asyncio.get_event_loop().run_in_executor(
            None, lambda s=string: sys.stdout.write(s+' '))
    return await asyncio.get_event_loop().run_in_executor(
            None, sys.stdin.readline)

async def cleaner():
    while True:
        await asyncio.sleep(60 * BEACONDELAY)
        gc.collect()
        beacon = send_tnc('NodePacket version 1.1\r', 0)
        ser.write(beacon)
        ser.readline()

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
    print('\33[33mSetting TNC in hostmode...\33[0m')
    ser.readline()

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

def init_tncConfig():
    global ACTCHANNELS
    ACTCHANNELS = {}
    for x in range(1, 18):
        if x == 2:
            ACTCHANNELS[0] = config.get('tncinit', '2')[2:]
        if x == 3:
            all_bytes = send_init_tnc(config.get('tncinit', str(x)),0,1)
            ser.write(all_bytes)
            ser.readline()
            # Set Callsign I for every channel Y
            callsign_str = config.get('tncinit', '17')
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
                ACTCHANNELS[x] = tmp
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
            all_bytes = send_init_tnc(config.get('tncinit', str(x)),0,1)
            ser.write(all_bytes)
            ser.readline()
    print('\33[1;33mTNC Active and listening...\33[0m')
    beacon = send_tnc('NodePacket version 1.1\r', 0)
    ser.write(beacon)
    ser.readline()

async def go_serial():
    # serial port stuff here
    global polling
    global ACTIVECHAN
    polling = 1
    while True:
        for x in range(int(channels[2:])):
            if polling == 1:
                ser.write(b'\xff\x01\x00G')
                polling_data = ser.readline()
                # print('IS 0000 > ' + polling_data.hex())
            if polling_data.hex() != 'ff0100':
                # print("stop polling")
                polling = 0
                chan_i = int(polling_data.hex()[4:6],16) - 1
                poll_byte = num2byte(chan_i) # bytearray.fromhex('%02d' % (chan_i,))
                ser.write(poll_byte + b'\x01\x00G')
                data = ser.readline()
                if data == '':
                    polling = 1
                    break
                # print('IS 0000 > ' + data.hex())
                data_int = int(data.hex()[2:4], 16)
                namechan = '[Monitor]'
                if chan_i != 0:
                    namechan = '[Chan %02d]' % (chan_i,)

                if data_int == 0:
                    # print("Status : Succes with NoInfo")
                    # print(namechan + " \33[37m" + data.decode() + "\33[0m")
                    polling = 1
                elif data_int == 1:
                    # print("Succes with Messages")
                    print(namechan + " \33[1;32m" + data.decode() + "\33[0m")
                    await sendmsg(chan_i,'cmd1',"OK:" + data.decode()[2:])
                elif data_int == 2:
                    # print("Failure with Messages")
                    print(namechan + " \33[1;31m" + data.decode() + "\33[0m")
                    await sendmsg(chan_i,'cmd2',"Error:" + data.decode()[2:])
                elif data_int == 3:
                    # print("Link Status")
                    print(namechan + " \33[0;37m" + data.decode()[2:] + "\33[0m")
                    await sendmsg(chan_i,'chat',data.decode()[2:])
                elif data_int == 4:
                    # print("Monitor Header NoInfo")
                    print(namechan + " \33[1;37m" + data.decode()[2:] + "\33[0m")
                    await sendmsg(chan_i,'cmd4',data.decode()[2:])
                elif data_int == 5:
                    # print("Monitor Header With Info")
                    print(namechan + " \33[1;37m" + data.decode()[2:] + "\33[0m")
                    #need check mheard if new or not and appent to msg *NEW*
                    await sendmsg(chan_i,'cmd5',data.decode()[2:-1])
                    callsign = data.decode()[2:].split()[1]
                elif data_int == 6:
                    data_decode = (codecs.decode(data, 'cp850')[3:])
                    data_out = data_decode.splitlines()
                    _print('\33[1;34m', end='')
                    for lines in data_out:
                        _print('                     ' + lines)
                        await sendmsg(chan_i,'warn',lines)
                    _print('\33[0m', end='')
                    #locator = re.findall(r'[A-R]{2}[0-9]{2}[A-Z]{2}', data_decode.upper())
                    # if locator == []:
                    #     logheard(callsign, 6, '')
                    # else:
                    #     logheard(callsign, 6, locator[0])
                elif data_int == 7:
                    # print("Connect information")
                    # This should not be on monitor
                    data_decode = (codecs.decode(data, 'cp850')[3:])
                    data_out = data_decode.splitlines()
                    _print('\33[1;30m', end='')
                    for lines in data_out:
                        _print('                     ' + lines)
                        await sendmsg(chan_i,'chat',lines)
                    _print('\33[0m', end='')
                else:
                    print("No data")
                    # pass
            x = x + 1
            await asyncio.sleep(0.016)
        else:
            x = 0;
            # polling = 1
            chan_i = int(ACTIVECHAN.hex(), 16)
            ser.write(ACTIVECHAN + b'\x01\x01\x40\x42')
            tmp = ser.readline()[2:-1].decode()
            await sendmsg(chan_i,'cmd1','@B:' + tmp)
            await asyncio.sleep(0.016)
            ser.write(ACTIVECHAN + b'\x01\x00\x4C')
            tmp = ser.readline()[2:-1].decode()
            await sendmsg(chan_i,'cmd1','L:' + tmp)
            tmp = int(psutil.Process(os.getpid()).memory_info().rss)
            await sendmsg(chan_i,'cmd1','@MEM:' + str(tmp))

if __name__ == "__main__":
    os.system("")
    print("\33[1;34m  _   _           _     ______          _        _      ")
    print(" | \\ | |         | |    | ___ \\        | |      | |     ")
    print(" |  \\| | ___   __| | ___| |_/ /_ _  ___| | _____| |_    ")
    print(" | . ` |/ _ \\ / _` |/ _ \\  __/ _` |/ __| |/ / _ \\ __|   ")
    print(" | |\\  | (_) | (_| |  __/ | | (_| | (__|   <  __/ |_    ")
    print(" \\_| \\_/\\___/ \\__,_|\\___\\_|  \\__,_|\\___|_|\\_\\___|\\__|   ")
    print("\33[1;32m  An open source Python WS Packet server V1.1ß          ")
    print("\33[1;32m  For WA8DED Modems that support HostMode               \33[0m\n")

    # Replacing the pring function to always add time
    _print = print # keep a local copy of the original print
    builtins.print = lambda *args, **kwargs: _print("\r\33[K\33[1;30m[" + time.strftime("%H:%M:%S", time.localtime()) + "]", *args, **kwargs)

    handler = functools.partial(process_request, os.getcwd() + os.path.sep + 'www')
    start_server = websockets.serve(mysocket, '0.0.0.0', MYPORT, process_request=handler, ping_interval=None)
    print("\33[1;33mStarting up HTTP server at http://localhost:%d/ \33[0m " % MYPORT)
    print("\33[1;33mWeb server files home folder set to " + os.getcwd() + os.path.sep + "www\33[0m")

    init_tncinWa8ded()
    init_tncConfig()

    try:
        loop = asyncio.get_event_loop()
        asyncio.ensure_future(go_serial())

        loop.run_until_complete(start_server)
        loop.create_task(main())
        loop.create_task(cleaner())
        loop.run_forever()
    except KeyboardInterrupt:
        print("\33[1;33mPut TNC in Un-attended mode...\33[0m")
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
        print("\33[1;31m " + repr(e) + "\33[0m")
