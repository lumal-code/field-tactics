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
    def test_initial_state_has_two_teams_of_three(self):
        state = SoccerSimulation({"pitch_width": 100, "pitch_height": 68}).state
        self.assertEqual(len(state.teams["left"].players), 3)
        self.assertEqual(len(state.teams["right"].players), 3)
        self.assertEqual((state.ball.position.x, state.ball.position.y), (68.0, 34.0))
        self.assertIs(state.ball.status, BallStatus.LOOSE)
        self.assertIsNone(state.ball.owner)
        self.assertEqual([player.team_id for player in state.teams["right"].players], ["right"] * 3)

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

    def test_visualizer_coordinates_use_pitch_dimensions(self):
        pitch = {"width": 100, "height": 68}
        self.assertEqual(pitch_to_screen({"x": 50, "y": 34}, pitch), (540, 412))
        self.assertEqual(screen_to_pitch((540, 412), pitch), {"x": 50.0, "y": 34.0})
        self.assertEqual(screen_to_pitch((-100, 900), pitch), {"x": 0.0, "y": 68})

    def test_nearest_player_on_each_team_moves_toward_the_ball(self):
        simulation = SoccerSimulation({})
        before = {
            team_id: [player.position.x for player in team.players]
            for team_id, team in simulation.state.teams.items()
        }
        for _ in range(60):
            simulation.step(1 / 60)
        self.assertAlmostEqual(simulation.state.time, 1.0)
        for team_id, team in simulation.state.teams.items():
            self.assertGreater(team.players[1].position.x, before[team_id][1])
            self.assertEqual(team.players[0].position.x, before[team_id][0])
            self.assertEqual(team.players[2].position.x, before[team_id][2])
            self.assertLessEqual(team.players[1].velocity.magnitude(), team.players[1].max_speed)

    def test_movement_respects_acceleration_limit(self):
        simulation = SoccerSimulation({})
        player = simulation.state.teams["left"].players[1]
        simulation.step(0.1)
        self.assertAlmostEqual(player.velocity.magnitude(), player.acceleration * 0.1)
        with self.assertRaises(ValueError):
            simulation.step(0)

    def test_mutable_velocity_defaults_are_independent(self):
        first = Ball(position=Vec2(0, 0))
        second = Ball(position=Vec2(0, 0))
        first.status = BallStatus.CONTROLLED
        first.owner = ("left", 2)
        kick_ball(first, Vec2(1, 0), 5)
        update_ball(first, 0.5)
        self.assertEqual((first.position.x, first.position.y), (2.5, 0.0))
        self.assertEqual((second.velocity.x, second.velocity.y), (0.0, 0.0))
        self.assertIs(first.status, BallStatus.LOOSE)
        self.assertIsNone(first.owner)

    def test_render_state_is_plain_and_detached(self):
        simulation = SoccerSimulation({})
        rendered = to_render_state(simulation.state)
        rendered["teams"]["left"]["players"][0]["position"]["x"] = -10
        self.assertEqual(simulation.state.teams["left"].players[0].position.x, 35.0)
        self.assertEqual(rendered["ball"], {"x": 68.0, "y": 34.0})


if __name__ == "__main__":
    unittest.main()
