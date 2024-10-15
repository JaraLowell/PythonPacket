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
import math
from unidecode import unidecode
import configparser
import pickle
import html

def num2byte(number):
    return bytearray.fromhex("{0:#0{1}x}".format(number,4)[2:])

config = configparser.ConfigParser()
config.read('./config.ini')

LoraDB    = {}
LoraDBPath = 'LoraDB.pkl'

MapMarkers = {}

MyLora = ''
MyPath = os.getcwd() + os.path.sep + 'txtfiles' + os.path.sep
mylorachan = {}
tlast = int(time.time())
today_date = date.today()
time_now = datetime.now()

if os.path.exists(LoraDBPath):
    with open(LoraDBPath, 'rb') as f:
        LoraDB = pickle.load(f)

# Function to insert colored text
def insert_colored_text(text_widget, text, color):
    text_widget.tag_configure(color, foreground=color)
    text_widget.insert(tk.END, text, color)
    text_widget.see(tk.END)

#----------------------------------------------------------- Meshtastic Lora Con ------------------------------------------------------------------------
import meshtastic.tcp_interface
import meshtastic.serial_interface
import base64
import yaml
from pubsub import pub
meshtastic_client = None
lora_lastmsg = ''
map_delete = int(config.get('meshtastic', 'mep_delete_time'))

try:
    from meshtastic.protobuf import config_pb2
except ImportError:
    from meshtastic import config_pb2

def value_to_graph(value, min_value=-19, max_value=1, graph_length=12):
    value = max(min_value, min(max_value, value))
    position = int((value - min_value) / (max_value - min_value) * (graph_length - 1))
    position0 = int((0 - min_value) / (max_value - min_value) * (graph_length - 1))
    graph = ['─'] * graph_length
    graph[position0] = '┴'
    graph[position] = '╥'
    return '└' + ''.join(graph) + '┘'

def connect_meshtastic(force_connect=False):
    global meshtastic_client, MyLora
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
    insert_colored_text(text_box1, "[" + time.strftime("%H:%M:%S", time.localtime()) + "] Connecting to meshtastic on " + cnto + "...\n", "#c24400")
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
    insert_colored_text(text_box1, "[" + time.strftime("%H:%M:%S", time.localtime()) + "] Connected to " + nodeInfo['user']['id'] + " > "  + nodeInfo['user']['shortName'] + " / " + nodeInfo['user']['longName'] + " using a " + nodeInfo['user']['hwModel'] + "\n", "#c24400")

    MyLora = (nodeInfo['user']['id'])[1:]
    logLora((nodeInfo['user']['id'])[1:], ['NODEINFO_APP', nodeInfo['user']['shortName'], nodeInfo['user']['longName'], nodeInfo['user']["macaddr"],nodeInfo['user']['hwModel']])
    # Lets get the Local Node's channels
    nodeInfo = meshtastic_client.getNode('^local')
    lora_config = nodeInfo.localConfig.lora
    modem_preset_enum = lora_config.modem_preset
    modem_preset_string = config_pb2._CONFIG_LORACONFIG_MODEMPRESET.values_by_number[modem_preset_enum].name
    channels = nodeInfo.channels
    if channels:
        for channel in channels:
            psk_base64 = base64.b64encode(channel.settings.psk).decode('utf-8')
            
            if channel.settings.name == '':
                mylorachan[channel.index] = str(channel.index)
            else:
                mylorachan[channel.index] = unidecode(channel.settings.name)
            
            if channel.index == 0 and mylorachan[channel.index] == '0':
                mylorachan[channel.index] = modem_preset_string

            if channel.index == 0:
                insert_colored_text(text_box1, "[" + time.strftime("%H:%M:%S", time.localtime()) + "] Lora Chat Channel 0 = " + mylorachan[0] + " using Key " + psk_base64 + "\n", "#c24400")
                padding_frame.config(text="Send a message to channel " + mylorachan[0])

    updatesnodes()

    pub.subscribe(on_meshtastic_message, "meshtastic.receive", loop=asyncio.get_event_loop())
    pub.subscribe(on_meshtastic_connection, "meshtastic.connection.established")
    pub.subscribe(on_lost_meshtastic_connection,"meshtastic.connection.lost")

    return meshtastic_client

