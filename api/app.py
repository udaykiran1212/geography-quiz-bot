from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import os
import google.generativeai as genai
import requests
from functools import wraps
import jwt
import json
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='../static', template_folder='../templates')
CORS(app)

# Configuration
app.config['SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'default-secret-key-for-development')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
FOURSQUARE_API_KEY = os.getenv('FOURSQUARE_API_KEY')
JWT_EXPIRATION_MINUTES = 30

# In-memory user storage (for demo purposes - replace with database in production)
users = {}

# Configure Gemini
try:
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash')
        logger.info("Gemini API configured successfully")
    else:
        logger.warning("GEMINI_API_KEY not found in environment variables")
except Exception as e:
    logger.error(f"Error configuring Gemini: {str(e)}")

# Authentication decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            auth_header = request.headers.get('Authorization')
            if not auth_header:
                return jsonify({'message': 'Token is missing'}), 401
                
            token = auth_header.split()[1]
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = data['user']
            return f(current_user, *args, **kwargs)
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Token is invalid'}), 401
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return jsonify({'message': 'Authentication failed'}), 401
    return decorated

@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Error rendering index: {str(e)}")
        return jsonify({'error': 'Failed to load page'}), 500

@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('../static', path)

@app.route('/api/auth/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        if not data or 'username' not in data or 'password' not in data:
            return jsonify({'error': 'Missing username or password'}), 400
            
        username = data['username']
        password = data['password']
        
        if username in users:
            return jsonify({'error': 'Username already exists'}), 400
            
        # In production, you should hash the password
        users[username] = {
            'password': password,
            'score': 0,
            'quizzes_completed': 0
        }
        
        return jsonify({'message': 'Registration successful'}), 201
        
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        if not data or 'username' not in data or 'password' not in data:
            return jsonify({'error': 'Missing username or password'}), 400
            
        username = data['username']
        password = data['password']
        
        if username not in users or users[username]['password'] != password:
            return jsonify({'error': 'Invalid credentials'}), 401
            
        # Create JWT token
        token = jwt.encode({
            'user': username,
            'exp': datetime.utcnow() + timedelta(minutes=JWT_EXPIRATION_MINUTES)
        }, app.config['SECRET_KEY'], algorithm='HS256')
        
        return jsonify({
            'token': token,
            'user': {
                'username': username,
                'score': users[username]['score'],
                'quizzes_completed': users[username]['quizzes_completed']
            }
        })
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/quiz/generate', methods=['GET'])
@token_required
def generate_quiz(current_user):
    try:
        # Default question when Gemini is not configured
        if not GEMINI_API_KEY:
            return jsonify({
                'id': 'sample_question_1',
                'question': 'What is the capital of France?',
                'options': ['Paris', 'London', 'Berlin', 'Madrid'],
                'correct_answer': 0
            })
            
        # Generate quiz using Gemini
        prompt = """
        Generate an interesting geography quiz question about world geography.
        Provide the question and 4 options where one is correct.
        Format the response as JSON with:
        {
            "question": "the question text",
            "options": ["option1", "option2", "option3", "option4"],
            "correct_answer": index_of_correct_answer
        }
        """
        
        response = model.generate_content(prompt)
        
        try:
            # Try to parse the response as JSON
            question_data = json.loads(response.text)
            question_data['id'] = f"question_{datetime.now().timestamp()}"
            return jsonify(question_data)
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            return jsonify({
                'id': 'generated_question_1',
                'question': 'Which country has the largest population?',
                'options': ['China', 'India', 'United States', 'Indonesia'],
                'correct_answer': 1
            })
            
    except Exception as e:
        logger.error(f"Quiz generation error: {str(e)}")
        return jsonify({
            'error': 'Failed to generate question',
            'default_question': {
                'id': 'fallback_question_1',
                'question': 'Which river is the longest in the world?',
                'options': ['Nile', 'Amazon', 'Yangtze', 'Mississippi'],
                'correct_answer': 0
            }
        }), 500

@app.route('/api/quiz/submit', methods=['POST'])
@token_required
def submit_quiz(current_user):
    try:
        data = request.get_json()
        if not data or 'answer' not in data or 'questionId' not in data:
            return jsonify({'error': 'Missing answer or question ID'}), 400
            
        # In production, you would validate the question ID and answer
        is_correct = data.get('is_correct', False)  # Normally you'd check against correct answer
        
        if is_correct:
            users[current_user]['score'] += 1
        users[current_user]['quizzes_completed'] += 1
        
        return jsonify({
            'message': 'Answer submitted successfully',
            'is_correct': is_correct,
            'score': users[current_user]['score'],
            'quizzes_completed': users[current_user]['quizzes_completed']
        })
        
    except Exception as e:
        logger.error(f"Quiz submission error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/quiz/progress', methods=['GET'])
@token_required
def get_progress(current_user):
    try:
        if current_user not in users:
            return jsonify({'error': 'User not found'}), 404
            
        return jsonify({
            'score': users[current_user]['score'],
            'quizzes_completed': users[current_user]['quizzes_completed']
        })
        
    except Exception as e:
        logger.error(f"Progress tracking error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# This is required for Vercel
if __name__ == '__main__':
    app.run(debug=True)
