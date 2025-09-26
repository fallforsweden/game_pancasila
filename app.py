from flask import Flask, render_template, request, redirect, url_for, session
import random

app = Flask(__name__)
app.secret_key = 'pancasila'

QUESTIONS = [
    {
        'question': 'Apa warna celana dalam fatur?',
        'options': ['Merah', 'Biru', 'Kuning', 'Gak Pake'],
        'answer': 'Merah',
        'explanation': 'Merah boi warnanya'
    },
    {
        'question': 'Apa warna celana dalam achmad?',
        'options': ['Merah', 'Biru', 'Kuning', 'Gak Pake'],
        'answer': 'Kuning',
        'explanation': 'Kuning katanya biar keren'
    },
    {
        'question': 'Apa mata kuliah yang diajarkan pak agung hari senin dan jumat?',
        'options': ['Sistem Tidak Cerdas', 'Sistem Bodoh', 'Mesin Tidak Belajar', 'Sistem Cerdas'],
        'answer': 'Sistem Cerdas',
        'explanation': 'Sebenernya sih gak tau ngajar apa, mahasiswa nya aja bingung semua.'
    },
    {
        'question': 'Kapan libur?',
        'options': ['besok', 'minggu depan', 'lusa', '25 desember'],
        'answer': '25 desember',
        'explanation': 'kalo belom uas sih harusnya 25 libur natal'
    }
]

# --- Flask Routes ---

@app.route('/', methods=['GET', 'POST'])
def index():
    """
    Handles the home page where the user enters their name.
    """
    if request.method == 'POST':
        # When the user submits their name, store it in the session
        session['username'] = request.form['username']
        # Redirect to the quiz start
        return redirect(url_for('start_quiz'))
    return render_template('index.html')

@app.route('/start')
def start_quiz():
    """
    Initializes the quiz state.
    """
    # Clear any previous quiz data
    session.pop('score', None)
    session.pop('q_indices', None)
    
    # Store quiz state in the session
    session['score'] = 0
    # Create a shuffled list of question indices
    question_indices = list(range(len(QUESTIONS)))
    random.shuffle(question_indices)
    session['q_indices'] = question_indices
    session['current_q_index'] = 0 # This will track our position in the shuffled list
    
    return redirect(url_for('ask_question'))

@app.route('/question', methods=['GET', 'POST'])
def ask_question():
    """
    Displays a question or processes an answer.
    """
    if 'q_indices' not in session or session['current_q_index'] >= len(session['q_indices']):
        # If the quiz is over or not started, go to results
        return redirect(url_for('results'))

    # Get the actual index for the current question
    question_index = session['q_indices'][session['current_q_index']]
    question_data = QUESTIONS[question_index]

    if request.method == 'POST':
        # --- This block handles the submitted answer ---
        user_answer = request.form.get('option')
        correct_answer = question_data['answer']
        is_correct = (user_answer == correct_answer)

        if is_correct:
            session['score'] += 1

        # Move to the next question for the next time this page is loaded
        session['current_q_index'] += 1

        # Show the answer and explanation page
        return render_template('question.html', 
                               question=question_data,
                               show_answer=True,
                               is_correct=is_correct,
                               user_answer=user_answer,
                               correct_answer=correct_answer)

    # --- This block handles showing a new question ---
    # Check if we have asked 10 questions already
    if session['current_q_index'] >= 10:
        return redirect(url_for('results'))
        
    return render_template('question.html', 
                           question=question_data, 
                           show_answer=False,
                           question_num=session['current_q_index'] + 1)

@app.route('/results')
def results():
    """
    Displays the final score and an option to restart.
    """
    score = session.get('score', 0)
    username = session.get('username', 'Player')
    total_questions = min(session.get('current_q_index', 0), 10)
    
    return render_template('results.html', 
                           username=username, 
                           score=score, 
                           total_questions=total_questions)

# This line allows the app to be run directly from the Python script
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
