"""Rondo holding, clear-lane passing, and state-dependent ball pursuit."""

from dataclasses import dataclass

from .objects import BallStatus
from .physics import EPSILON, plan_pass, predict_ball_position
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
    ## return attacking_goal.position
    return player.position


def is_pass_blocked(origin, target, defenders, ball_radius):
    """A lane is blocked when a defender's disc intersects the ball's segment."""
    segment = target - origin
    length_squared = segment.dot(segment)
    for defender in defenders:
        projection = (defender.position - origin).dot(segment) / length_squared if length_squared > EPSILON else 0.0
        fraction = min(max(projection, 0.0), 1.0)
        closest = origin + segment * fraction
        if closest.distance(defender.position) <= defender.radius + ball_radius + EPSILON:
            return True
    return False


def interception_target(player, state):
    """Choose the earliest estimated reachable ball position within three seconds."""
    ball = state.ball
    speed = min(player.velocity.magnitude(), player.max_speed)
    acceleration_time = (player.max_speed - speed) / player.max_acceleration
    target = ball.position.copy()
    for sample in range(1, 61):
        seconds = sample * 0.05
        predicted = predict_ball_position(ball, seconds)
        target = Vec2(
            min(max(predicted.x, ball.radius), state.pitch["width"] - ball.radius),
            min(max(predicted.y, ball.radius), state.pitch["height"] - ball.radius),
        )
        available_time = max(0.0, seconds - player.response_time)
        speeding_up = min(available_time, acceleration_time)
        reachable_distance = (
            speed * speeding_up + 0.5 * player.max_acceleration * speeding_up ** 2
            + player.max_speed * (available_time - speeding_up)
        )
        if player.position.distance(target) <= reachable_distance + player.radius + ball.radius:
            return target
    return target


def defender_target(player, state):
    if state.ball.status is BallStatus.CONTROLLED:
        carrier = next((
            candidate for team in state.teams.values() for candidate in team.players
            if (candidate.team_id, candidate.id) == state.ball.owner
        ), None)
        if carrier is None:
            raise ValueError("a controlled ball must reference an existing owner")
        return carrier.position.copy()
    if state.ball.velocity.magnitude() > EPSILON and player.position.distance(state.ball.position) <= player.reset_distance:
        return interception_target(player, state)
    if state.ball.velocity.magnitude() > EPSILON and player.position.distance(state.ball.position) >= player.reset_distance:
        return player.default_position.copy()
    return state.ball.position.copy()


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
            teammates = sorted(
                (player for player in team.players if player.id != carrier.id),
                key=lambda player: (carrier.position.distance(player.position), player.id),
            )
            opponents = [
                opponent for other_team in state.teams.values() for opponent in other_team.players
                if opponent.team_id != carrier.team_id
            ]
            under_pressure = any(
                carrier.position.distance(opponent.position) <= 3.0
                for opponent in opponents
            )
            receiver = None
            if under_pressure:
                for teammate in teammates:
                    trajectory = plan_pass(state.ball, carrier, teammate)
                    if trajectory is not None and not is_pass_blocked(
                        trajectory[0], teammate.position, opponents, state.ball.radius,
                    ):
                        receiver = teammate
                        break
            if receiver is not None:
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
            key=lambda player: (player.position.distance(carrier.position if carrier is not None else state.ball.position), player.id),
        )
        decisions.append(MoveDecision(team.id, nearest.id, defender_target(nearest, state)))
    return decisions
