"""Initial team decision: the closest player pursues the ball."""

from dataclasses import dataclass

from .vectors import Vec2


@dataclass(frozen=True)
class MoveDecision:
    team_id: str
    player_id: int
    target: Vec2


def decide(state):
    decisions = []
    for team in state.teams.values():
        if not team.players:
            continue
        nearest = min(
            team.players,
            key=lambda player: (player.position.distance(state.ball.position), player.id),
        )
        direction = Vec2(state.ball.position.x, state.ball.position.y) - nearest.position
        decisions.append(MoveDecision(team.id, nearest.id, direction))
    return decisions
