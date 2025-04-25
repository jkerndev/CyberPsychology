from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_migrate import Migrate
from models import db, Participant, Question, Response 
from ai import theme, subtheme, ai_pii_prompts, validate_answer, generate_ai_question, check_ollama_api, generate_ai_followup
from database import store_participant, preload_questions, static_questions, get_participant_hash
from datetime import datetime
from sqlalchemy.pool import StaticPool

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
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "connect_args": {"check_same_thread": False},
    "poolclass": StaticPool
}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['AI_VER'] = False
db.init_app(app)
migrate = Migrate(app, db)  # This registers the 'db' command

logger = logging.getLogger(__name__) 

# Create tables on startup
with app.app_context():
    if not check_ollama_api():
        exit(1)  # Stop the app if Ollama isn't reachable
    db.create_all()
    preload_questions()

@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()

# Home route
@app.route('/')
def home():
    return render_template('index.html', theme=theme, subtheme=subtheme)

# Toggle AI mode (POST-only)
@app.route('/admin/toggle-ai', methods=['POST'])
def toggle_ai_version():
    app.config['AI_VER'] = not app.config['AI_VER']
    return jsonify({
        "AI_VER": app.config['AI_VER'],
        "message": f"AI version is now {'enabled' if app.config['AI_VER'] else 'disabled'}"
    })

# Admin dashboard with a toggle button
@app.route('/admin/dashboard')
def admin_dashboard():
    return render_template("admin_dashboard.html", ai_mode=app.config['AI_VER'])

@app.route('/deleteinfo', methods=['POST'])
def delete_info():
    message = None

    participant_id = request.form.get('participant_id')
    if not participant_id or not participant_id.isdigit():
        message = "Invalid participant ID."
    else:
        hashed_id = get_participant_hash(participant_id)
        participant = Participant.query.filter_by(id=hashed_id).first()
        if participant:
            db.session.delete(participant)
            db.session.commit()
            message = f"Participant {participant_id} and their responses were successfully deleted."
        else:
            message = f"No participant found with ID {participant_id}."

    return render_template("admin_dashboard.html",
                           ai_mode=app.config['AI_VER'],
                           message=message)

# Survey route
@app.route('/survey/<int:question_id>', methods=['GET', 'POST'])
def survey(question_id):
    user = session.get('user')

    # If post, validate the answer
    if request.method == 'POST':
        answer = request.form.get('answer')
        skipped = request.form.get('skip_next') == "true"
        skip_all = request.form.get('skip_all') == "true"
        bypass = request.form.get('bypass') == "true"
        answered = not skip_all and not skipped and (bool(answer) or bypass)

        if skip_all:
         # Store response
            new_response = Response(
                participant_id=get_participant_hash(user),
                question_id=question_id,
                answered=answered,
                skipped=skipped,
                skip_alled=True,
                conversation=session.get('conversation')
            )
            db.session.add(new_response)
            db.session.commit()

            logger.info(f"Remaining questions skipped. Going to results page.")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"next_url": url_for('results')})
            else:
                return redirect(url_for('results'))

        # Validate the answer
        if answered:
            current_pii = ai_pii_prompts[question_id - 11][0] if app.config['AI_VER'] else ai_pii_prompts[question_id - 1][0]

            if bypass:
                new_response = Response(
                    participant_id=get_participant_hash(user),
                    question_id=question_id,
                    answered=True,
                    skipped=False,
                    skip_alled=False,
                    conversation=session.get('conversation')
                )
                db.session.add(new_response)
                db.session.commit()
                session['conversation'] = ''

                # If it's an AJAX request, return JSON
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({"next_url": url_for('survey', question_id=question_id + 1)})

                return redirect(url_for('survey', question_id=question_id + 1))

            validation_result = validate_answer(current_pii, answer)

            if not validation_result:
                session['conversation'] += "\n ---------NEW TEXT--------- \n"
                if app.config['AI_VER']:
                    new_prompt = generate_ai_followup(current_pii, answer)
                else:
                    question = Question.query.filter(Question.id == question_id).one()
                    question_text = question.text
                    new_prompt = f"Sorry, that answer didn't seem to be quite right. Please try answering again. {question_text}"
                session['conversation'] += new_prompt

                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({"new_prompt": new_prompt})
            else:
                new_response = Response(
                    participant_id=get_participant_hash(user),
                    question_id=question_id,
                    answered=answered,
                    skipped=skipped,
                    skip_alled=skip_all,
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
                participant_id=get_participant_hash(user),
                question_id=question_id,
                answered=answered,
                skipped=skipped,
                skip_alled=skip_all,
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
    session.clear()
    question_index = 11 if app.config['AI_VER'] else 1
    if request.method == 'POST':
        session_id = request.form.get('session_id')
        major = request.form.get('major')
        
        # Backend validation
        if not session_id.isdigit() or len(session_id) != 9 or not session_id.startswith("900"):
            flash("Invalid 900 number. It must be exactly 9 digits and start with '900'.", "error")
            return redirect(url_for('register'))

        # Check if participant already exists
        existing_participant = Participant.query.filter_by(id=get_participant_hash(session_id)).first()
        if existing_participant:
            flash("Sorry! Your student ID is already registered as completing the survey. You cannot take it again.", "error")
            return render_template('register.html', AI_MODE=app.config['AI_VER'], already_taken=True)

        store_participant(session_id, major, app.config['AI_VER'])
        session['user'] = session_id
        return redirect(url_for('survey', question_id=question_index, session_id=session_id))

    # If we're just rendering the registration page (GET), check if 'already_taken' param is set
    already_taken = bool(request.args.get('already_taken', 0))
    return render_template('register.html', AI_MODE=app.config['AI_VER'], already_taken=already_taken)


# Results page
@app.route('/results')
def results():
    if 'result' not in session:
        random_float = random.randrange(70, 101) / 100  # between 0.7 and 1.0
        gpa = 3 + random_float 
        gpa = f"{gpa:.2f}"
        session['result'] = gpa
    else:
        gpa = session['result']
    return render_template('results.html', result=gpa)

if __name__ == '__main__':
    app.run(
        host="10.0.0.1",
        port=5000,
        ssl_context=(
            r"C:\Users\Jason\Documents\Wireguard\ssl cybspsyc\10.0.0.1.pem",
            r"C:\Users\Jason\Documents\Wireguard\ssl cybspsyc\10.0.0.1-key.pem"
        ),
        debug=True
        )
