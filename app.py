from flask import Flask, request, jsonify, send_from_directory
from pathlib import Path
import sqlite3
import requests
import os



# -------------------------------------------------------
# CONFIG
# -------------------------------------------------------

# RapidAPI ExerciseDB Configuration


API_KEY = "94036287bbmshc05edf9cf6a6ec2p176b6fjsn407584f48c59"

BASE_URL = "https://exercisedb.p.rapidapi.com"

HEADERS = {
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": "exercisedb.p.rapidapi.com"
}


ROOT = Path(__file__).parent
DB = ROOT / "fitness.db"

app = Flask(__name__, static_folder=str(ROOT), static_url_path="")


# -------------------------------------------------------
# FRONTEND
# -------------------------------------------------------



@app.route("/")
def home():
    return send_from_directory(ROOT, "index.html")


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(ROOT, path)


# -------------------------------------------------------
# DATABASE
# -------------------------------------------------------

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS workouts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exercise TEXT NOT NULL,
        muscle_group TEXT NOT NULL,
        date TEXT NOT NULL,
        sets INTEGER NOT NULL,
        reps INTEGER NOT NULL,
        weight REAL NOT NULL,
        notes TEXT
    )
    """)

    conn.commit()
    conn.close()


# -------------------------------------------------------
# MUSCLE GROUPS
# -------------------------------------------------------

GROUPS = [
    "Chest",
    "Back",
    "Shoulders",
    "Biceps",
    "Triceps",
    "Legs",
    "Core",
    "Cardio"
]




@app.route("/muscle-groups")
def muscle_groups():
    return jsonify(GROUPS)


# -------------------------------------------------------
# EXERCISE DB API
# -------------------------------------------------------

@app.route("/exercises")
def get_exercises():
    """Get first 100 exercises."""
    try:
        response = requests.get(
            f"{BASE_URL}/exercises?limit=100&offset=0",
            headers=HEADERS,
            timeout=15
        )
        response.raise_for_status()
        return jsonify(response.json())

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/exercise/search")
def search_exercise():
    """Search exercise by name."""
    name = request.args.get("name", "").strip()

    if not name:
        return jsonify([])

    try:
        response = requests.get(
            f"{BASE_URL}/exercises/name/{name}?limit=20",
            headers=HEADERS,
            timeout=15
        )
        response.raise_for_status()
        return jsonify(response.json())

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/exercise/bodypart")
def exercise_by_bodypart():
    """Filter exercises by body part."""
    body = request.args.get("bodyPart", "chest")

    try:
        response = requests.get(
            f"{BASE_URL}/exercises/bodyPart/{body}?limit=50",
            headers=HEADERS,
            timeout=15
        )
        response.raise_for_status()
        return jsonify(response.json())

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -------------------------------------------------------
# SAVE WORKOUT
# -------------------------------------------------------

@app.route("/workouts", methods=["POST"])
def add_workout():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Invalid JSON data"}), 400

    # Required fields (weight is optional)
    required = ["exercise", "muscle_group", "date", "sets", "reps"]

    for field in required:
        if field not in data or data[field] in ["", None]:
            return jsonify({"error": f"{field} is required"}), 400

    weight = float(data.get("weight_kg") or 0)

    conn = None
    try:
        conn = get_db()

        conn.execute("""
            INSERT INTO workouts (
                exercise,
                muscle_group,
                date,
                sets,
                reps,
                weight,
                notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            data["exercise"].strip(),
            data["muscle_group"],
            data["date"],
            int(data["sets"]),
            int(data["reps"]),
            weight,
            data.get("notes", "").strip()
        ))

        conn.commit()

        total_reps = int(data["sets"]) * int(data["reps"])

        return jsonify({
            "message": "Workout Saved",
            "total_reps": total_reps
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if conn:
            conn.close()

# -------------------------------------------------------
# GET WORKOUTS
# -------------------------------------------------------

@app.route("/workouts")
def workouts():

    group = request.args.get("muscle_group", "All")

    conn = get_db()

    if group == "All":
        rows = conn.execute(
            "SELECT * FROM workouts ORDER BY id DESC"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM workouts WHERE muscle_group=? ORDER BY id DESC",
            (group,)
        ).fetchall()

    conn.close()

    data = []

    for row in rows:
        data.append({
            "id": row["id"],
            "exercise": row["exercise"],
            "muscle_group": row["muscle_group"],
            "date": row["date"],
            "sets": row["sets"],
            "reps": row["reps"],
            "weight_kg": row["weight"],
            "notes": row["notes"],
            "total_reps": row["sets"] * row["reps"]
        })

    return jsonify(data)


# -------------------------------------------------------
# DELETE WORKOUT
# -------------------------------------------------------

@app.route("/workouts/<int:id>", methods=["DELETE"])
def delete_workout(id):

    conn = get_db()

    cursor = conn.execute(
        "DELETE FROM workouts WHERE id=?",
        (id,)
    )

    conn.commit()

    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"error": "Workout not found"}), 404

    conn.close()

    return jsonify({"deleted": id})

