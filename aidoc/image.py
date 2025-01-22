from flask import (
    Blueprint, flash, redirect, render_template, request, session, url_for, send_from_directory, send_file, current_app, g,
)
from werkzeug.utils import secure_filename

import tensorflow as tf
import oralLesionNet
# Load the oralLesionNet model to the global variable
model = oralLesionNet.load_model()

import imageQualityChecker
qualityChecker = imageQualityChecker.ImageQualityChecker()

from PIL import Image, ImageFilter
import cv2
import numpy as np
from aidoc.user import validate_province_name,validate_duplicate_users,validate_phone,validate_national_id,remove_prefix,validate_license
import os
import glob
import shutil
import ast
import zipfile
from datetime import datetime
from dateutil.parser import parse

from aidoc.db import get_db
from aidoc.auth import login_required, role_validation
from aidoc.webapp import update_submission_record

# 'image' blueprint manages Image upload, AI prediction, and the Diagnosis
bp = Blueprint('image', __name__)

# Flask views

# region upload_image
@bp.route('/upload_image/<role>', methods=('GET', 'POST'))
@login_required
@role_validation
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
                    print(qualityResults['Class_Name'])
                    if qualityResults['Class_ID'] == 0:
                        flash(f'ระบบตรวจสอบพบว่าไฟล์ {imageName} คุณภาพของรูปไม่ได้มาตรฐาน ภาพช่องปากอาจไม่ชัด (เบลอ) หรือมืดเกินไป (เปิดไฟส่องสว่างช่องปากด้วย) กรุณานำส่งรูปที่ได้คุณภาพเท่านั้น')
                    elif qualityResults['Class_ID'] == 1:
                        flash(f'ระบบตรวจสอบพบว่าไฟล์ {imageName} ไม่ปรากฎช่องปากในภาพ กรุณานำส่งภาพถ่ายที่ได้มุมมองมาตรฐานตามตัวอย่างเท่านั้น')
                    data['imageQuality'] = qualityResults['Class_ID']

                    pil_img = create_thumbnail(pil_img)
                    pil_img.save(os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp', 'thumb_' + imageName)) 
                    # Save the current filenames on session for the upcoming prediction
                    imageNameList.append(imageName)
                else:
                    flash(f'ไฟล์ {imageName} ไม่ใช่ชนิดรูปภาพที่กำหนด ระบบรับข้อมูลเฉพาะที่เป็นชนิดรูปภาพที่กำหนดเท่านั้น')
            if len(imageList)>0:
                # Save the current filenames on session for the upcoming prediction
                session['imageNameList'] = imageNameList
            else:
                session.pop('imageNameList', None)
            if imageName:
                data['uploadedImage'] = imageName # Send back path of the last submitted image (if sent for more than 1)
            if g.user['default_location']:
                location = ast.literal_eval(g.user['default_location'])
                if location['district']:
                    data['default_location_text'] = "สถานที่คัดกรอง: ตำบล"+location['district']+" อำเภอ"+location['amphoe']+" จังหวัด"+location['province']+" " +str(location['zipcode'])
                else:
                    data['default_location_text'] = "สถานที่คัดกรอง: จังหวัด"+location['province']    
            else:
                location = {'district': None,
                            'amphoe': None,
                            'province': g.user['province'],
                            'zipcode': None}
                data['default_location_text'] = "สถานที่คัดกรอง: จังหวัด"+location['province']
        elif submission=='true': # upload confirmation is submitted
            # Check if submission list is in the queue (session), if so submit them to the Submission Module and the AI Prediction Engine
            if 'imageNameList' in session and session['imageNameList']:
                if role=='patient':
                    if request.form.get('inputPhone') is not None and request.form.get('inputPhone')!='':
                        session['sender_phone'] = request.form.get('inputPhone')
                    else:
                        session['sender_phone'] = None
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
                    if request.form.get('patient_id')!='':
                        session['patient_id'] = request.form.get('patient_id')
                    else:
                        session['patient_id'] = None
                if request.form.get('location') is not None and request.form.get('location')!='':
                    session['location'] = ast.literal_eval(request.form.get('location'))
                else:
                    session['location'] = {'district': None,
                                           'amphoe': None,
                                           'province': g.user['province'],
                                           'zipcode': None}
                
                upload_submission_module(target_user_id=session['user_id'])

                lastImageName = list(session['imageNameList'])[-1]
                db, cursor = get_db()
                sql = "SELECT id FROM submission_record WHERE fname=%s"
                val = (lastImageName, )
                cursor.execute(sql, val)
                result = cursor.fetchall() # There might be several images of the same name (duplication is checked only the same user upload the same files)
                result = result[-1] # The last image will be selected
                #Clear submission queue in the session
                session.pop('imageNameList', None)
                if role=='patient':
                    session.pop('sender_phone', None)
                    session.pop('sender_id', None)
                    session.pop('location', None)
                elif role=='osm':
                    session.pop('patient_national_id', None)
                    session.pop('patient_id', None)
                    session.pop('location', None)
                return redirect(url_for('webapp.diagnosis', role=role, img_id=result['id']))
    
    else: # For GET method, check the user compliance on user agreement and informed consent
        from aidoc.user import generate_legal_drafts, get_user_compliance
        data['user_compliance'] = get_user_compliance(session['user_id'])
        if not data['user_compliance']:
            generate_legal_drafts(session['user_id'])
            session['returning_page'] = 'upload_image'
    
    data['earthchieAPI'] = True # enable Earthchie's Thailand Address Auto-complete API
    return render_template(role+"_upload.html", data=data)

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
@role_validation
def delete_image(role):
    img_id = request.form.get('img_id')

    db, cursor = get_db()
    sql = "SELECT channel, sender_id, patient_id, fname FROM submission_record WHERE id=%s"
    val = (img_id, )
    cursor.execute(sql, val)
    result = cursor.fetchone()

    if result['channel']=='PATIENT':
        user_id = str(result['patient_id'])
    else:
        user_id = str(result['sender_id'])
    
    uploadDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'upload', user_id)
    thumbUploadDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'upload', 'thumbnail', user_id)
    outlinedDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'outlined', user_id)
    thumbOutlinedDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'outlined', 'thumbnail', user_id)
    maskDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'mask', user_id)

    recycleDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'recycle', user_id)
    os.makedirs(recycleDir, exist_ok=True)

    filename = result['fname']
    shutil.move(os.path.join(uploadDir, filename), os.path.join(recycleDir, filename))
    os.remove(os.path.join(thumbUploadDir, filename))
    os.remove(os.path.join(outlinedDir, filename))
    os.remove(os.path.join(thumbOutlinedDir, filename))
    os.remove(os.path.join(maskDir, filename))

    sql = "DELETE FROM submission_record WHERE id = %s"
    val = (img_id,)
    cursor.execute(sql, val)
    sql = "DELETE FROM patient_case_id WHERE id = %s"
    val = (img_id,)
    cursor.execute(sql, val)

    return redirect(url_for('image.record', role=role, page=session['current_record_page']))

