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
    
def init_tncConfig(ser, config, send_init_tnc, MyCall, channels, num2byte):
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