import math
import unittest

from simulation import SoccerSimulation
from simulation.objects import Ball, BallStatus, GameState, Player, Team
from simulation.physics import (
    PhysicsConfig, advance_physics, kick_ball, move_player,
    resolve_ball_interactions, update_ball,
)
from simulation.vectors import Vec2


def world(players=(), ball=None):
    return GameState(
        time=0, pitch={"width": 40, "height": 20},
        ball=ball if ball is not None else Ball(Vec2(35, 18)),
        teams={"left": Team("left", list(players))},
    )


class LocomotionTests(unittest.TestCase):
    def test_acceleration_and_speed_have_time_units(self):
        player = Player(1, "left", Vec2(0, 0))
        for tick in range(600):
            previous = player.velocity.copy()
            move_player(player, Vec2(1000, 0), 1 / 120)
            self.assertLessEqual(player.velocity.magnitude(), player.max_speed + 1e-9)
            self.assertLessEqual((player.velocity - previous).magnitude(), player.max_acceleration / 120 + 1e-9)
            if tick == 119:
                self.assertAlmostEqual(player.velocity.x, 3.0)

    def test_arrives_without_orbiting_a_stationary_target(self):
        player = Player(1, "left", Vec2(0, 0))
        furthest = 0
        for _ in range(1800):
            move_player(player, Vec2(10, 0), 1 / 120)
            furthest = max(furthest, player.position.x)
        self.assertLessEqual(furthest, 10.02)
        self.assertLess(player.position.distance(Vec2(10, 0)), player.arrival_radius + 0.01)
        self.assertEqual(player.velocity.magnitude(), 0)

    def test_idle_command_brakes_at_the_configured_rate(self):
        player = Player(1, "left", Vec2(0, 0), velocity=Vec2(6, 0))
        for _ in range(240):
            move_player(player, None, 1 / 120)
        self.assertEqual(player.velocity.magnitude(), 0)
        self.assertAlmostEqual(player.position.x, 6 ** 2 / (2 * player.max_deceleration), delta=0.03)

    def test_reversal_brakes_before_changing_direction(self):
        player = Player(1, "left", Vec2(10, 0), velocity=Vec2(6, 0))
        move_player(player, Vec2(0, 0), 1 / 120)
        self.assertGreater(player.velocity.x, 0)
        self.assertLess(player.acceleration.x, 0)
        for _ in range(240):
            move_player(player, Vec2(0, 0), 1 / 120)
        self.assertLess(player.velocity.x, 0)

    def test_turning_shares_the_acceleration_budget(self):
        player = Player(1, "left", Vec2(0, 0), velocity=Vec2(7, 0))
        for _ in range(100):
            forward = player.velocity.normalize()
            move_player(player, Vec2(0, 100), 1 / 120)
            longitudinal = player.acceleration.dot(forward)
            lateral = (player.acceleration - forward * longitudinal).magnitude()
            limit = player.max_acceleration if longitudinal >= 0 else player.max_deceleration
            self.assertLessEqual((longitudinal / limit) ** 2 + (lateral / player.max_lateral_acceleration) ** 2, 1 + 1e-9)
        self.assertGreater(player.velocity.y, 0)

    def test_motor_results_converge_when_public_tick_size_changes(self):
        results = []
        for dt in (1 / 30, 1 / 60, 1 / 120):
            player = Player(1, "left", Vec2(5, 5))
            state = world([player])
            for _ in range(round(2 / dt)):
                advance_physics(state, {("left", 1): Vec2(30, 5)}, dt)
            results.append(player.position.x)
        self.assertLess(max(results) - min(results), 0.02)


