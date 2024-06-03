#!/usr/bin/env python
import os
import sys
import functools
import json
import socketserver
import asyncio
import time
import websockets
from http import HTTPStatus

MYPORT = 8765
MIME_TYPES = {"html": "text/html", "js": "text/javascript", "css": "text/css"}
USERS = set()

async def process_request(sever_root, path, request_headers):
    """Serves a file when doing a GET request with a valid path."""
    if "Upgrade" in request_headers:
        return  # Probably a WebSocket connection

    if path == '/':
        path = '/index.html'

    response_headers = [('Server', 'asyncio websocket server'), ('Connection', 'close')]
    full_path = os.path.realpath(os.path.join(sever_root, path[1:]))
    if os.path.commonpath((sever_root, full_path)) != sever_root or not os.path.exists(full_path) or not os.path.isfile(full_path):
        print("[" + time.strftime("%H:%M:%S", time.localtime()) + "] [Network] HTTP GET {} 404 File not found".format(path))
        return HTTPStatus.NOT_FOUND, [], b'404 NOT FOUND'

    extension = full_path.split(".")[-1]
    mime_type = MIME_TYPES.get(extension, "application/octet-stream")
    response_headers.append(('Content-Type', mime_type))
    body = open(full_path, 'rb').read()
    response_headers.append(('Content-Length', str(len(body))))
    return HTTPStatus.OK, response_headers, body

async def handle_http(reader, writer):
    print(reader)
    data = await reader.read(100)
    message = data.decode()
    writer.write(data)
    await writer.drain()
    writer.close()

async def register(websocket):
    print("[" + time.strftime("%H:%M:%S", time.localtime()) + "] [Network] New WebSocket connection from", str(websocket.remote_address)[1:-1])
    USERS.add(websocket)

async def unregister(websocket):
    print("[" + time.strftime("%H:%M:%S", time.localtime()) + "] [Network] WebSocket connection closed for", str(websocket.remote_address)[1:-1])
    USERS.remove(websocket)

async def ws_callback(websocket, path):
    await register(websocket)
    try:
        async for message in websocket:
            print("[" + time.strftime("%H:%M:%S", time.localtime()) + "] [Network] " + message)
            await sendmsg(0,'echo',message)
    finally:
        await unregister(websocket)

async def sendmsg(channel, cmd, message):
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
        await user.send('{"time": ' + str(timenow) + ', "cmd": "' + cmd + '", "data": "' + message.strip() + '"}')

async def get_stdin_reader() -> asyncio.StreamReader:
    stream_reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(stream_reader)
    loop = asyncio.get_running_loop()
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)
    return stream_reader

async def main():
    os.system("") # in case the above \033[F no works like windows...

    print("\u001B[8;37;44m")
    print("  _   _           _     ______          _        _      ")
    print(" | \\ | |         | |    | ___ \\        | |      | |     ")
    print(" |  \\| | ___   __| | ___| |_/ /_ _  ___| | _____| |_    ")
    print(" | . ` |/ _ \\ / _` |/ _ \\  __/ _` |/ __| |/ / _ \\ __|   ")
    print(" | |\\  | (_) | (_| |  __/ | | (_| | (__|   <  __/ |_    ")
    print(" \\_| \\_/\\___/ \\__,_|\\___\\_|  \\__,_|\\___|_|\\_\\___|\\__|   ")
    print("\u001B[32m  An open source Python WS Packet server V1.1ß          ")
    print("\u001B[32m  For WA8DED Modems that support HostMode               \u001B[0m")

    handler = functools.partial(process_request, os.getcwd() + '/www')

    ws_server = await websockets.serve(ws_callback,'0.0.0.0',MYPORT,process_request=handler)
    print("[" + time.strftime("%H:%M:%S", time.localtime()) + "] [Network] \u001B[33mWebserver listening on port " + str(MYPORT) + "\u001B[0m")

    stdin_reader = await get_stdin_reader()
    try:
        while True:
            line = await stdin_reader.readline()
            await sendmsg(0,'echo',line.decode())
            print("\033[F[" + time.strftime("%H:%M:%S", time.localtime()) + "] [Console] " + line.decode() + "\033[A")
    except KeyboardInterrupt:
        os.exit()

if __name__ == '__main__':
    asyncio.run(main())
