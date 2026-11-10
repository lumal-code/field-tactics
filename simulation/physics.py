"""Small deterministic movement and ball updates."""

from math import sqrt

from .objects import BallStatus


def move_player(player, direction, dt):
    """Steer toward a target with acceleration, speed, and braking limits."""
    direction = direction.normalize()
    player.acceleration = direction * player.max_acceleration * dt
    player.velocity = player.velocity + player.acceleration
    player.velocity = player.velocity.limit(player.max_speed)
    player.position += player.velocity * dt


def kick_ball(ball, direction, power):
    """Add velocity in the kick direction."""
    ball.velocity += direction.normalize() * power
    ball.status = BallStatus.LOOSE
    ball.owner = None


def update_ball(ball, dt):
    """Move a loose ball at its current velocity."""
    ball.position += ball.velocity * dt


def resolve_ball_interactions(ball, players):
    """Reserved for contact and possession rules."""