# region rotate_image
@bp.route('/rotate_image/<return_page>/<role>/<img_id>', methods=('POST', ))
@login_required
def rotate_image(return_page, role, img_id):
    imagename = request.form.get('imagename')
    user_id = request.form.get('user_id')

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

    if return_page=='diagnosis':
        return redirect(url_for('image.diagnosis', role=role, img_id=img_id))

# region mask_editor
@bp.route('/mask_editor/<role>/<img_id>', methods=('POST', ))
@login_required
def mask_editor(role, img_id):

    imagename = request.form.get('imagename')
    user_id = request.form.get('user_id')

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

        return redirect(url_for('image.diagnosis', role=role, img_id=img_id))

    externalCoordinates, holesCoordinates = convertMask2Cordinates(maskPath)

    data = {}
    data['owner_id'] = user_id
    data['fname'] = imagename
    data['output_image'] = maskPath
    data['external_masking_path'] = externalCoordinates
    data['internal_masking_path'] = holesCoordinates

    return render_template("mask_editor.html", data=data, role=role, img_id=img_id)

# region rocompute_image
@bp.route('/recompute_image/<return_page>/<role>/<img_id>', methods=('POST', ))
@login_required
def recompute_image(return_page, role, img_id):
    imagename = request.form.get('imagename')
    user_id = request.form.get('user_id')

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
    sql = "UPDATE submission_record SET ai_prediction=%s, ai_scores=%s, updated_at=%s WHERE id=%s"
    val = (prediction, str(scores), datetime.now(), img_id)
    cursor.execute(sql, val)

    return redirect(url_for('image.'+return_page, role=role, img_id=img_id))

