# Logic and tactics development log

Started on **2026-11-12** for use when writing the project report. Earlier changes below are reconstructed from the development conversation, current source, and Git checkpoints. Commit dates identify saved checkpoints, not necessarily the exact day each individual feature was written. Changes without a verified date are kept in their known development order.

For future entries, record the date, what changed, why, important parameters/formulas, and the verification actually performed. Keep earlier entries when a rule changes so experiments can be compared. See [physics.md](physics.md) for the detailed mathematical model.

## Earlier TypeScript prototype

### 2026-11-02 — Ball-relative defensive shape

- **Change:** Three autonomous defenders followed targets calculated from formation anchors and ball location. Movement used velocity, acceleration, and speed limits on a pitch measured in meters.
- **Purpose:** Establish a visible, repeatable movement foundation before adding tactical decisions.
- **Checkpoint:** `538c29c` — first draft with three players following the ball.

### 2026-11-06 — Team jobs and individual actions

- **Change:** Team decisions assigned the closest player to press, the second closest to cover, and remaining players to hold shape. Individual decisions converted those jobs into movement targets. Tactical settings included line height and compactness.
- **Details:** Pressing aimed approximately 2 m goal-side of the ball; cover used the ball-to-goal line. Stable player-ID tiebreaks and zero-length geometry guards made decisions more predictable.
- **Checkpoint:** `44153c8`. These were TypeScript prototype rules; the later Python policy was rebuilt incrementally and does not currently include all these jobs.

### Before the Python migration — Separate teams

- **Change:** Split players into two team lists with three players each. Each team assigned jobs independently and defended its own goal direction. Settings belonged to teams, and player selection used both team and player IDs.
- **Purpose:** Support opponents and repeated jersey numbers without mixing team decisions.

## Python development

### 2026-11-10 checkpoint — Engine and visualization separation

- **Change:** Moved simulation logic into `simulation/` and browser drawing code into `frontend/`. The Python engine runs decisions → actions → physics → game rules and returns game state. The browser remains a separate static preview.
- **Evolution:** Began with a text state printer, then added Pygame for inspecting movement, pausing, stepping, resetting, and dragging the ball.
- **State model:** Introduced `Vec2`, `Player`, `Ball`, `Team`, and `GameState` objects. Corrected package imports, independent mutable defaults, target-versus-direction confusion, and time integration mistakes during this work.
- **Checkpoint:** `60c58b4` records the Python refactor.

### Subsequent Python iteration — Running and ball physics

- **Change:** Added target arrival, separate forward/braking/lateral acceleration limits, speed caps, and motor response time. Players without movement targets brake instead of drifting indefinitely.
- **Parameters:** Player maximum speed changed from 20 to 7 m/s. Initial engineering defaults became 3 m/s² forward acceleration, 5 m/s² braking, 4 m/s² lateral acceleration, and a 0.25 s response time.
- **Physics:** Added exact constant rolling deceleration for the ball, disc contacts, mass-based impulses, pitch containment, and bounded substeps. Added a response margin to arrival after a numerical check exposed overshoot. Pygame uses accumulated elapsed time to run fixed simulation ticks.
- **Verification:** Added scenarios for acceleration, arrival, stopping, reversal, turning, rolling friction, contacts, boundaries, and deterministic replay. Defaults are engineering choices, not fitted athlete measurements; full formulas and limitations are in [physics.md](physics.md).

### Subsequent Python iteration — Goal geometry

- **Change:** Added goals to game state, keyed by defending team, with mouth position, facing, width, and depth. Pygame draws the state geometry.
- **Scope:** This added geometry only. Scoring, crossing the goal line, goalpost collisions, and net physics are still unimplemented.

### Subsequent Python iteration — Receiving and dribbling

- **Change:** A player within 1 m of the ball becomes `RECEIVING_BALL`. Physical contact claims a free ball, stores its owner, and changes the owner to `DRIBBLING`. A controlled ball follows the carrier just ahead of their facing direction.
- **Contests:** Simultaneous claims use a uniform random choice. New opponent contact can challenge an owner; continuous contacts are remembered to avoid rerolling every substep. Teammates do not take an already controlled ball from one another. An optional simulation seed makes contests reproducible.
- **Policy revisions:** The first carrier policy fled 10 m away from the nearest opponent. This was changed to moving toward the attacking goal, then later to holding the current position for the rondo. The current `dribble_target` returns the player's position.

### 2026-11-11 checkpoint — Passing under pressure

- **Change:** An opponent within 3 m triggers a pass to the nearest teammate, excluding the carrier. Distance ties use player IDs.
- **Calculation:** For rolling deceleration c and distance d from release to reception, required launch speed is `sqrt(3² + 2cd)`, predicting at least 3 m/s at the receiver's current position. A moving-passer speed margin prevents immediate self-recapture. Infeasible passes are declined rather than weakened below the requirement.
- **Execution:** Added a pass action and stored pass intent. The receiver holds or returns to the planned reception point, while the passer brakes. Contact reception, interception, manual kicks, dragging, or a stopped free ball clear that intent.
- **Checkpoint:** `5d7c86b` records the dribbling/passing stage. The initial model aims at current receiver position and does not lead a moving player.

