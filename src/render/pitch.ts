import type { SimulationState } from '../sim/types';
import { DEFAULT_CONFIG } from '../sim/engine';

const WIDTH = 1000;
const HEIGHT = 680;
const SCALE = 10;

export function drawPitch(canvas: HTMLCanvasElement, state: SimulationState, selectedId: number | null): void {
  const context = canvas.getContext('2d');
  if (!context) return;
  context.clearRect(0, 0, WIDTH, HEIGHT);
  context.fillStyle = '#173b32';
  context.fillRect(0, 0, WIDTH, HEIGHT);

  context.strokeStyle = 'rgba(228, 244, 231, 0.48)';
  context.lineWidth = 2;
  context.strokeRect(10, 10, WIDTH - 20, HEIGHT - 20);
  context.beginPath();
  context.moveTo(WIDTH / 2, 10);
  context.lineTo(WIDTH / 2, HEIGHT - 10);
  context.moveTo(10, 170);
  context.lineTo(170, 170);
  context.lineTo(170, 510);
  context.lineTo(10, 510);
  context.moveTo(WIDTH - 10, 170);
  context.lineTo(WIDTH - 170, 170);
  context.lineTo(WIDTH - 170, 510);
  context.lineTo(WIDTH - 10, 510);
  context.stroke();
  context.beginPath();
  context.arc(WIDTH / 2, HEIGHT / 2, 90, 0, Math.PI * 2);
  context.stroke();

  for (const player of state.players) {
    const selected = player.id === selectedId;
    const px = player.position.x * SCALE;
    const py = player.position.y * SCALE;
    const tx = player.target.x * SCALE;
    const ty = player.target.y * SCALE;
    context.setLineDash([5, 6]);
    context.strokeStyle = selected ? '#f7ca78' : 'rgba(150, 216, 191, 0.55)';
    context.beginPath();
    context.moveTo(px, py);
    context.lineTo(tx, ty);
    context.stroke();
    context.setLineDash([]);
    context.beginPath();
    context.arc(tx, ty, selected ? 7 : 5, 0, Math.PI * 2);
    context.fillStyle = selected ? '#f7ca78' : '#88bea9';
    context.fill();
    context.beginPath();
    context.arc(px, py, selected ? 16 : 14, 0, Math.PI * 2);
    context.fillStyle = selected ? '#f7ca78' : '#d5eee0';
    context.fill();
    context.fillStyle = '#173b32';
    context.font = 'bold 12px system-ui';
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    context.fillText(String(player.id), px, py);
  }

  context.beginPath();
  context.arc(state.ball.x * SCALE, state.ball.y * SCALE, 10, 0, Math.PI * 2);
  context.fillStyle = '#ffffff';
  context.fill();
  context.strokeStyle = '#1a2824';
  context.lineWidth = 3;
  context.stroke();
}

export function pointerToPitch(canvas: HTMLCanvasElement, clientX: number, clientY: number) {
  const bounds = canvas.getBoundingClientRect();
  return {
    x: ((clientX - bounds.left) / bounds.width) * DEFAULT_CONFIG.pitchWidth,
    y: ((clientY - bounds.top) / bounds.height) * DEFAULT_CONFIG.pitchHeight,
  };
}

export function findPlayerAt(state: SimulationState, x: number, y: number): number | null {
  const player = state.players.find((candidate) => Math.hypot(candidate.position.x - x, candidate.position.y - y) < 2.4);
  return player?.id ?? null;
}
