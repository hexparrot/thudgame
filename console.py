#!/usr/bin/env python3
"""Headless CLI for the Thud! engine.

Reads a .thud game file from stdin (initial-position line followed by
one ply per line) and answers a question about that game:

    python3 console.py next_move < game.thud   # AI's best move for whoever is up
    python3 console.py validate  < game.thud   # 'True' if every ply is legal
    python3 console.py turn      < game.thud   # 'dwarf' or 'troll' — side to act
    python3 console.py captures  < game.thud   # longest capture from the last move

Exits 0 always; status is conveyed through stdout. Engine reasoning is
logged to stderr by ``thud.ai_engine.ai_log``.
"""

__author__ = "William Dizon"
__license__ = "MIT License"
__version__ = "1.8.0"
__email__ = "wdchromium@gmail.com"

import itertools
import sys

from thud import AIEngine, Gameboard, Ply

LOOKAHEAD = 3
USAGE = "usage: console.py {next_move|validate|turn|captures} < game.thud"


def replay(ply_lines):
    """Apply every ply in ``ply_lines`` to a fresh classic Gameboard.

    Raises RuntimeError(ply_index, ply_str) on the first illegal move
    or side-out-of-turn. The leading comma-delimited piece-list line
    (default positions) is skipped.
    """
    board = Gameboard('classic')
    turn = itertools.cycle(['dwarf', 'troll'])

    for raw in ply_lines:
        move = raw.strip()
        if not move or ',' in move:
            # comma-delimited line = saved starting position; ignore.
            continue

        ply = Ply.parse_string(move)
        if not ply:
            # First unparseable line ends the game stream (consistent with
            # the prior implementation's behavior).
            if not board.ply_list:
                continue
            break

        expected_side = next(turn)
        if ply.token != expected_side:
            raise RuntimeError(len(board.ply_list), move)

        valid = board.validate_move(ply.origin, ply.dest)
        if valid[0] or valid[1]:
            board.apply_ply(ply)
            board.ply_list.append(ply)
        else:
            raise RuntimeError(len(board.ply_list), move)

    return board


def cmd_next_move(ply_lines):
    board = replay(ply_lines)
    return str(AIEngine.calculate_best_move(board, board.turn_to_act(), LOOKAHEAD))


def cmd_validate(ply_lines):
    try:
        replay(ply_lines)
    except RuntimeError:
        return 'False'
    return 'True'


def cmd_turn(ply_lines):
    return replay(ply_lines).turn_to_act()


def cmd_captures(ply_lines):
    """Return the longest capture string from this turn that begins at the
    same square as the last move. Empty string if none."""
    if not ply_lines:
        return ''
    last_move = ply_lines[-1].strip()
    board = replay(ply_lines[:-1])
    candidates = sorted(
        (str(p) for p in board.find_caps(board.turn_to_act())),
        key=len, reverse=True,
    )
    for p in candidates:
        if last_move in p:
            return p
    return ''


COMMANDS = {
    'next_move': cmd_next_move,
    'validate': cmd_validate,
    'turn': cmd_turn,
    'captures': cmd_captures,
}


def main(argv):
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print(USAGE, file=sys.stderr)
        return 2

    ply_lines = sys.stdin.readlines()
    try:
        result = COMMANDS[argv[1]](ply_lines)
    except RuntimeError as e:
        if argv[1] == 'next_move':
            print('{}:{}'.format(e.args[0], e.args[1]))
        elif argv[1] == 'validate':
            print('False')
        return 0

    if result is not None:
        print(result)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
