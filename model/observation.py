# this file obtains the observations from the physics engine
#

from simulation.objects import GameState
import numpy as np

def get_obs(state: GameState, player: tuple[str, int]):
    '''
    creates the observation vector for the environment.
    starts with controlled player then teammates, then opponents
    each player contributes 5 (x,y,vx,vy,hasBall=0 if doesnt have the ball)
    then ball x,y,vx,vy
    '''

    team_id, player_id = player
    team = state.teams[team_id]
    observation = []

    chosen_player = next(
        (p for p in team.players if p.id == player_id),
        None,
    )

    if chosen_player is None:
        raise ValueError(f"Unknown Player Id: {player}")

    # add the controlled player to list
    observation.extend([
        chosen_player.position.x,
        chosen_player.position.y,
        chosen_player.velocity.x,
        chosen_player.velocity.y,
        float(
            (chosen_player.team_id, chosen_player.id) == state.ball.owner
        )
    ])

    for teammate in team.players:
        if teammate.id == player_id:
            continue
        else:
            observation.extend([
                teammate.position.x,
                teammate.position.y,
                teammate.velocity.x,
                teammate.velocity.y,
                float(
                    (teammate.team_id, teammate.id) == state.ball.owner
                )
            ])

    opponent_team = next(
        team
        for key, team in state.teams.items()
        if key != team_id
    )
    for opponent in opponent_team.players:
        observation.extend([
            opponent.position.x,
            opponent.position.y,
            opponent.velocity.x,
            opponent.velocity.y,
            float(
                (opponent.team_id, opponent.id) == state.ball.owner
            )
        ])

    observation.extend([
        state.ball.position.x,
        state.ball.position.y,
        state.ball.velocity.x,
        state.ball.velocity.y
    ])

    return np.array(observation, dtype=np.float32)


