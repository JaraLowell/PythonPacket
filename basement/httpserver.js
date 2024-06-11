"use strict";
const http = require('http');
const url = require('url');
const fs = require('fs');
const path = require('path');
const port = process.argv[2] || 73;

// via
// https://stackoverflow.com/questions/16333790/node-js-quick-file-server-static-files-over-http

http.createServer(function (req, res) {
    console.log(`========= ${req.method} ${req.url} ========`);

    if(req.url == '/') req.url = '/index.html';
    if(req.url == './favicon.ico') req.url = '/favicon.ico';

    // parse URL
    const parsedUrl = url.parse(req.url);
    // extract URL path
    let pathname = 'www' + `${parsedUrl.pathname}`;
    // based on the URL path, extract the file extension. e.g. .js, .doc, ...
    const ext = path.parse(pathname).ext;
    // maps file extension to MIME typere
    const mimeType = {
        '.ico': 'image/x-icon',
        '.html': 'text/html',
        '.js': 'text/javascript',
        '.json': 'application/json',
        '.css': 'text/css',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.wav': 'audio/wav',
        '.mp3': 'audio/mpeg',
        '.svg': 'image/svg+xml',
        '.pdf': 'application/pdf',
        '.doc': 'application/msword'
    };

    const mpath = "";

    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, PUT, PATCH, DELETE');
    res.setHeader('Access-Control-Allow-Headers', 'X-Requested-With,content-type');
    res.setHeader('Access-Control-Allow-Credentials', true);

    // read file from file system
    fs.readFile(mpath + pathname, function (err, data) {
        console.log("serving ", mpath + pathname)
        // return
        if (err) {
            res.statusCode = 500;
            res.end(`Error getting the file: ${err}.`);
        } else {
            // based on the URL path, extract the file extention. e.g. .js, .doc, ...
            const ext = path.parse(pathname).ext;
            // if the file is found, set Content-type and send data
            res.setHeader('Content-type', mimeType[ext] || 'text/plain');
            res.end(data);
        }
    });
}).listen(parseInt(port));

console.log(`Server listening on port ${port}`)