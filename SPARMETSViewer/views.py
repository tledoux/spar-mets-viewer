# -*- coding: utf-8 -*-
"""Definition of the routes for the application."""
import os
import time

from flask import jsonify, request, render_template, Response
from flask_babel import gettext
from requests import get, codes
from werkzeug.utils import secure_filename

from SPARMETSViewer import app, babel, db
from config import LANGUAGES

from .models import METS
from .parsemets import METSFile
from .referencedata import ReferenceData
from .rdfquery import label_query, from_sparql_results_to_json


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


@app.route("/labels/<path:label>", methods=['GET'])
def label_access(label):
    """Make a SPARQL query to retrieve a label"""
    platform = app.config['ACCESS_PLATFORM']
    if platform is None:
        return
    results = label_query(label, platform)
    return jsonify(results)


@app.route("/reference", methods=['GET'])
def reference_data_access():
    """Make a SPARQL query to retrieve reference data"""
    platform = app.config['ACCESS_PLATFORM']
    if platform is None:
        return
    kind = request.args.get("kind")
    if not kind:
        return Response("No kind parameter", status=codes.bad_request, mimetype="text/plain")
    ref_data = ReferenceData(platform)
    return jsonify(ref_data.get_data(kind))


@app.route("/reference/<kind>", methods=['GET'])
def reference_data_rest(kind):
    """Make a SPARQL query to retrieve reference data"""
    platform = app.config['ACCESS_PLATFORM']
    if platform is None:
        return

    ref_data = ReferenceData(platform)
    return jsonify(ref_data.get_data(kind))


