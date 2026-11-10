"""Pygame view of the headless simulation state."""

import argparse

from .engine import SoccerSimulation
from .state import to_render_state
from .vectors import Vec2


WINDOW_WIDTH = 1080
WINDOW_HEIGHT = 800
PITCH_MARGIN = 40
PITCH_TOP = 72
PITCH_WIDTH = 1000
PITCH_HEIGHT = 680
PITCH_RECT = (PITCH_MARGIN, PITCH_TOP, PITCH_WIDTH, PITCH_HEIGHT)

BACKGROUND = (16, 27, 25)
GRASS = (23, 59, 50)
LINE = (194, 222, 202)
LEFT_PLAYER = (213, 238, 224)
RIGHT_PLAYER = (241, 155, 135)
BALL = (255, 255, 255)
TEXT = (233, 238, 233)
MUTED = (169, 188, 176)


def pitch_to_screen(position, pitch):
    """Map a position in meters to the window's pitch rectangle."""
    return (
        round(PITCH_MARGIN + position["x"] / pitch["width"] * PITCH_WIDTH),
        round(PITCH_TOP + position["y"] / pitch["height"] * PITCH_HEIGHT),
    )


def screen_to_pitch(point, pitch):
    """Map a mouse position to meters, clamped to the pitch."""
    x = (point[0] - PITCH_MARGIN) / PITCH_WIDTH * pitch["width"]
    y = (point[1] - PITCH_TOP) / PITCH_HEIGHT * pitch["height"]
    return {
        "x": min(max(x, 0.0), pitch["width"]),
        "y": min(max(y, 0.0), pitch["height"]),
    }


def draw_state(pygame, screen, state, font, small_font, step_count, running):
    state = to_render_state(state)
    screen.fill(BACKGROUND)
    pitch = state["pitch"]
    field = pygame.Rect(PITCH_RECT)
    pygame.draw.rect(screen, GRASS, field)
    pygame.draw.rect(screen, LINE, field, 2)

    center_x = field.centerx
    center_y = field.centery
    pygame.draw.line(screen, LINE, (center_x, field.top), (center_x, field.bottom), 2)
    pygame.draw.circle(screen, LINE, (center_x, center_y), round(9 / pitch["width"] * PITCH_WIDTH), 2)
    pygame.draw.circle(screen, LINE, (center_x, center_y), 3)

    box_width = round(16.5 / pitch["width"] * PITCH_WIDTH)
    box_height = round(40.3 / pitch["height"] * PITCH_HEIGHT)
    pygame.draw.rect(screen, LINE, pygame.Rect(field.left, center_y - box_height // 2, box_width, box_height), 2)
    pygame.draw.rect(screen, LINE, pygame.Rect(field.right - box_width, center_y - box_height // 2, box_width, box_height), 2)

    for team_id, color in (("left", LEFT_PLAYER), ("right", RIGHT_PLAYER)):
        for player in state["teams"][team_id]["players"]:
            center = pitch_to_screen(player["position"], pitch)
            pygame.draw.circle(screen, color, center, 15)
            label = small_font.render(str(player["id"]), True, BACKGROUND)
            screen.blit(label, label.get_rect(center=center))

    pygame.draw.circle(screen, BACKGROUND, pitch_to_screen(state["ball"], pitch), 12)
    pygame.draw.circle(screen, BALL, pitch_to_screen(state["ball"], pitch), 9)

    title = font.render("Field Tactics", True, TEXT)
    status = small_font.render(f"{'RUNNING' if running else 'PAUSED'}  ·  STEP {step_count}", True, MUTED)
    screen.blit(title, (PITCH_MARGIN, 24))
    screen.blit(status, (WINDOW_WIDTH - status.get_width() - PITCH_MARGIN, 31))

    help_text = "Space: play/pause   Right: single step   R: reset   Drag ball   Esc: quit"
    help_surface = small_font.render(help_text, True, MUTED)
    screen.blit(help_surface, (PITCH_MARGIN, WINDOW_HEIGHT - 29))
    pygame.display.flip()


def main():
    parser = argparse.ArgumentParser(description="Show the soccer simulation in a Pygame window")
    parser.add_argument("--dt", type=float, default=1 / 60, help="seconds passed to each simulation step")
    args = parser.parse_args()
    if args.dt <= 0:
        parser.error("--dt must be positive")

    try:
        import pygame
    except ModuleNotFoundError as exc:
        if exc.name != "pygame":
            raise
        parser.exit(1, "Pygame is required. Install it with: python3 -m pip install -r requirements.txt\n")

    pygame.init()
    try:
        screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Field Tactics - Python Visualizer")
        clock = pygame.time.Clock()
        font = pygame.font.SysFont(None, 28)
        small_font = pygame.font.SysFont(None, 20)
        simulation = SoccerSimulation({"pitch_width": 100, "pitch_height": 68})
        step_count = 0
        running = False
        dragging_ball = False
        open_window = True

        while open_window:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    open_window = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        open_window = False
                    elif event.key == pygame.K_SPACE:
                        running = not running
                    elif event.key == pygame.K_RIGHT and not running:
                        simulation.step(args.dt)
                        step_count += 1
                    elif event.key == pygame.K_r:
                        simulation = SoccerSimulation({"pitch_width": 100, "pitch_height": 68})
                        step_count = 0
                        running = False
                        dragging_ball = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if pygame.Rect(PITCH_RECT).collidepoint(event.pos):
                        rendered = to_render_state(simulation.state)
                        ball_pixel = pitch_to_screen(rendered["ball"], rendered["pitch"])
                        if (event.pos[0] - ball_pixel[0]) ** 2 + (event.pos[1] - ball_pixel[1]) ** 2 <= 18 ** 2:
                            dragging_ball = True
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    dragging_ball = False
                elif event.type == pygame.MOUSEMOTION and dragging_ball:
                    position = screen_to_pitch(event.pos, simulation.state.pitch)
                    simulation.state.ball.position = Vec2(position["x"], position["y"])

            if running:
                simulation.step(args.dt)
                step_count += 1

            draw_state(pygame, screen, simulation.state, font, small_font, step_count, running)
            clock.tick(60)
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
