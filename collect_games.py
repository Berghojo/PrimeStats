from utils import *
import os
import pandas as pd
import json
from collections import namedtuple, defaultdict
GAME_TYPES = ["MATCHED_GAME", "CUSTOM_GAME"]


with (open('champion.json', encoding="utf8") as f):
    d = json.load(f)
    keys = []
    champ_names = list(d["data"].keys())
    for champ in champ_names:
        champ_data = d["data"][champ]
        keys.append(champ_data["key"])

    champions = pd.DataFrame(data={"id": keys, "name": champ_names})


def get_by_name(riotname, max_tries=10, n_games=2):
    headers = {
        "X-Riot-Token": os.getenv("LOL_API_KEY")
    }
    puuid = get_puuid(riotname, headers)
    start_id = 0
    filtered_games = []
    while len(filtered_games) < n_games and (start_id // 10) < max_tries:

        game_data = get_games(puuid, headers, start_id)
        games = filter_games_by(game_data, headers)

        start_id += 10
        if games:
            filtered_games += games

    game_obj = namedtuple("Game", ["blue", "blue_players", "ban_blue", "ban_red", "red_players", "red", "gameId"])
    game_list = {}


    if filtered_games:
        ban_data, summoner_data, game_data = get_game_data(filtered_games)
        for game in filtered_games:

            blue_picks = {"TOP": None,
                         "JUNGLE": None,
                         "MIDDLE": None,
                         "BOTTOM": None,
                         "UTILITY": None}
            red_picks = {"TOP": None,
                         "JUNGLE": None,
                         "MIDDLE": None,
                         "BOTTOM": None,
                         "UTILITY": None}
            game_id = game["metadata"]["matchId"]
            bans = ban_data[ban_data["gameId"] == game_id].sort_values(by =["Order"])
            blue_bans = bans[ban_data["Side"] == "Blue"]["Champion"].to_list()
            red_bans = bans[ban_data["Side"] == "Red"]["Champion"].to_list()

            for index, player in game_data[game_data["gameId"] == game_id].reset_index().iterrows():
                pick_dict = blue_picks if player.Side == "Blue" else red_picks
                name = summoner_data[summoner_data["puuid"] == player.Player]["Name"].iloc[0]
                pick_dict[player["Position"]] = (player.Champion, name)
            blue_champs, blue_players = zip(*blue_picks.values())
            red_champs, red_players = zip(*red_picks.values())

            game_list[game_id] = game_obj(blue_champs, blue_players, blue_bans, red_bans, red_players, red_champs, game_id)
    return game_list, games


def get_game_stats(game_list):
    headers = {
        "X-Riot-Token": os.getenv("LOL_API_KEY")
    }

    frames = []
    for gameId in game_list:
        print("gameId:", gameId)
        url = f"https://europe.api.riotgames.com/lol/match/v5/matches/{gameId}/timeline"
        response = requests.get(url, headers=headers)
        timeline_data = response.json()
        participants_to_id = pd.DataFrame(timeline_data["info"]["participants"])
        url = f"https://europe.api.riotgames.com/lol/match/v5/matches/{gameId}"
        response = requests.get(url, headers=headers)
        game_data = response.json()
        summoners = game_data["info"]["participants"]
        puuid_to_name = []
        for player in summoners:
            puuid_to_name.append({"name": player["riotIdGameName"], "puuid": player["puuid"]})
        puuid_to_name = pd.DataFrame(puuid_to_name)


        for time_stamp, frame in enumerate(timeline_data["info"]["frames"]):
            for participant_id in range(10):
                frame_data = frame["participantFrames"][str(participant_id+1)]
                for key, value in frame_data["damageStats"].items():
                    frame_data[key] = value
                frame_data["position"] = (frame_data["position"]["x"], frame_data["position"]["y"])
                frame_data["frameId"] = time_stamp

                puuid = participants_to_id[participants_to_id["participantId"] == participant_id+1].iloc[0][1]
                name = puuid_to_name[puuid_to_name["puuid"] == puuid]["name"].iloc[0]
                frame_data["participantId"] = name
                remove_keys(frame_data, ["championStats", "damageStats", "position"])
                frames.append(frame_data)
    frame_df = pd.DataFrame(frames)
    avg_df = frame_df.groupby(by = ["frameId", "participantId"]).mean().reset_index()



    return avg_df



def get_game_data(filtered_games):
    game_data = pd.DataFrame(columns=["gameId", "Player", "Champion", "Position", "Side"])
    summoner_data = pd.DataFrame(columns=["Name", "puuid"])
    ban_data = pd.DataFrame(columns=["gameId", "Champion", "Order", "Side"])
    for game in filtered_games:
        game_id = game["metadata"]["matchId"]
        summoners = game["info"]["participants"]
        ban_inserts = get_bans(game, game_id)
        ban_inserts = pd.DataFrame(ban_inserts)
        ban_data = pd.concat([ban_data, ban_inserts], ignore_index=True, axis="rows")
        team_ids = [None, None]

        for player in summoners:
            if team_ids[0] is None:
                team_ids[0] = player["teamId"]
            elif team_ids[1] is None and player["teamId"] != team_ids[0]:
                team_ids[1] = player["teamId"]

            insert = {"gameId": game_id, "Player": player["puuid"], "Champion": player["championName"],
                      "Position": player["teamPosition"], "Side": "Blue" if player["teamId"] == team_ids[0] else "Red"}
            game_data = pd.concat([game_data, pd.DataFrame(insert, index=[0])], ignore_index=True)
            insert = {"Name": player["riotIdGameName"], "puuid": player["puuid"]}
            summoner_data = pd.concat([summoner_data, pd.DataFrame(insert, index=[0])], ignore_index=True)

    return ban_data, summoner_data.drop_duplicates(), game_data


def get_bans(game, game_id):
    ban_inserts = {"gameId": [], "Champion": [], "Order": [], "Side": []}
    for n, team in enumerate(game["info"]["teams"]):
        for turn, b in enumerate(team["bans"]):
            ban_inserts["gameId"].append(game_id)
            mask = champions.id == str(b["championId"])
            ban_inserts["Champion"].append(champions[mask].iloc[0, 1])
            ban_inserts["Order"].append(turn)
            ban_inserts["Side"].append("Blue" if n == 0 else "Red")

        n += 1
    return ban_inserts


def filter_games_by(games, headers):
    filtered_games = []
    for match_id in games:
        url = f"https://europe.api.riotgames.com/lol/match/v5/matches/{match_id}"
        response = requests.get(url, headers=headers)
        data = response.json()
        #if data["info"]["gameType"] == GAME_TYPES[0]:
        filtered_games.append(data)
    return filtered_games
