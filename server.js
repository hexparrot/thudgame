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

process.on('SIGINT', function() {
  console.log("Caught interrupt signal; closing webui....");
  process.exit();
});

http.listen(8124, function(){
  console.log('listening on *:8124');
});



io.on('connect', function(socket) {
  console.log('starting new game');
  var match = new thud.game();

  socket.emit('start_new_classic', thud.STARTING_POSITIONS['CLASSIC']);

  socket.on('attempt_move', function(notation) {
    console.log('requesting move', notation);
    match.moves.push(notation);

    match.get_next_move(function(next_move) {
      if (next_move.indexOf('invalid_move') == -1) {
        console.log('valid move, replying:', next_move)
        match.moves.push(next_move);
        socket.emit('valid_move', {
          requested_move: notation,
          responded_move: next_move
        })
      } else {
        console.log('invalid_move')
        match.moves.pop();
        socket.emit('invalid_move', {
          requested_move: notation,
          responded_move: null
        })
      }

    });
    
  })
})

