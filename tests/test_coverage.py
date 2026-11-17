import unittest

from simulation import SoccerSimulation
from simulation.objects import Ball, BallStatus, Player, Team
from simulation.state import initialize_game, to_render_state
from simulation.tactics import covered_opponent_ids, decide, defender_target, press_lane_weight, update_coverage
from simulation.vectors import Vec2


def world(players, carrier=None):
    state = initialize_game({})
    state.teams = {}
    for player in players:
        state.teams.setdefault(player.team_id, Team(player.team_id)).players.append(player)
    if carrier is not None:
        state.ball = Ball(carrier.position + carrier.facing * 0.48, status=BallStatus.CONTROLLED, owner=(carrier.team_id, carrier.id))
    return state


class CoverageTests(unittest.TestCase):
    def test_coverage_includes_three_meters_and_excludes_anything_farther(self):
        defender = Player(1, "right", Vec2(10, 10))
        attacker = Player(1, "left", Vec2(13, 10))
        state = world([defender, attacker])
        self.assertEqual(covered_opponent_ids(state.teams["right"], state), {("left", 1)})
        attacker.position.x = 13.001
        self.assertEqual(covered_opponent_ids(state.teams["right"], state), set())

    def test_any_defender_can_cover_an_opponent_without_mixing_team_ids(self):
        first = Player(1, "right", Vec2(10, 10))
        second = Player(2, "right", Vec2(20, 10))
        close = Player(1, "left", Vec2(13, 10))
        farther = Player(2, "left", Vec2(23.01, 10))
        state = world([first, second, close, farther])
        update_coverage(state)
        self.assertEqual(state.teams["right"].covered_opponents, {("left", 1)})
        second.position.x = 20.02
        update_coverage(state)
        self.assertEqual(state.teams["right"].covered_opponents, {("left", 1), ("left", 2)})
        self.assertNotIn(("right", 1), state.teams["right"].covered_opponents)

    def test_coverage_clears_as_players_separate_and_render_data_is_detached(self):
        defender = Player(1, "right", Vec2(15, 10))
        attacker = Player(1, "left", Vec2(12, 10))
        state = world([defender, attacker])
        decide(state)
        self.assertEqual(state.teams["right"].covered_opponents, {("left", 1)})
        rendered = to_render_state(state)
        self.assertEqual(rendered["teams"]["right"]["covered_opponents"], [("left", 1)])
        rendered["teams"]["right"]["covered_opponents"].clear()
        self.assertEqual(state.teams["right"].covered_opponents, {("left", 1)})
        attacker.position.x = 11
        decide(state)
        self.assertEqual(state.teams["right"].covered_opponents, set())

    def test_coverage_refreshes_after_physics_moves_the_defender(self):
        defender = Player(1, "right", Vec2(15, 10), velocity=Vec2(7, 0))
        attacker = Player(1, "left", Vec2(12.01, 10))
        simulation = SoccerSimulation({"seed": 1})
        simulation.state = world([defender, attacker])
        simulation.state.ball = Ball(Vec2(30, 18))
        simulation.get_decisions()
        self.assertIn(("left", 1), simulation.state.teams["right"].covered_opponents)
        simulation.step(0.01)
        self.assertNotIn(("left", 1), simulation.state.teams["right"].covered_opponents)

    def test_a_team_with_no_defenders_covers_nobody(self):
        state = world([Player(1, "left", Vec2(10, 10))])
        state.teams["right"] = Team("right")
        update_coverage(state)
        self.assertEqual(state.teams["right"].covered_opponents, set())


