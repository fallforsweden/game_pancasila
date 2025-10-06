from flask import Flask, render_template, request, redirect, url_for, session, flash
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
    # --- PERUBAHAN DI SINI ---
    # Jika pengguna sudah login, langsung arahkan ke pilihan mode.
    if current_user.is_authenticated:
        return redirect(url_for('choose_mode'))
    # Jika belum, tampilkan halaman utama dengan tombol Login/Register.
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
    return redirect(url_for('index'))

@app.route('/choose-mode')
@login_required
def choose_mode():
    return render_template('choose_mode.html')

@app.route('/story-mode')
@login_required
def story_mode():
    return render_template('story_mode.html')

@app.route('/start-endless')
@login_required
def start_quiz():
    session.pop('score', None)
    session.pop('q_indices', None)
    session.pop('last_q_data', None)
    session['score'] = 0
    question_indices = list(range(len(QUESTIONS)))
    random.shuffle(question_indices)
    session['q_indices'] = question_indices
    session['current_q_index'] = 0
    return redirect(url_for('ask_question'))

@app.route('/question', methods=['GET', 'POST'])
@login_required
def ask_question():
    if 'q_indices' not in session: return redirect(url_for('start_quiz'))
    current_q_index_pos = session.get('current_q_index', 0)
    if current_q_index_pos >= len(session['q_indices']):
        random.shuffle(session['q_indices'])
        session['current_q_index'] = 0
        current_q_index_pos = 0
    question_index = session['q_indices'][current_q_index_pos]
    question_data = QUESTIONS[question_index]
    if request.method == 'POST':
        user_answer = request.form.get('option')
        correct_answer = question_data['answer']
        is_correct = (user_answer and user_answer == correct_answer)
        if not user_answer: user_answer, is_correct = 'Waktu Habis', False
        if is_correct:
            session['score'] += 1
            session['current_q_index'] += 1
            next_url = url_for('ask_question')
        else:
            next_url = url_for('results')
        return render_template('question.html', question=question_data, show_answer=True, is_correct=is_correct, user_answer=user_answer, correct_answer=correct_answer, next_url=next_url)
    question_num = session.get('score', 0) + 1
    return render_template('question.html', question=question_data, show_answer=False, question_num=question_num)

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

