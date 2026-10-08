import random
import uuid
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Allows cross-origin requests from your main frontend

# Mock database of teams per league
LEAGUE_TEAMS = {
    "Premier League": {
        "sport_key": "soccer",
        "teams": [
            "Arsenal",
            "Man City",
            "Liverpool",
            "Chelsea",
            "Man United",
            "Tottenham",
            "Aston Villa",
            "Newcastle",
        ],
    },
    "La Liga": {
        "sport_key": "soccer",
        "teams": [
            "Real Madrid",
            "Barcelona",
            "Atletico Madrid",
            "Sevilla",
            "Real Sociedad",
            "Villarreal",
        ],
    },
    "UEFA Champions League": {
        "sport_key": "soccer",
        "teams": [
            "Bayern Munich",
            "PSG",
            "Real Madrid",
            "Inter Milan",
            "Borussia Dortmund",
            "Arsenal",
        ],
    },
    "NBA": {
        "sport_key": "basketball",
        "teams": [
            "LA Lakers",
            "Boston Celtics",
            "Golden State Warriors",
            "Chicago Bulls",
            "Miami Heat",
            "Denver Nuggets",
        ],
    },
    "ATP Tennis": {
        "sport_key": "tennis",
        "teams": [
            "Novak Djokovic",
            "Carlos Alcaraz",
            "Jannik Sinner",
            "Daniil Medvedev",
            "Alexander Zverev",
        ],
    },
    "eFootball League": {
        "sport_key": "efootball",
        "teams": [
            "e-FC Barcelona",
            "e-Bayern",
            "e-Man United",
            "e-Arsenal",
            "e-Inter",
        ],
    },
}


def generate_mock_matches(requested_sport=None, count=100):
  matches = []
  now = datetime.now()

  for _ in range(count):
    # Select random league or filter by query
    league_name, data = random.choice(list(LEAGUE_TEAMS.items()))
    sport = data["sport_key"]

    if requested_sport and requested_sport != "all":
      if requested_sport.lower() not in [sport, league_name.lower()]:
        # Keep picking if sport requested doesn't match
        continue

    teams = data["teams"].copy()
    home = random.choice(teams)
    teams.remove(home)
    away = random.choice(teams)

    # Random commencement time (between today and 3 days from now)
    future_hours = random.randint(1, 72)
    match_dt = now + timedelta(hours=future_hours)

    match_date_str = match_dt.strftime("%d %b")  # e.g. "29 Sep"
    start_time_str = match_dt.strftime("%H:%M")  # e.g. "19:30"

    # Odds generation
    home_odds = round(random.uniform(1.30, 4.50), 2)
    draw_odds = (
        round(random.uniform(3.00, 4.20), 2) if sport == "soccer" else 1.00
    )
    away_odds = round(random.uniform(1.40, 5.00), 2)

    matches.append({
        "id": str(uuid.uuid4())[:8],
        "home_team": home,
        "away_team": away,
        "sport": sport,
        "league_name": league_name,
        "is_live": random.choice([True, False]),
        "match_date": match_date_str,
        "start_time": start_time_str,
        "score": "0 - 0",
        "home_odds": home_odds,
        "draw_odds": draw_odds,
        "away_odds": away_odds,
    })

  return matches


@app.route("/api/matches", methods=["GET"])
def get_mock_matches():
  sport = request.args.get("sport", "all").lower()
  matches = generate_mock_matches(requested_sport=sport, count=50)
  return jsonify({"success": True, "matches": matches})


if __name__ == "__main__":
  # Runs on port 8080 to avoid collision with 5000 and 55000
  print("🚀 Mock Odds Server running on http://127.0.0.1:8080/api/matches")
  app.run(host="0.0.0.0", port=8080, debug=True)