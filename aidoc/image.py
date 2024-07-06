from flask import (
    Blueprint, flash, redirect, render_template, request, session, url_for, send_from_directory, send_file, current_app, jsonify
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
import zipfile
from datetime import datetime, date
from dateutil.parser import parse

from aidoc.db import get_db
from aidoc.auth import login_required, role_validation

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
                    session.pop('zip_code', None)
                elif role=='osm':
                    session.pop('patient_national_id', None)
                    session.pop('patient_id', None)
                    session.pop('zip_code', None)
                return redirect(url_for('image.diagnosis', role=role, img_id=result['id']))
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
    sql = "SELECT sender_id, fname FROM submission_record WHERE id=%s"
    val = (img_id, )
    cursor.execute(sql, val)
    result = cursor.fetchone()

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
    sql = "UPDATE submission_record SET ai_prediction=%s, ai_scores=%s WHERE id=%s"
    val = (prediction, str(scores), img_id)
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

 # region quick_confirm
@bp.route('/quick_confirm/<role>/<int:img_id>', methods=('POST', ))
@login_required
@role_validation
def quick_confirm(role, img_id):
    if role=='specialist':
        ai_result = request.args.get('ai_result', type=int)
        if ai_result==0:
            diagnostic_code = 'NORMAL'
        elif ai_result==1:
            diagnostic_code = 'OPMD'
        else:
            diagnostic_code = 'OSCC'
        db, cursor = get_db()
        sql = "UPDATE submission_record SET dentist_id=%s, dentist_feedback_code=%s, dentist_feedback_date=%s, updated_at=%s WHERE id=%s"
        val = ( session["user_id"], diagnostic_code, datetime.now(), datetime.now(), img_id)
        cursor.execute(sql, val)
    return redirect(url_for('image.record', role=role, page=session['current_record_page']))

# region diagnosis
@bp.route('/diagnosis/<role>/<int:img_id>', methods=('GET', 'POST'))
@login_required
@role_validation
def diagnosis(role, img_id):
    if request.method=='POST':
        db, cursor = get_db()
        if request.args.get('special_request')=='true':
            sql = "UPDATE submission_record SET special_request=%s WHERE id=%s"
            val = (1, img_id)
            cursor.execute(sql, val)

        if role=='dentist' and 'feedback_submit' in request.form:
            dentist_feedback_code = request.form.get('agree_option')
            dentist_feedback_location = request.form.get('lesion_location')
            dentist_feedback_lesion = request.form.get('lesion_type')
            dentist_feedback_comment = request.form.get('dentist_comment')
            sql = "UPDATE submission_record SET dentist_feedback_code=%s, dentist_feedback_comment=%s, dentist_feedback_lesion=%s, dentist_feedback_location=%s WHERE id=%s"
            val = (dentist_feedback_code, dentist_feedback_comment, dentist_feedback_lesion, dentist_feedback_location, img_id)
            cursor.execute(sql, val)
        
        if role=='specialist' and request.args.get('specialist_feedback')=='true':
            dentist_feedback_code = request.form.get('dt_comment_option')
            dentist_feedback_lesion = None
            dentist_feedback_location = None
            dentist_feedback_comment = ''
            if dentist_feedback_code=='BAD_IMG':
                dentist_feedback_comment = request.form.get('BadImgCommentSelectOptions')
            elif dentist_feedback_code=='OPMD' or dentist_feedback_code=='OSCC':
                dentist_feedback_lesion = request.form.get('LesionTypeSelection')
                dentist_feedback_location = request.form.get('LesionLocationSelection')
            elif dentist_feedback_code=='OTHER':
                dentist_feedback_comment = request.form.get('OtherCommentTextarea', '')
            sql = '''UPDATE submission_record SET
                        dentist_id=%s,
                        dentist_feedback_code=%s,
                        dentist_feedback_comment=%s,
                        dentist_feedback_lesion=%s,
                        dentist_feedback_location=%s,
                        dentist_feedback_date=%s,
                        updated_at=%s
                    WHERE id=%s'''
            val = (session["user_id"],
                   dentist_feedback_code,
                   dentist_feedback_comment,
                   dentist_feedback_lesion,
                   dentist_feedback_location,
                   datetime.now(),
                   datetime.now(),
                   img_id)
            cursor.execute(sql, val)

    db, cursor = get_db()
    if role=='specialist':
        sql = '''SELECT submission_record.id AS img_id, case_id, fname, special_request,
                    patient_id, patient.name AS patient_name, patient.surname AS patient_surname, patient_national_id as saved_patient_national_id, patient.national_id AS db_patient_national_id, patient.birthdate,
                    patient.sex, patient.job_position, patient.email, patient.phone AS patient_phone, patient.address, patient.province,
                    sender_id, sender.name AS sender_name, sender.surname AS sender_surname, sender.hospital AS sender_hospital, sender.province AS sender_province,
                    sender.phone AS sender_phone_db, sender_phone,
                    dentist_id, dentist.name AS dentist_name, dentist.surname AS dentist_surname,
                    dentist_feedback_code, dentist_feedback_comment, dentist_feedback_lesion, dentist_feedback_location, dentist_feedback_date,
                    ai_prediction, ai_scores, submission_record.created_at
                FROM submission_record
                INNER JOIN patient_case_id ON submission_record.id = patient_case_id.id
                LEFT JOIN user AS sender ON submission_record.sender_id = sender.id
                LEFT JOIN user AS patient ON submission_record.patient_id = patient.id
                LEFT JOIN user AS dentist ON submission_record.dentist_id = dentist.id
                WHERE submission_record.id=%s'''
    elif role=='osm':
        sql = '''SELECT submission_record.id AS img_id, case_id, fname, special_request, sender_id, patient_id, sender_phone, sender.phone AS osm_phone, 
                    patient.name AS patient_name, patient.surname AS patient_surname, patient_national_id as saved_patient_national_id, patient.national_id AS db_patient_national_id, patient.birthdate,
                    patient.sex, patient.job_position, patient.email, patient.phone AS patient_phone, patient.address, patient.province,
                    ai_prediction, ai_scores, submission_record.created_at
                FROM submission_record
                INNER JOIN patient_case_id ON submission_record.id=patient_case_id.id
                LEFT JOIN user AS sender ON submission_record.sender_phone = sender.phone
                LEFT JOIN user AS patient ON submission_record.patient_id = patient.id
                WHERE submission_record.id=%s'''
    elif role=='dentist':
        sql = '''SELECT submission_record.id AS img_id, fname, sender_id,
                    dentist_feedback_code, dentist_feedback_comment, dentist_feedback_lesion, dentist_feedback_location,
                    ai_prediction, ai_scores
                FROM submission_record
                WHERE id=%s'''
    else:
        sql = '''SELECT submission_record.id AS img_id, case_id, fname, special_request, sender_id, patient_id, sender_phone, 
                    ai_prediction, ai_scores, submission_record.created_at
                FROM submission_record
                INNER JOIN patient_case_id ON submission_record.id=patient_case_id.id
                WHERE submission_record.id=%s'''
        
    val = (img_id, )
    cursor.execute(sql, val)
    data = cursor.fetchone()

    # Authorization check
    if data is None:
        return render_template('unauthorized_access.html', error_msg='ไม่พบข้อมูลที่ร้องขอ Data Not Found')
    elif (session['sender_mode']!=role) or \
        (role=='patient' and (session['user_id']!=data['patient_id'])) or \
        (role=='osm' and session['user_id']!=data['sender_id'] and data['sender_phone']!=data['osm_phone']) or \
        (role=='dentist' and session['user_id']!=data['sender_id']):
            return render_template('unauthorized_access.html', error_msg='คุณไม่มีสิทธิ์เข้าถึงข้อมูล Unauthorized Access')

    # Further process the data
    data['ai_scores'] = json.loads(data['ai_scores'])
    data['owner_id'] = data['sender_id']
    
    if role=='patient' and data['sender_id'] is None: # If an unregistered osm submit the data via the patient system, the data will be stored in the patient_id folder
        data['sender_id'] = data['patient_id']

    if role=='osm' or role=='specialist':
        if data['sender_phone'] != None or data['sender_id'] == None:
            data['owner_id'] = data['patient_id']
        
        data['thai_datetime'] = format_thai_datetime(data['created_at'])

        if role=='specialist':
            if data['patient_id']!=data['sender_id']:
                if 'sender_name' in data and data['sender_name'] is not None:
                    data['sender_description'] = f"{data['sender_name']} {data['sender_surname']} (เจ้าหน้าที่ผู้นำส่งข้อมูล, เบอร์โทรติดต่อ: {data['sender_phone_db']})"
                else:
                    data['sender_description'] = f"เจ้าหน้าที่ผู้นำส่งข้อมูล เบอร์โทรติดต่อ: {data['sender_phone']} (ยังไม่ได้ลงทะเบียน)"
            else:
                data['sender_description'] = f"{data['sender_name']} {data['sender_surname']} (ผู้ป่วยนำส่งรูปด้วยตัวเอง)"
        else: # osm
            data['sender_description'] = f"{session['user']['name']} {session['user']['surname']} (โทรศัพท์: {session['user']['phone']})"
            data['sender_hospital'] = session['user']['hospital']
            data['sender_province'] = session['user']['province']

        if 'birthdate' in data and data['birthdate'] is not None:
            data['patient_age'] = calculate_age(data['birthdate'])
            if data['sex']=='M':
                data['sex']='ชาย'
            elif data['sex']=='F':
                data['sex']='หญิง'

    dentist_diagnosis_map = {'NORMAL': 'ยืนยันว่าไม่พบรอยโรค (Normal)',
                                'OPMD': 'น่าจะมีรอยโรคที่คล้ายกันกับ OPMD',
                                'OSCC': 'น่าจะมีรอยโรคที่คล้ายกันกับ OSCC',
                                'BAD_IMG': 'ภาพถ่ายที่ส่งมายังไม่ได้มาตรฐาน ทำให้วินิจฉัยไม่ได้',
                                'OTHER': 'อื่น ๆ'
                            }
    bad_image_map = {'NON_STANDARD': 'มุมมองไม่ได้มาตรฐาน',
                     'BLUR': 'ภาพเบลอ ไม่ชัด',
                     'DARK': 'ภาพช่องปากมืดเกินไป ขอเปิดแฟลชด้วย',
                     'SMALL': 'ช่องปากเล็กเกินไป ขอนำกล้องเข้าใกล้ปากมากกว่านี้'
                    }
    lesion_location_map = {1: 'ริมฝีปากบนและล่าง (Lip)',
                           2: 'กระพุ้งแก้มด้านขวาด้านซ้าย (Buccal mucosa)',
                           3: 'เหงือกบนและล่าง (Gingiva)',
                           4: 'เหงือกด้านหลังฟันกรามล่าง (Retromolar area)',
                           5: 'เพดานแข็ง (Hard palate)',
                           6: 'เพดานอ่อน (Soft palate)',
                           7: 'ลิ้นด้านบนและด้านข้าง (Dorsal and lateral tongue)',
                           8: 'ใต้ลิ้น (Ventral tongue)',
                           9: 'พื้นปาก (Floor of mouth)'
                           }
    lesion_type_map = {1: 'รอยโรคสีขาว',
                       2: 'รอยโรคสีแดง',
                       3: 'รอยโรคสีขาวปนแดง',
                       4: 'รอยแผลถลอก',
                       5: 'ลักษณะเป็นก้อน'
                       }
    maps = {'dentist_diagnosis_map': dentist_diagnosis_map,
            'bad_image_map': bad_image_map,
            'lesion_location_map': lesion_location_map,
            'lesion_type_map': lesion_type_map}
    return render_template(role+'_diagnosis.html', data=data, maps=maps)
    
# region record
@bp.route('/record/<role>', methods=('GET', 'POST'))
@login_required
@role_validation
def record(role): # Submission records
   
    session['sender_mode'] = role
    if role=='patient': # Not available for patient
        return render_template('unauthorized_access.html', error_msg='ไม่พบข้อมูลที่ร้องขอ Data Not Found')

    # Reload the record every time the page is reloaded
    db, cursor = get_db()
    if role=='specialist':
        sql = '''SELECT submission_record.id, case_id, fname, patient_user.name, patient_user.surname, patient_user.birthdate,
                    sender_id, patient_id, dentist_id, sender_phone, special_request, patient_user.province,
                    dentist_feedback_comment,dentist_feedback_code,
                    ai_prediction, submission_record.created_at
                FROM submission_record
                INNER JOIN patient_case_id ON submission_record.id = patient_case_id.id
                LEFT JOIN user AS patient_user ON submission_record.patient_id = patient_user.id'''
        cursor.execute(sql)
    elif role=='osm':
        sql = '''SELECT submission_record.id, fname,
                    patient_user.name, patient_user.surname, patient_user.birthdate, patient_user.province,
                    case_id, sender_id, patient_id, dentist_id, special_request, sender_phone, 
                    dentist_feedback_comment,dentist_feedback_code,
                    ai_prediction, submission_record.created_at
                FROM submission_record
                INNER JOIN patient_case_id ON submission_record.id = patient_case_id.id
                LEFT JOIN user AS patient_user ON submission_record.patient_id = patient_user.id
                LEFT JOIN user AS sender_user ON submission_record.sender_phone = sender_user.phone
                WHERE sender_id = %s OR submission_record.sender_phone is not NULL'''
        val = (session["user_id"],)
        cursor.execute(sql, val)
    else:
        sql = '''SELECT submission_record.id, fname, name, surname, birthdate,
                    sender_id, patient_id, dentist_id, special_request, province,
                    dentist_feedback_comment,dentist_feedback_code,
                    ai_prediction, submission_record.created_at
                FROM submission_record
                LEFT JOIN user ON submission_record.patient_id = user.id
                WHERE sender_id = %s'''
        val = (session["user_id"],)
        cursor.execute(sql, val)
    db_query = cursor.fetchall()
    
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
    
    # Process each item in paginated_data
    for item in paginated_data:
        if 'sender_phone' in item and (item['sender_phone'] != None or item['sender_id'] == None):
            item['owner_id'] = item['patient_id']
        else:
            item['owner_id'] = item['sender_id']
        item["formatted_created_at"] = item["created_at"].strftime("%d/%m/%Y %H:%M")
        if ("birthdate" in item and item["birthdate"]):
            item["age"] = calculate_age(item["birthdate"])

    data = {}
    data['search'] = search_query
    data['agree'] = agree
    
    session['current_record_page'] = page

    return render_template(
                role + "_record.html",
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
    mask = output.resize(full_img.size, resample=Image.NEAREST)

    yellow_edge = Image.merge("RGB", (full_dilation_img, full_dilation_img, Image.new(mode="L", size=full_dilation_img.size)))
    outlined_img = full_img.copy()
    outlined_img.paste(yellow_edge, full_dilation_img)
    
    scores = [backgroundScore.numpy(), opmdScore.numpy(), osccScore.numpy()]
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
        
        # Create directory for the user (using user_id) if not exist
        user_id = str(target_user_id)
        uploadDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'upload', user_id)
        thumbUploadDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'upload', 'thumbnail', user_id)
        outlinedDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'outlined', user_id)
        thumbOutlinedDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'outlined', 'thumbnail', user_id)
        maskDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'mask', user_id)
        os.makedirs(uploadDir, exist_ok=True)
        os.makedirs(thumbUploadDir, exist_ok=True)
        os.makedirs(outlinedDir, exist_ok=True)
        os.makedirs(thumbOutlinedDir, exist_ok=True)
        os.makedirs(maskDir, exist_ok=True)

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
            
            if session['sender_mode']=='dentist':
                sql = "INSERT INTO submission_record (fname, sender_id, ai_prediction, ai_scores) VALUES (%s,%s,%s,%s)"
                val = (filename, session['user_id'], ai_predictions[i], ai_scores[i])
                cursor.execute(sql, val)
            elif session['sender_mode']=='patient':

                if ('sender_phone' in session and session['sender_phone']) or ('zip_code' in session and session['zip_code']):
                    sql = "UPDATE user SET default_sender_phone=%s, default_zip_code=%s WHERE id=%s"
                    val = (session['sender_phone'], session['zip_code'], session['user_id'])
                    cursor.execute(sql, val)
                
                if (session['user']['default_sender_phone'] and ('sender_phone' not in session or session['sender_phone'] is None)):
                    sql = "UPDATE user SET default_sender_phone=NULL WHERE id=%s"
                    val = (session['user_id'], )
                    cursor.execute(sql, val)

                if (session['user']['default_zip_code'] and ('zip_code' not in session or session['zip_code'] is None)):
                    sql = "UPDATE user SET default_zip_code=NULL WHERE id=%s"
                    val = (session['user_id'], )
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
        month_list_th[int(x.strftime('%m'))+1],
        int(x.strftime('%Y'))+543,
        x.strftime('%H'),
        x.strftime('%M')
    )
    return output_thai_datetime_str
    
