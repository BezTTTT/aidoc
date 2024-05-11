from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, send_from_directory, current_app
)
from werkzeug.utils import secure_filename


import oralLesionNet
# Load the oralLesionNet model to the global variable
model = oralLesionNet.load_model()

import tensorflow as tf
from PIL import Image, ImageFilter

import os
import shutil

from aidoc.db import get_db
from aidoc.auth import login_required

# image blueprint manages image upload, image management, image processing, and AI prediction
bp = Blueprint('image', __name__)

# Flask views

@bp.route('/upload/dentist', methods=('GET', 'POST'))
@login_required
def dentist_upload():
    data = {}
    if request.method == 'POST':

        if request.form.get('rotation_submitted'):
            imageName = request.form.get('uploadedImage')
            rotate_temp_image(imageName)
        else:
            imageName = None
            imageList = request.files.getlist("imageList")

            imageNameList = []
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

                    # Save the current filenames on session for the upcoming prediction
                    imageNameList.append(imageName)
                else:
                    flash('รับข้อมูลเฉพาะที่เป็นรูปภาพเท่านั้น')
            
            if len(imageList)>0:
                # Save the current filenames on session for the upcoming prediction
                session['imageNameList'] = imageNameList
            else:
                session.pop('imageNameList', None)
        if imageName:
            data['uploadedImage'] = imageName # Send back path of the last submitted image (if sent for more than 1)
        
    return render_template("dentist_upload_new.html", data=data)

@bp.route('/temp/thumbnail/<path:imagename>')
@login_required
def get_temp_thumbnail(imagename):

    # TIFF file is allowed but when displaying on the website, it must be converted to png (saved to temp)
    
    # Check if the file is not tiff, then return the file
    if '.tif' not in imagename.lower() and '.tiff' not in imagename.lower():
        return send_from_directory(os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp'), 'thumb_'+imagename)
    
    if '.tiff' in imagename.lower():
        imagename_png = imagename.replace('.tiff', '.png')
    elif '.tif' in imagename.lower():
        imagename_png = imagename.replace('.tif', '.png')
    
    im = Image.open(os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp', imagename))
    im.save(os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp', 'thumb_'+imagename_png))

    return send_from_directory(os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp'), 'thumb_'+imagename_png)


@bp.route('/submission', methods=('POST', ))
@login_required
def submission():

    # Define the related directories
    tempDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp')
    
    # Model prediction
    for filename in session['imageNameList']:
        imgPath = os.path.join(tempDir, filename)
        outlined_img = oral_lesion_prediction(imgPath)
        outlined_img.save(os.path.join(tempDir, 'outlined_'+filename))

    '''
    # Create directory for the user (using user_id) if not exist
    user_id = str(session['user_id'])
    uploadDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'upload', user_id)
    thumbDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'thumbnail', user_id)



    os.makedirs(thumbDir, exist_ok=True)
    os.makedirs(uploadDir, exist_ok=True)
    
    # Copy files to the storage
    for filename in session['imageNameList']:
        if os.path.isfile(os.path.join(tempDir, filename)):
            shutil.copy2(os.path.join(tempDir, filename), os.path.join(uploadDir, filename))
            shutil.copy2(os.path.join(tempDir, 'thumb_'+filename), os.path.join(thumbDir, filename))
    
    # Try to clear temp folder if #files are more than CLEAR_TEMP_THRESHOLD
    if len(os.listdir(tempDir)) > current_app.config['CLEAR_TEMP_THRESHOLD']:
        for filename in os.listdir(tempDir):
            if os.path.isfile(os.path.join(tempDir, filename)):
                os.remove(os.path.join(tempDir, filename))

    # Add the prediction record to the database

    '''

    return render_template("dentist_upload_new.html")



# Helper functions

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'tif', 'tiff'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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

def create_mask(pred_mask):
  pred_mask = tf.math.argmax(pred_mask, axis=-1)
  pred_mask = pred_mask[..., tf.newaxis]
  return pred_mask[0]

def oral_lesion_prediction(imgPath):
    img = tf.keras.utils.load_img(imgPath, target_size=(342, 512, 3))
    img = tf.expand_dims(img, axis=0)

    global model
    pred_mask = model.predict(img)
    output_mask = create_mask(pred_mask)

    normalPixelCount = tf.reduce_sum(tf.cast(tf.math.equal(output_mask, 0), tf.int64))    
    opmd_mask = tf.cast(tf.math.equal(output_mask, 1), tf.int64)
    oscc_mask = tf.cast(tf.math.equal(output_mask, 2), tf.int64)
    opmdPixelCount = tf.reduce_sum(opmd_mask)
    osccPixelCount = tf.reduce_sum(oscc_mask)
    if osccPixelCount > tf.maximum(opmdPixelCount, osccPixelCount):
        return img
    else:
        if  opmdPixelCount > osccPixelCount:
            output_mask = opmd_mask
        else:
            output_mask = oscc_mask
    
    output = tf.keras.utils.array_to_img(output_mask)
    edge_img = output.filter(ImageFilter.FIND_EDGES)
    dilation_img = edge_img.filter(ImageFilter.MaxFilter(3))

    yellow_edge = Image.merge("RGB", (dilation_img, dilation_img, Image.new(mode="L", size=dilation_img.size)))
    img = tf.squeeze(img, axis=0)
    input_img = tf.keras.utils.array_to_img(img)    
    outlined_img = input_img.copy()
    outlined_img.paste(yellow_edge, dilation_img)
    
    return outlined_img