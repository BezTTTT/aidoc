from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, send_from_directory, current_app, jsonify
)
from werkzeug.utils import secure_filename

####### Disable this section if you are not using the prediction model for speeding up the development process ##########

import tensorflow as tf
import oralLesionNet
# Load the oralLesionNet model to the global variable
model = oralLesionNet.load_model()

#########################################################################################################################

from PIL import Image, ImageFilter

import os
import glob
import shutil
import json
from datetime import date

from aidoc.db import get_db
from aidoc.auth import login_required, role_validation, role_authorization

# 'image' blueprint manages Image upload, AI prediction, and the Diagnosis
bp = Blueprint('image', __name__)

# Flask views

# region upload_image
@bp.route('/upload_image/<role>', methods=('GET', 'POST'))
@login_required
@role_validation
@role_authorization
def upload_image(role):
    data = {}
    session['sender_mode'] = role
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
                    pil_img = create_thumbnail(pil_img)
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
            if 'imageNameList' in session and session['imageNameList']:
                if role=='patient':
                    if request.form.get('inputPhone') is not None and request.form.get('inputPhone')!='':
                        session['sender_phone'] = request.form.get('inputPhone')
                    else:
                        session['sender_phone'] = None

                    if request.form.get('inputZipCode') is not None and request.form.get('inputZipCode')!='':
                        session['zip_code'] = request.form.get('inputZipCode')
                    else:
                        session['zip_code'] = None

                    if request.form.get('sender_id') is not None and request.form.get('sender_id')!='':
                        session['sender_id'] = request.form.get('sender_id')
                    elif session['sender_phone'] is None:
                        session['sender_id'] = session['user_id']
                    else:
                        session['sender_id'] = None

                if role=='osm':
                    if request.form.get('inputIdentityID') is not None and request.form.get('inputIdentityID')!='':
                        session['patient_national_id'] = request.form.get('inputIdentityID')
                    else:
                        session['patient_national_id'] = None

                    if request.form.get('inputZipCode') is not None and request.form.get('inputZipCode')!='':
                        session['zip_code'] = request.form.get('inputZipCode')
                    else:
                        session['zip_code'] = None

                    if request.form.get('patient_id')!='':
                        session['patient_id'] = request.form.get('patient_id')
                    else:
                        session['patient_id'] = None

                if 'sender_id' not in session or session['sender_id']==None:
                    upload_submission_module(target_user_id=session['user_id'])
                else:
                    upload_submission_module(target_user_id=session['sender_id']) # Upload files to the sender folders, not patient's

                lastImageName = list(session['imageNameList'])[-1]

                db, cursor = get_db()
                sql = "SELECT id FROM submission_record WHERE fname=%s"
                val = (lastImageName, )
                cursor.execute(sql, val)
                result = cursor.fetchone()

                #Clear submission queue in the session
                session.pop('imageNameList', None)

                if role=='patient':
                    session.pop('sender_phone', None)
                    session.pop('sender_id', None)
                    session.pop('zip_code', None)
                elif role=='osm':
                    session.pop('patient_national_id', None)
                    session.pop('patient_id', None)
                    session.pop('zip_code', None)

                return redirect(url_for('image.diagnosis', id=result['id']))
    if role=='patient':
        return render_template("patient_upload.html", data=data)
    elif role=='dentist':
        return render_template("dentist_upload.html", data=data)
    elif role=='osm':
        return render_template("osm_upload.html", data=data)
    else:
        return None

