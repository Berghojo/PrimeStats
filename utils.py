import pandas as pd
import requests

def get_name(puuid, headers):
    url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-puuid/{puuid}"
    response = requests.get(url, headers=headers)
    assert response.status_code == 200
    return response.json()["gameName"]


def increcment_dict(dict, key):
    if key not in dict:
        dict[key] = 1
    else:
        dict[key]+=1
    


def show_event_types(events):
    event_types = set()

    for e in events:
        for e2 in e:
            event_types.add(e2["type"])
            if e2["type"] == "ELITE_MONSTER_KILL":
                print(e2)
    print(event_types)

def get_puuid(ign, headers):
    try:
        assert "#" in ign
        name, tag = ign.split("#")
        url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{name}/{tag}"
        response = requests.get(url, headers=headers)
        assert response.status_code == 200

        return response.json()["puuid"]
    except AssertionError:
        print("IGN not found")

def get_games(puuid, headers, start, n_per_request=10):
    print(f"Getting {n_per_request} games")
    url = f"https://europe.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start={start}&count={n_per_request}&type=tourney"

    response = requests.get(url, headers=headers)

    data = response.json()
    print(response.status_code)
    assert response.status_code == 200
    return data

def remove_keys(d, keys):
    for key in keys:
        del d[key]


def dataframe_to_google_chart(df: pd.DataFrame):
    # df = df[df["participantId"]
    #         == 1]

    df = df.fillna(method='ffill')
    names = list(pd.unique(df["participantId"]))
    data = df.to_dict(orient='records')
    keys = list(data[0].keys())
    
    outputRaw = {}
    max_len = df["frameId"].max()
    for name in names:
        player_frames = df[df["participantId"] == name].sort_values(by="frameId").copy().reset_index().reindex(range(max_len+1), method='ffill')
        outputRaw[name] = player_frames.to_dict(orient='records')
    output = {}

    for key in keys:
        output[key] = {"cols": [{"id": "", "label": "timestamp", "value": "", "type": "number"}
                                ] + [{"id": "", "label": name, "value": "", "type": "number"} for name in outputRaw.keys()],
              "rows": [{"c": [{"v": i, "f": None}] +
              [{"v": outputRaw[name][i][key], "f": None} for name in names] } for i in range(max_len+1)],
                       }

    return output