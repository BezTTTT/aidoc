from flask import Blueprint, flash, redirect, render_template, request, session, url_for, current_app, g

from werkzeug.utils import secure_filename

from PIL import Image, ImageFilter

import os
import shutil
import json
import datetime
import re

from aidoc.db import get_db
from aidoc.auth import login_required
from aidoc.image import rotate_temp_image, allowed_file, create_thumbnail, oral_lesion_prediction, rename_if_duplicated, convertMask2Cordinates

import imageQualityChecker
qualityChecker = imageQualityChecker.ImageQualityChecker()

bp = Blueprint('general', __name__)

# region general index
@bp.route('/general')
def general_index():
    if g.user is None:
        session.clear() # logged out from everything

    if g.user: # already logged in
        if 'sender_mode' in session and session['sender_mode']=='general':
            return redirect('/general/upload')
    else:
        session['sender_mode'] = 'general'
        return render_template("general_login.html")

# region login
@bp.route('/general/login', methods=('Post',))
def general_login():
    session['sender_mode'] = 'general'
    email = request.form['email']
    error_msg = None
    db, cursor = get_db()
    cursor.execute('SELECT * FROM general_user WHERE email = %s', (email,))
    user = cursor.fetchone()
    if user is None:
        error_msg = "Please register the new user for the first time"
    if error_msg is None: # Logged in sucessfully
        session['user_id'] = user['id']
        return redirect('/general/upload')
    
    flash(error_msg)
    data = {'email': email}
    return render_template("general_register.html", data=data)

# region register
@bp.route('/general/register', methods=('GET', 'POST'))
def general_register():
    data = {}

    if request.method == 'POST':
        # This section extract the submitted form to 
        data["name"] = request.form["name"]
        data["surname"] = request.form["surname"]
        data["email"] = request.form["email"]
        data["job_position"] = request.form["job_position"]
        data["workplace"] = request.form["workplace"]
        data["city"] = request.form["city"]
        data["country"] = request.form["country"]

        data["valid_email"] = True

        email_pattern = r'([A-Za-z0-9]+[.-_])*[A-Za-z0-9]+@[A-Za-z0-9-]+(\.[A-Z|a-z]{2,})+'
        data["valid_email"] = re.fullmatch(email_pattern, data["email"]) is not None
        if not data["valid_email"]:
            flash('Invalid email format')
            return render_template("general_register.html", data=data)
        
        # Create new account if there is no duplicate account, else merge the accounts
        db, cursor = get_db()
        sql = "INSERT INTO general_user (name, surname, email, job_position, workplace, city, country) VALUES (%s,%s,%s,%s,%s,%s,%s)"
        val = (data["name"], data["surname"], data["email"], data["job_position"], data["workplace"], data["city"],data["country"])
        cursor.execute(sql, val)

        # Load the newly registered user to the session (using national_id and is_patient flag)
        cursor.execute('SELECT id FROM general_user where email = %s', (data["email"],))
        new_user = cursor.fetchone()
        session['user_id'] = new_user['id']
        return redirect('/general/upload')
    else:
        return render_template("general_register.html", data=data)

