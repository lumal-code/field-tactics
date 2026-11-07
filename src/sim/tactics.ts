import { clampToPitch, distance, dot, length, scale, subtract, add } from './geometry';
import type { Vec2 } from './geometry';
import type { PlayerAction, PlayerState, SimulationConfig, SimulationState, TacticalConfig } from './types';

export interface DefensiveRole {
  id: number;
  label: string;
  anchor: Vec2;
}

export const DEFAULT_TACTICS_CONFIG: Readonly<TacticalConfig> = {
  lineHeight: 35,
  compactness: 1,
};

export const DEFENSIVE_ROLES: readonly DefensiveRole[] = [
  { id: 2, label: 'Left defender', anchor: { x: 35, y: 20 } },
  { id: 3, label: 'Center defender', anchor: { x: 35, y: 34 } },
  { id: 4, label: 'Right defender', anchor: { x: 35, y: 48 } },
];

export interface PlayerDecision {
  playerId: number;
  action: PlayerAction;
  target: Vec2;
  reason: string;
}

const rolesById = new Map(DEFENSIVE_ROLES.map((role) => [role.id, role]));

export function selectClosestPlayer(players: readonly PlayerState[], ball: Vec2): PlayerState | undefined {
  let closest: PlayerState | undefined;
  let shortestDistance = Infinity;
  for (const player of players) {
    const playerDistance = distance(player.position, ball);
    if (playerDistance < shortestDistance || (playerDistance === shortestDistance && closest && player.id < closest.id)) {
      closest = player;
      shortestDistance = playerDistance;
    }
  }
  return closest;
}

export function selectNextClosest(players: readonly PlayerState[], ball: Vec2, currPresser: number | undefined): PlayerState | undefined {
  let nextClosest: PlayerState | undefined;
  let shortestDistance = Infinity;
  for (const player of players) {
    if (player.id === currPresser) {
      continue;
    }
    const playerDistance = distance(player.position, ball);
    if (playerDistance < shortestDistance || (playerDistance === shortestDistance && nextClosest && player.id < nextClosest.id)) {
      nextClosest = player;
      shortestDistance = playerDistance;
    }
  }
  return nextClosest;
}

export function decideDefense(state: Readonly<SimulationState>, config: SimulationConfig): PlayerDecision[] {
  const presserId = selectClosestPlayer(state.players, state.ball)?.id;
  const coverId = selectNextClosest(state.players, state.ball, presserId)?.id;
  return state.players.map((player): PlayerDecision => {
    if (player.id === presserId) {
      return {
        playerId: player.id,
        action: 'press',
        target: press(player, state.ball, config),
        reason: 'Press ball: closest defender',
      };
    }
    if (player.id === coverId) {
      return {
        playerId: player.id,
        action: 'cover',
        target: betweenBallAndGoal(player, state.ball, config),
        reason: 'Cover ball: second closest',
      };
    }
    const role = rolesById.get(player.id);
    if (!role) throw new Error(`No defensive role for player ${player.id}`);
    return {
      playerId: player.id,
      action: 'hold-shape',
      target: defensiveTarget(role.anchor, state.ball, config, state.tactics),
      reason: 'Hold shape and shift with ball',
    };
  });
}

export function betweenBallAndGoal(player: PlayerState, ball: Vec2, config: SimulationConfig): Vec2 {
  const goal: Vec2 = { x: 0, y: config.pitchHeight / 2 };
  const ballToPlayer: Vec2 = subtract(player.position, ball);
  const ballToGoal: Vec2 = subtract(goal, ball);
  const b: Vec2 = ballToGoal;
  const a: Vec2 = ballToPlayer;
  const goalDistanceSquared = dot(b, b);
  if (goalDistanceSquared === 0) return { ...ball };

  const projbA: Vec2 = scale(ballToGoal, Math.abs(dot(a, b) / goalDistanceSquared));
  const dirToLine: Vec2 = subtract(projbA, ballToPlayer);

  return clampToPitch(
    {
      x: player.position.x + dirToLine.x,
      y: player.position.y + dirToLine.y,
    },
    config.pitchWidth,
    config.pitchHeight
  );
}

export function press(player: PlayerState, ball: Vec2, config: SimulationConfig): Vec2 {
  const goal: Vec2 = { x: 0, y: config.pitchHeight / 2 };
  const playerToBall: Vec2 = subtract(ball, player.position);
  const ballToGoal: Vec2 = subtract(goal, ball);

  const distanceToGoal = length(ballToGoal);
  const goalwardOffset = distanceToGoal === 0
    ? { x: 0, y: 0 }
    : scale(ballToGoal, Math.min(2, distanceToGoal) / distanceToGoal);
  const targetDisplacement = add(playerToBall, goalwardOffset);

  return clampToPitch(add(player.position, targetDisplacement), config.pitchWidth, config.pitchHeight);
}

export function effectiveDefensiveAnchor(anchor: Vec2, config: SimulationConfig, tactics: TacticalConfig): Vec2 {
  const centerY = config.pitchHeight / 2;
  return clampToPitch(
    {
      x: anchor.x + tactics.lineHeight - DEFAULT_TACTICS_CONFIG.lineHeight,
      y: centerY + (anchor.y - centerY) * tactics.compactness,
    },
    config.pitchWidth,
    config.pitchHeight,
  );
}

export function defensiveTarget(anchor: Vec2, ball: Vec2, config: SimulationConfig, tactics: TacticalConfig): Vec2 {
  const effectiveAnchor = effectiveDefensiveAnchor(anchor, config, tactics);
  const ballOffsetX = ball.x - config.pitchWidth / 2;
  const ballOffsetY = ball.y - config.pitchHeight / 2;
  return clampToPitch(
    { x: effectiveAnchor.x + ballOffsetX * 0.24, y: effectiveAnchor.y + ballOffsetY * 0.3 },
    config.pitchWidth,
    config.pitchHeight,
  );
}
