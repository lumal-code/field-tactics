import unittest

from simulation import SoccerSimulation
from simulation.objects import Ball, BallStatus, PassState, Player, Team
from simulation.physics import predict_ball_position
from simulation.state import initialize_game, to_render_state
from simulation.tactics import decide, defender_target, interception_target
from simulation.vectors import Vec2


def world(ball, players):
    state = initialize_game({})
    state.ball = ball
    state.teams = {}
    for player in players:
        state.teams.setdefault(player.team_id, Team(player.team_id)).players.append(player)
    return state


class DefenderDecisionTests(unittest.TestCase):
    def test_rondo_defender_has_an_independent_default_position_at_pitch_center(self):
        simulation = SoccerSimulation({"pitch_width": 40, "pitch_height": 30})
        defender = simulation.state.teams["right"].players[0]
        self.assertEqual(defender.default_position.distance(Vec2(20, 15)), 0)
        self.assertEqual(defender.reset_distance, 5)
        self.assertTrue(all(player.default_position is None for player in simulation.state.teams["left"].players))
        defender.position.x = 25
        self.assertEqual(defender.default_position.x, 20)
        rendered = to_render_state(simulation.state)
        rendered["teams"]["right"]["players"][0]["default_position"]["x"] = -1
        self.assertEqual(defender.default_position.x, 20)

    def test_five_meter_reset_takes_priority_over_every_pursuit_branch(self):
        defender = Player(1, "right", Vec2(15, 10), default_position=Vec2(20, 10))
        carrier = Player(1, "left", Vec2(9.52, 10))
        ball = Ball(Vec2(10, 10))
        state = world(ball, [carrier, defender])
        for status, velocity, owner in (
            (BallStatus.LOOSE, Vec2(0, 0), None),
            (BallStatus.LOOSE, Vec2(4, 0), None),
            (BallStatus.CONTROLLED, Vec2(0, 0), ("left", 1)),
        ):
            with self.subTest(status=status, velocity=velocity):
                ball.status, ball.velocity, ball.owner = status, velocity, owner
                target = defender_target(defender, state)
                self.assertEqual(target.distance(Vec2(20, 10)), 0)
                target.x = -1
                self.assertEqual(defender.default_position.x, 20)

    def test_pursuit_resumes_when_the_ball_is_closer_than_the_reset_distance(self):
        defender = Player(1, "right", Vec2(15, 10), default_position=Vec2(20, 10))
        ball = Ball(Vec2(10, 10))
        state = world(ball, [defender])
        self.assertEqual(defender_target(defender, state).distance(defender.default_position), 0)
        ball.position.x = 10.01
        self.assertEqual(defender_target(defender, state).distance(ball.position), 0)

    def test_reset_moves_through_physics_instead_of_teleporting(self):
        defender = Player(1, "right", Vec2(15, 10), default_position=Vec2(20, 10))
        simulation = SoccerSimulation({"seed": 1})
        simulation.state = world(Ball(Vec2(8, 10)), [defender])
        for _ in range(60):
            simulation.step()
        self.assertGreater(defender.position.x, 15)
        self.assertLess(defender.position.x, 20)
        self.assertLess(defender.position.distance(defender.default_position), 5)
        self.assertLessEqual(defender.velocity.magnitude(), defender.max_speed)

    def test_controlled_ball_targets_the_carrier_instead_of_the_ball_offset(self):
        carrier = Player(1, "left", Vec2(10, 10))
        defender = Player(1, "right", Vec2(5, 10))
        ball = Ball(Vec2(10.48, 10), status=BallStatus.CONTROLLED, owner=("left", 1))
        state = world(ball, [carrier, defender])
        target = defender_target(defender, state)
        self.assertEqual(target.distance(carrier.position), 0)
        self.assertGreater(target.distance(ball.position), 0)
        target.x = -1
        self.assertEqual(carrier.position.x, 10)

    def test_a_stationary_loose_ball_is_chased_directly(self):
        defender = Player(1, "right", Vec2(5, 5))
        ball = Ball(Vec2(10, 10))
        target = defender_target(defender, world(ball, [defender]))
        self.assertEqual(target.distance(ball.position), 0)
        target.x = -1
        self.assertEqual(ball.position.x, 10)

    def test_a_moving_loose_ball_is_targeted_ahead_of_its_current_position(self):
        defender = Player(1, "right", Vec2(8, 7))
        ball = Ball(Vec2(10, 10), velocity=Vec2(4, 0))
        target = defender_target(defender, world(ball, [defender]))
        self.assertGreater(target.x, ball.position.x)
        self.assertEqual(target.y, 10)
        self.assertLessEqual(target.x, 20)  # Stopping point for 4 m/s at 0.8 m/s^2.
        self.assertEqual((ball.position.x, ball.position.y, ball.velocity.x, ball.velocity.y), (10, 10, 4, 0))

    def test_the_defender_switches_decisions_as_ball_state_changes(self):
        carrier = Player(1, "left", Vec2(10, 10))
        defender = Player(1, "right", Vec2(5, 5))
        ball = Ball(Vec2(10.48, 10), status=BallStatus.CONTROLLED, owner=("left", 1))
        state = world(ball, [carrier, defender])

        def target():
            return next(action.target for action in decide(state) if action.team_id == "right")

        self.assertEqual(target().distance(carrier.position), 0)
        ball.status, ball.owner, ball.velocity = BallStatus.LOOSE, None, Vec2(4, 0)
        self.assertGreater(target().x, ball.position.x)
        ball.velocity = Vec2(0, 0)
        self.assertEqual(target().distance(ball.position), 0)

    def test_a_controlled_ball_selects_the_nearest_defender_to_the_carrier(self):
        carrier = Player(1, "left", Vec2(10, 10))
        near_carrier = Player(2, "right", Vec2(9.1, 10))
        near_ball = Player(1, "right", Vec2(11.1, 10))
        state = world(Ball(Vec2(10.48, 10), status=BallStatus.CONTROLLED, owner=("left", 1)), [carrier, near_carrier, near_ball])
        action = next(action for action in decide(state) if action.team_id == "right")
        self.assertEqual(action.player_id, near_carrier.id)

    def test_an_intended_receiver_keeps_the_reception_target_while_defenders_predict(self):
        passer = Player(1, "left", Vec2(8, 10))
        receiver = Player(2, "left", Vec2(20, 10))
        defender = Player(1, "right", Vec2(12, 7))
        ball = Ball(Vec2(10, 10), velocity=Vec2(5, 0), pass_state=PassState(("left", 1), ("left", 2), Vec2(20, 10)))
        actions = decide(world(ball, [passer, receiver, defender]))
        receiving = next(action for action in actions if action.team_id == "left")
        defending = next(action for action in actions if action.team_id == "right")
        self.assertEqual(receiving.player_id, 2)
        self.assertEqual(receiving.target.distance(Vec2(20, 10)), 0)
        self.assertGreater(defending.target.x, ball.position.x)


