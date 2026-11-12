import unittest
from unittest.mock import patch

from simulation import SoccerSimulation
from simulation.objects import Ball, BallStatus, Player, PlayerStatus, Team
from simulation.state import to_render_state
from simulation.vectors import Vec2


def scenario(players, ball, seed=0):
    simulation = SoccerSimulation({"seed": seed})
    simulation.state.teams = {}
    for player in players:
        simulation.state.teams.setdefault(player.team_id, Team(player.team_id)).players.append(player)
    simulation.state.ball = ball
    simulation.possession.update_statuses(simulation.state)
    return simulation


class PossessionTests(unittest.TestCase):
    def test_receiving_starts_within_one_meter_and_clears_when_out_of_range(self):
        player = Player(1, "left", Vec2(9, 10))
        simulation = scenario([player], Ball(Vec2(10, 10)))
        self.assertIs(player.status, PlayerStatus.RECEIVING_BALL)
        self.assertIs(simulation.state.ball.status, BallStatus.LOOSE)
        player.position.x = 8.99
        simulation.possession.update_statuses(simulation.state)
        self.assertIs(player.status, PlayerStatus.IDLE)

    def test_receiving_does_not_claim_a_ball_without_contact(self):
        player = Player(1, "left", Vec2(9.2, 10))
        simulation = scenario([player], Ball(Vec2(10, 10)))
        simulation.step()
        self.assertIs(player.status, PlayerStatus.RECEIVING_BALL)
        self.assertIs(simulation.state.ball.status, BallStatus.LOOSE)
        self.assertIsNone(simulation.state.ball.owner)

    def test_receive_contact_and_dribble_follow_the_owner_end_to_end(self):
        player = Player(1, "left", Vec2(9.1, 10))
        defender = Player(1, "right", Vec2(5, 10))
        ball = Ball(Vec2(10, 10))
        simulation = scenario([player, defender], ball)
        self.assertIs(player.status, PlayerStatus.RECEIVING_BALL)
        for _ in range(180):
            simulation.step()
            if ball.status is BallStatus.CONTROLLED:
                break
        self.assertEqual(ball.owner, ("left", 1))
        self.assertIs(player.status, PlayerStatus.DRIBBLING)
        start = player.position.copy()
        for _ in range(60):
            simulation.step()
            self.assertAlmostEqual(ball.position.distance(player.position), player.radius + ball.radius + 0.02)
            self.assertAlmostEqual(ball.velocity.distance(player.velocity), 0)
        self.assertGreater(player.position.x, start.x)
        self.assertEqual(ball.owner, ("left", 1))

    def test_a_fast_ball_is_received_inside_a_physics_substep(self):
        player = Player(1, "left", Vec2(10, 10))
        ball = Ball(Vec2(8, 10), velocity=Vec2(35, 0))
        simulation = scenario([player], ball)
        self.assertIs(player.status, PlayerStatus.IDLE)
        simulation.step(0.1)
        self.assertEqual(ball.owner, ("left", 1))
        self.assertIs(ball.status, BallStatus.CONTROLLED)
        self.assertIs(player.status, PlayerStatus.DRIBBLING)

    def test_simultaneous_contacts_are_one_random_contest_with_all_players(self):
        left = Player(1, "left", Vec2(9.54, 10))
        right = Player(1, "right", Vec2(10.46, 10), facing=Vec2(-1, 0))
        simulation = scenario([right, left], Ball(Vec2(10, 10)))
        with patch.object(simulation.possession.random, "choice", side_effect=lambda players: players[0]) as choose:
            simulation.step(0.1)
        self.assertEqual(choose.call_count, 1)
        contenders = choose.call_args.args[0]
        self.assertEqual({(player.team_id, player.id) for player in contenders}, {("left", 1), ("right", 1)})
        self.assertEqual(simulation.state.ball.owner, ("left", 1))

    def test_an_opponent_can_win_a_challenge_for_a_controlled_ball(self):
        owner = Player(1, "left", Vec2(10, 10))
        opponent = Player(1, "right", Vec2(10.94, 10), facing=Vec2(-1, 0))
        ball = Ball(Vec2(10.48, 10), status=BallStatus.CONTROLLED, owner=("left", 1))
        simulation = scenario([owner, opponent], ball)
        with patch.object(simulation.possession.random, "choice", side_effect=lambda players: players[-1]) as choose:
            simulation.step(0.01)
        self.assertEqual(choose.call_count, 1)
        self.assertEqual(ball.owner, ("right", 1))
        self.assertIs(opponent.status, PlayerStatus.DRIBBLING)
        self.assertIs(owner.status, PlayerStatus.RECEIVING_BALL)

    def test_a_continuous_challenge_does_not_roll_again_until_separation(self):
        owner = Player(1, "left", Vec2(10, 10))
        opponent = Player(1, "right", Vec2(10.94, 10))
        ball = Ball(Vec2(10.48, 10), status=BallStatus.CONTROLLED, owner=("left", 1))
        simulation = scenario([owner, opponent], ball)
        with patch.object(simulation.possession.random, "choice", side_effect=lambda players: players[0]) as choose:
            for _ in range(5):
                simulation.possession.resolve_contacts(simulation.state, [opponent])
            self.assertEqual(choose.call_count, 1)
            simulation.possession.resolve_contacts(simulation.state, [])
            simulation.possession.resolve_contacts(simulation.state, [opponent])
            self.assertEqual(choose.call_count, 2)

    def test_teammates_do_not_take_a_controlled_ball(self):
        owner = Player(1, "left", Vec2(10, 10))
        teammate = Player(2, "left", Vec2(10.94, 10))
        ball = Ball(Vec2(10.48, 10), status=BallStatus.CONTROLLED, owner=("left", 1))
        simulation = scenario([owner, teammate], ball)
        simulation.step()
        self.assertEqual(ball.owner, ("left", 1))
        self.assertIs(owner.status, PlayerStatus.DRIBBLING)

    def test_simultaneous_contests_repeat_with_the_same_seed(self):
        results = []
        for _ in range(2):
            simulation = scenario([
                Player(1, "left", Vec2(9.54, 10)),
                Player(1, "right", Vec2(10.46, 10), facing=Vec2(-1, 0)),
            ], Ball(Vec2(10, 10)), seed=42)
            for _ in range(20):
                simulation.step()
            results.append(to_render_state(simulation.state))
        self.assertEqual(results[0], results[1])


