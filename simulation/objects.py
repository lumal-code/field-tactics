"""Mutable state objects owned by the simulation engine."""

from dataclasses import dataclass, field
from enum import Enum

from .vectors import Vec2


class BallStatus(Enum):
    CONTROLLED = "controlled"
    CONTESTED = "contested"
    LOOSE = "loose"


@dataclass
class Ball:
    position: Vec2
    velocity: Vec2 = field(default_factory=lambda: Vec2(0, 0))
    status: BallStatus = BallStatus.LOOSE
    # Player numbers repeat across teams, so an owner needs both identifiers.
    owner: tuple[str, int] | None = None


@dataclass
class Player:
    id: int
    team_id: str
    position: Vec2
    velocity: Vec2 = field(default_factory=lambda: Vec2(0, 0))
    acceleration: Vec2 = field(default_factory=lambda: Vec2(0, 0))
    max_speed: float = 20.0 # in m/s
    max_acceleration: float = 3.0 # in m/s^2


@dataclass
class Team:
    id: str
    players: list[Player] = field(default_factory=list)
    formation: str = "3-player unit"


@dataclass
class GameState:
    time: float
    pitch: dict[str, float]
    ball: Ball
    teams: dict[str, Team]
