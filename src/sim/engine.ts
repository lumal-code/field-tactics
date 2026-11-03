import { clampToPitch } from './geometry';
import type { Vec2 } from './geometry';
import { moveToward } from './movement';
import { DEFAULT_TACTICS_CONFIG, DEFENSIVE_ROLES, decideDefense, defensiveTarget, effectiveDefensiveAnchor } from './tactics';
import type { SimulationConfig, SimulationState, TacticalConfig } from './types';

export const DEFAULT_CONFIG: Readonly<SimulationConfig> = {
  pitchWidth: 100,
  pitchHeight: 68,
  fixedDt: 1 / 60,
  maxSpeed: 7,
  maxAcceleration: 14,
  slowingRadius: 4,
};

function initialState(config: SimulationConfig, tactics: TacticalConfig): SimulationState {
  const ball = { x: 68, y: config.pitchHeight / 2 };
  return {
    time: 0,
    ball,
    tactics: { ...tactics },
    players: DEFENSIVE_ROLES.map((role) => ({
      id: role.id,
      role: role.label,
      position: effectiveDefensiveAnchor(role.anchor, config, tactics),
      velocity: { x: 0, y: 0 },
      target: defensiveTarget(role.anchor, ball, config, tactics),
      action: 'hold-shape' as const,
      decision: 'Hold shape and shift with ball',
    })),
  };
}

export class SimulationEngine {
  private state: SimulationState;
  readonly config: Readonly<SimulationConfig>;

  constructor(config: SimulationConfig = DEFAULT_CONFIG) {
    this.config = { ...config };
    this.state = initialState(this.config, DEFAULT_TACTICS_CONFIG);
    this.updateTargets();
  }

  setTactics(update: Partial<TacticalConfig>): void {
    const next = { ...this.state.tactics, ...update };
    if (!Number.isFinite(next.lineHeight) || next.lineHeight < 0 || next.lineHeight > this.config.pitchWidth) {
      throw new RangeError('lineHeight must be within the pitch width');
    }
    if (!Number.isFinite(next.compactness) || next.compactness <= 0) {
      throw new RangeError('compactness must be a positive finite number');
    }
    this.state.tactics = next;
    this.updateTargets();
  }

  setBallPosition(position: Vec2): void {
    this.state.ball = clampToPitch(position, this.config.pitchWidth, this.config.pitchHeight);
    this.updateTargets();
  }

  step(): void {
    this.updateTargets();
    for (const player of this.state.players) {
      const moved = moveToward(player, player.target, this.config);
      player.position = moved.position;
      player.velocity = moved.velocity;
    }
    this.state.time += this.config.fixedDt;
  }

  reset(): void {
    this.state = initialState(this.config, this.state.tactics);
    this.updateTargets();
  }

  getSnapshot(): SimulationState {
    return {
      time: this.state.time,
      ball: { ...this.state.ball },
      tactics: { ...this.state.tactics },
      players: this.state.players.map((player) => ({
        ...player,
        position: { ...player.position },
        velocity: { ...player.velocity },
        target: { ...player.target },
      })),
    };
  }

  private updateTargets(): void {
    const decisions = decideDefense(this.getSnapshot(), this.config);
    for (let index = 0; index < decisions.length; index += 1) {
      const decision = decisions[index];
      const player = this.state.players[index];
      if (!decision || !player || player.id !== decision.playerId) throw new Error('Defensive decision mismatch');
      player.target = decision.target;
      player.action = decision.action;
      player.decision = decision.reason;
    }
  }
}
