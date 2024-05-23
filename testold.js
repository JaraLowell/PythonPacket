/* Lets test a serial port */
const { SerialPort } = require('serialport'); 
const { InterByteTimeoutParser } = require('@serialport/parser-inter-byte-timeout');
const { ReadlineParser } = require('@serialport/parser-readline');

console.clear()

var fs        = require("fs");
var WebSocket = require('ws');
var util      = require("util");
var Logger    = require('./logger');
var request   = require("request");
var legacy    = require('legacy-encoding'); // Needed for DOS Latin US (Ascii Ext) or CP437 character decoding
var readline  = require('readline');

var myInterval;
var weatherb  = 0;
var bootint   = 1;
var counter   = 0;
var init      = 1;
var polling   = 0;
var sidepoll  = -1;
var mychan    = 0;
var sendreq;
var workbuffer     = [];
var monitorbuffer  = [];
var channelbuffers = [];
var ChRemoteCall   = {};
var ChMyCall       = {};
var ChInOrOut      = {};
var readme         = {};
var mheard         = {};

/*
    The SET MHeard items
*/

// so 'callsign' = ['name','jo locator if known',first heard,last heard,heard count,first connect, last connect, connect count];
function logheard2(callsign, cmd, info) {
    // Current date and time :3
    var timenow = Math.floor(new Date().getTime() / 1000);

    // Lets remove the -Channel if pressent
    var sindex  = callsign.search('-');
    if(sindex > 1) callsign = callsign.substring(0,sindex);

    // If CMD...
    if(cmd == 5) {
        if(callsign in mheard) { mheard[callsign][3] = timenow; mheard[callsign][4] += 4; } else { mheard[callsign] = ['','',timenow,timenow,1,0,0,0]; }
        workbuffer.push([0,'§§',3,'§§','MH']);
    }
    else if(cmd == 6) {
        if(callsign in mheard) { mheard[callsign][1] = info.toString(); } else { mheard[callsign] = ['',info.toString(),timenow,timenow,1,0,0,0]; }
    }
    else if(cmd == 3) {
        if(callsign in mheard) { mheard[callsign][6] = timenow; mheard[callsign][7] += 1; if(mheard[callsign][5] == 0) { mheard[callsign][5] = timenow; }}
    }
}

/*
    Prety console msg
*/
console.log("\u001B[8;37;44m");
console.log("  _   _           _     ______          _        _      ");
console.log(" | \\ | |         | |    | ___ \\        | |      | |     ");
console.log(" |  \\| | ___   __| | ___| |_/ /_ _  ___| | _____| |_    ");
console.log(" | . ` |/ _ \\ / _` |/ _ \\  __/ _` |/ __| |/ / _ \\ __|   ");
console.log(" | |\\  | (_) | (_| |  __/ | | (_| | (__|   <  __/ |_    ");
console.log(" \\_| \\_/\\___/ \\__,_|\\___\\_|  \\__,_|\\___|_|\\_\\___|\\__|   ");
console.log("\u001B[32m  An open source NodeJS AX.25 Packet server V1.0ß       ");
console.log("\u001B[32m  For WA8DED Modems that support HostMode               \u001B[0m");

Logger.start();
Logger.info("\u001B[33mNode.js v" + process.versions.node + " (" + process.platform + " " + process.arch + ")\u001B[0m");
Logger.info("\u001B[33mChrome's V8 JavaScript engine v" + process.versions.v8 + "\u001B[0m");

var jsonString;
if (fs.existsSync('monitor.log')) { jsonString = fs.readFileSync('monitor.log', 'utf8'); monitorbuffer = JSON.parse(jsonString); }
if (fs.existsSync('channel.log')) { jsonString = fs.readFileSync('channel.log', 'utf8'); channelbuffers = JSON.parse(jsonString); }
if (fs.existsSync('mheard.log'))  { jsonString = fs.readFileSync('mheard.log', 'utf8'); mheard = JSON.parse(jsonString); }

/*
    Lets define how we log shizle and later on send to Web interface...
*/
process.on('SIGINT', function() {
    Logger.warn("Closing TNC...");
    clearInterval(myInterval);

    port.drain();

    // This is what should happen if you press X or close rather then ctrl + c
    // port.write(Buffer.from([0x00, 0x01, 0x01, 0x4d, 0x4e])); // ^MN
    // port.write(Buffer.from([0x00, 0x01, 0x06, 0x55, 0x31, 0x41, 0x77, 0x61, 0x79, 0x21])); // U1 Away!
    // port.write(Buffer.from([0x00, 0x01, 0x01, 0x4b, 0x32])); // ^K2
    port.write(Buffer.from([0x00, 0x01, 0x05, 0x4a, 0x48, 0x4f, 0x53, 0x54, 0x30])); // ^JHOST0

    fs.writeFileSync('mheard.log', JSON.stringify(mheard), 'utf-8');
    fs.writeFileSync('monitor.log', JSON.stringify(monitorbuffer), 'utf-8');
    fs.writeFileSync('channel.log', JSON.stringify(channelbuffers), 'utf-8');

    port.close();
    process.exit(1);
});

process.on('exit', function (code) {
    Logger.debug("process.exit(" + code + ")");
    Logger.shutdown();
});

