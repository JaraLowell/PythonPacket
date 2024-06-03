#!/usr/bin/env python3
import os
import time
import sys
import asyncio
import functools
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
        print("[" + time.strftime("%H:%M:%S", time.gmtime()) + "] [Network] HTTP GET {} 404 File not found".format(path))
        return HTTPStatus.NOT_FOUND, [], b'404 NOT FOUND'

    extension = full_path.split(".")[-1]
    mime_type = MIME_TYPES.get(extension, "application/octet-stream")
    response_headers.append(('Content-Type', mime_type))
    body = open(full_path, 'rb').read()
    response_headers.append(('Content-Length', str(len(body))))
    return HTTPStatus.OK, response_headers, body

async def register(websocket):
    print("[" + time.strftime("%H:%M:%S", time.gmtime()) + "] [Network] New WebSocket connection from", str(websocket.remote_address)[1:-1])
    USERS.add(websocket)

async def unregister(websocket):
    print("[" + time.strftime("%H:%M:%S", time.gmtime()) + "] [Network] WebSocket connection closed for", str(websocket.remote_address)[1:-1])
    USERS.remove(websocket)

async def mysocket(websocket, path):
    await register(websocket)
    try:
        async for message in websocket:
            print("[" + time.strftime("%H:%M:%S", time.gmtime()) + "] [Network] " + message)
            await sendmsg(message)
    finally:
        await unregister(websocket)

async def sendmsg(message):
    timenow = int(time.time())
    for user in USERS:
        await user.send('{"time": ' + str(timenow) + ', "cmd": "chat", "data": "' + message.strip() + '"}')

async def get_stdin_reader() -> asyncio.StreamReader:
    stream_reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(stream_reader)
    loop = asyncio.get_running_loop()
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)
    return stream_reader

async def main():
    stdin_reader = await get_stdin_reader()
    while True:
        line = await stdin_reader.readline()
        await sendmsg(line.decode())
        print("\033[F[" + time.strftime("%H:%M:%S", time.gmtime()) + "] [Console] " + line.decode() + "\033[A")

if __name__ == "__main__":
    os.system("") # in case the above \033[F no works like windows...

    print("\u001B[8;37;44m");
    print("  _   _           _     ______          _        _      ")
    print(" | \\ | |         | |    | ___ \\        | |      | |     ")
    print(" |  \\| | ___   __| | ___| |_/ /_ _  ___| | _____| |_    ")
    print(" | . ` |/ _ \\ / _` |/ _ \\  __/ _` |/ __| |/ / _ \\ __|   ")
    print(" | |\\  | (_) | (_| |  __/ | | (_| | (__|   <  __/ |_    ")
    print(" \\_| \\_/\\___/ \\__,_|\\___\\_|  \\__,_|\\___|_|\\_\\___|\\__|   ")
    print("\u001B[32m  An open source Python WS Packet server V1.1ß          ")
    print("\u001B[32m  For WA8DED Modems that support HostMode               \u001B[0m")

    handler = functools.partial(process_request, os.getcwd() + '/www')
    start_server = websockets.serve(mysocket, '0.0.0.0', MYPORT, process_request=handler)
    print("[" + time.strftime("%H:%M:%S", time.gmtime()) + "] [Network] \u001B[33mRunning server at http://localhost:%d/\u001B[0m" % MYPORT)

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(start_server)
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        loop.stop
