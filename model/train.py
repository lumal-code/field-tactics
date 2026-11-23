import gymnasium as gym
from stable_baselines3 import PPO
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.monitor import Monitor

from .environment import RondoEnv

def main():
# Check that observations, actions, and return values fit SB3.
    check_env(RondoEnv())

    # Monitor records episode rewards and lengths.
    env = Monitor(RondoEnv())

    model = PPO(
        "MlpPolicy",
        env,
        verbose=1,
        device="cpu",
        seed=42,
    )

    model.learn(total_timesteps=10_000)
    model.save("rondo_defender")

    env.close()

if __name__ == '__main__':
    main()
