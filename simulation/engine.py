"""Simulation update order, independent of any frontend."""

from math import isfinite

from .objects import BallStatus
from .physics import move_player, update_ball
from .state import initialize_game
from .tactics import decide


class SoccerSimulation:
    def __init__(self, config):
        self.state = initialize_game(config)
        self._directions = {}

    def step(self, dt):
        if not isfinite(dt) or dt <= 0:
            raise ValueError("dt must be a positive finite number")
        decisions = self.get_decisions()
        self.apply_actions(decisions, dt)
        self.update_physics(dt)
        self.resolve_game_rules()
        return self.state

    def get_decisions(self):
        return decide(self.state)

    def apply_actions(self, decisions, dt):
        """Store this step's targets; physics owns position updates."""
        self._directions = {(decision.team_id, decision.player_id): decision.target for decision in decisions}

    def update_physics(self, dt):
        for team in self.state.teams.values():
            for player in team.players:
                direction = self._directions.get((team.id, player.id))
                if direction is not None:
                    move_player(player, direction, dt)
                else:
                    player.position += player.velocity * dt
        if self.state.ball.status is BallStatus.LOOSE:
            update_ball(self.state.ball, dt)
        self.state.time += dt

    def resolve_game_rules(self):
        """Placeholder for possession, boundaries, and other rules."""