process.on('uncaughtException', function (err) {
    Logger.fatal(err.stack);
    process.exit(1);
});

/*
    The Web Socket Server (WORKS AND TESTED!) ;p
*/
const wsServer = new WebSocket.Server({ port: 7712 })
Logger.info('server active on port 7712');

wsClients = [];

wsServer.on('connection', (ws) => {
    ws.remoteAddress = ws._socket.remoteAddress;
    ws.remotePort = ws._socket.remotePort;
    Logger.debug('[Network] New conenction from ' + ws.remoteAddress + ':' + ws.remotePort);

    var index = wsClients.push(ws) - 1;
    ws.on('message', async (msg) => {
        onReceive(msg);
    });
    ws.on('close', function(connection) {
        Logger.debug('[Network] Connection closed');
        wsClients.splice(index, 1);
    });

    /* Lets send the default data */
    /* small half a sec delay so webby has time to load everything */
    sleep(250).then(() => {
        var index;
        /* Sending channel buffers */
        if(channelbuffers.length) {
            index = 0;
            while(channelbuffers[index]) {
                ws.send(channelbuffers[index].toString());
                index++;
            }
        }
        /* Sending Monmitor  buffers */
        if(monitorbuffer.length) {
            index = 0;
            while(monitorbuffer[index]) {
                ws.send(monitorbuffer[index].toString());
                index++;
            }
        }
        workbuffer.push([0,'§§',0,'§§','M']);
        workbuffer.push([0,'§§',0,'§§','I']);
        workbuffer.push([0,'§§',0,'§§','C']);
        workbuffer.push([0,'§§',1,'§§','CHN']);
        workbuffer.push([0,'§§',3,'§§','MH']);
        tncbuffer = ''; tncchans = '';
    });
});

const sleep = (waitTimeInMs) => new Promise(resolve => setTimeout(resolve, waitTimeInMs));

// Msg from Webpage in to here
function onReceive(msg) {
    Logger.chat("[Network] " + msg);
    var text = msg.toString();

    if(text.charCodeAt(0) == 0x40) {
        // msg starts with @
        mychan = parseInt(text.toString('ascii').substring(1, text.length));
        Logger.debug("Active Channel set to " + mychan.toString());
        workbuffer.push([mychan,'§§',0,'§§','I']);
        tncbuffer = ''; tncchans = '';
    } else if(text.charCodeAt(0) != 0x5e) {
        // maybe route trough textchunk(text.toString('ascii'), mychan, 'NL0MSK');
        //onSerial(mychan, 'echo', text.toString('ascii'))
        workbuffer.push([mychan,'§§',6,'§§',text]);
    } else {
        // msg starts with ^
        sendreq = text.toString('ascii').substring(1, text.length).toUpperCase();
        if(sendreq.substring(0,1) == 'C') ChInOrOut[mychan] = 1;
        workbuffer.push([mychan,'§§',0,'§§',text.toString('ascii').substring(1, text.length)]);
    }
}

// Msg out to webpage and to log file
function onSerial(chn, cmd, msg) {
    var tmp = {};
    tmp['time'] = Math.floor(new Date().getTime() / 1000);
    tmp['chan'] = parseInt(chn);
    tmp['cmd']  = cmd;
    tmp['data'] = msg;
    for (var i=0; i < wsClients.length; i++) wsClients[i].send(JSON.stringify(tmp));
    /* Lets also keep a buffer for re-connecting clients */
    if(cmd != 'cmd1' && cmd != 'cmd2' && cmd != 'cmd3' && cmd != 'cmd100') {
        // GP uses like 300 lines for monitor, 
        // and 500 for channel 1; and 100 for any channel after
        if(chn == 0) {
            monitorbuffer.push(JSON.stringify(tmp));
            if(monitorbuffer.length > 300) monitorbuffer.shift();
        } else {
            channelbuffers.push(JSON.stringify(tmp));
            if(channelbuffers.length > 500) channelbuffers.shift();
        }
    }
}

/*
    Open Serial port
*/
const port = new SerialPort({path: '/dev/ttyUSB0', baudRate: 9600});

port.on('error', function(err) { Logger.fatal('Serial Port Error: ', err.message); });
port.on('close', function(err) { Logger.fatal('Serial Port Closed: ', err.message); });
port.on('open', function() {
    Logger.debug('Serial port open');
    readme.a = 0;
    readme.b = 0;
    readme.c = '';
    bootint = 1;
    MonBuff = 0;
    polling = 0;
    init    = 1;
    port.write(Buffer.from([0x11, 0x18, 0x1b])); // Init
    port.write(Buffer.from([0x4a, 0x48, 0x4f, 0x53, 0x54, 0x31, 0x0d]));
    Logger.debug("Starting TNC...");
//    myInterval = setInterval(sendinit, 1300);
    setInterval(sendbeacon, 1320000); // was 9600000 every 22 min i hope . . . . ? 1320000
});

// Read Short Lines
const parser = port.pipe(new InterByteTimeoutParser({interval: 28}));

// Read the long(er) text lines via ReadlineParser
const parser2 = port.pipe(new ReadlineParser({delimiter: [0x00], encoding: 'hex'}));