# region download_image
@bp.route('/download_image/<user_id>/<imagename>', methods=('GET', ))
@login_required
def download_image(user_id, imagename):

    uploadDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'upload', user_id)
    outlinedDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'outlined', user_id)
    maskDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'mask', user_id)

    imagePath = os.path.join(uploadDir, imagename)
    outlinedPath =os.path.join(outlinedDir, imagename)
    maskPath = os.path.join(maskDir, imagename)

    zip_filename = os.path.splitext(imagename)
    zip_filename = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp', zip_filename[0] + '_uid_' + user_id + '.zip')
    with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(imagePath, imagename)
        zipf.write(outlinedPath, 'outlined_' + imagename)
        zipf.write(maskPath, 'mask_' + imagename)

    response = send_file(zip_filename, as_attachment=True)
    response.call_on_close(lambda: os.remove(zip_filename))
    return response

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
    
    ### The Connected Component Analysis, requires OpenCV ##########
    analysis = cv2.connectedComponentsWithStats(predictionMask.numpy().astype(dtype='uint8'), 4, cv2.CV_32S)
    (numLabels, labels, stats, centroid) = analysis
    output = np.zeros((342, 512), dtype="uint8")
    maxArea = 0
    for i in range(1, numLabels):
        area = stats[i, cv2.CC_STAT_AREA]
        maxArea = max(maxArea, area)
        if area > 500: 
            componentMask = (labels == i).astype("uint8")*255
            output = cv2.bitwise_or(output, componentMask) 
    predictionMask = tf.convert_to_tensor(output)
    predictionMask = tf.math.equal(predictionMask, 255)
    predictionMask = predictionMask[..., tf.newaxis]
    ################################################################

    pred_mask = tf.squeeze(pred_mask, axis=0)  # Remove batch dimension
    backgroundChannel = pred_mask[:,:,0]
    opmdChannel = pred_mask[:,:,1]
    osccChannel = pred_mask[:,:,2]
    
    #predictionMaskSum = tf.reduce_sum(tf.cast(predictionMask,  tf.int64)) # Count number of pixels in prediction mask
    predictionIndexer = tf.squeeze(predictionMask, axis=-1) # Remove singleton dimension (last index)
    if maxArea>500: # Threshold to cut noises are 500 pixels
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

    # Pillow is used to create the boundary
    # Pillow has a very strong relationship with tensorflow
    output = tf.keras.utils.array_to_img(predictionMask)
    edge_img = output.filter(ImageFilter.FIND_EDGES)
    dilation_img = edge_img.filter(ImageFilter.MaxFilter(3))

    full_img = Image.open(imgPath)
    full_dilation_img = dilation_img.resize(full_img.size, resample=Image.NEAREST)
    mask = output.resize(full_img.size, resample=Image.NEAREST)

    yellow_edge = Image.merge("RGB", (full_dilation_img, full_dilation_img, Image.new(mode="L", size=full_dilation_img.size)))
    outlined_img = full_img.copy()
    outlined_img.paste(yellow_edge, full_dilation_img)
    
    scores = [backgroundScore.numpy().item(), opmdScore.numpy().item(), osccScore.numpy().item()]
    return outlined_img, predictClass, scores, mask

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
            db, cursor = get_db()
            
            if session['sender_mode']=='dentist':
                
                if g.user['default_location'] is None or str(g.user['default_location'])!=str(session['location']):
                    sql = "UPDATE user SET default_location=%s WHERE id=%s"
                    val = (str(session['location']), session['user_id'])
                    cursor.execute(sql, val)
                    load_logged_in_user() # Update the user info on g variable
                sql = '''INSERT INTO submission_record
                    (fname,
                    sender_id,
                    location_district,
                    location_amphoe,
                    location_province,
                    location_zipcode,
                    ai_prediction,
                    ai_scores,
                    channel)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)'''
                val = (filename,
                       session['user_id'],
                       session['location']['district'],
                       session['location']['amphoe'],
                       session['location']['province'],
                       session['location']['zipcode'],
                       ai_predictions[i],
                       ai_scores[i],
                       'DENTIST')
                cursor.execute(sql, val)
            elif session['sender_mode']=='patient':
                if g.user['default_location'] is None or str(g.user['default_location'])!=str(session['location']):
                    sql = "UPDATE user SET default_location=%s WHERE id=%s"
                    val = (str(session['location']), session['user_id'])
                    cursor.execute(sql, val)
                    load_logged_in_user() # Update the user info on g variable
                if 'sender_phone' in session and session['sender_phone']:
                    sql = "UPDATE user SET default_sender_phone=%s WHERE id=%s"
                    val = (session['sender_phone'], session['user_id'])
                    cursor.execute(sql, val)
                    load_logged_in_user() # Update the user info on g variable
                
                if (g.user['default_sender_phone'] and ('sender_phone' not in session or session['sender_phone'] is None)):
                    sql = "UPDATE user SET default_sender_phone=NULL WHERE id=%s"
                    val = (session['user_id'], )
                    cursor.execute(sql, val)
                    load_logged_in_user() # Update the user info on g variable
                
                sql = '''INSERT INTO submission_record 
                        (fname,
                        sender_id,
                        sender_phone,
                        location_district,
                        location_amphoe,
                        location_province,
                        location_zipcode,
                        patient_id,
                        ai_prediction,
                        ai_scores,
                        channel)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'''
                val = (filename,
                        session['sender_id'],
                        session['sender_phone'],
                        session['location']['district'],
                        session['location']['amphoe'],
                        session['location']['province'],
                        session['location']['zipcode'],
                        session['user_id'],
                        ai_predictions[i],
                        ai_scores[i],
                        'PATIENT')
                cursor.execute(sql, val)
                
                cursor.execute("SELECT LAST_INSERT_ID()")
                row = cursor.fetchone()
                sql = "INSERT INTO patient_case_id (id) VALUES (%s)"
                val = (row['LAST_INSERT_ID()'],)
                cursor.execute(sql, val)
            elif session['sender_mode']=='osm':
                if g.user['default_location'] is None or str(g.user['default_location'])!=str(session['location']):
                    sql = "UPDATE user SET default_location=%s WHERE id=%s"
                    val = (str(session['location']), session['user_id'])
                    cursor.execute(sql, val)
                    load_logged_in_user() # Update the user info on g variable
                sql = '''INSERT INTO submission_record 
                        (fname, 
                        sender_id,
                        location_district,
                        location_amphoe,
                        location_province,
                        location_zipcode,
                        patient_id,
                        patient_national_id,
                        ai_prediction,
                        ai_scores,
                        channel)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'''
                val = (filename,
                        session['user_id'],
                        session['location']['district'],
                        session['location']['amphoe'],
                        session['location']['province'],
                        session['location']['zipcode'],
                        session['patient_id'],
                        session['patient_national_id'],
                        ai_predictions[i],
                        ai_scores[i],
                        'OSM')
                cursor.execute(sql, val)
                cursor.execute("SELECT LAST_INSERT_ID()")
                row = cursor.fetchone()
                sql = "INSERT INTO patient_case_id (id) VALUES (%s)"
                val = (row['LAST_INSERT_ID()'],)
                cursor.execute(sql, val)

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
    if isinstance(born,str):
        born = parse(born)
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

