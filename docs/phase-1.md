# Phase 1: simulation foundation

## What is in the repository

The original starter had one TypeScript file, a CommonJS/ES module conflict, an incompatible `ts-node`/TypeScript combination, and no working test, build, or browser entry point. The current setup uses Vite for the browser, Vitest for headless tests, and a separate `src/sim` module for simulation code.

## Architectural decisions

- **State:** `SimulationState` holds simulation time, ball position, and player position, velocity, target, and decision. Coordinates are in meters on a 100 × 68 pitch. Tactical anchors and movement limits live in configuration, rather than in rendering code. Plain objects are easier to serialize, inspect, and compare than a hierarchy of mutable agent classes. We can add agent policies behind functions when the behavior warrants it.
- **Update loop:** the engine advances exactly 1/60 second per `step()`. The browser uses `requestAnimationFrame` only to decide how many fixed steps to run, with an accumulator and a catch-up cap. This prevents variable frame rate from changing movement math. Under severe browser lag, the display may fall behind simulation time because the cap favors responsiveness. Headless experiments can call `step()` directly for exact tick counts.
- **Movement:** a player seeks its tactical target using desired velocity. Its change in velocity is limited to `maxAcceleration × dt`, velocity is limited to `maxSpeed`, and position is integrated with the new velocity. A slowing radius reduces overshoot near a target. Pitch boundaries are clamped. This is a simple, stable steering model, not collision or biomechanics simulation.
- **Defensive position:** each defender has a fixed formation anchor. Line height and compactness produce an effective anchor, then the unit shifts by a bounded fraction of the ball's displacement from midfield. The closest defender is assigned to press the ball while the others hold shape. This is only a first pressing rule; marking, lane blocking, and stable assignment under changing distances still need work.
- **Rendering:** React owns controls and the selected-player inspector. Canvas draws a snapshot and maps pointer movement to ball coordinates. The renderer never changes player decisions. The engine has no DOM, Canvas, React, timer, or random-number dependency.
- **Reproducibility:** no randomness is used in Phase 1. Resetting and replaying the same ball positions at the same ticks should produce the same state. Future stochastic scenarios should receive a seeded random source.

## Smallest validating demonstration

Drag the ball across the pitch while three defenders maintain their relative shape and move toward new targets with speed and acceleration limits. Pause, select a player, and inspect its target and decision. This checks the engine/UI boundary and makes incorrect steering or target calculations visible.

## Tests and evidence

The initial tests cover vector limits and distance, speed/acceleration bounds, deterministic replay, tactical shape translation, boundary clamping, and snapshot isolation. Visual plausibility alone does not establish tactical quality. Phase 2 should add measurable compactness, pressure distance, and lane coverage metrics before comparing tactical settings.

## Next work, sized for 5–10 hours per week

1. **Week 1:** refine the fixed-step engine and ball dragging, inspect target overlays, and add edge-case tests. The current slice is the starting point.
2. **Week 2:** refine the line height and compactness controls and measure their effect on targets and settled player positions. The basic controls and target tests are in place.
3. **Week 3:** refine the basic closest-player press, add one cover assignment and a simple pass-lane score. Show the selected action and its reason in the inspector.
4. **Week 4:** create a few repeatable ball-carrier scenarios and report pressure distance, shape width/depth, and lane availability. Keep passing and full 5v5 interactions for Phase 3.

Each step should leave a usable demo and passing headless tests. Use a small, measured behavior change before adding more agent rules.
