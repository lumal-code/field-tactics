import { useEffect, useRef, useState } from 'react';
import type { PointerEvent } from 'react';
import { SimulationEngine } from './sim/engine';
import { distance, length } from './sim/geometry';
import { drawPitch, findPlayerAt, pointerToPitch } from './render/pitch';
import type { SimulationState } from './sim/types';

export default function App() {
  const [engine] = useState(() => new SimulationEngine());
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const draggingBallRef = useRef(false);
  const playingRef = useRef(false);
  const speedRef = useRef(1);
  const selectedIdRef = useRef<number | null>(3);
  const [snapshot, setSnapshot] = useState<SimulationState>(() => engine.getSnapshot());
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [selectedId, setSelectedId] = useState<number | null>(3);

  useEffect(() => {
    let frame = 0;
    let previous = 0;
    let accumulated = 0;
    const tick = (now: number) => {
      if (previous === 0) previous = now;
      const elapsed = Math.min((now - previous) / 1000, 0.1);
      previous = now;
      let steps = 0;
      if (playingRef.current) {
        accumulated += elapsed * speedRef.current;
        while (accumulated >= engine.config.fixedDt && steps < 12) {
          engine.step();
          accumulated -= engine.config.fixedDt;
          steps += 1;
        }
        if (steps === 12) accumulated = 0;
      } else {
        accumulated = 0;
      }
      const next = engine.getSnapshot();
      if (steps > 0) setSnapshot(next);
      if (canvasRef.current) drawPitch(canvasRef.current, next, selectedIdRef.current);
      frame = requestAnimationFrame(tick);
    };

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [engine]);

  function togglePlaying() {
    const next = !playingRef.current;
    playingRef.current = next;
    setPlaying(next);
  }

  function reset() {
    engine.reset();
    playingRef.current = false;
    setPlaying(false);
    setSnapshot(engine.getSnapshot());
  }

  function onPointerDown(event: PointerEvent<HTMLCanvasElement>) {
    const canvas = event.currentTarget;
    const point = pointerToPitch(canvas, event.clientX, event.clientY);
    const state = engine.getSnapshot();
    if (distance(state.ball, point) < 3) {
      draggingBallRef.current = true;
      canvas.setPointerCapture(event.pointerId);
      engine.setBallPosition(point);
      setSnapshot(engine.getSnapshot());
    } else {
      const playerId = findPlayerAt(state, point.x, point.y);
      if (playerId !== null) {
        selectedIdRef.current = playerId;
        setSelectedId(playerId);
      }
    }
  }

  function onPointerMove(event: PointerEvent<HTMLCanvasElement>) {
    if (draggingBallRef.current) {
      engine.setBallPosition(pointerToPitch(event.currentTarget, event.clientX, event.clientY));
      setSnapshot(engine.getSnapshot());
    }
  }

  function onPointerUp(event: PointerEvent<HTMLCanvasElement>) {
    draggingBallRef.current = false;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  }

  const selected = snapshot.players.find((player) => player.id === selectedId);

  return (
    <main className="app">
      <header className="header">
        <div>
          <p className="eyebrow">FIELD TACTICS / PHASE 1</p>
          <h1>Defensive shape lab</h1>
          <p className="subtitle">Drag the ball. The closest defender presses while teammates hold their shape.</p>
        </div>
        <span className="status">{playing ? 'RUNNING' : 'PAUSED'}</span>
      </header>

      <section className="workspace" aria-label="Simulation workspace">
        <div className="pitch-panel">
          <canvas
            ref={canvasRef}
            width={1000}
            height={680}
            aria-label="Soccer pitch with draggable ball and three defenders"
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={onPointerUp}
          />
          <div className="pitch-caption"><span>● Ball: drag to reposition</span><span>○ Dotted lines: movement targets</span></div>
        </div>

        <aside className="sidebar">
          <section className="card">
            <h2>Simulation</h2>
            <div className="controls">
              <button type="button" className="primary" onClick={togglePlaying}>{playing ? 'Pause' : 'Start'}</button>
              <button type="button" onClick={reset}>Reset</button>
            </div>
            <label className="field">Playback speed
              <select value={speed} onChange={(event) => {
                const next = Number(event.target.value);
                speedRef.current = next;
                setSpeed(next);
              }}>
                <option value={1}>1×</option>
                <option value={2}>2×</option>
                <option value={4}>4×</option>
              </select>
            </label>
            <div className="readout"><span>Simulation time</span><strong>{snapshot.time.toFixed(2)} s</strong></div>
          </section>

          <section className="card">
            <h2>Tactical settings</h2>
            <label className="field tactic-control">
              <span>Line height <strong>{snapshot.tactics.lineHeight} m</strong></span>
              <input type="range" min="20" max="55" step="1" value={snapshot.tactics.lineHeight}
                onChange={(event) => {
                  engine.setTactics({ lineHeight: Number(event.target.value) });
                  setSnapshot(engine.getSnapshot());
                }} />
            </label>
            <label className="field tactic-control">
              <span>Compactness <strong>{snapshot.tactics.compactness.toFixed(2)}</strong></span>
              <input type="range" min="0.5" max="1.5" step="0.05" value={snapshot.tactics.compactness}
                onChange={(event) => {
                  engine.setTactics({ compactness: Number(event.target.value) });
                  setSnapshot(engine.getSnapshot());
                }} />
            </label>
            <p className="hint">Targets respond immediately. Players follow when running; lower compactness tightens their spacing.</p>
          </section>

          <section className="card">
            <h2>Player inspector</h2>
            <p className="hint">Select a defender on the pitch.</p>
            {selected ? <>
              <h3>{selected.role}</h3>
              <div className="readout"><span>Position</span><strong>{selected.position.x.toFixed(1)}, {selected.position.y.toFixed(1)} m</strong></div>
              <div className="readout"><span>Target</span><strong>{selected.target.x.toFixed(1)}, {selected.target.y.toFixed(1)} m</strong></div>
              <div className="readout"><span>Speed</span><strong>{length(selected.velocity).toFixed(2)} m/s</strong></div>
              <div className="readout"><span>To target</span><strong>{distance(selected.position, selected.target).toFixed(1)} m</strong></div>
              <div className="readout"><span>Action</span><strong>{selected.action}</strong></div>
              <div className="decision"><span>Current decision</span><p>{selected.decision}</p></div>
            </> : <p>No player selected.</p>}
          </section>

          <section className="card note">
            <h2>Model scope</h2>
            <p>This first slice tests deterministic movement, ball-relative shape, and a basic closest-player press. Marking, passing, and possession come later.</p>
          </section>
        </aside>
      </section>
    </main>
  );
}
