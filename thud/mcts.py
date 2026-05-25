"""MCTSNode — scaffolding for a Monte Carlo Tree Search opponent.

The integration with AIEngine is not finished (see the broken state of
the prior ``console.py`` MCTS driver). Kept here so the data structure
isn't lost while the rest of the codebase is reorganized.
"""


class MCTSNode:
    def __init__(self, game_state, parent=None):
        self.game_state = game_state
        self.parent = parent
        self.children = []
        self.visits = 0
        self.value = 0

    def __repr__(self):
        return "MCTSNode(visits={}, value={})".format(self.visits, self.value)

    def add_child(self, child_node):
        self.children.append(child_node)

    def update_value(self, new_value):
        self.value += new_value
        self.visits += 1

    def average_value(self):
        if self.visits == 0:
            return 0
        return self.value / self.visits
