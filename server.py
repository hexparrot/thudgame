"""aiohttp HTTP + WebSocket server for a multiplayer Thud! game.

One global game state. The first two WebSocket connections to claim a
side become the dwarf and troll players; anyone after that is a
spectator. Players may release and re-claim sides freely (including
swapping sides) at any time. Either player can reset the game.

Wire protocol (JSON over WebSocket):

  Client -> server
    {"type": "claim_side",   "side": "dwarf" | "troll"}
    {"type": "release_side"}
    {"type": "reset",        "ruleset": "classic" | "kvt" | "klash"}
    {"type": "move",         "origin": int, "dest": int}

  Server -> client
    {"type": "state",   ...full board state...}
    {"type": "role",    "role": "dwarf" | "troll" | "spectator"}
    {"type": "players", "dwarf_taken": bool, "troll_taken": bool,
                        "spectator_count": int}
    {"type": "error",   "message": str}

Run with ``python3 server.py``; the site is then on http://localhost:8080/.
"""

import json
import logging
from pathlib import Path

from aiohttp import WSMsgType, web

from thud import Gameboard, NoMoveException, Ply


ROOT = Path(__file__).parent
WEB = ROOT / 'web'
PORT = 8080
# Image assets the page requests via /img/<name>. Whitelisted so the
# generic file route can't be turned into a path-traversal vector.
IMAGE_ASSETS = frozenset({'tb.gif', 'pawn.gif', 'rook.gif', 'thudstone.gif'})
RULESETS = ('classic', 'kvt', 'klash')

log = logging.getLogger('thud.server')


class GameSession:
    """Single shared game + player-slot allocation.

    There's only ever one of these per process (module-level GAME). The
    aiohttp server is single-threaded async, so guarded mutation through
    the message handler is sufficient — no locks needed.
    """

    def __init__(self):
        self.board = Gameboard('classic')
        self.dwarf_ws = None
        self.troll_ws = None
        self.clients = set()

    def role_of(self, ws):
        if ws is self.dwarf_ws:
            return 'dwarf'
        if ws is self.troll_ws:
            return 'troll'
        return 'spectator'

    def auto_assign(self, ws):
        """Give this connection the first open side, or spectator."""
        if self.dwarf_ws is None:
            self.dwarf_ws = ws
        elif self.troll_ws is None:
            self.troll_ws = ws

    def release(self, ws):
        if self.dwarf_ws is ws:
            self.dwarf_ws = None
        if self.troll_ws is ws:
            self.troll_ws = None

    def try_claim(self, ws, side):
        """Atomically swap the caller into ``side``. Returns True on success."""
        if side == 'dwarf':
            if self.dwarf_ws is not None and self.dwarf_ws is not ws:
                return False
            self.release(ws)  # drop any current slot
            self.dwarf_ws = ws
            return True
        if side == 'troll':
            if self.troll_ws is not None and self.troll_ws is not ws:
                return False
            self.release(ws)
            self.troll_ws = ws
            return True
        return False

    def state_payload(self):
        return {
            'type': 'state',
            'board': {
                'dwarfs': list(self.board.dwarfs.get_bits()),
                'trolls': list(self.board.trolls.get_bits()),
                'thudstone': list(self.board.thudstone.get_bits()),
                'playable': list(self.board.playable.get_bits()),
            },
            'ply_list': [str(p) for p in self.board.ply_list],
            'turn': self.board.turn_to_act(),
            'winner': self.board.game_winner,
            'ruleset': self.board.ruleset,
        }

    def players_payload(self):
        players = sum(s is not None for s in (self.dwarf_ws, self.troll_ws))
        return {
            'type': 'players',
            'dwarf_taken': self.dwarf_ws is not None,
            'troll_taken': self.troll_ws is not None,
            'spectator_count': len(self.clients) - players,
        }


GAME = GameSession()


async def _send(ws, payload):
    if ws.closed:
        return
    try:
        await ws.send_str(json.dumps(payload))
    except ConnectionResetError:
        pass


async def _broadcast(payload):
    msg = json.dumps(payload)
    dead = []
    for ws in GAME.clients:
        if ws.closed:
            dead.append(ws)
            continue
        try:
            await ws.send_str(msg)
        except ConnectionResetError:
            dead.append(ws)
    for ws in dead:
        GAME.clients.discard(ws)
        GAME.release(ws)


