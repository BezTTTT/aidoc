from flask import Flask
import os

# Application Factory
def create_app(test_config=None):

    print('\033[1m' + '\033[93m' + ' AIDOC Application Starting ... ' + '\033[0m')

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
    os.makedirs(os.path.join(IMAGE_DATA_DIR, 'mask'), exist_ok=True)
    os.makedirs(os.path.join(IMAGE_DATA_DIR, 'upload', 'thumbnail'), exist_ok=True)
    os.makedirs(os.path.join(IMAGE_DATA_DIR, 'outlined', 'thumbnail'), exist_ok=True)
    
    # Create folders for the default user_id:0 to save general public submissions
    user_id = '0'
    uploadDir = os.path.join(app.config['IMAGE_DATA_DIR'], 'upload', user_id)
    thumbUploadDir = os.path.join(app.config['IMAGE_DATA_DIR'], 'upload', 'thumbnail', user_id)
    outlinedDir = os.path.join(app.config['IMAGE_DATA_DIR'], 'outlined', user_id)
    thumbOutlinedDir = os.path.join(app.config['IMAGE_DATA_DIR'], 'outlined', 'thumbnail', user_id)
    maskDir = os.path.join(app.config['IMAGE_DATA_DIR'], 'mask', user_id)
    os.makedirs(uploadDir, exist_ok=True)
    os.makedirs(thumbUploadDir, exist_ok=True)
    os.makedirs(outlinedDir, exist_ok=True)
    os.makedirs(thumbOutlinedDir, exist_ok=True)
    os.makedirs(maskDir, exist_ok=True)

    app.config['LEGAL_DIR'] = os.path.join(projectDir, 'legal') 

    # Register blueprints
    from . import auth
    app.register_blueprint(auth.bp)
    from . import image
    app.register_blueprint(image.bp)
    from . import webapp
    app.register_blueprint(webapp.bp)
    from . import user
    app.register_blueprint(user.bp)
    from . import general
    app.register_blueprint(general.bp)
    from .API import report
    app.register_blueprint(report.routes.report_bp)
    from .API import admin
    app.register_blueprint(admin.routes.admin_bp)
    from .API import database_migration
    app.register_blueprint(database_migration.routes.migration_bp)
    from .API import line
    app.register_blueprint(line.routes.line_blueprint)
    
    from . import osm_group
    app.register_blueprint(osm_group.bp, url_prefix='/osm_group')

    # Add special endpoints
    app.add_url_rule('/', endpoint='index')

    # Register the click command init-db
    # Use command: 'flask --app aidoc init-db' to create all tables for the aidoc_development database
    from . import db
    db.init_app(app)

    # Create log file for each application run
    import logging
    from logging.handlers import RotatingFileHandler
    import datetime
    os.makedirs('aidoc_logs', exist_ok=True)
    current_time = datetime.datetime.now()
    current_time_str = current_time.strftime("%d-%b-%Y_%H-%M")
    file_handler = RotatingFileHandler(os.path.join('aidoc_logs', f'aidoc_{current_time_str}.log'), maxBytes=10*2**20, backupCount=10)
    file_handler.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    app.logger.setLevel(logging.DEBUG)
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.DEBUG)
    werkzeug_logger.addHandler(file_handler)
    werkzeug_logger.addHandler(console_handler)

    print('\033[1m' + '\033[93m' + ' AIDOC Application Ready ... ' + '\033[0m')

    return app