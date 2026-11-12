# Physics model

This document describes the implemented model in `simulation/physics.py`, its connection to `engine.py`, and the assumptions behind it. All defaults are tunable engineering choices. They have not been fitted to real player tracking data.

## Purpose and research basis

The model simulates movement across the ground for a small tactics simulator. A player is a disc with position, velocity, and a controlled acceleration. Feet, joints, stride cycles, balance, and vertical motion are outside the model.

The separation between tactical objectives, steering, and locomotion follows the approach described by [Craig Reynolds, *Steering Behaviors for Autonomous Characters*](https://www.red3d.com/cwr/papers/1999/gdc99steer.pdf). His arrival behavior motivates reducing desired speed as a character approaches its destination. The arrival formula and acceleration constraints below are this project's engineering choices, rather than a reproduction of his controller.

The fixed simulation tick follows the distinction between physics ticks and rendered frames explained in [Godot's physics interpolation documentation](https://docs.godotengine.org/en/stable/tutorials/physics/interpolation/physics_interpolation_introduction.html). Bounded substeps and contact impulses use standard rigid body simulation ideas also discussed in [Box2D's simulation documentation](https://box2d.org/documentation/md_simulation.html); this code does not embed Box2D or reproduce its full solver.

Predictive crowd avoidance is deliberately a future layer. [RVO2 separates preferred velocity from collision avoiding velocity](https://gamma-web.iacs.umd.edu/RVO2/documentation/2.0/whatsnew.html). This engine currently implements physical disc contact, not ORCA or a guarantee of collision-free navigation. Players can therefore become blocked while pursuing a target.

## Units, state, and defaults

Coordinates and radii use meters, time uses seconds, velocity uses m/s, acceleration uses m/s², and mass uses kilograms. The default pitch remains the project's 40 × 20 m training field. Positive x points right and positive y points down in the top-down view. There is no gravity term because all motion lies on the ground plane.

| Parameter | Default | Meaning |
| --- | ---: | --- |
| Player maximum speed | 7 m/s | Motor speed cap; replaces the previous 20 m/s default |
| Forward acceleration | 3 m/s² | Ability to gain speed |
| Braking acceleration | 5 m/s² | Ability to slow down |
| Lateral acceleration | 4 m/s² | Ability to change travel direction |
| Response time, τ | 0.25 s | Velocity controller response scale |
| Arrival radius | 0.15 m | Region in which the target requests zero speed |
| Player radius / mass | 0.35 m / 75 kg | Effective contact disc |
| Ball radius / mass | 0.11 m / 0.43 kg | Effective contact disc |
| Ball rolling deceleration, c | 0.8 m/s² | Constant loss of ground speed |
| Ball speed cap | 35 m/s | Safety and gameplay cap |
| Player contact restitution | 0 | No bounce along the contact normal |
| Ball contact restitution | 0.35 | Partial bounce against players |
| Public simulation tick | 1/60 s | Default decision frequency |
| Maximum physics substep | 1/120 s | Further reduced by a travel bound |
| Contact iterations | 6 | Passes through contacts per substep |

The player radius includes a simplified personal body footprint. Mass affects contact impulses, not a player's ability to produce the configured running acceleration. These values should be calibrated through sprint, braking, turning, and ball-roll scenarios before making claims about realism. [Renkin et al., *Validation and Optimisation of Player Motion Models in Football*](https://eprints.cs.univie.ac.at/7322/1/ICCS_2022_paper_381.pdf) demonstrates why motion models need validation against observations and why simple unconstrained motion assumptions can misrepresent reachable positions. That study is not a validation of this engine.

## From tactical target to movement

`MoveDecision.target` is an **absolute pitch position**. Tactics produces decisions for all teams before physics changes any position. The engine copies those targets and passes them to physics. A player without a target receives a braking command; they do not coast indefinitely because their previous decision disappeared.

Let p be position, v velocity, q the target, h the physics substep, b maximum braking acceleration, and ρ the arrival radius.

### Desired velocity and arrival

Compute displacement d and remaining distance r:

```text
d = q − p
r = max(0, |d| − ρ)
```

With constant braking, stopping distance is `s² / (2b)`. A velocity controller also takes time to respond. The implemented conservative envelope adds a response allowance `sτ`:

```text
r = sτ + s² / (2b)
s_brake = sqrt((bτ)² + 2br) − bτ
s_desired = min(max_speed, s_brake)
v_desired = normalize(d) × s_desired
```

The quadratic equation gives the positive root shown above. Close to the destination this approaches `r / τ`, giving a gentle approach. A zero displacement produces zero desired velocity, without division by zero. A missing target also produces zero desired velocity.

This is a conservative controller heuristic. It does not guarantee arrival at every moving target or exact arrival at a requested time. Collision forces, changing targets, and limited turning can prevent it from following the preferred motion.

### Acceleration, braking, and turning

The requested acceleration closes the gap between current and desired velocity:

```text
a_request = (v_desired − v) / max(τ, h)
```

When desired velocity is zero, `a_request = −v/h`. The acceleration constraints then remove as much speed as the braking limit permits, reaching exactly zero when physically possible within the substep.

At rest, requested acceleration is limited to the forward acceleration magnitude. While moving, let u be the normalized current velocity. Split the request into longitudinal and lateral components:

```text
a_parallel = dot(a_request, u)
a_lateral = a_request − u × a_parallel
L = max_acceleration       if a_parallel >= 0
L = max_deceleration       otherwise
E = sqrt((a_parallel / L)² + (|a_lateral| / max_lateral_acceleration)²)
a = a_request / max(1, E)
```

The ellipse shares the acceleration budget between changing speed and turning. It prevents a player from applying full forward acceleration and full sideways acceleration simultaneously. At roughly constant speed, the lateral limit implies a minimum turning radius near `|v|² / max_lateral_acceleration`. Thus a fast player needs more space to turn.

Travel direction and facing are not independent: facing follows nonzero velocity. Sideways shuffling, backwards running, planted-foot pivots, fatigue, and separate sprint modes are future extensions.

### Integration

Player movement uses semi-implicit Euler integration:

```text
v_next = limit_magnitude(v + ah, max_speed)
p_next = p + v_next h
stored_acceleration = (v_next − v) / h
```

Acceleration is stored in m/s². The factor h is applied once when integrating acceleration into velocity and once when integrating velocity into position. `Player.acceleration` records motor acceleration before contact and boundary corrections. A collision can change velocity impulsively without respecting the motor acceleration ellipse.

## Ground ball motion and kicks

A kick adds a delta velocity in the supplied nonzero direction:

```text
v_next = limit_magnitude(v + normalize(direction) × power, ball.max_speed)
```

`power` is measured in m/s, not newtons. The equivalent impulse would be `ball.mass × delta_velocity`. A kick releases ownership and sets the ball to `LOOSE`.

Between contacts, ground rolling uses constant deceleration c opposite velocity. With initial speed s and unit travel direction u:

```text
t_roll = min(h, s/c)                     if c > 0, otherwise h
distance = s × t_roll − 0.5c × t_roll²
p_next = p + u × distance
v_next = u × max(0, s − ch)
```

This integrates free rolling exactly for the assumed constant deceleration. The ball stops in finite time and never reverses because of friction. With c = 0 it travels at constant velocity. For example, 8 m/s with c = 2 m/s² gives a 4 s stopping time and a 16 m stopping distance.

No lofted passes, gravity, aerodynamic drag, spin, turf variation, or bouncing off the ground are modeled.

### Ground passes

`PassDecision` identifies the carrier and an intended teammate. A carrier issues this action when any opponent's center is at most 3 m away, selecting the nearest teammate by current center distance. Equal distances use player IDs as a stable tiebreaker. With no teammate or an infeasible pass, the carrier keeps the existing goal-directed dribble behavior.

`plan_pass` places the release point just outside the passer's body in the direction of the receiver, at `player.radius + ball.radius + 0.02` meters from the passer center. This is an instantaneous foot-placement approximation, allowing backward passes without sending the ball through the passer's contact disc.

Let d be the distance from this release point to the teammate's current position, c the ball's rolling deceleration, and v_arrival = 3 m/s. Constant deceleration gives:

```text
v_arrival² = v_launch² − 2cd
v_required = sqrt(v_arrival² + 2cd)
v_launch = max(v_required, dot(passer.velocity, pass_direction) + 0.5)
```

The second bound lets a moving passer release the ball faster than their own velocity along the pass direction. The passer brakes after releasing, so this prevents an immediate self-recapture. If the required launch speed exceeds `ball.max_speed`, or the teammate is too close for a valid release point, the pass is declined rather than silently weakened.

`pass_ball` sets the desired world velocity along the pass direction and releases ownership. It does not add this velocity to the ball's inherited carrier velocity: the equivalent kick impulse is `ball.mass × (desired_velocity − previous_velocity)`. No kick duration or force in newtons is modeled. Generic `kick_ball` retains its existing delta-velocity behavior.

For an unobstructed roll to a stationary target, the formula predicts exactly 3 m/s at the target center, or more if the moving-passer bound raised launch speed. Physical reception normally happens earlier, at body contact, so contact speed is slightly higher. This guarantee is a prediction at the planned point; moving receivers, interceptions, contacts, and boundaries can change where or whether reception happens.

`Ball.pass_state` stores the passer, receiver, and a detached copy of the reception point. The receiver is directed to hold or return to that point during flight, and teammates do not all chase the pass. The opposing team's nearest player can still pursue and intercept it. Acquiring possession clears this intent. A generic kick, dragging the ball, or a loose ball coming to rest also cancels it. This initial policy neither leads moving receivers nor checks passing-lane safety.

## Contacts and boundaries

Players and the ball are circles. For two overlapping bodies, let n point from the first center to the second, δ be penetration, and w₁ = 1/m₁, w₂ = 1/m₂ be inverse masses. Separate their positions in inverse-mass proportion:

```text
p₁ -= n × δ × w₁ / (w₁ + w₂)
p₂ += n × δ × w₂ / (w₁ + w₂)
```

If centers coincide, the solver chooses the positive x axis as a deterministic normal. This is a numerical fallback, not a model of human preference.

For closing relative normal speed `v_rel = dot(v₂ − v₁, n) < 0`, apply a normal impulse with restitution e:

```text
J = −(1 + e) × v_rel / (w₁ + w₂)
v₁ -= n × J × w₁
v₂ += n × J × w₂
```

An isolated impulse conserves linear momentum before speed caps are applied. Restitution below one loses normal kinetic energy. Speed caps and positional correction are additional numerical/gameplay constraints, so the complete solver is not a strictly energy-conserving mechanics model. There are no tangential contact impulses or body rotation.

Physical contacts are resolved in sorted team/player order, with six passes by default. Dense groups can retain small overlaps after the finite iteration budget. The solver has no predictive path avoidance. The engine supplies a separate possession callback to inspect ball contacts before disc impulses are applied.

Player centers are constrained inside the pitch by their radii. At a boundary, outward normal velocity is removed and tangential velocity remains. The ball uses the same containment by default, creating a closed training area rather than throw-ins or goal rules. Set `physics.contain_ball` to false when implementing out-of-play rules.

`GameState.goals` stores the geometry of the two goals, keyed by defending team. A goal's position is the mouth center on the goal line; facing points into the pitch, width spans across the mouth, and depth extends behind the line. The visualizer draws these objects. They do not yet alter containment, register scores, or add goalpost/net collisions.

`LOOSE` and `CONTESTED` balls both use free rolling and contact physics. A `CONTROLLED` ball requires a valid `(team_id, player_id)` owner. It is placed just ahead of that player's facing direction, copies their velocity, and skips disc impulses while controlled. This kinematic attachment does not simulate individual touches. Pitch containment can shorten the attachment offset and remove the ball's outward velocity near an edge.

### Receiving, possession, and dribbling

`possession.py` maintains `PlayerStatus.IDLE`, `RECEIVING_BALL`, and `DRIBBLING`. A non-owner is receiving when their center is at most `receiving_distance` (default 1 m) from the ball center. Leaving that range resets their status. The owner is always marked dribbling. Receiving is a proximity state, not an immediate possession claim.

The engine's possession callback checks all player-ball contacts together at the start of a tick and after each physics substep, before bounce impulses or sequential overlap corrections can move the ball away. Contact means center distance is at most the sum of the player and ball radii, with a small numerical tolerance. A lone contacting player claims a free ball immediately. Multiple contacting players compete in one uniform random choice. A fast incoming ball can therefore be received during a substep even if the player was outside 1 m at the beginning of the tick. There is currently no speed or skill limit on trapping.

For a controlled ball, a new opponent contact triggers a uniform random contest between the carrier and all new challengers. A teammate cannot take the carrier's ball by walking into it. Continuous contacts are remembered so the same encounter is not rolled again every substep; an opponent must separate and touch again to challenge again. The winning owner is stored on the ball, and player statuses are refreshed. `CONTESTED` is not displayed as a lasting intermediate state because the random decision is immediate.

The carrier's dribble target is the center of the opposing team's goal, following the current implementation of `dribble_target`. Pressure within 3 m overrides that movement with a pass decision when a valid teammate is available. Teammates stop chasing their carrier, while the opposing team's nearest player pursues the ball. During a pass, the intended receiver holds the reception point. Running acceleration, turning limits, and pitch containment still apply.

These are simple gameplay rules, rather than a realistic model of trapping, shielding, or tackling. Calling `advance_physics` without the engine's possession callback retains pure ball collision behavior for standalone physics experiments.

## Time stepping and repeatability

`SoccerSimulation.step()` defaults to the configured 1/60 s tick. An explicit dt must be finite, positive, and no larger than 0.25 s. Faster playback should run more ticks, rather than request one large step.

Each tick runs decisions once, holds their target positions during physics, advances all bodies, and increments simulation time by dt. Physics subdivides the interval using:

```text
N = max(1, ceil(dt / max_substep), ceil(dt × relative_speed_bound / smallest_radius))
h = dt / N
```

The speed bound includes body speed caps and any larger current speed. For players it considers two players approaching, and for the ball it considers a player and ball approaching. Limiting relative travel to approximately the smallest body radius reduces tunneling. It is not continuous collision detection: extremely shallow grazing contacts can still be missed. A swept time-of-impact solver is the next improvement if those cases matter.

The Pygame loop accumulates elapsed wall time and runs fixed ticks as needed before drawing. A frame contributes at most 0.25 s to avoid an unlimited catch-up loop after a stall. Excess wall time is dropped; simulation time can therefore lag real time during a long interruption. Rendering currently shows the latest state without interpolation. Its pitch fit preserves equal meter scale in both axes; ball/player dots may be enlarged slightly for visibility.

The physical solver has no randomness. Possession contests use a separate `random.Random` instance per simulation. By default its seed is unspecified, so contests can vary between runs. Set `seed` in the simulation config to reproduce a scenario, including the same tick, contact, and command sequence, within the same numerical environment. Different tick durations can change when tactics makes decisions and when contacts occur. Floating point behavior is not promised to be bit-for-bit identical across platforms.

## Configuration and extension points

```python
from simulation import SoccerSimulation

simulation = SoccerSimulation({
    "pitch_width": 40,
    "pitch_height": 20,
    "fixed_dt": 1 / 60,
    "seed": 42,
    "receiving_distance": 1.0,
    "player": {"max_speed": 7, "max_deceleration": 5},
    "ball": {"rolling_deceleration": 0.8},
    "physics": {"contain_ball": True, "contact_iterations": 6},
})
simulation.step()
```

`objects.py` owns state and body parameters, `tactics.py` owns movement and pass decisions, `possession.py` owns receiving/contact claims, `physics.py` owns movement, pass trajectories, and contact detection, and `state.to_render_state` produces detached drawing data including statuses, ownership, and active pass intent. Pygame shows blue receiver rings, gold carrier rings, and a ball ownership/pass readout. The browser frontend remains independent.

Before comparing tactical strategies, validate running and stopping distances, turn behavior, and ball roll against chosen observations. Improve contact claims with interception, skill, and ball-speed constraints; add predictive avoidance to preferred movement. Each should have its own scenarios so changes in tactics can be distinguished from changes in locomotion.

## Verification

`tests/test_physics.py` checks acceleration and speed bounds, stationary-target arrival, idle braking distance, reversal, the turning ellipse, convergence across tick sizes, ball friction and stopping, momentum/restitution for an isolated contact, a fast head-on ball collision, coincident-body recovery, boundary behavior, controlled-ball attachment, and invalid inputs. Engine tests cover absolute targets, detached render data, decision/update ordering, and deterministic scenario replay.

`tests/test_possession.py` checks the 1 m receiving threshold, contact-only acquisition, full receiving-to-dribbling movement, fast-ball capture, simultaneous random selection, possession transfer, contact latching, teammate behavior, seeded replay, and goal-directed dribbling.

`tests/test_passing.py` checks the 3 m pressure threshold, nearest-teammate selection, distance ties, predicted arrival speed with and without friction, velocity direction, speed-cap rejection, complete reception, moving/backward releases without self-recapture, interception, detached pass metadata, and action ownership validation.

These checks verify the stated numerical model. They do not establish biological accuracy, collision-free planning, or tactical quality.

Run them with `python -m unittest discover -s tests` in the activated virtual environment, or `npm test` from the repository root after creating `.venv`.
