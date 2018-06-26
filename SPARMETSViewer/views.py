# -*- coding: utf-8 -*-
"""Definition of the routes for the application."""
import os
import sys

from functools import lru_cache
from flask import request, render_template, jsonify
from flask_babel import gettext
from requests import get  # to make GET request
from werkzeug.utils import secure_filename

from SPARMETSViewer import app, babel, db
from config import LANGUAGES

from .models import METS
from .parsemets import METSFile


@babel.localeselector
def get_locale():
    """Retrieve locale based on available languages"""
    return request.accept_languages.best_match(LANGUAGES.keys())


def download(url, file_name):
    """Download a url in the given file"""
    # open in binary mode
    with open(file_name, "wb") as file:
        # get request
        response = get(url)
        if response.status_code != 200:
            raise ValueError("Not found")
        # write to file
        file.write(response.content)


def from_ark_to_name(ark):
    """Transform an ark in a name"""
    name = ark.replace(":", "-").replace("/", "-").replace("--", "-")
    if name.endswith(".xml"):
        return name
    return name + ".xml"


def allowed_file(filename):
    """Return the files with allowed extensions"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


@app.route("/", methods=['GET', 'POST'])
@app.route("/index", methods=['GET', 'POST'])
def index():
    """Primary route"""
    mets_instances = METS.query.all()
    return render_template('index.html', mets_instances=mets_instances)


@app.route("/upload", methods=['GET', 'POST'])
def render_page():
    """Access to the upload choice"""
    if request.method == 'POST':
        ark = request.form.get("ark")
    else:
        ark = request.args.get("ark", default="", type=str)
    if ark is not None and ark.startswith(app.config['ARK_PREFIX']):
        ark = ark.partition(app.config['ARK_PREFIX'])[2]

    return render_template(
        'upload.html',
        ark=ark,
        ark_prefix=app.config['ARK_PREFIX'],
        access_platform=app.config['ACCESS_PLATFORM'])


@app.route("/labels/<label>", methods=['GET'])
@lru_cache(maxsize=128)
def label_query(label):
    """Make a SPARQL query to retrieve a label"""
    platform = app.config['ACCESS_PLATFORM']
    if platform is None:
        return
    if platform == "TEST":
        if label == "sparprovenance:digitization":
            # print("THL label test for ", label, file=sys.stderr)
            return jsonify(
                {"head": {"link": [], "vars": ["label"]},
                 "results": {
                    "distinct": "false", "ordered": "true",
                    "bindings": [{"label": {"type": "literal", "value": "Numérisation"}}]}})
        else:
            return jsonify(
                {"head": {"link": [], "vars": ["label"]},
                 "results": {"distinct": "false", "ordered": "true", "bindings": []}})
    # Make a SPARQL query to retrieve the label
    endpoint = app.config['ACCESS_ENDPOINT']
    query = """
        SELECT ?label WHERE { %s rdfs:label ?label.
        FILTER (lang(?label) = '%s' or lang(?label) = '' } LIMIT 1""" % (label, gettext("en"))
    response = get(
        endpoint,
        headers={'Accept': 'application/sparql-results+json'},
        params={'query': query, 'format': 'application/sparql-results+json'})
    return response.content


@app.route("/sparql", methods=['GET', 'POST'])
def sparql_query():
    """Make a SPARQL query"""
    if request.method == 'POST':
        query = request.form.get("query")
    else:
        query = request.args.get("query")
    if query is None:
        raise ValueError("No query")

    endpoint = app.config['ACCESS_ENDPOINT']
    # print("THL sparql", endpoint + " " + query, file=sys.stderr)

    response = get(
        endpoint,
        headers={'Accept': 'application/sparql-results+json'},
        params={'query': query, 'format': 'application/sparql-results+json'})
    # print("THL sparql response", response.status_code, file=sys.stderr)
    return response.content


@app.route("/search", methods=['GET', 'POST'])
def search_ark():
    """Access to the search choice"""
    return render_template(
        'search.html',
        ark_prefix=app.config['ARK_PREFIX'],
        access_platform=app.config['ACCESS_PLATFORM'])


@app.route('/uploadsuccess', methods=['GET', 'POST'])
def upload_file():
    """Make the upload"""
    error = None
    if request.method == 'POST':
        nickname = request.form.get("nickname")
        # check if the post request has the file part
        if 'file' not in request.files:
            error = gettext('No file part')
            return render_template(
                'upload.html',
                error=error,
                ark_prefix=app.config['ARK_PREFIX'],
                access_platform=app.config['ACCESS_PLATFORM'])
        file = request.files['file']
        # if user does not select file, browser also
        # submit a empty part without filename
        if file.filename == '':
            error = gettext('No selected file')
            return render_template(
                'upload.html',
                error=error,
                ark_prefix=app.config['ARK_PREFIX'],
                access_platform=app.config['ACCESS_PLATFORM'])
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            mets_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            aip_name = os.path.basename(filename)
            mets = METSFile(mets_path, aip_name, nickname)
            success = mets.parse_mets()
            # delete file from uploads folder
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            if not success:
                error = gettext('METS already exists')
                return render_template(
                    'upload.html',
                    error=error,
                    ark_prefix=app.config['ARK_PREFIX'],
                    access_platform=app.config['ACCESS_PLATFORM'])
            # Success back to index
            mets_instances = METS.query.all()
            success = gettext('Success! METS file uploaded!')
            return render_template('index.html', mets_instances=mets_instances, success=success)
        else:
            error = gettext('Not allowed selected file')
            return render_template(
                'upload.html',
                error=error,
                ark_prefix=app.config['ARK_PREFIX'],
                access_platform=app.config['ACCESS_PLATFORM'])


@app.route('/retrievesuccess', methods=['GET', 'POST'])
def retrieve_ark():
    """Make the retrieval from ark"""
    error = None
    if request.method == 'POST':
        ark = request.form.get("ark")
        # check if the post request has the file part
        if ark is None or not ark.startswith("b"):
            error = gettext('No ARK part')
            return render_template(
                'upload.html',
                error=error,
                ark_prefix=app.config['ARK_PREFIX'],
                access_platform=app.config['ACCESS_PLATFORM'])
        access_platform = app.config['ACCESS_PLATFORM']
        access_server = app.config['ACCESS_URL']
        ark = app.config['ARK_PREFIX'] + ark.strip()
        if access_platform == 'TEST':
            url = access_server
        else:
            url = '%s/access/referenceDocumentRepository/%s.manifest' % (access_server, ark)
        filename = from_ark_to_name(ark)

        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
        mets_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        try:
            download(url, mets_path)
        except ValueError:
            os.remove(mets_path)
            error = gettext('METS not found')
            return render_template(
                'upload.html',
                error=error,
                ark_prefix=app.config['ARK_PREFIX'],
                access_platform=app.config['ACCESS_PLATFORM'])

        aip_name = os.path.basename(filename)
        mets = METSFile(mets_path, aip_name, access_platform)
        success = mets.parse_mets()
        # delete file from uploads folder
        os.remove(mets_path)
        if not success:
            error = gettext('METS already exists')
            return render_template(
                'upload.html',
                error=error,
                ark_prefix=app.config['ARK_PREFIX'],
                access_platform=app.config['ACCESS_PLATFORM'])
        # Success back to index
        mets_instances = METS.query.all()
        success = gettext('Success! METS file uploaded!')
        return render_template('index.html', mets_instances=mets_instances, success=success)


# See https://www.ntu.edu.sg/home/ehchua/programming/webprogramming/Python3_Flask.html
@app.route('/aip/<mets_file>')
def show_aip(mets_file):
    """Show a METS file"""
    mets_instance = METS.query.filter_by(metsfile='%s' % (mets_file)).first()
    original_files = mets_instance.metslist
    dcmetadata = mets_instance.dcmetadata
    filecount = mets_instance.originalfilecount
    aip_uuid = mets_file
    for element in dcmetadata:
        tag = element.get('element')
        if tag and tag == 'ark identifier':
            aip_uuid = element['value']
            break

    return render_template(
        'aip.html', original_files=original_files,
        mets_file=mets_file, dcmetadata=dcmetadata, filecount=filecount,
        aip_uuid=aip_uuid
    )


@app.route('/delete/<mets_file>')
def confirm_delete_aip(mets_file):
    """Access to the deletion"""
    return render_template('delete.html', mets_file=mets_file)


@app.route('/deletesuccess/<mets_file>')
def delete_aip(mets_file):
    """Delete the file"""
    mets_instance = METS.query.filter_by(metsfile='%s' % (mets_file)).first()
    db.session.delete(mets_instance)
    db.session.commit()
    return render_template('deletesuccess.html')


@app.route('/aip/<mets_file>/file/<fid>')
def show_file(mets_file, fid):
    """Access to the description of a file"""
    mets_instances = METS.query.filter_by(metsfile='%s' % (mets_file)).first()
    original_files = mets_instances.metslist
    for original_file in original_files:
        if original_file["id"] == fid:
            target_original_file = original_file
            break
    return render_template('detail.html', original_file=target_original_file, mets_file=mets_file)
