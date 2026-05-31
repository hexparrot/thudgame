"""Tests for Gameboard: default positions, move/cap enumeration, rules,
win conditions, and end-to-end ply replay."""

import copy
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from thud.gameboard import Gameboard
from thud.bitboard import Bitboard
from thud.ply import Ply


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestDefaultPositions:
    def test_classic_counts(self):
        g = Gameboard('classic')
        assert len(g.dwarfs) == 32
        assert len(g.trolls) == 8
        assert len(g.thudstone) == 1

    def test_kvt_counts(self):
        g = Gameboard('kvt')
        assert len(g.dwarfs) == 16
        assert len(g.trolls) == 8
        assert len(g.thudstone) == 1

    def test_klash_counts(self):
        g = Gameboard('klash')
        assert len(g.dwarfs) == 24
        assert len(g.trolls) == 0  # Trolls materialize during play.

    def test_default_positions_returns_iterable_twice(self):
        """Regression: get_default_positions used to return a `map` object,
        which silently exhausted after one iteration."""
        g = Gameboard('classic')
        positions = g.get_default_positions('troll', 'classic')
        first = list(positions)
        second = list(positions)
        assert first == second

    def test_default_positions_supports_in(self):
        g = Gameboard('classic')
        positions = g.get_default_positions('troll', 'classic')
        # G7 is one of the 8 default classic troll squares; H8 is the thudstone.
        assert Ply.notation_to_position('G7') in positions
        assert Ply.notation_to_position('H8') not in positions

    def test_unknown_token_raises(self):
        g = Gameboard('classic')
        with pytest.raises(ValueError):
            g.get_default_positions('elf', 'classic')


class TestTokenAt:
    def test_dwarf_position(self):
        g = Gameboard('classic')
        # F1 is a default dwarf square.
        assert g.token_at(Ply.notation_to_position('F1')) == 'dwarf'

    def test_troll_position(self):
        g = Gameboard('classic')
        # H8 is the thudstone in classic. Pick G7 for a troll.
        assert g.token_at(Ply.notation_to_position('G7')) == 'troll'

    def test_thudstone_position(self):
        g = Gameboard('classic')
        assert g.token_at(Ply.notation_to_position('H8')) == 'thudstone'

    def test_empty_playable_position(self):
        g = Gameboard('classic')
        # F8 is empty in the opening position.
        assert g.token_at(Ply.notation_to_position('F8')) == 'empty'


class TestTurnToAct:
    def test_dwarf_starts(self):
        g = Gameboard('classic')
        assert g.turn_to_act() == 'dwarf'

    def test_alternates(self):
        g = Gameboard('classic')
        g.ply_list.append('fake')
        assert g.turn_to_act() == 'troll'
        g.ply_list.append('fake')
        assert g.turn_to_act() == 'dwarf'


class TestFindMoves:
    def test_classic_opening_dwarf_move_count_is_stable(self):
        """Lock the opening-move count as a regression sentinel."""
        g = Gameboard('classic')
        moves = list(g.find_moves('dwarf'))
        assert len(moves) == 656

    def test_classic_opening_troll_caps_empty(self):
        """No troll can capture from the opening; dwarfs are out of reach."""
        g = Gameboard('classic')
        caps = list(g.find_caps('troll'))
        assert caps == []

    def test_all_moves_have_valid_token(self):
        g = Gameboard('classic')
        for m in g.find_moves('dwarf'):
            assert m.token == 'dwarf'

    def test_all_moves_originate_from_dwarfs(self):
        g = Gameboard('classic')
        dwarf_positions = set(g.dwarfs.get_bits())
        for m in g.find_moves('dwarf'):
            assert m.origin in dwarf_positions

    def test_all_moves_land_on_playable_empty(self):
        g = Gameboard('classic')
        occupied = set(g.occupied_squares().get_bits())
        playable = set(g.playable.get_bits())
        for m in g.find_moves('dwarf'):
            assert m.dest in playable
            assert m.dest not in occupied


