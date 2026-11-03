import { add, clampToPitch, length, limit, scale, subtract } from './geometry';
import type { Vec2 } from './geometry';
import type { SimulationConfig } from './types';

export interface MovementState {
  position: Vec2;
  velocity: Vec2;
}

export function moveToward(
  player: MovementState,
  target: Vec2,
  config: SimulationConfig,
): MovementState {
  const displacement = subtract(target, player.position);
  const remaining = length(displacement);
  const desiredSpeed = config.maxSpeed * Math.min(1, remaining / config.slowingRadius);
  const desiredVelocity = remaining === 0 ? { x: 0, y: 0 } : scale(displacement, desiredSpeed / remaining);
  const velocityChange = limit(subtract(desiredVelocity, player.velocity), config.maxAcceleration * config.fixedDt);
  const velocity = limit(add(player.velocity, velocityChange), config.maxSpeed);
  const nextPosition = add(player.position, scale(velocity, config.fixedDt));
  const position = clampToPitch(nextPosition, config.pitchWidth, config.pitchHeight);

  // Remove outward velocity at a boundary so the player does not keep pushing against it.
  return {
    position,
    velocity: {
      x: position.x !== nextPosition.x ? 0 : velocity.x,
      y: position.y !== nextPosition.y ? 0 : velocity.y,
    },
  };
}
