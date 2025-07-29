import requests

def get_name(puuid, headers):
    url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-puuid/{puuid}"
    response = requests.get(url, headers=headers)
    assert response.status_code == 200
    return response.json()["gameName"]

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


def dataframe_to_google_chart(df):
    df = df[df["participantId"] == 1]
    data = df.to_dict(orient='records')
    keys = data[0].keys()
    output = {"cols": [{"id": "", "label": key, "value": "", "type": "number"} for key in keys],
              "rows": [{"c": [{"v": value, "f": None} for value in d.values()]} for d in data],
              }

    return output