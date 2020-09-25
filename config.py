# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

import os
from decouple import config

class Config(object):
    basedir    = os.path.abspath(os.path.dirname(__file__))
    SECRET_KEY = config('SECRET_KEY', default='sdnfogui3wn')
    SQLALCHEMY_DATABASE_URI = config('SQLALCHEMY_DATABASE_URI', default='sqlite:///test-3.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class ProductionConfig(Config):
    DEBUG = False

    # Security
    SESSION_COOKIE_HTTPONLY  = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = 3600

    # PostgreSQL database
    SQLALCHEMY_DATABASE_URI = '{}://{}:{}@{}:{}/{}'.format(
        config('DB_ENGINE'   , default='postgresql'    ),
        config('DB_USERNAME' , default='appseed'       ),
        config('DB_PASS'     , default='pass'          ),
        config('DB_HOST'     , default='localhost'     ),
        config('DB_PORT'     , default=5432            ),
        config('DB_NAME'     , default='appseed-flask' )
    )

class DebugConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = False

# Load all possible configurations
config_dict = {
    'Production': ProductionConfig,
    'Debug'     : DebugConfig
}
