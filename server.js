var http = require('http')
var fs = require('fs')
var static = require('node-static')

var fileServer = new static.Server('.',  { cache: false });

require('http').createServer(function (request, response) {
    request.addListener('end', function () {
      fileServer.serve(request, response)
    }).resume();
}).listen(8124);

