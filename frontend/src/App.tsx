import { useEffect, useRef, useState } from 'react';
import { drawPitch, findPlayerAt } from './render/pitch';
import type { PlayerSelection } from './render/pitch';
import { sampleState } from './sampleState';

export default function App() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [selected, setSelected] = useState<PlayerSelection | null>(null);

  useEffect(() => {
    if (canvasRef.current) drawPitch(canvasRef.current, sampleState, selected);
  }, [selected]);

  const player = selected && sampleState.teams[selected.teamId].players.find((entry) => entry.id === selected.playerId);

  return (
    <main className="app">
      <header className="header">
        <div>
          <p className="eyebrow">FIELD TACTICS / FRONTEND PREVIEW</p>
          <h1>Match visualizer</h1>
          <p className="subtitle">A sample 3v3 state for checking the pitch renderer. Select a player to inspect its position.</p>
        </div>
        <span className="status">STATIC SAMPLE</span>
      </header>
      <section className="workspace" aria-label="Sample match state">
        <div className="pitch-panel">
          <canvas
            ref={canvasRef}
            width={1000}
            height={680}
            aria-label="Soccer pitch with three sample players per team"
            onClick={(event) => setSelected(findPlayerAt(event.currentTarget, sampleState, event.clientX, event.clientY))}
          />
          <div className="pitch-caption">Mint: left team · Coral: right team · White: ball</div>
        </div>
        <aside className="sidebar">
          <section className="card">
            <h2>Sample state</h2>
            <div className="readout"><span>Time</span><strong>{sampleState.time.toFixed(2)} s</strong></div>
            <div className="readout"><span>Pitch</span><strong>{sampleState.pitch.width} × {sampleState.pitch.height} m</strong></div>
            <div className="readout"><span>Ball</span><strong>{sampleState.ball.x}, {sampleState.ball.y} m</strong></div>
          </section>
          <section className="card">
            <h2>Player inspector</h2>
            {player ? <>
              <h3>{selected?.teamId} team · #{player.id}</h3>
              <div className="readout"><span>Position</span><strong>{player.position.x}, {player.position.y} m</strong></div>
            </> : <p className="hint">Select a player on the pitch.</p>}
          </section>
          <section className="card note">
            <h2>Current scope</h2>
            <p>The browser view uses local sample data. The Python simulation runs separately in the terminal.</p>
          </section>
        </aside>
      </section>
    </main>
  );
}