parser2.on('data', function(data2) {
    if(readme.b != 0) {
        var tmp  = Buffer.from(data2.substring(readme.b - 2,data2.length - (readme.b - 4)), 'hex');
        var text = legacy.decode(tmp, 'ibm850').replace(/[\r]/g, '\n');
        text = text.replace(/[\x00-\x08]/g, '');

        if(readme.b == 6) {
            if(readme.d != text.length) Logger.fatal('Buffer underrun, expected ' + readme.d + ' bytes and got ' + text.length);

            if(text != '') {
                onSerial(readme.a,'warn',text);
                Logger.warn('          ' + text);
            }
            if(readme.c != '') {
                var locator = text.toUpperCase().match(/[A-R]{2}[0-9]{2}[A-Z]{2}[0-9]{2}/g);
                if(locator == null) locator = text.toUpperCase().match(/[A-R]{2}[0-9]{2}[A-Z]{2}/g);
                if(locator != null) logheard2(readme.c, 6, locator);
                readme.c = '';
            }
        } else if(readme.b == 8) {
            if(readme.d != text.length) Logger.fatal('Buffer underrun, expected ' + readme.d + ' bytes and got ' + text.length);

            if(text != '') {
                onSerial(readme.a,'chat',text);
                Logger.chat('          ' + text);
            }

            // lets deal with commands
            if(text.toUpperCase().includes('//NAME')) {
                chan_c('Function not yet implemented...', readme.a,1);
                // logname(ChRemoteCall[channel],) right.. we no know callsign here yet....
            } else if(text.includes('//')) {
                var value = 2 + parseInt(text.search('//'));
                var reqcmd = text.charAt(value).toUpperCase();

                     if(reqcmd == 'H') { openfile('help', readme.a, ChRemoteCall[readme.a]); }
                else if(reqcmd == 'M') { sendMH(readme.a); } //chan_c('* Geen MHeard File *', readme.a,1); }
                else if(reqcmd == 'N') { openfile('news', readme.a, ChRemoteCall[readme.a]); }
                else if(reqcmd == 'I') { openfile('info', readme.a, ChRemoteCall[readme.a]); }
                else if(reqcmd == 'W') { openfile('weer', readme.a, ChRemoteCall[readme.a]); }
                else if(reqcmd == 'Q') { chan_c('Totziens maar weer!', readme.a,1); sendreq = 'D'; port.write(Buffer.from(chan_s(sendreq,readme.a))); }
                else chan_c('ehh what moet dat nu? // whaaa?', readme.a,1);
            }
        }
        readme.b = 0;
    }
});

/*
    Send JHOST1 to modem to see if we can sync
*/
var bootup = function() {
    port.write(Buffer.from([0x11, 0x18, 0x1b]));
    port.write(Buffer.from([0x4a, 0x48, 0x4f, 0x53, 0x54, 0x31, 0x0d]));
}

/*
    Lets listen to the serial port and deal with data
*/
var geo1 = locator2deg('JO32MW49'); // our locator
var lon1 = geo1.longitude * (Math.PI / 180);
var lat1 = geo1.latitude * (Math.PI / 180);
var heardnew = '';
var thetext = '';
var MonBuff  = 0;
var infbuffer = '';
var tncbuffer;
var tncchans;

