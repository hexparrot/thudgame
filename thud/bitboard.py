"""Bitboard: a fixed-width 289-bit mask over the 17x17 Thud! board.

This is the core spatial primitive the engine builds on. Every kind of
piece-set (dwarfs, trolls, the thudstone, the playable area) is stored as
a Bitboard, so move/capture enumeration becomes bit-shift + mask, with no
per-square Python loops in the hot path.
"""


class Bitboard:
    """Fixed-width 289-bit mask over a 17x17 board.

    Bit/position convention: a board position ``p`` (0..288) corresponds to
    bit ``N - 1 - p`` of ``value``. Position 0 is the most-significant bit;
    position 288 is the least-significant bit. ``str(bb)`` is therefore a
    289-character binary string in position order (leftmost char = position 0),
    which is the form ``InfluenceMap`` and ``Gameboard.display`` rely on.

    All operations are width-safe: shifts and ``~`` mask back to the 289-bit
    field so values never go negative or grow beyond the board.
    """

    BOARD_WIDTH = 17
    N = BOARD_WIDTH * BOARD_WIDTH
    MASK = (1 << N) - 1

    __slots__ = ('value',)

    def __init__(self, positions=None):
        self.value = 0
        if positions:
            for p in positions:
                # Reject anything that isn't a real board square. Without this
                # a large negative position makes ``1 << (N-1-p)`` allocate a
                # multi-gigabyte integer (a one-message DoS via the server),
                # and a non-int blows up with a confusing TypeError deep in the
                # shift. Callers that pass untrusted input (Gameboard.is_dumb)
                # already catch ValueError/TypeError and treat it as illegal.
                if not isinstance(p, int) or not (0 <= p < Bitboard.N):
                    raise ValueError("position out of range: {!r}".format(p))
                self.value |= 1 << (Bitboard.N - 1 - p)

    def __str__(self):
        return format(self.value & Bitboard.MASK, '0{}b'.format(Bitboard.N))

    def __repr__(self):
        return 'Bitboard.create({})'.format(self.value & Bitboard.MASK)

    def __len__(self):
        return (self.value & Bitboard.MASK).bit_count()

    def __getitem__(self, key):
        if isinstance(key, slice):
            return str(self)[key]
        # Off-board indices read as unset rather than raising. token_at and
        # neighbour walks probe positions just past the edge (p < 0 or
        # p >= N); a key >= N would otherwise be a negative shift -> ValueError.
        if not (0 <= key < Bitboard.N):
            return 0
        return (self.value >> (Bitboard.N - 1 - key)) & 1

    def __iter__(self):
        v = self.value & Bitboard.MASK
        for i in range(Bitboard.N):
            yield (v >> (Bitboard.N - 1 - i)) & 1

    def __lshift__(self, other):
        return Bitboard.create((self.value << other) & Bitboard.MASK)

    def __rshift__(self, other):
        return Bitboard.create(self.value >> other)

    def __and__(self, other):
        return Bitboard.create(self.value & other.value)

    def __or__(self, other):
        return Bitboard.create(self.value | other.value)

    def __invert__(self):
        return Bitboard.create((~self.value) & Bitboard.MASK)

    def __bool__(self):
        return bool(self.value & Bitboard.MASK)

    def __eq__(self, other):
        if not isinstance(other, Bitboard):
            return NotImplemented
        return (self.value & Bitboard.MASK) == (other.value & Bitboard.MASK)

    def __hash__(self):
        return hash(self.value & Bitboard.MASK)

    def get_bits(self):
        """Yield positions (0..N-1) of set bits, in ascending order."""
        v = self.value & Bitboard.MASK
        for i in range(Bitboard.N):
            if v & (1 << (Bitboard.N - 1 - i)):
                yield i

    @staticmethod
    def create(integer):
        """Build a Bitboard from a raw integer, masked to the 289-bit field."""
        b = Bitboard()
        b.value = integer & Bitboard.MASK
        return b