# region load_image
@bp.route('/load_image/<folder>/<user_id>/<imagename>')
@login_required
def load_image(folder, user_id, imagename):

    # In the future, please implement the privilege check system (only authorized users can access certain files)

    # folder: temp, upload, upload_thumbnail, outlined, outlined_thumbnail

    # TIFF file is allowed but it cannot be displayed on the website, it must be converted to png (saved to temp)
    # We need to treat tif files differently than other image type
    if '.tif' not in imagename.lower() and '.tiff' not in imagename.lower():
        if 'temp' in folder:
            return send_from_directory(os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp'), 'thumb_'+imagename, conditional=False)
        elif 'thumbnail' in folder:
            folders = folder.split('_')
            return send_from_directory(os.path.join(current_app.config['IMAGE_DATA_DIR'], folders[0], folders[1], user_id), imagename, conditional=False)
        else:
            return send_from_directory(os.path.join(current_app.config['IMAGE_DATA_DIR'], folder, user_id), imagename, conditional=False)
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
            return send_from_directory(os.path.dirname(saved_name), os.path.basename(saved_name), conditional=False)
        else:
            if 'thumbnail' in folder:
                folders = folder.split('_')
                im = Image.open(os.path.join(current_app.config['IMAGE_DATA_DIR'], folders[0], folders[1], user_id, imagename))
                if 'outlined' in folder:
                    saved_name = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp', 'thumb_outlined_'+imagename_png)
                else:
                    saved_name = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp', imagename_png)
                im.save(saved_name)
                return send_from_directory(os.path.dirname(saved_name), os.path.basename(saved_name), conditional=False)
            else:
                im = Image.open(os.path.join(current_app.config['IMAGE_DATA_DIR'], folder, user_id, imagename))
                im.save(os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp', imagename_png))
                return send_from_directory(os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp'), imagename_png, conditional=False)

# region delete_image
@bp.route('/delete_image/<role>', methods=('POST', ))
@login_required
def delete_image(role):
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
    
    if 'need_db_refresh' in session:
        session['need_db_refresh']=True

    return redirect(url_for('image.record', role=role))
    
    
# region diagnosis
@bp.route('/diagnosis/<int:id>', methods=('GET', 'POST'))
@login_required
def diagnosis(id):
    if request.method=='POST':
        if request.args.get('special_request')=='true':
            db, cursor = get_db()
            sql = "UPDATE submission_record SET special_request=%s WHERE id=%s"
            val = ( 1, session.get('img_id'))
            cursor.execute(sql, val)
            session.pop('img_id', None)
            if 'need_db_refresh' in session:
                session['need_db_refresh']=True

        if 'feedback_submit' in request.form and 'img_id' in session and session['sender_mode']=='dentist':
            dentist_feedback_code = request.form.get('agree_option')
            dentist_feedback_location = request.form.get('lesion_location')
            dentist_feedback_lesion = request.form.get('lesion_type')
            dentist_feedback_comment = request.form.get('dentist_comment')
            db, cursor = get_db()
            sql = "UPDATE submission_record SET dentist_feedback_code=%s, dentist_feedback_comment=%s, dentist_feedback_lesion=%s, dentist_feedback_location=%s WHERE id=%s"
            val = (dentist_feedback_code, dentist_feedback_comment, dentist_feedback_lesion, dentist_feedback_location, session.get('img_id'))
            cursor.execute(sql, val)
            session.pop('img_id', None)
            if 'need_db_refresh' in session:
                session['need_db_refresh']=True
            
    if session['sender_mode']=='dentist':
        if 'img_id' not in session or session['img_id']!=id: # Check if the image is already loaded to the session
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
    
    if session['sender_mode']=='patient':
        if 'img_id' not in session or session['img_id']!=id: # Check if the image is already loaded to the session
            db, cursor = get_db()
            sql = "SELECT * FROM submission_record INNER JOIN patient_case_id ON submission_record.id=patient_case_id.id WHERE submission_record.id=%s"
            val = (id, )
            cursor.execute(sql, val)
            result = cursor.fetchone()
            session['img_id'] = result['id']
            session['img_fname'] = result['fname']
            session['img_sender_id'] = result['sender_id']
            session['img_ai_prediction'] = result['ai_prediction']
            session['img_ai_scores'] = json.loads(result['ai_scores'])
            session['img_dentist_feedback_code'] = result['dentist_feedback_code']
            session['img_dentist_feedback_comment'] = result['dentist_feedback_comment']
            session['img_dentist_feedback_lesion'] = result['dentist_feedback_lesion']
            session['img_dentist_feedback_location'] = result['dentist_feedback_location']

            session['case_id'] = result['case_id']
            session['special_request'] = result['special_request']
        return render_template('patient_diagnosis.html')
    
    if session['sender_mode']=='osm':
        if 'img_id' not in session or session['img_id']!=id: # Check if the image is already loaded to the session
            db, cursor = get_db()
            sql = "SELECT * FROM submission_record INNER JOIN patient_case_id ON submission_record.id=patient_case_id.id WHERE submission_record.id=%s"
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

            session['case_id'] = result['case_id']
            session['special_request'] = result['special_request']
        return render_template('osm_diagnosis.html')
# region record
@bp.route('/record/<role>', methods=('GET', 'POST'))
@login_required
@role_validation
@role_authorization
def record(role): # Submission records
   
    if session['sender_mode'] != role: # Check role switching
        session['need_db_refresh']=True
        session['sender_mode'] = role

    if 'need_db_refresh' not in session or \
        session.get('need_db_refresh')==True or \
        request.args.get('refresh', default='false', type=str)=='true':
        session['need_db_refresh']=False
    
        # Reload the record every time the page is reloaded
        db, cursor = get_db()
        if role=='specialist':
            sql = '''SELECT submission_record.id, case_id, fname, name, surname, birthdate,
                        sender_id, patient_id, dentist_id, special_request, province,
                        dentist_feedback_comment,dentist_feedback_code,
                        ai_prediction, submission_record.created_at
                    FROM submission_record
                    INNER JOIN user ON submission_record.patient_id = user.id
                    INNER JOIN patient_case_id ON submission_record.id = patient_case_id.id
                    WHERE user.is_patient = TRUE OR user.is_osm = TRUE'''
            cursor.execute(sql)
        else:
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
        if role=='specialist':
            record_comment = record.get("dentist_feedback_comment")
            record_fname = record.get("fname").lower()
            record_agree = record.get("dentist_feedback_code")
            record_name = record.get("name")
            record_surname = record.get("surname")
            if (not search_query or search_query in record_comment or search_query in record_fname or \
                    search_query in record_name or search_query in record_surname) and \
                (not agree or agree==record_agree):
                filtered_data.append(record)
        else:
            record_comment = record.get("dentist_feedback_comment")
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
        if 'current_record_page' in session:
            page = session['current_record_page']
        else:
            page = 1
        
    PER_PAGE = 12 #number images data show on record page per page
    total_pages = (len(filtered_data) - 1) // PER_PAGE + 1
    start_idx = (page - 1) * PER_PAGE
    end_idx = start_idx + PER_PAGE
    paginated_data = filtered_data[start_idx:end_idx]
    
    # Format the date in the desired format
    for item in paginated_data:
        item["formatted_created_at"] = item["created_at"].strftime("%d/%m/%Y %H:%M")
        if "birthdate" in item:
            item["age"] = calculate_age(item["birthdate"])

    data = {}
    data['search'] = search_query
    data['agree'] = agree
    
    session['current_record_page'] = page

    if role=='dentist':
        return render_template(
                "dentist_record.html",
                data=data,
                pagination=paginated_data,
                current_page=page,
                total_pages=total_pages)
    elif role=='osm':
        return render_template(
                "osm_record.html",
                data=data,
                pagination=paginated_data,
                current_page=page,
                total_pages=total_pages)
    elif role=='specialist':
        return render_template(
                "specialist_record.html",
                data=data,
                pagination=paginated_data,
                current_page=page,
                total_pages=total_pages)

# Helper functions
# region create_thumbnail
def create_thumbnail(pil_img):
    MAX_SIZE = 342
    width = pil_img.size[0]
    height = pil_img.size[1]
    if height < MAX_SIZE:
        new_height = MAX_SIZE
        new_width  = int(new_height * width / height)
        pil_img = pil_img.resize((new_width, new_height), Image.NEAREST)
        if new_width > MAX_SIZE:
            canvas = Image.new(pil_img.mode, (new_width, new_width), (255, 255, 255))
            canvas.paste(pil_img)
            pil_img = canvas.resize((MAX_SIZE, MAX_SIZE), Image.NEAREST)
    else:
        pil_img.thumbnail((MAX_SIZE,MAX_SIZE))
    return pil_img

# region allowed_files
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'tif', 'tiff'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# region rotate_temp_image
def rotate_temp_image(imagename):
    imagePath = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp', imagename)
    pil_img = Image.open(imagePath) 
    pil_img = pil_img.rotate(-90, expand=True)
    pil_img.save(imagePath)

    # Create the thumbnails
    pil_img = create_thumbnail(pil_img)
    pil_img.save(os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp', 'thumb_' + imagename))

# region oral_lesion_prediction
# AI Prediction Engine
def oral_lesion_prediction(imgPath):
    
    #import tensorflow as tf
    
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

# region upload_submission_module
# Upload Submission Module
def upload_submission_module(target_user_id):
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
            pil_img = create_thumbnail(pil_img)
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
        user_id = str(target_user_id)
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
            
            if session['sender_mode']=='dentist':
                sql = "INSERT INTO submission_record (fname, sender_id, ai_prediction, ai_scores) VALUES (%s,%s,%s,%s)"
                val = (filename, session['user_id'], ai_predictions[i], ai_scores[i])
                cursor.execute(sql, val)
            elif session['sender_mode']=='patient':

                if ('sender_phone' in session and session['sender_phone']) or ('zip_code' in session and session['zip_code']):
                    sql = "UPDATE user SET default_sender_phone=%s, default_zip_code=%s WHERE id=%s"
                    val = (session['sender_phone'], session['zip_code'], session['user_id'])
                    cursor.execute(sql, val)

                sql = '''INSERT INTO submission_record 
                        (fname,
                        sender_id,
                        sender_phone,
                        zip_code,
                        patient_id,
                        ai_prediction,
                        ai_scores)
                        VALUES (%s,%s,%s,%s,%s,%s,%s)'''
                val = (filename,
                        session['sender_id'],
                        session['sender_phone'],
                        session['zip_code'],
                        session['user_id'],
                        ai_predictions[i],
                        ai_scores[i])
                cursor.execute(sql, val)
                
                cursor.execute("SELECT LAST_INSERT_ID()")
                row = cursor.fetchone()
                sql = "INSERT INTO patient_case_id (id) VALUES (%s)"
                val = (row['LAST_INSERT_ID()'],)
                cursor.execute(sql, val)

            elif session['sender_mode']=='osm':

                if ('patient_national_id' in session and session['patient_national_id']) or ('zip_code' in session and session['zip_code']):
                    sql = "UPDATE user SET default_zip_code=%s WHERE id=%s"
                    val = (session['zip_code'], session['user_id'])
                    cursor.execute(sql, val)

                sql = '''INSERT INTO submission_record 
                        (fname, 
                        sender_id,
                        zip_code,
                        patient_id,
                        patient_national_id,
                        ai_prediction,
                        ai_scores)
                        VALUES (%s,%s,%s,%s,%s,%s,%s)'''
                val = (filename,
                        session['user_id'],
                        session['zip_code'],
                        session['patient_id'],
                        session['patient_national_id'],
                        ai_predictions[i],
                        ai_scores[i])
                cursor.execute(sql, val)

                cursor.execute("SELECT LAST_INSERT_ID()")
                row = cursor.fetchone()
                sql = "INSERT INTO patient_case_id (id) VALUES (%s)"
                val = (row['LAST_INSERT_ID()'],)
                cursor.execute(sql, val)

            if 'need_db_refresh' in session:
                session['need_db_refresh']=True

# region rename_if_duplicated
# Rename the filename if duplicates in the user folder, By appending a running number
def rename_if_duplicated(uploadDir, checked_filename):

    file_parts = os.path.splitext(checked_filename)
    duplicate_files = glob.glob(os.path.join(uploadDir, file_parts[0] + '**'))
    if len(duplicate_files)==0:
        return checked_filename
    else:
        runningNumber = len(duplicate_files)
    
    while (os.path.isfile(os.path.join(uploadDir, checked_filename))):
        file_parts = os.path.splitext(checked_filename)
        checked_filename = file_parts[0] + '_' + str(runningNumber) + file_parts[1]
        runningNumber+=1
        
    return checked_filename


def calculate_age(born):
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))