parser.on('data', function(data) {
    if(data) {
        var ChanName;
        if(bootint == 1) {
            // console.log(data.toString('ascii'));
            if(data.toString('ascii').includes('JHO') || data.toString('ascii').includes('ST1') || data.toString('ascii').includes('HOS')) {
                clearInterval(myInterval);
                bootint = 0;
                Logger.debug("TNC SYNC OK...");
                init = 1;
                myInterval = setInterval(sendinit, 130);
            } else {
                //port.write(Buffer.from(chan_s('QRES')));
                port.write(Buffer.from([0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01]));
                Logger.debug("TNC SYNC FAIL...");
                port.drain();
                port.write(Buffer.from([0x11, 0x18, 0x1b]));
                port.write(Buffer.from([0x4a, 0x48, 0x4f, 0x53, 0x54, 0x31, 0x0d]));
            }
            return;
        }
        if(init > 0) { if(data.toString('ascii').includes('ST1')) return; }

        var channel = parseInt(data.toString('hex').substring(0,2), 16);
        var command = parseInt(data.toString('hex').substring(2,4), 16);

        if(channel <= 254) {
            ChanName = '[Chan ' + ("00" + channel).slice(-2) + '] ';
            if(channel == 0) ChanName = '[Monitor] ';

            thetext = data.toString('ascii').substring(2).replace(/[\x00-\x08]/g, '');

            if(command == 0) {
                // Success, no data follows
                polling = 255;
                if(sidepoll != -1) { polling = sidepoll; sidepoll = -1; }
            } else if( command == 1 ) {
                // Success, message follows (end with 00)
                if(sendreq == '@B') { if(thetext != tncbuffer) { tncbuffer = thetext; onSerial(channel, 'cmd1', sendreq + ':' + thetext); onSerial(channel, 'cmd1', '@MEM:' + process.memoryUsage().rss);}}
                else if(sendreq == 'L') { if(thetext != tncchans) { tncchans = thetext; onSerial(channel, 'cmd1', sendreq + ':' + thetext); }}
                else {
                    onSerial(channel, 'cmd1', sendreq + ':' + thetext);
                    Logger.debug(sendreq + ':' + thetext);
                }
            } else if( command == 2) {
                // Failure, message follows
                ChanName += sendreq + ' ' + thetext;
                onSerial(channel, 'cmd2', sendreq + ':' + thetext);
                Logger.error(ChanName);
            } else if( command == 3) {
                // Link status
                ChanName += thetext;
                Logger.chat(ChanName);
                onSerial(channel,'chat',thetext);
                if(data.toString('ascii').includes('DISCONNECTED')) {
                    ChInOrOut[channel] = -1;
                    ChRemoteCall[channel] = 'None';
                    onSerial(0, 'cmd3', JSON.stringify(ChRemoteCall));
                } else if(data.toString('ascii').includes('CONNECTED')) {
                    if(ChInOrOut[channel] == -1) ChInOrOut[channel] = 2;
                    ChRemoteCall[channel] = ChanName.split(" ")[5];
                    onSerial(0, 'cmd3', JSON.stringify(ChRemoteCall));
                    logheard2(ChanName.split(" ")[5], 3, '');
                    if(ChInOrOut[channel] == 2) openfile('ctext', channel, ChRemoteCall[channel]);
                }
            } else if( command == 4) {
                // Monitor header/no info
                ChanName += thetext;
                var callsign = thetext.split(" ")[1];
                onSerial(channel,'cmd4',thetext);
                Logger.info(ChanName);
                logheard2(callsign, 5, '');
            } else if( command == 5) {
                // Monitor header/info
                var callsign = thetext.split(" ")[1];

                // Lets Remove the -num
                var sindex  = callsign.search('-');
                if(sindex > 1) callsign = callsign.substring(0,sindex);

                heardnew = '';
                var lasttz = ' * NEW *';
                if(callsign in mheard) {
                    lasttz = ' (Last seen ' + ezDate(mheard[callsign][3]) + ' ago)';
                    // not new
                }

                logheard2(callsign, 5, '');
                readme.c = callsign;
                ChanName += thetext + lasttz;
                Logger.info(ChanName);
                onSerial(channel,'cmd5', thetext + lasttz);

                if(lasttz == ' * NEW *') {
                    heardnew = callsign;
                }
            } else if( command == 6) {
                // Monitor information
                readme.a = channel;
                readme.b = 6;
                readme.d = data.toString('ascii').charCodeAt(2);

                data = data.subarray(3, data.length - 1); // removge 1st 00 06 xx and last 0d
                var text = legacy.decode(data, 'ibm850');
                if(heardnew != '') {
                    var extra = '5x5';
                    var locator = text.toUpperCase().match(/[A-R]{2}[0-9]{2}[A-Z]{2}[0-9]{2}/g);
                    if(locator == null) locator = text.toUpperCase().match(/[A-R]{2}[0-9]{2}[A-Z]{2}/g);
                    if(locator != null) {
                        var geo2 = locator2deg(locator.toString());
                        var lon2 = geo2.longitude * (Math.PI / 180);
                        var lat2 = geo2.latitude * (Math.PI / 180);
                        extra = (locator.toString() + ' ' + calc_gc(lat1, -lon1, lat2, -lon2));
                    }
                    sendcq(heardnew,extra);
                    heardnew = '';
                }
            } else if( command == 7) {
                // Connected information
                readme.a = channel;
                readme.b = 8;
                readme.d = data.toString('ascii').charCodeAt(2);
            }
        } else {
            // Polling for Data
            //if(readme.b != 0) return;

            sidepoll = -1;
            if(parseInt(data.toString('hex').substring(4,6), 16) != 0) {
                // meep we have new shiz
                polling = parseInt(data.toString('hex').substring(6,8), 16);
                if(data.toString('hex').length > 8) {
                    polling = parseInt(data.toString('hex').substring(8,10), 16);
                    sidepoll = parseInt(data.toString('hex').substring(6,8), 16);
                    if(sidepoll > 0) sidepoll -= 1;
                    if(sidepoll == 254) polling = 255;
                }
            }
        }
    }
    if(init == 0) {
        init = -1;
        clearInterval(myInterval);
        myInterval = setInterval(checkbuff, 120);
    }
});

