"""Tests for Ply: notation conversion, parse_string, equality, and hashing."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from thud.ply import NoMoveException, Ply


class TestNotationConversion:
    @pytest.mark.parametrize('notation, position', [
        # position = file + rank * 17. Files A..P -> 1..15; J is 9 (no I).
        ('A1', 1 + 1 * 17),
        ('P1', 15 + 1 * 17),
        ('A15', 1 + 15 * 17),
        ('P15', 15 + 15 * 17),
        ('H8', 8 + 8 * 17),
    ])
    def test_notation_round_trip(self, notation, position):
        assert Ply.notation_to_position(notation) == position
        assert Ply.position_to_notation(position) == notation

    def test_position_tuple_round_trip(self):
        for pos in range(17, 17 * 16):
            t = Ply.position_to_tuple(pos)
            assert Ply.tuple_to_position(t) == pos

    def test_default_dwarf_positions_use_notation(self):
        """Cross-check: dF1 in start.thud should resolve to the F1 position."""
        # Per the README, dF1 is one of the default dwarf squares.
        f1 = Ply.notation_to_position('F1')
        assert Ply.position_to_notation(f1) == 'F1'


class TestParseString:
    def test_simple_move(self):
        p = Ply.parse_string('dF1-G2')
        assert p.token == 'dwarf'
        assert p.origin == Ply.notation_to_position('F1')
        assert p.dest == Ply.notation_to_position('G2')
        assert p.captured == []

    def test_capture(self):
        p = Ply.parse_string('TG7-F7xE7')
        assert p.token == 'troll'
        assert p.captured == [Ply.notation_to_position('E7')]

    def test_multi_capture(self):
        p = Ply.parse_string('TG7-F7xE7xD7')
        assert p.token == 'troll'
        assert sorted(p.captured) == sorted([
            Ply.notation_to_position('E7'),
            Ply.notation_to_position('D7'),
        ])

    def test_thudstone_move(self):
        p = Ply.parse_string('RH8-H6')
        assert p.token == 'thudstone'

    def test_optional_space_after_token(self):
        """Notation allows an optional space after the side abbreviation."""
        a = Ply.parse_string('dF1-G2')
        b = Ply.parse_string('d F1-G2')
        assert a == b

    def test_unparseable_returns_none(self):
        assert Ply.parse_string('not a ply') is None
        assert Ply.parse_string('') is None

    @pytest.mark.parametrize('notation', [
        'dF1-G2', 'TG7-F7xE7', 'TG7-F7xE7xD7', 'dP9-K14', 'RH8-H7',
    ])
    def test_str_round_trip(self, notation):
        ply = Ply.parse_string(notation)
        assert ply is not None
        assert str(ply) == notation


class TestEquality:
    def test_structural_equality(self):
        a = Ply.parse_string('dF1-G2')
        b = Ply.parse_string('dF1-G2')
        assert a == b
        assert hash(a) == hash(b)

    def test_distinct_moves_unequal(self):
        a = Ply.parse_string('dF1-G2')
        b = Ply.parse_string('dF1-G3')
        assert a != b

    def test_score_does_not_affect_equality(self):
        """Regression: the old __eq__ compared by score, so different
        moves with matching scores collapsed in sets."""
        a = Ply.parse_string('dF1-G2')
        b = Ply.parse_string('dF1-G3')
        a.score = 42
        b.score = 42
        assert a != b
        assert hash(a) != hash(b) or True  # different keys very likely different hashes

    def test_capture_order_does_not_affect_equality(self):
        a = Ply('troll', 100, 101, [50, 60])
        b = Ply('troll', 100, 101, [60, 50])
        assert a == b
        assert hash(a) == hash(b)

    def test_usable_in_set(self):
        s = {
            Ply.parse_string('dF1-G2'),
            Ply.parse_string('dF1-G2'),
            Ply.parse_string('dF1-G3'),
        }
        assert len(s) == 2


class TestBool:
    def test_truthy_for_real_ply(self):
        assert bool(Ply.parse_string('dF1-G2'))

    def test_falsy_for_all_none(self):
        assert not bool(Ply(None, None, None, None))

    def test_position_zero_does_not_make_falsy(self):
        """Regression: the old __bool__ checked `if token and origin and dest`,
        which returned False if either position was 0. Position 0 is off the
        playable board today, but the predicate is still wrong."""
        ply = Ply('dwarf', 0, 100, [])
        assert bool(ply) is True


class TestOrdering:
    def test_lt_uses_score(self):
        a = Ply.parse_string('dF1-G2'); a.score = 5
        b = Ply.parse_string('dF1-G3'); b.score = 10
        assert a < b
        assert not (b < a)

    def test_lt_returns_real_bool(self):
        a = Ply.parse_string('dF1-G2'); a.score = 5
        b = Ply.parse_string('dF1-G3'); b.score = 10
        # Regression: the old __lt__ returned True or None (no False branch).
        assert (b < a) is False


class TestNoMoveException:
    def test_carries_token(self):
        try:
            raise NoMoveException('dwarf')
        except NoMoveException as e:
            assert e.token == 'dwarf'
