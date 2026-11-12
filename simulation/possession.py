"""Receiving and possession rules, separate from physical collision response."""

from math import isfinite
from random import Random

from .objects import BallStatus, PlayerStatus


class PossessionSystem:
    def __init__(self, seed=None, receiving_distance=1.0):
        if not isfinite(receiving_distance) or receiving_distance <= 0:
            raise ValueError("receiving_distance must be positive and finite")
        self.receiving_distance = receiving_distance
        self.random = Random(seed)
        self._previous_contacts = set()

    def update_statuses(self, state):
        owner = state.ball.owner if state.ball.status is BallStatus.CONTROLLED else None
        for team in state.teams.values():
            for player in team.players:
                if (player.team_id, player.id) == owner:
                    player.status = PlayerStatus.DRIBBLING
                elif player.position.distance(state.ball.position) <= self.receiving_distance:
                    player.status = PlayerStatus.RECEIVING_BALL
                else:
                    player.status = PlayerStatus.IDLE

    def resolve_contacts(self, state, contacts):
        """All contacts in a substep are considered together, before any bounce."""
        contacts = sorted(contacts, key=lambda player: (player.team_id, player.id))
        contact_ids = {(player.team_id, player.id) for player in contacts}
        ball = state.ball

        if ball.status is BallStatus.CONTROLLED:
            owner = next((
                player for team in state.teams.values() for player in team.players
                if (player.team_id, player.id) == ball.owner
            ), None)
            if owner is None:
                raise ValueError("a controlled ball must reference an existing owner")
            # A carrier keeps control unless a new opponent contact challenges it.
            challengers = [
                player for player in contacts
                if player.team_id != owner.team_id
                and (player.team_id, player.id) not in self._previous_contacts
            ]
            contenders = [owner, *challengers] if challengers else []
            contact_ids.add(ball.owner)
        else:
            contenders = contacts

        if contenders:
            winner = self.random.choice(contenders) if len(contenders) > 1 else contenders[0]
            ball.status = BallStatus.CONTROLLED
            ball.owner = (winner.team_id, winner.id)
            ball.velocity = winner.velocity.copy()
            ball.pass_state = None
            contact_ids.add(ball.owner)

        self._previous_contacts = contact_ids
        self.update_statuses(state)
