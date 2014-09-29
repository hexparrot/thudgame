var thud = require('../thud');
var test = exports;

NOTATION_VALID_REGEX = /([T|d|R])([A-HJ-P])([0-9]+)-([A-HJ-P])([0-9]+)(.*)/;

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

test.push_notation = function(test) {
  var instance = new thud.game();

  instance.moves.push('dA6-O6');

  test.equal(instance.moves[0], 'dA6-O6');
  test.done();
}

test.get_next_move = function(test) {
  var instance = new thud.game();

  instance.moves.push('dA6-O6');
  instance.get_next_move(function(notation) {
    test.ok(notation.match(NOTATION_VALID_REGEX));
    test.done();
  })
}