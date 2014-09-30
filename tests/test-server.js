var thud = require('../thud');
var server = require('../server');
var async = require('async');
var test = exports;

NOTATION_VALID_REGEX = /^([T|d|R])([A-HJ-P])([0-9]+)-([A-HJ-P])([0-9]+)(.*)/;

test.tearDown = function(callback) {
  callback();
}

test.backend = function(test) {
  var events = require('events');
  var be = new server.backend();

  test.ok(be.games instanceof Object);
  test.ok(be.front_end instanceof events.EventEmitter);
  test.done();
};
