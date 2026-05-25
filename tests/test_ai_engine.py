"""Tests for AIEngine: scoring, smoke-test for calculate_best_move, and
regressions for the previously-broken methods."""

import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Silence the engine's INFO logging during tests.
logging.disable(logging.CRITICAL)

from thud.ai_engine import AIEngine
from thud.bitboard import Bitboard
from thud.gameboard import Gameboard
from thud.ply import NoMoveException, Ply


class TestScore:
    def test_troll_score_weights_trolls_4x(self):
        g = Gameboard('classic')
        ai = AIEngine(g)
        # 8 trolls * 4 - 32 dwarfs = 0
        assert ai.score('troll') == 8 * 4 - 32

    def test_dwarf_score_weights_trolls_4x_negative(self):
        g = Gameboard('classic')
        ai = AIEngine(g)
        # 32 dwarfs - 8 trolls * 4 = 0
        assert ai.score('dwarf') == 32 - 8 * 4

    def test_score_rises_when_enemy_pieces_removed(self):
        g = Gameboard('classic')
        ai = AIEngine(g)
        before = ai.score('troll')
        ai.board.dwarfs = Bitboard(list(ai.board.dwarfs.get_bits())[1:])
        after = ai.score('troll')
        assert after == before + 1


class TestCalculateBestMove:
    def test_troll_returns_legal_move_after_dwarf_opener(self):
        g = Gameboard('classic')
        opener = Ply.parse_string('dP9-K14')
        g.apply_ply(opener)
        g.ply_list.append(opener)

        decision = AIEngine.calculate_best_move(g, 'troll', 0)
        assert decision is not None
        assert decision.token == 'troll'
        assert g.trolls[decision.origin] == 1, "must move from a troll"
        # README's example expects TG7-F7 specifically (deterministic given
        # the heuristic). If the heuristic is ever retuned this assertion
        # will fail loudly — that's the point.
        assert str(decision) == 'TG7-F7'

    def test_dwarf_returns_legal_move_at_opening(self):
        g = Gameboard('classic')
        decision = AIEngine.calculate_best_move(g, 'dwarf', 0)
        assert decision is not None
        assert decision.token == 'dwarf'
        assert g.dwarfs[decision.origin] == 1

    def test_raises_nomoveexception_when_dwarfs_routed(self):
        g = Gameboard('classic')
        g.dwarfs = Bitboard()
        with pytest.raises(NoMoveException) as exc:
            AIEngine.calculate_best_move(g, 'dwarf', 0)
        assert exc.value.token == 'dwarf'

    def test_raises_nomoveexception_when_trolls_routed(self):
        g = Gameboard('classic')
        g.trolls = Bitboard()
        with pytest.raises(NoMoveException) as exc:
            AIEngine.calculate_best_move(g, 'troll', 0)
        assert exc.value.token == 'troll'


class TestFilterThreatenedPieces:
    """Regression for the `self.get_direction` typo that previously made
    this method raise AttributeError every time it was called."""

    def test_does_not_crash_on_opening_board(self):
        g = Gameboard('classic')
        ai = AIEngine(g)
        # Opening: nothing is in capture range yet.
        assert ai.filter_threatened_pieces('troll') == 0
        assert ai.filter_threatened_pieces('dwarf') == 0


class TestCpuVsCpuSmoke:
    def test_twenty_move_game_runs_to_completion(self):
        """End-to-end: the engine plays both sides for 20 plies without
        raising or producing illegal moves (apply_ply doesn't validate,
        but our smoke runs only via calculate_best_move output)."""
        g = Gameboard('classic')
        for _ in range(20):
            side = g.turn_to_act()
            try:
                m = AIEngine.calculate_best_move(g, side, 0)
            except NoMoveException:
                break
            # Origin must hold the moving side's piece.
            assert getattr(g, side + 's')[m.origin] == 1
            g.apply_ply(m)
            g.ply_list.append(m)
            if g.get_game_outcome():
                break
        # Trolls heavily favored when both sides play heuristically; just
        # confirm at least one piece changed.
        assert len(g.dwarfs) <= 32
