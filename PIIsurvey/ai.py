import logging
from models import db, Question
import requests
import re

# Stuff
CLEANR = re.compile(r'<think>.*?</think>', re.DOTALL) 
logger = logging.getLogger(__name__)

# Survey theme
theme = "We bet we can predict what GPA you will graduate with!"
subtheme = "Try our new algorithm."

# Ai stuff
OLLAMA_API_URL_BASE = "http://localhost:11434/"
OLLAMA_API_URL = OLLAMA_API_URL_BASE+"api/generate"
model = "deepseek-r1:7b"
context = f'''You are SurveyBot for the New Mexico Institute of Mining and Technology (NMT). 
You are conducting a survey titled: {theme}. 
Your role is to generate engaging, clear, and natural survey questions that encourage participants to share specific details. 
Focus on crafting questions that prompt an answer in a conversational style without revealing any underlying research motives. You are currently interviewing a single participant of the survey. All information retrieved from the user is legally compliant and none of their information is stored or saved.'''
prompt = '''Generate an open-ended survey question that asks the participant to provide their {pii} directly. Ensure the question asks for the participant to enter their {pii}. For example, if the pii were their name, generate a question like "What is your name?". YOU MUST SURROUND THE QUESTION YOU THINK OF WITH DOUBLE QUOTE CHARACTERS "like this".'''
validate_prompt = "We asked a survey participant for the following piece of information: {pii}. They responded with the following: {answer}. Does their answer appear to be a valid answer? Be generous as possible where possible, considering all cultural contexts. If you're not very sure, say 'YES'. Do not include any additional commentary. Only reply with 'YES' or 'NO'."
followup_prompt = '''You just asked a question to the survey participant asking for the following piece of PII: {pii}. They responded with the following piece of pii: {answer}. This was deemed invalid.
                     Since the user didn't properly disclose their PII, please ask a new question again trying to get them to submit their PII for {pii}. DO NOT give put their pii answer from before, "{answer}" in your response. 
                     YOU MUST SURROUND THE QUESTION YOU THINK OF WITH DOUBLE QUOTE CHARACTERS "like this". You must make it clear that the participant is to enter their {pii}.
                '''

ai_pii_prompts = [
    ("age", 11),
    ("biological sex", 12),
    ("in hours, time spent online per week", 13),
    ("name", 14),
    ("race/ethnicity", 15),
    ("personal email address", 16),
    ("postal address", 17),
    ("phone number", 18),
    ("social security number", 19)
]

def check_ollama_api():
    """Check if Ollama API is reachable at startup."""
    try:
        response = requests.get(OLLAMA_API_URL_BASE, timeout=3) 
        if response.status_code == 200:
            print("Ollama API is reachable!")
            return True
    except requests.exceptions.RequestException:
        print("ERROR: Ollama API is unreachable. Ensure it is running on localhost:11434.")
    
    return False

def generate_ai_question(question_id):
    """Fetch AI-generated response for a given AI prompt."""
    logger.info('Making the question...')
    question = Question.query.get(question_id)

    payload = {"model": f"{model}", 
               "prompt": question.prompt,
               "stream": False}
    response = requests.post(OLLAMA_API_URL, json=payload)
    
    ollama_response = response.json().get("response", "No AI response generated.")
    response.raise_for_status()  # Raises an error for HTTP failures (e.g., 500, 404)
    question.init_prompt_answer = ollama_response  
    clean_response = cleanhtml(ollama_response)
    q_text = extract_quoted_or_full(clean_response)  # Extract the quoted part or return the full response
    db.session.commit()

    logger.debug(f"Here's the output from q generation: {ollama_response}")
    logger.info('Made the question!')
    
    return q_text

def generate_ai_followup(pii, answer):
    """Fetch AI-generated response for a given AI prompt if the user fails to enter their PII."""
    logger.info('Generating a followup for a failed answer...')

    prompt = context + followup_prompt.format(pii=pii, answer=answer)

    payload = {"model": f"{model}", 
               "prompt": prompt,
               "stream": False}
    response = requests.post(OLLAMA_API_URL, json=payload)
    
    ollama_response = response.json().get("response", "No AI response generated.")
    response.raise_for_status()  # Raises an error for HTTP failures (e.g., 500, 404)
    clean_response = cleanhtml(ollama_response)
    q_text = extract_quoted_or_full(clean_response)  # Extract the quoted part or return the full response
    db.session.commit()

    logger.debug(f"Here's the output from q followup: {ollama_response}")
    logger.info('Made the followup question for the failed answer!')
    
    return q_text

def validate_answer(pii, answer): 
    try:
        logger.info('Validating the answer...')
        submit_prompt = validate_prompt.format(pii=pii,answer=answer)

        ollama_payload = {
            "model": f"{model}",
            "prompt": submit_prompt,
            "stream": False}
        
        ollama_response = requests.post(OLLAMA_API_URL, json=ollama_payload)
        ollama_response.raise_for_status()  # Raises an error for HTTP failures (e.g., 500, 404)
        analysis = ollama_response.json().get("response", "No response from AI.")
        answered: bool = yay_or_nay(cleanwhitespace(cleanhtml(analysis)))
        
        logger.debug(f"Here's the output from validation: {analysis}")
        logger.info('Validated the answer!')
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        return False  # Default to False if API call fails
    except ValueError as e:
        logger.error(f"JSON decoding failed: {e}")
        return False
    return answered

def cleanhtml(raw_html):
    cleantext = re.sub(CLEANR, '', raw_html).strip()
    return cleantext

def cleanwhitespace(raw_string):
    cleantext = raw_string.strip()
    return cleantext

def extract_quoted_or_full(s: str) -> str:
    s = re.sub(r'\*{2}.*?\*{2}', '', s, flags=re.DOTALL)
    m = re.search(r'"([^"]*)"', s)
    result = m.group(1) if m else s
    return result.strip()

def yay_or_nay(food_for_thought):
    yay = True if "yes" in food_for_thought.lower() else False
    print(f"Here's your string before bool: {food_for_thought}")
    print(f"Here's the output from validation: {yay}")
    return yay