### After initial passing — Blocked lanes and alternate receivers

- **Change:** Check teammates from nearest to farthest. If a defender blocks the nearest pass, try the other teammate; if all lanes are blocked, use the carrier's current holding policy.
- **Geometry:** Find the closest point on the finite release-to-receiver segment. A lane is blocked when defender distance to that point is at most `defender.radius + ball.radius`. Only opponents are blockers. This uses current positions and does not predict future lane occupation.
- **Verification:** Added blocked/clear lane selection, both options blocked, diagonal geometry, and segment-end tests. An interception test was changed to move a defender into a lane after launch, since a lane already blocked at decision time is now rejected.

### Rondo experiment — Smaller scenario and stationary carriers

- **Change:** The engine now starts `initialize_rondo`: three attackers in a triangle and one defender at the center, on a default 20 × 20 m field. The original 3v3 initializer remains available. Carriers hold their position while deciding whether to pass.
- **Purpose:** Isolate possession, passing, and defensive decisions before expanding to directional soccer.
- **Current limitation:** The ball starts loose. There is no round-ending condition when the defender gains control. Both teams still use generic possession logic, so attackers can chase it back and the lone defender can hold it indefinitely.

### Defender experiment — Three decisions

- **Change:** Controlled ball → press the carrier directly. Loose moving ball → predict an interception point. Loose stationary ball → chase its current position. The intended pass receiver keeps its reception-point action.
- **Prediction:** Sample rolling-ball positions every 0.05 s up to 3 s. Select the first point estimated reachable using current speed, acceleration, maximum speed, contact radii, and a response-time margin. Otherwise pursue the final predicted point.
- **Adjustment:** Added the response margin after an interception check showed that an optimistic reach estimate could select a point the steering controller reached too late.
- **Limitation:** Reach is an estimate; it does not solve exact turning, braking, future collisions, or future carrier movement.

### 2026-11-12 checkpoint — Defender default position and reset

- **Original change:** Stored an independent `default_position` at the pitch center. At a ball-to-defender distance of at least 5 m, return there through normal movement physics. Resume pursuit when closer than 5 m. Originally this check preceded all pursuit branches and only applied when a default position existed.
- **Checkpoint:** `e989f85` — defender returns to starting position when too far from the ball.
- **Historical verification:** The suite passed 69 tests after the original implementation. That is a historical result, not the result for the subsequently tuned policy below.

## Current experiment recorded on 2026-11-12

- **Threshold revision:** `Player.reset_distance` is now 3 m instead of the original 5 m.
- **Branch revision:** Controlled balls are always pressed directly. A moving loose ball is intercepted at distances up to and including 3 m; beyond 3 m the player targets its default position. Stationary loose balls are chased directly. At exactly the threshold, the interception branch wins because it is checked first.
- **Known defect:** The return-home branch currently calls `player.default_position.copy()` without checking for `None`. Attackers and custom test players can lack a default position, causing an `AttributeError` when they enter this branch.
- **Current verification:** `npm test` on 2026-11-12 ran 69 tests and reported **5 failures and 5 errors**. Failures include expectations for the original 5 m/all-pursuit-state reset rule; the errors hit the missing-default-position case. Existing README/physics descriptions of the reset rule still largely describe the original version.

## Measurements and discussed follow-up

- **Earlier performance measurement:** Engine-only averages on the development machine were approximately 2.36 ms/tick for 3v1, 3.65 ms for 3v3, and 29.29 ms for a synthetic 11v11 setup. The runs used seed 42, excluded rendering, and measured 600, 600, and 240 ticks respectively after warm-up. These are local scenario timings, not a general speed guarantee or tactical-quality evaluation.
- **Profile findings:** About 89% of profiled time was in physics and 10% in tactics. Repeated all-pairs contacts, small NumPy vector allocations, and conservative substeps were identified as optimization opportunities. Those optimizations were discussed, not implemented.
- **Observed behavior:** Fixed starts and simple holding/passing rules produce repeated sequences, with random contact contests creating a small number of branches. After a defender wins possession, there is currently no explicit rondo completion rule.
- **Discussed, not implemented:** Start a round with attacker possession; end on defender control or the ball leaving the area; record possession duration and completed passes; reset for another attempt. Vary starting positions and seeds for broader evaluation. Active supporting movement is also future work.

## Future entry format

```text
### YYYY-MM-DD — Short change description
- Changed: What rule/model changed, including the previous behavior if useful.
- Reason: The problem or experiment that motivated it.
- Details: Important thresholds, formulas, assumptions, or affected files.
- Verification: Checks actually run and their results, or "not run".
- Observations: Measured effects, remaining limitations, or follow-up questions.
```
