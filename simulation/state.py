"""Initial state and a plain-data view for renderers."""

from math import isfinite

from .objects import Ball, GameState, Player, Team
from .vectors import Vec2


def initialize_game(config):
    width = config.get("pitch_width", 40) # field set in meters
    height = config.get("pitch_height", 20)
    if not isfinite(width) or not isfinite(height) or width <= 0 or height <= 0:
        raise ValueError("pitch dimensions must be positive finite numbers")
    center_y = height / 2

    def team(team_id, x):
        return Team(
            id=team_id,
            players=[
                Player(id=player_id, team_id=team_id, position=Vec2(x, center_y + offset * height / 68))
                for player_id, offset in ((2, -14), (3, 0), (4, 14))
            ],
        )

    return GameState(
        time=0.0,
        pitch={"width": width, "height": height},
        ball=Ball(position=Vec2(width * 0.68, center_y)),
        teams={"left": team("left", width * 0.35), "right": team("right", width * 0.65)},
    )


def to_render_state(state):
    """Produce plain data without exposing the engine's mutable objects."""
    return {
        "time": state.time,
        "pitch": dict(state.pitch),
        "ball": {"x": float(state.ball.position.x), "y": float(state.ball.position.y)},
        "teams": {
            team_id: {
                "players": [
                    {
                        "id": player.id,
                        "position": {"x": float(player.position.x), "y": float(player.position.y)},
                    }
                    for player in team.players
                ]
            }
            for team_id, team in state.teams.items()
        },
    }
