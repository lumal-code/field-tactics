import type { GameState, TeamId } from '../types';

const TEAM_IDS: TeamId[] = ['left', 'right'];

export interface PlayerSelection { teamId: TeamId; playerId: number }

export function drawPitch(canvas: HTMLCanvasElement, state: GameState, selected: PlayerSelection | null): void {
  const context = canvas.getContext('2d');
  if (!context) return;

  const width = canvas.width;
  const height = canvas.height;
  const sx = width / state.pitch.width;
  const sy = height / state.pitch.height;
  context.fillStyle = '#173b32';
  context.fillRect(0, 0, width, height);

  context.strokeStyle = 'rgba(228, 244, 231, 0.55)';
  context.lineWidth = 2;
  context.strokeRect(10, 10, width - 20, height - 20);
  context.beginPath();
  context.moveTo(width / 2, 10);
  context.lineTo(width / 2, height - 10);
  context.stroke();
  context.beginPath();
  context.arc(width / 2, height / 2, 9 * sx, 0, Math.PI * 2);
  context.stroke();

  for (const teamId of TEAM_IDS) {
    for (const player of state.teams[teamId].players) {
      const active = selected?.teamId === teamId && selected.playerId === player.id;
      const x = player.position.x * sx;
      const y = player.position.y * sy;
      context.beginPath();
      context.arc(x, y, active ? 17 : 15, 0, Math.PI * 2);
      context.fillStyle = active ? '#f7ca78' : teamId === 'left' ? '#d5eee0' : '#f19b87';
      context.fill();
      context.fillStyle = '#173b32';
      context.font = 'bold 12px system-ui';
      context.textAlign = 'center';
      context.textBaseline = 'middle';
      context.fillText(String(player.id), x, y);
    }
  }

  context.beginPath();
  context.arc(state.ball.x * sx, state.ball.y * sy, 10, 0, Math.PI * 2);
  context.fillStyle = '#fff';
  context.fill();
  context.strokeStyle = '#1a2824';
  context.lineWidth = 3;
  context.stroke();
}

export function findPlayerAt(canvas: HTMLCanvasElement, state: GameState, clientX: number, clientY: number): PlayerSelection | null {
  const bounds = canvas.getBoundingClientRect();
  const x = ((clientX - bounds.left) / bounds.width) * state.pitch.width;
  const y = ((clientY - bounds.top) / bounds.height) * state.pitch.height;
  for (const teamId of TEAM_IDS) {
    const player = state.teams[teamId].players.find((candidate) =>
      Math.hypot(candidate.position.x - x, candidate.position.y - y) < 2.4,
    );
    if (player) return { teamId, playerId: player.id };
  }
  return null;
}
