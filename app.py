import csv
import io

import requests
from flask import Flask, request, jsonify, render_template, Response
from requests import get, RequestException
from mapping import *
import bs4
import json
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

PLAYER_STAT_TITLES = [
    "Games Played",
    "Goals",
    "Assists",
    "Points",
    "PIM",
    "Position"
]


@app.route('/player/stats-options')
def player_stat_options():
    """Return a list of player stat titles that can be selected."""
    return jsonify({"stats": PLAYER_STAT_TITLES})

@app.route('/')
def hello_world():  # put application's code here
    return 'Hello World!'


@app.route('/teams/<team_id>')
def team_stats(team_id):
    # Fetch the page content
    stats = get(f"https://www.nihlnational.com/team/{teamUrlMap[team_id]['url']}/team-stats?id_season=1")

    # Parse the HTML content
    soup = bs4.BeautifulSoup(stats.text, 'html.parser')
    stats_section = soup.find('section', {'id': 'main-section'})

    # Dictionary to store stats
    team_stats_dictionary = {"Name": teamUrlMap[team_id]["name"]}

    # Extract stats from the grid elements
    stats_grid = stats_section.find_all('div', class_='grid gap-1 text-center')
    for grid_item in stats_grid:
        value = grid_item.find('div', class_='text-[1.75rem] font-semibold leading-9').text.strip()
        label = grid_item.find('b', class_='text-sm text-cool-gray-500').text.strip()
        team_stats_dictionary[label] = value

    # Extract percentage stats (e.g., Powerplay, Penalty killing)
    percentage_stats = stats_section.find_all('div', class_='relative')
    for stat in percentage_stats:
        label = stat.find('div', class_='mb-4 text-base font-bold').text.strip()
        value = stat.find('div', class_='text-clamp56 font-bold').text.strip()
        additional_info_element = stat.find('div', class_='badge-secondary-disabled mx-auto mb-1 mt-6 w-max')
        additional_info = additional_info_element.text.strip() if additional_info_element else "N/A"  # Default to "N/A" if not found
        team_stats_dictionary[label] = {
            "success_percentage": value
        }

    # Print the structured stats (or return them in your route)
    print(team_stats_dictionary)
    return team_stats_dictionary


