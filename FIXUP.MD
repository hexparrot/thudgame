# FIXUP — Engine Polish Audit for Thud!

**Purpose.** Prepare the engine for a machine-learning AI opponent. ML self-play
demands three properties: **every game terminates**, **no move ever raises an
unexpected exception mid-game**, and **self-play is fast and deterministic**. This
document locates the latent behaviors that broke those properties and specifies a fix
for each. Line numbers are against the pre-fix tree (`master`, 159 tests passing).

> **Status: IMPLEMENTED.** All robustness findings (E/G/S/C/W) and the classic
> rules-fidelity items (R1 scored terminal, R2 optional/subset troll capture is
> documented as a follow-up) have been fixed **across all three variants** — including
> the klash/KVT crash paths that were previously deferred. Evidence: the test suite
> now has **195 passing** (159 original + 36 new regression tests in
> `tests/test_fixes.py`), and a 10-game-per-ruleset self-play soak now **terminates
> every game with a scored outcome** (classic 10/10 wins, KVT 10/10 scored at the
> cutoff, klash 10/10 — up from classic 9/10, KVT 0/10, klash 0/10). What remains
> deferred is **only the KVT/klash rules *fidelity*** (R3/R4) — the unverified dwarf
> count, rock-adjacency, and klash's non-canonical status — which needs an
> authoritative rulebook, not a code fix. See [Implementation notes](#implementation-notes-what-changed).

**Scope.** Engine (`thud/bitboard.py`, `ply.py`, `gameboard.py`, `influence_map.py`,
`ai_engine.py`), applications (`console.py`, `gui.py`, `server.py`), web UI
(`web/app.js`). Every engine and server finding below was reproduced with a script;
see [Appendix A](#appendix-a--reproduction-evidence). GUI findings are verified by
code inspection (Tk interaction is not scriptable headlessly). Two axes are covered:
**robustness** (crash / hang / loop — the numbered E/G/S/C/W findings) and **rules
fidelity** (does the engine implement *real* Thud — the R findings in
[Rules fidelity](#rules-fidelity)). The latter matters for ML because a learned policy
will exploit any divergence between the engine's rules and the game it is meant to play.

**Variant scope.** The **crash/hang/loop fixes were applied to all three variants** —
klash now materializes trolls and plays a full game, and KVT no longer hangs. What is
still **deferred is the rules *fidelity*** of KVT and klash (R3/R4): those rules could
not be corroborated from independent sources, so the engine implements a best-effort /
project-original interpretation. The classic rules *are* authoritatively corroborated
(see [Rules fidelity](#rules-fidelity)), so classic is the recommended target for the
first ML iteration; KVT/klash are playable and terminating but rules-unverified.

**Headline.** The single most important result: **AI-vs-AI self-play does not
reliably finish.** In a 10-game-per-ruleset soak, classic crashed 1/10 mid-game,
**KVT terminated 0/10** (6 shuffled to the move cap, 4 hung 120 s on one move), and
klash could not start a single game. For an ML training loop these are showstoppers.

## Contents

- [Severity & class taxonomy](#severity--class-taxonomy)
- [Findings — Engine](#findings--engine-thud)
- [Findings — Applications](#findings--applications)
- [Findings — Web UI](#findings--web-ui-webappjs)
- [Rules fidelity (do the engine's rules match real Thud?)](#rules-fidelity)
- [ML-readiness assessment](#ml-readiness-assessment)
- [Fix ordering](#fix-ordering)
- [Non-findings (verified safe)](#non-findings-verified-safe)
- [Appendix A — reproduction evidence](#appendix-a--reproduction-evidence)

---

## Severity & class taxonomy

**Severity**

| Level | Meaning |
|-------|---------|
| CRITICAL | Can prevent *any* game (including self-play) from terminating, or crashes in ordinary play. Blocks ML training. |
| HIGH | Crash / hang / rules corruption reachable through normal use or a hostile network peer. |
| MEDIUM | Crash or state corruption reachable on specific but realistic inputs. |
| LOW | Robustness / correctness rough edge; no crash or hang in normal play. |

**Class tags:** `[infinite-loop]` `[crash]` `[hang]` `[rules-integrity]` `[dos]` `[robustness]`

**Per-finding format:** *Location · Trigger · Impact · Fix · Verification.*

**Roll-up**

| Severity | Engine | Apps | Web | Total |
|----------|:------:|:----:|:---:|:-----:|
| CRITICAL | 2 | 0 | 0 | 2 |
| HIGH | 4 | 4 | 0 | 8 |
| MEDIUM | 4 | 4 | 0 | 8 |
| LOW | 1 | 2 | 3 | 6 |
| **Total** | **11** | **10** | **3** | **24** |

Counts are **robustness** findings (crash / hang / loop). The four **rules-fidelity**
findings (R1–R4) are tallied separately in [Rules fidelity](#rules-fidelity).

---

## Findings — Engine (`thud/`)

### E1 — Boxed-in troll: infinite loop in the AI fallback  ·  CRITICAL `[infinite-loop]`

- **Location:** `thud/ai_engine.py:161-163` (loop), `:129-146` (`alternate_direction`).
- **Trigger:** `nonoptimal_troll_moves()` is the troll AI's last-resort move source
  (reached when there are no captures and no setups). For each troll it steps toward
  the nearest dwarf, and if that square is occupied it calls `alternate_direction`
  and retries:
  ```python
  while self.board.token_at(t + direction) != 'empty':
      delta = alternate_direction(delta)
      direction = self.board.delta_to_direction(delta)
  ```
  `token_at` returns `None` for off-board squares (`gameboard.py:121-130`), which is
  `!= 'empty'`, so blocked *and* off-board squares both keep the loop alive.
  `alternate_direction` only ever proposes **two** alternates and picks one at
  random, so when a troll is fully enclosed (all 8 neighbors occupied or off-board)
  the two alternates are themselves blocked and the loop spins forever.
- **Impact:** The engine hangs — no exception, no timeout, one core pinned at 100%.
  Fatal to self-play, which is exactly the position type (crowded midgame) where the
  troll runs out of captures/setups. Secondary: `alternate_direction((0,0))` would do
  `random.choice([])` → `IndexError`.
- **Fix:** Bound the search to the 8 real directions and fall through gracefully:
  ```python
  step = None
  for cand in candidate_directions(delta):        # yields the ≤8 distinct king steps
      dest = t + cand
      if self.board.token_at(dest) == 'empty':    # 'empty' only — never None
          step = cand
          break
  if step is not None:
      candidates.append(Ply('troll', t, t + step, []))
  # else: this troll has no non-optimal move; contribute nothing.
  ```
  Never treat `None` (off-board) as a movable target; never loop without a
  termination bound. Add a `NoMoveException`/empty-list contract when *no* troll can
  move (see E3/E4 for the caller side).
- **Verification:** `repro_e1_boxed_troll.py` (5 s alarm) → `REPRODUCED: infinite
  loop`. Regression test: a board with one enclosed troll must make
  `nonoptimal_troll_moves()` return in bounded time (assert under a timeout).

### E2 — No scoring and no termination bound → games never end  ·  CRITICAL (ML) `[hang]` `[rules-integrity]`

- **Location:** `thud/gameboard.py:330-390` (`get_game_outcome`).
- **Trigger:** The engine decides a game **only by rout** (one side captured to zero),
  plus the KVT objective and klash mobilization. But **real Thud is almost never won by
  rout — it is *scored*.** A battle ends by mutual agreement or when the side to move
  has no legal move, and the result is decided by surviving material: **dwarfs score 1
  per surviving dwarf, trolls score 4 per surviving troll, and the difference is the
  score** (two battles with swapped sides are summed). See
  [Rules fidelity → R1](#rules-fidelity). The engine implements **none** of this: no
  score, no no-legal-move ending, no repetition / no-progress cutoff, no scored or
  `'draw'` outcome.
- **Impact:** With rout as the only practical terminal, two AIs (or an ML policy) that
  never force the last capture shuffle forever. The soak measured KVT positions
  repeating up to **78 times** and **every KVT game failing to terminate**; a training
  loop that waits for `get_game_outcome()` to go truthy stalls on these games forever.
- **Fix — real Thud scoring at a cutoff (the chosen model):** make the engine return a
  *scored, always-reachable* terminal rather than a chess-style draw:
  1. **Scored outcome.** Give `get_game_outcome` (or a sibling `result()`) a terminal
     value equal to the material differential from the troll's perspective,
     `S = 4·len(trolls) − len(dwarfs)` — the **authoritative 4:1 weight**, which is
     exactly what `AIEngine.score` already computes (`ai_engine.py:48-54`; reuse it).
     `S > 0` → troll ahead, `S < 0` → dwarf ahead, `S == 0` → draw. Return the winner
     **and** `S` so ML gets a graded reward and the harness can sum the two battles.
  2. **Terminal conditions**, any of which ends the game and is then scored by `S`:
     (a) rout — already detected; (b) **the side to move has no legal move** — the
     official ending, which also closes the missing-stalemate gap; (c) a **no-progress
     cutoff** for self-play — a configurable `MAX_PLIES` move cap and/or *N*-fold
     repetition of the position key `(dwarfs.value, trolls.value, thudstone.value,
     turn_to_act())`. Real Thud uses mutual agreement here, which self-play cannot do,
     so the cutoff is the mechanical stand-in — but it resolves **by score**, not an
     automatic draw.
  3. Thread the scored terminal through `game_winner` and the UIs. KVT and klash keep
     their objective wins (rock saved/captured, mobilization), which simply set `S` to
     a decisive value.
- **Verification:** `soak_selfplay.py` (per-game cap + 120 s wall guard) shows
  KVT = `{'CAP-HIT': 6, 'WALL-CLOCK HANG': 4}` today. Regression: after the fix a soak
  of N games per ruleset reaches a scored terminal every game (no wall-clock-guard
  hits), and a hand-built position with a known survivor count returns the expected
  `S = 4·trolls − dwarfs`.

### E3 — `StopIteration` when a side has no moves  ·  HIGH `[crash]`

- **Location:** `thud/ai_engine.py:314` — `decision = next(b.board.find_moves('dwarf'))`.
- **Trigger:** Dwarf branch, last resort: no captures, no setups/blocks, no
  influence candidates. If `find_moves('dwarf')` is empty (all dwarfs immobilized),
  `next(...)` raises `StopIteration` instead of the engine's own `NoMoveException`.
- **Impact:** An uncaught `StopIteration` escapes `calculate_best_move`. Callers that
  catch `NoMoveException` (the GUI worker, `predict_future`) do **not** catch this, so
  it becomes a crash/aborted turn. Reproduced in **KVT** (where dwarf captures are
  jump-based, so a sealed dwarf has neither a move nor a capture).
- **Fix:** `decision = next(b.board.find_moves('dwarf'), None)` and let the existing
  `if not decision: raise NoMoveException(token)` at `:323-324` handle it — or wrap
  the `next` in `try/except StopIteration: raise NoMoveException('dwarf')`.
- **Verification:** `repro_e3_no_dwarf_moves.py` → KVT branch prints
  `REPRODUCED: uncaught StopIteration`. Regression: a sealed-dwarf KVT board must make
  `calculate_best_move(g,'dwarf',0)` raise `NoMoveException`, not `StopIteration`.

### E4 — `filter_best` rejects all candidates when scores are negative  ·  MEDIUM (latent) `[crash-adjacent]`

- **Location:** `thud/ai_engine.py:194-207`.
- **Trigger:** The acceptance threshold is `candidates[0].score * (1 - variance_pct)`.
  When the best score is **negative** (routine for the troll, whose material score is
  `4·trolls − dwarfs`, e.g. `−28` with one troll left) and `variance_pct > 0`, the
  threshold is *more positive than the best score itself*, so `top` is empty and the
  method returns the falsy sentinel `Ply(None, None, None, None)`.
- **Impact:** The caller sees a falsy decision and raises `NoMoveException` even though
  legal, scored candidates exist — a spurious "no moves" that ends the game wrongly.
  **Latent today:** all four current call sites pass the default `variance_pct=0`
  (thresholds collapse to `>= best`, which always admits the best). It is a landmine
  for the ML work, which is exactly the kind of caller likely to pass a tolerance.
- **Fix:** Make the band symmetric around magnitude, not sign:
  `threshold = best - abs(best) * variance_pct` (equivalently rank by score and take
  the top `variance_pct` fraction). Guarantee a non-empty return whenever
  `candidates` is non-empty.
- **Verification:** `repro_e4_filter_best.py` → `variance_pct=0` truthy,
  `variance_pct=0.1` falsy on scores `[-28,-28]`. Regression: `filter_best` with any
  `variance_pct in [0,1]` and non-empty candidates must return a truthy `Ply`.

### E5 — Outcome checks crash on degenerate boards  ·  MEDIUM `[crash]`

- **Location:** `thud/gameboard.py:338-339` (`check_mobilized` → `next(pieces)`),
  `:352` and `:357` (`list(self.thudstone.get_bits())[0]`).
- **Trigger:** `check_mobilized` (klash) does `next(self.dwarfs.get_bits())` with **no
  default** — `StopIteration` when dwarfs are empty. The KVT thudstone checks index
  `[0]` of the thudstone bit list — `IndexError` when the thudstone has been captured
  off the board or was never placed.
- **Impact:** `get_game_outcome()` raises instead of returning a winner/None, aborting
  the very call meant to detect the end of the game. Reachable in klash (dwarfs routed)
  and in KVT edge positions.
- **Fix:** `next(self.dwarfs.get_bits(), None)` with an early `return False` when
  empty; guard the thudstone lookups with `bits = list(self.thudstone.get_bits()); if
  not bits: return False`. Note both outcomes should already be decided by the rout
  check ordering — make that explicit so the connectivity/thudstone helpers are only
  reached with a non-empty set.
- **Verification:** `repro_e5_outcome.py` → Case A `StopIteration`, Case B
  `IndexError`, both `REPRODUCED`. Regression: `get_game_outcome` returns cleanly on a
  klash 0-dwarf board and a KVT thudstone-absent board.

### E6 — Notation codec crashes / accepts off-board positions  ·  MEDIUM `[crash]`

- **Location:** `thud/ply.py:92-103` (`position_to_notation`, `notation_to_position`),
  `:118-119` (`_PLY_NOTATION_RE`).
- **Trigger:** `to_letter.get(...)`/`to_number.get(...)` return `None` for a file
  index or letter outside A–P, then `None + str`/`None + int` raises `TypeError`. Off-
  board positions whose file component *does* fall in 1–15 don't crash but render
  garbage notation (`str(Ply('troll',93,-10,[]))` → `'TH5-G-1'`). The regex
  `([A-HJ-P])([0-9]+)` accepts any rank digits, so `parse_string('dA0-A16')` yields a
  ply with `dest=273` (off the 289-square board) instead of `None`.
- **Impact:** `str(ply)` of an off-board ply crashes (interacts with **E1**, which can
  build such plies) or silently records corrupt moves into `ply_list` and `.thud`
  save files; `parse_string` admits illegal saved games. For ML this means training
  data can contain positions the board can't represent.
- **Fix:** In the codecs, validate that file ∈ 1..15 and rank ∈ 1..15 and raise a
  precise `ValueError` (or return `None`) instead of doing arithmetic on `None`. In
  the regex, constrain rank to `(1[0-5]|[1-9])` so out-of-range ranks fail to parse.
- **Verification:** `repro_e6_notation.py` → three `TypeError`s reproduced;
  `parse_string('dA0-A16')` yields `dest=273`. Regression: off-board
  `position_to_notation` raises `ValueError`; `parse_string` of an out-of-range rank
  returns `None`.

### E7 — Empty-origin "move" validates → free pass / non-termination  ·  HIGH `[rules-integrity]` `[hang]`

- **Location:** `thud/gameboard.py:280-306` (`is_valid_move`), fall-through
  `return True` at `:306`; thudstone branch `:295-305` not ruleset-gated.
- **Trigger:** `is_valid_move` branches on `squares[0]` being `'dwarf'`, `'troll'`, or
  `'thudstone'`. When the origin square is **empty**, none match and control falls
  through to `return True`. `validate_move(<empty>, <empty>)` therefore returns
  `(True, False, [])`. Over the wire (`server.py:227` reads `token_at(origin)` *after*
  validation) the applied ply has token `'empty'`: `apply_ply` no-ops, but the ply is
  appended and `turn_to_act()` flips.
- **Impact:** A player (or a bugged/hostile agent) can **pass** indefinitely by
  "moving" empty squares — combined with **E2** this alone makes games non-terminating,
  and it corrupts `ply_list` with `NoneH5-H4`-style notation. Separately, the
  thudstone-escort branch runs in **classic** and **klash**, not just KVT, so the
  thudstone becomes movable outside the one ruleset that allows it.
- **Fix:** Make `is_valid_move` return `False` when `squares[0] not in
  ('dwarf','troll','thudstone')` (empty/off-board origin). Gate the thudstone branch on
  `self.ruleset == 'kvt'`. Belt-and-suspenders: have `server.py` reject a move whose
  `origin` is not owned by the mover (see **S1**).
- **Verification:** `repro_e7_null_move.py` → `validate_move(empty→empty)=(True,…)`,
  turn flips with no board change, `ply=NoneH5-H4`; classic thudstone move validates
  `True`. Regression: empty-origin moves return `(False, …)` in every ruleset;
  thudstone moves are illegal outside KVT.

### E8 — Out-of-range position: unbounded allocation / shift crash  ·  HIGH `[dos]`

- **Location:** `thud/bitboard.py:33` (`1 << (N-1-p)`), `:44-47` (`__getitem__`).
- **Trigger:** `Bitboard([p])` with a large **negative** `p` computes
  `1 << (288 - p)` — for `p = -8·10¹⁰` that is a ~10 GB integer. The
  `except (TypeError, ValueError)` guard at `gameboard.py:212` only catches *positive*
  out-of-range `p` (which produce a negative shift → `ValueError`); a negative `p`
  produces a valid but enormous left shift and allocates. Separately, `__getitem__`
  with `key >= 289` shifts by a negative count → `ValueError`, so `token_at(p)` crashes
  for `p ≥ 289` instead of returning `None`.
- **Impact:** Memory-exhaustion DoS reachable from a single crafted position index
  (see **S2** for the network path). The `__getitem__` crash is the sharp edge behind
  **E6**'s unchecked notation parsing.
- **Fix:** Range-check positions at the boundary: `Bitboard.__init__` should reject
  `p` outside `0..N-1` with a `ValueError`; `__getitem__` should return `0` (or raise a
  clear `IndexError`) for out-of-range keys rather than doing a negative shift. Since
  the engine's own callers stay in `0..288`, the cost is a cheap guard on the hostile
  path.
- **Verification:** `repro_s2_negative_int.py` → int size grows linearly with `|p|`
  (13 KB → 133 KB → 1.3 MB at −10⁵…−10⁷); `__getitem__(289)` → `ValueError`.
  `fuzz_validate.py` (10 000 adversarial ints, negatives capped) → **0 exceptions**,
  confirming the danger is the *allocation size*, not a `validate_move` exception.
  Regression: `Bitboard([-1])` and `Bitboard([289])` raise `ValueError`.

### E9 — Influence map bleeds across the board edge  ·  LOW `[robustness]`

- **Location:** `thud/influence_map.py:36-44` (`hit`).
- **Trigger:** Splash from a piece adds influence to `pos + di` guarded only against
  columns 0 and 16, so a contribution from column 1 with `di = -3` wraps onto column
  15 of the adjacent row.
- **Impact:** The dwarf AI's positional heuristic is subtly wrong near the edges; it
  biases clustering. Not a crash or hang. Worth noting because an ML value head trained
  against this heuristic's outputs would inherit the artifact.
- **Fix:** Convert the position to `(file, rank)` and clamp/reject splash targets whose
  file or rank leaves `1..15`, instead of the column-0/16 test on the raw index.
- **Verification:** Unit test: a single piece at file 1 must contribute zero influence
  to file 15 of any row.

### E10 — AI applies a `None` ply → `AttributeError` in ordinary play  ·  HIGH `[crash]`

- **Location:** `thud/ai_engine.py:308-310` (dwarf branch) feeding
  `select_best_future` → `predict_future` at `:210-221`.
- **Trigger:** In the dwarf branch `best_move` is initialized to `None` and only set
  if some influence-variance tier yields candidates; every tier can `continue`, leaving
  it `None`. If a threat/setup/block also made `tsb` truthy, the code runs
  `select_best_future(b.board, [tsb, best_move], lookahead, token)` — i.e. with `None`
  in the candidate list. `select_best_future` calls `predict_future(board, None, …)`,
  which does `AIEngine(board).apply((None,))` → `apply_ply(None)` → `None.token`.
- **Impact:** `AttributeError: 'NoneType' object has no attribute 'token'` mid-move, in
  **classic** self-play with default settings — **1 of 10** soak games hit it (ply 36,
  deterministically at seed 1006). This is a live crash in normal AI play, not an edge
  case, and it will halt an ML self-play worker.
- **Fix:** Filter `None` before scoring:
  `plies = [p for p in (tsb, best_move) if p]` and pass that to `select_best_future`;
  and/or have `select_best_future`/`predict_future` skip falsy plies. Ensure a truthy
  fallback (`next(find_moves(...), None)` guarded by E3's fix) so a real move is always
  chosen when one exists.
- **Verification:** `repro_e10_e11.py` (replays seed 1006) →
  `REPRODUCED at ply 36: AttributeError`. Regression: a full classic self-play soak
  (fixed seeds) completes with zero `AttributeError`s.

### E11 — Klash AI game cannot start  ·  MEDIUM `[crash]`

- **Location:** `thud/ai_engine.py:249-250` guard vs. the klash opening.
- **Trigger:** Klash begins with **zero trolls** on the board (trolls *materialize*
  during play). `calculate_best_move` guards `elif not len(b.board.trolls): raise
  NoMoveException('troll')`, which fires immediately — before any dwarf move, before
  any materialization — because troll count is 0 at the opening.
- **Impact:** Every klash AI game ends instantly with `NoMoveException(troll)` (soak:
  **10/10** at ply 0). Materialization is not wired into move generation or the AI, so
  klash is effectively unplayable by the current engine's AI. The ML opponent cannot
  train on klash as-is.
- **Fix:** Either (a) scope the ML work to classic/KVT and document klash as
  human-only, or (b) wire materialization into `find_moves`/`find_caps` and relax the
  empty-troll guard for klash (trolls-remaining-to-materialize > 0 is a legal
  to-move state). Recommend (a) for the first ML iteration, (b) as a tracked follow-up.
- **Verification:** `repro_e10_e11.py` → `REPRODUCED: NoMoveException(troll) at move 0`.
  Regression: after whichever path is chosen, klash either raises a *clear,
  documented* "unsupported" error or plays a full game.

---

## Findings — Applications

### G1 — `_cpu_tick` dies before it reschedules → AI stops forever  ·  HIGH `[hang]`

- **Location:** `gui.py:639-643`.
- **Trigger:** `_cpu_tick` runs `_drain_ai_results()`, `_maybe_start_ai()`,
  `_animate_thinking()`, then reschedules itself with `self.master.after(CPU_POLL_MS,
  self._cpu_tick)` **as the last line**. If any of the three preceding calls raises,
  the `after(...)` never runs. Tk prints the traceback but keeps `mainloop` alive, so
  the poll loop is silently dead. `_drain_ai_results` only catches `queue.Empty`, so a
  `KeyError`/`AttributeError` from `execute_ply` (see G3, or an E10-style AI result)
  propagates straight out.
- **Impact:** The AI turn machine stops permanently; the UI sits on "Computer is
  thinking…" with no recovery short of restart.
- **Fix:** Wrap the tick body in `try/finally` so the reschedule always happens, and
  surface the error to `user_notice`:
  ```python
  def _cpu_tick(self):
      try:
          self._drain_ai_results(); self._maybe_start_ai(); self._animate_thinking()
      except Exception as e:
          self.user_notice.set(f"internal error: {e}")
      finally:
          self.master.after(CPU_POLL_MS, self._cpu_tick)
  ```
- **Verification:** Code inspection; exercised by forcing `_drain_ai_results` to raise.
  Regression: a raised exception in the tick body must not stop subsequent ticks.

### G2 — KVT pickup indexes short history → `IndexError`  ·  HIGH `[crash]`

- **Location:** `gui.py:403-410`.
- **Trigger:** The KVT multi-capture pickup path reads `ply_list[-2]` and `[-3]`
  (`:407-408`) guarded only by `self.board.ply_list` being non-empty (`:404`). A KVT
  game whose recent history is shorter than 3 plies — e.g. a loaded game whose first
  ply is a troll capture — makes `[-2]`/`[-3]` raise `IndexError` inside the Tk
  `mouseDown` callback on the next click.
- **Impact:** Crash on user interaction (traceback to console; via G1 this also kills
  the AI poll loop).
- **Fix:** Guard on length: `if len(self.board.ply_list) >= 3 and …` before the `[-2]`/
  `[-3]` reads, treating shorter histories as "not a continued multi-capture".
- **Verification:** Code inspection. Regression: constructing the KVT pickup state with
  a 1- or 2-ply history must not raise.

### G3 — Stale AI result applied to a rebuilt board → `KeyError`  ·  MEDIUM `[crash]` → `[hang]`

- **Location:** `gui.py:680-695` (`_drain_ai_results` → `execute_ply` at `:686`) with
  `:523-526` (`self.sprites[...]`).
- **Trigger:** The worker computes on a deep-copied snapshot (`:662`), but its result
  is applied to the **live** board/sprites via `execute_ply`. If the user rebuilds the
  board while the worker thinks (clicking a history ply → `play_out_moves` →
  `newgame_common` rebuilds `self.sprites`), the returned ply's `origin` no longer has a
  sprite → `self.sprites[fullply.origin]` raises `KeyError`.
- **Impact:** Crash; and because it escapes `_drain_ai_results` (only `queue.Empty`
  caught) it realizes **G1** → permanent AI hang.
- **Fix:** Before applying, validate the result against current state: check the AI ply
  was computed for the currently-displayed position (e.g. stamp the snapshot's
  `len(ply_list)` and compare), and that `origin` maps to a live sprite; discard and
  recompute otherwise. G1's `try/finally` keeps the loop alive regardless.
- **Verification:** Code inspection. Regression: applying an AI ply whose origin is
  absent from `self.sprites` is rejected, not fatal.

### G4 — Undo replays klash materialization plies → `KeyError` / count desync  ·  MEDIUM `[crash]` `[rules-integrity]`

- **Location:** `gui.py:733-747` (`undo_last_ply`), replay via `execute_ply` (`:746`).
- **Trigger:** Undo rebuilds by replaying every prior ply through `execute_ply`, which
  does `self.sprites[fullply.origin]` (`:526`). Klash **materialization** plies have
  `origin == dest` and no sprite at `origin` → `KeyError`. Materialization also happens
  via `add_troll` (which bumps `klash_trolls`), so replaying through `execute_ply`
  bypasses it and desyncs `klash_trolls`, breaking the klash win check at
  `gameboard.py:362`.
- **Impact:** Undo crashes in klash and, where it doesn't, corrupts the materialized-
  troll count.
- **Fix:** Make replay materialization-aware (dispatch on a materialization ply to
  `add_troll` + sprite-create rather than `move_sprite`), or rebuild via the same
  code path that produced the plies. Overlaps with **E11**: if klash stays out of the
  first ML pass, still fix undo so the GUI doesn't crash.
- **Verification:** Code inspection. Regression: undo across a klash materialization
  ply restores both sprites and `klash_trolls`.

### S1 — Server never checks piece ownership  ·  HIGH `[rules-integrity]`

- **Location:** `server.py:200-235` (`_handle_move`).
- **Trigger:** The handler checks only `turn_to_act() != role` (`:208`) and that the
  move validates; it never checks that `token_at(origin)` matches the mover's side. It
  reads the token *after* validation (`:227`) and applies whatever piece sits there.
- **Impact:** On your turn you can move the **opponent's** pieces (or the thudstone).
  Reproduced: on the dwarf turn, `validate_move(troll_origin, dest)` passes and a troll
  ply is applied. Corrupts game semantics and, with **E7**, lets a player manipulate
  any square. Over a network this is an exploit, not just a bug.
- **Fix:** After the turn check, require `GAME.board.token_at(origin) == role` (map
  `'dwarf'`/`'troll'` roles to piece tokens) and reject otherwise. This also closes
  E7's network path.
- **Verification:** `repro_s1_wrong_piece.py` → troll ply accepted on the dwarf turn.
  Regression (server test, mirroring `tests/test_server.py`): a dwarf client moving a
  troll piece gets an `error`, board unchanged.

### S2 — Crafted position index can OOM the server  ·  HIGH `[dos]`

- **Location:** `server.py:212-217` (accepts any `int`) → **E8** allocation path.
- **Trigger:** `_handle_move` accepts any `origin`/`dest` that `isinstance(_, int)`
  (`:214`) with no range check, then calls `validate_move` → `Bitboard([origin])`. A
  large negative int forces a multi-gigabyte allocation (see E8).
- **Impact:** One WebSocket message can exhaust server memory. Note: `validate_move`
  itself is exception-*safe* on adversarial ints (fuzz: 0 exceptions), so this is
  purely the allocation-size vector — which is exactly why an input bound is the right
  fix rather than a `try/except`.
- **Fix:** Validate `0 <= origin < 289` and `0 <= dest < 289` in `_handle_move` before
  touching the engine (reject with an `error` otherwise). Fixing E8's `Bitboard`
  bound is the defense-in-depth backstop.
- **Verification:** `repro_s2_negative_int.py` (linear growth, safe scale) +
  `fuzz_validate.py` (0 exceptions). Regression: out-of-range `origin`/`dest` are
  rejected before any Bitboard is built.

### S3 — Broadcast mutates the client set mid-iteration  ·  MEDIUM `[crash]` `[rules-integrity]`

- **Location:** `server.py:150-163` (`_broadcast`).
- **Trigger:** `for ws in GAME.clients:` iterates the **live** set while `await
  ws.send_str(...)` (`:158`) yields control. A client connecting (`GAME.clients.add`)
  or disconnecting during that await mutates the set → `RuntimeError: Set changed size
  during iteration`.
- **Impact:** The broadcast aborts partway; clients after the mutation point never get
  the new state and desync from the game. Timing-dependent but reachable under
  concurrent connects.
- **Fix:** Iterate a snapshot: `for ws in list(GAME.clients):`. (Dead-client cleanup at
  `:161-163` already iterates a separate list, so only the send loop needs it.)
- **Verification:** `repro_s3_broadcast.py` (minimal asyncio model) → `RuntimeError`.
  Regression: broadcasting while a task adds a client completes without raising.

### S4 — Engine runs synchronously on the event loop  ·  LOW `[robustness]`

- **Location:** `server.py` — `validate_move`/`get_game_outcome` called inline in the
  async handler.
- **Trigger:** These are CPU work on the single aiohttp event-loop thread. Cheap today,
  but the ML opponent's move computation will not be.
- **Impact:** Latency spikes / head-of-line blocking when a move computation is heavy;
  not a hang with the current heuristic AI.
- **Fix:** When the server drives the AI, run `calculate_best_move` (and any heavy
  validation) via `asyncio.to_thread(...)` / a process pool so the loop keeps serving
  other clients.
- **Verification:** Load-test once the ML opponent is wired in; ensure other clients'
  pings are answered during an AI move.

### C1 — `console.py next_move` crashes on a finished/blocked game  ·  MEDIUM `[crash]`

- **Location:** `console.py:69-71` (`cmd_next_move`) and `:117-124` (`main`).
- **Trigger:** `cmd_next_move` calls `calculate_best_move`, which raises
  `NoMoveException` on a routed/sealed position. `main` catches only `RuntimeError`
  (`:119`), so `NoMoveException` escapes as a traceback / exit-1.
- **Impact:** Any pipeline calling `next_move` on a terminal position crashes instead
  of reporting "no move". (Compounded by E3, which can turn the same situation into a
  `StopIteration`.)
- **Fix:** Catch `NoMoveException` in `main` (or in `cmd_next_move`) and emit a defined
  sentinel line (e.g. empty output or a `no-move` token) with a stable exit code.
- **Verification:** Feed a rout position to `next_move`; expect the sentinel, not a
  traceback. Regression: a CLI test over a terminal-position `.thud` input.

### C2 — `turn`/`captures` swallow errors silently  ·  LOW `[robustness]`

- **Location:** `console.py:117-124` (`main`).
- **Trigger:** On a `RuntimeError`, `main` prints for `next_move`/`validate` but for
  `turn`/`captures` falls through printing nothing and returns `0`.
- **Impact:** A malformed input to `turn`/`captures` is indistinguishable from a valid
  empty result — silent failure in scripts.
- **Fix:** Emit an explicit error to stderr and return a non-zero exit code for the
  `turn`/`captures` error path.
- **Verification:** Feed an illegal `.thud` to `captures`; expect a diagnostic +
  non-zero exit.

---

## Findings — Web UI (`web/app.js`)

All three are LOW `[robustness]` — no crash or hang of the *engine*; they degrade the
client experience.

- **W1 — No reconnect.** `app.js:64-72`: on `close`/`error` the UI shows "Offline"
  permanently; only a page reload recovers. *Fix:* exponential-backoff reconnect that
  re-requests state on reopen.
- **W2 — Post-move render race.** `app.js:220-224`: after `send({type:'move'})` the
  client does `setTimeout(render, 200)`; a legal move whose state broadcast arrives
  after 200 ms briefly snaps the sprite back, and a rejected move is only visually
  corrected on the timer. *Fix:* render on receipt of the authoritative `state`/`error`
  message rather than on a fixed timer.
- **W3 — Drag robustness.** `onMouseUp`/`onMouseMove` (`app.js:204-230`) clear `drag`
  on mouseup, but there's no cancel path if the pointer/touch is interrupted
  mid-drag. *Fix:* add a cancel handler that clears `drag` and re-renders.

---

## Rules fidelity

The findings above are about the engine *crashing or hanging*. This section is a
different axis: **does the engine implement the actual game of Thud?** A learned policy
will ruthlessly exploit any square where the engine's rules diverge from real Thud, so
fidelity is a first-class ML concern, not pedantry.

**Method & reliability.** `WebFetch` was unavailable in this environment, so no primary
page was read verbatim end to end; every load-bearing claim below was cross-checked
across **≥2 independent authoritative sources** via search extracts — Wikipedia
"Thud (game)", the L-Space Discworld wiki, the Discworld Fandom wiki, BoardGameGeek
(#4532 Thud, #25748 Koom Valley Thud), and mirrors of the original THUD! rules PDF.
`thudgame.com` (the canonical rules host) is currently down. Claims that rest on a
single source or that could not be verified are flagged **[UNVERIFIED]** below and
should be checked against the physical rulebook before you rely on them for training.

### What is faithful (trust these)

**Classic Thud — the core rules match the engine exactly.**
- Board: 15×15 with a 15-square triangle removed per corner → octagon, **165 playable
  squares**. The engine's `dist_from_center = [0,2,3,4,5,6,7,7,7,7,7,6,5,4,3,2,0]`
  inscribes exactly 165 squares. ✔
- Setup: immovable Thudstone at centre; 8 trolls on the 8 squares around it; 32 dwarfs
  on the perimeter except the 4 aligned with the Thudstone. ✔
- Dwarf = chess-queen slide, cannot jump. ✔ Troll = one square, king-like. ✔
- **Dwarf hurl:** a line of *N* dwarfs throws the front dwarf up to *N* squares over
  empty squares onto a troll; **a lone dwarf may capture an adjacent troll** (line of
  1, distance 1). The engine's `is_valid_cap_normal` implements exactly this, including
  the lone-dwarf case (`gameboard.py:253-262`). ✔
- **Troll shove:** a line of *N* trolls shoves the end troll up to *N* squares onto an
  empty square, capturing adjacent dwarfs, and **a lone troll may capture on an
  ordinary one-square move**. The engine matches (`gameboard.py:263-277`). ✔
- **Scoring weight is authoritative: dwarfs 1/survivor, trolls 4/survivor.** The
  engine's `AIEngine.score` (`ai_engine.py:48-54`) already uses this exact 4:1 weight —
  so the ML scored terminal in **E2** is not an invention, it is the real rule. ✔

### R-findings (rules divergences)

- **R1 — HIGH (ML) `[rules-integrity]`. The engine has no scoring and no real ending.**
  Real Thud is decided by the surviving-material score (`4·trolls − dwarfs`
  differential, two battles summed), ending by mutual agreement or a no-legal-move
  position; **rout is a rare special case, not the normal terminal.** The engine models
  only rout. *This is the same root cause as* **E2** *— fix them together*: implement
  the scored terminal and the no-legal-move / no-progress endings. Impact: without it
  the engine cannot even express who won a normal game of Thud, and self-play never
  terminates.

- **R2 — MEDIUM `[rules-integrity]`. Troll capture is all-or-nothing; the server forces
  it.** Official rule: on a *normal* troll move, capturing adjacent dwarfs is
  **optional and the troll chooses which subset** (0..all) to remove; only a *shove* is
  compulsory-capture (must take ≥1). The engine captures **all** adjacent dwarfs (or
  none, via a separate non-capturing move) — it cannot take a chosen subset
  (`gameboard.py:263-277`, `tokens_adjacent(dest,'dwarf')` returns them all) — and
  `server.py:223-228` **auto-captures** whenever a capture is legal ("compulsory
  capturing"), which is not the normal-move rule. *Impact for ML:* the troll action
  space is narrower than legal Thud (no partial captures, no decline-capture on a normal
  move), so a policy trained here will not transfer to a rules-faithful opponent. *Fix:*
  represent capture-subset choice in the move/action encoding, and make the server honor
  optional capture on normal moves.

- **R3 — HIGH (ML) `[rules-integrity]` [UNVERIFIED]. KVT rules cannot be certified; at
  least two look wrong.** Koom Valley Thud is a real Trevor Truran variant and the
  engine's broad strokes match (moveable rock; dwarfs escort it to 5 goal squares on
  the far edge; trolls win by surrounding the rock with 3; trolls move up to 3; troll
  captures are checkers-style multi-jumps; dwarf capture is a custodial sandwich). But
  the specifics could not be verified and two conflict with sourced text:
  - **Dwarf count:** the engine seeds **16** dwarfs for KVT (`gameboard.py:90-95`);
    sources imply the **same 32** as classic. Unresolved conflict.
  - **Rock-move escort:** the engine requires **≥2** dwarfs adjacent to both origin and
    destination (`gameboard.py:298-305`); sources say **1**.
  - **[UNVERIFIED]** exact KVT starting layout (only published as a diagram image),
    whether the troll multi-jump *must* continue while captures remain (engine forces
    it via `must_be_jump`), whether KVT has an explicit draw, and whether KVT truly has
    rout wins (engine has them; no source confirms).
  *Impact:* KVT self-play would train against rules that are partly unverified and
  possibly wrong. *Fix:* reconcile against the physical KVT rulebook/diagram before
  using KVT for ML; treat the dwarf-count and rock-adjacency numbers as suspect.

- **R4 — INFO `[rules-integrity]`. "Klash" is not a real Thud variant.** Exhaustive
  search found only two published rulesets — **Classic Thud** and **Koom Valley Thud**.
  "Klash" exists **only in this codebase** (`hexparrot/thudgame`): its materialization
  (trolls appear during play, capped at 6) and dwarf "mobilization" (all dwarfs
  connected) win are original to the project, so **the code is its own and only spec**.
  It is also internally inconsistent (materialization is allowed on any of the 8 central
  squares but capped at 6) and, per **E11**/**G4**, unplayable by the current AI and
  crash-prone on undo. *Recommendation:* exclude klash from the ML work (classic only
  for now — KVT is also deferred, see R3); if you later revive it, write down its rules
  as an explicit spec and fix E11/G4 first.

### Rules-findings roll-up

| ID | Variant | Severity | Status | Divergence |
|----|---------|----------|--------|------------|
| R1 | classic | HIGH (ML) | **active** (⇒ E2) | no scoring; only rout ends a game |
| R2 | classic | MEDIUM | **active** | troll capture is all-or-nothing; server forces capture |
| R3 | KVT | HIGH (ML) [UNVERIFIED] | deferred | dwarf count 16 vs 32, rock adjacency 2 vs 1, layout/multi-jump/draw unverified |
| R4 | klash | INFO | deferred | non-canonical; code is the only spec; internally inconsistent |

**Sources** (cross-checked, ≥2 per load-bearing claim):
[Wikipedia — Thud](https://en.wikipedia.org/wiki/Thud_(game)) ·
[L-Space Discworld wiki](https://wiki.lspace.org/Thud) ·
[Discworld Fandom wiki](https://discworld.fandom.com/wiki/Thud_(game)) ·
[BGG #4532 Thud](https://boardgamegeek.com/boardgame/4532/thud) ·
[BGG #25748 Koom Valley Thud](https://boardgamegeek.com/boardgame/25748/koom-valley-thud) ·
original THUD! rules PDF (mirrors: docslib.org/doc/2427705, tesera.ru THUD_RULES.pdf).
`thudgame.com` (canonical host) was unreachable; `WebFetch` was unavailable, so claims
rest on cross-checked search extracts — items that could not be corroborated are marked
**[UNVERIFIED]**.

---

## ML-readiness assessment

The ML opponent will (a) generate games by self-play, (b) read positions/outcomes as
training signal, and (c) call the engine millions of times. Priorities:

**1. Termination & scoring (blocks training).** Implement the E2/R1 **scored terminal**
in the engine so every driver (self-play loop, server, GUI, CLI) inherits it: a game
ends on rout, on a no-legal-move position, or at a no-progress cutoff, and its value is
the authoritative differential `S = 4·trolls − dwarfs` (reuse `AIEngine.score`,
`ai_engine.py:48-54`). The no-progress cutoff needs a cheap position key, exact given
the bitboard representation:
```python
position_key = (board.dwarfs.value, board.trolls.value,
                board.thudstone.value, board.turn_to_act())
```
Maintain a `Counter` over these keys per game; trigger the cutoff at the N-th repeat or
at `MAX_PLIES`, then **score by S** (not an automatic draw). Also fix **E1/E3/E4/E10**
so a move computation cannot hang or crash a self-play worker. **Scope the first ML
iteration to classic only:** KVT and klash rules are unverified / non-canonical
(**R3/R4**), so they and their variant-specific findings (E5, E11, G2, G4) are deferred
— revisit once you have an authoritative KVT rulebook and a written klash spec.

**2. Self-play throughput.** `AIEngine.__init__` deep-copies the whole board
(`ai_engine.py:37`), and `filter_best` builds a *fresh* `AIEngine` per candidate
(`:197`), so move selection is `O(candidates × deepcopy)`. A position is four Python
ints (the four Bitboard `value`s) plus `ply_list`; a snapshot/restore of those ints is
dramatically cheaper than `copy.deepcopy`. Recommended: give `Gameboard` a lightweight
`snapshot()`/`restore()` (copy the four ints + a shallow ply-list marker) and have the
AI apply/undo instead of deep-copying. Baseline to beat (this soak, lookahead 0):
classic ≈ **93 plies/sec**; KVT ≈ 6 plies/sec (dominated by the E1/E2 pathologies,
which the fixes should remove). Profile one game with `cProfile` before and after.

**3. Determinism.** `filter_best` and `nonoptimal_troll_moves` call `random.choice`
against the global RNG. For reproducible training, thread an injectable `random.Random`
(seeded per game/worker) through `AIEngine` instead of the module-global `random`.

**4. Engine/UI separation.** The engine is already UI-free — good. Codify a **headless
self-play driver** as the canonical entry point (the `soak_selfplay.py` loop is a
working template) rather than the Tk `simulate_game` at `gui.py:785`, which inherits
the E1 loop and the G-series GUI hazards.

**5. Hygiene.** Remove the stale `thud/__pycache__/mcts.cpython-313.pyc` (no `mcts.py`
source; `__pycache__/` is gitignored, so this is a local `rm`, not a repo change). It
is inert — Python 3 will not import a sourceless `.pyc` from `__pycache__` — but it is
confusing next to a from-scratch ML/MCTS effort.

---

## Fix ordering

All tiers below are **DONE** (across all variants). Only the KVT/klash rules-*fidelity*
items (R3/R4) and the R2 troll-capture-subset refactor remain open.

**Tier 1 — blockers for ML self-play. ✅ done.** E1, E2/R1, E3, E7, E10, S1, S2, G1 —
the crashes / hangs / non-termination reachable in ordinary AI play or from the network,
plus the scored terminal (E2/R1). A self-play loop now runs to completion for every
ruleset and yields a scored result. (E7 also gates the thudstone to KVT, protecting
classic/klash from a movable stone.)

**Tier 2 — correctness. ✅ done** (E4, E6, E8, G3, S3, C1). **R2** (optional / subset
troll capture) is **open** — a move-encoding change best done alongside the ML action
space; the server still auto-captures (documented compulsory-capture limitation).

**Tier 3 — polish. ✅ mostly done.** E9 (influence edge-wrap) is **open** (heuristic-only,
low value). S4, C2, W1, W2, W3 done; determinism (seedable RNG) and the `mcts.pyc`
cleanup done; the snapshot/restore *API* is added (`Gameboard.snapshot/restore`) though
the AI still deep-copies (wiring it in is the remaining throughput win).

**Also done (previously deferred as KVT/klash-specific):** E5, E11, G2, G4 — the
klash/KVT crash paths were fixed too, so all variants play and terminate.

**Still deferred — KVT & klash rules fidelity (needs a rulebook, not code):** R3 (KVT
dwarf count 16-vs-32, rock adjacency 2-vs-1, unverified layout/multi-jump/draw), R4
(klash is non-canonical — the engine's materialization/mobilization rules are
project-original). The engine now *plays* these variants without crashing or hanging,
but whether it plays them by the *right* rules is unconfirmed.

---

## Implementation notes (what changed)

The fixes landed in the working tree (no behavior change to the 159 original tests;
36 new regression tests in `tests/test_fixes.py` lock each fix). Highlights:

- **Termination (E2/R1).** New `Gameboard.result(max_plies=DEFAULT_MAX_PLIES)` returns a
  scored terminal `{winner, score, reason}` — `score = 4*trolls - dwarfs` (the official
  weight, reused from `AIEngine.score`). Ends on rout/objective (`win`), no legal move
  (`no-move`, also the stalemate guard), or the no-progress cap (`cutoff`). Server, and
  the new `thud/selfplay.py` driver, use it; the GUI keeps get_game_outcome + the now-safe
  AI worker.
- **Klash (E11).** `Gameboard.find_materializations` generates troll materialization
  plies; `apply_ply` routes an `origin == dest` troll through `add_troll`; the AI guard is
  relaxed for klash and materializations join the troll fallback pool.
- **Loops/crashes.** `nonoptimal_troll_moves` now does a bounded direction search (E1);
  `filter_best` uses a magnitude-relative band and is empty-safe (E4); the dwarf branch
  filters `None` plies (E10) and defaults its final `next()` (E3); `get_game_outcome`
  helpers guard empty bitboards (E5); `is_valid_move` rejects empty-origin moves and gates
  the thudstone to KVT (E7); `Bitboard` range-checks positions (E8); `Ply` notation
  validates on/off-board and `parse_string` rejects off-board (E6).
- **Server.** `_handle_move` range-checks positions (S2) and enforces piece ownership
  (S1); `_broadcast` iterates a snapshot of the client set (S3); uses `result()`.
- **GUI.** `_cpu_tick` reschedules in a `finally` (G1); KVT pickup length-guards history
  (G2); stale AI results are discarded (G3); undo and `execute_ply` are materialization-
  aware (G4).
- **Web.** Auto-reconnect with backoff (W1); render on the authoritative message, no fixed
  timer (W2); drag-cancel handler (W3); `draw` is displayed.
- **ML-readiness.** Seedable engine RNG (`thud.ai_engine.seed`); `thud/selfplay.py`
  headless driver; `Gameboard.snapshot/restore`; stale `mcts.pyc` removed.

**Open follow-ups:** R2 (optional/subset troll capture), E9 (influence edge-wrap),
wiring the AI onto snapshot/restore for throughput, and the R3/R4 rules-fidelity
reconciliation.

---

## Non-findings (verified safe)

Recorded so they aren't re-investigated:

- **`gameboard.py:201-206` `is_materializing`** — `(len(self.ply_list) % 2 and
  'troll')` looks suspicious but is correct: it's falsy on even ply counts and the
  truthy `'troll'` string is only used for its boolean value. Obscure style, not a bug.
- **Bitboard width-safety** — all shifts/`~` mask to 289 bits for **in-range**
  positions; values never go negative or overflow the board. (The out-of-range hazard
  is E8, a boundary-input issue, not a masking issue.)
- **AI recursion depth** — `predict_future` recurses only `lookahead` levels (≤3 in
  all callers); bounded and safe.
- **Server concurrency** — aiohttp is single-threaded async; there are no data races on
  `GAME` (the one real concurrency bug is S3's set-mutation-during-await, listed as a
  finding).
- **`fuzz_validate.py`** — 10 000 adversarial `validate_move` calls raised **0**
  exceptions; the function is robust to junk ints at its return path (the DoS is E8's
  allocation size, addressed by S2's input bound).

---

## Appendix A — reproduction evidence

Scripts live in the session scratchpad (`…/scratchpad/repro/`), self-contained with
`sys.path` pointed at the repo and `signal.alarm` timeouts so a genuine hang prints
`REPRODUCED: timeout` instead of hanging the run. They do **not** modify the repo; the
159-test suite is unchanged and green.

| Finding(s) | Script | Result |
|---|---|---|
| E1 | `repro_e1_boxed_troll.py` | `REPRODUCED: infinite loop — timed out after 5s` |
| E3 | `repro_e3_no_dwarf_moves.py` | KVT: `REPRODUCED: uncaught StopIteration`; classic: has captures (n/a) |
| E4 | `repro_e4_filter_best.py` | `variance=0` truthy, `variance=0.1` falsy on scores `[-28,-28]` — `REPRODUCED` |
| E5 | `repro_e5_outcome.py` | Case A `StopIteration`, Case B `IndexError` — both `REPRODUCED` |
| E6 | `repro_e6_notation.py` | 3× `TypeError`; `parse_string('dA0-A16')` → `dest=273` (off-board) |
| E7 | `repro_e7_null_move.py` | empty→empty validates `True`, turn flips, `ply=NoneH5-H4`; classic thudstone move `True` |
| E10, E11 | `repro_e10_e11.py` | E11: `NoMoveException(troll)` at move 0; E10: `AttributeError` at ply 36 (seed 1006) |
| S1 | `repro_s1_wrong_piece.py` | troll ply `TG7-F6` accepted on the dwarf turn |
| S2, E8 | `repro_s2_negative_int.py` | int grows 13 KB→133 KB→1.3 MB (−10⁵…−10⁷); `__getitem__(289)` → `ValueError` |
| S3 | `repro_s3_broadcast.py` | `RuntimeError: Set changed size during iteration` |
| E2 (+E1) | `soak_selfplay.py` | see table below |
| — | `fuzz_validate.py` | 10 000 `validate_move` calls → **0 exceptions** |

**Self-play soak (10 games per ruleset, lookahead 0, 400-ply cap, 120 s wall guard):**

| Ruleset | Outcomes | Throughput | Notes |
|---|---|---|---|
| classic | `troll×6, dwarf×3, AttributeError×1` | 92.6 plies/s | the crash is **E10**, ply 36 |
| kvt | `CAP-HIT×6, WALL-CLOCK-HANG×4` | 6.4 plies/s | **0 games terminated**; positions repeated up to 78× (**E2**); the 4 hangs are single moves not returning (**E1**/pathological search) |
| klash | `NoMoveException(troll)×10` | — | every game dies at ply 0 (**E11**) |

Reproduce end-to-end:
```
cd <scratchpad>/repro
python3 repro_e1_boxed_troll.py   # …and the other repro_*.py
python3 soak_selfplay.py 10 400
python3 fuzz_validate.py
cd <repo> && python3 -m pytest tests/ -q   # 159 passed
```