@app.route("/customquery", methods=['POST'])
def custom_query_json():
    """Make a SPARQL query and get back a simple json for table"""
    # if request.method == 'POST':
    #    query = request.form.get("query")
    # else:
    #    query = request.args.get("query")
    if not request.is_json:
        resp = Response("No json parameters", status=codes.bad_request, mimetype="text/plain")
        return resp
    content = request.get_json()
    platform = app.config['ACCESS_PLATFORM']
    if platform is None:
        return

    endpoint = app.config['ACCESS_ENDPOINT']
    channel = content['filter']['channel']
    app.logger.debug("THL QUERY with %s", channel)
    filter = ""
    if "period" in content['filter']:
        period = content['filter']['period']
        filter += "FILTER (STRSTARTS(STR(?ingest_date), '%s'))" % period
    limit = "OFFSET " + str(content['offset']) + " LIMIT " + str(content['limit'])
    columns = content['columns']
    head = "?ark "
    triples = """?p sparprovenance:hasEvent ?e.
        ?e a sparprovenance:ingestCompletion.
        ?e dc:date ?ingest_date. """
    optional = ""
    withOrder = False
    withReception = False
    for col in columns:
        if col == "ingest_date":
            head += "?ingest_date "
        elif col == "file_count":
            head += "?file_count "
            triples += " ?p sparfixity:fileCount ?file_count. "
        elif col == "size":
            head += "?size "
            triples += " ?p sparfixity:size ?size. "
        elif col == "title":
            head += "?title "
            optional += " OPTIONAL { ?p dc:title ?title } "
        elif col == "creator":
            head += "(GROUP_CONCAT(DISTINCT ?creato; separator=', ') AS ?creator) "
            optional += " OPTIONAL { ?p dc:creator ?creato } "
        elif col == "call_no":
            head += "?call_no "
            optional += " OPTIONAL { ?p sparreference:callNumber ?call_no } "
        elif col == "record_no":
            head += "?record_no "
            optional += " OPTIONAL { ?p dc:relation ?record_no } "
        elif col == "contract_no":
            head += "?contract_no "
            optional += " OPTIONAL { ?p dc:rights ?contract_no } "
        elif col == "order_no":
            withOrder = True
            head += "?order_no "
        elif col == "order_date":
            withOrder = True
            head += "?order_date "
        elif col == "order_issuer":
            withOrder = True
            head += "?order_issuer "
        elif col == "reception_no":
            withReception = True
            head += "?reception_no "
        elif col == "reception_date":
            withReception = True
            head += "?reception_date "
    if withOrder:
        optional += """ OPTIONAL { ?p sparprovenance:hasEvent ?eOrder.
            ?eOrder a sparprovenance:orderPlacing.
            ?eOrder dc:date ?order_date.
            ?eOrder sparprovenance:hasIssuer ?order_issuer.
            ?eOrder dc:description ?order_no. }"""
    if withReception:
        optional += """ OPTIONAL { ?p sparprovenance:hasEvent ?eReception.
            ?eReception a sparprovenance:documentReception.
            ?eReception dc:date ?reception_date.
            ?eReception dc:description ?reception_no. }"""

    queryCount = """SELECT (count(?ark) AS ?total)
        WHERE {
        ?ark sparcontext:hasLastVersion/sparcontext:hasLastRelease ?p.
        GRAPH ?g {
        ?p a sparstructure:group.
        ?p sparcontext:isMemberOf <%s>.
        %s
        %s
        } }""" % (channel, triples, filter)
    if 'total' in content:
        total = int(content['total'])
    elif platform == "TEST":  # long queries on TEST
        total = 2
    else:
        response = get(
            endpoint,
            headers={'Accept': 'application/sparql-results+json'},
            params={'query': queryCount, 'format': 'application/sparql-results+json'})
        if response.status_code != codes.ok:
            resp = Response(
                response.data,
                status=response.status_code,
                mimetype=response.content_type
            )
            return resp
        totals = response.json()
        total = int(totals.get("results").get("bindings")[0].get("total").get("value"))
        app.logger.debug("Find %s results for channel %s", total, channel)

    query = """SELECT
        %s
        WHERE {
        ?ark sparcontext:hasLastVersion/sparcontext:hasLastRelease ?p.
        GRAPH ?g {
        ?p a sparstructure:group.
        ?p sparcontext:isMemberOf <%s>.
        %s %s
        %s
        } } %s""" % (head, channel, triples, optional, filter, limit)

    app.logger.debug("THL QUERY with %s", query)
    if platform == "TEST":  # long queries on TEST
        time.sleep(5)
    response = get(
        endpoint,
        headers={'Accept': 'application/sparql-results+json'},
        params={'query': query, 'format': 'application/sparql-results+json'})
    app.logger.debug("THL SPARQL %s response %s", endpoint, response.status_code)
    if response.status_code != codes.ok:
        resp = Response(response.data, status=response.status_code, mimetype=response.content_type)
        return resp
    results = response.json()
    # app.logger.debug("THL JSON response %s", results)
    return jsonify(from_sparql_results_to_json(results, withCounts=True, count=total))


@app.route("/graph", methods=['GET', 'POST'])
def get_graph():
    """Retrieve the full graph for a given ark"""
    if request.method == 'POST':
        ark = request.form.get("ark")
    else:
        ark = request.args.get("ark")
    if ark is None:
        resp = Response("No ark", status=codes.bad_request, mimetype="text/plain")
        return resp
    ark = app.config['ARK_PREFIX'] + ark.strip()
    app.logger.debug("Get graph with %s", ark)
    platform = app.config['ACCESS_PLATFORM']
    if platform is None:
        return
    endpoint = app.config['ACCESS_ENDPOINT']
    if platform == 'TEST':
        endpoint = app.config['GRAPH_TESTFILE']
    query = """SELECT ?s ?p ?o WHERE {
        <%s> sparcontext:hasLastVersion/sparcontext:hasLastRelease ?arkvr.
        GRAPH ?g {
          ?arkvr a sparstructure:group.
          ?s ?p ?o.
        } """ % ark
    app.logger.debug("Get graph endpoint %s", endpoint)

    response = get(
        endpoint,
        headers={'Accept': 'application/sparql-results+json'},
        params={'query': query, 'format': 'application/sparql-results+json'})
    app.logger.debug("Get graph response %s", response.status_code)
    if response.status_code != codes.ok:
        resp = Response(response.data, status=response.status_code, mimetype=response.content_type)
        return resp
    results = response.json()
    # app.logger.debug("THL JSON response %s", results)
    return jsonify(results)


