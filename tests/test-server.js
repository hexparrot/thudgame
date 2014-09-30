var thud = require('../thud');
var server = require('../server');
var async = require('async');
var events = require('events');
var test = exports;

NOTATION_VALID_REGEX = /^([T|d|R])([A-HJ-P])([0-9]+)-([A-HJ-P])([0-9]+)(.*)/;

test.tearDown = function(callback) {
  callback();
}

test.backend = function(test) {
  var be = new server.backend();
  
  test.ok(be.games instanceof Object);
  test.ok(be.front_end instanceof events.EventEmitter);
  test.done();
};

test.create_game = function(test) {
  var be = new server.backend();
  be.front_end.of = function() { return new events.EventEmitter; }
  be.front_end.on = function(event, fn) { return new events.EventEmitter; }

  be.create_game(function(game_id) {
    test.equal(Object.keys(be.games).length, 1);
    test.ok(be.games[game_id].instance instanceof thud.game);
    test.ok(be.games[game_id].nsp instanceof events.EventEmitter);
    test.done();
  })
}
