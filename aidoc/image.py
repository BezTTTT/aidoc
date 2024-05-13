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
import datetime

from aidoc.db import get_db
from aidoc.auth import login_required

# 'image' blueprint manages Image upload, AI prediction, and the Diagnosis
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

@bp.route('/diagnosis/dentist', methods=('POST', ))
@login_required
def dentist_diagnosis():

    # Check if submission list is in the queue (session), if so submit them to the Submission Module and the AI Prediction Engine
    # then render the dentist_diagnosis template
    if session.get('imageNameList') is not None:
        lastImageName, ai_prediction, ai_scores = submission()
        data = {
            'imagename':  lastImageName,
            'ai_prediction': ai_prediction,
            'ai_scores': ai_scores,
        }
        return render_template('dentist_diagnosis.html', data=data)
    else:
        return redirect(url_for('dentist'))
    

PER_PAGE = 12 #number images data show on history page per page
@bp.route('/history/dentist', methods=('GET', 'POST'))
@login_required
def dentist_history():

    # Reload the history every time the page is reloaded    
    sql = "SELECT * FROM history WHERE userId = %s"
    val = (data["userId"],)
    mycursor.execute(sql, val)
    res = mycursor.fetchall()
    mydb.commit()
    cls_name = ["NM", "OPMD", "OSCC"]
    for i in range(len(res)):
        res[i]["image_class"] = cls_name[
            np.argmax(list(map(float, res[i]["score"].split())))
        ]
    data["history"] = res

    # Filter data if search query is provided
    search_query = request.args.get("search") 
    filter = request.args.get("filter") 

    if search_query is not None:
        session['history_search'] = search_query
    else:
        search_query = session.get('history_search', '')

    if filter is not None:
        session['history_filter'] = filter
    else:
        filter = session.get('history_filter', '')

    
    # # Initialize an empty list to store filtered results
    filtered_data = []

    # Loop through the data and apply both search and filter criteria
    for item in data["history"]:
        item_comment = item.get("comment", "").lower()
        item_fname = item.get("fname", "").lower()

        # Check if search_query is present in comment or fname
        search_match = (
            search_query.lower() in item_comment or search_query.lower() in item_fname
        )

        # Check if filter matches the comment (split by "~" and compare the first part)
        filter_match = filter.strip() == item_comment.split("~")[0].strip()

        # If there's no search query or the item matches the search query, and there's no filter or the item matches the filter, include it in the filtered_data
        if (not search_query or search_match) and (not filter or filter_match):
            filtered_data.append(item)

    # Sort the filtered data
    filtered_data = sorted(filtered_data, key=lambda x: x["date"], reverse=True)

    # Pagination
    page = request.args.get("page", 1, type=int)
    if request.method == "POST":
        page = request.form.get("current_history_page")
        page = int(page)
        
    total_pages = (len(filtered_data) - 1) // PER_PAGE + 1
    start_idx = (page - 1) * PER_PAGE
    end_idx = start_idx + PER_PAGE
    paginated_data = filtered_data[start_idx:end_idx]
    
        # Format the date in the desired format
    for item in paginated_data:
        item["date"] = datetime.strptime(item["date"], "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y %H.%M")

    return render_template(
            "history.html",
            data=data,
            pagination=paginated_data,
            current_page=page,
            total_pages=total_pages,
            search_query=search_query,
            filter = filter)




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

# Submission Module
def submission():
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
        for filename in session['imageNameList']:
            if os.path.isfile(os.path.join(tempDir, filename)):
                shutil.copy2(os.path.join(tempDir, filename), os.path.join(uploadDir, filename))
                shutil.copy2(os.path.join(tempDir, 'thumb_'+filename), os.path.join(thumbUploadDir, filename))
                shutil.copy2(os.path.join(tempDir, 'outlined_'+filename), os.path.join(outlinedDir, filename))
                shutil.copy2(os.path.join(tempDir, 'thumb_outlined_'+filename), os.path.join(thumbOutlinedDir, filename))
        
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
              
        lastImageName = list(session['imageNameList'])[-1]

        #Clear submission queue in the session
        session.pop('imageNameList', None)

        # If submit multiple image, return only the last image for visualization
        return (lastImageName, ai_predictions[-1], json.loads(ai_scores[-1]))
    else:
        return