class TestApplyPly:
    def test_dwarf_move_relocates_bit(self):
        g = Gameboard('classic')
        origin = Ply.notation_to_position('F1')
        dest = Ply.notation_to_position('F2')  # adjacent empty
        # F2 isn't empty in classic — pick a real legal move instead.
        # dF1-G2 is the canonical opening move.
        dest = Ply.notation_to_position('G2')
        ply = Ply('dwarf', origin, dest, [])
        g.apply_ply(ply)
        assert g.dwarfs[origin] == 0
        assert g.dwarfs[dest] == 1

    def test_troll_capture_removes_only_from_dwarf_bitboard(self):
        g = Gameboard('classic')
        # Synthesize: troll at G7 capturing dwarf at F1 (not realistic, but
        # apply_ply does no validation — we're testing the mechanic).
        f1 = Ply.notation_to_position('F1')
        g7 = Ply.notation_to_position('G7')
        f7 = Ply.notation_to_position('F7')
        ply = Ply('troll', g7, f7, [f1])
        trolls_before = len(g.trolls)
        dwarfs_before = len(g.dwarfs)
        g.apply_ply(ply)
        assert len(g.trolls) == trolls_before  # troll count unchanged
        assert len(g.dwarfs) == dwarfs_before - 1  # one captured
        assert g.dwarfs[f1] == 0

    def test_apply_ply_does_not_mutate_inputs(self):
        g = Gameboard('classic')
        origin = Ply.notation_to_position('F1')
        dest = Ply.notation_to_position('G2')
        ply = Ply('dwarf', origin, dest, [])
        ply_str_before = str(ply)
        g.apply_ply(ply)
        assert str(ply) == ply_str_before


class TestValidateMove:
    def test_legal_dwarf_opening(self):
        g = Gameboard('classic')
        origin = Ply.notation_to_position('F1')
        dest = Ply.notation_to_position('G2')
        move, cap, captured = g.validate_move(origin, dest)
        assert move is True
        assert cap is False

    def test_origin_equals_dest_is_invalid(self):
        g = Gameboard('classic')
        f1 = Ply.notation_to_position('F1')
        move, cap, captured = g.validate_move(f1, f1)
        assert move is False
        assert cap is False
        assert captured == []

    def test_off_board_origin_is_invalid(self):
        g = Gameboard('classic')
        # Position 0 is in the corner frame (off the playable area).
        f1 = Ply.notation_to_position('F1')
        move, cap, captured = g.validate_move(0, f1)
        assert move is False


class TestWinConditions:
    def test_dwarf_wins_when_trolls_routed(self):
        g = Gameboard('classic')
        g.trolls = Bitboard()
        g.ply_list.append('fake')  # make it troll's turn
        assert g.get_game_outcome() == 'dwarf'

    def test_troll_wins_when_dwarfs_routed(self):
        g = Gameboard('classic')
        g.dwarfs = Bitboard()
        # Dwarf's turn (ply_list is empty, so dwarf to act).
        assert g.get_game_outcome() == 'troll'

    def test_no_winner_in_opening_position(self):
        g = Gameboard('classic')
        assert g.get_game_outcome() is None


class TestReplayFixture:
    """Replay a real .thud fixture move-by-move."""

    def _load_plies(self, name):
        with open(os.path.join(REPO_ROOT, name)) as f:
            lines = [l.strip() for l in f if l.strip()]
        # First line is comma-delimited starting positions; skip it.
        return [Ply.parse_string(l) for l in lines if ',' not in l]

    def test_open_thud_replays_cleanly(self):
        """All 6 moves in open.thud should validate and apply without error."""
        plies = self._load_plies('open.thud')
        assert len(plies) >= 6
        g = Gameboard('classic')
        for ply in plies:
            valid = g.validate_move(ply.origin, ply.dest)
            assert valid[0] or valid[1], "ply rejected: {}".format(ply)
            g.apply_ply(ply)
            g.ply_list.append(ply)
        # The fixture includes capture plies — pieces removed accordingly.
        assert len(g.dwarfs) < 32  # at least one dwarf captured


