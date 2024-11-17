# app.py
from flask import Flask, render_template, request, jsonify
import numpy as np
import pandas as pd
from tensorflow.keras.models import load_model
import pickle
from datetime import datetime
from flask_pymongo import PyMongo
import requests
import io
from config import ProductionConfig, DevelopmentConfig
import os
import logging
from flask_wtf.csrf import CSRFProtect

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configure the app
if os.environ.get('FLASK_ENV') == 'production':
    app.config.from_object(ProductionConfig)
else:
    app.config.from_object(DevelopmentConfig)

# Initialize extensions
csrf = CSRFProtect(app)
mongo = PyMongo(app)

def download_and_load_model(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        model = load_model(io.BytesIO(response.content))
        return model
    except Exception as e:
        logger.error(f"Failed to download model: {str(e)}")
        raise

def download_and_load_scaler(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        scaler = pickle.load(io.BytesIO(response.content))
        return scaler
    except Exception as e:
        logger.error(f"Failed to download scaler: {str(e)}")
        raise

def validate_input(age, year1_marks, year2_marks, studytime, failures):
    if not (0 <= age <= app.config['MAX_AGE']):
        raise ValueError(f"Age must be between 0 and {app.config['MAX_AGE']}")
    if not (0 <= year1_marks <= 100):
        raise ValueError("Year 1 marks must be between 0 and 100")
    if not (0 <= year2_marks <= 100):
        raise ValueError("Year 2 marks must be between 0 and 100")
    if not (0 <= studytime <= app.config['MAX_STUDY_HOURS']):
        raise ValueError(f"Study time must be between 0 and {app.config['MAX_STUDY_HOURS']}")
    if not (0 <= failures <= app.config['MAX_FAILURES']):
        raise ValueError(f"Failures must be between 0 and {app.config['MAX_FAILURES']}")
    return True

# Load the model and scaler
try:
    model = download_and_load_model(app.config['MODEL_URL'])
    scaler = download_and_load_scaler(app.config['SCALER_URL'])
except Exception as e:
    logger.critical(f"Failed to initialize model or scaler: {str(e)}")
    raise

def save_to_mongo(data):
    try:
        collection = mongo.db.student_performance_data
        result = collection.insert_one(data)
        return result.inserted_id is not None
    except Exception as e:
        logger.error(f"Failed to save to MongoDB: {str(e)}")
        return False

def predict_new_input(model, scaler, age, year1_marks, year2_marks, studytime, failures):
    try:
        new_input = pd.DataFrame({
            'age': [age],
            'year1_marks': [year1_marks],
            'year2_marks': [year2_marks],
            'studytime': [studytime],
            'failures': [failures]
        })
        new_input_scaled = scaler.transform(new_input)
        predicted_marks = model.predict(new_input_scaled)
        return predicted_marks[0][0]
    except Exception as e:
        logger.error(f"Prediction failed: {str(e)}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict():
    try:
        # Retrieve and validate form data
        name = request.form['name']
        age = int(request.form['age'])
        year1_marks = float(request.form['year1_marks'])
        year2_marks = float(request.form['year2_marks'])
        studytime = float(request.form['study_time'])
        failures = int(request.form['failures'])

        validate_input(age, year1_marks, year2_marks, studytime, failures)
        
        prediction = predict_new_input(
            model, scaler, age, year1_marks, year2_marks, studytime, failures
        )

        if prediction is None:
            return jsonify({'error': 'Prediction failed'}), 500

        capped_prediction = min(
            round(float(prediction), 2), 
            app.config['MAX_PREDICTION_SCORE']
        )

        data = {
            'name': name,
            'age': age,
            'year1_marks': year1_marks,
            'year2_marks': year2_marks,
            'study_time': studytime,
            'failures': failures,
            'predicted_score': capped_prediction,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        if not save_to_mongo(data):
            return jsonify({'error': 'Database error'}), 500

        return jsonify({'prediction': capped_prediction})
    
    except KeyError:
        return jsonify({'error': 'Missing required field'}), 400
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
