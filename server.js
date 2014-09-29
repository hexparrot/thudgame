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
  var game_id = socket['client']['conn']['id'];
  console.log('Starting new game with client:', 
              socket['client']['conn']['remoteAddress'],
              '\nGame ID:',
              game_id);
  
  var match = new thud.game();
  socket.emit('start_classic_game', thud.STARTING_POSITIONS['CLASSIC']);

  socket.on('attempt_move', function(notation) {
    console.log(game_id, 'requesting move:', notation);
    match.moves.push(notation);

    match.get_next_move(function(next_move) {
      if (next_move.indexOf('invalid_move') >= 0) {
        console.log(game_id, 'move rejected:', notation)
        match.moves.pop();
        socket.emit('move_rejected', {
          requested_move: notation,
          responded_move: null
        })
      } else {
        console.log(game_id, 'move accepted:', notation);
        console.log(game_id, 'responds with:', next_move);
        match.moves.push(next_move);
        socket.emit('move_accepted', {
          requested_move: notation,
          responded_move: next_move
        })
      }
    });
  })
})

