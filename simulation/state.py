"""Initial state and a plain-data view for renderers."""

from math import isfinite

from .objects import Ball, GameState, Goal, Player, Team
from .vectors import Vec2


def initialize_game(config):
    width = config.get("pitch_width", 40) # field set in meters
    height = config.get("pitch_height", 20)
    if not isfinite(width) or not isfinite(height) or width <= 0 or height <= 0:
        raise ValueError("pitch dimensions must be positive finite numbers")
    center_y = height / 2
    goal_width = config.get("goal_width", min(3.0, height / 2))
    goal_depth = config.get("goal_depth", 1.0)
    if goal_width > height:
        raise ValueError("goal_width must fit within the pitch height")

    def team(team_id, x):
        return Team(
            id=team_id,
            players=[
                Player(
                    id=player_id, team_id=team_id,
                    position=Vec2(x, center_y + offset * height / 68),
                    facing=Vec2(1 if team_id == "left" else -1, 0),
                    **config.get("player", {}),
                )
                for player_id, offset in ((2, -14), (3, 0), (4, 14))
            ],
        )

    return GameState(
        time=0.0,
        pitch={"width": width, "height": height},
        ball=Ball(position=Vec2(width * 0.68, center_y), **config.get("ball", {})),
        teams={"left": team("left", width * 0.35), "right": team("right", width * 0.65)},
        goals={
            "left": Goal("left", Vec2(0, center_y), Vec2(1, 0), goal_width, goal_depth),
            "right": Goal("right", Vec2(width, center_y), Vec2(-1, 0), goal_width, goal_depth),
        },
    )


def to_render_state(state):
    """Produce plain data without exposing the engine's mutable objects."""
    return {
        "time": state.time,
        "pitch": dict(state.pitch),
        "ball": {
            "x": float(state.ball.position.x), "y": float(state.ball.position.y),
            "radius": state.ball.radius, "status": state.ball.status.value, "owner": state.ball.owner,
            "pass": {
                "passer": state.ball.pass_state.passer,
                "receiver": state.ball.pass_state.receiver,
                "target": {"x": float(state.ball.pass_state.target.x), "y": float(state.ball.pass_state.target.y)},
            } if state.ball.pass_state is not None else None,
        },
        "goals": {
            goal_id: {
                "team_id": goal.team_id,
                "position": {"x": float(goal.position.x), "y": float(goal.position.y)},
                "facing": {"x": float(goal.facing.x), "y": float(goal.facing.y)},
                "width": goal.width,
                "depth": goal.depth,
            }
            for goal_id, goal in state.goals.items()
        },
        "teams": {
            team_id: {
                "players": [
                    {
                        "id": player.id,
                        "position": {"x": float(player.position.x), "y": float(player.position.y)},
                        "velocity": {"x": float(player.velocity.x), "y": float(player.velocity.y)},
                        "radius": player.radius,
                        "status": player.status.value,
                    }
                    for player in team.players
                ]
            }
            for team_id, team in state.teams.items()
        },
    }
