from flask import Flask
import os

import logging
log = logging.getLogger('werkzeug')
#log.setLevel(logging.ERROR)
log.setLevel(logging.INFO)

def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    
    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # Create Flask instance folder
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Create imageData/* folders
    projectDir = os.path.dirname(app.root_path)
    IMAGE_DATA_DIR = os.path.join(projectDir, 'imageData') 
    app.config['IMAGE_DATA_DIR'] = IMAGE_DATA_DIR
    try:
        os.makedirs(IMAGE_DATA_DIR)
        os.makedirs(os.path.join(IMAGE_DATA_DIR, 'temp'))
        os.makedirs(os.path.join(IMAGE_DATA_DIR, 'upload'))
        os.makedirs(os.path.join(IMAGE_DATA_DIR, 'outline'))
        os.makedirs(os.path.join(IMAGE_DATA_DIR, 'thumbnail'))
    except OSError:
        pass

    from . import db
    db.init_app(app)
    
    from . import auth
    app.register_blueprint(auth.bp)
    from . import image
    app.register_blueprint(image.bp)

    app.add_url_rule('/', endpoint='index')
    app.add_url_rule('/login/dentist', endpoint='dentist')

    return app