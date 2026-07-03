"""Headless self-play driver for the Thud! engine.

The canonical entry point for AI-vs-AI games — engine tuning and ML data
generation. Unlike ``gui.py``'s ``simulate_game`` it has no Tk dependency and
decides games with :meth:`Gameboard.result`, a *scored, always-terminating*
outcome, so a game can never hang. Move selection is deterministic for a given
``seed`` (see :func:`thud.ai_engine.seed`).

    from thud import selfplay
    r = selfplay.play_game('classic', seed=0)
    # -> {'winner': 'troll', 'score': 20, 'reason': 'win', 'plies': 62, ...}
"""

from . import ai_engine
from .ai_engine import AIEngine
from .gameboard import DEFAULT_MAX_PLIES, Gameboard
from .ply import NoMoveException


def play_game(ruleset='classic', seed=None, max_plies=DEFAULT_MAX_PLIES,
              lookahead=0):
    """Play one AI-vs-AI game; return a scored result dict.

    Returns ``{'winner', 'score', 'reason', 'plies', 'ply_list'}``. The first
    three come from :meth:`Gameboard.result`: winner is
    'dwarf' / 'troll' / 'draw', score is the troll-perspective material
    differential (``4*trolls - dwarfs``), reason is 'win' / 'no-move' /
    'cutoff'. Deterministic for a fixed ``seed``.
    """
    if seed is not None:
        ai_engine.seed(seed)
    board = Gameboard(ruleset)

    def finish(term):
        return {**term, 'plies': len(board.ply_list),
                'ply_list': list(board.ply_list)}

    while True:
        term = board.result(max_plies=max_plies)
        if term:
            return finish(term)
        side = board.turn_to_act()
        try:
            ply = AIEngine.calculate_best_move(board, side, lookahead)
        except NoMoveException:
            # result() said the side had a legal move but the chooser gave
            # up; decide on material, matching result()'s 'no-move' terminal.
            return finish(board._scored_terminal('no-move'))
        board.apply_ply(ply)
        board.ply_list.append(ply)


def play_set(games=10, ruleset='classic', base_seed=0, **kw):
    """Play ``games`` games with seeds ``base_seed..base_seed+games-1``.

    Returns a list of result dicts from :func:`play_game`.
    """
    return [play_game(ruleset=ruleset, seed=base_seed + i, **kw)
            for i in range(games)]
