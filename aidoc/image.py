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
import json
from datetime import datetime

from aidoc.db import get_db
from aidoc.auth import login_required

# 'image' blueprint manages Image upload, AI prediction, and the Diagnosis
bp = Blueprint('image', __name__)

# Flask views

@bp.route('/upload/dentist', methods=('GET', 'POST'))
@login_required
def dentist_upload():
    data = {}
    session['sender_mode'] = 'dentist'
    submission = request.args.get('submission', default='false', type=str)
    if request.method == 'POST':
        if request.form.get('rotation_submitted'):
            imageName = request.form.get('uploadedImage')
            rotate_temp_image(imageName)
            data = {'uploadedImage': imageName}
        elif submission=='false': # Load and show the image, wait for the confirmation
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
                    pil_img.save(os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp', 'thumb_' + imageName)) 

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
        
        elif submission=='true': # upload confirmation is submitted

            # Check if submission list is in the queue (session), if so submit them to the Submission Module and the AI Prediction Engine
            if session.get('imageNameList') is not None:
                upload_submission_module()
                lastImageName = list(session['imageNameList'])[-1]

                db, cursor = get_db()
                sql = "SELECT id FROM submission_record WHERE fname=%s"
                val = (lastImageName, )
                cursor.execute(sql, val)
                result = cursor.fetchone()

                #Clear submission queue in the session
                session.pop('imageNameList', None)

                return redirect(url_for('image.diagnosis', id=result['id']))
    return render_template("dentist_upload.html", data=data)

@bp.route('/load_image/<folder>/<user_id>/<imagename>')
@login_required
def load_image(folder, user_id, imagename):

    # In the future, please implement the privilege check system (only authorized users can access certain files)

    # folder: temp, upload, upload_thumbnail, outlined, outlined_thumbnail

    # TIFF file is allowed but it cannot be displayed on the website, it must be converted to png (saved to temp)
    # We need to treat tif files differently than other image type
    if '.tif' not in imagename.lower() and '.tiff' not in imagename.lower():
        if 'temp' in folder:
            return send_from_directory(os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp'), 'thumb_'+imagename)
        elif 'thumbnail' in folder:
            folders = folder.split('_')
            return send_from_directory(os.path.join(current_app.config['IMAGE_DATA_DIR'], folders[0], folders[1], user_id), imagename)
        else:
            return send_from_directory(os.path.join(current_app.config['IMAGE_DATA_DIR'], folder, user_id), imagename)
    else:
        # If tif, create the equivalent png and save to temp
        if '.tiff' in imagename.lower():
            imagename_png = imagename.replace('.tiff', '.png')
        elif '.tif' in imagename.lower():
            imagename_png = imagename.replace('.tif', '.png')

        if 'temp' in folder:
            im = Image.open(os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp', 'thumb_'+imagename))
            saved_name = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp', 'thumb_'+imagename_png)
            im.save(saved_name)
            return send_from_directory(os.path.dirname(saved_name), os.path.basename(saved_name))
        else:
            if 'thumbnail' in folder:
                folders = folder.split('_')
                im = Image.open(os.path.join(current_app.config['IMAGE_DATA_DIR'], folders[0], folders[1], user_id, imagename))
                if 'outlined' in folder:
                    saved_name = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp', 'thumb_outlined_'+imagename_png)
                else:
                    saved_name = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp', imagename_png)
                im.save(saved_name)
                return send_from_directory(os.path.dirname(saved_name), os.path.basename(saved_name))
            else:
                im = Image.open(os.path.join(current_app.config['IMAGE_DATA_DIR'], folder, user_id, imagename))
                im.save(os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp', imagename_png))
                return send_from_directory(os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp'), imagename_png)

@bp.route('/delete_image', methods=('POST', ))
@login_required
def delete_image():
    img_id = request.form.get('img_id')

    db, cursor = get_db()
    sql = "SELECT sender_id, fname FROM submission_record WHERE id=%s"
    val = (img_id, )
    cursor.execute(sql, val)
    result = cursor.fetchone()

    user_id = str(result['sender_id'])
    uploadDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'upload', user_id)
    thumbUploadDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'upload', 'thumbnail', user_id)
    outlinedDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'outlined', user_id)
    thumbOutlinedDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'outlined', 'thumbnail', user_id)
    
    recycleDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'recycle', user_id)
    os.makedirs(recycleDir, exist_ok=True)

    filename = result['fname']
    shutil.move(os.path.join(uploadDir, filename), os.path.join(recycleDir, filename))
    os.remove(os.path.join(thumbUploadDir, filename))
    os.remove(os.path.join(outlinedDir, filename))
    os.remove(os.path.join(thumbOutlinedDir, filename))

    sql = "DELETE FROM submission_record WHERE id = %s"
    val = (img_id,)
    cursor.execute(sql, val)
    
    if session.get('need_db_refresh') is not None:
        session['need_db_refresh']=True

    if session['sender_mode']=='dentist':
        return redirect(url_for('image.dentist_history'))
    
