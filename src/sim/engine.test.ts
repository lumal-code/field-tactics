import { describe, expect, it } from 'vitest';
import { SimulationEngine, DEFAULT_CONFIG } from './engine';
import { distance, length, limit } from './geometry';
import { moveToward } from './movement';

describe('geometry and movement', () => {
  it('limits a vector without changing its direction', () => {
    const result = limit({ x: 3, y: 4 }, 2);
    expect(result.x).toBeCloseTo(1.2);
    expect(result.y).toBeCloseTo(1.6);
    expect(distance({ x: 0, y: 0 }, { x: 3, y: 4 })).toBe(5);
  });

  it('respects acceleration and speed limits over repeated steps', () => {
    let player = { position: { x: 10, y: 34 }, velocity: { x: 0, y: 0 } };
    for (let tick = 0; tick < 600; tick += 1) {
      const previous = player.velocity;
      player = moveToward(player, { x: 90, y: 34 }, DEFAULT_CONFIG);
      expect(length(player.velocity)).toBeLessThanOrEqual(DEFAULT_CONFIG.maxSpeed + 1e-10);
      expect(distance(previous, player.velocity)).toBeLessThanOrEqual(DEFAULT_CONFIG.maxAcceleration * DEFAULT_CONFIG.fixedDt + 1e-10);
    }
    expect(player.position.x).toBeGreaterThan(50);
  });
});

describe('simulation engine', () => {
  it('moves the presser toward the ball while other defenders preserve shape targets', () => {
    const engine = new SimulationEngine();
    engine.setBallPosition({ x: 100, y: 68 });
    const before = engine.getSnapshot();
    expect(before.players.map((player) => player.target)).toEqual([
      { x: 47, y: 30.2 },
      { x: 47, y: 44.2 },
      { x: 100, y: 68 },
    ]);
    expect(before.players.map((player) => player.action)).toEqual(['hold-shape', 'hold-shape', 'press']);
    for (let tick = 0; tick < 120; tick += 1) engine.step();
    const after = engine.getSnapshot();
    expect(after.players[0]!.position.x).toBeGreaterThan(before.players[0]!.position.x);
    expect(after.players[0]!.target.y - after.players[1]!.target.y).toBeCloseTo(-14);
  });

  it('clamps the ball to the pitch and replays deterministically', () => {
    const first = new SimulationEngine();
    const second = new SimulationEngine();
    for (const engine of [first, second]) {
      engine.setBallPosition({ x: 200, y: -10 });
      for (let tick = 0; tick < 180; tick += 1) engine.step();
    }
    expect(first.getSnapshot().ball).toEqual({ x: 100, y: 0 });
    expect(first.getSnapshot()).toEqual(second.getSnapshot());
  });

  it('does not expose mutable internal state through snapshots', () => {
    const engine = new SimulationEngine();
    const snapshot = engine.getSnapshot();
    snapshot.players[0]!.position.x = -100;
    snapshot.ball.x = -100;
    expect(engine.getSnapshot().players[0]!.position.x).toBe(35);
    expect(engine.getSnapshot().ball.x).toBe(68);
  });

  it('applies tactical settings to targets without moving players until a step', () => {
    const configured = new SimulationEngine();
    const baseline = new SimulationEngine();
    const before = configured.getSnapshot();
    configured.setTactics({ lineHeight: 48 });
    configured.setTactics({ compactness: 0.75 });
    const after = configured.getSnapshot();
    expect(after.tactics).toEqual({ lineHeight: 48, compactness: 0.75 });
    expect(after.players.map((player) => player.position)).toEqual(before.players.map((player) => player.position));
    expect(after.players.map((player) => player.decision)).toEqual(before.players.map((player) => player.decision));
    expect(after.players[0]!.target.x - baseline.getSnapshot().players[0]!.target.x).toBeCloseTo(13);
    expect(after.players[2]!.target.y - after.players[0]!.target.y).toBeCloseTo(21);
    expect(after.players[1]!.target).toEqual(after.ball);

    configured.step();
    expect(configured.getSnapshot().players[1]!.position.x).toBeGreaterThan(before.players[1]!.position.x);

    const snapshot = configured.getSnapshot();
    snapshot.tactics.lineHeight = 0;
    expect(configured.getSnapshot().tactics.lineHeight).toBe(48);
    configured.reset();
    expect(configured.getSnapshot().tactics).toEqual({ lineHeight: 48, compactness: 0.75 });
    expect(configured.getSnapshot().players[0]!.position).toEqual({ x: 48, y: 23.5 });
  });
});

describe('decisions', () => {
  it('closest player chooses to press', () => {
    const engine = new SimulationEngine();
    expect(engine.getSnapshot().players.filter((player) => player.action === 'press').map((player) => player.id)).toEqual([3]);

    engine.setBallPosition({ x: 35, y: 20 });
    const movedBall = engine.getSnapshot();
    expect(movedBall.players.filter((player) => player.action === 'press').map((player) => player.id)).toEqual([2]);
    expect(movedBall.players[0]!.target).toEqual(movedBall.ball);

    engine.setBallPosition({ x: 35, y: 27 });
    expect(engine.getSnapshot().players.filter((player) => player.action === 'press').map((player) => player.id)).toEqual([2]);
  });
});