/*
    The 120 ms polling . . .
*/
var checkbuff = function() {
    // Lets wait till line read is done reading
    counter += 1;
    if(workbuffer.length && polling > 10) {
        /* our send to tnc buffer, maybe skip if buffers less then 300 ? */
        var todo = (workbuffer[0].toString()).split(',§§,');
        workbuffer.shift();
        // console.log('chn ' + todo[0] + ', cmd ' + todo[1] + ', msg ' + todo[2]);
        if     (todo[1] == 0) { sendreq = todo[2]; port.write(Buffer.from(chan_s(sendreq, todo[0]))); }
        else if(todo[1] == 1) { onSerial(0,'cmd3', JSON.stringify(ChRemoteCall)); }
        else if(todo[1] == 2) { textchunk(todo[2], todo[0], 'NL0MSK'); }
        else if(todo[1] == 3) { onSerial(0, 'cmd100', JSON.stringify(mheard)); }
        else if(todo[1] == 4) { chan_c(todo[2],todo[0],0); }
        else if(todo[1] == 6) { chan_c(todo[2],todo[0],1); onSerial(todo[0],'echo',todo[2]); }
    } else if(counter == 12 && polling > 10) {
        sendreq = 'L';
        port.write(Buffer.from([mychan, 0x01, 0x00, 0x4c])); // Channel Status ^L
    } else if(counter > 24 && polling > 10) {
        sendreq = '@B';
        port.write(Buffer.from([0x00, 0x01, 0x01, 0x40, 0x42])); // Buffer ^@B
        counter = 0;
    } else {
        port.write(Buffer.from([polling, 0x01, 0x00, 0x47])); // Poll Data on Ch polling
    }
}

/*
     open terminal and use for chat
*/
var stdin = process.openStdin();
stdin.addListener("data", function(adata) {
    if(adata.length) {
        var text = adata.toString().replace(/\r?\n|\r/g, "");

        process.stdout.moveCursor(0, -1);
        process.stdout.clearLine(1);

        if(text.charCodeAt(0) == 0x40) {
            mychan = parseInt(text.toString('ascii').substring(1, text.length));
            Logger.debug("Active Channel set to " + mychan.toString());
        } else if(text.charCodeAt(0) != 0x5e) {
            // maybe route trough textchunk(text.toString('ascii'), mychan, 'NL0MSK');
            chan_c(text.toString('ascii'),mychan,1);

            var ChanName = '[Chan ' + ("00" + mychan).slice(-2) + '] ';
            if(mychan == 0) ChanName = '[Monitor] ';
            ChanName += text.toString('ascii');
            Logger.chat(ChanName);
        } else {
            sendreq = text.toString('ascii').substring(1, text.length).toUpperCase();
            if(sendreq.substring(0,1) == 'C') ChInOrOut[mychan] = 1;
            if(sendreq.substring(0,1) == 'F') openfile(text.substring(3), mychan, ''); else port.write(Buffer.from(chan_s(text.substring(1, text.length),mychan)));
        }
    }
});

/*
    Semd string to channel 0 Like TIME!
*/
function chan_s(str, chnS) {
    var arr = [];

    //arr.push([chnS.toString(16)]);
    arr.push(chnS);
    arr.push([0x01]); // Info/CMD
    //arr.push(['0x' + ("00" + (str.length - 1).toString(16)).slice(-2)]);
    var txtlen = parseInt(str.length - 1);
    arr.push(txtlen);
    for (var i = 0, l = str.length; i < l; i ++) {
        var ascii = str.charCodeAt(i);
        arr.push(ascii);
    }
    return arr;
}

function chan_c(text, chnC, crn) {
    if(crn == 1) text += '\r'
    var arr = [];
    arr.push(chnC);
    arr.push([0x00]); // Info/CMD
    var txtlen = parseInt(text.length - 1);
    arr.push(txtlen);
    for (var i = 0, l = text.length; i < l; i ++) {
        var ascii = text.charCodeAt(i);
        arr.push(ascii);
    }
    port.write(Buffer.from(arr)); // Send
    //console.log(Buffer.from(arr).toString('hex'));
}

/*
    Reading files like info.txt, news.txt etc...
*/
function openfile(file, chnF, callsign) {
    try {
        var filecont = fs.readFileSync('txtfiles/' + file + '.txt', 'ascii').replace(/\r?\n|\r/g, "\r");
        //var tmp  = Buffer.from(filecont, 'hex');
        //var filecont = legacy.decode(tmp, 'ibm850').replace(/\r?\n|\r/g, "\r");
        textchunk(filecont, chnF, callsign);
    } catch (err) {
        textchunk('* file ' + file + ' niet gevonden! *', chnF, callsign);
    }
}

