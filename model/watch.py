"""Watch a saved policy with pause, single tick, reset, and ball dragging."""
from pathlib import Path

import pygame
from stable_baselines3 import PPO

from .environment import RondoEnv
from .observation import get_obs
from simulation.objects import BallStatus
from simulation.vectors import Vec2
from simulation.visualizer import (
    draw_state, pitch_rectangle, pitch_to_screen, screen_to_pitch,
    WINDOW_WIDTH, WINDOW_HEIGHT,
)


class PolicyPlayback:
    """Draw each physics tick; refresh the policy command every six ticks."""

    def __init__(self, env, model, seed=1000):
        self.env = env
        self.model = model
        self.seed = seed
        self.open_window = True
        self.reset()

    def reset(self):
        self.env.reset(seed=self.seed)
        self.running = False
        self.finished = False
        self.dragging = False
        self.result = ""
        self.ticks = 0
        self.decisions = 0
        self.ticks_left = 0
        self.action = Vec2(0, 0)
        self.velocity = Vec2(0, 0)

    @property
    def state(self):
        return self.env.sim.state

    @property
    def goal_depth(self):
        return max((g.depth for g in self.state.goals.values()), default=0.0)

    def tick(self):
        if self.finished or self.dragging:
            return
        if self.ticks_left == 0:
            obs = get_obs(self.state, self.env.player_key)
            action, _ = self.model.predict(obs, deterministic=True)
            self.action = Vec2(float(action[0]), float(action[1]))
            speed = self.env.player.max_speed
            self.velocity = (self.action * speed).limit(speed)
            self.ticks_left = 6
            self.decisions += 1

        self.env.sim.step(
            ignore_player=self.env.player_key, desired_velocity=self.velocity,
        )
        self.ticks += 1
        self.ticks_left -= 1
        # Match the environment's current episode-ending order.
        if self.state.time >= 30.0:
            self.result = "TIMEOUT"
        elif self.state.ball.owner == self.env.player_key:
            self.result = "WIN"
        if self.result:
            self.finished = True
            self.running = False
            print(self.result, {"time": self.state.time})

    def move_ball(self, point):
        position = screen_to_pitch(point, self.state.pitch, self.goal_depth)
        ball = self.state.ball
        ball.position = Vec2(
            min(max(position["x"], ball.radius), self.state.pitch["width"] - ball.radius),
            min(max(position["y"], ball.radius), self.state.pitch["height"] - ball.radius),
        )
        ball.velocity = Vec2(0, 0)
        ball.status = BallStatus.LOOSE
        ball.owner = None
        ball.pass_state = None
        self.env.sim.possession.update_statuses(self.state)
        # Invalidate the held command so the next tick uses the edited state.
        self.ticks_left = 0

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.open_window = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.open_window = False
            elif event.key == pygame.K_SPACE and not self.finished:
                self.running = not self.running
            elif event.key == pygame.K_RIGHT and not self.running:
                self.tick()
            elif event.key == pygame.K_r:
                self.reset()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.finished and pygame.Rect(pitch_rectangle(
                self.state.pitch, self.goal_depth,
            )).collidepoint(event.pos):
                ball = self.state.ball
                pixel = pitch_to_screen(
                    {"x": ball.position.x, "y": ball.position.y},
                    self.state.pitch, self.goal_depth,
                )
                if (event.pos[0] - pixel[0]) ** 2 + (event.pos[1] - pixel[1]) ** 2 <= 18 ** 2:
                    self.dragging = True
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self.move_ball(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging:
                self.move_ball(event.pos)
            self.dragging = False

    @property
    def detail(self):
        return (
            f"PPO decision {self.decisions} | action ({self.action.x:+.3f}, {self.action.y:+.3f})"
            f" | desired velocity ({self.velocity.x:+.2f}, {self.velocity.y:+.2f}) m/s"
            + (f" | {self.result} - R to reset" if self.finished else "")
        )


def main():
    model_path = Path(__file__).resolve().parents[1] / "rondo_defender.zip"
    model = PPO.load(model_path, device="cpu")
    env = RondoEnv()
    playback = PolicyPlayback(env, model)

    pygame.init()
    try:
        screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Field Tactics - PPO Defender")
        font = pygame.font.SysFont(None, 28)
        small_font = pygame.font.SysFont(None, 20)
        clock = pygame.time.Clock()
        accumulated = 0.0

        while playback.open_window:
            elapsed = min(clock.tick(60) / 1000, 0.25)
            for event in pygame.event.get():
                playback.handle_event(event)
                if event.type == pygame.KEYDOWN:
                    accumulated = 0.0
            if not playback.open_window:
                break
            if playback.running and not playback.dragging:
                accumulated += elapsed
                while accumulated >= env.sim.fixed_dt and playback.running:
                    playback.tick()
                    accumulated -= env.sim.fixed_dt
            else:
                accumulated = 0.0
            draw_state(
                pygame, screen, playback.state, font, small_font,
                playback.ticks, playback.running, detail_text=playback.detail,
            )
    finally:
        env.close()
        pygame.quit()


if __name__ == "__main__":
    main()
