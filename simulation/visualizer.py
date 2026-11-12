"""Pygame view of the headless simulation state."""

import argparse
from math import isfinite

from .engine import SoccerSimulation
from .objects import BallStatus
from .state import to_render_state
from .vectors import Vec2


WINDOW_WIDTH = 1080
WINDOW_HEIGHT = 800
PITCH_MARGIN = 40
PITCH_TOP = 72
PITCH_WIDTH = 1000
PITCH_HEIGHT = 680

BACKGROUND = (16, 27, 25)
GRASS = (23, 59, 50)
LINE = (194, 222, 202)
LEFT_PLAYER = (213, 238, 224)
RIGHT_PLAYER = (241, 155, 135)
BALL = (255, 255, 255)
TEXT = (233, 238, 233)
MUTED = (169, 188, 176)
RECEIVING = (102, 190, 235)
DRIBBLING = (247, 202, 120)


def pitch_rectangle(pitch, goal_depth=0.0):
    """Fit the pitch without stretching distances along either axis."""
    scale = min(PITCH_WIDTH / (pitch["width"] + 2 * goal_depth), PITCH_HEIGHT / pitch["height"])
    width, height = pitch["width"] * scale, pitch["height"] * scale
    return (PITCH_MARGIN + (PITCH_WIDTH - width) / 2, PITCH_TOP + (PITCH_HEIGHT - height) / 2, width, height)


def pitch_to_screen(position, pitch, goal_depth=0.0):
    """Map a position in meters to the window's pitch rectangle."""
    left, top, width, height = pitch_rectangle(pitch, goal_depth)
    return (round(left + position["x"] / pitch["width"] * width), round(top + position["y"] / pitch["height"] * height))


def screen_to_pitch(point, pitch, goal_depth=0.0):
    """Map a mouse position to meters, clamped to the pitch."""
    left, top, width, height = pitch_rectangle(pitch, goal_depth)
    x = (point[0] - left) / width * pitch["width"]
    y = (point[1] - top) / height * pitch["height"]
    return {
        "x": min(max(x, 0.0), pitch["width"]),
        "y": min(max(y, 0.0), pitch["height"]),
    }