/*
    Lets break up the package in small parts
    according to the document max 256 characters
    minus CR
    so that be <ch><cmd><lgth>< data ><cr>
    = 252 for data ASCII characters yet in port sniffer we saw HEX 7F as max pack len wish is 127 ascii characters for data ?
*/
function textchunk(cnktext, chnT, callsign) {
    cnktext = cnktext.replace('%v', 'NodeJS Packet v1.0'); // Softwaare version
    cnktext = cnktext.replace('%c', callsign); // %c = The Call of the opposite Station
    if(callsign in mheard) cnktext = cnktext.replace('%n', mheard[callsign][0] + ' (' + callsign + ')'); else cnktext = cnktext.replace('%n', callsign); // The Name of the opposite Station
    cnktext = cnktext.replace('%y', ChMyCall[chnT]);// %y = One's own Call
    cnktext = cnktext.replace('%k', chnT.toString());       // The Number of the Channel, on which the Text will be sent
    cnktext = cnktext.replace('%t', getTimeString());      // Time in the HH:MM:SS, e.g. "10:41:32"
    cnktext = cnktext.replace('%d', getDateTimeString());  // The actual Date, e.g. "25.03.1991"
    // %b = Corresponds to the Bell Character (07h)
    cnktext = cnktext.replace('%i', 'Er is nieuws !, //NEws om het te lezen.\n'); // News
    cnktext = cnktext.replace('%z', 'GMT+1');              // %z = The Time Zone of the server
    cnktext = cnktext.replace('%>', callsign.toString() + ' to NL0MSK >\n');
    // %o = Reads a Line from ORIGIN.GPI (Chosen at Random)
    // %? = Requests the Logged On Station to give its Name if name is unknown

    var ConText = '[Chan ' + ("00" + chnT).slice(-2) + '] ';
    if(chnT == 0) ConText = '[Monitor] ';

    onSerial(chnT, 'echo', cnktext);

    if((cnktext.split(/\r/).length - 1) >= 2) {
        Logger.chat(ConText + cnktext.replace(/(\r\n|\n|\r)/gm,"\n                     "));
    } else {
        Logger.chat(ConText + cnktext);
    }
    // pack len max 242, default 128
    while(cnktext.length > 128) {
        var tmp = cnktext.substring(0,128);
        cnktext = cnktext.substring(128,cnktext.length);
        // workbuffer.push([chnT,'§§',4,'§§',tmp]);
        chan_c(tmp, chnT, 0);
    }
    // workbuffer.push([chnT,'§§',4,'§§',cnktext]);
    if(cnktext.length) chan_c(cnktext, chnT, 0);
}

/*
    Simple x days, hours minutes based on unix time stamp
*/
function ezDate($d) {
    $temp = 0;
    $ts = Math.floor(new Date().getTime() / 1000) - $d;

    if     ($ts>31536000) { $temp = Math.round($ts/31536000,0); $val = $temp + ' year'; }
    else if($ts>2419200) { $temp = Math.round($ts/2419200,0); $val = $temp + ' month'; }
    else if($ts>604800) { $temp = Math.round($ts/604800,0); $val = $temp + ' week'; }
    else if($ts>86400) { $temp = Math.round($ts/86400,0); $val = $temp + ' day'; }
    else if($ts>3600) { $temp = Math.round($ts/3600,0); $val = $temp + ' hour'; }
    else if($ts>60) { $temp = Math.round($ts/60,0); $val = $temp + ' minute'; }
    else { $temp = $ts; $val = $temp + ' second'; }
    if( $temp > 1 ) $val += 's';

    return $val;
}

/*
    Time in 00:00:00 format
*/
function getTimeString() {
    var date = new Date();
    var th = date.getHours();
    var tm = date.getMinutes();
    var ts = date.getSeconds();
    th = ("00" + th).slice(-2);
    tm = ("00" + tm).slice(-2);
    ts = ("00" + ts).slice(-2);
    return th + ":" + tm + ":" + ts;
};

/*
    Date in year//month/day format
*/
function getDateTimeString() {
    var date = new Date();
    var dy = date.getFullYear();
    var dm = date.getMonth() + 1;
    var dd = date.getDate();
    dy = ("0000" + dy).slice(-2);
    dm = ("00" + dm).slice(-2);
    dd = ("00" + dd).slice(-2);
    return dy + "/" + dm + "/" + dd;
};

/*    Lets make a beacon and send it ~   */
var sendbeacon = function() {
    var date = new Date();
    let th = Number(date.getHours());
    if(th > 0 && th < 10) return;

    if (global.gc) global.gc();

    if(weatherb == 0) {
        /*  Using local stored json file saved from weather station  */
        var url = 'http://192.168.178.228/data/report/raw.json';
        wjson = request(url, {json:true}, (error, res, body) => {
            var text;
            if (!error && res.statusCode == 200) {
                var wjson = body;
                var winddir = ['N','NNO','NO','ONO','O','OZO','ZO','ZZO','Z','ZZW','ZW','WZW','W','WNW','NW','NNW','N'];
                var wtet = winddir[Math.round(wjson['winddir_avg10m']*16/360)];
                text = `Weather at JO32MW, Wind ${wtet} ${wjson['windspeedbf_avg10m'].toString()}bf, Temp ${Math.round(wjson['tempc']).toString()}C, Hum ${wjson['humidity'].toString()}%, Baro ${Math.round(wjson['baromabshpa']).toString()} hpa @ ${getTimeString().slice(0,5)}`;
            }
            chan_c(text, 0, 1);
        });
        weatherb = 1;
    } else {
        var text = `Sysop Jara, Mussel GRN NLD EU, JO32MW49 JSNode Packet v1.0Beta @ ${getTimeString().slice(0,5)}`;
        weatherb = 0;
        chan_c(text, 0, 1);
    }
}

function sendMH(chnz) {
    var sendme = 'NL0MSK Heard-list\r Station    Sysop     Locator   Last\r\r'
    var tmptext;
    var tn = Math.floor(new Date().getTime() / 1000);

    for(var k in mheard) {
        if((tn - mheard[k][3]) < 43200) {
            sendme += ' ' + k + ' '.repeat(11 - k.length);
            tmptext = mheard[k][0];
            if(tmptext == '') tmptext = '-';
            sendme += tmptext + ' '.repeat(10 - tmptext.length);

            tmptext = mheard[k][1];
            if(tmptext == '') tmptext = '-';
            sendme += tmptext + ' '.repeat(10 - tmptext.length);

            tmptext = ezDate(mheard[k][3]);
            sendme += tmptext + ' ago\r';
        }
    }
    sendme += '\rGenerated on ' + getDateTimeString() + ' at ' + getTimeString() + ' GMT+1\r';
    textchunk(sendme, chnz, '');
}

