from flask import Flask, request, redirect, render_template, flash
from flask_babel import gettext
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from SPARMETSViewer import app, babel, db
from .models import METS
from .parsemets import METSFile, convert_size

from config import LANGUAGES
from flask_babel import refresh;

import collections
import datetime
import fnmatch
import math
import os
import sys
from lxml import etree, objectify

@babel.localeselector
def get_locale():
    return request.accept_languages.best_match(LANGUAGES.keys())

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


@app.route("/", methods=['GET', 'POST'])
@app.route("/index", methods=['GET', 'POST'])
def index():
    mets_instances = METS.query.all()
    return render_template('index.html', mets_instances = mets_instances)


@app.route("/upload", methods=['GET', 'POST'])
def render_page():
    return render_template('upload.html')


@app.route('/uploadsuccess', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        nickname = request.form.get("nickname")
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return render_template('upload.html')
        file = request.files['file']
        # if user does not select file, browser also
        # submit a empty part without filename
        if file.filename == '':
            flash('No selected file')
            return render_template('upload.html')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            mets_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            aip_name = os.path.basename(filename)
            mets = METSFile(mets_path, aip_name, nickname)
            mets.parse_mets()
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename)) # delete file from uploads folder
            return render_template('uploadsuccess.html')

# See https://www.ntu.edu.sg/home/ehchua/programming/webprogramming/Python3_Flask.html
@app.route('/aip/<mets_file>')
def show_aip(mets_file):
    mets_instance = METS.query.filter_by(metsfile='%s' % (mets_file)).first()
    original_files = mets_instance.metslist
    dcmetadata = mets_instance.dcmetadata
    filecount = mets_instance.originalfilecount
    for element in dcmetadata:
        if element['element'] == 'ark identifier':
            aip_uuid = element['value']
            break

    return render_template('aip.html', original_files=original_files,
        mets_file=mets_file, dcmetadata=dcmetadata, filecount=filecount,
        aip_uuid=aip_uuid)


@app.route('/delete/<mets_file>')
def confirm_delete_aip(mets_file):
    return render_template('delete.html', mets_file=mets_file)


@app.route('/deletesuccess/<mets_file>')
def delete_aip(mets_file):
    mets_instance = METS.query.filter_by(metsfile='%s' % (mets_file)).first()
    db.session.delete(mets_instance)
    db.session.commit()
    return render_template('deletesuccess.html')


@app.route('/aip/<mets_file>/file/<ID>')
def show_file(mets_file, ID):
    mets_instances = METS.query.filter_by(metsfile='%s' % (mets_file)).first()
    original_files = mets_instances.metslist
    for original_file in original_files:
        if original_file["id"] == ID:
            target_original_file = original_file
            break
    return render_template('detail.html', original_file=target_original_file, mets_file=mets_file)
