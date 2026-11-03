export interface Vec2 {
  x: number;
  y: number;
}

export function add(a: Vec2, b: Vec2): Vec2 {
  return { x: a.x + b.x, y: a.y + b.y };
}

export function subtract(a: Vec2, b: Vec2): Vec2 {
  return { x: a.x - b.x, y: a.y - b.y };
}

export function scale(v: Vec2, factor: number): Vec2 {
  return { x: v.x * factor, y: v.y * factor };
}

export function length(v: Vec2): number {
  return Math.hypot(v.x, v.y);
}

export function distance(a: Vec2, b: Vec2): number {
  return length(subtract(a, b));
}

export function limit(v: Vec2, maxLength: number): Vec2 {
  const magnitude = length(v);
  return magnitude > maxLength && magnitude > 0 ? scale(v, maxLength / magnitude) : { ...v };
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function clampToPitch(position: Vec2, width: number, height: number): Vec2 {
  return { x: clamp(position.x, 0, width), y: clamp(position.y, 0, height) };
}
