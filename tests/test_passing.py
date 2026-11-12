import math
import unittest
from unittest.mock import patch

from simulation import SoccerSimulation
from simulation.objects import Ball, BallStatus, Player, Team
from simulation.physics import kick_ball, pass_ball, plan_pass, update_ball
from simulation.state import to_render_state
from simulation.tactics import MoveDecision, PassDecision, is_pass_blocked
from simulation.vectors import Vec2


def controlled_scenario(passer, teammates, opponents, ball=None):
    simulation = SoccerSimulation({"seed": 0})
    simulation.state.teams = {}
    for player in [passer, *teammates, *opponents]:
        simulation.state.teams.setdefault(player.team_id, Team(player.team_id)).players.append(player)
    simulation.state.ball = ball if ball is not None else Ball(
        passer.position + passer.facing * 0.48,
        velocity=passer.velocity.copy(), status=BallStatus.CONTROLLED,
        owner=(passer.team_id, passer.id),
    )
    simulation.possession.update_statuses(simulation.state)
    return simulation


class PassDecisionTests(unittest.TestCase):
    def test_a_blocked_nearest_teammate_falls_back_to_the_other_teammate(self):
        passer = Player(1, "left", Vec2(10, 10))
        nearest = Player(2, "left", Vec2(14, 10))
        other = Player(3, "left", Vec2(10, 16))
        simulation = controlled_scenario(passer, [nearest, other], [Player(1, "right", Vec2(12, 10))])
        action = next(action for action in simulation.get_decisions() if action.team_id == "left")
        self.assertIsInstance(action, PassDecision)
        self.assertEqual(action.receiver_id, 3)

    def test_a_clear_nearest_lane_keeps_priority_over_the_other_teammate(self):
        passer = Player(1, "left", Vec2(10, 10))
        nearest = Player(2, "left", Vec2(14, 10))
        other = Player(3, "left", Vec2(10, 16))
        simulation = controlled_scenario(passer, [nearest, other], [Player(1, "right", Vec2(10, 12))])
        action = next(action for action in simulation.get_decisions() if action.team_id == "left")
        self.assertIsInstance(action, PassDecision)
        self.assertEqual(action.receiver_id, 2)

    def test_both_blocked_lanes_keep_the_carrier_dribbling(self):
        passer = Player(1, "left", Vec2(10, 10))
        simulation = controlled_scenario(passer, [
            Player(2, "left", Vec2(14, 10)), Player(3, "left", Vec2(10, 16)),
        ], [Player(1, "right", Vec2(12, 10)), Player(2, "right", Vec2(10, 12))])
        action = next(action for action in simulation.get_decisions() if action.team_id == "left")
        self.assertIsInstance(action, MoveDecision)

    def test_pressure_at_three_meters_selects_the_nearest_teammate(self):
        passer = Player(1, "left", Vec2(10, 10))
        near = Player(3, "left", Vec2(10, 16))
        far = Player(2, "left", Vec2(18, 10))
        opponent = Player(1, "right", Vec2(13, 10))
        simulation = controlled_scenario(passer, [far, near], [opponent])
        action = next(action for action in simulation.get_decisions() if action.team_id == "left")
        self.assertIsInstance(action, PassDecision)
        self.assertEqual((action.player_id, action.receiver_id), (1, 3))
        opponent.position.x = 13.01
        action = next(action for action in simulation.get_decisions() if action.team_id == "left")
        self.assertIsInstance(action, MoveDecision)

    def test_equal_distance_teammates_use_player_id_as_a_tiebreaker(self):
        passer = Player(1, "left", Vec2(10, 10))
        simulation = controlled_scenario(passer, [
            Player(3, "left", Vec2(15, 10)), Player(2, "left", Vec2(10, 15)),
        ], [Player(1, "right", Vec2(8, 10))])
        action = next(action for action in simulation.get_decisions() if isinstance(action, PassDecision))
        self.assertEqual(action.receiver_id, 2)

    def test_an_unreachable_pass_keeps_the_carrier_dribbling(self):
        passer = Player(1, "left", Vec2(10, 10))
        receiver = Player(2, "left", Vec2(20, 10))
        ball = Ball(Vec2(10.48, 10), status=BallStatus.CONTROLLED, owner=("left", 1), max_speed=2)
        simulation = controlled_scenario(passer, [receiver], [Player(1, "right", Vec2(8, 10))], ball)
        action = next(action for action in simulation.get_decisions() if action.team_id == "left")
        self.assertIsInstance(action, MoveDecision)
        self.assertIsNone(plan_pass(ball, passer, receiver))


