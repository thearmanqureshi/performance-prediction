# config.py
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')
    MONGO_URI = os.getenv('MONGO_URI')
    SESSION_COOKIE_SECURE = True
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    MODEL_URL = os.getenv('MODEL_URL')
    SCALER_URL = os.getenv('SCALER_URL')
    MAX_PREDICTION_SCORE = 98
    MAX_AGE = 100
    MAX_STUDY_HOURS = 24
    MAX_FAILURES = 10

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = True
    SESSION_COOKIE_SECURE = False