def format_thai_datetime(x):
    month_list_th = ['มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน','กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม']
    output_thai_datetime_str = '{} {} {} {}:{}'.format(
        x.strftime('%d'),
        month_list_th[int(x.strftime('%m'))-1],
        int(x.strftime('%Y'))+543,
        x.strftime('%H'),
        x.strftime('%M')
    )
    return output_thai_datetime_str
# Part of the mask editor module
# Developed by Tewarit Somrit
def convertMask2Cordinates(maskPath) :

    img = cv2.imread(maskPath, cv2.IMREAD_GRAYSCALE)

    # Threshold the image to create a binary image
    _, thresholded = cv2.threshold(img,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)

    # Find contours in the binary image with retrieval mode RETR_TREE
    contours, hierarchy = cv2.findContours(thresholded, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)

    newContours = []
    newHierarchy = [[]]

    # Filter out small contours (noise) based on area
    for i, contour in enumerate(contours):
        if (cv2.contourArea(contour) > 10):
            newContours.append(contour)
            newHierarchy[0].append(hierarchy[0][i])

    contours = newContours
    hierarchy = newHierarchy

    # Separate external perimeters and internal contours
    externalContours = []
    internalContours = []

    for i, contour in enumerate(contours):
        if hierarchy[0][i][3] == -1:
            externalContours.append(contour)
        else:
            internalContours.append(contour)

    # Convert the external perimeters to a list of numpy arrays
    externalCoordinates = []
    for externalContour in externalContours:
        externalPath = np.squeeze(externalContour)
        externalCoordinates.append([{'x': int(x), 'y': int(y)} for x, y in externalPath])

    # Convert the internal contours to a list of numpy arrays
    holesCoordinates = []
    for internalContour in internalContours:
        holePath = np.squeeze(internalContour)
        holesCoordinates.append([{'x': int(x), 'y': int(y)} for x, y in holePath])

    return externalCoordinates, holesCoordinates