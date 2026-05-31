"""thud — Python implementation of the Thud! boardgame.

Submodules are organized by responsibility:

  * bitboard       — 289-bit board mask (Bitboard)
  * ply            — half-move + notation (Ply, NoMoveException)
  * influence_map  — heuristic influence grid (InfluenceMap)
  * gameboard      — rules + legal-move enumeration (Gameboard)
  * ai_engine      — heuristic move chooser (AIEngine, ai_log)

The top-level package re-exports the names that the GUI and CLI use so
``from thud import *`` still works for existing call sites.
"""

__author__ = "William Dizon"
__license__ = "MIT License"
__version__ = "1.8.0"
__email__ = "wdchromium@gmail.com"

from .ai_engine import AIEngine, ai_log
from .bitboard import Bitboard
from .gameboard import Gameboard
from .influence_map import InfluenceMap
from .ply import NoMoveException, Ply

__all__ = [
    'AIEngine',
    'Bitboard',
    'Gameboard',
    'InfluenceMap',
    'NoMoveException',
    'Ply',
    'ai_log',
]