class PressureLaneBlendTests(unittest.TestCase):
    def test_blend_is_full_press_at_one_meter_and_full_lane_at_eight(self):
        carrier = Player(1, "left", Vec2(10, 10))
        receiver = Player(2, "left", Vec2(22, 10))
        for position, expected in (
            (Vec2(10.6, 10.8), Vec2(10, 10)),
            (Vec2(12.7, 13.6), Vec2(11.35, 10)),
            (Vec2(14.8, 16.4), Vec2(14.8, 10)),
            (Vec2(16, 18), Vec2(16, 10)),
        ):
            with self.subTest(position=position):
                defender = Player(1, "right", position)
                state = world([carrier, receiver, defender], carrier)
                target = defender_target(defender, state)
                self.assertAlmostEqual(target.distance(expected), 0)

    def test_blend_weights_are_clamped_outside_the_one_to_eight_meter_range(self):
        self.assertEqual(press_lane_weight(0), 0)
        self.assertEqual(press_lane_weight(1), 0)
        self.assertAlmostEqual(press_lane_weight(4.5), 0.5)
        self.assertEqual(press_lane_weight(8), 1)
        self.assertEqual(press_lane_weight(20), 1)

    def test_a_receiver_covered_by_a_teammate_is_skipped(self):
        carrier = Player(1, "left", Vec2(10, 10))
        nearest = Player(2, "left", Vec2(14, 10))
        other = Player(3, "left", Vec2(10, 18))
        defender = Player(1, "right", Vec2(20, 18))
        covering_teammate = Player(2, "right", Vec2(14, 12.5))
        state = world([carrier, nearest, other, defender, covering_teammate], carrier)
        self.assertEqual(defender_target(defender, state).distance(Vec2(10, 18)), 0)
        self.assertIn(("left", 2), state.teams["right"].covered_opponents)
        covering_teammate.position = Vec2(35, 15)
        self.assertEqual(defender_target(defender, state).distance(Vec2(14, 10)), 0)
        self.assertNotIn(("left", 2), state.teams["right"].covered_opponents)

    def test_the_defender_also_skips_a_receiver_it_already_covers_itself(self):
        carrier = Player(1, "left", Vec2(10, 10))
        covered_receiver = Player(2, "left", Vec2(16, 10))
        other = Player(3, "left", Vec2(10, 18))
        defender = Player(1, "right", Vec2(16, 12))
        state = world([carrier, covered_receiver, other, defender], carrier)
        target = defender_target(defender, state)
        self.assertEqual(target.x, 10)
        self.assertGreater(target.y, 10)

    def test_nearest_uncovered_option_is_measured_from_the_carrier(self):
        carrier = Player(1, "left", Vec2(10, 10))
        near_carrier = Player(2, "left", Vec2(16, 10))
        near_defender = Player(3, "left", Vec2(10, 18))
        defender = Player(1, "right", Vec2(10, 14))
        state = world([carrier, near_carrier, near_defender, defender], carrier)
        self.assertAlmostEqual(defender_target(defender, state).distance(carrier.position), 0)

    def test_all_covered_options_fall_back_to_pressing_the_carrier(self):
        carrier = Player(1, "left", Vec2(10, 10))
        receiver = Player(2, "left", Vec2(22, 10))
        defender = Player(1, "right", Vec2(16, 18))
        covering_teammate = Player(2, "right", Vec2(22, 12))
        state = world([carrier, receiver, defender, covering_teammate], carrier)
        self.assertEqual(defender_target(defender, state).distance(carrier.position), 0)

    def test_lane_projection_stays_on_the_finite_passing_segment(self):
        carrier = Player(1, "left", Vec2(10, 10))
        receiver = Player(2, "left", Vec2(15, 10))
        defender = Player(1, "right", Vec2(20, 18))
        state = world([carrier, receiver, defender], carrier)
        self.assertEqual(defender_target(defender, state).distance(receiver.position), 0)

    def test_coincident_carrier_and_receiver_do_not_produce_invalid_geometry(self):
        carrier = Player(1, "left", Vec2(10, 10))
        receiver = Player(2, "left", Vec2(10, 10))
        defender = Player(1, "right", Vec2(20, 18))
        state = world([carrier, receiver, defender], carrier)
        self.assertEqual(defender_target(defender, state).distance(carrier.position), 0)


if __name__ == "__main__":
    unittest.main()