function sendcq(callsign, extra) {
    workbuffer.push([0,'§§',0,'§§','C APU25N WIDE3-3']);
    workbuffer.push([0,'§§',6,'§§','HEARDDX: ' + callsign + ' at ' + getTimeString() + ', ' + extra + ' from NL0MSK, Good Day!']); //was 2
    workbuffer.push([0,'§§',0,'§§','C CQ']);
}

/*
    Sending settings at JHost init
    Remeber: The TNC3 displays the correct date for dates from 1980 to 2037
*/
function sendinit() {
    if(init <= 0) {
        // why we here?
    } else if(init <= 19) {
        var Defs = {
        // Initialisation
        1 : 'G 0',
        2 : 'C CQ',
        3 : 'Y 10',
        4 : 'M IUS',
        5 : 'U 0',
        6 : 'K YY/MM/DD',
        7 : 'K HH:MM:SS',
        8 : '@V 0',
        // Settings File
        9 : 'K 0',
        10: 'O 3',
        11: 'P 62',
        12: 'T 62',
        13: 'W 10',
        14: 'R 1',
        // All = UISC
        15: 'M UISC+',
        16: 'C CQ',
        17: 'X 1',
        18: 'N 6',
        19: 'I NL0MSK',

/*
        // Set up Channels
    Obviouslu cant use chan_0 for that so skip for now nor really needed as it uses Global anyways
    if we want to like define each channel with a new callname per channel
        22: [0x01, 0x01, 0x00, 0x43],                                                      // Ch 1 : ^C
        23: [0x01, 0x01, 0x07, 0x49, 0x20, 0x4e, 0x4c, 0x30, 0x4d, 0x53, 0x4b],            // Ch 1 : ^I NL0MSK
        24: [0x01, 0x01, 0x00, 0x49],                                                      // Ch 1 : ^I
        25: [0x02, 0x01, 0x00, 0x43],                                                      // Ch 2 : ^C
        26: [0x02, 0x01, 0x07, 0x49, 0x20, 0x4e, 0x4c, 0x30, 0x4d, 0x53, 0x4b],            // Ch 2 : ^I NL0MSK
        27: [0x02, 0x01, 0x00, 0x49],                                                      // Ch 2 : ^I
        28: [0x03, 0x01, 0x00, 0x43],                                                      // Ch 3 : ^C
        29: [0x03, 0x01, 0x07, 0x49, 0x20, 0x4e, 0x4c, 0x30, 0x4d, 0x53, 0x4b],            // Ch 3 : ^I NL0MSK
        30: [0x03, 0x01, 0x00, 0x49],                                                      // Ch 3 : ^I
        31: [0x04, 0x01, 0x00, 0x43],                                                      // Ch 4 : ^C
        32: [0x04, 0x01, 0x07, 0x49, 0x20, 0x4e, 0x4c, 0x30, 0x4d, 0x53, 0x4b],            // Ch 4 : ^I NL0MSK
        33: [0x04, 0x01, 0x00, 0x49],                                                      // Ch 4 : ^I
        34: [0x05, 0x01, 0x00, 0x43],                                                      // Ch 5 : ^C
        35: [0x05, 0x01, 0x07, 0x49, 0x20, 0x4e, 0x4c, 0x30, 0x4d, 0x53, 0x4b],            // Ch 5 : ^I NL0MSK
        36: [0x05, 0x01, 0x00, 0x49],                                                      // Ch 5 : ^I
        37: [0x06, 0x01, 0x00, 0x43],                                                      // Ch 6 : ^C
        38: [0x06, 0x01, 0x07, 0x49, 0x20, 0x4e, 0x4c, 0x30, 0x4d, 0x53, 0x4b],            // Ch 6 : ^I NL0MSK
        39: [0x06, 0x01, 0x00, 0x49],                                                      // Ch 6 : ^I
        40: [0x07, 0x01, 0x00, 0x43],                                                      // Ch 7 : ^C
        41: [0x07, 0x01, 0x07, 0x49, 0x20, 0x4e, 0x4c, 0x30, 0x4d, 0x53, 0x4b],            // Ch 7 : ^I NL0MSK
        42: [0x07, 0x01, 0x00, 0x49],                                                      // Ch 7 : ^I
        43: [0x08, 0x01, 0x00, 0x43],                                                      // Ch 8 : ^C
        44: [0x08, 0x01, 0x07, 0x49, 0x20, 0x4e, 0x4c, 0x30, 0x4d, 0x53, 0x4b],            // Ch 8 : ^I NL0MSK
        45: [0x08, 0x01, 0x00, 0x49],                                                      // Ch 8 : ^I
        46: [0x09, 0x01, 0x00, 0x43],                                                      // Ch 9 : ^C
        47: [0x09, 0x01, 0x07, 0x49, 0x20, 0x4e, 0x4c, 0x30, 0x4d, 0x53, 0x4b],            // Ch 9 : ^I NL0MSK
        48: [0x09, 0x01, 0x00, 0x49],                                                      // Ch 9 : ^I
        49: [0x0a, 0x01, 0x00, 0x43],                                                      // Ch 10: ^C
        50: [0x0a, 0x01, 0x07, 0x49, 0x20, 0x4e, 0x4c, 0x30, 0x4d, 0x53, 0x4b],            // Ch 10: ^I NL0MSK
        51: [0x0a, 0x01, 0x00, 0x49],                                                      // Ch 10: ^I
        52: [0x00, 0x01, 0x00, 0x43],                                                      // Read ^Ch 0
*/
        };

        if(init == 1) { Logger.debug("Sending TNC Init's"); }

        if(init == 3) {
            // Welp lets populate the channel callsign connected list...
            var maxchannels = parseInt(Defs[3].toString().substring(1,Defs[3].length));
            var index = 1;
            while(index <= maxchannels) {
                ChRemoteCall[index] = 'None';
                ChMyCall[index]     = 'NL0MSK';
                ChInOrOut[index]    = '-1';
                console.log('Channel ' + index + ' set to NL0MSK');
                index += 1;
            }
        }

        if(init == 7) {
            sendreq = 'K ' + getDateTimeString();
            port.write(Buffer.from(chan_s(sendreq,0)));
        } else if(init == 8) {
            sendreq = 'K ' + getTimeString();
            port.write(Buffer.from(chan_s(sendreq,0)));
        } else {
            sendreq = Defs[init];
            port.write(Buffer.from(chan_s(sendreq,0)));
        }
        init = init + 1;
        polling = 0;
    } else {
        counter = 0;
        init = 0;
        polling = 255;
        port.write(Buffer.from([polling, 0x01, 0x00, 0x47]));
        Logger.debug("TNC Active and listening...");
        sendbeacon();
    }
}