@app.route('/players/<team_id>/stats/<player_number>')
def single_player_stats(team_id, player_number):
    try:
        # Fetch the page content
        rows = fetch_players_page(team_id)

        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 9:  # Ensure there are enough columns
                continue

            current_player_number = cols[0].text.strip().lstrip("#")  # Remove '#' from the number
            if current_player_number == player_number:
                return {
                    "Player Number": current_player_number,
                    "First Name": cols[1].text.split()[0].strip(),
                    "Last Name": " ".join(cols[1].text.split()[1:]).strip(),
                    "Games Played": cols[3].text.strip(),
                    "Goals": cols[4].text.strip(),
                    "Assists": cols[5].text.strip(),
                    "Points": cols[6].text.strip(),
                    "PIM": cols[7].text.strip(),
                    "Logo": teamUrlMap[team_id]["logo"],
                    "header": "Season So Far",
                    "Position": cols[2].text.strip(),
                    "Color": teamUrlMap[team_id]["color"],
                    "Color-s": teamUrlMap[team_id]["color-s"],
                }

        return jsonify({"error": "Player not found."}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/teams/<team_id>/player-id/<player_number>')
def player_id_by_number(team_id, player_number):
    try:
        # Fetch the page content
        rows = fetch_players_page(team_id)

        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 2:  # Ensure there are enough columns
                continue

            current_player_number = cols[0].text.strip().lstrip("#")  # Remove '#' from the number
            if current_player_number == player_number:
                player_link = cols[1].find('a')
                if player_link:
                    href = player_link['href']
                    extracted_player_id = href.split('/')[2].split('-')[0]
                    first_name = cols[1].text.split()[0].strip()
                    last_name = " ".join(cols[1].text.split()[1:]).strip()
                    return jsonify({
                        "Player ID": extracted_player_id,
                        "Team ID": team_id,
                        "Player Number": player_number,
                        "First Name": first_name,
                        "Last Name": last_name
                    }), 200

        return jsonify({"error": "Player not found."}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/players/<team_id>/<player_number>')
def player_page(player_number, team_id):
    try:
        player_data = get(f"http://127.0.0.1:5000/teams/{team_id}/player-id/{player_number}")
        player_data = json.loads(player_data.text)

        url = f"https://www.nihlnational.com/player/{player_number}-{player_data['First Name'].lower()}-{player_data['Last Name'].lower()}"
        response = get(url)
        response.raise_for_status()

        player_id = player_data["Player ID"]

        soup = bs4.BeautifulSoup(response.text, 'html.parser')

        # Locate the stats section
        stats_section = soup.find('section', {'id': 'main-section'})
        if not stats_section:
            return jsonify({"error": "Unable to locate the stats section."}), 404

        # Extract basic player information
        player_info_section = soup.find('div', {'class': 'mb-7 flex flex-wrap items-center gap-8 max-sm:flex-col lg:px-8'})
        if not player_info_section:
            return jsonify({"error": "Unable to locate the player info section."}), 404

        player_info = {}
        details = player_info_section.find_all('li', {'class': 'grid gap-1'})
        for detail in details:
            key = detail.find('b').text.strip()
            value = detail.find('span').text.strip()
            player_info[key] = value

        # Locate all stats tables in the stats section
        tables = stats_section.find_all('table')
        if not tables:
            return jsonify({"error": "Unable to locate the stats tables."}), 404

        # Parse season stats
        season_stats_table = tables[0]
        season_stats = []
        for row in season_stats_table.find('tbody').find_all('tr'):
            cols = row.find_all('td')
            season_stats.append({
                "Season": cols[0].text.strip(),
                "League": cols[1].text.strip(),
                "Stage": cols[2].text.strip(),
                "Team": cols[3].text.strip(),
                "Games Played": cols[4].text.strip(),
                "Goals": cols[5].text.strip(),
                "Assists": cols[6].text.strip(),
                "Points": cols[7].text.strip(),
                "Penalty Minutes": cols[8].text.strip(),
                "Powerplay Goals": cols[9].text.strip(),
                "Shorthanded Goals": cols[10].text.strip()
            })

        # Parse last 5 matches stats
        last_matches_table = tables[1]
        last_matches_stats = []
        for row in last_matches_table.find('tbody').find_all('tr'):
            cols = row.find_all('td')
            last_matches_stats.append({
                "Date": cols[0].text.strip(),
                "Match": cols[1].text.strip(),
                "Goals": cols[2].text.strip(),
                "Assists": cols[3].text.strip(),
                "Points": cols[4].text.strip(),
                "Penalty Minutes": cols[5].text.strip(),
                "Powerplay Goals": cols[6].text.strip(),
                "Shorthanded Goals": cols[7].text.strip()
            })

        return jsonify({
            "Player ID": player_id,
            "Player Info": player_info,
            "Season Stats": season_stats,
            "Last 5 Matches Stats": last_matches_stats
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def fetch_players_page(team_id):
    url = f"https://www.nihlnational.com/team/{teamUrlMap[team_id]['url']}/player-stats?id_season=4"
    response = get(url)
    response.raise_for_status()

    # Parse the HTML content
    soup = bs4.BeautifulSoup(response.text, 'html.parser')

    stats_table = soup.find('table', {'class': 'styled align-middle'})
    if not stats_table:
        return jsonify({"error": "Unable to locate the stats table on the page."}), 404

    rows = stats_table.find('tbody').find_all('tr')

    return rows

@app.route('/game/<game_id>')
def game_page(game_id):
    fixtures_url = "https://s3-eu-west-1.amazonaws.com/nihl.hokejovyzapis.cz/league-matches/2025/1.json"
    home_team, guest_team = fetch_fixture_data(fixtures_url, game_id)

    home_team_id = name_to_id(home_team)
    guest_team_id = name_to_id(guest_team)


    return render_template('index.html',
                           game_id=game_id,
                           home_team=home_team,
                           guest_team=guest_team,
                           home_team_id=home_team_id,
                           guest_team_id=guest_team_id)

def fetch_fixture_data(fixtures_url, game_id):
    """Fetch fixture data to get home and guest team names."""
    try:
        response = get(fixtures_url)
        response.raise_for_status()
        data = response.json()
        for match in data['matches']:
            if match['id'] == int(game_id):
                return match['home']['name'], match['guest']['name']
    except RequestException as e:
        print(f"Error fetching fixture data: {e}")
    return None, None

def name_to_id(name):
    for team_id in teamUrlMap:
        if name == teamUrlMap[team_id]['name']:
            return team_id

    return None


@app.route('/rosters/<game_id>/<home_team>')
def get_players_on_roster(game_id, home_team):
    # Fetch the game info JSON
    game_info = get(
        f'https://s3-eu-west-1.amazonaws.com/nihl.hokejovyzapis.cz/matches/{game_id}/game-info.json')
    game_info = json.loads(game_info.text)

    players = []
    print(home_team)

    if home_team == "False":
        home_team = False
    elif home_team == "True":
        home_team = True



    if home_team:
        for player_id, player in game_info['roster']['home'].items():
            players.append({
                'name': f"{player['name']} {player['surname']}",
                'id': player_id,
                'number': player['jersey']  # Include the player's number
            })
    else:
        for player_id, player in game_info['roster']['visitor'].items():
            players.append({
                'name': f"{player['name']} {player['surname']}",
                'id': player_id,
                'number': player['jersey']  # Include the player's number
            })

    return players


@app.route('/is_home_team', methods=['GET'])
def is_home_team():
    # Get query parameters
    team_id = request.args.get('game_id')
    game_id = request.args.get('team_id')

    if not game_id or not team_id:
        return jsonify({"error": "Missing game_id or team_id"}), 400

    try:
        # Fetch the game info JSON
        game_info = requests.get(f'https://s3-eu-west-1.amazonaws.com/nihl.hokejovyzapis.cz/matches/{game_id}/game-info.json')
        game_info.raise_for_status()  # Ensure the request was successful
        game_data = game_info.json()

        # Check if the team is the home team
        home_team_id = str(game_data['gameInfo']['teamInfo']['home']['id'])
        print(home_team_id)
        print(team_id)
        if team_id == home_team_id:
            return jsonify({"is_home_team": True, "team_id": team_id, "game_id": game_id})
        else:
            return jsonify({"is_home_team": False, "team_id": team_id, "game_id": game_id})

    except requests.RequestException as e:
        return jsonify({"error": "Failed to fetch game data", "details": str(e)}), 500
    except KeyError as e:
        return jsonify({"error": "Unexpected data structure", "details": str(e)}), 500


def single_player_stats_game(game_id, team_id, player_number):
    team_stats = get(f'https://s3-eu-west-1.amazonaws.com/nihl.hokejovyzapis.cz/matches/{game_id}/team-stats/{team_id}.json')

    for player in team_stats.json():
        print(player)
        if int(player["jersey"]) == int(player_number):
            print("I got here")
            return {
                "First Name": player["firstname"],
                "Last Name": player["surname"],
                "Player Number": str(player["jersey"]),
                "Games Played": str(player["statistics"]["games"]),
                "Goals": str(player["statistics"]["goals"]["home"] + player["statistics"]["goals"]["away"]),
                "Assists": str(player["statistics"]["assists"]["home"] + player["statistics"]["assists"]["away"]),
                "Points": str(player["statistics"]["points"]["home"] + player["statistics"]["points"]["away"]),
                "PIM": str(player["statistics"]["penaltyMinutes"]),
                "Logo": teamUrlMap[team_id]['logo'],
                "header": "So Far This Game",
                "Color": teamUrlMap[team_id]["color"],
                "Color-s": teamUrlMap[team_id]["color-s"],
                "Position": player["position"],
            }

@app.route('/output/player', methods=['GET', 'POST'])
def output():
    if request.method == 'POST':
        output = io.StringIO()

        team_id = request.args.get('team_id')
        if team_id is None:
            return jsonify({"error": "Missing team_id"}), 400

        player_number = request.args.get('player_number')
        if player_number is None:
            return jsonify({"error": "Missing player_number"}), 400

        season_stats = request.args.get('season_stats')
        game_id = request.args.get('game_id')
        print(season_stats)
        print(game_id)
        if season_stats == 'true':
            player_stats = single_player_stats(team_id, player_number)
        else:
            player_stats = single_player_stats_game(game_id, team_id, player_number)
            print('Debug')


        print(player_stats)

        if player_stats is None:
            return jsonify({"error": "Unable to fetch player stats"}), 500

        selected_stats = request.args.getlist('stats')
        if selected_stats:
            base_fields = ["First Name", "Last Name", "Player Number"]
            filtered_stats = {}
            for key in base_fields:
                if key in player_stats:
                    filtered_stats[key] = player_stats[key]

            for stat in selected_stats:
                if stat in player_stats:
                    filtered_stats[stat] = player_stats[stat]

            if filtered_stats:
                player_stats = filtered_stats

        writer = csv.DictWriter(output, fieldnames=player_stats.keys())

        writer.writeheader()
        writer.writerow(player_stats)

        # Get CSV content
        csv_content = output.getvalue()
        output.close()
        file_path = "player_stats.csv"
        with open(file_path, "w", newline="") as file:
            file.write(csv_content)

        # Return as a response
        return Response(
            csv_content,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=player_stats.csv"}
        )
    else:
        file_path = "player_stats.csv"
        try:
            with open(file_path, "r") as file:
                csv_content = file.read()
        except FileNotFoundError:
            return Response("CSV file not found", status=404)

            # Return the CSV content as a response
        return Response(
            csv_content,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=player_stats.csv"}
        )



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
