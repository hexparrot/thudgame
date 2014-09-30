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

    match.query('validate', function(is_valid) {
      if (!is_valid) {
        console.log(game_id, 'move rejected:', notation)
        match.moves.pop();
        socket.emit('move_rejected', {
          requested: notation,
          responded: null
        })
      } else {
        match.query('next_move', function(next_move) {
          console.log(game_id, 'move accepted:', notation);
          console.log(game_id, 'responds with:', next_move);
          match.moves.push(next_move);
          socket.emit('move_accepted', {
            requested: notation,
            responded: next_move
          })   
        })
  
      }
    })
  })
})

