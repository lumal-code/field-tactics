from typing import Optional
import numpy as np
import gymnasium as gym
from .observation import get_obs
from simulation.engine import SoccerSimulation
from simulation.vectors import Vec2

class RondoEnv(gym.Env):
    def __init__(self, config=None, player_key=("defender", 3)):
        super().__init__()

        self.config = dict(config or {})
        self.player_key = player_key
        self.sim = None

        # Four players × five features, plus four ball features.
        self.observation_space = gym.spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(24,),
            dtype=np.float32,
        )

        # Direction x, direction y, and a normalized speed command.
        self.action_space = gym.spaces.Box(
            low=-1.0,
            high=1.0,
            shape=(2,),
            dtype=np.float32,
        )

    def _get_info(self):
        '''Compute auxiliary information for debugging.

        Returns:
            dict: info with current time or something

        '''

        return {
            'time': 0
        }
    
    def reset(self, *, seed=None, options=None):
        """Start a new episode.

        Args:
            seed: Random seed for reproducible episodes
            options: Additional configuration (unused in this example)

        Returns:
            tuple: (observation, info) for the initial state
        """
        # IMPORTANT: Must call this first to seed the random number generator
        super().reset(seed=seed)

        episode_config = dict(self.config)
        episode_config["seed"] = int(
            self.np_random.integers(0, 2**32)
        )

        self.sim = SoccerSimulation(episode_config)

        observation = get_obs(self.sim.state, self.player_key)
        info = {"time": self.sim.state.time}

        return observation, info

    def step(self, action):
        """Execute one timestep within the environment.

        Args:
            action: The action to take (vx, vy)

        Returns:
            tuple: (observation, reward, terminated, truncated, info)
        """
        velocity = Vec2(action[0], action[1])
        reward = 0
        terminated = False  
        truncated = False
        # run 6 physics ticks
        for _ in range(6):
            self.sim.step(ignore_player=self.player_key, desired_velocity=velocity)
        
        observation = get_obs(self.state)
        
        return observation, reward, terminated, truncated, info

        
