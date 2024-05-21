# NodeJSPacket
NodeJS Ham Radio Packet

Build in Node JS

Right now it sends and recieves, can connect but has still some ways to go; The map data it grabs from the monitor if a station in it's beacon sends it's location.

It also only right now coded to work with the WA8DED protocol as some tnc's use so not KISS as if yet tough perhaps atr a stage this be a good thing to add or via
a driver file of sorts. I'm in end just a hoby coder so am sure it not the best of the best and many other selutions be posible vs what i done. So who knows
with a few more people we can make this a great add on packat software for the ham world.

Mine is running on a Raspberry PI, and then any computer in my house can access it via a web site as seen in the images below.

Monitor
![afbeelding](https://i.gyazo.com/afdd00d5f3eb70dc1432e2a41d75ab0a.png)

MHeard
![afbeelding](https://i.gyazo.com/4e7e950cd7fae377a0ac6beee0ba4608.png)

Map (from MHeard)
![afbeelding](https://i.gyazo.com/3fc83dac7ee3be2025e4c6a2c1bc09a2.png)

# Setup
Node used v18.4.0

The serial config is in testold.js on line 211 {path: '/dev/ttyUSB0', baudRate: 9600} this point to an USB serial dongle the 1st one connected to the Rasberrie

The website config on line 108 conncts to ws://127.0.0.1:7712 this needs to reflect your own config obviously; where 127.0.0.1 is the IP or DNS name of the machine that is running the testold.js

To start from the command line start it via in the folder you have testold.js in
$ clear & node testold.js --expose-gc

if you have no http server to host the www folder, you can run
$ clear & node httpserver.js

Make sure your TNC modem was turned off and back one before starting the software, like give it a good seven counts before hitting enter after giving it power. Make sure the boudrate between pc is same as setup in the TNC modem (this is NOT tha trasmite boudrate) aand that the modem is in WA8DED mode.

# To do...
* Config file and option to change these via Config button
* More cleaner and correct way of handling serial data and not as now via two ways
* Additional option to choose either WA8DED or for example LISS
* Working connect button rather then using ^C station
* Maybe adding WSS and HTTPS as some browsers seem to think secure means somting when 30 trilion computers use it

# Side note
This is early early setup, we still missing a lot of functions and to be fair, the js is a mess using two ways of serial port reading because well.. to lazy to do it right i guess...
A fix for this should in time be made obviously so that we can choose between WA8DED or KISS or perhaps even Direwolf via simply selecting what module to start. But that for later versions
