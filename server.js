var thud = require('./thud');
var events = require('events');
var uuid = require('node-uuid');
var server = exports;

server.backend = function(socket_emitter) {
  var self = this;

  self.games = {}
  self.front_end = socket_emitter || new events.EventEmitter();

  self.create_game = function(sides, callback) {
    var game_id = uuid.v1();
    self.games[game_id] = new thud.game(sides);
    callback(game_id);
  }

  self.front_end.on('connection', function(socket) {
    var ip = socket['client']['conn']['remoteAddress'];
    console.log('Starting new game with client:', ip);

    socket.on('create_game', function(sides) {
      self.create_game(sides, function(game_id) {
        socket.emit('new_game_created', {
          game: game_id,
          positions: thud.STARTING_POSITIONS['CLASSIC']
        })
      })
    })

    socket.on('attempt_move', function(data){
      var game_id = data.game;
      var instance = self.games[game_id];
      
      instance.push(data.move, function(is_valid) {
        if (is_valid) {
          console.log('Game:', game_id, 'accepted move', data.move, 'from', ip);
          socket.emit('move_accepted', {
            game: game_id,
            requested: data.move
          })

          instance.query('next_move', function(next_move) {
            console.log('Game:', game_id, 'responds with', next_move, 'to', ip);
            instance.moves.push(next_move);
            socket.emit('cpu_response', {
              game: game_id,
              responded: next_move
            })
          })

        } else {
          console.log('Game:', game_id, 'rejected move', data.move, 'from', ip);
          socket.emit('move_rejected', {
            game: game_id,
            requested: data.move
          })
        }
      })
    })
  })

  return self;
}
