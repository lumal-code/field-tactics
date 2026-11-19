import gymnasium as gym

env = gym.make('CartPole-v1', render_mode='human')

observation, info = env.reset()

print(f"Starting observation: {observation}")

episode_over = False
total_reward = 0

while not episode_over:
    action = env.action_space.sample()

    observation, reward, terminated, truncated, info = env.step(action)

    total_reward += reward

    if truncated:
        print('truncated')

    episode_over = terminated or truncated

print(f"episode over. total reward: {total_reward}")
env.close()