class BallAndContactTests(unittest.TestCase):
    def test_rolling_friction_stops_without_reversing(self):
        ball = Ball(Vec2(0, 0), velocity=Vec2(8, 0), rolling_deceleration=2)
        update_ball(ball, 10)
        self.assertAlmostEqual(ball.position.x, 16)
        self.assertEqual(ball.velocity.magnitude(), 0)
        update_ball(ball, 1)
        self.assertAlmostEqual(ball.position.x, 16)

    def test_ball_free_flight_is_independent_of_partition(self):
        first = Ball(Vec2(0, 0), velocity=Vec2(6, 2))
        second = Ball(Vec2(0, 0), velocity=Vec2(6, 2))
        update_ball(first, 1)
        for _ in range(100):
            update_ball(second, 0.01)
        self.assertAlmostEqual(first.position.distance(second.position), 0)
        self.assertAlmostEqual(first.velocity.distance(second.velocity), 0)

    def test_ball_contact_conserves_momentum_before_speed_caps(self):
        player = Player(1, "left", Vec2(10, 10))
        ball = Ball(Vec2(10.4, 10), velocity=Vec2(-10, 0))
        momentum = ball.velocity.x * ball.mass
        resolve_ball_interactions(ball, [player], restitution=0.5)
        self.assertAlmostEqual(player.mass * player.velocity.x + ball.mass * ball.velocity.x, momentum)
        self.assertAlmostEqual(ball.velocity.x - player.velocity.x, 5)
        self.assertAlmostEqual(ball.position.distance(player.position), ball.radius + player.radius)

    def test_fast_ball_does_not_pass_through_a_player_head_on(self):
        player = Player(1, "left", Vec2(10, 10))
        ball = Ball(Vec2(8, 10), velocity=Vec2(35, 0))
        state = world([player], ball)
        advance_physics(state, {}, 0.1)
        self.assertLess(ball.velocity.x, 0)
        self.assertLess(ball.position.x, player.position.x)

    def test_coincident_players_separate_deterministically(self):
        first, second = Player(1, "left", Vec2(10, 10)), Player(2, "left", Vec2(10, 10))
        advance_physics(world([first, second]), {}, 1 / 60)
        self.assertGreaterEqual(first.position.distance(second.position), first.radius + second.radius - 1e-8)
        self.assertTrue(math.isfinite(first.position.x))

    def test_pitch_boundary_removes_only_outward_velocity(self):
        player = Player(1, "left", Vec2(0.36, 10), velocity=Vec2(-5, 2))
        state = world([player])
        advance_physics(state, {}, 0.1)
        self.assertGreaterEqual(player.position.x, player.radius)
        self.assertGreaterEqual(player.velocity.x, 0)
        self.assertGreater(player.velocity.y, 0)

    def test_ball_containment_can_be_disabled_for_future_out_of_play_rules(self):
        contained = world(ball=Ball(Vec2(39, 10), velocity=Vec2(10, 0)))
        free = world(ball=Ball(Vec2(39, 10), velocity=Vec2(10, 0)))
        advance_physics(contained, {}, 0.2)
        advance_physics(free, {}, 0.2, PhysicsConfig(contain_ball=False))
        self.assertAlmostEqual(contained.ball.position.x, 40 - contained.ball.radius)
        self.assertEqual(contained.ball.velocity.x, 0)
        self.assertGreater(free.ball.position.x, 40)

    def test_controlled_ball_follows_owner_until_kicked(self):
        owner = Player(1, "left", Vec2(10, 10), velocity=Vec2(1, 0))
        ball = Ball(Vec2(0, 0), status=BallStatus.CONTROLLED, owner=("left", 1))
        advance_physics(world([owner], ball), {}, 1 / 60)
        self.assertGreater(ball.position.x, owner.position.x)
        self.assertAlmostEqual(ball.velocity.distance(owner.velocity), 0)
        kick_ball(ball, Vec2(1, 0), 10)
        self.assertIs(ball.status, BallStatus.LOOSE)
        self.assertIsNone(ball.owner)


class ValidationTests(unittest.TestCase):
    def test_rejects_invalid_timesteps_and_parameters(self):
        simulation = SoccerSimulation({})
        for dt in (0, -1, float("nan"), float("inf"), 1):
            with self.subTest(dt=dt), self.assertRaises(ValueError):
                simulation.step(dt)
        with self.assertRaises(ValueError):
            Player(1, "left", Vec2(0, 0), max_deceleration=0)
        with self.assertRaises(ValueError):
            PhysicsConfig(ball_restitution=2)
        with self.assertRaises(ValueError):
            Vec2(float("nan"), 0)


if __name__ == "__main__":
    unittest.main()
