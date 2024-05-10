from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, current_app
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from PIL import Image
import os

from aidoc.db import get_db
from aidoc.auth import login_required


bp = Blueprint('image', __name__)

@bp.route('/image/dentist', methods=('GET', 'POST'))
@login_required
def dentist_upload():
    if request.method == 'POST':
        
        file = request.files["imageList"]
        filename = secure_filename(file.filename)
        file.save(os.path.join('imageData', 'temp', filename))

        #with Image.open(filename) as im:
        #    upload_path = 'imageData/temp' + filename
        #    im.save(upload_path)

        #if len(imagefile) > 1: #Check if upload multi image
        #    # Go to predict multi files
        #    return multi_upload(imagefile)
    return render_template("dentist_upload_new.html")