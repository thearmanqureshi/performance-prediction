from flask import Flask, render_template, request, jsonify
import numpy as np
import pandas as pd
from tensorflow.keras.models import load_model
import pickle
from datetime import datetime
from flask_pymongo import PyMongo
import requests
import tempfile
import os
import logging

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configure the app
if os.environ.get('FLASK_ENV') == 'production':
    from config import ProductionConfig
    app.config.from_object(ProductionConfig)
else:
    from config import DevelopmentConfig
    app.config.from_object(DevelopmentConfig)

# Initialize MongoDB
mongo = PyMongo(app)

def download_and_load_model(url):
    """
    Downloads a Keras model from a URL and loads it from a temporary file.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        # Save to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".h5") as temp_file:
            temp_file.write(response.content)
            temp_file_path = temp_file.name

        # Load model from temporary file
        model = load_model(temp_file_path)

        # Cleanup
        os.unlink(temp_file_path)

        return model
    except Exception as e:
        logger.error(f"Failed to download or load model: {str(e)}")
        raise

def download_and_load_scaler(url):
    """
    Downloads a scaler from a URL and loads it from a temporary file.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()

        # Save to a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(response.content)
            temp_file_path = temp_file.name

        # Load scaler
        with open(temp_file_path, 'rb') as f:
            scaler = pickle.load(f)

        # Cleanup
        os.unlink(temp_file_path)

        return scaler
    except Exception as e:
        logger.error(f"Failed to download or load scaler: {str(e)}")
        raise

def validate_input(age, year1_marks, year2_marks, studytime, failures):
    """
    Validates the input data for prediction.
    """
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

def save_to_mongo(data):
    """
    Saves data to MongoDB.
    """
    try:
        collection = mongo.db.student_performance_data
        result = collection.insert_one(data)
        return result.inserted_id is not None
    except Exception as e:
        logger.error(f"Failed to save to MongoDB: {str(e)}")
        return False

def predict_new_input(model, scaler, age, year1_marks, year2_marks, studytime, failures):
    """
    Prepares input data, scales it, and makes a prediction using the model.
    """
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

# Load the model and scaler
try:
    model = download_and_load_model(app.config['MODEL_URL'])
    scaler = download_and_load_scaler(app.config['SCALER_URL'])
except Exception as e:
    logger.critical(f"Failed to initialize model or scaler: {str(e)}")
    raise

@app.route('/')
def index():
    """
    Renders the home page.
    """
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict():
    """
    Handles predictions from form submissions.
    """
    try:
        # Retrieve and validate form data
        name = request.form['name']
        age = int(request.form['age'])
        year1_marks = float(request.form['year1_marks'])
        year2_marks = float(request.form['year2_marks'])
        studytime = float(request.form['study_time'])
        failures = int(request.form['failures'])

        # Validate input data
        validate_input(age, year1_marks, year2_marks, studytime, failures)
        
        # Make prediction
        prediction = predict_new_input(
            model, scaler, age, year1_marks, year2_marks, studytime, failures
        )

        if prediction is None:
            return jsonify({'error': 'Prediction failed'}), 500

        # Cap the prediction score to the max allowed value
        capped_prediction = min(
            round(float(prediction), 2), 
            app.config['MAX_PREDICTION_SCORE']
        )

        # Prepare data for MongoDB
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

        # Save prediction data to MongoDB
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