class InterceptionPredictionTests(unittest.TestCase):
    def test_prediction_accounts_for_friction_and_does_not_reverse_after_stopping(self):
        ball = Ball(Vec2(10, 10), velocity=Vec2(1, 0), rolling_deceleration=2)
        self.assertAlmostEqual(predict_ball_position(ball, 0.25).x, 10.1875)
        self.assertAlmostEqual(predict_ball_position(ball, 5).x, 10.25)
        self.assertEqual(ball.position.x, 10)
        self.assertEqual(ball.velocity.x, 1)

    def test_an_unreachable_fast_ball_uses_the_bounded_prediction_horizon(self):
        defender = Player(1, "right", Vec2(2, 2), max_speed=0)
        ball = Ball(Vec2(10, 10), velocity=Vec2(4, 0), rolling_deceleration=0)
        target = interception_target(defender, world(ball, [defender]))
        self.assertAlmostEqual(target.x, 22)

    def test_prediction_respects_the_ball_stopping_point_and_pitch_bounds(self):
        defender = Player(1, "right", Vec2(2, 2), max_speed=0)
        ball = Ball(Vec2(10, 10), velocity=Vec2(1, 0), rolling_deceleration=2)
        self.assertAlmostEqual(interception_target(defender, world(ball, [defender])).x, 10.25)
        ball.position, ball.velocity, ball.rolling_deceleration = Vec2(39, 10), Vec2(10, 0), 0
        self.assertAlmostEqual(interception_target(defender, world(ball, [defender])).x, 40 - ball.radius)

    def test_a_more_agile_defender_estimates_an_earlier_interception(self):
        ball = Ball(Vec2(10, 10), velocity=Vec2(4, 0))
        slow = Player(1, "right", Vec2(10, 4), max_acceleration=0.5)
        fast = Player(2, "right", Vec2(10, 4), max_acceleration=3)
        state = world(ball, [slow, fast])
        self.assertLess(interception_target(fast, state).x, interception_target(slow, state).x)

    def test_predictive_chase_can_capture_a_travelling_ball(self):
        defender = Player(1, "right", Vec2(14, 8))
        simulation = SoccerSimulation({"seed": 1})
        simulation.state = world(Ball(Vec2(10, 10), velocity=Vec2(4, 0)), [defender])
        for _ in range(180):
            simulation.step()
            if simulation.state.ball.status is BallStatus.CONTROLLED:
                break
        self.assertEqual(simulation.state.ball.owner, ("right", 1))


if __name__ == "__main__":
    unittest.main()
