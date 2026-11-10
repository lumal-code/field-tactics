# Phase 1: Python simulation skeleton

The simulation is a headless Python package. `SoccerSimulation.step(dt)` calls decision making, action application, physics, and rule resolution in that order, then returns `state`. `initialize_game(config)` creates a minimal 3v3 object state. The first decision rule sends the nearest player from each team toward the ball. Movement respects acceleration and speed limits. Ball contact, possession, passing, and other rules remain unimplemented.

The Python visualizer opens a Pygame window and draws a plain-data copy of the current state after each step. It can pause, single step, reset, and drag the ball. The React frontend lives under `frontend/` and renders a separate, static sample using Canvas. There is no API, shared runtime, or import between Python and TypeScript.

The next useful step is to add one defensive job or ball interaction at a time, with a scenario test for each. When the simulation produces meaningful states, choose a transport such as saved JSON traces or a local API, then feed those states into the existing Canvas renderer.
