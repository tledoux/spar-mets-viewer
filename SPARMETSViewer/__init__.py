# -*- coding: utf-8 -*-
"""Initialization of the Flask App."""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_babel import Babel
from os import environ

app = Flask(__name__)
# Default configuration
app.config.from_object('config')
# Local configuration from METS_VIEWER environment variable
if environ.get('METSVIEWER_SETTINGS') is not None:
    app.config.from_envvar('METSVIEWER_SETTINGS')
babel = Babel(app)
db = SQLAlchemy(app)

from SPARMETSViewer import views, models