def on_lost_meshtastic_connection(interface):
    print("[LoraNet] Lost connection. Reconnecting...")
    insert_colored_text(text_box1, "[" + time.strftime("%H:%M:%S", time.localtime()) + "] Lost connection. Reconnecting...\n", "#c24400")
    connect_meshtastic(force_connect=True)

def on_meshtastic_connection(interface, topic=pub.AUTO_TOPIC):
    # called when we (re)connect to the radio
    # defaults to broadcast, specify a destination ID if you wish
    # interface.sendText("hello mesh")
    insert_colored_text(text_box1, "[" + time.strftime("%H:%M:%S", time.localtime()) + "] Connection Made...\n", "#c24400")
    print("[LoraNet] Connection Made...")

def logLora(nodeID, info):
    tnow = int(time.time())
    if nodeID in LoraDB:
        LoraDB[nodeID][0] = tnow # time last seen
    else:
        LoraDB[nodeID] = [tnow, '', '', 81.0, 186.0, 0, '', '', tnow, '', '', '',-1]
        insert_colored_text(text_box3, "[" + time.strftime("%H:%M:%S", time.localtime()) + "] New Node Logged ! #" + nodeID + "\n", "#c24400")

    if info[0] == 'NODEINFO_APP':
        tmp = str(info[1].encode('ascii', 'xmlcharrefreplace'), 'ascii').replace("\n", "") # short name
        if tmp != '':
            LoraDB[nodeID][1] = tmp
        else:
            LoraDB[nodeID][1] = nodeID[-4:]
        tmp = str(info[2].encode('ascii', 'xmlcharrefreplace'), 'ascii').replace("\n", "") # long name
        if tmp != '':
            LoraDB[nodeID][2] = tmp
        else:
            LoraDB[nodeID][2] = '!' + nodeID
        LoraDB[nodeID][6] = info[3] # mac adress
        LoraDB[nodeID][7] = info[4] # hardware
    elif info[0] == 'POSITION_APP':
        LoraDB[nodeID][3] = info[1] # latitude
        LoraDB[nodeID][4] = info[2] # longitude
        LoraDB[nodeID][5] = info[3] # altitude
        LoraDB[nodeID][9] = LatLon2qth(info[1],info[2])
    
