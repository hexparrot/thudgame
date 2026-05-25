"""Ply — one half-move in Thud!, plus board-notation helpers.

A ``Ply`` carries the side moving (``token``), the origin and destination
squares (as 0..288 integer positions), and a list of captured-piece
positions. ``Ply.parse_string`` and ``str(ply)`` round-trip the textual
game-notation used in .thud save files.

``NoMoveException`` lives here because it's a game-primitive concern (no
legal moves exist for a side) rather than something specific to one engine.
"""

import math
import re


class NoMoveException(Exception):
    """Raised when the side to act has no legal move."""

    def __init__(self, token):
        super().__init__(token)
        self.token = token


class Ply:
    """One half-move: token, origin, destination, and any captures.

    ``score`` is a scratch field populated by ``AIEngine.filter_best``;
    it is intentionally not part of structural equality.
    """

    abbr = {'dwarf': 'd', 'd': 'd',
            'troll': 'T', 'T': 'T',
            'thudstone': 'R', 'R': 'R'}

    to_letter = {1: 'A', 2: 'B', 3: 'C', 4: 'D', 5: 'E',
                 6: 'F', 7: 'G', 8: 'H', 9: 'J', 10: 'K',
                 11: 'L', 12: 'M', 13: 'N', 14: 'O', 15: 'P'}

    to_number = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5,
                 'F': 6, 'G': 7, 'H': 8, 'J': 9, 'K': 10,
                 'L': 11, 'M': 12, 'N': 13, 'O': 14, 'P': 15}

    def __init__(self, token, origin, dest, captured=None):
        self.token = token
        self.origin = origin
        self.dest = dest
        self.captured = list(captured) if captured else []
        self.score = -100

    def _key(self):
        """Structural-equality key: (token, origin, dest, sorted captured)."""
        return (self.token, self.origin, self.dest, tuple(sorted(self.captured)))

    def __str__(self):
        cap_string = ''.join('x' + self.position_to_notation(cap)
                             for cap in self.captured)
        return (str(self.abbr.get(self.token))
                + str(self.position_to_notation(self.origin)) + '-'
                + str(self.position_to_notation(self.dest))
                + cap_string)

    def __repr__(self):
        return "Ply({!r}, {!r}, {!r}, {!r})".format(
            self.token, self.origin, self.dest, self.captured)

    def __eq__(self, other):
        if not isinstance(other, Ply):
            return NotImplemented
        return self._key() == other._key()

    def __hash__(self):
        return hash(self._key())

    def __lt__(self, other):
        if not isinstance(other, Ply):
            return NotImplemented
        return self.score < other.score

    def __bool__(self):
        return (self.token is not None
                and self.origin is not None
                and self.dest is not None)

    @staticmethod
    def position_to_tuple(position):
        """Integer position -> (file, rank). Inverse of tuple_to_position."""
        rank = position // 17
        file = position - (rank * 17)
        return (file, rank)

    @staticmethod
    def position_to_notation(position):
        """Integer position -> 'A1'-style notation."""
        conv = Ply.position_to_tuple(position)
        file = Ply.to_letter.get(int(conv[0]))
        rank = str(int(conv[1]))
        return file + rank

    @staticmethod
    def notation_to_position(notation):
        """'A1'-style notation -> integer position."""
        file = Ply.to_number.get(notation[0])
        return file + int(notation[1:]) * 17

    @staticmethod
    def tuple_to_position(notation):
        """(file, rank) -> integer position. Inverse of position_to_tuple."""
        return notation[1] * 17 + notation[0]

    @staticmethod
    def calc_pythagoras(a_pos, b_pos):
        """Euclidean distance between two integer positions."""
        a = Ply.position_to_tuple(a_pos)
        b = Ply.position_to_tuple(b_pos)
        return math.sqrt(pow(a[0] - b[0], 2) + pow(a[1] - b[1], 2))

    _SIDE_FROM_ABBR = {'d': 'dwarf', 'T': 'troll', 'R': 'thudstone'}
    _PLY_NOTATION_RE = re.compile(
        r"([TdR]) ?([A-HJ-P])([0-9]+)-([A-HJ-P])([0-9]+)(.*)"
    )

    @staticmethod
    def parse_string(ply_notation):
        """Parse one ply of game notation (e.g. 'dF1-G2', 'TG7-F7xE7').

        Returns ``None`` if the string does not match the ply grammar.
        """
        m = Ply._PLY_NOTATION_RE.search(str(ply_notation))
        if not m:
            return None
        captures = [Ply.notation_to_position(c) for c in m.group(6).split('x')[1:]]
        return Ply(
            Ply._SIDE_FROM_ABBR.get(m.group(1)),
            Ply.notation_to_position(m.group(2) + m.group(3)),
            Ply.notation_to_position(m.group(4) + m.group(5)),
            captures,
        )
