# Field Tactics

The project now has two independent parts:

```text
simulation/        Python game state, engine loop, tactics, physics, Pygame visualizer
frontend/          React, TypeScript, and Canvas match view
tests/             Python engine tests
```

The browser currently renders a local, static 3v3 sample. It does not run or read the Python simulation. The Python engine currently starts a 3v1 rondo, with constrained running, braking, turning, rolling ball motion, disc contacts, possession, and passing. Carriers hold their position and, under pressure within 3 m, pass to the nearest teammate with a clear lane.

## Run the Python simulation

Requires Python 3.10+, Pygame, and NumPy. A virtual environment keeps the Python dependencies local to this project:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m simulation
.venv/bin/python -m unittest discover -s tests
```

The Pygame window draws the pitch, ball, and players from a plain-data view of the Python state. Press **Space** to play or pause, **Right Arrow** for one step while paused, **R** to reset, or **Esc** to quit. You can drag the ball. Short lines show player velocity. The default rondo pitch is 20 × 20 m and the physics runs at fixed ticks independently of drawing.

A blue ring means `RECEIVING_BALL` (within 1 m of the ball), and a gold ring means `DRIBBLING`. Physical contact claims a free ball. The ball follows its carrier, whose teammates stop chasing it. Opponent contact can challenge possession; simultaneous contacts are resolved randomly, once per continuous contact. Set `seed` in the simulation config for repeatable contests, and `receiving_distance` to change the 1 m threshold.

Under pressure (an opponent within 3 m), the carrier checks teammates from nearest to farthest. A defender blocks a lane if their body intersects the ball's straight path from release to reception, including the ball's radius. A blocked nearest option causes the carrier to try the other teammate; if all options are blocked, the carrier keeps dribbling. Kick speed accounts for distance and rolling friction, targeting at least 3 m/s at the teammate's current position. The receiver stays near that reception point, and the passer brakes while the ball travels. The ball readout shows the intended receiver during flight. Opponents can still move into the path and intercept after launch. This initial model does not lead a moving receiver or predict future defender positions.

The pressing player uses three decisions: go directly at the carrier when the ball is controlled, aim for a predicted interception point when it is loose and moving, and go directly at a stationary loose ball. Prediction accounts for rolling friction, estimated acceleration/speed, and a response-time margin, with a maximum three-second lookahead. It is recalculated every tick and does not model future collisions or exact turning time. An intended pass receiver still holds the reception point.

The rondo defender's `default_position` is the pitch center. When the ball is at least `reset_distance` (default 5 m) from the defender, its movement target becomes that default position. It runs back using normal physics and resumes pursuit as soon as the ball is closer than 5 m. The rule applies to players with a configured default position; the rondo attackers have none.

See [docs/physics.md](docs/physics.md) for the assumptions, formulas, parameter defaults, research sources, and verification scenarios. These parameters are engineering defaults, not measurements of real players.

Goal geometry lives in `simulation.state.goals["left"]` and `simulation.state.goals["right"]`. Each goal stores its defending team, mouth center, facing direction, width, and depth. Defaults are 3 m wide and 1 m deep; set `goal_width` and `goal_depth` in the simulation config to change them. Pygame draws this geometry. Scoring and goal-line crossing rules are not implemented yet.

## Run the browser preview

Requires Node.js 22.12+ or 24+ and npm.

```sh
npm ci
npm run dev
```

Open the URL printed by Vite. You can select a sample player to inspect its position. The browser view is a renderer preview, not a running match.

```sh
npm run check    # TypeScript check
npm run build    # browser bundle
npm test         # Python engine tests
```

## Next implementation points

- `simulation/state.py`: initial state and later state fields.
- `simulation/objects.py` and `simulation/vectors.py`: internal state objects and vector math.
- `simulation/engine.py`: update order and coordination between systems.
- `simulation/tactics.py`: pursuit, goal-directed dribbling, and passing decisions.
- `simulation/possession.py`: receiving statuses, contact claims, and random possession contests.
- `simulation/physics.py`: locomotion, rolling friction, substeps, and contact resolution.
- `simulation/visualizer.py`: Pygame drawing and controls.
- `frontend/src/render/pitch.ts`: Canvas drawing from a game-state object.

Keep the Python state shape and the TypeScript `GameState` type aligned when a connection is added later. For now they are separate by design.
