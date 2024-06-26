from flask import Flask
import os

import logging
logger = logging.getLogger('waitress')
logger.setLevel(logging.DEBUG)

# Application Factory
def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    
    # Setup the app configuration file (instance/config.py)
    if test_config is None:
        app.config.from_pyfile('config.py', silent=True) # load the instance config, if it exists, when not testing
    else:
        app.config.from_mapping(test_config) # load the test config if passed in
    # Create Flask instance folder
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Create imageData/* folders
    projectDir = os.path.dirname(app.root_path)
    IMAGE_DATA_DIR = os.path.join(projectDir, 'imageData') 
    app.config['IMAGE_DATA_DIR'] = IMAGE_DATA_DIR
    os.makedirs(IMAGE_DATA_DIR, exist_ok=True)
    os.makedirs(os.path.join(IMAGE_DATA_DIR, 'temp'), exist_ok=True)
    os.makedirs(os.path.join(IMAGE_DATA_DIR, 'recycle'), exist_ok=True)
    os.makedirs(os.path.join(IMAGE_DATA_DIR, 'upload', 'thumbnail'), exist_ok=True)
    os.makedirs(os.path.join(IMAGE_DATA_DIR, 'outlined', 'thumbnail'), exist_ok=True)
    
    # Register blueprints
    from . import auth
    app.register_blueprint(auth.bp)
    from . import image
    app.register_blueprint(image.bp)
    from . import user
    app.register_blueprint(user.bp)

    # Add special endpoints
    app.add_url_rule('/', endpoint='index')

    # Register the click command init-db
    from . import db
    db.init_app(app)

    return app
