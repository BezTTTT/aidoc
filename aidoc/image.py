from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, send_from_directory, current_app
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from PIL import Image
import os

from aidoc.db import get_db
from aidoc.auth import login_required

bp = Blueprint('image', __name__)

# Flask views

@bp.route('/upload/dentist', methods=('GET', 'POST'))
@login_required
def dentist_upload():
    data = {}
    if request.method == 'POST':

        if request.form.get('rotation_submitted'):
            imageName = request.form.get('imagePath')
            rotate_temp_image(imageName)
        else:
            imageName = None
            imageList = request.files.getlist("imageList")
            
            check_clear_temp()
            
            if len(imageList)>0:
                session['imageList'] = imageList
            else:
                session.pop('imageList', None)
                
            for imageFile in imageList: 
                if imageFile and allowed_file(imageFile.filename):
                    imageName = secure_filename(imageFile.filename)
                    imagePath = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp', imageName)
                    imageFile.save(imagePath)

                    #Create the temp thumbnail
                    pil_img = Image.open(imagePath) 
                    MAX_SIZE = (512, 512) 
                    pil_img.thumbnail(MAX_SIZE) 
                    
                    # creating thumbnail 
                    thumbPath = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp', 'thumb_' + imageName)
                    pil_img.save(thumbPath) 

                else:
                    flash('รับข้อมูลเฉพาะที่เป็นรูปภาพเท่านั้น')
        if imageName:
            data['imagePath'] = imageName # Send back path of the last submitted image (if sent for more than 1)
        
    return render_template("dentist_upload_new.html", data=data)

@bp.route('/temp/thumbnail/<path:imagename>')
def get_temp_thumbnail(imagename):
    return send_from_directory(os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp'), 'thumb_'+imagename, as_attachment=True)

# Helper functions

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'tif', 'tiff'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def check_clear_temp():
    # Delete all files in the temp folder if there are more than CLEAR_TEMP_THRESHOLD
    tempDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp')
    if len(os.listdir(tempDir)) > current_app.config['CLEAR_TEMP_THRESHOLD']:
        for filename in os.listdir(tempDir):
            if os.path.isfile(os.path.join(tempDir, filename)):
                os.remove(os.path.join(tempDir, filename))

def rotate_temp_image(imagename):
    imagePath = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp', imagename)
    pil_img = Image.open(imagePath) 
    print(pil_img.size)
    pil_img = pil_img.rotate(-90, expand=True)
    print(pil_img.size)
    pil_img.save(imagePath)

    MAX_SIZE = (512, 512) 
    pil_img.thumbnail(MAX_SIZE) 
    thumbPath = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp', 'thumb_' + imagename)
    pil_img.save(thumbPath) 