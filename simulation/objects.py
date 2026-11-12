"""Mutable state objects owned by the simulation engine."""

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite

from .vectors import Vec2


def _validate_parameters(body, positive, nonnegative=()):
    for name in positive:
        value = getattr(body, name)
        if not isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be positive and finite")
    for name in nonnegative:
        value = getattr(body, name)
        if not isfinite(value) or value < 0:
            raise ValueError(f"{name} must be nonnegative and finite")


class BallStatus(Enum):
    CONTROLLED = "controlled"
    CONTESTED = "contested"
    LOOSE = "loose"


class PlayerStatus(Enum):
    IDLE = "idle"
    RECEIVING_BALL = "receiving_ball"
    DRIBBLING = "dribbling"


@dataclass(frozen=True)
class PassState:
    passer: tuple[str, int]
    receiver: tuple[str, int]
    target: Vec2  # Receiver's position when the pass was launched.


@dataclass
class Ball:
    position: Vec2
    velocity: Vec2 = field(default_factory=lambda: Vec2(0, 0))
    status: BallStatus = BallStatus.LOOSE
    # Player numbers repeat across teams, so an owner needs both identifiers.
    owner: tuple[str, int] | None = None
    radius: float = 0.11
    mass: float = 0.43
    rolling_deceleration: float = 0.8
    max_speed: float = 35.0
    pass_state: PassState | None = None

    def __post_init__(self):
        _validate_parameters(self, ("radius", "mass", "max_speed"), ("rolling_deceleration",))


@dataclass
class Player:
    id: int
    team_id: str
    position: Vec2
    velocity: Vec2 = field(default_factory=lambda: Vec2(0, 0))
    acceleration: Vec2 = field(default_factory=lambda: Vec2(0, 0))
    max_speed: float = 7.0  # m/s
    max_acceleration: float = 3.0  # m/s^2, forward
    max_deceleration: float = 5.0  # m/s^2, braking
    max_lateral_acceleration: float = 4.0  # m/s^2, turning
    response_time: float = 0.25  # seconds
    arrival_radius: float = 0.15  # meters
    radius: float = 0.35
    mass: float = 75.0
    facing: Vec2 = field(default_factory=lambda: Vec2(1, 0))
    status: PlayerStatus = PlayerStatus.IDLE

    def __post_init__(self):
        _validate_parameters(self, (
            "max_acceleration", "max_deceleration", "max_lateral_acceleration",
            "response_time", "radius", "mass",
        ), ("max_speed", "arrival_radius"))


@dataclass
class Team:
    id: str
    players: list[Player] = field(default_factory=list)
    formation: str = "3-player unit"


@dataclass
class Goal:
    team_id: str  # Team defending this goal.
    position: Vec2  # Center of the mouth, on the goal line.
    facing: Vec2  # Unit direction from the mouth into the pitch.
    width: float = 3.0
    depth: float = 1.0

    def __post_init__(self):
        _validate_parameters(self, ("width", "depth"))
        if self.facing.magnitude() == 0:
            raise ValueError("goal facing must be nonzero")
        self.facing = self.facing.normalize()


@dataclass
class GameState:
    time: float
    pitch: dict[str, float]
    ball: Ball
    teams: dict[str, Team]
    goals: dict[str, Goal] = field(default_factory=dict)