class DribbleDecisionTests(unittest.TestCase):
    def test_carrier_attacks_the_goal_when_not_under_pressure(self):
        carrier = Player(1, "left", Vec2(15, 10))
        teammate = Player(2, "left", Vec2(14, 10))
        nearest = Player(1, "right", Vec2(10, 10))
        farther = Player(2, "right", Vec2(30, 10))
        ball = Ball(Vec2(15.48, 10), status=BallStatus.CONTROLLED, owner=("left", 1))
        simulation = scenario([carrier, teammate, nearest, farther], ball)
        decisions = simulation.get_decisions()
        attacking = [decision for decision in decisions if decision.team_id == "left"]
        self.assertEqual([decision.player_id for decision in attacking], [1])
        self.assertEqual(attacking[0].target.distance(simulation.state.goals["right"].position), 0)

    def test_carrier_with_no_teammate_keeps_dribbling_under_pressure(self):
        carrier = Player(1, "left", Vec2(39, 10))
        defender = Player(1, "right", Vec2(38, 10))
        simulation = scenario([carrier, defender], Ball(Vec2(39.48, 10), status=BallStatus.CONTROLLED, owner=("left", 1)))
        decision = next(decision for decision in simulation.get_decisions() if decision.team_id == "left")
        self.assertEqual(decision.target.distance(simulation.state.goals["right"].position), 0)


if __name__ == "__main__":
    unittest.main()
