from flask import Flask, render_template,jsonify, request, redirect, url_for, session, flash, make_response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import random
import json
import os

# --- App Initialization and Config ---
app = Flask(__name__)
app.secret_key = 'pancasila_cerdas_super_secret'
instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
os.makedirs(instance_path, exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(instance_path, 'scores.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Database and Login Manager Setup ---
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- Database Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    
    # --- ADD THIS LINE ---
    current_scene = db.Column(db.String(100), nullable=False, default='scene_1')
    # ---------------------

    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class ScoreEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.now())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('scores', lazy=True))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Load Questions ---
try:
    with open('questions.json', 'r', encoding='utf-8') as f:
        QUESTIONS = json.load(f)
except FileNotFoundError:
    QUESTIONS = []
    print("FATAL ERROR: questions.json not found! The quiz cannot run.")

@app.cli.command("init-db")
def init_db_command():
    """Clears existing data and creates new tables."""
    db.create_all()
    print("Initialized the database and created tables.")

# --- Application Routes ---
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('choose_mode'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('choose_mode'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Username sudah digunakan.', 'error')
            return redirect(url_for('register'))
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registrasi berhasil! Silakan login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('choose_mode'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('choose_mode'))
        else:
            flash('Username atau password salah.', 'error')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Kamu berhasil logout.', 'success')
    return redirect(url_for('login'))

@app.route('/choose-mode')
@login_required
def choose_mode():
    return render_template('choose_mode.html')

@app.route('/story-mode')
@login_required
def story_mode():
    return render_template('story_mode.html')

@app.route('/api/story/current')
@login_required
def get_current_scene():
    """
    Fetches the JSON data for the user's current scene.
    """
    scene_name = current_user.current_scene
    scene_filename = f"{scene_name}.json"
    
    # We expect scene files to be in /static/data/scenes/
    scene_path = os.path.join(app.static_folder, 'data', 'scenes', scene_filename)

    if not os.path.exists(scene_path):
        # If the scene file doesn't exist, it might mean the story is over.
        # Or, if scene_1 is missing, it's a server error.
        if scene_name == 'scene_1':
            return jsonify({"error": "FATAL: scene_1.json not found"}), 500
        else:
            # User has finished the last scene, and there is no next scene file.
            return jsonify({"story_complete": True})
            
    with open(scene_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return jsonify(data)


@app.route('/api/story/complete', methods=['POST'])
@login_required
def complete_scene():
    """
    Called by JS when a scene is finished. Updates the user's progress.
    """
    data = request.json
    next_scene_name = data.get('next_scene')

    if not next_scene_name:
        return jsonify({"error": "No 'next_scene' provided in request"}), 400

    # Get the user from the DB and update their scene
    user = User.query.get(current_user.id)
    user.current_scene = next_scene_name
    db.session.commit()
    
    return jsonify({"status": "success", "new_scene": next_scene_name})

# Ganti fungsi start_quiz yang lama dengan yang ini
@app.route('/start-endless')
@login_required
def start_quiz():
    # Menginisialisasi skor dan nyawa
    session.pop('score', None)
    session.pop('q_indices', None)
    session.pop('last_q_data', None)
    session['score'] = 0
    session['lives'] = 3  # Memberikan 3 kesempatan di awal
    
    question_indices = list(range(len(QUESTIONS)))
    random.shuffle(question_indices)
    session['q_indices'] = question_indices
    session['current_q_index'] = 0
    return redirect(url_for('ask_question'))

# Ganti fungsi ask_question yang lama dengan yang ini
@app.route('/question', methods=['GET', 'POST'])
@login_required
def ask_question():
    # Pastikan kuis sudah dimulai
    if 'q_indices' not in session or 'lives' not in session:
        return redirect(url_for('start_quiz'))

    current_q_index_pos = session.get('current_q_index', 0)
    # Jika pertanyaan habis, mulai dari awal lagi
    if current_q_index_pos >= len(session['q_indices']):
        random.shuffle(session['q_indices'])
        session['current_q_index'] = 0
        current_q_index_pos = 0

    question_index = session['q_indices'][current_q_index_pos]
    question_data = QUESTIONS[question_index]
    
    # --- PERBAIKAN UTAMA ADA DI SINI ---
    response = None # Variabel untuk menyimpan response

    if request.method == 'POST' and request.is_json:
        user_answer = request.json.get('option')
        correct_answer = question_data['answer']
        is_correct = (user_answer == correct_answer)

        # Jika waktu habis
        if not user_answer:
            user_answer = 'Waktu Habis'
            is_correct = False

        game_over = False
        if is_correct:
            session['score'] += 1
            session['current_q_index'] += 1
        else:
            session['lives'] -= 1
            if session['lives'] > 0:
                session['current_q_index'] += 1
            else:
                game_over = True

        lives = session.get("lives", 3)
        max_lives = 3   

        current_question = QUESTIONS[question_index]
        user_answer = request.json.get("option")
        correct = (user_answer == current_question["answer"])

        # Cek bonus
        bonus = current_question.get("bonus_health", 0)
        bonus_given = False

        if correct and bonus > 0 and lives < max_lives:
            lives += bonus
            if lives > max_lives:
                lives = max_lives
            bonus_given = True

        session["lives"] = lives

        
        # Buat response untuk dikirim
        return jsonify({
            "correct": correct,
            "user_answer": user_answer,
            "correct_answer": current_question["answer"],
            "explanation": current_question["explanation"],
            "lives": lives,
            "max_lives": max_lives,
            "bonus_given": bonus_given,
            "game_over": game_over
        })
            
    else: # Method GET
        question_num = session.get('score', 0) + 1
        # Buat response untuk dikirim
        response = make_response(render_template('question.html',
                                                 question=question_data,
                                                 show_answer=False,
                                                 question_num=question_num,
                                                 lives=session.get('lives', 3))) # Kirim 'lives'

    # Tambahkan header anti-cache ke response
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response
@app.route('/results')
@login_required
def results():
    score = session.get('score', 0)
    if score > 0:
        db.session.add(ScoreEntry(username=current_user.username, score=score, user_id=current_user.id))
        db.session.commit()
    top_scores_query = db.session.query(ScoreEntry.username, func.max(ScoreEntry.score).label("max_score")).group_by(ScoreEntry.username).order_by(func.max(ScoreEntry.score).desc()).limit(10).all()
    top_scores = [{'username': s.username, 'score': s.max_score} for s in top_scores_query]
    session.pop('score', None); session.pop('q_indices', None); session.pop('current_q_index', None)
    return render_template('results.html', username=current_user.username, score=score, top_scores=top_scores)

@app.route('/api/story/progress', methods=['POST'])
@login_required
def save_story_progress():
    """
    Menyimpan posisi event terakhir yang sudah dicapai user di story mode.
    """
    data = request.json
    current_scene = data.get('scene_id')
    current_event_index = data.get('event_index')

    if not current_scene or current_event_index is None:
        return jsonify({"error": "Incomplete data"}), 400

    # Simpan ke session
    session['story_progress'] = {
        "scene": current_scene,
        "event_index": current_event_index
    }

    return jsonify({"status": "progress_saved"})

@app.route("/api/answer-record", methods=["POST"])
def record_answer():
    data = request.get_json()
    path = "static/data/answer_records.json"

    # Pastikan file ada
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump([], f)

    with open(path, "r") as f:
        records = json.load(f)

    records.append(data)

    with open(path, "w") as f:
        json.dump(records, f, indent=2)

    return jsonify({"status": "ok"})

@app.route("/api/next-question")
def api_next_question():
    questions = session.get("questions", [])
    index = session.get("question_index", 0)
    lives = session.get("lives", 3)
    max_lives = 3

    # pindah ke soal berikutnya
    index += 1
    session["question_index"] = index

    # kalau habis
    if index >= len(questions):
        return jsonify({
            "game_over": True
        })

    q = questions[index]

    return jsonify({
        "game_over": False,
        "question_num": index + 1,
        "question": q["question"],
        "options": q["options"],
        "lives": lives,
        "max_lives": max_lives
    })



@app.route("/api/stats")
def api_stats():
    file_path = os.path.join("static", "data", "answer_records.json")

    # Pastikan file ada
    if not os.path.exists(file_path):
        print("File tidak ditemukan:", file_path)
        return jsonify([])

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            records = json.load(f)
    except Exception as e:
        print("Gagal membaca file:", e)
        return jsonify([])

    # Hitung soal yang paling banyak salah
    wrong_stats = {}
    for r in records:
        if not r.get("is_correct", True):  # ambil hanya jawaban salah
            q = r.get("question_text", "Tanpa teks soal")
            wrong_stats[q] = wrong_stats.get(q, 0) + 1

    result = [
        {"question_text": q, "wrong_count": c}
        for q, c in sorted(wrong_stats.items(), key=lambda x: x[1], reverse=True)
    ]

    return jsonify(result)


@app.route("/stats")
def stats_page():
    return render_template("stats.html")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