class PassPhysicsTests(unittest.TestCase):
    def test_launch_speed_delivers_three_meters_per_second_at_the_target(self):
        for distance, friction in ((2, 0.8), (10, 0.8), (25, 1.5), (10, 0)):
            with self.subTest(distance=distance, friction=friction):
                passer = Player(1, "left", Vec2(5, 5))
                receiver = Player(2, "left", Vec2(5 + distance, 5))
                ball = Ball(Vec2(5.48, 5), rolling_deceleration=friction)
                pass_ball(ball, passer, receiver)
                travel = ball.position.distance(receiver.position)
                initial_speed = ball.velocity.magnitude()
                self.assertAlmostEqual(initial_speed, math.sqrt(3 ** 2 + 2 * friction * travel))
                flight_time = 2 * travel / (initial_speed + 3)
                update_ball(ball, flight_time)
                self.assertAlmostEqual(ball.position.distance(receiver.position), 0)
                self.assertAlmostEqual(ball.velocity.magnitude(), 3)

    def test_the_pass_replaces_inherited_sideways_velocity(self):
        passer = Player(1, "left", Vec2(5, 5), velocity=Vec2(0, 5))
        receiver = Player(2, "left", Vec2(15, 5))
        ball = Ball(Vec2(5, 5.48), velocity=Vec2(0, 5), status=BallStatus.CONTROLLED, owner=("left", 1))
        pass_ball(ball, passer, receiver)
        self.assertAlmostEqual(ball.velocity.y, 0)
        self.assertGreater(ball.velocity.x, 3)
        self.assertIs(ball.status, BallStatus.LOOSE)
        self.assertIsNone(ball.owner)

    def test_pass_speed_limit_does_not_silently_weaken_a_pass(self):
        ball = Ball(Vec2(5, 5), max_speed=3)
        with self.assertRaises(ValueError):
            pass_ball(ball, Player(1, "left", Vec2(5, 5)), Player(2, "left", Vec2(15, 5)))


