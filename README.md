# spar-mets-viewer

Une application Web pour aider l'exploration des fichiers METS de [SPAR](http://www.bnf.fr/fr/professionnels/spar_systeme_preservation_numerique.html), directement inspiré de [METSFlask](https://github.com/timothyryanwalsh/METSFlask) pour Archivematica.

Pour que le fichier soit interprété correctement, il doit être conforme au [profil générique des METS pour le système SPAR](https://www.loc.gov/standards/mets/profiles/00000039.xml).

----

A web application for human-friendly exploration of [SPAR](http://www.bnf.fr/fr/professionnels/spar_systeme_preservation_numerique.html) METS files
directly inspired by [METSFlask](https://github.com/timothyryanwalsh/METSFlask) for Archivematica

For the file to be correctly read, it needs to comply with the [Generic METS profile for the SPAR system](https://www.loc.gov/standards/mets/profiles/00000039.xml).

## Install locally (dev):  
(Tested with Python 3.5, including pip and virtualenv)

* Clone files and cd to directory:  
`git clone https://github.com/tledoux/spar-mets-viewer.git && cd spar-mets-viewer` 
* Set up virtualenv:  
`virtualenv venv` 
* Activate virtualenv:  
`source venv/bin/activate`  or `source venv/Scripts/activate` (on Windows)
* Install requirements:  
`pip install -r requirements.txt` 
* Create database:  
`chmod a+x db_create.py`  
`./db_create.py`
* Eventually, extract the strings to be translated:  
`pybabel extract -F babel.cfg -o SPARMETSViewer/messages.pot SPARMETSViewer`
* Update them if necessary (currently only english and french is available):  
`pybabel update -i SPARMETSViewer/messages.pot -d SPARMETSViewer/translations`
* Compile the translations:  
`pybabel compile -d SPARMETSViewer/translations`
* Run (on localhost, port 5000):  
`./run.py`  
* Go to `localhost:5000` in browser. 

## Configuration

If you need to specify local settings, instead of modifing `config.py`,
you can define the `METSVIEWER_SETTINGS` environment variable to locate a file.
This file, say `production_config.py`, will define the parameters you want to locally set and that will 
overide the ones defined by default in `config.py`.