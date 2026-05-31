"""InfluenceMap — signed score grid summarizing piece pressure on the board.

Each piece contributes a 7x7 splash of influence (positive for the
``add`` side, negative for the ``subtract`` side) falling off linearly
with Chebyshev distance from its square. ``AIEngine`` uses this to find
dense friendly clusters worth flocking toward.
"""

import itertools


class InfluenceMap:
    """A 17x17 grid of signed integer influence scores."""

    BOARD_WIDTH = 17

    def __init__(self, add, subtract):
        # Plain list, not array('B'): unsigned bytes raised OverflowError
        # on negative deltas, which the prior bare `except: pass` in hit()
        # then silently swallowed — so all enemy influence was discarded.
        self.influence_map = [0] * (InfluenceMap.BOARD_WIDTH ** 2)

        for i, c in enumerate(str(add)):
            if c == '1':
                self.hit(i, 6)
        for i, c in enumerate(str(subtract)):
            if c == '1':
                self.hit(i, -6)

    def __getitem__(self, key):
        return self.influence_map[key]

    def hit(self, pos, value=6):
        """Add a falloff splash of ``value`` centered at ``pos``."""
        W = InfluenceMap.BOARD_WIDTH
        for di, dj in itertools.product([-3, -2, -1, 0, 1, 2, 3], repeat=2):
            position = pos + di + dj * W
            # Skip non-playable edge columns/rows (the WxW grid frames a
            # (W-2)x(W-2) playable area; the first/last row and column are
            # off-board).
            if (position < W or position >= W * (W - 1)
                    or position % W == 0 or position % W == W - 1):
                continue
            self.influence_map[position] += value // max(abs(di), abs(dj), 1)

    def highest(self, variance_pct=0):
        """Return positions whose influence is within ``variance_pct`` of the max."""
        top = max(self.influence_map)
        if top <= 0:
            return []
        threshold = top * (1 - variance_pct)
        return [i for i, v in enumerate(self.influence_map) if v >= threshold]

    def display(self):
        for i, v in enumerate(self.influence_map):
            if not i % self.BOARD_WIDTH:
                print()
            print(str(v).rjust(3), end='')
