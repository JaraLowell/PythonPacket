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
from playsound import playsound

'''
Fix sub parts if they brake a main part install > pip install --upgrade setuptools <sub tool name>
Upgrade the Meshtastic Python Library           > pip install --upgrade meshtastic
Build the build                                 > pyinstaller --icon=mesh.ico -F --onefile --noconsole LoraLog.py
'''

def num2byte(number):
    return bytearray.fromhex("{0:#0{1}x}".format(number,4)[2:])

def has_pairs(lst):
    return len(lst) != 0 and len(lst) % 2 == 0

config = configparser.ConfigParser()
config.read('./config.ini')

LoraDB    = {}
LoraDBPath = 'LoraDB.pkl'

MapMarkers = {}

MyLora = ''
MyLoraText1 = ''
MyLoraText2 = ''
MyPath = os.getcwd() + os.path.sep + 'txtfiles' + os.path.sep
mylorachan = {}
tlast = int(time.time())
today_date = date.today()
time_now = datetime.now()

if os.path.exists(LoraDBPath):
    with open(LoraDBPath, 'rb') as f:
        LoraDB = pickle.load(f)

# Function to insert colored text
'''
def insert_colored_text(text_widget, text, color, center=False):
    text_widget.tag_configure(color, foreground=color)
    text_widget.insert(tk.END, text, color)
    if ".frame5" not in str(text_widget):
        text_widget.see(tk.END)
'''
def insert_colored_text(text_widget, text, color, center=False):
    text_widget.tag_configure(color, foreground=color)
    text_widget.insert(tk.END, text, color)
    if center:
        text_widget.tag_configure("center", justify='center')
        text_widget.tag_add("center", "1.0", "end")
    if ".frame5" not in str(text_widget):
        text_widget.see(tk.END)
#----------------------------------------------------------- Meshtastic Lora Con ------------------------------------------------------------------------
import meshtastic.tcp_interface
import meshtastic.serial_interface
import base64
# import yaml
from pubsub import pub
meshtastic_client = None
map_delete = int(config.get('meshtastic', 'map_delete_time')) * 60
map_oldnode = int(config.get('meshtastic', 'map_oldnode_time')) * 60

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
    retry_limit = 10
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
                time.sleep(attempts * 3)
            else:
                print("[LoraNet] Could not connect: {e}")
                return None

    nodeInfo = meshtastic_client.getMyNodeInfo()
    print("[LoraNet] Connected to " + nodeInfo['user']['id'] + " > "  + nodeInfo['user']['shortName'] + " / " + nodeInfo['user']['longName'] + " using a " + nodeInfo['user']['hwModel'])
    insert_colored_text(text_box1, "[" + time.strftime("%H:%M:%S", time.localtime()) + "] Connected to " + nodeInfo['user']['id'] + " > "  + nodeInfo['user']['shortName'] + " / " + nodeInfo['user']['longName'] + " using a " + nodeInfo['user']['hwModel'] + "\n", "#c24400")

    MyLora = (nodeInfo['user']['id'])[1:]
    root.wm_title("Meshtastic Lora Logger - " + html.unescape(LoraDB[MyLora][1]))

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
    global LoraDB
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