def on_meshtastic_message(packet, interface, loop=None):
    # loop=None
    try:
        #print(yaml.dump(packet))
        global lora_lastmsg
        global tlast
        donoting = True
        ischat = False
        if "decoded" in packet:
            data = packet["decoded"]
            text_from = ''
            if "fromId" in packet and packet["fromId"] is not None:
                text_from  = packet["fromId"][1:]
                text_mqtt = ''
                text_msgs = ''
                fromraw = text_from
                tnow = int(time.time())
                if text_from in LoraDB:
                    LoraDB[text_from][0] = tnow
                    if LoraDB[text_from][1] != '':
                        text_from = LoraDB[text_from][1] + " (" + LoraDB[text_from][2] + ")"
                else:
                    LoraDB[text_from] = [tnow, '', '', 81.0, 186.0, 0, '', '', tnow, '', '', '', -1]
                    insert_colored_text(text_box3, "[" + time.strftime("%H:%M:%S", time.localtime()) + "] New Node Logged ! #" + text_from + "\n", "#c24400")

                if "viaMqtt" in packet:
                    LoraDB[fromraw][10] = ' via mqtt'
                    text_mqtt = ' via mqtt'
                else:
                    LoraDB[fromraw][10] = ''
                    # if MyLora != fromraw: print(yaml.dump(packet))

                # Lets Work the Msgs
                if data["portnum"] == "TELEMETRY_APP":
                    if "deviceMetrics" in  data["telemetry"]:
                        text = data["telemetry"]["deviceMetrics"]
                        text_raws = ''
                        if "voltage" in text:
                            text_raws += 'Power: ' + str(round(text["voltage"],2)) + 'v '
                        if "batteryLevel" in text:
                            text_raws += 'Battery: ' + str(text["batteryLevel"]) + '% '
                        if "channelUtilization" in text:
                            text_raws += 'ChUtil: ' + str(round(text["channelUtilization"],2)) + '% '
                        if "airUtilTx" in text:
                            text_raws += 'AirUtilTX (DutyCycle): ' + str(round(text["airUtilTx"],2)) + '% '
                        if "uptimeSeconds" in text:
                            text_raws += '\n' + (' ' * 11) + 'Uptime ' + ez_date(text["uptimeSeconds"])
                        if text_raws != '':
                            text_raws = 'Node Telemetry\n' + (' ' * 11) + text_raws
                        else:
                            text_raws = 'Node Telemetry'
                    else:
                        text_raws = 'Node Telemetry'
                    donoting = False
                elif data["portnum"] == "CHAT_APP":
                    text = data["chat"]
                    if "text" in text:
                        text_msgs = str(text["text"].encode('ascii', 'xmlcharrefreplace'), 'ascii').rstrip()
                        text_raws = text["text"]
                        text_chns = 'Private'
                        if "toId" in packet:
                            if packet["toId"] == '^all':
                                text_chns = text_chns = str(mylorachan[0].encode('ascii', 'xmlcharrefreplace'), 'ascii')

                        if "channel" in packet:
                            text_chns = str(mylorachan[packet["channel"]].encode('ascii', 'xmlcharrefreplace'), 'ascii')

                        ischat = True
                    else:
                        text_raws = 'Node Chat Encrypted'
                    donoting = False
                elif data["portnum"] == "POSITION_APP":
                    text = data["position"]
                    if "altitude" in text:
                        text_msgs = "Node Position "
                        if "latitude" in text:
                            text_msgs += "latitude " + str(round(text["latitude"],4)) + " "
                        if "longitude" in text:
                            text_msgs += "longitude " + str(round(text["longitude"],4)) + " "
                        '''
                        if "latitude" in text and "longitude" in text:
                            qth = LatLon2qth(round(text["latitude"],6), round(text["longitude"],6))
                            text_msgs += "(" + qth + ") "
                        '''
                        if "altitude" in text:
                            text_msgs += "altitude " + str(text["altitude"]) + " meter"
                        if "satsInView" in text:
                            text_msgs += " (" + str(text["satsInView"]) + " satelites)"

                        if("latitude" in text and "longitude" in text and LoraDB[MyLora][3] != 81.0 and LoraDB[MyLora][3] != 186.0 and MyLora != fromraw):
                            text_msgs += "\n" + (' ' * 11) + "Distance: " + calc_gc(text["latitude"], text["longitude"], LoraDB[MyLora][3], LoraDB[MyLora][4])
                            if fromraw in MapMarkers:
                                MapMarkers[fromraw][0].set_position(round(text["latitude"],6), round(text["longitude"],6))
                                MapMarkers[fromraw][0].set_text(LoraDB[fromraw][1])
                        text_raws = text_msgs
                        logLora(packet["fromId"][1:], ['POSITION_APP', text["latitude"], text["longitude"], text["altitude"]])
                    else:
                        text_raws = 'Node Position'
                    donoting = False
                elif data["portnum"] == "NODEINFO_APP":
                    text = data["user"]
                    if "shortName" in text:
                        lora_sn = str(text["shortName"].encode('ascii', 'xmlcharrefreplace'), 'ascii')
                        lora_ln = str(text["longName"].encode('ascii', 'xmlcharrefreplace'), 'ascii')
                        lora_mc = text["macaddr"]
                        lora_mo = text["hwModel"]
                        logLora(packet["fromId"][1:], ['NODEINFO_APP', lora_sn, lora_ln, lora_mc, lora_mo])
                        if fromraw in MapMarkers:
                            MapMarkers[fromraw][0].set_text(html.unescape(lora_sn))
                        text_raws = "Node Info using hardware " + lora_mo
                        text_from = LoraDB[packet["fromId"][1:]][1] + " (" + LoraDB[packet["fromId"][1:]][2] + ")"
                    else:
                        text_raws = 'Node Info'
                    donoting = False
                elif data["portnum"] == "TEXT_MESSAGE_APP" and "text" in data:
                    text_msgs = str(data["text"].encode('ascii', 'xmlcharrefreplace'), 'ascii').rstrip()
                    text_raws = data["text"]
                    text_chns = 'Private'
                    if "toId" in packet:
                        if packet["toId"] == '^all':
                            text_chns = str(mylorachan[0].encode('ascii', 'xmlcharrefreplace'), 'ascii')

                    if "channel" in packet:
                        text_chns = str(mylorachan[packet["channel"]].encode('ascii', 'xmlcharrefreplace'), 'ascii')

                    ischat = True
                    donoting = False
                elif data["portnum"] == "NEIGHBORINFO_APP":
                    text_raws = 'Node Neighborinfo'
                    if "neighborinfo" in data and "neighbors" in data["neighborinfo"]:
                        text = data["neighborinfo"]["neighbors"]
                        for neighbor in text:
                            nodeid = hex(neighbor["nodeId"])[2:]
                            if nodeid in LoraDB and LoraDB[nodeid][1] != '':
                                nodeid = LoraDB[nodeid][1]
                            else:
                                nodeid = '!' + nodeid
                            text_raws += '\n' + (' ' * 11) + nodeid
                            if "snr" in neighbor:
                                text_raws += ' (' + str(neighbor["snr"]) + 'dB)'
                    donoting = False
                else:
                    text_raws = 'Node ' + (data["portnum"].split('_APP', 1)[0]).title()
                    if MyLora != fromraw:
                        donoting = False

                # Cleanup and get ready to print
                if data["portnum"] != "POSITION_APP" and data["portnum"] != "TEXT_MESSAGE_APP":
                    logLora(packet["fromId"][1:],['UPDATETIME'])

                if "snr" in packet and packet['snr'] is not None:
                    LoraDB[fromraw][11] = str(packet['snr']) + 'dB'

                if "rxSnr" in packet and packet['rxSnr'] is not None:
                    LoraDB[fromraw][11] = str(packet['rxSnr']) + 'dB'

                # Lets work the map
                if fromraw in MapMarkers:
                    MapMarkers[fromraw][2] = tnow
                    if "viaMqtt" in packet and MapMarkers[fromraw][1] == False:
                        MapMarkers[fromraw][1] = True
                        MapMarkers[fromraw][0].change_icon(tk_mqtt)
                    elif "viaMqtt" not in packet and MapMarkers[fromraw][1] == True:
                        MapMarkers[fromraw][0].change_icon(tk_direct)
                        MapMarkers[fromraw][1] = False
                elif LoraDB[fromraw][3] != 81.0 and LoraDB[fromraw][4] != 186.0 and "viaMqtt" in packet:
                    MapMarkers[fromraw] = ['', True, tnow]
                    MapMarkers[fromraw][0] = map.set_marker(round(LoraDB[fromraw][3],6), round(LoraDB[fromraw][4],6), text=html.unescape(LoraDB[fromraw][1]), icon = tk_mqtt, text_color = '#02bae8', font = ('Fixedsys', 8))
                elif LoraDB[fromraw][3] != 81.0 and LoraDB[fromraw][4] != 186.0 and "viaMqtt" not in packet:
                    MapMarkers[fromraw] = ['', False, tnow]
                    MapMarkers[fromraw][0] = map.set_marker(round(LoraDB[fromraw][3],6), round(LoraDB[fromraw][4],6), text=html.unescape(LoraDB[fromraw][1]), icon = tk_direct, text_color = '#02bae8', font = ('Fixedsys', 8))

                if donoting == False and text_raws != '' and MyLora != fromraw:
                    print("[LoraNet]\33[0;37m " + text_from + LoraDB[fromraw][10] + "\33[0m")
                    insert_colored_text(text_box1, '[' + time.strftime("%H:%M:%S", time.localtime()) + '] ' + html.unescape(text_from) + ' [' + html.unescape(fromraw) + ']' + LoraDB[fromraw][10] + "\n", "#d1d1d1")
                    if ischat == True:
                        insert_colored_text(text_box3, "[" + time.strftime("%H:%M:%S", time.localtime()) + "] " + html.unescape(text_from) + LoraDB[fromraw][10] + "\n", "#d1d1d1")
                    if "viaMqtt" in packet:
                        # _print('\33[0;32m' + (' ' * 21) + text_raws + '\33[0m')
                        insert_colored_text(text_box1, (' ' * 11) + html.unescape(text_raws) + '\n', "#c9a500")
                        if ischat == True:
                            insert_colored_text(text_box3, (' ' * 11) + '[' + text_chns +'] ' + html.unescape(text_raws) + '\n', "#00c983")
                    else:
                        text_from = ''
                        if LoraDB[fromraw][12] > 0:
                            text_from = '\n' + (' ' * 11) + str(LoraDB[fromraw][12]) + ' hops '
                        if LoraDB[fromraw][11] != '' and MyLora != fromraw:
                            if text_from == '':
                                text_from = '\n' + (' ' * 11)
                            v = float(LoraDB[fromraw][11].replace('dB', ''))
                            text_from += f"{round(v,1)}dB {value_to_graph(v)}"

                        # _print('\33[0;33m' + (' ' * 21) + text_raws + text_from + '\33[0m')
                        insert_colored_text(text_box1, (' ' * 11) + text_raws + text_from + '\n', "#00c983")
                        if ischat == True:
                            insert_colored_text(text_box3, (' ' * 11) + '[' + text_chns +'] ' + html.unescape(text_raws) + '\n', "#02bae8")
                elif donoting == False and text_raws != '' and MyLora == fromraw:
                    insert_colored_text(text_box2, "[" + time.strftime("%H:%M:%S", time.localtime()) + '] ' + html.unescape(text_from) + LoraDB[fromraw][10] + "\n", "#d1d1d1")
                    insert_colored_text(text_box2, (' ' * 11) + html.unescape(text_raws) + '\n', "#00c983")
        tnow = int(time.time())
        if tnow > tlast + 900:
            tlast = tnow
            with open(LoraDBPath, 'wb') as f:
                pickle.dump(LoraDB, f)
            print('Saved Databases')

            for nodeID in list(MapMarkers.keys()):
                if MapMarkers[nodeID][2] < tnow - map_delete:
                    print("[LoraNet] \33[1;31m" + nodeID + " removed from map\33[0m")
                    MapMarkers[nodeID][0].delete()
                    del MapMarkers[nodeID]

            gc.collect()
    except Exception as e:
        print("[LoraNet] \33[1;31m" + repr(e))

