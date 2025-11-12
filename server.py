from flask import Flask, jsonify, request, session
from flask_cors import CORS
import json, os

app = Flask(__name__)
app.secret_key = "supersecret"

# Izinkan session cookies di frontend (penting)
CORS(app, supports_credentials=True)

# Folder semua scene
SCENE_FOLDER = os.path.join("static", "data", "scenes")

# ------------------------------
# 1. Ambil scene aktif
# ------------------------------
@app.route("/api/story/current")
def get_story():
    progress = session.get("story_progress")
    scene_id = progress["scene"] if progress and progress.get("scene") else "scene_1"
    scene_file = os.path.join(SCENE_FOLDER, f"{scene_id}.json")

    if not os.path.exists(scene_file):
        return jsonify({"error": f"Scene file {scene_file} not found."}), 404

    with open(scene_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Tambahkan progress posisi event
    data["resume_event"] = progress.get("event_index", 0) if progress else 0
    return jsonify(data)

# ------------------------------
# 2. Simpan progres pemain
# ------------------------------
@app.route("/save-progress", methods=["POST"])
def save_progress():
    data = request.get_json()
    session["story_progress"] = {
        "scene": data.get("scene"),
        "event_index": data.get("event_index", 0)
    }
    print("✅ Progress saved:", session["story_progress"])
    return jsonify({"status": "saved"})

# ------------------------------
# 3. Ambil progres dari session
# ------------------------------
@app.route("/session-data")
def session_data():
    print("📦 Session now:", session.get("story_progress"))
    return jsonify({"story_progress": session.get("story_progress")})

# ------------------------------
# 4. Scene selesai -> lanjut ke scene berikut
# ------------------------------
@app.route("/api/story/complete", methods=["POST"])
def complete_scene():
    data = request.get_json()
    session["story_progress"] = {
        "scene": data.get("next_scene"),
        "event_index": 0
    }
    print("➡️ Scene complete, next:", data.get("next_scene"))
    return jsonify({"status": "success"})

if __name__ == "__main__":
    app.run(debug=True)
