# Field Tactics

A small, browser-based soccer tactics simulator. The engine is plain TypeScript and has no browser or React dependency, so the same scenarios can run in tests and future batch experiments.

## Run

Requires Node.js 22.12+ or 24+ and npm.

```sh
npm ci
npm run dev
```

Open the local URL printed by Vite. Drag the ball to see the closest defender press while the others shift together. Start or pause the simulation, reset it, change playback speed, and select a defender to inspect its target and decision.

```sh
npm run check   # TypeScript type check
npm run check:watch  # keep checking types while editing (second terminal)
npm test        # deterministic engine tests
npm run build   # production browser bundle
```

`npm run dev` checks types before starting. During development, run `npm run check:watch` in another terminal to see new type errors as files change. Browser runtime errors appear in the browser developer console.

## Architecture and Phase 1 plan

See [docs/phase-1.md](docs/phase-1.md) for the state model, update loop, movement equations, tactical target calculation, tradeoffs, and next steps.
