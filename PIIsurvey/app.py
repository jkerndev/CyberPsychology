from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from models import db, Participant, Question, Response 
from ai import theme, subtheme, ai_pii_prompts, validate_answer, generate_ai_question, check_ollama_api, generate_ai_followup
from database import store_participant, preload_questions, static_questions
from datetime import datetime

import os
import logging
import random

logging_level = logging.DEBUG

# Set up global logging
logging.basicConfig(
    level=logging_level,  
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler()  # Logs to the console
    ]
)

app = Flask(__name__)
app.config.update(SECRET_KEY=os.urandom(24)) # This app is and always will be run locally, no secret key needed
app.logger.setLevel(logging_level)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['AI_VER'] = False
db.init_app(app)

logger = logging.getLogger(__name__) 

# Create tables on startup
with app.app_context():
    if not check_ollama_api():
        exit(1)  # Stop the app if Ollama isn't reachable
    db.create_all()
    preload_questions()

# Home route
@app.route('/')
def home():
    return render_template('index.html', theme=theme, subtheme=subtheme)

# Survey route
@app.route('/survey/<int:question_id>', methods=['GET', 'POST'])
def survey(question_id):
    user = session.get('user')

    # If post, validate the answer
    if request.method == 'POST':
        answer = request.form.get('answer')
        skipped = request.form.get('skip_next') == "true"
        answered = not skipped and bool(answer)

        # Validate the answer
        if answered:
            current_pii = ai_pii_prompts[question_id - 11][0] if app.config['AI_VER'] else ai_pii_prompts[question_id - 1][0]
            validation_result = validate_answer(current_pii, answer)

            if not validation_result:
                session['conversation'] += "\n ---------NEW TEXT--------- \n"
                if app.config['AI_VER']:
                    new_prompt = generate_ai_followup(current_pii, answer)
                else:
                    new_prompt = "Sorry, that answer didn't seem to be quite right. Please try answering again."
                session['conversation'] += new_prompt

                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({"new_prompt": new_prompt})
            else:
                # Store response
                new_response = Response(
                    participant_id=user,
                    question_id=question_id,
                    answered=answered,
                    skipped=skipped,
                    conversation=session.get('conversation')
                )
                db.session.add(new_response)
                db.session.commit()
                session['conversation'] = ''

                logger.info(f"Question answered. Moving to question {question_id + 1}")

                # If it's an AJAX request, return JSON
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({"next_url": url_for('survey', question_id=question_id + 1)})

                return redirect(url_for('survey', question_id=question_id + 1))

        elif skipped:
            new_response = Response(
                participant_id=user,
                question_id=question_id,
                answered=answered,
                skipped=skipped,
                conversation=session.get('conversation')
            )
            db.session.add(new_response)
            db.session.commit()
            session['conversation'] = ''

            logger.info(f"Question skipped. Moving to question {question_id + 1}")

            # If it's an AJAX request, return JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"next_url": url_for('survey', question_id=question_id + 1)})

            return redirect(url_for('survey', question_id=question_id + 1))

    # If >9, redirect to results
    if (question_id > 9 and not app.config['AI_VER']) or (question_id > 19 and app.config['AI_VER']):
        return redirect(url_for('results'))

    # If new, generate question

    question_text = None
    if app.config['AI_VER']:
        question_text = generate_ai_question(question_id)
    else:
        question = Question.query.filter(Question.id == question_id).one()
        question_text = question.text
    session['conversation'] = session.get('conversation', '') + question_text

    new_prompt = None

    return render_template('survey.html', question=question_text, question_id=question_id, new_prompt=new_prompt)

@app.route('/register', methods=['GET', 'POST'])
def register():
    question_index = 11 if app.config['AI_VER'] else 1
    if request.method == 'POST':
        session_id = request.form.get('session_id')
        major = request.form.get('major')
        
        # Backend validation
        if not session_id.isdigit() or len(session_id) != 9 or not session_id.startswith("900"):
            flash("Invalid 900 number. It must be exactly 9 digits and start with '900'.", "error")
            return redirect(url_for('register'))

        # Check if participant already exists
        existing_participant = Participant.query.filter_by(id=int(session_id)).first()
        if existing_participant:
            flash("You have already completed the survey with that ID. You cannot take it again.", "error")
            return redirect(url_for('register', already_taken=True))

        # Store participant (remove the `gender` argument here)
        store_participant(session_id, major)
        session['user'] = session_id
        return redirect(url_for('survey', question_id=question_index, session_id=session_id))

    # If we're just rendering the registration page (GET), check if 'already_taken' param is set
    already_taken = bool(request.args.get('already_taken', 0))
    return render_template('register.html', AI_MODE=app.config['AI_VER'], already_taken=already_taken)


# Results page
@app.route('/results')
def results():
    random_float = random.random()
    gpa = 3 + random_float 
    gpa = f"{gpa:.2f}"
    return render_template('results.html', result=gpa)

if __name__ == '__main__':
    app.run(debug=True)