# -------------------------------------------------------
# STATS
# -------------------------------------------------------

@app.route("/stats")
def stats():

    conn = get_db()
    rows = conn.execute("SELECT * FROM workouts").fetchall()
    conn.close()

    total_entries = len(rows)
    total_reps = 0
    total_sets = 0
    sessions = set()
    volume_by_group = {}
    heaviest = None

    for row in rows:
        reps = row["sets"] * row["reps"]

        total_reps += reps
        total_sets += row["sets"]
        sessions.add(row["date"])

        group = row["muscle_group"]
        volume_by_group[group] = volume_by_group.get(group, 0) + reps

        if heaviest is None or row["weight"] > heaviest["weight"]:
            heaviest = row

    return jsonify({
        "total_entries": total_entries,
        "sessions": len(sessions),
        "week_sessions": len(sessions),

        # MAIN VALUES
        "total_reps": total_reps,
        "total_sets": total_sets,

        # CHART
        "volume_by_group": volume_by_group,

        # HEAVIEST LIFT
        "heaviest_lift": {
            "exercise": heaviest["exercise"],
            "weight_kg": heaviest["weight"]
        } if heaviest else None
    })

# -------------------------------------------------------
# BMI CALCULATOR
# -------------------------------------------------------

@app.route("/bmi", methods=["POST"])
def bmi():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    try:
        height = float(data["height_cm"]) / 100
        weight = float(data["weight_kg"])
    except (KeyError, ValueError):
        return jsonify({"error": "Enter valid height and weight"}), 400

    if height <= 0 or weight <= 0:
        return jsonify({"error": "Height and weight must be greater than zero"}), 400


    bmi = round(weight / (height ** 2), 1)

    if bmi < 18.5:
        category = "Underweight"
        advice = "Increase calories and protein."
    elif bmi < 25:
        category = "Healthy range"
        advice = "Great! Maintain your weight."
    elif bmi < 30:
        category = "Overweight"
        advice = "Slight calorie deficit and exercise."
    else:
        category = "Obese"
        advice = "Consult a doctor and follow a weight-loss plan."

    healthy_min = round(18.5 * (height ** 2), 1)
    healthy_max = round(24.9 * (height ** 2), 1)

    position = max(0, min(100, (bmi - 12) / 28 * 100))

    return jsonify({
        "bmi": bmi,
        "category": category,
        "advice": advice,
        "healthy_weight_kg": {
            "min": healthy_min,
            "max": healthy_max
        },
        "position_pct": position
    })


# -------------------------------------------------------
# BMI HISTORY (optional for JS)
# -------------------------------------------------------

@app.route("/bmi/history")
def bmi_history():
    return jsonify([])


# -------------------------------------------------------
# RUN APP
# -------------------------------------------------------

if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)