@bp.route('/diagnosis/<int:id>', methods=('GET', 'POST'))
@login_required
def diagnosis(id):
    if request.method=='POST':
        if request.form.get('feedback_submit') != None and session.get('img_id') is not None:
            dentist_feedback_code = request.form.get('agree_option')
            dentist_feedback_location = request.form.get('lesion_location')
            dentist_feedback_lesion = request.form.get('lesion_type')
            dentist_feedback_comment = request.form.get('dentist_comment')
            db, cursor = get_db()
            sql = "UPDATE submission_record SET dentist_feedback_code=%s, dentist_feedback_comment=%s, dentist_feedback_lesion=%s, dentist_feedback_location=%s WHERE id=%s"
            val = (dentist_feedback_code, dentist_feedback_comment, dentist_feedback_lesion, dentist_feedback_location, session.get('img_id'))
            cursor.execute(sql, val)
            session.pop('img_id', None)
            if session.get('need_db_refresh') is not None:
                session['need_db_refresh']=True
            
    if session['sender_mode']=='dentist':
        if session.get('img_id') is None or session['img_id']!=id:
            db, cursor = get_db()
            sql = "SELECT * FROM submission_record WHERE id=%s"
            val = (id, )
            cursor.execute(sql, val)
            result = cursor.fetchone()
            session['img_id'] = result['id']
            session['img_fname'] = result['fname']
            session['img_ai_prediction'] = result['ai_prediction']
            session['img_ai_scores'] = json.loads(result['ai_scores'])
            session['img_dentist_feedback_code'] = result['dentist_feedback_code']
            session['img_dentist_feedback_comment'] = result['dentist_feedback_comment']
            session['img_dentist_feedback_lesion'] = result['dentist_feedback_lesion']
            session['img_dentist_feedback_location'] = result['dentist_feedback_location']
        return render_template('dentist_diagnosis.html')
    

PER_PAGE = 12 #number images data show on history page per page
@bp.route('/history/dentist', methods=('GET', 'POST'))
@login_required
def dentist_history():

    session['sender_mode'] = 'dentist'

    if session.get('need_db_refresh') is None or session.get('need_db_refresh')==True:
        session['need_db_refresh']=False
    
        # Reload the history every time the page is reloaded
        db, cursor = get_db()
        sql = "SELECT * FROM submission_record WHERE sender_id = %s"
        val = (session["user_id"],)
        cursor.execute(sql, val)
        db_query = cursor.fetchall()
        session['saved_db_query'] = db_query
    else:
        db_query = session['saved_db_query']
    
    # Filter data if search query is provided
    search_query = request.args.get("search", "") 
    agree = request.args.get("agree", "") 

    # # Initialize an empty list to store filtered results
    filtered_data = []

    # Loop through the data and apply both search and filter criteria
    for record in db_query:
        record_comment = record.get("dentist_feedback_comment").lower()
        record_fname = record.get("fname").lower()
        record_agree = record.get("dentist_feedback_code")

        if (not search_query or search_query in record_comment or search_query in record_fname) and \
            (not agree or agree==record_agree):
            filtered_data.append(record)

    # Sort the filtered data
    filtered_data = sorted(filtered_data, key=lambda x: x["created_at"], reverse=True)

    # Pagination
    page = request.args.get("page", 1, type=int)
    if request.method == "POST":
        page = request.form.get("current_history_page", 1, type=int)
        page = int(page)
        
    total_pages = (len(filtered_data) - 1) // PER_PAGE + 1
    start_idx = (page - 1) * PER_PAGE
    end_idx = start_idx + PER_PAGE
    paginated_data = filtered_data[start_idx:end_idx]
    
    # Format the date in the desired format
    for item in paginated_data:
        item["formatted_created_at"] = item["created_at"].strftime("%d/%m/%Y %H:%M")

    data = {}
    data['search'] = search_query
    data['agree'] = agree
    
    return render_template(
            "dentist_history.html",
            data=data,
            pagination=paginated_data,
            current_page=page,
            total_pages=total_pages)

