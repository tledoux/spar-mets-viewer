# -*- coding: utf-8 -*-
import os
basedir = os.path.abspath(os.path.dirname(__file__))

SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'app.db')
SQLALCHEMY_MIGRATE_REPO = os.path.join(basedir, 'db_repository')
SQLALCHEMY_TRACK_MODIFICATIONS = False

UPLOAD_FOLDER = 'uploads'
# None (to forbid Ark download), TEST (to download the sample METS), PFO, PFV, ...
ACCESS_PLATFORM = 'TEST'
# If TEST, the url of the sample METS, otherwise the url of the ACCESS module
ACCESS_URL = 'http://localhost:5000/static/bpt6k6566369z.manifest.version0.release0.xml'
ARK_PREFIX = 'ark:/12148/'
ALLOWED_EXTENSIONS = set(['xml'])
# available languages
LANGUAGES = {
    'en': 'English',
    'fr': 'Français'
}