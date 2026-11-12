"""Pursue, dribble toward goal, or pass to the nearest teammate under pressure."""

from dataclasses import dataclass

from .objects import BallStatus
from .physics import plan_pass
from .vectors import Vec2


@dataclass(frozen=True)
class MoveDecision:
    team_id: str
    player_id: int
    target: Vec2  # Absolute pitch position, in meters.


@dataclass(frozen=True)
class PassDecision:
    team_id: str
    player_id: int
    receiver_id: int


def dribble_target(player, state):
    attacking_goal = next(
        goal
        for goal in state.goals.values()
        if goal.team_id != player.team_id
    )
    return attacking_goal.position


def decide(state):
    decisions = []
    carrier = None
    if state.ball.status is BallStatus.CONTROLLED:
        carrier = next((
            player for team in state.teams.values() for player in team.players
            if (player.team_id, player.id) == state.ball.owner
        ), None)
        if carrier is None:
            raise ValueError("a controlled ball must reference an existing owner")
    for team in state.teams.values():
        if not team.players:
            continue
        if carrier is not None and carrier.team_id == team.id:
            teammates = [player for player in team.players if player.id != carrier.id]
            receiver = min(
                teammates, key=lambda player: (carrier.position.distance(player.position), player.id),
                default=None,
            )
            under_pressure = any(
                carrier.position.distance(opponent.position) <= 3.0
                for other_team in state.teams.values() for opponent in other_team.players
                if opponent.team_id != carrier.team_id
            )
            if under_pressure and receiver is not None and plan_pass(state.ball, carrier, receiver) is not None:
                decisions.append(PassDecision(team.id, carrier.id, receiver.id))
                continue
            decisions.append(MoveDecision(team.id, carrier.id, dribble_target(carrier, state)))
            continue
        active_pass = state.ball.pass_state
        if carrier is None and active_pass is not None and team.id == active_pass.receiver[0]:
            decisions.append(MoveDecision(team.id, active_pass.receiver[1], active_pass.target.copy()))
            continue
        nearest = min(
            team.players,
            key=lambda player: (player.position.distance(state.ball.position), player.id),
        )
        decisions.append(MoveDecision(team.id, nearest.id, state.ball.position.copy()))
    return decisions
