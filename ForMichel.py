#!/usr/bin/env python3
import os
import time
import sys
import asyncio
import gc

# psutil and websockets needs pip install
import psutil
import websockets
import functools
from http import HTTPStatus

# Next two are for the radio side of things
# text = codecs.decode(data, 'cp850').replace('\r', '\n')
import json
import codecs

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
            print("\r\033[K[" + time.strftime("%H:%M:%S", time.localtime()) + "] [Network]\u001B[31m HTTP GET {} 404 File not found".format(path) + "\u001B[0m")
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
    print("\r\033[K[" + time.strftime("%H:%M:%S", time.localtime()) + "] [Network]\u001B[32m New WebSocket connection from", str(websocket.remote_address)[1:-1].replace('\'','').replace(', ',':') + "\u001B[0m")
    USERS.add(websocket)

async def unregister(websocket):
    print("\r\033[K[" + time.strftime("%H:%M:%S", time.localtime()) + "] [Network]\u001B[32m WebSocket connection closed for", str(websocket.remote_address)[1:-1].replace('\'','').replace(', ',':') + "\u001B[0m")
    USERS.remove(websocket)

async def mysocket(websocket, path):
    await register(websocket)
    try:
        async for message in websocket:
            print("\r\033[K[" + time.strftime("%H:%M:%S", time.localtime()) + "] [Network]\u001B[34m " + message + "\u001B[0m")
            await sendmsg(0,'echo',message)
    finally:
        await unregister(websocket)

async def sendmsg(chan, cmd, message):
    #  cmd    chan      msg
    # -----------------------------
    # cmd1     0        @B:###
    # cmd1     0        @MEM:#####
    # cmd1     0        @L:####
    # cmd1     0        @M:##
    # cmd1     0        @I:##
    # cmd1    1~x       @B:
    # cmd1    1~x       @MEM:#####
    # cmd1    1~x       I:#
    # cmd1    1~x       L:####
    # cmd2    0~x       TNC Error
    # cmd3    1~x       Active channels...
    # cmd100   -        mheard
    # warn    0~x       monitor info
    # info    0~x       
    # chat    0~x       connect info
    # echo    0~x       console/website chat
    # cmd4    0~x       monitor header/no info
    # cmd5    0~x       monitor header/info
    timenow = int(time.time())
    for user in USERS:
        await user.send('{"time":' + str(timenow) + ',"chan":' + str(chan) + ',"cmd":"' + cmd + '","data":"' + message.strip() + '"}')

async def main():
    while True:
        text = await ainput("")
        text = text.encode().decode()
        await sendmsg(0,'echo',text)
        print("\033[F\r[" + time.strftime("%H:%M:%S", time.localtime()) + "] [Console]\u001B[34m " + text + "\u001B[0m", end='')

async def ainput(string: str) -> str:
    await asyncio.get_event_loop().run_in_executor(
            None, lambda s=string: sys.stdout.write(s+' '))
    return await asyncio.get_event_loop().run_in_executor(
            None, sys.stdin.readline)

async def cleaner():
    while True:
        await asyncio.sleep(60 * 5)
        gc.collect()
        tmp = int(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024))
        await sendmsg(0,'cmd1','@MEM:' + str(tmp))
        print("\r\033[K[" + time.strftime("%H:%M:%S", time.localtime()) + "]\u001B[33m Running GC cleaner " + str(tmp) + "MB used \u001B[0m ")


if __name__ == "__main__":
    os.system("")
    print("  _   _           _     ______          _        _      ")
    print(" | \\ | |         | |    | ___ \\        | |      | |     ")
    print(" |  \\| | ___   __| | ___| |_/ /_ _  ___| | _____| |_    ")
    print(" | . ` |/ _ \\ / _` |/ _ \\  __/ _` |/ __| |/ / _ \\ __|   ")
    print(" | |\\  | (_) | (_| |  __/ | | (_| | (__|   <  __/ |_    ")
    print(" \\_| \\_/\\___/ \\__,_|\\___\\_|  \\__,_|\\___|_|\\_\\___|\\__|   ")
    print("\u001B[32m  An open source Python WS Packet server V1.1ß          ")
    print("\u001B[32m  For WA8DED Modems that support HostMode               \u001B[0m\n")

    handler = functools.partial(process_request, os.getcwd() + '')
    start_server = websockets.serve(mysocket, '0.0.0.0', MYPORT, process_request=handler)
    print("\r\033[K[" + time.strftime("%H:%M:%S", time.localtime()) + "]\u001B[33m Starting up HTTP server at http://localhost:%d/ \u001B[0m " % MYPORT)
  
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(start_server)
        loop.create_task(main())
        loop.create_task(cleaner())
        loop.run_forever()
    except KeyboardInterrupt:
        sys.exit()
    except Exception as e:
        print("\r\033[K[" + time.strftime("%H:%M:%S", time.localtime()) + "]\u001B[31m " + repr(e) + " \u001B[0m ")
