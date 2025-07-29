import requests
import json
from datetime import datetime
import pandas as pd
from utils import *
import os
import secrets




with (open('champion.json', encoding="utf8") as f):
    d = json.load(f)
    keys = []
    champ_names = list(d["data"].keys())
    for champ in champ_names:
        champ_data = d["data"][champ]
        keys.append(champ_data["key"])

    champions = pd.DataFrame(data={"id": keys, "name": champ_names})

key =  os.getenv("LOL_API_KEY")
print(key)
match_ids = ["7455129765"]

match_ids = ['EUW1_' + m for m in match_ids]

headers = {
    "X-Riot-Token": key
}

game_type = ["MATCHED_GAME", "CUSTOM_GAME"]
puuid = get_puuid("Herr Grey#6781", headers)

games = get_games(puuid, headers)
print(games)

filtered_games = []
for match_id in games:

    url = f"https://europe.api.riotgames.com/lol/match/v5/matches/{match_id}"
    response = requests.get(url, headers=headers)
    data = response.json()

    if data["info"]["gameType"] == game_type[1]:
        filtered_games.append(data)

game_data = pd.DataFrame(columns = ["gameId", "Player", "Champion", "Position", "Side"])
summoner_data = pd.DataFrame(columns = ["Name", "puuid"])

ban_data = pd.DataFrame(columns = ["gameId", "Champion", "Order", "Side"])
frames_data = pd.DataFrame(columns = ["gameId", "frame", "puuid", "unspentGold", "magicDamageDone", "magicDamageDoneToChampions", "magicDamageTaken"])
for game in filtered_games[:1]:
    game_id = game["metadata"]["matchId"]
    keys = game["info"].keys()

    summoners = game["info"]["participants"]
    team_ids = [None, None]
    ban_inserts = {"gameId": [], "Champion": [] , "Order": [], "Side": []}
    for n, team in enumerate(game["info"]["teams"]):
        for turn, b in enumerate(team["bans"]):

            ban_inserts["gameId"].append(game_id)
            mask = champions.id ==  str(b["championId"])
            ban_inserts["Champion"].append(champions[mask].iloc[0, 1])
            ban_inserts["Order"].append(turn)
            ban_inserts["Side"].append("Blue" if n == 0 else "Red")

        n+=1

    ban_inserts = pd.DataFrame(ban_inserts)
    ban_data = pd.concat([ban_data, ban_inserts], ignore_index=True, axis = "rows")
    team_ids = [None, None]

    for player in summoners:
        if team_ids[0] is None:
            team_ids[0] = player["teamId"]
        elif team_ids[1] is None and player["teamId"] != team_ids[0]:
            team_ids[1] = player["teamId"]

        insert = {"gameId": game_id, "Player": player["puuid"], "Champion": player["championName"], "Position": player["teamPosition"], "Side": "Blue" if player["teamId"] == team_ids[0] else "Red"}
        game_data = pd.concat([game_data, pd.DataFrame(insert, index = [0])], ignore_index=True)
        insert = {"Name": player["riotIdGameName"], "puuid": player["puuid"]}
        summoner_data = pd.concat([summoner_data, pd.DataFrame(insert, index = [0])], ignore_index=True)


    url = f"https://europe.api.riotgames.com/lol/match/v5/matches/{game_id}/timeline"
    response = requests.get(url, headers=headers)
    timeline_data = response.json()
    participants_to_id = pd.DataFrame(timeline_data["info"]["participants"])
    print(participants_to_id)
    frame_data = timeline_data["info"]["frames"][0]["participantFrames"]["1"]
    remove_keys(frame_data, ["championStats" , "participantId"])
    for key, value in frame_data.items():
        print(key, value)


