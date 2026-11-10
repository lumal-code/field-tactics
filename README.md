# Field Tactics

The project now has two independent parts:

```text
simulation/        Python game state, engine loop, tactics, physics, Pygame visualizer
frontend/          React, TypeScript, and Canvas match view
tests/             Python engine tests
```

The browser currently renders a local, static 3v3 sample. It does not run or read the Python simulation. The Python engine uses player, ball, and team objects; each team's closest player moves toward the ball. Possession and passing rules remain placeholders.

## Run the Python simulation

Requires Python 3.10+, Pygame, and NumPy. A virtual environment keeps the Python dependencies local to this project:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m simulation
.venv/bin/python -m unittest discover -s tests
```

The Pygame window draws the pitch, ball, and both three-player teams from a plain-data view of the Python state. Press **Space** to play or pause, **Right Arrow** for one step while paused, **R** to reset, or **Esc** to quit. You can drag the ball. The nearest player on each team follows it.

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
- `simulation/tactics.py`: nearest-player decision, with room for more jobs.
- `simulation/physics.py`: acceleration-limited movement and ball updates.
- `simulation/visualizer.py`: Pygame drawing and controls.
- `frontend/src/render/pitch.ts`: Canvas drawing from a game-state object.

Keep the Python state shape and the TypeScript `GameState` type aligned when a connection is added later. For now they are separate by design.
