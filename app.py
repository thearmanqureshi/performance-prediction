from flask import Flask, render_template, request, jsonify
import numpy as np
import pandas as pd
from tensorflow.keras.models import load_model
import pickle
from datetime import datetime
from flask_pymongo import PyMongo
import requests
import io
from flask_bcrypt import Bcrypt
import os
from config import ProductionConfig, DevelopmentConfig
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Use ProductionConfig when FLASK_ENV is production
if os.environ.get('FLASK_ENV') == 'production':
    app.config.from_object(ProductionConfig)
else:
    app.config.from_object(DevelopmentConfig)

# URLs for Google Drive files
model_url = "https://drive.google.com/uc?id=1cyP8_m9-rxGnjzP5AOGT7vUOPo7egi85&export=download"
scaler_url = "https://drive.google.com/uc?id=14-iYqt7IB1n92b86Uj3QcJ5gpoNmj715&export=download"

# Function to download and load the model
def download_and_load_model(url):
    response = requests.get(url)
    if response.status_code == 200:
        model = load_model(io.BytesIO(response.content))
        return model
    else:
        raise Exception(f"Failed to download model from {url}")

# Function to download and load the scaler
def download_and_load_scaler(url):
    response = requests.get(url)
    if response.status_code == 200:
        scaler = pickle.load(io.BytesIO(response.content))
        return scaler
    else:
        raise Exception(f"Failed to download scaler from {url}")

# Load the trained model and scaler from Google Drive URLs
model = download_and_load_model(model_url)
scaler = download_and_load_scaler(scaler_url)

def save_to_mongo(data):
    """Save prediction data to MongoDB"""
    try:
        collection = mongo.db.student_performance_data
        result = collection.insert_one(data)
        print(f"Inserted document ID: {result.inserted_id}")  # Debug log
        return result.inserted_id is not None
    except Exception as e:
        print(f"Error saving to MongoDB: {e}")
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
        print(f"Error during prediction: {e}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict():
    try:
        # Retrieve form data
        name = request.form['name']
        age = int(request.form['age'])
        year1_marks = float(request.form['year1_marks'])
        year2_marks = float(request.form['year2_marks'])
        studytime = float(request.form['study_time'])
        failures = int(request.form['failures'])

        # Predict final marks
        prediction = predict_new_input(model, scaler, age, year1_marks, year2_marks, studytime, failures)

        if prediction is None:
            return jsonify({'error': 'Prediction failed due to internal error.'}), 500

        # Cap the predicted score at 98
        capped_prediction = min(round(float(prediction), 2), 98)

        # Prepare data for storage
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

        # Save to MongoDB
        if not save_to_mongo(data):
            return jsonify({'error': 'Error saving data to MongoDB.'}), 500

        # Return the result as a JSON response
        return jsonify({'prediction': capped_prediction} )
    
    except KeyError as ke:
        return jsonify({'error': f'Missing required field: {ke}'}), 400
    except ValueError as ve:
        return jsonify({'error': 'Invalid input. Please ensure all fields contain correct values.'}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error.'}), 500

if __name__ == '__main__':
    app.run(debug=True)
