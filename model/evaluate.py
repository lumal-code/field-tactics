import numpy as np
from stable_baselines3 import PPO

from .environment import RondoEnv
from pathlib import Path

MODEL_PATH = Path(__file__).resolve().parents[1] / "rondo_defender.zip"

def main():
    env = RondoEnv()
    model = PPO.load(MODEL_PATH, device="cpu")

    rewards = []
    win_times = []
    episodes = 20

    for episode in range(episodes):
        obs, info = env.reset(seed=1000 + episode)
        total_reward = 0.0

        while True:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(action)
            total_reward += reward

            if terminated or truncated:
                break

        # In your environment, termination means winning possession.
        won = terminated
        rewards.append(total_reward)

        if won:
            win_times.append(info["time"])

        print(
            f"Episode {episode + 1}: "
            f"{'WIN' if won else 'TIMEOUT'}, "
            f"time={info['time']:.2f}s, "
            f"reward={total_reward:.2f}"
        )

    print(f"\nWin rate: {len(win_times) / episodes:.0%}")
    print(f"Average reward: {np.mean(rewards):.2f}")

    if win_times:
        print(f"Average time to win: {np.mean(win_times):.2f}s")

    env.close()


if __name__ == "__main__":
    main()
