from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
import random
import json 
from datetime import datetime 

app = Flask(__name__)
app.secret_key = 'pancasila'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///scores.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class ScoreEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.now())

    def __repr__(self):
        return f'<ScoreEntry {self.username}: {self.score}>'

try:
    with open('questions.json', 'r') as f:
        QUESTIONS = json.load(f)
except FileNotFoundError:
    print("WARNING: questions.json not found! Using an empty list.")
    QUESTIONS = []

# --- Flask Routes ---

@app.route('/', methods=['GET', 'POST'])
def index():
    """
    Handles the home page where the user enters their name.
    """
    if request.method == 'POST':
        session['username'] = request.form['username']
        return redirect(url_for('start_quiz'))
    return render_template('index.html')

@app.route('/start')
def start_quiz():
    """
    Initializes the quiz state.
    """
    if not QUESTIONS:
        session['error_message'] = "Quiz data not loaded. Check questions.json."
        return redirect(url_for('results'))
        
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
def ask_question():
    """
    Displays a question or processes an answer. Logic for Endless Quiz is here.
    """
    if 'q_indices' not in session:
        return redirect(url_for('start_quiz'))

    current_q_index_pos = session['current_q_index']
    total_q_count = len(QUESTIONS)

    # LOGIKA ENDLESS: ULANGI DAN ACAK JIKA SEMUA PERTANYAAN SUDAH DILIHAT
    if current_q_index_pos >= total_q_count:
        question_indices = list(range(total_q_count))
        random.shuffle(question_indices)
        session['q_indices'] = question_indices
        session['current_q_index'] = 0
        current_q_index_pos = 0 
    
    # Dapatkan data pertanyaan saat ini
    question_index = session['q_indices'][current_q_index_pos]
    question_data = QUESTIONS[question_index]

    if request.method == 'POST':
        user_answer = request.form.get('option')
        correct_answer = question_data['answer']
        is_correct = False
        
        # Penilaian Jawaban (Termasuk Timeout)
        if user_answer and user_answer != 'TIMEOUT_SIGNAL':
            is_correct = (user_answer == correct_answer)
        else:
            user_answer = 'Waktu Habis / Tidak Ada Jawaban'
            is_correct = False

        if is_correct:
            # JIKA BENAR: Tambah skor, pindah ke soal berikutnya, tombol Next ke /question
            session['score'] += 1
            session['current_q_index'] += 1
            next_url = url_for('ask_question')
        else:
            # JIKA SALAH: KUIS SELESAI. Tombol Next ke /results
            next_url = url_for('results')
            
            # Simpan data soal yang salah terakhir untuk ditampilkan di halaman hasil
            session['last_q_data'] = {
                'question': question_data['question'],
                'user_answer': user_answer,
                'correct_answer': correct_answer,
                'explanation': question_data['explanation']
            }
            
        # Tampilkan halaman hasil/jawaban (feedback)
        return render_template('question.html', 
                                question=question_data,
                                show_answer=True,
                                is_correct=is_correct,
                                user_answer=user_answer,
                                correct_answer=correct_answer,
                                next_url=next_url) # Kirim URL tujuan tombol

    # --- This block handles showing a new question (GET) ---
    
    # Nomor pertanyaan adalah skor + 1, karena skor melacak jumlah jawaban benar
    question_num = session.get('score', 0) + 1
        
    return render_template('question.html', 
                           question=question_data, 
                           show_answer=False,
                           question_num=question_num)

@app.route('/results')
def results():
    """
    Displays the final score and an option to restart.
    """
    error_message = session.pop('error_message', None)
    
    # Ambil skor sebelum menghapus dari sesi
    score = session.get('score', 0)
    username = session.get('username', 'Player')
    
    # Ambil data soal yang salah terakhir (untuk ditampilkan di results.html)
    last_q_data = session.pop('last_q_data', None)
    
    # Menyimpan skor ke Database (hanya skor streak terbaik yang berhasil)
    if score > 0 and username != 'Player': 
        with app.app_context():
            new_entry = ScoreEntry(username=username, score=score)
            db.session.add(new_entry)
            db.session.commit()

    # Mengambil skor tertinggi (Highest Streak per user)
    with app.app_context():
        top_scores = db.session.query(
        ScoreEntry.username,
        func.max(ScoreEntry.score).label("score")
        ).group_by(ScoreEntry.username) \
        .order_by(func.max(ScoreEntry.score).desc()) \
        .limit(10).all()

    # Hapus semua data kuis (kecuali username) dari sesi
    session.pop('q_indices', None)
    session.pop('current_q_index', None)
    session.pop('score', None)
        
    return render_template('results.html', 
                           username=username, 
                           score=score, 
                           total_questions=score, # Total pertanyaan yang dijawab benar = Score
                           top_scores=top_scores,
                           last_q_data=last_q_data,
                           error_message=error_message)

def create_db():
    with app.app_context():
        db.create_all()
        print("Database initialized and tables created!")

# This line allows the app to be run directly from the Python script
if __name__ == '__main__':
    create_db()
    app.run(host='0.0.0.0', port=5000, debug=True)