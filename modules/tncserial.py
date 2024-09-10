import time
from datetime import date, datetime

import configparser

config = configparser.ConfigParser()
config.read('./config.ini')

today_date = date.today()
time_now = datetime.now()

# Set TNC in WA8DED Hostmode
def init_tncinWa8ded(ser, sys):
    try:
        ser.open()
    except Exception as e:
        print("[Serial!] \33[1;31m" + repr(e))
        sys.exit()
    ser.write(b'\x11\x18\x1b')
    ser.readline()
    ser.write(b'\x4a\x48\x4f\x53\x54\x31\x0d')
    print('\33[0;33mSetting TNC in hostmode...\33[0m')
    statustnc = ser.readline().decode().rstrip()
    if statustnc != "JHOST1":
        print(statustnc)
        print("[ DEBUG ] NO TNC!!!!")
        sys.exit()
    else:
        print("[ DEBUG ] \33[0;32m" + statustnc  + '\33[0m')
    ser.write(b'\x00\x01\x00\x56')
    print("[ DEBUG ] \33[0;32m" + ser.readline().decode()[2:] + '\33[0m')
    
def init_tncConfig(ser, MyCall, channels, num2byte, sendqueue, BEACONTEXT):
    global ACTCHANNELS
    ACTCHANNELS = {}
    print('\33[0;33mSetting TNC Configs...\33[0m')
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

def logheard(MHeard, MyCall, sendqueue, call, cmd, info):
    tnow = int(time.time())
    # 'callsign' = ['name','jo locator if known',first heard,last heard,heard count,first connect, last connect, connect count];
    #                  0              1              2           3           4           5             6             7
    sindex = call.find('-')
    if sindex > 1:
        call = call[:sindex]

    # testcallsign = re.search('[\\d]{0,1}[A-Z]{1,2}\\d([A-Z]{1,4}|\\d{3,3}|\\d{1,3}[A-Z])[A-Z]{0,5}', call.upper())
    if len(call) < 7:
        # call = testcallsign.group(0)
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
    else:
        print('[ DEBUG ] Log Error, Not a callsign > ' + call)