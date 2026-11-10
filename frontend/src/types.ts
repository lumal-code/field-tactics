export type TeamId = 'left' | 'right';

export interface Position { x: number; y: number }
export interface Player { id: number; position: Position }
export interface Team { players: Player[] }

export interface GameState {
  time: number;
  pitch: { width: number; height: number };
  ball: Position;
  teams: Record<TeamId, Team>;
}