# Helper functions

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'tif', 'tiff'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def rotate_temp_image(imagename):
    imagePath = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp', imagename)
    pil_img = Image.open(imagePath) 
    pil_img = pil_img.rotate(-90, expand=True)
    pil_img.save(imagePath)

    # Create the thumbnails
    MAX_SIZE = (512, 512) 
    pil_img.thumbnail(MAX_SIZE) 
    pil_img.save(os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp', 'thumb_' + imagename))

# AI Prediction Engine
def oral_lesion_prediction(imgPath):
    img = tf.keras.utils.load_img(imgPath, target_size=(342, 512, 3))
    img = tf.expand_dims(img, axis=0)

    global model
    pred_mask = model.predict(img)

    output_mask = tf.math.argmax(pred_mask, axis=-1)
    output_mask = output_mask[..., tf.newaxis]
    output_mask = output_mask[0]

    predictionMask = tf.math.not_equal(output_mask, 0)

    pred_mask = tf.squeeze(pred_mask, axis=0)  # Remove batch dimension
    backgroundChannel = pred_mask[:,:,0]
    opmdChannel = pred_mask[:,:,1]
    osccChannel = pred_mask[:,:,2]
    
    predictionMaskSum = tf.reduce_sum(tf.cast(predictionMask,  tf.int64)) # Count number of pixels in prediction mask
    predictionIndexer = tf.squeeze(predictionMask, axis=-1) # Remove singleton dimension (last index)
    if predictionMaskSum>200: # Threshold to cut noises are 200 pixels
        opmdScore = tf.reduce_mean(opmdChannel[predictionIndexer])
        osccScore = tf.reduce_mean(osccChannel[predictionIndexer])
        backgroundScore = tf.reduce_mean(backgroundChannel[predictionIndexer])
        if opmdScore>osccScore:
            predictClass = 1
        else:
            predictClass = 2
    else:
        backgroundIndexer = tf.math.logical_not(predictionIndexer)
        opmdScore = tf.reduce_mean(opmdChannel[backgroundIndexer])
        osccScore = tf.reduce_mean(osccChannel[backgroundIndexer])
        backgroundScore = tf.reduce_mean(backgroundChannel[backgroundIndexer])
        predictClass = 0

    output = tf.keras.utils.array_to_img(predictionMask)
    edge_img = output.filter(ImageFilter.FIND_EDGES)
    dilation_img = edge_img.filter(ImageFilter.MaxFilter(3))

    full_img = Image.open(imgPath)
    full_dilation_img = dilation_img.resize(full_img.size, resample=Image.NEAREST)

    yellow_edge = Image.merge("RGB", (full_dilation_img, full_dilation_img, Image.new(mode="L", size=full_dilation_img.size)))
    outlined_img = full_img.copy()
    outlined_img.paste(yellow_edge, full_dilation_img)
    
    scores = [backgroundScore.numpy(), opmdScore.numpy(), osccScore.numpy()]
    return outlined_img, predictClass, scores

# Upload Submission Module
def upload_submission_module():
    if session['imageNameList']:
        # Define the related directories
        tempDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp')

        # Model prediction
        ai_predictions = []
        ai_scores = []
        for i, filename in enumerate(session['imageNameList']):
            imgPath = os.path.join(tempDir, filename)
            outlined_img, prediction, scores = oral_lesion_prediction(imgPath)
            outlined_img.save(os.path.join(tempDir, 'outlined_'+filename))

            #Create the thumbnail and saved to temp folder
            pil_img = Image.open(os.path.join(tempDir, 'outlined_'+filename)) 
            MAX_SIZE = (512, 512) 
            pil_img.thumbnail(MAX_SIZE) 
            pil_img.save(os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp', 'thumb_outlined_' + filename)) 

            ai_predictions.append(prediction)
            ai_scores.append(str(scores))
        
        if session['imageNameList']:
            session['ai_predictions'] = ai_predictions
            session['ai_infos'] = ai_scores
        else:
            session.pop('ai_predictions', None)
            session.pop('ai_infos', None)
        
        # Create directory for the user (using user_id) if not exist
        user_id = str(session['user_id'])
        uploadDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'upload', user_id)
        thumbUploadDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'upload', 'thumbnail', user_id)
        outlinedDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'outlined', user_id)
        thumbOutlinedDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'outlined', 'thumbnail', user_id)
        os.makedirs(uploadDir, exist_ok=True)
        os.makedirs(thumbUploadDir, exist_ok=True)
        os.makedirs(outlinedDir, exist_ok=True)
        os.makedirs(thumbOutlinedDir, exist_ok=True)

        # Copy files to the storage
        checked_filename_lst = []
        for filename in session['imageNameList']:
            if os.path.isfile(os.path.join(tempDir, filename)):

                checked_filename = rename_if_duplicated(uploadDir, filename)

                shutil.copy2(os.path.join(tempDir, filename), os.path.join(uploadDir, checked_filename))
                shutil.copy2(os.path.join(tempDir, 'thumb_'+filename), os.path.join(thumbUploadDir, checked_filename))
                shutil.copy2(os.path.join(tempDir, 'outlined_'+filename), os.path.join(outlinedDir, checked_filename))
                shutil.copy2(os.path.join(tempDir, 'thumb_outlined_'+filename), os.path.join(thumbOutlinedDir, checked_filename))

                checked_filename_lst.append(checked_filename)
        session['imageNameList'] = checked_filename_lst

        # Try to clear temp folder if #files are more than CLEAR_TEMP_THRESHOLD
        if len(os.listdir(tempDir)) > current_app.config['CLEAR_TEMP_THRESHOLD']:
            for filename in os.listdir(tempDir):
                if os.path.isfile(os.path.join(tempDir, filename)):
                    os.remove(os.path.join(tempDir, filename))

        # Add the prediction record to the database
        for i, filename in enumerate(session['imageNameList']):
            db, cursor = get_db()
            sql = "INSERT INTO submission_record (fname, sender_id, ai_prediction, ai_scores) VALUES (%s,%s,%s,%s)"
            val = (filename, session['user_id'], ai_predictions[i], ai_scores[i])
            cursor.execute(sql, val)

            if session.get('need_db_refresh') is not None:
                session['need_db_refresh']=True

# Rename the filename if duplicates in the user folder, By appending a running number
def rename_if_duplicated(uploadDir, checked_filename):

    underscore_splits = checked_filename.split('_')
    extension_splits = underscore_splits[-1].split('.')
    if len(underscore_splits)>1:
        runningNumber = int(extension_splits[0])
        previouslyDuplicate = True
    else:
        runningNumber = 1
        previouslyDuplicate = False
        
    while (os.path.isfile(os.path.join(uploadDir, checked_filename))):
        if previouslyDuplicate:
            underscores_merge = '_'.join(underscore_splits[:-1])
            checked_filename = underscores_merge + '_' + str(runningNumber+1) + '.' + extension_splits[1]
        else:
            file_parts = os.path.splitext(checked_filename)
            checked_filename = file_parts[0] + '_' + str(runningNumber) + file_parts[1]
        runningNumber+=1
        previouslyDuplicate = True
        underscore_splits = checked_filename.split('_')
    return checked_filename