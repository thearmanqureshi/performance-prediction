from flask import Flask, render_template, request, jsonify
import numpy as np
import pandas as pd
from tensorflow.lite.python.interpreter import Interpreter
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

# Global variables
interpreter = None
scaler = None


def download_file(url, suffix):
    """
    Downloads a file from a URL and saves it to a temporary location.
    Returns the file path.
    """
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            for chunk in response.iter_content(chunk_size=8192):
                temp_file.write(chunk)
            return temp_file.name
    except Exception as e:
        logger.error(f"Failed to download file from {url}: {str(e)}")
        raise


def load_tflite_model(model_path):
    """
    Loads the TensorFlow Lite model into an interpreter.
    """
    try:
        interpreter = Interpreter(model_path=model_path)
        interpreter.allocate_tensors()
        logger.info("TensorFlow Lite model loaded successfully.")
        return interpreter
    except Exception as e:
        logger.error(f"Failed to load TensorFlow Lite model: {str(e)}")
        raise


def load_scaler(scaler_path):
    """
    Loads the scaler from a file.
    """
    try:
        with open(scaler_path, 'rb') as f:
            scaler = pickle.load(f)
        logger.info("Scaler loaded successfully.")
        return scaler
    except Exception as e:
        logger.error(f"Failed to load scaler: {str(e)}")
        raise


def initialize_model_and_scaler():
    """
    Initializes the TensorFlow Lite model and scaler by downloading them from the configured URLs.
    """
    global interpreter, scaler
    try:
        model_path = download_file(app.config['MODEL_URL'], '.tflite')
        scaler_path = download_file(app.config['SCALER_URL'], '.pkl')

        interpreter = load_tflite_model(model_path)
        scaler = load_scaler(scaler_path)

        # Clean up temporary files
        os.unlink(model_path)
        os.unlink(scaler_path)
    except Exception as e:
        logger.critical(f"Failed to initialize model or scaler: {str(e)}")
        raise


def predict_with_tflite(interpreter, input_data):
    """
    Runs a prediction using the TensorFlow Lite interpreter.
    """
    try:
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()

        # Prepare input tensor
        interpreter.set_tensor(input_details[0]['index'], input_data)
        interpreter.invoke()

        # Get the prediction
        prediction = interpreter.get_tensor(output_details[0]['index'])
        return prediction[0][0]
    except Exception as e:
        logger.error(f"Prediction with TensorFlow Lite failed: {str(e)}")
        return None


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

        # Prepare input data for prediction
        input_data = pd.DataFrame({
            'age': [age],
            'year1_marks': [year1_marks],
            'year2_marks': [year2_marks],
            'studytime': [studytime],
            'failures': [failures]
        })

        scaled_data = scaler.transform(input_data)
        scaled_data = scaled_data.astype(np.float32)

        # Run the prediction
        prediction = predict_with_tflite(interpreter, scaled_data)
        if prediction is None:
            return jsonify({'error': 'Prediction failed'}), 500

        # Cap the prediction score to the max allowed value
        capped_prediction = min(round(float(prediction), 2), app.config['MAX_PREDICTION_SCORE'])

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
        collection = mongo.db.student_performance_data
        collection.insert_one(data)

        return jsonify({'prediction': capped_prediction})
    except KeyError:
        return jsonify({'error': 'Missing required field'}), 400
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


# Initialize model and scaler at startup
initialize_model_and_scaler()
