"""Tests for InfluenceMap, including the regression for the array('B')
overflow bug that silently dropped subtractive influence."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from thud.bitboard import Bitboard
from thud.influence_map import InfluenceMap


class TestSymmetry:
    def test_empty_inputs_give_zero_map(self):
        imap = InfluenceMap(Bitboard(), Bitboard())
        assert all(v == 0 for v in imap.influence_map)

    def test_same_position_cancels(self):
        """An add piece and a subtract piece at the same square should
        contribute equal-and-opposite influence everywhere."""
        bb = Bitboard([Bitboard.N // 2])  # center-ish square
        imap = InfluenceMap(bb, bb)
        assert all(v == 0 for v in imap.influence_map)


class TestHitNegative:
    def test_negative_values_dont_overflow(self):
        """Regression: prior `array('B')` (unsigned bytes) raised
        OverflowError on any negative add, which a bare `except: pass`
        silently swallowed, so enemy influence was discarded entirely."""
        bb_add = Bitboard()
        bb_sub = Bitboard([8 * 17 + 8])  # center square
        imap = InfluenceMap(bb_add, bb_sub)
        # At least one cell must now hold a negative value.
        assert min(imap.influence_map) < 0

    def test_only_subtractive_produces_negative_grid(self):
        bb_sub = Bitboard([8 * 17 + 8])
        imap = InfluenceMap(Bitboard(), bb_sub)
        assert max(imap.influence_map) <= 0
        assert min(imap.influence_map) < 0


class TestHighest:
    def test_returns_empty_when_max_non_positive(self):
        # Pure subtract: max is 0 or negative -> no candidates.
        imap = InfluenceMap(Bitboard(), Bitboard([8 * 17 + 8]))
        assert imap.highest() == []

    def test_returns_single_top_for_zero_variance(self):
        bb_add = Bitboard([8 * 17 + 8])
        imap = InfluenceMap(bb_add, Bitboard())
        top = imap.highest(0)
        # The single source contributes max influence to its own square.
        # All returned positions must equal the maximum value.
        max_v = max(imap.influence_map)
        assert max_v > 0
        for p in top:
            assert imap.influence_map[p] == max_v

    def test_variance_includes_more_candidates(self):
        bb_add = Bitboard([8 * 17 + 8])
        imap = InfluenceMap(bb_add, Bitboard())
        narrow = imap.highest(0)
        wide = imap.highest(0.5)
        assert len(wide) >= len(narrow)


class TestEdges:
    def test_off_board_positions_skipped(self):
        """A piece in the dead center hits 7x7 squares; none of them
        should land on the off-board frame (rows 0/16, cols 0/16)."""
        bb = Bitboard([8 * 17 + 8])
        imap = InfluenceMap(bb, Bitboard())
        # Frame cells must remain zero.
        for c in range(17):
            assert imap.influence_map[c] == 0          # row 0
            assert imap.influence_map[16 * 17 + c] == 0  # row 16
        for r in range(17):
            assert imap.influence_map[r * 17] == 0      # col 0
            assert imap.influence_map[r * 17 + 16] == 0  # col 16
