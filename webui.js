var express = require('express');
var app = express();
var http = require('http').Server(app);
var io = require('socket.io')(http);
var thud = require('./thud');

var response_options = {root: __dirname};

app.get('/', function(req, res){
  res.sendFile('index.html', response_options);
});

app.use(express.static(__dirname));

var be = server.backend(io);

process.on('SIGINT', function() {
  console.log("Caught interrupt signal; closing webui....");
  process.exit();
});

http.listen(8124, function(){
  console.log('listening on *:8124');
});
