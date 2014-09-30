var thud = require('../thud');
var async = require('async');
var test = exports;

NOTATION_VALID_REGEX = /^([T|d|R])([A-HJ-P])([0-9]+)-([A-HJ-P])([0-9]+)(.*)/;

test.tearDown = function(callback) {
  callback();
}

test.start_new_game = function(test) {
  var instance = new thud.game();

  instance.positions(function(positions) {
  	test.equal(positions, thud.STARTING_POSITIONS['CLASSIC']);
    test.done();
  })
};

test.push = function(test) {
  async.series([
    function(callback) {
      var instance = new thud.game();
      instance.push('dA6-O6', function(is_valid) {
        test.ok(is_valid);
        test.equal(instance.moves.length, 1);
        callback(null);
      })
    },
    function(callback) {
      var instance = new thud.game();
      instance.push('dA6-A15', function(is_valid) {
        test.ok(!is_valid);
        test.equal(instance.moves.length, 0);
        callback(null);
      })
    }
  ], function(err, results) {
    test.done();
  })

}

test.get_next_move = function(test) {
  var instance = new thud.game();

  instance.moves.push('dA6-O6');
  instance.query('next_move', function(notation) {
    test.equal(notation[0], 'T');
    test.ok(notation.match(NOTATION_VALID_REGEX));
    test.done();
  })
}

test.get_next_move_midgame = function(test) {
  var instance = new thud.game();

  instance.moves.push('dA6-O6');
  instance.moves.push('TH9-J10');
  instance.moves.push('dF15-O7');

  test.equal(instance.moves.length, 3);

  async.series([
    function(callback) {
      instance.query('next_move', function(notation) {
        test.equal(notation[0], 'T');
        instance.moves.push(notation);
        callback(null);
      })
    },
    function(callback) {
      instance.query('next_move', function(notation) {
        test.equal(notation[0], 'd');
        instance.moves.push(notation);
        callback(null);
      })
    }
  ], function(err, results) {
    test.equal(instance.moves.length, 5);
    test.done();
  })
}

test.invalid_move = function(test) {
  var instance = new thud.game();
  instance.moves.push('dA6-O6');
  instance.moves.push('TH9-J10');
  instance.moves.push('dO6-A15');

  instance.query('validate', function(notation) {
    test.equal(notation, 'False');
    test.done();
  })
}