var events = require('events');
var uuid = require('node-uuid');
var mongojs = require('mongojs');
var server = exports;

STARTING_POSITIONS = {
  'CLASSIC': 'dF1,dG1,dJ1,dK1,dE2,dL2,dD3,dM3,dC4,dN4,dB5,dO5,dA6,dP6,dA7,dP7,dA9,dP9,dA10,dP10,dB11,dO11,dC12,dN12,dD13,dM13,dE14,dL14,dF15,dG15,dJ15,dK15,TG7,TH7,TJ7,TG8,TJ8,TG9,TH9,TJ9,RH8'
}

server.backend = function(socket_emitter) {
  var self = this;

  self.db = mongojs('gamesdb', ['games']);
  self.front_end = socket_emitter || new events.EventEmitter();

  self.create_game = function(dwarf_controller, troll_controller, callback) {
    // callback returns function(game_id) 
    var game_id = uuid.v1();
    self.db.games.save({
      game_id: game_id,
      dwarf_controller: dwarf_controller || 'human',
      troll_controller: troll_controller || 'human',
      moves: [],
      starting_positions: STARTING_POSITIONS['CLASSIC'],
      complete: false
    }, function(err, saved) {
      if (err) {
        callback(null);
      } else {
        callback(saved);
      }
    })
  }

  self.find_game = function(game_id, callback) {
    // callback returns function(game) 
    self.db.games.findOne({game_id: game_id}, function(err, game) {
      if (!err)
        callback(game);
      else
        console.error('No game found with', criteria);
    })
  }

  self.turn_to_act = function(moves) {
    return (moves.length % 2 == 0 ? 'dwarf' : 'troll')
  }

  self.query = function(moves, type, callback) {
    var start = new Date().getTime();

    if (['validate', 'next_move', 'captures'].indexOf(type) < 0)
      throw 'query type not permitted.'
    var exec = require('child_process').exec;
    var child = exec(__dirname + '/console.py ' + type);

    child.stdout.on('data', function(data) {
      var retval = data.toString('ascii').trim();
      console.info(type, moves[moves.length-1], new Date().getTime() - start, 'ms');

      if (type == 'validate')
        callback(JSON.parse(retval.toLowerCase()));
      else
        callback(retval);
    })

    child.stdin.write(moves.join('\n'));
    child.stdin.end();
  }

  self.validate_move = function(data, callback) {
    self.find_game(data.game_id, function(game) {
      var recorded_moves = game.moves;
      recorded_moves.push(data.move);

      self.query(recorded_moves, 'validate', function(is_valid) {
        if (!is_valid) {
          callback(null);
        } else {
          self.query(recorded_moves, 'captures', function(full_capstring) {
            if (full_capstring.indexOf('x') >= 0) {
              recorded_moves.pop();
              recorded_moves.push(full_capstring)
            }
            callback(full_capstring || data.move);
          })
        }
      })
    })
  }

  self.front_end.on('connection', function(socket) {
    var ip = socket['client']['conn']['remoteAddress'];
    console.log('New client connected:', ip);

    socket.on('create_game', function(data) {
      self.create_game(data.dwarf_controller, data.troll_controller, function(game) {
        if (!game) {
          console.log('Failed to provision a new gameboard for', ip);
        } else {
          console.log('Request to provision a new gameboard from', ip);
          console.log('Game ID:', game.game_id)
          socket.emit('new_game_created', {
            game_id: game.game_id,
            positions: game.starting_positions
          })
        }
      })
    })

    socket.on('attempt_move', function(data) {
      self.validate_move(data, function(validated_move) {
        console.log(data, validated_move)
        if (validated_move) {
          self.db.games.findAndModify({
            query: {game_id: data.game_id},
            update: { $push: {moves: validated_move}}
          })
          console.log('Game:', data.game_id, 'accepted move', validated_move, 'from', ip);
          socket.emit('move_accepted', {
            game_id: data.game_id,
            requested: validated_move
          })
        } else {
          console.log('Game:', data.game_id, 'rejected move', data.move, 'from', ip);
        }
      })
    });

    socket.on('wait_for_cpu', function(game_id) {
      self.find_game(game_id, function(game) {
        if (game[self.turn_to_act(game.moves) + '_controller'] == 'cpu') {
          self.query(game.moves, 'next_move', function(next_move) {
            self.db.games.findAndModify({
              query: {game_id: game_id},
              update: { $push: {moves: next_move}}
            })
            console.log('Game:', game_id, 'responded with', next_move, 'to', ip);
            socket.emit('cpu_response', {
              game_id: game_id,
              responded: next_move
            })
          })
        }
      })
    })
  })

  return self;
}