def on_meshtastic_message(packet, interface, loop=None):
    # print(yaml.dump(packet))
    global MyLora, MyLoraText1, MyLoraText2, LoraDB, MapMarkers
    ischat = False
    tnow = int(time.time())
    if "decoded" in packet:
        data = packet["decoded"]
        text_from = ''
        if "fromId" in packet and packet["fromId"] is not None:
            text_from  = packet["fromId"][1:]
            if text_from == '':
                #  mmm empty ID ? lets return
                return
            viaMqtt = False
            text_msgs = ''
            fromraw = text_from
            if text_from in LoraDB:
                LoraDB[text_from][0] = tnow
                if LoraDB[text_from][1] != '':
                    text_from = LoraDB[text_from][1] + " (" + LoraDB[text_from][2] + ")"
            else:
                LoraDB[text_from] = [tnow, '', '', 81.0, 186.0, 0, '', '', tnow, '', '', '', -1]
                insert_colored_text(text_box3, "[" + time.strftime("%H:%M:%S", time.localtime()) + "] New Node Logged ! #" + text_from + "\n", "#c24400")
                playsound('data/NewNode.mp3')

            if "viaMqtt" in packet:
                LoraDB[fromraw][10] = ' via mqtt'
                viaMqtt = True
            else:
                LoraDB[fromraw][10] = ''
                # if MyLora != fromraw: print(yaml.dump(packet))

            LoraDB[fromraw][12] = -1
            if "hopStart" in packet: LoraDB[fromraw][12] = packet['hopStart']

            # Lets Work the Msgs
            if data["portnum"] == "TELEMETRY_APP":
                text_raws = 'Node Telemetry'
                telemetry = packet['decoded'].get('telemetry', {})
                if telemetry:
                    device_metrics = telemetry.get('deviceMetrics', {})
                    if device_metrics:
                        LoraDB[fromraw][9] = ''
                        text_raws += '\n' + (' ' * 11) + 'Battery: ' + str(device_metrics.get('batteryLevel', 0)) + '% '
                        if device_metrics.get('batteryLevel', 0) < 101:
                            LoraDB[fromraw][9] = str(device_metrics.get('batteryLevel', 0)) + '% '
                        text_raws += 'Power: ' + str(round(device_metrics.get('voltage', 0.00),2)) + 'v '
                        LoraDB[fromraw][9] += str(round(device_metrics.get('voltage', 0.00),2)) + 'v'
                        text_raws += 'ChUtil: ' + str(round(device_metrics.get('channelUtilization', 0.00),2)) + '% '
                        text_raws += 'AirUtilTX (DutyCycle): ' + str(round(device_metrics.get('airUtilTx', 0.00),2)) + '%'
                        text_raws += '\n' + (' ' * 11) + 'Uptime ' + ez_date(device_metrics.get('uptimeSeconds', 0))
                        if MyLora == fromraw:
                            MyLoraText1 = (' ChUtil').ljust(13) + str(round(device_metrics.get('channelUtilization', 0.00),2)).rjust(6) + '%\n' + (' AirUtilTX').ljust(13) + str(round(device_metrics.get('airUtilTx', 0.00),2)).rjust(6) + '%\n' + (' Power').ljust(13) + str(round(device_metrics.get('voltage', 0.00),2)).rjust(6) + 'v\n' + (' Battery').ljust(13) + str(device_metrics.get('batteryLevel', 0)).rjust(6) + '%\n'
                    power_metrics = telemetry.get('powerMetrics', {})
                    if power_metrics:
                        text_raws += '\n' + (' ' * 11) + 'CH1 Voltage: ' + str(round(power_metrics.get('ch1_voltage', 'N/A'),2)) + 'v'
                        text_raws += ' CH1 Current: ' + str(round(power_metrics.get('ch1_current', 'N/A'),2)) + 'mA'
                        text_raws += ' CH2 Voltage: ' + str(round(power_metrics.get('ch2_voltage', 'N/A'),2)) + 'v'
                        text_raws += ' CH2 Current: ' + str(round(power_metrics.get('ch2_current', 'N/A'),2)) + 'mA'
                    environment_metrics = telemetry.get('environmentMetrics', {})
                    if environment_metrics:
                        text_raws += '\n' + (' ' * 11) + 'Temperature: ' + str(round(environment_metrics.get('temperature', 0.00),2)) + '°C'
                        text_raws += ' Humidity: ' + str(round(environment_metrics.get('relativeHumidity', 0.00),2)) + '%'
                        text_raws += ' Pressure: ' + str(round(environment_metrics.get('barometricPressure', 0.00),2)) + 'hPa'
                    localstats_metrics = telemetry.get('localStats', {})
                    if localstats_metrics:
                        text_raws += '\n' + (' ' * 11) + 'PacketsTx: ' + str(localstats_metrics.get('numPacketsTx', 0))
                        text_raws += ' PacketsRx: ' + str(localstats_metrics.get('numPacketsRx', 0))
                        text_raws += ' PacketsRxBad: ' + str(localstats_metrics.get('numPacketsRxBad', 0))
                        text_raws += ' Nodes: ' + str(localstats_metrics.get('numOnlineNodes', 0)) + '/' + str(localstats_metrics.get('numTotalNodes', 0))
                        if MyLora == fromraw:
                            MyLoraText2 = (' PacketsTx').ljust(13) + str(localstats_metrics.get('numPacketsTx', 0)).rjust(7) + '\n' + (' PacketsRx').ljust(13) + str(localstats_metrics.get('numPacketsRx', 0)).rjust(7) + '\n' + (' Rx Bad').ljust(13) + str(localstats_metrics.get('numPacketsRxBad', 0)).rjust(7) + '\n' + (' Nodes').ljust(13) + str(localstats_metrics.get('numOnlineNodes', 0)).rjust(7) + '\n'
                if text_raws == 'Node Telemetry':
                    text_raws += '\n' + (' ' * 11) + 'No Data'
            elif data["portnum"] == "CHAT_APP":
                text = data["chat"]
                if "text" in text:
                    text_msgs = str(text["text"].encode('ascii', 'xmlcharrefreplace'), 'ascii').rstrip()
                    text_raws = text["text"]
                    text_chns = 'Private'
                    if "toId" in packet:
                        if packet["toId"] == '^all':
                            text_chns = text_chns = str(mylorachan[0])

                    if "channel" in packet:
                        text_chns = str(mylorachan[packet["channel"]])

                    ischat = True
                    playsound('data/NewChat.mp3')
                else:
                    text_raws = 'Node Chat Encrypted'
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
                        text_msgs += "\n" + (' ' * 11) + "Distance: ±" + calc_gc(text["latitude"], text["longitude"], LoraDB[MyLora][3], LoraDB[MyLora][4])
                        if fromraw in MapMarkers:
                            MapMarkers[fromraw][0].set_position(round(text["latitude"],6), round(text["longitude"],6))
                            MapMarkers[fromraw][0].set_text(LoraDB[fromraw][1])
                    text_raws = text_msgs
                    logLora(packet["fromId"][1:], ['POSITION_APP', text["latitude"], text["longitude"], text["altitude"]])
                else:
                    text_raws = 'Node Position'
            elif data["portnum"] == "NODEINFO_APP":
                text = data["user"]
                if "shortName" in text:
                    lora_sn = str(text["shortName"].encode('ascii', 'xmlcharrefreplace'), 'ascii')
                    lora_ln = str(text["longName"].encode('ascii', 'xmlcharrefreplace'), 'ascii')
                    lora_mc = text["macaddr"]
                    lora_mo = text["hwModel"]
                    if lora_sn in lora_ln and "Meshtastic" in lora_ln:
                        if LoraDB[fromraw][1] == '': lora_sn = LoraDB[fromraw][1]
                        if LoraDB[fromraw][2] == '': lora_ln = LoraDB[fromraw][2]
                    logLora(packet["fromId"][1:], ['NODEINFO_APP', lora_sn, lora_ln, lora_mc, lora_mo])
                    if fromraw in MapMarkers:
                        MapMarkers[fromraw][0].set_text(html.unescape(lora_sn))
                    text_raws = "Node Info using hardware " + lora_mo
                    if "isLicensed" in text and text["isLicensed"] == True:
                        text_raws += " (Licensed)"
                    if 'role' in text:
                        text_raws +=  " Role: " + text["role"]

                    text_from = lora_sn + " (" + lora_ln + ")"
                else:
                    text_raws = 'Node Info No Data'
            elif data["portnum"] == "TEXT_MESSAGE_APP" and "text" in data:
                text_msgs = str(data["text"].encode('ascii', 'xmlcharrefreplace'), 'ascii').rstrip()
                text_raws = data["text"]
                text_chns = 'Private'
                if "toId" in packet:
                    if packet["toId"] == '^all':
                        text_chns = str(mylorachan[0])

                if "channel" in packet:
                    text_chns = str(mylorachan[packet["channel"]])

                ischat = True
                playsound('data/NewChat.mp3')
            elif data["portnum"] == "NEIGHBORINFO_APP":
                text_raws = 'Node Neighborinfo'
                listmaps = []
                if fromraw not in MapMarkers and fromraw in LoraDB:
                    MapMarkers[fromraw] = [None, True, tnow, None]
                    MapMarkers[fromraw][0] = map.set_marker(round(LoraDB[fromraw][3],6), round(LoraDB[fromraw][4],6), text=html.unescape(LoraDB[fromraw][1]), icon = tk_mqtt, text_color = '#02bae8', font = ('Fixedsys', 8), data=fromraw, command = click_command)

                if fromraw in MapMarkers:
                    if len(MapMarkers[fromraw]) > 3 and MapMarkers[fromraw][3] is not None:
                        MapMarkers[fromraw][3].delete()
                        MapMarkers[fromraw][3] = None

                if "neighborinfo" in data and "neighbors" in data["neighborinfo"]:
                    text = data["neighborinfo"]["neighbors"]
                    for neighbor in text:
                        nodeid = hex(neighbor["nodeId"])[2:]
                        if nodeid in LoraDB and LoraDB[nodeid][1] != '':
                            LoraDB[nodeid][0] = tnow
                            # Lets add to map ass well if we are not on map abd our db knows the station
                            if nodeid not in MapMarkers:
                                MapMarkers[nodeid] = [None, True, tnow, None]
                                MapMarkers[nodeid][0] = map.set_marker(round(LoraDB[nodeid][3],6), round(LoraDB[nodeid][4],6), text=html.unescape(LoraDB[nodeid][1]), icon = tk_mqtt, text_color = '#02bae8', font = ('Fixedsys', 8), data=nodeid, command = click_command)
                            else:
                                MapMarkers[nodeid][2] = tnow
                            # Lets add to paths ass well if we are on map
                            if fromraw in MapMarkers:
                                pos = ( round(LoraDB[fromraw][3],6), round(LoraDB[fromraw][4],6) )
                                listmaps.append(pos)
                                pos = ( round(LoraDB[nodeid][3],6) , round(LoraDB[nodeid][4],6) )
                                listmaps.append(pos)
                            nodeid = LoraDB[nodeid][1]
                        else:
                            nodeid = '!' + nodeid
                        text_raws += '\n' + (' ' * 11) + nodeid
                        if "snr" in neighbor:
                            text_raws += ' (' + str(neighbor["snr"]) + 'dB)'
                    # Add Paths if we have any
                    if fromraw in MapMarkers and has_pairs(listmaps):
                        try:
                            # How can MapMarkers[fromraw][3] cause a IndexError: list index out of range
                            if len(MapMarkers[fromraw]) > 3 and MapMarkers[fromraw][3] is None:
                                MapMarkers[fromraw][3] = map.set_path(listmaps, color="#006642", width=2)
                        except Exception as e:
                            print("\33[0;31m " + repr(e) + "\33[1;37m\33[0m") 
            else:
                text_raws = 'Node ' + (data["portnum"].split('_APP', 1)[0]).title()

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
                if viaMqtt == True and MapMarkers[fromraw][1] == False:
                    MapMarkers[fromraw][1] = True
                    MapMarkers[fromraw][0].change_icon(tk_mqtt)
                elif viaMqtt == False and MapMarkers[fromraw][1] == True:
                    MapMarkers[fromraw][1] = False
                    MapMarkers[fromraw][0].change_icon(tk_direct)
            elif LoraDB[fromraw][3] != 81.0 and LoraDB[fromraw][4] != 186.0 and viaMqtt == True:
                MapMarkers[fromraw] = [None, True, tnow, None]
                MapMarkers[fromraw][0] = map.set_marker(round(LoraDB[fromraw][3],6), round(LoraDB[fromraw][4],6), text=html.unescape(LoraDB[fromraw][1]), icon = tk_mqtt, text_color = '#02bae8', font = ('Fixedsys', 8), data=fromraw, command = click_command)
                MapMarkers[fromraw][0].text_color = '#02bae8'
            elif LoraDB[fromraw][3] != 81.0 and LoraDB[fromraw][4] != 186.0 and viaMqtt == False:
                MapMarkers[fromraw] = [None, False, tnow, None]
                MapMarkers[fromraw][0] = map.set_marker(round(LoraDB[fromraw][3],6), round(LoraDB[fromraw][4],6), text=html.unescape(LoraDB[fromraw][1]), icon = tk_direct, text_color = '#02bae8', font = ('Fixedsys', 8), data=fromraw, command = click_command)
                MapMarkers[fromraw][0].text_color = '#02bae8'

            text_from = html.unescape(text_from)
            text_raws = html.unescape(text_raws)

            if text_raws != '' and MyLora != fromraw:
                print("[LoraNet]\33[0;37m " + text_from + LoraDB[fromraw][10] + "\33[0m")
                insert_colored_text(text_box1, '[' + time.strftime("%H:%M:%S", time.localtime()) + '] ' + text_from + ' [' + fromraw + ']' + LoraDB[fromraw][10] + "\n", "#d1d1d1")
                if ischat == True:
                    insert_colored_text(text_box3, "[" + time.strftime("%H:%M:%S", time.localtime()) + "] " + text_from + LoraDB[fromraw][10] + "\n", "#d1d1d1")
                if viaMqtt == True:
                    insert_colored_text(text_box1, (' ' * 11) + text_raws + '\n', "#c9a500")
                    if ischat == True:
                        insert_colored_text(text_box3, (' ' * 11) + '[' + text_chns +'] ' + text_raws + '\n', "#00c983")
                else:
                    text_from = ''
                    if LoraDB[fromraw][12] > 0:
                        text_from = '\n' + (' ' * 11) + str(LoraDB[fromraw][12]) + ' hops '
                    if LoraDB[fromraw][11] != '' and MyLora != fromraw:
                        if text_from == '':
                            text_from = '\n' + (' ' * 11)
                        v = float(LoraDB[fromraw][11].replace('dB', ''))
                        text_from += f"{round(v,1)}dB {value_to_graph(v)}"

                    insert_colored_text(text_box1, (' ' * 11) + text_raws + text_from + '\n', "#00c983")
                    if ischat == True:
                        insert_colored_text(text_box3, (' ' * 11) + '[' + text_chns +'] ' + text_raws + '\n', "#02bae8")
            elif text_raws != '' and MyLora == fromraw:
                print("[LoraNet]\33[0;37m " + text_from + LoraDB[fromraw][10] + "\33[0m")
                insert_colored_text(text_box2, "[" + time.strftime("%H:%M:%S", time.localtime()) + '] ' + text_from + LoraDB[fromraw][10] + "\n", "#d1d1d1")
                insert_colored_text(text_box2, (' ' * 11) + text_raws + '\n', "#00c983")
            else:
                insert_colored_text(text_box1, '[' + time.strftime("%H:%M:%S", time.localtime()) + '] ' + text_from + ' [' + fromraw + ']' + LoraDB[fromraw][10] + "\n", "#d1d1d1")
        else:
            print("[LoraNet] No ID in packet")
            insert_colored_text(text_box1, '[' + time.strftime("%H:%M:%S", time.localtime()) + '] No NodeID in packet\n', "#c24400")
    else:
        if "fromId" in packet and packet["fromId"] is not None:
            text_from  = packet["fromId"][1:]
            if text_from != '':
                if text_from in LoraDB:
                    LoraDB[text_from][0] = tnow
                    if LoraDB[text_from][1] != '':
                        text_from = LoraDB[text_from][1] + " (" + LoraDB[text_from][2] + ") "
                else:
                    LoraDB[text_from] = [tnow, '', '', 81.0, 186.0, 0, '', '', tnow, '', '', '', -1]
                    insert_colored_text(text_box3, "[" + time.strftime("%H:%M:%S", time.localtime()) + "] New Node Logged ! #" + text_from + "\n", "#c24400")
                    playsound('data/NewNode.mp3')
                    text_from = text_from + " "
        print("[LoraNet] No decoded in packet")
        insert_colored_text(text_box1, '[' + time.strftime("%H:%M:%S", time.localtime()) + '] ' + text_from + 'Packed Encrypted\n', "#c24400")