function calc_gc(lat1, lon1, lat2, lon2) {
    var d = Math.acos(Math.sin(lat1) * Math.sin(lat2) + Math.cos(lat1) * Math.cos(lat2) * Math.cos(lon1 - lon2));
    var gc_d = Math.round(((180.0 / Math.PI) * d) * 60 * 10) / 10;
    var gc_dm = Math.round(1.852 * gc_d * 10) / 10;

    if (Math.sin(lon2 - lon1) < 0)
        tc = Math.acos((Math.sin(lat2) - Math.sin(lat1) * Math.cos(d)) / (Math.sin(d) * Math.cos(lat1)));
    else if (lon2 - lon1 == 0)
        if (lat2 < lat1)
            tc = (Math.PI / 180) * 180;
        else
            tc = 0;
    else
        tc = 2 * Math.PI - Math.acos((Math.sin(lat2) - Math.sin(lat1) * Math.cos(d)) / (Math.sin(d) * Math.cos(lat1)));

    gc_tc = Math.round(tc * (180.0 / Math.PI) * 10) / 10;
    var winddir = ['N','NNO','NO','ONO','O','OZO','ZO','ZZO','Z','ZZW','ZW','WZW','W','WNW','NW','NNW','N'];
    var wtet = winddir[Math.round(gc_tc*16/360)];
    return gc_dm + 'Km ' + wtet + ' ('+ gc_tc + ')';
}

function locator2deg(locator) {
    if(locator.length == 6) locator += "55AA";
    if(locator.length == 8) locator += "LL";

    var i = 0;
    var loca = new Array();
    while (i < 10) {
        loca[i] = locator.charCodeAt(i) - 65;
        i++;
    }
    loca[2] += 17;
    loca[3] += 17;
    loca[6] += 17;
    loca[7] += 17;
    var lon = (loca[0] * 20 + loca[2] * 2 + loca[4] / 12 + loca[6] / 120 + loca[8] / 2880 - 180);
    var lat = (loca[1] * 10 + loca[3] + loca[5] / 24 + loca[7] / 240 + loca[9] /5760 - 90);
    var orb = {};
    orb['latitude']=lat;
    orb['longitude']=lon;
    return (orb);
}

/* if report from L on chan not 0 
          a b c d e f
          a = Number of link status messages not yet displayed
          b = Number of receive frames not yet displayed
          c = Number of send frames not yet transmitted
          d = Number of transmitted frames not yet acknowledged
          e = Number of tries on current operation
          f = Link state
              Possible link states are:
               0 = Disconnected
               1 = Link Setup
               2 = Frame Reject
               3 = Disconnect Request
               4 = Information Transfer
               5 = Reject Frame Sent
               6 = Waiting Acknowledgement
               7 = Device Busy
               8 = Remote Device Busy
               9 = Both Devices Busy
              10 = Waiting Acknowledgement and Device Busy
              11 = Waiting Acknowledgement and Remote Busy
              12 = Waiting Acknowledgement and Both Devices Busy
              13 = Reject Frame Sent and Device Busy
              14 = Reject Frame Sent and Remote Busy
              15 = Reject Frame Sent and Both Devices Busy
          NOTE 1:  Only items a and b are displayed for channel 0.
          NOTE 2:  Only states 0 - 4 are possible if version 1 is in use.
*/
