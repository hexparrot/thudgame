"""Tests for the Bitboard class.

The board is a 17x17 grid (N = 289 positions). Position p sets bit
``N - 1 - p`` of the underlying integer; str(bb) is a 289-character
binary string where the leftmost char is position 0.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from thud.bitboard import Bitboard


N = Bitboard.N
MASK = Bitboard.MASK


class TestConstruction:
    def test_empty_construction(self):
        bb = Bitboard()
        assert bb.value == 0
        assert len(bb) == 0
        assert not bb

    def test_empty_list_construction(self):
        assert Bitboard([]).value == 0

    def test_none_construction(self):
        assert Bitboard(None).value == 0

    def test_single_position_zero_sets_msb(self):
        bb = Bitboard([0])
        assert bb.value == 1 << (N - 1)
        assert len(bb) == 1

    def test_single_position_last_sets_lsb(self):
        bb = Bitboard([N - 1])
        assert bb.value == 1
        assert len(bb) == 1

    def test_multiple_positions_or_together(self):
        bb = Bitboard([0, 5, 100, 288])
        expected = (1 << 288) | (1 << 283) | (1 << 188) | (1 << 0)
        assert bb.value == expected
        assert len(bb) == 4

    def test_mutable_default_isolation(self):
        """Constructing twice must not share state (regression for the old
        `positions=[]` mutable default)."""
        a = Bitboard()
        b = Bitboard()
        a.value |= 1
        assert b.value == 0


class TestString:
    def test_str_length_is_n(self):
        assert len(str(Bitboard())) == N

    def test_str_all_zeros_for_empty(self):
        assert str(Bitboard()) == '0' * N

    def test_str_leftmost_is_position_zero(self):
        bb = Bitboard([0])
        s = str(bb)
        assert s[0] == '1'
        assert s[1:] == '0' * (N - 1)

    def test_str_rightmost_is_position_last(self):
        bb = Bitboard([N - 1])
        s = str(bb)
        assert s[-1] == '1'
        assert s[:-1] == '0' * (N - 1)

    def test_str_arbitrary_positions(self):
        positions = [0, 17, 18, 144, 287, 288]
        bb = Bitboard(positions)
        s = str(bb)
        for p in positions:
            assert s[p] == '1', "expected '1' at position {}".format(p)
        for p in range(N):
            if p not in positions:
                assert s[p] == '0'


class TestLen:
    def test_len_empty(self):
        assert len(Bitboard()) == 0

    def test_len_full(self):
        bb = Bitboard.create(MASK)
        assert len(bb) == N

    @pytest.mark.parametrize('positions', [
        [0], [N - 1], [0, N - 1],
        list(range(0, N, 10)),
        [42, 100, 200, 288],
    ])
    def test_len_matches_positions(self, positions):
        assert len(Bitboard(positions)) == len(positions)


class TestGetitem:
    def test_getitem_returns_int(self):
        bb = Bitboard([5])
        assert isinstance(bb[5], int)
        assert isinstance(bb[6], int)

    def test_getitem_set_positions_return_one(self):
        positions = [0, 7, 42, 200, 288]
        bb = Bitboard(positions)
        for p in positions:
            assert bb[p] == 1

    def test_getitem_unset_positions_return_zero(self):
        bb = Bitboard([5])
        for p in range(N):
            if p != 5:
                assert bb[p] == 0

    def test_getitem_truthiness_matches_value(self):
        """Regression: old __getitem__ returned '0'/'1' strings; bool('0')
        is True, which silently broke `if bb[pos]:` checks (notably the
        thudstone-move adjacency count in Gameboard)."""
        bb = Bitboard([5])
        assert bool(bb[5]) is True
        assert bool(bb[6]) is False

    def test_getitem_slice_returns_str(self):
        """Slices fall through to str() for back-compat."""
        bb = Bitboard([0, 5])
        assert bb[0:6] == '100001'


class TestIteration:
    def test_iter_yields_n_values(self):
        bb = Bitboard([0, 5])
        values = list(bb)
        assert len(values) == N

    def test_iter_values_at_set_positions(self):
        positions = [0, 5, 100, 288]
        bb = Bitboard(positions)
        values = list(bb)
        for p in positions:
            assert values[p] == 1

    def test_iter_is_fresh_each_call(self):
        """Regression: the old __iter__ was the instance itself with
        mutable state, so a second iteration started from wherever the
        first stopped (or worse, from mid-state if the first didn't run
        to completion)."""
        bb = Bitboard([0, 288])
        first = list(bb)
        second = list(bb)
        assert first == second

    def test_nested_iteration(self):
        """Regression for the same stateful __iter__: nested loops would
        share `self.x` and silently corrupt each other."""
        bb = Bitboard([0, 100, 288])
        pairs = []
        for outer in bb:
            for inner in bb:
                pairs.append((outer, inner))
        assert len(pairs) == N * N


class TestShifts:
    def test_rshift_moves_position_forward(self):
        """value >> d corresponds to positions moving from p to p+d in the
        position-numbering convention."""
        bb = Bitboard([5])
        assert (bb >> 1) == Bitboard([6])

    def test_lshift_moves_position_backward(self):
        bb = Bitboard([5])
        assert (bb << 1) == Bitboard([4])

    def test_rshift_zero_is_identity(self):
        bb = Bitboard([0, 100, 288])
        assert (bb >> 0) == bb

    def test_lshift_off_top_is_masked(self):
        """Position 0 shifted left should drop off (no negative bits)."""
        bb = Bitboard([0])
        shifted = bb << 1
        assert shifted.value == 0
        assert len(shifted) == 0


class TestBoolean:
    def test_and_intersection(self):
        a = Bitboard([0, 5, 100])
        b = Bitboard([5, 100, 200])
        assert (a & b) == Bitboard([5, 100])

    def test_and_disjoint_is_empty(self):
        a = Bitboard([0, 5])
        b = Bitboard([10, 20])
        assert (a & b) == Bitboard()

    def test_or_union(self):
        a = Bitboard([0, 5])
        b = Bitboard([5, 10])
        assert (a | b) == Bitboard([0, 5, 10])

    def test_or_with_empty_is_identity(self):
        a = Bitboard([0, 5, 288])
        assert (a | Bitboard()) == a


class TestInvert:
    """Regression tests for the rewritten ~ operator. The old implementation
    used Python's ~ on an arbitrary-precision int, producing a negative
    number, then tried to reconstruct a 289-char string with an ad-hoc
    two's-complement-ish substitution that forced the trailing bit on. The
    new implementation masks back to the 289-bit field."""

    def test_invert_empty_is_full(self):
        assert (~Bitboard()).value == MASK
        assert len(~Bitboard()) == N

    def test_invert_full_is_empty(self):
        full = Bitboard.create(MASK)
        assert (~full).value == 0
        assert len(~full) == 0

    def test_invert_flips_bit_count(self):
        positions = [0, 5, 100, 288]
        bb = Bitboard(positions)
        assert len(~bb) == N - len(bb)

    def test_invert_union_with_self_is_full(self):
        bb = Bitboard([0, 5, 100, 288])
        assert (bb | ~bb) == Bitboard.create(MASK)

    def test_invert_intersect_with_self_is_empty(self):
        bb = Bitboard([0, 5, 100, 288])
        assert (bb & ~bb) == Bitboard()

    def test_invert_is_involution(self):
        bb = Bitboard([7, 42, 200])
        assert ~~bb == bb

    def test_invert_does_not_force_trailing_bit(self):
        """The old __str__ had `s[:-1] + '1'` in the negative-value branch,
        forcing the last bit on regardless of input. Verify the new ~ leaves
        the last bit correctly cleared when the original had it set."""
        bb = Bitboard([N - 1])  # only the last bit is set
        inv = ~bb
        assert inv[N - 1] == 0
        assert len(inv) == N - 1


class TestGetBits:
    def test_get_bits_empty(self):
        assert list(Bitboard().get_bits()) == []

    def test_get_bits_round_trip(self):
        positions = [0, 5, 100, 144, 200, 288]
        bb = Bitboard(positions)
        assert list(bb.get_bits()) == sorted(positions)

    def test_get_bits_full(self):
        bb = Bitboard.create(MASK)
        assert list(bb.get_bits()) == list(range(N))


class TestEqualityAndHash:
    def test_equal_construction(self):
        assert Bitboard([0, 5]) == Bitboard([5, 0])

    def test_unequal(self):
        assert Bitboard([0]) != Bitboard([1])

    def test_hash_equal_for_equal_boards(self):
        assert hash(Bitboard([0, 5])) == hash(Bitboard([5, 0]))

    def test_usable_in_set(self):
        s = {Bitboard([0]), Bitboard([0]), Bitboard([1])}
        assert len(s) == 2

    def test_usable_as_dict_key(self):
        d = {Bitboard([0]): 'a', Bitboard([1]): 'b'}
        assert d[Bitboard([0])] == 'a'
        assert d[Bitboard([1])] == 'b'

    def test_eq_with_non_bitboard_returns_notimplemented(self):
        # Python falls back to identity comparison, yielding False.
        assert (Bitboard([0]) == 'foo') is False


class TestCreate:
    def test_create_round_trip(self):
        bb = Bitboard([0, 5, 288])
        assert Bitboard.create(bb.value) == bb

    def test_create_masks_oversize_input(self):
        # An integer with bits set above position N-1 should be masked off
        # rather than producing an out-of-range bitboard.
        oversize = (1 << (N + 5)) | 1
        bb = Bitboard.create(oversize)
        assert bb.value == 1
        assert len(bb) == 1

    def test_create_zero(self):
        bb = Bitboard.create(0)
        assert bb.value == 0
        assert not bb