def updatesnodes():
    global LoraDB, MyLora, MapMarkers
    info = ''
    itmp = 0
    tnow = int(time.time())
    for nodes, info in meshtastic_client.nodes.items():
        if "user" in info:
            tmp = info['user']
            if "id" in tmp and tmp['id'] != '':
                # Only push to DB if we actually get a node ID
                nodeID = str(tmp['id'])[1:]
                nodeLast = tnow
                itmp = itmp + 1

                if "lastHeard" in info and info["lastHeard"] is not None: nodeLast = info['lastHeard']

                if nodeID not in LoraDB:
                    LoraDB[nodeID] = [nodeLast, '', '', 81.0, 186.0, 0, '', '', tnow, '', '', '',-1]
                    insert_colored_text(text_box3, "[" + time.strftime("%H:%M:%S", time.localtime()) + "] New Node Logged ! #" + nodeID + "\n", "#c24400")

                # New node?
                if "shortName" in tmp and "longName" in tmp:
                    lora_sn = str(tmp['shortName'].encode('ascii', 'xmlcharrefreplace'), 'ascii').replace("\n", "")
                    lora_ln = str(tmp['longName'].encode('ascii', 'xmlcharrefreplace'), 'ascii').replace("\n", "")
                    if lora_sn in lora_ln and "Meshtastic" in lora_ln:
                        if LoraDB[nodeID][1] == '': LoraDB[nodeID][1] = lora_ln
                        if LoraDB[nodeID][2] == '': LoraDB[nodeID][2] = lora_ln
                    else:
                        LoraDB[nodeID][1] = lora_sn
                        LoraDB[nodeID][2] = lora_ln
                if "macaddr" in tmp: LoraDB[nodeID][6] = str(tmp['macaddr'])
                if "hwModel" in tmp: LoraDB[nodeID][7] = str(tmp['hwModel'])
                LoraDB[nodeID][12] = -1
                if "hopsAway" in info: LoraDB[nodeID][12] = info['hopsAway']

                if "position" in info:
                    tmp2 = info['position']
                    if "latitude" in tmp2 and "longitude" in tmp2:
                        LoraDB[nodeID][3] = tmp2['latitude']
                        LoraDB[nodeID][4] = tmp2['longitude']
                    if "altitude" in tmp:
                        LoraDB[nodeID][5] = tmp['altitude']
                    
                    if nodeID == MyLora:
                        if MyLora not in MapMarkers:
                            MapMarkers[MyLora] = [None, False, nodeLast, None]
                            MapMarkers[MyLora][0] = map.set_marker(round(LoraDB[MyLora][3],6), round(LoraDB[MyLora][4],6), text=html.unescape(LoraDB[MyLora][1]), icon = tk_icon, text_color = '#00c983', font = ('Fixedsys', 8), data=MyLora, command = click_command)
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
        val = "Just now"
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

    return f"{round(EARTH_R*c,1)}Km"

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
    from tkinter import Frame
    from tkintermapview import TkinterMapView

    def on_closing():
        with open(LoraDBPath, 'wb') as f:
            pickle.dump(LoraDB, f)
        print('Saved Databases')
        root.quit()
        sys.exit()

    # Initialize the main window
    def create_text(frame, row, column, frheight, frwidth):
        # Create a frame with a black background to simulate padding color
        padding_frame = tk.Frame(frame, background="#121212", padx=2, pady=2)
        padding_frame.grid(row=row, column=column, rowspan=1, columnspan=1, padx=0, pady=0, sticky='nsew')
        
        # Configure grid layout for the padding frame
        padding_frame.grid_rowconfigure(0, weight=1)
        padding_frame.grid_columnconfigure(0, weight=1)
        
        # Create a text widget inside the frame
        text_area = tk.Text(padding_frame, wrap=tk.WORD, width=frwidth, height=frheight, bg='#242424', fg='#dddddd', font=('Fixedsys', 10))
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
            playsound('data/NewChat.mp3')

    root = customtkinter.CTk()
    root.title("Meshtastic Lora Logger")
    root.resizable(True, True)
    root.iconbitmap("data\mesh.ico")
    root.protocol('WM_DELETE_WINDOW', on_closing)

    # Map MArker Images
    tk_icon = ImageTk.PhotoImage(Image.open("data\marker.png"))
    tk_direct = ImageTk.PhotoImage(Image.open("data\marker-green.png"))
    tk_mqtt = ImageTk.PhotoImage(Image.open("data\marker-orange.png"))
    tk_old = ImageTk.PhotoImage(Image.open("data\marker-grey.png"))

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
    frame.grid_columnconfigure(2, weight=0)

    # Configure grid layout for the root window
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)

    # Create three text boxes with padding color
    text_box1 = create_text(frame, 0, 0, 30, 100)
    insert_colored_text(text_box1, "Meshtastic Lora Logger v 1.2 By Jara Lowell\n", "#02bae8")
    text_box2 = create_text(frame, 1, 0, 10, 100)
    text_box3 = create_text(frame, 2, 0, 10, 100)

    padding_frame = tk.LabelFrame(frame, background="#242424", padx=0, pady=4, text=my_label.get(), bg='#242424', fg='#999999', font=('Fixedsys', 10), borderwidth=0, highlightthickness=0, labelanchor='n')
    padding_frame.grid(row=4, column=0, rowspan=1, columnspan=1, padx=0, pady=0, sticky="nsew")
    padding_frame.grid_rowconfigure(1, weight=1)
    padding_frame.grid_columnconfigure(0, weight=1)

    text_box4 = tk.Entry(padding_frame, textvariable=my_msg, width=90, bg='#242424', fg='#eeeeee', font=('Fixedsys', 10))
    text_box4.grid(row=4, column=0)
    text_box4.bind("<Return>", send)

    frame_right = tk.Frame(frame, bg="#242424", borderwidth=0, highlightthickness=0, highlightcolor="#242424", highlightbackground="#242424", padx=2, pady=2)
    frame_right.grid(row=0, column=1, rowspan=5, columnspan=1, padx=0, pady=0, sticky='nsew')
    frame_right.grid_rowconfigure(0, weight=1)
    frame_right.grid_columnconfigure(0, weight=1)

    map = TkinterMapView(frame_right, padx=0, pady=0, bg_color='#121212')
    map.grid(row=0, column=0, sticky='nsew')

    overlay = None
    def click_command(marker):
        global LoraDB, MyLora, overlay
        # Info we get from marker click
        print(marker.text)
        print(marker.data)

        # Destroy the existing overlay if it exists
        if overlay is not None:
            overlay.destroy()

        overlay = Frame(root, bg='#242424', padx=3, pady=2, highlightbackground='#999999', highlightthickness=1)
        overlay.place(relx=0.5, rely=0.5, anchor='center')  # Center the frame

        # info_label = tk.Label(overlay, text=text_loc, bg='#242424', fg='#d1d1d1', font=('Fixedsys', 12))
        # info_label.pack(pady=2)

        info_label = tk.Text(overlay, bg='#242424', fg='#dddddd', font=('Fixedsys', 10), width=51, height=12)
        info_label.pack(pady=2)
        insert_colored_text(info_label, "\n⬢ ", "#" + marker.data[:6],  center=True)
        # text_loc += html.unescape(LoraDB[marker.data][1]).ljust(10)
        if LoraDB[marker.data][2] != '':
            text_loc = html.unescape(LoraDB[marker.data][2]) + '\n'
        elif LoraDB[marker.data][1] != '':
            text_loc = html.unescape(LoraDB[marker.data][2]) + '\n'
        else:
            text_loc = '#' + str(marker.data) + '\n'
        insert_colored_text(info_label, text_loc, "#02bae8",  center=True)
        text_loc = ('─' * 34) + '\n'
        insert_colored_text(info_label, text_loc, "#3d3d3d")
        text_loc = ' Position : ' + str(round(LoraDB[marker.data][3],6)) + '/' + str(round(LoraDB[marker.data][4],6)) + ' (' + LatLon2qth(round(LoraDB[marker.data][3],6),round(LoraDB[marker.data][4],6)) + ')\n'
        text_loc += ' Altitude : ' + str(LoraDB[marker.data][5]) + 'm\n'
        insert_colored_text(info_label, text_loc, "#d1d1d1")
        text_loc = ('─' * 34) + '\n'
        insert_colored_text(info_label, text_loc, "#3d3d3d")
        text_loc = ' HW Model : ' + str(LoraDB[marker.data][7]) + '\n'
        text_loc += ' Hex ID   : ' + '!' + str(marker.data).ljust(14)
        text_loc += 'MAC Addr  : ' + str(LoraDB[marker.data][6]) + '\n'
        text_loc += ' Last SNR : ' + str(LoraDB[marker.data][11]).ljust(15)
        text_loc += 'Last Seen : ' + ez_date(int(time.time()) - LoraDB[marker.data][0]) + '\n'
        text_loc += ' Power    : ' + LoraDB[marker.data][9].ljust(15)
        text_loc += 'First Seen: ' + datetime.fromtimestamp(LoraDB[marker.data][8]).strftime('%b %#d \'%y') + '\n'
        if LoraDB[marker.data][3] != 81.0 and LoraDB[marker.data][3] != 186.0:
            text_loc += ' Distance : ' + calc_gc(LoraDB[marker.data][3], LoraDB[marker.data][4], LoraDB[MyLora][3], LoraDB[MyLora][4]).ljust(15)
        else:
            text_loc += ' Distance : -\n'
        if LoraDB[marker.data][12] > 0:
            text_loc += 'HopsAway  : ' + str(LoraDB[marker.data][12]) + '\n'
        insert_colored_text(info_label, text_loc, "#d1d1d1")

        # Create a frame to hold the buttons
        button_frame = Frame(overlay, bg='#242424')
        button_frame.pack(pady=2)

        # Add buttons
        button1 = tk.Button(button_frame, text="Button 1", command=lambda: print("Button 1 clicked"), bg='#242424', fg='#d1d1d1', font=('Fixedsys', 10))
        button1.pack(side=tk.LEFT, padx=5)

        button2 = tk.Button(button_frame, text="Button 2", command=lambda: print("Button 2 clicked"), bg='#242424', fg='#d1d1d1', font=('Fixedsys', 10))
        button2.pack(side=tk.LEFT, padx=5)

        button3 = tk.Button(button_frame, text="Button 3", command=lambda: print("Button 3 clicked"), bg='#242424', fg='#d1d1d1', font=('Fixedsys', 10))
        button3.pack(side=tk.LEFT, padx=5)

        close_button = tk.Button(overlay, text="Close", command=overlay.destroy, bg='#242424', fg='#d1d1d1', font=('Fixedsys', 10))
        close_button.pack(pady=5)

    frame_middle = tk.Frame(frame, bg="#242424", borderwidth=0, highlightthickness=0, padx=0, pady=0)
    frame_middle.grid(row=0, column=2, rowspan=5, columnspan=1, padx=0, pady=0, sticky='nsew')
    frame_middle.grid_rowconfigure(0, weight=1)
    frame_middle.grid_columnconfigure(0, weight=0)

    # Create a text widget inside the middle frame to display the last 30 active nodes
    text_box_middle = create_text(frame_middle, 0, 0, 0, 21)

    # Function to update the middle frame with the last 30 active nodes
    def update_active_nodes():
        global MyLora, MyLoraText1, MyLoraText2, tlast, MapMarkers, LoraDB
        current_view = text_box_middle.yview()
        # Sort the nodes by last seen time
        sorted_nodes = sorted(LoraDB.items(), key=lambda item: item[1][0], reverse=True)[:30]
        text_box_middle.delete("1.0", tk.END)
        insert_colored_text(text_box_middle, "\n " + LoraDB[MyLora][1] + "\n", "#da0000")
        if MyLoraText1 != '':
            insert_colored_text(text_box_middle, MyLoraText1, "#d1d1d1")
        if MyLoraText2 != '':
            insert_colored_text(text_box_middle, MyLoraText2, "#d1d1d1")
        text_box_middle.mark_set(LoraDB[MyLora][1], "1.0")
        tnow = int(time.time())
        for node_id, node_info in sorted_nodes:
            node_time = node_info[0]

            if LoraDB[node_id][8] == 0: LoraDB[node_id][8] = LoraDB[node_id][0] # Fix for first seen being 0 on old DBs
            if '.' not in LoraDB[node_id][9]: LoraDB[node_id][9] = '' # Fix for old DBs with no power info

            if tnow - node_time >= map_oldnode and node_id != MyLora:
                if node_id in MapMarkers:
                    if len(MapMarkers[node_id]) > 3 and MapMarkers[node_id][3] is not None:
                        MapMarkers[node_id][3].delete()
                    MapMarkers[node_id][0].delete()
                    del MapMarkers[node_id]
            elif tnow - node_time >= map_delete and node_id != MyLora:
                if node_id in MapMarkers:
                    if MapMarkers[node_id][0].text_color != '#6d6d6d':
                        if len(MapMarkers[node_id]) > 3 and MapMarkers[node_id][3] is not None:
                            MapMarkers[node_id][3].delete()
                        MapMarkers[node_id][0].delete()
                        MapMarkers[node_id][0] = None
                        MapMarkers[node_id][0] = map.set_marker(round(LoraDB[node_id][3],6), round(LoraDB[node_id][4],6), text=html.unescape(LoraDB[node_id][1]), icon = tk_old, text_color = '#6d6d6d', font = ('Fixedsys', 8), data=node_id, command = click_command)
                        MapMarkers[node_id][0].text_color = '#6d6d6d'
                else:
                    if 'Meshtastic' in LoraDB[node_id][1]:
                        LoraDB[node_id][1] = (LoraDB[node_id][1])[-4:]
                    MapMarkers[node_id] = [None, True, tnow, None]
                    MapMarkers[node_id][0] = map.set_marker(round(LoraDB[node_id][3],6), round(LoraDB[node_id][4],6), text=html.unescape(LoraDB[node_id][1]), icon = tk_old, text_color = '#6d6d6d', font = ('Fixedsys', 8), data=node_id, command = click_command)
                    MapMarkers[node_id][0].text_color = '#6d6d6d'
            elif tnow - node_time < map_delete or node_id == MyLora:
                node_name = node_info[1].ljust(9)
                node_wtime = ez_date(tnow - node_time).rjust(10)
                if LoraDB[node_id][3] != 81.0 and LoraDB[node_id][3] != 186.0:
                    node_dist = calc_gc(LoraDB[node_id][3], LoraDB[node_id][4], LoraDB[MyLora][3], LoraDB[MyLora][4]).ljust(9)
                else:
                    node_dist = ' '.ljust(9)
                node_sig = LoraDB[node_id][11].rjust(10)
                # node_hop = ''
                # if LoraDB[node_id][12] > 0:
                #     node_hop = (str(LoraDB[node_id][12]) + ' Hops Away')
                if MyLora != node_id:
                    if node_info[10] == ' via mqtt':
                        insert_colored_text(text_box_middle, ('─' * 14) + '\n', "#3d3d3d")
                        insert_colored_text(text_box_middle, f" {node_name}{node_wtime}\n", "#c9a500")
                        insert_colored_text(text_box_middle, f" {node_dist}\n", "#9d9d9d")
                        # insert_colored_text(text_box_middle, f" {node_hop}\n", "#9d9d9d")
                        if node_id not in MapMarkers:
                            MapMarkers[node_id] = [None, True, tnow, None]
                            MapMarkers[node_id][0] = map.set_marker(round(LoraDB[node_id][3],6), round(LoraDB[node_id][4],6), text=html.unescape(LoraDB[node_id][1]), icon = tk_mqtt, text_color = '#02bae8', font = ('Fixedsys', 8), data=node_id, command = click_command)
                            MapMarkers[node_id][0].text_color = '#02bae8'
                        elif MapMarkers[node_id][0].text_color != '#02bae8':
                            MapMarkers[node_id][0].delete()
                            MapMarkers[node_id][0] = None
                            MapMarkers[node_id][0] = map.set_marker(round(LoraDB[node_id][3],6), round(LoraDB[node_id][4],6), text=html.unescape(LoraDB[node_id][1]), icon = tk_mqtt, text_color = '#02bae8', font = ('Fixedsys', 8), data=node_id, command = click_command)
                            MapMarkers[node_id][0].text_color = '#02bae8'
                    else:
                        insert_colored_text(text_box_middle, ('─' * 14) + '\n', "#3d3d3d")
                        insert_colored_text(text_box_middle, f" {node_name}{node_wtime}\n", "#00c983")
                        insert_colored_text(text_box_middle, f" {node_dist}{node_sig}\n", "#9d9d9d")
                        # insert_colored_text(text_box_middle, f" {node_hop}\n", "#9d9d9d")
                        if node_id not in MapMarkers:
                            MapMarkers[node_id] = [None, False, tnow, None]
                            MapMarkers[node_id][0] = map.set_marker(round(LoraDB[node_id][3],6), round(LoraDB[node_id][4],6), text=html.unescape(LoraDB[node_id][1]), icon = tk_direct, text_color = '#02bae8', font = ('Fixedsys', 8), data=node_id, command = click_command)
                            MapMarkers[node_id][0].text_color = '#02bae8'
                        elif MapMarkers[node_id][0].text_color != '#02bae8':
                            MapMarkers[node_id][0].delete()
                            MapMarkers[node_id][0] = None
                            MapMarkers[node_id][0] = map.set_marker(round(LoraDB[node_id][3],6), round(LoraDB[node_id][4],6), text=html.unescape(LoraDB[node_id][1]), icon = tk_direct, text_color = '#02bae8', font = ('Fixedsys', 8), data=node_id, command = click_command)
                            MapMarkers[node_id][0].text_color = '#02bae8'

        text_box_middle.yview_moveto(current_view[0])
        if tnow > tlast + 900:
            updatesnodes()
            tlast = tnow
            with open(LoraDBPath, 'wb') as f:
                pickle.dump(LoraDB, f)
            print('Saved Databases')
            gc.collect()
        root.after(2000, update_active_nodes)    
    ### end

    map.set_position(48.860381, 2.338594)
    map.set_tile_server(config.get('meshtastic', 'map_tileserver'))
    map.set_zoom(5)
    
    root.after(2000, update_active_nodes)  # Schedule the next update in 30 seconds
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