import pandas as pd


def calc_diff(frame_df: pd.DataFrame, player_df: pd.DataFrame):
    print(player_df)
    player_join = frame_df.merge(player_df, how="left", left_on=['participantId', 'gameId'], right_on=['name', 'gameId']).reset_index()

    matchup_join = player_join.merge(player_join, how="inner", on=['Position', 'gameId', 'frameId'], suffixes= ("", "_2")).reset_index()
    matchup_join = matchup_join[matchup_join["name"] != matchup_join["name_2"]]
    #print(matchup_join[["name", "Champion", "Champion_2", "name_2", "frameId"]])

    matchup_join["gold_difference"] = matchup_join['totalGold'] - matchup_join['totalGold_2']
    matchup_join["effective_gold"] = matchup_join['totalGold'] - matchup_join['currentGold']
    matchup_join["xp_per_minute"] = (matchup_join["xp"] / matchup_join["frameId"]).fillna(0)
    matchup_join["xp_difference"] = matchup_join['xp'] - matchup_join['xp_2']

    return matchup_join[["name", "Champion", "gold_difference", "effective_gold", "xp_difference", "xp_per_minute", "gameId", "frameId"]]