async def _broadcast_state():
    await _broadcast(GAME.state_payload())
    await _broadcast(GAME.players_payload())


async def _handle_claim(ws, data):
    side = data.get('side')
    if side not in ('dwarf', 'troll'):
        await _send(ws, {'type': 'error', 'message': 'invalid side'})
        return
    if not GAME.try_claim(ws, side):
        await _send(ws, {'type': 'error', 'message': '{} is taken'.format(side)})
        return
    await _send(ws, {'type': 'role', 'role': GAME.role_of(ws)})
    await _broadcast(GAME.players_payload())


async def _handle_release(ws):
    GAME.release(ws)
    await _send(ws, {'type': 'role', 'role': 'spectator'})
    await _broadcast(GAME.players_payload())


async def _handle_reset(data):
    ruleset = data.get('ruleset', 'classic')
    if ruleset not in RULESETS:
        ruleset = 'classic'
    GAME.board = Gameboard(ruleset)
    await _broadcast_state()


async def _handle_move(ws, data):
    role = GAME.role_of(ws)
    if role == 'spectator':
        await _send(ws, {'type': 'error', 'message': 'spectators cannot move'})
        return
    if GAME.board.game_winner:
        await _send(ws, {'type': 'error', 'message': 'game over; reset to play again'})
        return
    if GAME.board.turn_to_act() != role:
        await _send(ws, {'type': 'error', 'message': "it is not your turn"})
        return

    origin = data.get('origin')
    dest = data.get('dest')
    if not (isinstance(origin, int) and isinstance(dest, int)):
        await _send(ws, {'type': 'error', 'message': 'origin/dest must be ints'})
        return

    move, cap, captured = GAME.board.validate_move(origin, dest)
    if not (move or cap):
        await _send(ws, {'type': 'error', 'message': 'illegal move'})
        return

    # Auto-capture when both move and capture would be legal. This mirrors
    # Tkinter's "compulsory capturing" default (the only mode supported
    # over the wire — the per-piece capture selection UI doesn't exist
    # here yet).
    token = GAME.board.token_at(origin)
    ply = Ply(token, origin, dest, captured if cap else [])
    GAME.board.apply_ply(ply)
    GAME.board.ply_list.append(ply)
    outcome = GAME.board.get_game_outcome()
    if outcome:
        GAME.board.game_winner = outcome

    await _broadcast_state()


_HANDLERS = {
    'claim_side': lambda ws, d: _handle_claim(ws, d),
    'release_side': lambda ws, d: _handle_release(ws),
    'reset': lambda ws, d: _handle_reset(d),
    'move': lambda ws, d: _handle_move(ws, d),
}


async def websocket_handler(request):
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)

    GAME.clients.add(ws)
    GAME.auto_assign(ws)
    role = GAME.role_of(ws)
    log.info('client connected, role=%s (%d total)', role, len(GAME.clients))

    await _send(ws, {'type': 'role', 'role': role})
    await _send(ws, GAME.state_payload())
    await _broadcast(GAME.players_payload())

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    await _send(ws, {'type': 'error', 'message': 'invalid json'})
                    continue
                handler = _HANDLERS.get(data.get('type'))
                if handler is None:
                    await _send(ws, {'type': 'error', 'message': 'unknown message type'})
                    continue
                try:
                    await handler(ws, data)
                except Exception as exc:  # surface server bugs to the client
                    log.exception('handler error')
                    await _send(ws, {'type': 'error', 'message': 'server error: {}'.format(exc)})
            elif msg.type == WSMsgType.ERROR:
                log.warning('ws closed with exception %s', ws.exception())
                break
    finally:
        GAME.clients.discard(ws)
        GAME.release(ws)
        log.info('client disconnected (%d remain)', len(GAME.clients))
        await _broadcast(GAME.players_payload())

    return ws


async def index_handler(request):
    return web.FileResponse(WEB / 'index.html')


async def asset_handler(request):
    name = request.match_info['name']
    if name not in IMAGE_ASSETS:
        raise web.HTTPNotFound()
    return web.FileResponse(ROOT / name)


def make_app():
    app = web.Application()
    app.router.add_get('/', index_handler)
    app.router.add_get('/ws', websocket_handler)
    app.router.add_get('/img/{name}', asset_handler)
    app.router.add_static('/web/', WEB)
    return app


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(name)s %(levelname)s %(message)s')
    web.run_app(make_app(), port=PORT)