def _pos(notation):
    return Ply.notation_to_position(notation)


def _board(dwarfs=(), trolls=()):
    """A classic board cleared of its default armies (thudstone stays at H8).

    Scenarios are built on the fully-playable center row (rank 8, files A-P)
    plus one diagonal, so every square used is on the octagon.
    """
    g = Gameboard('classic')
    g.dwarfs = Bitboard([_pos(n) for n in dwarfs])
    g.trolls = Bitboard([_pos(n) for n in trolls])
    return g


class TestClassicCaptureRules:
    """Lock the canonical classic mechanics: dwarf 'throw' line-length,
    conditional troll 'shove' capture, multi-capture, and stone-blocking.

    These are the rules the deliverable's 'flawless classic' bar rests on.
    Each asserts the exact (move, cap, captured) tuple from validate_move;
    the expected values were verified empirically against the engine.
    """

    def test_dwarf_throws_one_adjacent_troll(self):
        # A lone dwarf throws itself one square onto an adjacent troll.
        g = _board(dwarfs=['D8'], trolls=['C8'])
        assert g.validate_move(_pos('D8'), _pos('C8')) == (False, True, [_pos('C8')])

    def test_single_dwarf_cannot_throw_two(self):
        # Throwing two squares needs a backing line of two dwarfs; one can't.
        g = _board(dwarfs=['E8'], trolls=['C8'])
        assert g.validate_move(_pos('E8'), _pos('C8')) == (False, False, [])

    def test_two_dwarf_line_throws_two(self):
        # E8 (front) + F8 (backer) is a line of 2, so the front throws 2.
        g = _board(dwarfs=['E8', 'F8'], trolls=['C8'])
        assert g.validate_move(_pos('E8'), _pos('C8')) == (False, True, [_pos('C8')])

    def test_troll_shove_captures_on_single_step(self):
        # A one-square troll move that lands beside a dwarf is a shove of
        # length 1: it both moves and captures the adjacent dwarf.
        g = _board(dwarfs=['C8'], trolls=['E8'])
        assert g.validate_move(_pos('E8'), _pos('D8')) == (True, True, [_pos('C8')])

    def test_troll_move_not_adjacent_does_not_capture(self):
        # Same move, but no dwarf adjacent to the landing square -> move only.
        g = _board(dwarfs=['L8'], trolls=['E8'])
        assert g.validate_move(_pos('E8'), _pos('D8')) == (True, False, [])

    def test_troll_captures_multiple_adjacent_dwarfs(self):
        # A shove removes *all* dwarfs adjacent to the landing square.
        g = _board(dwarfs=['C8', 'D9'], trolls=['E8'])
        move, cap, captured = g.validate_move(_pos('E8'), _pos('D8'))
        assert move is True and cap is True
        assert sorted(captured) == sorted([_pos('C8'), _pos('D9')])

    def test_thudstone_blocks_dwarf_line_move(self):
        # The H8 stone sits between F8 and J8; the dwarf cannot move across it.
        g = _board(dwarfs=['F8'])
        assert g.validate_move(_pos('F8'), _pos('J8')) == (False, False, [])

    def test_troll_cannot_move_two_squares_without_a_shove(self):
        # Trolls step one square (like a king); two squares needs a troll line.
        g = _board(trolls=['E8'])
        assert g.validate_move(_pos('E8'), _pos('C8')) == (False, False, [])

    def test_dwarf_throws_one_diagonally(self):
        # Diagonals are core (dwarfs move like queens); confirm the throw
        # generalizes off the orthogonal axis.
        g = _board(dwarfs=['D4'], trolls=['E5'])
        assert g.validate_move(_pos('D4'), _pos('E5')) == (False, True, [_pos('E5')])