# region upload
@bp.route('/general/upload', methods=('GET', 'POST'))
@login_required
def general_upload():
    data = {}
    session['sender_mode'] = 'general'
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
                    fileName, fileExtension = os.path.splitext(imageFile.filename)
                    fileName = secure_filename(fileName)
                    if fileName != '':
                        imageName = fileName+fileExtension
                    else:
                        newFileName = 'secured_filename'
                        suffix = datetime.now().strftime("%y%m%d_%H%M%S")
                        imageName = "_".join([newFileName, suffix]) + fileExtension 
                    imagePath = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp', imageName)
                    imageFile.save(imagePath)
                    #Create the temp thumbnail
                    pil_img = Image.open(imagePath).convert('RGB')

                    # Check image quality
                    global qualityChecker
                    qualityResults = qualityChecker.predict(pil_img)
                    if qualityResults['Class_ID'] == 0:
                        flash('System detects that the picture failed the quality test. The mouth might be too blury, too small, or too dark (please use flash light). Please send only the high quality images')
                    elif qualityResults['Class_ID'] == 1:
                        flash('System detects that the picture may not contain a mouth. Please follow the guidelines below for taking the oral images')
                    data['imageQuality'] = qualityResults['Class_ID']

                    pil_img = create_thumbnail(pil_img)
                    pil_img.save(os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp', 'thumb_' + imageName)) 
                    # Save the current filenames on session for the upcoming prediction
                    imageNameList.append(imageName)
                else:
                    flash('Only image data are allowed')
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
                upload_general_submission_module()
                lastImageName = list(session['imageNameList'])[-1]
                db, cursor = get_db()
                sql = "SELECT id FROM general_submission_record WHERE fname=%s"
                val = (lastImageName, )
                cursor.execute(sql, val)
                result = cursor.fetchall() # There might be several images of the same name (duplication is checked only the same user upload the same files)
                result = result[-1] # The last image will be selected
                #Clear submission queue in the session
                session.pop('imageNameList', None)
                return redirect(url_for('general.general_diagnosis', img_id=result['id']))

    return render_template("general_upload.html", data=data)

# region dignosis
@bp.route('/general/diagnosis/<int:img_id>', methods=('GET', ))
@login_required
def general_diagnosis(img_id):       

    db, cursor = get_db()
    if session['sender_mode']=='general':
        sql = '''SELECT general_submission_record.id AS img_id, fname, general_sender_id AS sender_id, ai_prediction, ai_scores
                FROM general_submission_record
                WHERE id=%s'''
        
    val = (img_id, )
    cursor.execute(sql, val)
    data = cursor.fetchone()

    # Authorization check
    if data is None:
        return render_template('unauthorized_access.html', error_msg='Data Not Found')
    elif (session['sender_mode']!='general') or (session['sender_mode']=='general' and (session['user_id']!=data['sender_id'])):
        return render_template('unauthorized_access.html', error_msg='Unauthorized Access')

    # Further process the data
    data['ai_scores'] = json.loads(data['ai_scores'])

    return render_template('general_diagnosis.html', data=data)

# region rotate general image
@bp.route('/rotate_general_image/<img_id>', methods=('POST', ))
@login_required
def rotate_general_image(img_id):
    imagename = request.form.get('imagename')
    
    user_id = '0'
    uploadDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'upload', user_id)
    thumbUploadDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'upload', 'thumbnail', user_id)
    outlinedDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'outlined', user_id)
    thumbOutlinedDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'outlined', 'thumbnail', user_id)
    maskDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'mask', user_id)

    imagePath = os.path.join(uploadDir, imagename)
    thumbPath = os.path.join(thumbUploadDir, imagename)
    outlinedPath = os.path.join(outlinedDir, imagename)
    thumbOutlinedImagePath = os.path.join(thumbOutlinedDir, imagename)
    maskPath = os.path.join(maskDir, imagename)

    pil_img = Image.open(imagePath) 
    pil_img = pil_img.rotate(-90, expand=True)
    pil_img.save(imagePath)
    thumb_img = create_thumbnail(pil_img)
    thumb_img.save(thumbPath)

    pil_img = Image.open(outlinedPath) 
    pil_img = pil_img.rotate(-90, expand=True)
    pil_img.save(outlinedPath)
    thumb_img = create_thumbnail(pil_img)
    thumb_img.save(thumbOutlinedImagePath)
    
    pil_img = Image.open(maskPath) 
    pil_img = pil_img.rotate(-90, expand=True)
    pil_img.save(maskPath)

    return redirect(url_for('general.general_diagnosis', img_id=img_id))

# region mask_editor
@bp.route('/general_mask_editor/<img_id>', methods=('POST', ))
@login_required
def mask_editor(img_id):

    imagename = request.form.get('imagename')
    user_id = '0'

    maskDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'mask', user_id)
    outlinedDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'outlined', user_id)
    thumbOutlinedDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'outlined', 'thumbnail', user_id)
    maskPath = os.path.join(maskDir, imagename)
    outlinedPath = os.path.join(outlinedDir, imagename)
    thumbOutlinedImagePath = os.path.join(thumbOutlinedDir, imagename)

    if 'mask_file' in request.files:
        mask_img_file = request.files['mask_file']
        mask_img_file.save(maskPath)
        
        uploadDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'upload', user_id)
        imagePath = os.path.join(uploadDir, imagename)
        input_img = Image.open(imagePath)

        output = Image.open(maskPath).convert('L')
        output = output.resize((512, 342)) # Resize the mask to the standard size
        edge_img = output.filter(ImageFilter.FIND_EDGES)
        dilation_img = edge_img.filter(ImageFilter.MaxFilter(3))
        dilation_img = dilation_img.resize(input_img.size) # Restore the mask size to the original size

        yellow_edge = Image.merge("RGB", (dilation_img, dilation_img, Image.new(mode="L", size=dilation_img.size)))
        outlined_img = input_img.copy()
        outlined_img.paste(yellow_edge, dilation_img)
        outlined_img.save(outlinedPath)
        thumb_img = create_thumbnail(outlined_img)
        thumb_img.save(thumbOutlinedImagePath)

        return redirect(url_for('general.general_diagnosis', img_id=img_id))

    externalCoordinates, holesCoordinates = convertMask2Cordinates(maskPath)
    
    data = {}
    data['owner_id'] = user_id
    data['fname'] = imagename
    data['output_image'] = maskPath
    data['external_masking_path'] = externalCoordinates
    data['internal_masking_path'] = holesCoordinates

    return render_template("general_mask_editor.html", data=data, img_id=img_id)

