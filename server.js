var thud = require('./thud');
var events = require('events');
var uuid = require('node-uuid');
var server = exports;

server.backend = function(socket_emitter) {
  var self = this;
  
  self.games = {}
  self.front_end = socket_emitter || new events.EventEmitter();
}


