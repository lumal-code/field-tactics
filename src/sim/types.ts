import type { Vec2 } from './geometry';

export type PlayerAction = 'hold-shape' | 'press';

export interface PlayerState {
  id: number;
  role: string;
  position: Vec2;
  velocity: Vec2;
  target: Vec2;
  action: PlayerAction;
  decision: string;
}

export interface SimulationState {
  time: number;
  ball: Vec2;
  players: PlayerState[];
  tactics: TacticalConfig;
}

export interface SimulationConfig {
  pitchWidth: number;
  pitchHeight: number;
  fixedDt: number;
  maxSpeed: number;
  maxAcceleration: number;
  slowingRadius: number;
}

export interface TacticalConfig {
  // Absolute x coordinate of the defensive line, in pitch meters.
  lineHeight: number;
  // 1 is baseline spacing; smaller values make the unit tighter.
  compactness: number;
}
