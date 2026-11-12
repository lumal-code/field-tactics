"""Simulation update order, independent of any frontend."""

from math import isfinite

from .objects import BallStatus
from .physics import PhysicsConfig, advance_physics, pass_ball, plan_pass
from .possession import PossessionSystem
from .state import initialize_game
from .tactics import MoveDecision, PassDecision, decide


class SoccerSimulation:
    def __init__(self, config):
        self.physics_config = PhysicsConfig(**config.get("physics", {}))
        self.fixed_dt = config.get("fixed_dt", 1 / 60)
        if not isfinite(self.fixed_dt) or not 0 < self.fixed_dt <= self.physics_config.max_step:
            raise ValueError("fixed_dt must be positive and no larger than physics.max_step")
        self.state = initialize_game(config)
        self.possession = PossessionSystem(
            seed=config.get("seed"), receiving_distance=config.get("receiving_distance", 1.0),
        )
        self.possession.update_statuses(self.state)
        self._targets = {}

    def step(self, dt=None):
        dt = self.fixed_dt if dt is None else dt
        if not isfinite(dt) or not 0 < dt <= self.physics_config.max_step:
            raise ValueError("dt must be positive and no larger than physics.max_step")
        self.possession.update_statuses(self.state)
        decisions = self.get_decisions()
        self.apply_actions(decisions, dt)
        self.update_physics(dt)
        self.resolve_game_rules()
        return self.state

    def get_decisions(self):
        return decide(self.state)

    def apply_actions(self, decisions, dt):
        """Validate the batch, launch any pass, and store movement targets."""
        players = {(player.team_id, player.id): player for team in self.state.teams.values() for player in team.players}
        targets = {}
        seen = set()
        passing = None
        for decision in decisions:
            if not isinstance(decision, (MoveDecision, PassDecision)):
                raise ValueError(f"unsupported action: {type(decision).__name__}")
            key = (decision.team_id, decision.player_id)
            if key not in players or key in seen:
                raise ValueError(f"invalid or duplicate movement decision for {key}")
            seen.add(key)
            if isinstance(decision, MoveDecision):
                targets[key] = decision.target.copy()
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

    def update_physics(self, dt):
        advance_physics(
            self.state, self._targets, dt, self.physics_config,
            on_ball_contacts=self.possession.resolve_contacts,
        )
        self.state.time += dt

    def resolve_game_rules(self):
        if self.state.ball.status is not BallStatus.CONTROLLED and self.state.ball.velocity.magnitude() == 0:
            self.state.ball.pass_state = None
        self.possession.update_statuses(self.state)