@app.route("/query", methods=['GET', 'POST'])
def query_json():
    """Make a SPARQL query and get back a simple json for table"""
    if request.method == 'POST':
        query = request.form.get("query")
    else:
        query = request.args.get("query")
    if query is None:
        resp = Response("No query", status=codes.bad_request, mimetype="text/plain")
        return resp
    app.logger.debug("THL QUERY with %s", query)
    platform = app.config['ACCESS_PLATFORM']
    if platform is None:
        return

    endpoint = app.config['ACCESS_ENDPOINT']
    if platform == 'TEST':
        if "SUM(" in query:
            endpoint = app.config['REPORT_ENDPOINT']

    response = get(
        endpoint,
        headers={'Accept': 'application/sparql-results+json'},
        params={'query': query, 'format': 'application/sparql-results+json'})
    app.logger.debug("THL SPARQL response %s", response.status_code)
    if response.status_code != codes.ok:
        resp = Response(response.data, status=response.status_code, mimetype=response.content_type)
        return resp
    results = response.json()
    # app.logger.debug("THL JSON response %s", results)
    return jsonify(from_sparql_results_to_json(results))


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

    response = get(
        endpoint,
        headers={'Accept': 'application/sparql-results+json'},
        params={'query': query, 'format': 'application/sparql-results+json'})
    app.logger.debug("SPARQL response %s", response.status_code)
    return response.content


@app.route("/referenceInfo", methods=['GET', 'POST'])
def reference_info():
    """Access to the reference data"""
    return render_template(
        'reference.html',
        ark_prefix=app.config['ARK_PREFIX'],
        access_platform=app.config['ACCESS_PLATFORM'])


@app.route("/search", methods=['GET', 'POST'])
def search_ark():
    """Access to the search choice"""
    platform = app.config['ACCESS_PLATFORM']
    ref_data = ReferenceData(platform)
    channels = ref_data.get_data("channel")
    return render_template(
        'search.html',
        channels=channels,
        ark_prefix=app.config['ARK_PREFIX'],
        access_platform=platform)


@app.route("/report", methods=['GET', 'POST'])
def report():
    """Access to the search choice"""
    platform = app.config['ACCESS_PLATFORM']
    ref_data = ReferenceData(platform)
    channels = ref_data.get_data("channel")

    return render_template(
        'report.html',
        channels=channels,
        ark_prefix=app.config['ARK_PREFIX'],
        access_platform=platform)


@app.route("/retrieve", methods=['GET', 'POST'])
def retrieve():
    """Access to the retrieve form"""
    platform = app.config['ACCESS_PLATFORM']
    ref_data = ReferenceData(platform)
    channels = ref_data.get_data("channel")

    return render_template(
        'retrieve.html',
        channels=channels,
        ark_prefix=app.config['ARK_PREFIX'],
        access_platform=platform)


@app.route("/explore", methods=['GET', 'POST'])
def explore():
    """Access to explore the graph"""
    ark = None
    if request.method == 'POST':
        ark = request.form.get("ark")
    elif request.method == 'GET':
        ark = request.args.get("ark")

    return render_template(
        'explore.html',
        ark=ark,
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
        nickname = request.form.get("nickname")
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
        name = access_platform
        if nickname:
            name += " - " + nickname
        mets = METSFile(mets_path, aip_name, name)
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
    level = mets_instance.level
    original_files = mets_instance.metslist
    dcmetadata = mets_instance.dcmetadata
    divs = mets_instance.divs
    filecount = mets_instance.originalfilecount
    aip_uuid = mets_file
    for element in dcmetadata:
        tag = element.get('element')
        if tag and tag == 'ark identifier':
            aip_uuid = element['value']
            break

    return render_template(
        'aip.html', original_files=original_files,
        mets_file=mets_file, level=level, dcmetadata=dcmetadata, divs=divs,
        filecount=filecount, aip_uuid=aip_uuid
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
    return render_template(
        'detail.html',
        original_file=target_original_file, mets_file=mets_file)