class PassIntegrationTests(unittest.TestCase):
    def test_a_pass_is_received_at_or_above_three_meters_per_second(self):
        passer = Player(1, "left", Vec2(10, 10))
        receiver = Player(2, "left", Vec2(20, 10))
        opponent = Player(1, "right", Vec2(10, 12))
        simulation = controlled_scenario(passer, [receiver], [opponent])
        arrivals = []
        original = simulation.possession.resolve_contacts

        def record_arrival(state, contacts):
            if receiver in contacts and state.ball.pass_state is not None:
                arrivals.append(state.ball.velocity.magnitude())
            original(state, contacts)

        with patch.object(simulation.possession, "resolve_contacts", side_effect=record_arrival):
            for _ in range(300):
                simulation.step()
                if simulation.state.ball.owner == ("left", 2):
                    break
        self.assertEqual(simulation.state.ball.owner, ("left", 2))
        self.assertTrue(arrivals)
        self.assertGreaterEqual(arrivals[0], 3)
        self.assertIsNone(simulation.state.ball.pass_state)

    def test_a_moving_passer_cannot_immediately_reclaim_their_release(self):
        for receiver_x in (5, 12):
            with self.subTest(receiver_x=receiver_x):
                passer = Player(1, "left", Vec2(10, 10), velocity=Vec2(7, 0))
                receiver = Player(2, "left", Vec2(receiver_x, 10))
                simulation = controlled_scenario(passer, [receiver], [Player(1, "right", Vec2(10, 12))])
                simulation.step()
                self.assertIs(simulation.state.ball.status, BallStatus.LOOSE)
                self.assertIsNone(simulation.state.ball.owner)
                actions = [action for action in simulation.get_decisions() if action.team_id == "left"]
                self.assertEqual([action.player_id for action in actions], [2])

    def test_an_opponent_can_intercept_and_clear_the_pass_intent(self):
        passer = Player(1, "left", Vec2(10, 10))
        receiver = Player(2, "left", Vec2(20, 10))
        opponent = Player(1, "right", Vec2(12, 11))
        simulation = controlled_scenario(passer, [receiver], [opponent])
        # The lane is clear when selected; a defender then moves into the flight.
        simulation.apply_actions(simulation.get_decisions(), simulation.fixed_dt)
        self.assertIsNotNone(simulation.state.ball.pass_state)
        opponent.position = Vec2(12, 10)
        for _ in range(120):
            simulation.step()
            if simulation.state.ball.owner == ("right", 1):
                break
        self.assertEqual(simulation.state.ball.owner, ("right", 1))
        self.assertIsNone(simulation.state.ball.pass_state)

    def test_pass_snapshot_is_detached_and_manual_kicks_cancel_the_intent(self):
        passer = Player(1, "left", Vec2(10, 10))
        receiver = Player(2, "left", Vec2(20, 10))
        simulation = controlled_scenario(passer, [receiver], [Player(1, "right", Vec2(10, 12))])
        simulation.apply_actions(simulation.get_decisions(), simulation.fixed_dt)
        rendered = to_render_state(simulation.state)
        self.assertEqual(rendered["ball"]["pass"]["receiver"], ("left", 2))
        rendered["ball"]["pass"]["target"]["x"] = -10
        self.assertEqual(simulation.state.ball.pass_state.target.x, 20)
        kick_ball(simulation.state.ball, Vec2(0, 1), 1)
        self.assertIsNone(simulation.state.ball.pass_state)

    def test_an_invalid_pass_action_does_not_release_possession(self):
        passer = Player(1, "left", Vec2(10, 10))
        receiver = Player(2, "left", Vec2(20, 10))
        simulation = controlled_scenario(passer, [receiver], [])
        with self.assertRaises(ValueError):
            simulation.apply_actions([PassDecision("left", 2, 1)], simulation.fixed_dt)
        self.assertEqual(simulation.state.ball.owner, ("left", 1))


class PassLaneTests(unittest.TestCase):
    def test_a_defender_on_or_touching_the_lane_blocks_it(self):
        for y in (0, 0.46):
            with self.subTest(y=y):
                defender = Player(1, "right", Vec2(5, y))
                self.assertTrue(is_pass_blocked(Vec2(0, 0), Vec2(10, 0), [defender], 0.11))

    def test_defenders_outside_the_lane_or_beyond_its_ends_do_not_block(self):
        for position in (Vec2(5, 0.47), Vec2(-2, 0), Vec2(12, 0)):
            with self.subTest(position=position):
                defender = Player(1, "right", position)
                self.assertFalse(is_pass_blocked(Vec2(0, 0), Vec2(10, 0), [defender], 0.11))

    def test_diagonal_lanes_use_perpendicular_distance(self):
        defender = Player(1, "right", Vec2(5, 5.5))
        self.assertTrue(is_pass_blocked(Vec2(0, 0), Vec2(10, 10), [defender], 0.11))
        defender.position = Vec2(5, 6)
        self.assertFalse(is_pass_blocked(Vec2(0, 0), Vec2(10, 10), [defender], 0.11))


if __name__ == "__main__":
    unittest.main()
