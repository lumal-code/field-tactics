"""Deterministic 2D locomotion, rolling ball motion, and disc contacts.

Units, formulas, and limitations are documented in docs/physics.md.
"""

from dataclasses import dataclass
from itertools import combinations
from math import ceil, isfinite, sqrt

from .objects import BallStatus, PassState
from .vectors import Vec2

EPSILON = 1e-10


@dataclass(frozen=True)
class PhysicsConfig:
    max_substep: float = 1 / 120
    max_step: float = 0.25
    contact_iterations: int = 6
    player_restitution: float = 0.0
    ball_restitution: float = 0.35
    contain_ball: bool = True

    def __post_init__(self):
        for name in ("max_substep", "max_step"):
            if not isfinite(getattr(self, name)) or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive and finite")
        if not isinstance(self.contact_iterations, int) or self.contact_iterations < 1:
            raise ValueError("contact_iterations must be a positive integer")
        for value in (self.player_restitution, self.ball_restitution):
            if not isfinite(value) or not 0 <= value <= 1:
                raise ValueError("restitution must be between zero and one")


def _validate_dt(dt):
    if not isfinite(dt) or dt <= 0:
        raise ValueError("dt must be a positive finite number")


def move_player(player, target, dt):
    """Arrive at an absolute target; None requests a controlled stop."""
    _validate_dt(dt)
    desired_velocity = Vec2(0, 0)
    if target is not None:
        displacement = target - player.position
        remaining = max(0.0, displacement.magnitude() - player.arrival_radius)
        braking_response = player.max_deceleration * player.response_time
        desired_speed = min(
            player.max_speed,
            sqrt(braking_response ** 2 + 2 * player.max_deceleration * remaining) - braking_response,
        )
        desired_velocity = displacement.normalize() * desired_speed

    speed = player.velocity.magnitude()
    requested = (desired_velocity - player.velocity) / max(player.response_time, dt)
    # An idle/arrived command actively brakes instead of leaving perpetual drift.
    if desired_velocity.magnitude() <= EPSILON:
        requested = player.velocity * (-1 / dt)

    if speed <= EPSILON:
        acceleration = requested.limit(player.max_acceleration)
    else:
        forward = player.velocity / speed
        longitudinal = requested.dot(forward)
        lateral = requested - forward * longitudinal
        longitudinal_limit = player.max_acceleration if longitudinal >= 0 else player.max_deceleration
        # An ellipse shares the motor budget between speed changes and turning.
        demand = sqrt(
            (longitudinal / longitudinal_limit) ** 2
            + (lateral.magnitude() / player.max_lateral_acceleration) ** 2
        )
        acceleration = requested * (1 / max(1.0, demand))

    previous_velocity = player.velocity
    player.velocity = (previous_velocity + acceleration * dt).limit(player.max_speed)
    player.acceleration = (player.velocity - previous_velocity) / dt
    player.position += player.velocity * dt
    if player.velocity.magnitude() > EPSILON:
        player.facing = player.velocity.normalize()


def kick_ball(ball, direction, power):
    """Apply a delta velocity in m/s and release any existing owner."""
    if not isfinite(power) or power < 0:
        raise ValueError("kick power must be finite and nonnegative")
    if direction.magnitude() <= EPSILON:
        raise ValueError("kick direction must be nonzero")
    ball.velocity = (ball.velocity + direction.normalize() * power).limit(ball.max_speed)
    ball.status = BallStatus.LOOSE
    ball.owner = None
    ball.pass_state = None


def plan_pass(ball, passer, receiver, arrival_speed=3.0):
    """Return (release position, velocity), or None if the pass is infeasible."""
    if not isfinite(arrival_speed) or arrival_speed <= 0:
        raise ValueError("arrival_speed must be positive and finite")
    displacement = receiver.position - passer.position
    release_offset = passer.radius + ball.radius + 0.02
    if displacement.magnitude() <= release_offset:
        return None
    direction = displacement.normalize()
    origin = passer.position + direction * release_offset
    distance = origin.distance(receiver.position)
    required_speed = sqrt(arrival_speed ** 2 + 2 * ball.rolling_deceleration * distance)
    # A moving passer must also release the ball faster than they move along it.
    launch_speed = max(required_speed, passer.velocity.dot(direction) + 0.5)
    if launch_speed > ball.max_speed:
        return None
    return origin, direction * launch_speed


def pass_ball(ball, passer, receiver, arrival_speed=3.0):
    """Launch a ground pass with a planned final world velocity."""
    trajectory = plan_pass(ball, passer, receiver, arrival_speed)
    if trajectory is None:
        raise ValueError("pass cannot meet the arrival speed within the ball's speed limit")
    ball.position, ball.velocity = trajectory
    ball.status = BallStatus.LOOSE
    ball.owner = None
    ball.pass_state = PassState(
        passer=(passer.team_id, passer.id), receiver=(receiver.team_id, receiver.id),
        target=receiver.position.copy(),
    )


def update_ball(ball, dt):
    """Integrate constant rolling deceleration exactly, without reversing."""
    _validate_dt(dt)
    if ball.status is BallStatus.CONTROLLED:
        return
    speed = ball.velocity.magnitude()
    if speed <= EPSILON:
        ball.velocity = Vec2(0, 0)
        return
    direction = ball.velocity / speed
    rolling_time = min(dt, speed / ball.rolling_deceleration) if ball.rolling_deceleration > 0 else dt
    travel = speed * rolling_time - 0.5 * ball.rolling_deceleration * rolling_time ** 2
    ball.position += direction * travel
    ball.velocity = direction * max(0.0, speed - ball.rolling_deceleration * dt)


