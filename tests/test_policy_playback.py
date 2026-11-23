"""Regression checks for interactive policy playback without a desktop window."""
import unittest

import numpy as np
import pygame

from model.environment import RondoEnv
from model.watch import PolicyPlayback
from simulation.objects import BallStatus
from simulation.vectors import Vec2
from simulation.visualizer import pitch_to_screen


class RecordingPolicy:
    def __init__(self):
        self.observations = []

    def predict(self, obs, deterministic=True):
        self.observations.append(obs.copy())
        return np.array([0.2, -0.1], dtype=np.float32), None


class PolicyPlaybackTests(unittest.TestCase):
    def setUp(self):
        self.env = RondoEnv()
        self.policy = RecordingPolicy()
        self.playback = PolicyPlayback(self.env, self.policy)
        self.addCleanup(self.env.close)

    def key(self, key):
        self.playback.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key))

    def test_pause_and_single_tick_keep_six_tick_decision_cadence(self):
        self.assertFalse(self.playback.running)
        self.key(pygame.K_SPACE)
        self.assertTrue(self.playback.running)
        self.key(pygame.K_SPACE)
        self.assertFalse(self.playback.running)
        for _ in range(6):
            self.key(pygame.K_RIGHT)
        self.assertEqual(self.playback.ticks, 6)
        self.assertEqual(len(self.policy.observations), 1)
        self.key(pygame.K_RIGHT)
        self.assertEqual(len(self.policy.observations), 2)
        self.assertAlmostEqual(self.playback.state.time, 7 / 60)

    def test_drag_releases_ball_and_invalidates_held_action(self):
        self.playback.tick()
        ball = self.playback.state.ball
        start = pitch_to_screen({'x': ball.position.x, 'y': ball.position.y},
                                self.playback.state.pitch, self.playback.goal_depth)
        target = pitch_to_screen({'x': 3, 'y': 4},
                                 self.playback.state.pitch, self.playback.goal_depth)
        self.playback.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=start))
        self.assertTrue(self.playback.dragging)
        before = self.playback.state.time
        self.playback.tick()
        self.assertEqual(self.playback.state.time, before)
        self.playback.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=target))
        self.playback.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONUP, button=1, pos=target))
        self.assertIsNone(ball.owner)
        self.assertEqual(ball.status, BallStatus.LOOSE)
        self.assertEqual(ball.velocity.magnitude(), 0)
        self.assertEqual(self.playback.ticks_left, 0)
        edited = [ball.position.x, ball.position.y, 0, 0]
        self.playback.tick()
        self.assertEqual(len(self.policy.observations), 2)
        np.testing.assert_allclose(self.policy.observations[-1][-4:], edited)

    def test_playback_matches_environment_for_same_actions(self):
        reference = RondoEnv()
        self.addCleanup(reference.close)
        reference.reset(seed=1000)
        for _ in range(3):
            for _ in range(6):
                self.playback.tick()
            expected, _, _, _, _ = reference.step(np.array([0.2, -0.1], dtype=np.float32))
            from model.observation import get_obs
            actual = get_obs(self.playback.state, self.env.player_key)
            np.testing.assert_allclose(actual, expected)
        self.assertEqual(self.playback.decisions, 3)

    def test_reset_clears_episode_and_held_command(self):
        self.playback.tick()
        self.key(pygame.K_r)
        self.assertEqual(self.playback.state.time, 0)
        self.assertEqual(self.playback.ticks_left, 0)
        self.assertEqual(self.playback.decisions, 0)
        self.assertFalse(self.playback.running)
        self.assertFalse(self.playback.finished)

    def test_possession_stops_playback_immediately(self):
        self.env.player.position = Vec2(2, 2)
        self.playback.state.ball.owner = self.env.player_key
        self.playback.state.ball.status = BallStatus.CONTROLLED
        self.playback.tick()
        self.assertTrue(self.playback.finished)
        self.assertEqual(self.playback.result, 'WIN')
        before = self.playback.state.time
        self.playback.tick()
        self.assertEqual(self.playback.state.time, before)
        self.key(pygame.K_r)
        self.assertFalse(self.playback.finished)


if __name__ == '__main__':
    unittest.main()