def draw_state(pygame, screen, state, font, small_font, step_count, running):
    state = to_render_state(state)
    screen.fill(BACKGROUND)
    pitch = state["pitch"]
    goal_depth = max((goal["depth"] for goal in state["goals"].values()), default=0.0)

    def project(position):
        return pitch_to_screen(position, pitch, goal_depth)

    field = pygame.Rect(pitch_rectangle(pitch, goal_depth))
    scale = field.width / pitch["width"]
    pygame.draw.rect(screen, GRASS, field)
    pygame.draw.rect(screen, LINE, field, 2)

    center_x = field.centerx
    center_y = field.centery
    pygame.draw.line(screen, LINE, (center_x, field.top), (center_x, field.bottom), 2)
    pygame.draw.circle(screen, LINE, (center_x, center_y), round(0.13 * min(field.width, field.height)), 2)
    pygame.draw.circle(screen, LINE, (center_x, center_y), 3)

    box_width = round(field.width * 0.16)
    box_height = round(field.height * 0.5)
    pygame.draw.rect(screen, LINE, pygame.Rect(field.left, center_y - box_height // 2, box_width, box_height), 2)
    pygame.draw.rect(screen, LINE, pygame.Rect(field.right - box_width, center_y - box_height // 2, box_width, box_height), 2)

    for goal in state["goals"].values():
        position, facing = goal["position"], goal["facing"]
        tangent = {"x": -facing["y"], "y": facing["x"]}
        posts = [
            {axis: position[axis] + side * tangent[axis] * goal["width"] / 2 for axis in ("x", "y")}
            for side in (-1, 1)
        ]
        back = [{axis: post[axis] - facing[axis] * goal["depth"] for axis in ("x", "y")} for post in posts]
        outline = [project(posts[0]), project(back[0]), project(back[1]), project(posts[1])]
        color = LEFT_PLAYER if goal["team_id"] == "left" else RIGHT_PLAYER
        pygame.draw.polygon(screen, (32, 46, 41), outline)
        pygame.draw.lines(screen, color, False, outline, 2)
        for post in posts:
            pygame.draw.circle(screen, LINE, project(post), 3)

    for team_id, color in (("left", LEFT_PLAYER), ("right", RIGHT_PLAYER)):
        for player in state["teams"][team_id]["players"]:
            center = project(player["position"])
            tip = project({
                axis: player["position"][axis] + player["velocity"][axis] * 0.25
                for axis in ("x", "y")
            })
            pygame.draw.line(screen, color, center, tip, 2)
            radius = max(9, round(player["radius"] * scale))
            if player["status"] in ("receiving_ball", "dribbling"):
                ring = DRIBBLING if player["status"] == "dribbling" else RECEIVING
                pygame.draw.circle(screen, ring, center, radius + 4, 2)
            pygame.draw.circle(screen, color, center, radius)
            label = small_font.render(str(player["id"]), True, BACKGROUND)
            screen.blit(label, label.get_rect(center=center))

    ball_radius = max(5, round(state["ball"]["radius"] * scale))
    pygame.draw.circle(screen, BACKGROUND, project(state["ball"]), ball_radius + 2)
    pygame.draw.circle(screen, BALL, project(state["ball"]), ball_radius)

    title = font.render("Field Tactics", True, TEXT)
    status = small_font.render(f"{'RUNNING' if running else 'PAUSED'}  ·  {state['time']:.2f} s  ·  STEP {step_count}", True, MUTED)
    screen.blit(title, (PITCH_MARGIN, 24))
    screen.blit(status, (WINDOW_WIDTH - status.get_width() - PITCH_MARGIN, 31))
    owner = state["ball"]["owner"]
    ball_label = f"Ball: {state['ball']['status']}"
    if owner is not None:
        ball_label += f" - {owner[0]} #{owner[1]}"
    elif state["ball"]["pass"] is not None:
        receiver = state["ball"]["pass"]["receiver"]
        ball_label += f" - pass to {receiver[0]} #{receiver[1]}"
    screen.blit(small_font.render(ball_label, True, MUTED), (PITCH_MARGIN, 54))
    legend = small_font.render("Blue ring: receiving   Gold ring: dribbling", True, MUTED)
    screen.blit(legend, (WINDOW_WIDTH - legend.get_width() - PITCH_MARGIN, 54))

    help_text = "Space: play/pause   Right: single step   R: reset   Drag ball   Esc: quit"
    help_surface = small_font.render(help_text, True, MUTED)
    screen.blit(help_surface, (PITCH_MARGIN, WINDOW_HEIGHT - 29))
    pygame.display.flip()


def main():
    parser = argparse.ArgumentParser(description="Show the soccer simulation in a Pygame window")
    parser.add_argument("--dt", type=float, default=1 / 60, help="seconds passed to each simulation step")
    args = parser.parse_args()
    if not isfinite(args.dt) or not 0 < args.dt <= 0.25:
        parser.error("--dt must be positive and no larger than 0.25 seconds")

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
        config = {"fixed_dt": args.dt}
        simulation = SoccerSimulation(config)
        step_count = 0
        running = False
        dragging_ball = False
        open_window = True
        accumulated = 0.0

        while open_window:
            elapsed = min(clock.tick(60) / 1000, 0.25)
            goal_depth = max((goal.depth for goal in simulation.state.goals.values()), default=0.0)
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
                        simulation = SoccerSimulation(config)
                        step_count = 0
                        running = False
                        dragging_ball = False
                        accumulated = 0.0
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if pygame.Rect(pitch_rectangle(simulation.state.pitch, goal_depth)).collidepoint(event.pos):
                        rendered = to_render_state(simulation.state)
                        ball_pixel = pitch_to_screen(rendered["ball"], rendered["pitch"], goal_depth)
                        if (event.pos[0] - ball_pixel[0]) ** 2 + (event.pos[1] - ball_pixel[1]) ** 2 <= 18 ** 2:
                            dragging_ball = True
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    dragging_ball = False
                elif event.type == pygame.MOUSEMOTION and dragging_ball:
                    position = screen_to_pitch(event.pos, simulation.state.pitch, goal_depth)
                    simulation.state.ball.position = Vec2(position["x"], position["y"])
                    simulation.state.ball.velocity = Vec2(0, 0)
                    simulation.state.ball.status = BallStatus.LOOSE
                    simulation.state.ball.owner = None
                    simulation.state.ball.pass_state = None
                    simulation.possession.update_statuses(simulation.state)

            if not open_window:
                break
            if running:
                accumulated += elapsed
                while accumulated >= simulation.fixed_dt:
                    simulation.step()
                    step_count += 1
                    accumulated -= simulation.fixed_dt
            else:
                accumulated = 0.0

            draw_state(pygame, screen, simulation.state, font, small_font, step_count, running)
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
