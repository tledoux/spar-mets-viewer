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
ACCESS_URL = 'http://localhost:5000/static/samples/bpt6k206840w.manifest.xml'
ACCESS_ENDPOINT = 'http://localhost:5000/static/samples/sparqlResponse.json'
SPARQL_URL = 'http://localhost:5000/static/samples/bpt6k206840w.rdf.json'
ARK_PREFIX = 'ark:/12148/'
ALLOWED_EXTENSIONS = set(['xml'])
# available languages
LANGUAGES = {
    'en': 'English',
    'fr': 'Français'
}