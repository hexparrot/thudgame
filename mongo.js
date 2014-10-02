var mongojs = require('mongojs');

var db = mongojs('mydb', ['games']);

db.games.save({
		game_id: '12345',
		dwarf_controller: "human",
		troll_controller: "human",
		moves: [],
		complete: false
	}, function(err, saved) {
  	if( err || !saved ) console.log("game not saved");
  		else console.log("game saved");
});