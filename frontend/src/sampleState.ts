import type { GameState } from './types';

// A standalone drawing example. It is not loaded from the Python simulation.
export const sampleState: GameState = {
  time: 0,
  pitch: { width: 100, height: 68 },
  ball: { x: 68, y: 34 },
  teams: {
    left: { players: [
      { id: 2, position: { x: 35, y: 20 } },
      { id: 3, position: { x: 35, y: 34 } },
      { id: 4, position: { x: 35, y: 48 } },
    ] },
    right: { players: [
      { id: 2, position: { x: 65, y: 20 } },
      { id: 3, position: { x: 65, y: 34 } },
      { id: 4, position: { x: 65, y: 48 } },
    ] },
  },
};