# region rocompute_image
@bp.route('/recompute_general_image/<img_id>', methods=('POST', ))
@login_required
def recompute_general_image(img_id):
    imagename = request.form.get('imagename')
    
    user_id = '0'
    uploadDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'upload', user_id)
    outlinedDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'outlined', user_id)
    thumbOutlinedDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'outlined', 'thumbnail', user_id)
    maskDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'mask', user_id)
    os.makedirs(maskDir, exist_ok=True)

    imagePath = os.path.join(uploadDir, imagename)
    outlinedPath = os.path.join(outlinedDir, imagename)
    thumbOutlinedImagePath = os.path.join(thumbOutlinedDir, imagename)
    maskPath = os.path.join(maskDir, imagename)

    outlined_img, prediction, scores, mask = oral_lesion_prediction(imagePath)
    outlined_img.save(outlinedPath)
    mask.save(maskPath)

    #Create the thumbnail and saved to temp folder
    pil_img = Image.open(outlinedPath) 
    pil_img = create_thumbnail(pil_img)
    pil_img.save(thumbOutlinedImagePath) 

    db, cursor = get_db()
    sql = "UPDATE general_submission_record SET ai_prediction=%s, ai_scores=%s WHERE id=%s"
    val = (prediction, str(scores), img_id)
    cursor.execute(sql, val)

    return redirect(url_for('general.general_diagnosis', img_id=img_id))

# region upload general submission module
def upload_general_submission_module():
    if session['imageNameList']:
        # Define the related directories
        tempDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp')

        # Model prediction
        ai_predictions = []
        ai_scores = []
        for i, filename in enumerate(session['imageNameList']):
            imgPath = os.path.join(tempDir, filename)
            outlined_img, prediction, scores, mask = oral_lesion_prediction(imgPath)

            outlined_img.save(os.path.join(tempDir, 'outlined_'+filename))
            mask.save(os.path.join(tempDir, 'mask_'+filename))

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
        
        # General public user is always saved to user_id: 0 in the main project
        # To check which files are from which user, please 
        user_id = '0'
        uploadDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'upload', user_id)
        thumbUploadDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'upload', 'thumbnail', user_id)
        outlinedDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'outlined', user_id)
        thumbOutlinedDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'outlined', 'thumbnail', user_id)
        maskDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'mask', user_id)

        # Copy files to the storage
        checked_filename_lst = []
        for filename in session['imageNameList']:
            if os.path.isfile(os.path.join(tempDir, filename)):

                checked_filename = rename_if_duplicated(uploadDir, filename)

                shutil.copy2(os.path.join(tempDir, filename), os.path.join(uploadDir, checked_filename))
                shutil.copy2(os.path.join(tempDir, 'thumb_'+filename), os.path.join(thumbUploadDir, checked_filename))
                shutil.copy2(os.path.join(tempDir, 'outlined_'+filename), os.path.join(outlinedDir, checked_filename))
                shutil.copy2(os.path.join(tempDir, 'thumb_outlined_'+filename), os.path.join(thumbOutlinedDir, checked_filename))
                shutil.copy2(os.path.join(tempDir, 'mask_'+filename), os.path.join(maskDir, checked_filename))

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
            
            sql = "INSERT INTO general_submission_record (fname, general_sender_id, ai_prediction, ai_scores) VALUES (%s,%s,%s,%s)"
            val = (filename, session['user_id'], ai_predictions[i], ai_scores[i])
            cursor.execute(sql, val)
