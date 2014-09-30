var thud = exports;

thud.STARTING_POSITIONS = {
	'CLASSIC': 'dF1,dG1,dJ1,dK1,dE2,dL2,dD3,dM3,dC4,dN4,dB5,dO5,dA6,dP6,dA7,dP7,dA9,dP9,dA10,dP10,dB11,dO11,dC12,dN12,dD13,dM13,dE14,dL14,dF15,dG15,dJ15,dK15,TG7,TH7,TJ7,TG8,TJ8,TG9,TH9,TJ9,RH8'
}

thud.game = function(options) {
  var self = this;

  options = options || {};
  self.controller = {
    dwarf: options.dwarf || 'human',
    troll: options.troll || 'human'
  }

  self.moves = [];

  self.positions = function(callback) {
    callback(thud.STARTING_POSITIONS['CLASSIC']);
  }

  self.push = function(notation, callback) {
    self.moves.push(notation);

    self.query('validate', function(is_valid) {
      is_valid = JSON.parse(is_valid.toLowerCase());
      
      if (!is_valid)
        self.moves.pop();

      callback(is_valid);
    })
  }

  self.whose_turn = function() {
    if (self.moves.length % 2 == 0)
      return 'dwarf'
    else
      return 'troll'
  }

  self.query = function(type, callback) {
    if (['validate', 'next_move'].indexOf(type) < 0)
      throw 'query type not permitted.'
    var exec = require('child_process').exec;
    var child = exec(__dirname + '/console.py ' + type);

    child.stdout.on('data', function(data) {
      callback(data.toString('ascii').trim());
    })

    child.stdin.write(self.moves.join('\n'));
    child.stdin.end();
  }
}