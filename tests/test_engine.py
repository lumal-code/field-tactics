import unittest

from simulation import SoccerSimulation
from simulation.objects import Ball, BallStatus
from simulation.physics import kick_ball, update_ball
from simulation.state import to_render_state
from simulation.vectors import Vec2
from simulation.visualizer import pitch_to_screen, screen_to_pitch


class RecordingSimulation(SoccerSimulation):
    def __init__(self, config):
        super().__init__(config)
        self.calls = []

    def get_decisions(self):
        self.calls.append("decide")
        return ["sample action"]

    def apply_actions(self, decisions, dt):
        self.calls.append(("actions", decisions, dt))

    def update_physics(self, dt):
        self.calls.append(("physics", dt))

    def resolve_game_rules(self):
        self.calls.append("rules")


class SoccerSimulationTests(unittest.TestCase):
    def test_initial_state_has_three_attackers_and_one_defender(self):
        state = SoccerSimulation({"pitch_width": 100, "pitch_height": 68}).state
        self.assertEqual(len(state.teams["left"].players), 3)
        self.assertEqual(len(state.teams["right"].players), 1)
        self.assertEqual((state.ball.position.x, state.ball.position.y), (68.0, 34.0))
        self.assertIs(state.ball.status, BallStatus.LOOSE)
        self.assertIsNone(state.ball.owner)
        self.assertEqual([player.team_id for player in state.teams["right"].players], ["right"])

    def test_step_runs_phases_in_order_and_returns_state(self):
        simulation = RecordingSimulation({})
        result = simulation.step(0.1)
        self.assertIs(result, simulation.state)
        self.assertEqual(simulation.calls, [
            "decide",
            ("actions", ["sample action"], 0.1),
            ("physics", 0.1),
            "rules",
        ])

    def test_goals_follow_pitch_dimensions_and_render_without_sharing_state(self):
        simulation = SoccerSimulation({"pitch_width": 50, "pitch_height": 30, "goal_width": 4, "goal_depth": 1.5})
        left, right = simulation.state.goals["left"], simulation.state.goals["right"]
        self.assertEqual((left.position.x, left.position.y), (0, 15))
        self.assertEqual((right.position.x, right.position.y), (50, 15))
        self.assertEqual((left.facing.x, right.facing.x), (1, -1))
        self.assertEqual((left.team_id, right.team_id), ("left", "right"))
        self.assertEqual((left.width, right.depth), (4, 1.5))
        rendered = to_render_state(simulation.state)
        rendered["goals"]["left"]["position"]["x"] = 99
        self.assertEqual(left.position.x, 0)
        pitch = simulation.state.pitch
        point = pitch_to_screen({"x": 25, "y": 15}, pitch, goal_depth=1.5)
        self.assertEqual(screen_to_pitch(point, pitch, goal_depth=1.5), {"x": 25, "y": 15})

    def test_goal_dimensions_must_fit_the_pitch(self):
        for config in ({"goal_width": 0}, {"goal_width": 21}, {"goal_depth": -1}):
            with self.subTest(config=config), self.assertRaises(ValueError):
                SoccerSimulation(config)

    def test_visualizer_coordinates_use_pitch_dimensions(self):
        pitch = {"width": 100, "height": 68}
        self.assertEqual(pitch_to_screen({"x": 50, "y": 34}, pitch), (540, 412))
        self.assertEqual(screen_to_pitch((540, 412), pitch), {"x": 50.0, "y": 34.0})
        self.assertEqual(screen_to_pitch((-100, 900), pitch), {"x": 0.0, "y": 68})

    def test_nearest_player_on_each_team_moves_toward_the_ball(self):
        simulation = SoccerSimulation({})
        before = {(player.team_id, player.id): player.position.copy()
                  for team in simulation.state.teams.values() for player in team.players}
        selected = {(action.team_id, action.player_id) for action in simulation.get_decisions()}
        ball_position = simulation.state.ball.position.copy()
        for _ in range(60):
            simulation.step(1 / 60)
        self.assertAlmostEqual(simulation.state.time, 1.0)
        for team_id, team in simulation.state.teams.items():
            for player in team.players:
                previous = before[(team_id, player.id)]
                if (team_id, player.id) in selected:
                    self.assertLess(player.position.distance(ball_position), previous.distance(ball_position))
                else:
                    self.assertEqual(player.position.distance(previous), 0)
                self.assertLessEqual(player.velocity.magnitude(), player.max_speed)

    def test_movement_respects_acceleration_limit(self):
        simulation = SoccerSimulation({})
        action = next(action for action in simulation.get_decisions() if action.team_id == "left")
        player = next(player for player in simulation.state.teams["left"].players if player.id == action.player_id)
        simulation.step(0.1)
        self.assertAlmostEqual(player.velocity.magnitude(), player.max_acceleration * 0.1)
        self.assertAlmostEqual(player.acceleration.magnitude(), player.max_acceleration)
        with self.assertRaises(ValueError):
            simulation.step(0)

    def test_mutable_velocity_defaults_are_independent(self):
        first = Ball(position=Vec2(0, 0))
        second = Ball(position=Vec2(0, 0))
        first.status = BallStatus.CONTROLLED
        first.owner = ("left", 2)
        kick_ball(first, Vec2(1, 0), 5)
        update_ball(first, 0.5)
        self.assertEqual((first.position.x, first.position.y), (2.4, 0.0))
        self.assertEqual((second.velocity.x, second.velocity.y), (0.0, 0.0))
        self.assertIs(first.status, BallStatus.LOOSE)
        self.assertIsNone(first.owner)

    def test_render_state_is_plain_and_detached(self):
        simulation = SoccerSimulation({"pitch_width": 100, "pitch_height": 68})
        original_x = simulation.state.teams["left"].players[0].position.x
        rendered = to_render_state(simulation.state)
        rendered["teams"]["left"]["players"][0]["position"]["x"] = -10
        self.assertEqual(simulation.state.teams["left"].players[0].position.x, original_x)
        self.assertEqual(rendered["ball"], {
            "x": 68.0, "y": 34.0, "radius": 0.11, "status": "loose", "owner": None, "pass": None,
        })

    def test_replays_the_same_scenario_deterministically(self):
        first, second = SoccerSimulation({"seed": 7}), SoccerSimulation({"seed": 7})
        for simulation in (first, second):
            for tick in range(120):
                if tick == 60:
                    simulation.state.ball.position = Vec2(20, 4)
                simulation.step()
        self.assertEqual(to_render_state(first.state), to_render_state(second.state))

    def test_decisions_use_absolute_positions_and_detached_targets(self):
        simulation = SoccerSimulation({})
        original = simulation.state.ball.position.copy()
        decisions = simulation.get_decisions()
        self.assertEqual(len(decisions), 2)
        for decision in decisions:
            self.assertEqual(decision.target.distance(original), 0)
        decisions[0].target.x = -1
        self.assertEqual(simulation.state.ball.position.distance(original), 0)


if __name__ == "__main__":
    unittest.main()
