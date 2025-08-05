from utils import *
import os
import pandas as pd
import json
import urllib.request, json 
from collections import namedtuple, defaultdict
from stat_calc import *

GAME_TYPES = ["MATCHED_GAME", "CUSTOM_GAME"]
IRRELEVANT_STATS =  []



with (open('champion.json', encoding="utf8") as f):
    d = json.load(f)
    keys = []
    champ_names = list(d["data"].keys())
    for champ in champ_names:
        champ_data = d["data"][champ]
        keys.append(champ_data["key"])

    champions = pd.DataFrame(data={"id": keys, "name": champ_names})


def get_by_name(riotname, max_tries=10, n_games=20):
    headers = {
        "X-Riot-Token": os.getenv("LOL_API_KEY")
    }
    puuid = get_puuid(riotname, headers)
    start_id = 0
    filtered_games = []
    while len(filtered_games) < n_games and (start_id // 10) < max_tries:

        game_data = get_games(puuid, headers, start_id, n_per_request=100
                              )
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
   
    player_data = []

    greater = lambda x, y:  x > y
    smaller_eq = lambda x, y:  x <= y

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
            player_data.append({"name": player["riotIdGameName"], "Champion": player["championName"], "Position": player["teamPosition"], "puuid": player["puuid"], "gameId": gameId})
        puuid_to_name = pd.DataFrame(puuid_to_name)
        events = []
        player_kda = [{"kills": 0, 
                       "deaths": 0,
                        "assists": 0
                        }.copy() for _ in range(10)]
        blue_objectives = {
            "Grubs": 0,
            "Herald": 0,
            "Dragon": 0,
            "Atakhan":0,
            "Baron": 0
            }
        blue_kills = 0
        red_kills = 0
        red_objectives = blue_objectives.copy()
        player_solo_kills = [0 for i in range(10)]
        for time_stamp, frame in enumerate(timeline_data["info"]["frames"]):
            event_data = frame["events"]
            objective_participation = {
            "Grubs": [],
            "Herald": [],
            "Dragon": [],
            "Atakhan":[],
            "Baron": []
            }
            for e in event_data:
                if e["type"] == "ELITE_MONSTER_KILL":
                    killer = e['killerId']
                    side_select = smaller_eq if killer <= 5 else greater
                    if 'assistingParticipantIds' in e:
                        assists = [participant for participant in e['assistingParticipantIds'] if side_select(participant,  5)] 
                    else:
                        assists = []
                    assists.append(killer)
                    objectives = blue_objectives if killer <= 5 else red_objectives
        
                    match e["monsterType"]:
                        case "RIFTHERALD":
                            monsterType = "Herald"
                        case "ATAKHAN":
                            monsterType = "Atakhan"
                        case "HORDE":
                            monsterType = "Grubs"
                        case "BARON_NASHOR":
                            monsterType = "Baron"
                        case "DRAGON":
                            monsterType = "Dragon"
                        case _:
                            raise Exception(f"Unknown Monstertype {e["monsterType"]}")

                    objectives[monsterType] += 1
                   
                    objective_participation[monsterType] = assists

                elif e["type"] == "CHAMPION_KILL":
                    if e['killerId'] < 6:
                        blue_kills += 1
                    else:
                        red_kills += 1
                    killer = e['killerId']
                    if 'assistingParticipantIds' in e:
                        assists = [participant for participant in e['assistingParticipantIds']] 
                    else:
                        assists = []
                    died = e['victimId']
                    for player in assists:
                        player_kda[player-1]["assists"] += 1
                    if not assists:
                        player_solo_kills[killer-1] += 1
                    player_kda[killer-1]["kills"] += 1
                    player_kda[died-1]["deaths"] += 1
                    
                if e["type"] == "ELITE_MONSTER_KILL":
                    pass

            for participant_id in range(10):
                frame_data = frame["participantFrames"][str(participant_id+1)]
                frame_data["side"] = "Blue" if participant_id < 5 else "Red"
                puuid = participants_to_id[participants_to_id["participantId"] == participant_id+1].iloc[0][1]
                name = puuid_to_name[puuid_to_name["puuid"] == puuid]["name"].iloc[0]
                frame_data["participantId"] = name
               
                for key, value in frame_data["damageStats"].items():
                    frame_data[key] = value

                for key, value in player_kda[participant_id].items():
                    frame_data[key] = value
                all_kills = blue_kills if participant_id < 5 else red_kills
                frame_data["kill_participation"] = (player_kda[participant_id]["kills"] + player_kda[participant_id]["assists"]) / all_kills if all_kills > 0 else 1
                objectives = blue_objectives if participant_id <= 5 else red_objectives

                for key, value in objectives.items():
                    # if name == "Miso Tasty" and objective_participation[key]:
                    #     print(participant_id, objective_participation[key], key)
                    if participant_id+1 in objective_participation[key]:
                        frame_data[key] = 1
                    else:
                        frame_data[key] = 0
                        
                    

                frame_data["solo_kills"] = player_solo_kills[participant_id]
                
                frame_data["position"] = (frame_data["position"]["x"], frame_data["position"]["y"])
                frame_data["frameId"] = time_stamp
                frame_data["gameId"] = gameId
                
                remove_keys(frame_data, ["championStats", "damageStats", "position"])
                frames.append(frame_data)
            events.append(event_data)
    #show_event_types(events)
    
    frame_df = pd.DataFrame(frames)
    frame_df = frame_df.ffill()
    player_df= pd.DataFrame(player_data)
    diff_df = calc_diff(frame_df, player_df)

    frame_df = frame_df.merge(diff_df, how="left", left_on=['participantId', 'gameId', "frameId"], right_on=['name', 'gameId', "frameId"]).reset_index(drop=True).drop_duplicates(inplace=False)
    columns = ["kills", "deaths", "assists", "frameId", "participantId", "gameId"]
    
    #print(frame_df[(frame_df["participantId"] == "ECF FeRY") & (frame_df["frameId"] == 8)][columns])
    kda_view = frame_df.groupby(by = ["frameId", "participantId"])[["kills", "deaths", "assists"]].sum().reset_index()
  
   # print(kda_view[kda_view["participantId"] == "Ecf FeRY"])
    deaths = kda_view["deaths"]
    deaths[deaths == 0] = -1
    kda = (kda_view["kills"] + kda_view["assists"]) / deaths
    kda = kda.fillna(-1)
    avg_df = frame_df.groupby(by = ["frameId", "participantId"]).mean(numeric_only=True).reset_index()

    avg_df = avg_df.drop(IRRELEVANT_STATS, axis=1)
    avg_df.insert(2, "kda", kda)
    avg_df = avg_df.reset_index(drop=True)
    print(avg_df.head())
    return avg_df, player_df.drop_duplicates(subset=["name", "Position", "puuid"])

def add_to_players(frame, e, key):
    participants = (e['assistingParticipantIds'] + [e['killerId']]) if 'assistingParticipantIds' in e else [e['killerId']]
    for p in participants:
        if (p-1) // 5 == (e['killerId']-1) // 5:
             increcment_dict(frame["participantFrames"][str(p)], key)



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