def updatesnodes():
    info = ''
    itmp = 0
    for nodes, info in meshtastic_client.nodes.items():
        if "user" in info:
            tmp = info['user']
            if "id" in tmp:
                # Only push to DB if we actually get a node ID
                nodeID = str(tmp['id'])[1:]
                nodeLast = 0
                itmp = itmp + 1

                if "lastHeard" in info and info["lastHeard"] is not None: nodeLast = info['lastHeard']

                if nodeID in LoraDB:
                    LoraDB[nodeID][0] = nodeLast
                else:
                    LoraDB[nodeID] = [nodeLast, '', '', 81.0, 186.0, 0, '', '', nodeLast, '', '', '',-1]
                    insert_colored_text(text_box3, "[" + time.strftime("%H:%M:%S", time.localtime()) + "] New Node Logged ! #" + nodeID + "\n", "#c24400")

                if "shortName" in tmp: LoraDB[nodeID][1] = str(tmp['shortName'].encode('ascii', 'xmlcharrefreplace'), 'ascii').replace("\n", "")
                if "longName" in tmp: LoraDB[nodeID][2] = str(tmp['longName'].encode('ascii', 'xmlcharrefreplace'), 'ascii').replace("\n", "")
                if "macaddr" in tmp: LoraDB[nodeID][6] = str(tmp['macaddr'])
                if "hwModel" in tmp: LoraDB[nodeID][7] = str(tmp['hwModel'])
                if "hopsAway" in info: LoraDB[nodeID][12] = info['hopsAway']

                if "position" in info:
                    tmp2 = info['position']
                    if "latitude" in tmp2 and "longitude" in tmp2:
                        LoraDB[nodeID][3] = tmp2['latitude']
                        LoraDB[nodeID][4] = tmp2['longitude']
                        LoraDB[nodeID][9] = LatLon2qth(tmp2['latitude'],tmp2['longitude'])
                    if "altitude" in tmp:
                        LoraDB[nodeID][5] = tmp['altitude']
                    
                    if nodeID == MyLora:
                        MapMarkers[MyLora] = ['', False, nodeLast]
                        MapMarkers[MyLora][0] = map.set_marker(round(LoraDB[MyLora][3],6), round(LoraDB[MyLora][4],6), text=html.unescape(LoraDB[MyLora][1]), icon = tk_icon, text_color = '#00c983', font = ('Fixedsys', 8))
                        map.set_position(round(LoraDB[nodeID][3],6), round(LoraDB[nodeID][4],6))
                        map.set_zoom(11)
                        print("my lat logn set " + str(round(LoraDB[nodeID][3],6)) + " " + str(round(LoraDB[nodeID][4],6)))

                if "viaMqtt" in info: LoraDB[nodeID][10] = ' via mqtt'
                if "snr" in info and info['snr'] is not None: LoraDB[nodeID][11] = str(info['snr']) + 'dB'

