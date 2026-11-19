"""Simulation update order, independent of any frontend."""

from math import isfinite

from .objects import BallStatus
from .physics import PhysicsConfig, advance_physics, pass_ball, plan_pass
from .possession import PossessionSystem
from .state import initialize_game, initialize_rondo
from .tactics import VelocityDecision, MoveDecision, PassDecision, decide, update_coverage


class SoccerSimulation:
    def __init__(self, config):
        self.physics_config = PhysicsConfig(**config.get("physics", {}))
        self.fixed_dt = config.get("fixed_dt", 1 / 60)
        if not isfinite(self.fixed_dt) or not 0 < self.fixed_dt <= self.physics_config.max_step:
            raise ValueError("fixed_dt must be positive and no larger than physics.max_step")
        self.state = initialize_rondo(config)
        self.possession = PossessionSystem(
            seed=config.get("seed"), receiving_distance=config.get("receiving_distance", 1.0),
        )
        self.possession.update_statuses(self.state)
        update_coverage(self.state)
        self._targets = {}
        self._velocities = {}

    def step(self, dt=None, *, ignore_player=None, desired_velocity=None):
        dt = self.fixed_dt if dt is None else dt
        if not isfinite(dt) or not 0 < dt <= self.physics_config.max_step:
            raise ValueError("dt must be positive and no larger than physics.max_step")
        self.possession.update_statuses(self.state)
        decisions = self.get_decisions(ignore_player)

        if desired_velocity is not None:
            if ignore_player is None:
                raise ValueError("A velocity command needs a controlled player")

            team_id, player_id = ignore_player
            decisions.append(
                VelocityDecision(team_id, player_id, desired_velocity)
            )
        self.apply_actions(decisions, dt)
        self.update_physics(dt)
        self.resolve_game_rules()
        return self.state

    def get_decisions(self, ignore_player=None):
        return decide(self.state, ignore_player)

    def apply_actions(self, decisions, dt):
        """Validate the batch, launch any pass, and store movement targets."""
        players = {(player.team_id, player.id): player for team in self.state.teams.values() for player in team.players}
        targets = {}
        velocities = {}
        seen = set()
        passing = None
        for decision in decisions:
            if not isinstance(decision, (MoveDecision, PassDecision, VelocityDecision)):
                raise ValueError(f"unsupported action: {type(decision).__name__}")
            key = (decision.team_id, decision.player_id)
            if key not in players or key in seen:
                raise ValueError(f"invalid or duplicate movement decision for {key}")
            seen.add(key)
            if isinstance(decision, MoveDecision):
                targets[key] = decision.target.copy()
            elif isinstance(decision, VelocityDecision):
                velocities[key] = decision.velocity.copy()
            elif isinstance(decision, PassDecision):
                receiver_key = (decision.team_id, decision.receiver_id)
                if (
                    passing is not None or self.state.ball.status is not BallStatus.CONTROLLED
                    or self.state.ball.owner != key or receiver_key == key or receiver_key not in players
                ):
                    raise ValueError("only the ball carrier can pass to an existing teammate")
                passer, receiver = players[key], players[receiver_key]
                if plan_pass(self.state.ball, passer, receiver) is None:
                    raise ValueError("pass cannot meet the required arrival speed")
                passing = passer, receiver
        if passing is not None:
            passer, receiver = passing
            pass_ball(self.state.ball, passer, receiver)
            targets[(receiver.team_id, receiver.id)] = self.state.ball.pass_state.target.copy()
        self._targets = targets
        self._velocities = velocities

    def update_physics(self, dt):
        advance_physics(
            self.state, self._targets, dt, self.physics_config,
            on_ball_contacts=self.possession.resolve_contacts, velocities=self._velocities
        )
        self.state.time += dt

    def resolve_game_rules(self):
        if self.state.ball.status is not BallStatus.CONTROLLED and self.state.ball.velocity.magnitude() == 0:
            self.state.ball.pass_state = None
        self.possession.update_statuses(self.state)
        update_coverage(self.state)
