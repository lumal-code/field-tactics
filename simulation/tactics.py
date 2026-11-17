"""Rondo holding, clear-lane passing, and state-dependent ball pursuit."""

from dataclasses import dataclass

from .objects import BallStatus
from .physics import EPSILON, plan_pass, predict_ball_position
from .vectors import Vec2

COVERAGE_DISTANCE = 3.0
FULL_PRESS_DISTANCE = 1.0
FULL_LANE_DISTANCE = 8.0


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


def covered_opponent_ids(team, state):
    """Coverage is relative to a team and uses center-to-center distance."""
    return {
        (opponent.team_id, opponent.id)
        for other_team in state.teams.values() if other_team.id != team.id
        for opponent in other_team.players
        if any(defender.position.distance(opponent.position) <= COVERAGE_DISTANCE for defender in team.players)
    }


def update_coverage(state):
    for team in state.teams.values():
        team.covered_opponents = covered_opponent_ids(team, state)


def press_lane_weight(distance):
    """Linearly shift from carrier pressure at 1 m to the lane at 8 m."""
    return min(max((distance - FULL_PRESS_DISTANCE) / (FULL_LANE_DISTANCE - FULL_PRESS_DISTANCE), 0.0), 1.0)


def controlled_defender_target(player, carrier, state, covered):
    """Blend pressure with the lane to the carrier's nearest uncovered teammate."""
    receivers = [
        candidate for team in state.teams.values() for candidate in team.players
        if candidate.team_id == carrier.team_id and candidate.id != carrier.id
        and (candidate.team_id, candidate.id) not in covered
    ]
    receiver = min(
        receivers, key=lambda candidate: (carrier.position.distance(candidate.position), candidate.id),
        default=None,
    )
    if receiver is None:
        return carrier.position.copy()

    lane = receiver.position - carrier.position
    length_squared = lane.dot(lane)
    if length_squared <= EPSILON:
        return carrier.position.copy()
    fraction = min(max((player.position - carrier.position).dot(lane) / length_squared, 0.0), 1.0)
    lane_target = carrier.position + lane * fraction
    to_carrier = carrier.position - player.position
    to_lane = lane_target - player.position
    lane_weight = press_lane_weight(to_carrier.magnitude())
    return player.position + to_carrier * (1 - lane_weight) + to_lane * lane_weight


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


def defender_target(player, state, covered=None):
    if state.ball.status is BallStatus.CONTROLLED:
        carrier = next((
            candidate for team in state.teams.values() for candidate in team.players
            if (candidate.team_id, candidate.id) == state.ball.owner
        ), None)
        if carrier is None:
            raise ValueError("a controlled ball must reference an existing owner")
        if covered is None:
            team = state.teams[player.team_id]
            covered = covered_opponent_ids(team, state)
            team.covered_opponents = covered
        return controlled_defender_target(player, carrier, state, covered)
    if state.ball.velocity.magnitude() > EPSILON:
        if player.default_position is not None and player.position.distance(state.ball.position) > player.reset_distance:
            return player.default_position.copy()
        return interception_target(player, state)
    return state.ball.position.copy()


def decide(state):
    update_coverage(state)
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
        decisions.append(MoveDecision(team.id, nearest.id, defender_target(nearest, state, team.covered_opponents)))
    return decisions
