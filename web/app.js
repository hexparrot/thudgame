/* Thud! browser client.
 *
 * Receives state updates over a WebSocket, renders pieces as positioned
 * <img> sprites on top of the board background, and lets the active
 * side drag a piece to send a {type:"move"} request back. The server is
 * authoritative — the UI doesn't optimistically apply moves; it waits
 * for the next state broadcast to redraw.
 *
 * Coordinate convention matches thud/ply.py: position = rank*17 + file
 * for file 1..15 and rank 1..15. Screen cell (sx, sy) (each in 0..14)
 * therefore maps to position = sy*17 + sx + 18.
 */

(() => {
  const SQUARE = 40;
  const SPRITE_FOR = {
    dwarf: '/img/pawn.gif',
    troll: '/img/rook.gif',
    thudstone: '/img/thudstone.gif',
  };

  // ----- DOM ----------------------------------------------------------
  const $ = (id) => document.getElementById(id);
  const spritesEl = $('sprites');
  const boardEl = $('board-wrap');
  const noticeEl = $('notice');
  const roleEl = $('role-banner');
  const playersEl = $('players-summary');
  const plyListEl = $('ply-list');
  const dwarfCountEl = $('dwarf-count');
  const trollCountEl = $('troll-count');
  const turnEl = $('turn-indicator');

  // ----- State --------------------------------------------------------
  let myRole = 'spectator';
  let lastState = null;
  let drag = null;
  let noticeTimer = 0;

  // ----- Position helpers --------------------------------------------
  function positionToPixel(position) {
    const rank = Math.floor(position / 17);
    const file = position - rank * 17;
    return { x: (file - 1) * SQUARE, y: (rank - 1) * SQUARE };
  }

  function pixelToPosition(x, y) {
    const sx = Math.floor(x / SQUARE);
    const sy = Math.floor(y / SQUARE);
    if (sx < 0 || sx > 14 || sy < 0 || sy > 14) return null;
    return sy * 17 + sx + 18;
  }

  function capitalize(s) {
    return s ? s.charAt(0).toUpperCase() + s.slice(1) : '';
  }

  function rulesetLabel(name) {
    if (name === 'kvt') return 'KVT';
    return capitalize(name);
  }

  // ----- WebSocket ----------------------------------------------------
  const wsProto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const WS_URL = `${wsProto}//${location.host}/ws`;
  const RECONNECT_MIN_MS = 1000;
  const RECONNECT_MAX_MS = 15000;
  let ws = null;
  let reconnectDelay = RECONNECT_MIN_MS;
  let reconnectTimer = 0;

  function connect() {
    ws = new WebSocket(WS_URL);

    ws.addEventListener('open', () => {
      reconnectDelay = RECONNECT_MIN_MS;  // reset backoff after a good connect
      setNotice('Connected.', 1500);
      // The server re-sends role + full state on connect, so a reconnect
      // resynchronizes automatically — nothing else to do here.
    });

    ws.addEventListener('close', () => {
      // Auto-reconnect with exponential backoff instead of leaving the UI
      // dead until a manual page reload.
      setNotice(`Disconnected. Reconnecting in ${Math.round(reconnectDelay / 1000)}s…`,
                0, true);
      roleEl.textContent = 'Offline';
      clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(connect, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 2, RECONNECT_MAX_MS);
    });

    ws.addEventListener('error', () => setNotice('Connection error.', 0, true));

    ws.addEventListener('message', (event) => {
      let msg;
      try { msg = JSON.parse(event.data); } catch (e) { return; }
      switch (msg.type) {
        case 'state':   onState(msg);   break;
        case 'role':    onRole(msg);    break;
        case 'players': onPlayers(msg); break;
        case 'error':   onError(msg);   break;
      }
    });
  }

  function send(payload) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify(payload));
  }

  // ----- Message handlers --------------------------------------------
  function onState(msg) {
    lastState = msg;
    render();
  }

  function onRole(msg) {
    myRole = msg.role;
    roleEl.textContent = 'You are: ' + capitalize(myRole);
  }

  function onPlayers(msg) {
    playersEl.textContent =
      `Dwarf: ${msg.dwarf_taken ? 'taken' : 'open'}    ` +
      `Troll: ${msg.troll_taken ? 'taken' : 'open'}\n` +
      `Spectators: ${msg.spectator_count}`;
  }

  function onError(msg) {
    setNotice(msg.message, 3000, true);
    // A rejected move: redraw from the last authoritative state so the
    // dragged piece snaps back immediately (no fixed timer needed).
    render();
  }

  function setNotice(text, holdMs, isError) {
    clearTimeout(noticeTimer);
    noticeEl.textContent = text;
    noticeEl.classList.toggle('error', !!isError);
    if (holdMs && holdMs > 0) {
      noticeTimer = setTimeout(() => {
        noticeEl.textContent = '';
        noticeEl.classList.remove('error');
      }, holdMs);
    }
  }

  // ----- Rendering ----------------------------------------------------
  function render() {
    if (!lastState) return;

    // Sprites: rebuild from scratch each tick. Cheap (≤41 elements),
    // and trivially correct under deletes/captures.
    spritesEl.innerHTML = '';
    for (const p of lastState.board.dwarfs)    addSprite(p, 'dwarf');
    for (const p of lastState.board.trolls)    addSprite(p, 'troll');
    for (const p of lastState.board.thudstone) addSprite(p, 'thudstone');

    // Counts + turn indicator
    dwarfCountEl.textContent = lastState.board.dwarfs.length;
    trollCountEl.textContent = lastState.board.trolls.length;
    if (lastState.winner) {
      const label = lastState.winner === 'draw'
        ? 'Draw' : `${capitalize(lastState.winner)} win`;
      turnEl.textContent = `${label} (${rulesetLabel(lastState.ruleset)})`;
    } else {
      turnEl.textContent = `${capitalize(lastState.turn)} to move (${rulesetLabel(lastState.ruleset)})`;
    }

    // Ply list
    plyListEl.innerHTML = '';
    lastState.ply_list.forEach((p, i) => {
      const row = document.createElement('div');
      row.className = 'ply-entry';
      const turn = Math.floor(i / 2) + 1;
      const side = i % 2 === 0 ? '.' : '…';
      row.textContent = `${String(turn).padStart(3)}${side} ${p}`;
      plyListEl.appendChild(row);
    });
    plyListEl.scrollTop = plyListEl.scrollHeight;
  }

  function addSprite(position, type) {
    const { x, y } = positionToPixel(position);
    const img = document.createElement('img');
    img.src = SPRITE_FOR[type];
    img.className = 'sprite sprite-' + type;
    img.style.left = x + 'px';
    img.style.top = y + 'px';
    img.dataset.position = position;
    img.dataset.type = type;
    img.draggable = false;
    img.addEventListener('mousedown', onSpriteDown);
    img.addEventListener('touchstart', onSpriteDown, { passive: false });
    spritesEl.appendChild(img);
  }

  // ----- Drag handling ------------------------------------------------
  function pickupAllowed(spriteType) {
    if (myRole === 'spectator') return false;
    if (lastState && lastState.winner) return false;
    if (!lastState || lastState.turn !== myRole) return false;
    if (spriteType === myRole) return true;
    // KVT: dwarf player also moves the thudstone.
    if (spriteType === 'thudstone' && lastState.ruleset === 'kvt' && myRole === 'dwarf') {
      return true;
    }
    return false;
  }

  function getEventCoords(e) {
    if (e.touches && e.touches[0]) {
      return { clientX: e.touches[0].clientX, clientY: e.touches[0].clientY };
    }
    return { clientX: e.clientX, clientY: e.clientY };
  }

  function onSpriteDown(e) {
    const sprite = e.currentTarget;
    if (!pickupAllowed(sprite.dataset.type)) return;
    e.preventDefault();
    const { clientX, clientY } = getEventCoords(e);
    const boardRect = boardEl.getBoundingClientRect();
    drag = {
      sprite,
      originPosition: parseInt(sprite.dataset.position, 10),
      offsetX: clientX - boardRect.left - parseInt(sprite.style.left, 10),
      offsetY: clientY - boardRect.top - parseInt(sprite.style.top, 10),
      boardRect,
    };
    sprite.classList.add('dragging');
  }

  function onMouseMove(e) {
    if (!drag) return;
    const { clientX, clientY } = getEventCoords(e);
    const x = clientX - drag.boardRect.left - drag.offsetX;
    const y = clientY - drag.boardRect.top - drag.offsetY;
    drag.sprite.style.left = x + 'px';
    drag.sprite.style.top = y + 'px';
  }

  function onMouseUp(e) {
    if (!drag) return;
    const { clientX, clientY } = getEventCoords(e);
    const localX = clientX - drag.boardRect.left;
    const localY = clientY - drag.boardRect.top;
    const dest = pixelToPosition(localX, localY);

    if (dest !== null && dest !== drag.originPosition) {
      send({ type: 'move', origin: drag.originPosition, dest });
    }
    // Snap back to the last authoritative state immediately. A legal move is
    // redrawn when the server broadcasts new state (onState); an illegal one
    // when the server replies with an error (onError). No fixed timer, which
    // used to flicker on slow links and mask rejected moves for 200ms.
    render();
    drag.sprite.classList.remove('dragging');
    drag = null;
  }

  function onDragCancel() {
    // Pointer/touch interrupted mid-drag (e.g. touchcancel, context menu):
    // drop the drag and restore the board rather than leaving a stuck sprite.
    if (!drag) return;
    drag.sprite.classList.remove('dragging');
    drag = null;
    render();
  }

  document.addEventListener('mousemove', onMouseMove);
  document.addEventListener('mouseup', onMouseUp);
  document.addEventListener('touchmove', onMouseMove, { passive: false });
  document.addEventListener('touchend', onMouseUp);
  document.addEventListener('touchcancel', onDragCancel);

  // ----- Menu buttons -------------------------------------------------
  document.getElementById('menubar').addEventListener('click', (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;
    const action = btn.dataset.action;
    if (action === 'reset') {
      send({ type: 'reset', ruleset: btn.dataset.ruleset });
    } else if (action === 'claim') {
      send({ type: 'claim_side', side: btn.dataset.side });
    } else if (action === 'release') {
      send({ type: 'release_side' });
    }
  });

  // Open the socket (and keep it open via reconnect-on-close above).
  connect();
})();