#-------------------------------------------------------------- Side Functions ---------------------------------------------------------------------------

def ez_date(d):
    ts = d
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

def calc_gc(end_lat, end_long, start_lat, start_long):
    start_lat = math.radians(start_lat)
    start_long = math.radians(start_long)
    end_lat = math.radians(end_lat)
    end_long = math.radians(end_long)

    d_lat = math.fabs(start_lat - end_lat)
    d_long = math.fabs(start_long - end_long)

    EARTH_R = 6372.8

    y = ((math.sin(start_lat)*math.sin(end_lat)) + (math.cos(start_lat)*math.cos(end_lat)*math.cos(d_long)))

    x = math.sqrt((math.cos(end_lat)*math.sin(d_long))**2 + ( (math.cos(start_lat)*math.sin(end_lat)) - (math.sin(start_lat)*math.cos(end_lat)*math.cos(d_long)))**2)

    c = math.atan(x/y)

    return f"± {round(EARTH_R*c,1)} Km"

def is_hour_between(start, end):
    now = datetime.now().hour
    is_between = False
    is_between |= start <= now <= end
    is_between |= end < start and (start <= now or now <= end)
    return is_between

#---------------------------------------------------------------- Start Mains -----------------------------------------------------------------------------

if __name__ == "__main__":
    os.system("")

    # Replacing the pring function to always add time
    _print = print # keep a local copy of the original print
    builtins.print = lambda *args, **kwargs: _print("\r\33[K\33[1;30m[" + time.strftime("%H:%M:%S", time.localtime()) + "]", *args, **kwargs)

    isLora = True
    print("\33[0;33mLoading meshtastic plugin...")

    from PIL import Image, ImageTk
    import tkinter as tk
    import customtkinter
    from tkinter import scrolledtext
    from tkinter import ttk
    from tkintermapview import TkinterMapView

    def on_closing():
        with open(LoraDBPath, 'wb') as f:
            pickle.dump(LoraDB, f)
        print('Saved Databases')
        root.quit()
        sys.exit()

    # Initialize the main window
    
    def create_text(frame, row, column, frheight):
        # Create a frame with a black background to simulate padding color
        padding_frame = tk.Frame(frame, background="#121212", padx=2, pady=2)
        padding_frame.grid(row=row, column=column, rowspan=1, columnspan=1, padx=0, pady=0, sticky='nsew')
        
        # Configure grid layout for the padding frame
        padding_frame.grid_rowconfigure(0, weight=1)
        padding_frame.grid_columnconfigure(0, weight=1)
        
        # Create a text widget inside the frame
        text_area = tk.Text(padding_frame, wrap=tk.WORD, width=100, height=frheight, bg='#242424', fg='#dddddd', font=('Fixedsys', 10))
        text_area.grid(row=0, column=0, sticky='nsew')
        return text_area

    def send(event=None):
        text2send = my_msg.get().rstrip()
        if text2send != '':
            meshtastic_client.sendText(text2send)
            text_from = LoraDB[MyLora][1] + " (" + LoraDB[MyLora][2] + ")"
            insert_colored_text(text_box3, "[" + time.strftime("%H:%M:%S", time.localtime()) + "] " + html.unescape(text_from) + "\n", "#d1d1d1")
            insert_colored_text(text_box3, (' ' * 11) + '[' + str(mylorachan[0].encode('ascii', 'xmlcharrefreplace'), 'ascii') +'] ' + text2send + '\n', "#02bae8")
            my_msg.set("")

    root = customtkinter.CTk()
    root.title("Meshtastic Lora Logger")
    root.resizable(True, True)
    root.iconbitmap("mesh.ico")
    root.protocol('WM_DELETE_WINDOW', on_closing)

    my_msg = tk.StringVar()  # For the messages to be sent.
    my_msg.set("")
    my_label = tk.StringVar()
    my_label.set("Send a message to channel")

    frame = tk.Frame(root, borderwidth=0, highlightthickness=1, highlightcolor="#121212", highlightbackground="#121212")
    frame.grid(row=0, column=0, padx=2, pady=2, sticky='nsew')

    # Configure grid layout for the main frame
    frame.grid_rowconfigure(0, weight=1)
    frame.grid_rowconfigure(1, weight=1)
    frame.grid_rowconfigure(2, weight=1)
    frame.grid_rowconfigure(3, weight=0)
    frame.grid_columnconfigure(0, weight=0)
    frame.grid_columnconfigure(1, weight=1)

    # Configure grid layout for the root window
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)

    # Create three text boxes with padding color
    text_box1 = create_text(frame, 0, 0, 30)
    insert_colored_text(text_box1, "Meshtastic Lora Logger v 1.1 By Jara Lowell\n", "#02bae8")
    text_box2 = create_text(frame, 1, 0, 10)
    text_box3 = create_text(frame, 2, 0, 10)

    padding_frame = tk.LabelFrame(frame, background="#242424", padx=0, pady=4, text=my_label.get(), bg='#242424', fg='#999999', font=('Fixedsys', 10), borderwidth=0, highlightthickness=0, labelanchor='n')
    padding_frame.grid(row=4, column=0, rowspan=1, columnspan=1, padx=0, pady=0, sticky="nsew")
    padding_frame.grid_rowconfigure(1, weight=1)
    padding_frame.grid_columnconfigure(0, weight=1)

    text_box4 = tk.Entry(padding_frame, textvariable=my_msg, width=90, bg='#242424', fg='#eeeeee', font=('Fixedsys', 10))
    text_box4.grid(row=4, column=0)
    text_box4.bind("<Return>", send)

    frame_right = tk.Frame(frame, bg="#242424", borderwidth=0, highlightthickness=0, highlightcolor="#242424", highlightbackground="#242424", background="#242424", padx=2, pady=2)
    frame_right.grid(row=0, column=1, rowspan=5, columnspan=1, padx=0, pady=0, sticky='nsew')
    frame_right.grid_rowconfigure(0, weight=1)
    frame_right.grid_columnconfigure(0, weight=1)

    map = TkinterMapView(frame_right, padx=0, pady=0, bg_color='#121212')
    map.grid(row=0, column=0, sticky='nsew')

    map.set_position(48.860381, 2.338594)
    map.set_tile_server("http://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png")
    map.set_zoom(5)
    
    tk_icon = ImageTk.PhotoImage(Image.open("marker.png"))
    tk_direct = ImageTk.PhotoImage(Image.open("marker-green.png"))
    tk_mqtt = ImageTk.PhotoImage(Image.open("marker-orange.png"))

    root.meshtastic_interface = connect_meshtastic()

    try:
        root.mainloop()
    except KeyboardInterrupt:
        with open(LoraDBPath, 'wb') as f:
            pickle.dump(LoraDB, f)
        print('Saved Databases')
        sys.exit()
    except Exception as e:
        print("\33[0;31m " + repr(e) + "\33[1;37m\33[0m")