def _resolve_contact(first, second, restitution):
    offset = second.position - first.position
    separation = offset.magnitude()
    penetration = first.radius + second.radius - separation
    if penetration < 0:
        return
    normal = offset / separation if separation > EPSILON else Vec2(1, 0)
    inverse_first, inverse_second = 1 / first.mass, 1 / second.mass
    inverse_sum = inverse_first + inverse_second
    first.position -= normal * (penetration * inverse_first / inverse_sum)
    second.position += normal * (penetration * inverse_second / inverse_sum)

    closing_speed = (second.velocity - first.velocity).dot(normal)
    if closing_speed < 0:
        impulse = -(1 + restitution) * closing_speed / inverse_sum
        first.velocity = (first.velocity - normal * (impulse * inverse_first)).limit(first.max_speed)
        second.velocity = (second.velocity + normal * (impulse * inverse_second)).limit(second.max_speed)


def resolve_ball_interactions(ball, players, restitution=0.35):
    """Resolve physical contact; possession transitions belong to game rules."""
    if not isfinite(restitution) or not 0 <= restitution <= 1:
        raise ValueError("restitution must be between zero and one")
    if ball.status is not BallStatus.CONTROLLED:
        for player in players:
            _resolve_contact(player, ball, restitution)


def _contain(body, pitch):
    """Contain a disc in a training pitch and remove outward normal speed."""
    for axis, extent in (("x", pitch["width"]), ("y", pitch["height"])):
        coordinate = getattr(body.position, axis)
        velocity = getattr(body.velocity, axis)
        if coordinate <= body.radius:
            setattr(body.position, axis, body.radius)
            setattr(body.velocity, axis, max(0.0, velocity))
        elif coordinate >= extent - body.radius:
            setattr(body.position, axis, extent - body.radius)
            setattr(body.velocity, axis, min(0.0, velocity))


def _attach_controlled_ball(state, players):
    owner = next((player for player in players if (player.team_id, player.id) == state.ball.owner), None)
    if owner is None:
        raise ValueError("a controlled ball must reference an existing owner")
    offset = owner.radius + state.ball.radius + 0.02
    facing = owner.facing.normalize() if owner.facing.magnitude() > EPSILON else Vec2(1, 0)
    state.ball.position = owner.position + facing * offset
    state.ball.velocity = owner.velocity.copy()


def _notify_ball_contacts(state, players, handler):
    if handler is not None:
        contacts = [
            player for player in players
            if player.position.distance(state.ball.position) <= player.radius + state.ball.radius + EPSILON
        ]
        handler(state, contacts)


def advance_physics(state, targets, dt, config=PhysicsConfig(), on_ball_contacts=None):
    """Advance all bodies together with bounded substeps and stable contact order."""
    _validate_dt(dt)
    if dt > config.max_step:
        raise ValueError(f"dt must not exceed {config.max_step}; advance multiple ticks instead")
    players = [
        player for team_id in sorted(state.teams)
        for player in sorted(state.teams[team_id].players, key=lambda player: player.id)
    ]
    bodies = [*players, state.ball]
    if state.ball.status is BallStatus.CONTROLLED and state.ball.owner not in {
        (player.team_id, player.id) for player in players
    }:
        raise ValueError("a controlled ball must reference an existing owner")
    for body in bodies:
        if min(state.pitch.values()) <= 2 * body.radius:
            raise ValueError("pitch must be larger than every body's diameter")

    # Limit both elapsed time and possible relative travel per contact check.
    max_player_speed = max((max(player.max_speed, player.velocity.magnitude()) for player in players), default=0.0)
    max_ball_speed = max(state.ball.max_speed, state.ball.velocity.magnitude())
    relative_speed_bound = max(2 * max_player_speed, max_player_speed + max_ball_speed)
    min_radius = min(body.radius for body in bodies)
    substeps = max(1, ceil(dt / config.max_substep), ceil(dt * relative_speed_bound / min_radius))
    h = dt / substeps

    if state.ball.status is BallStatus.CONTROLLED:
        _attach_controlled_ball(state, players)
    _notify_ball_contacts(state, players, on_ball_contacts)
    for _ in range(substeps):
        for player in players:
            move_player(player, targets.get((player.team_id, player.id)), h)
        update_ball(state.ball, h)
        if state.ball.status is BallStatus.CONTROLLED:
            _attach_controlled_ball(state, players)
        _notify_ball_contacts(state, players, on_ball_contacts)
        for _ in range(config.contact_iterations):
            for first, second in combinations(players, 2):
                _resolve_contact(first, second, config.player_restitution)
            resolve_ball_interactions(state.ball, players, config.ball_restitution)
            for player in players:
                _contain(player, state.pitch)
            if config.contain_ball and state.ball.status is not BallStatus.CONTROLLED:
                _contain(state.ball, state.pitch)
        if state.ball.status is BallStatus.CONTROLLED:
            _attach_controlled_ball(state, players)
            if config.contain_ball:
                _contain(state.ball, state.pitch)
