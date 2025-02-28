from models import db, Participant, Response, Question
from ai import ai_pii_prompts, context, prompt, theme, subtheme
import requests

static_questions = [
    ("What is your age?", 1),
    ("What is your gender?", 2),
    ("In hours, how much time do you spend online per week?", 3),
    ("What is your name?", 4),
    ("What is your race/ethnicity?", 5),
    ("What is your personal email address?", 6),
    ("What is your postal address?", 7),
    ("What is your phone number?", 8),
    ("What is your social security number?", 9)
]

def preload_questions():
    if not Question.query.first():  # Avoid duplicates
        # Insert static questions
        for q in static_questions:
            db.session.add(Question(id=q[1], text=q[0], is_ai_generated=False))
        
        # Insert AI prompts (initially with empty responses)
        for pii in ai_pii_prompts:
            db.session.add(Question(id=pii[1], prompt=context.format(theme=theme)+prompt.format(pii=pii[0]), is_ai_generated=True))
        
        db.session.commit()

def store_participant(session_id, major):
    """
    Stores a new participant in the database.
    :param session_id: The 900 number of the participant
    :param major: The participant's major
    """
    
    new_participant = Participant(id=int(session_id), major=major)
    db.session.add(new_participant)
    db.session.commit()