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

import os
import glob
import shutil
import ast
import zipfile
from datetime import datetime
from dateutil.parser import parse

from aidoc.db import get_db

def upload_submission_module(target_user_id,filename,testImgPath):
    # Define the related directories
    tempDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp')

    # Model prediction
    ai_predictions = []
    ai_scores = []

    imgPath = os.path.join(tempDir, filename)
    shutil.copy(testImgPath, imgPath)
    #Create the temp thumbnail
    pil_imgup = Image.open(imgPath).convert('RGB')

    pil_imgup = create_thumbnail(pil_imgup)
    pil_imgup.save(os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp', 'thumb_' + filename)) 
    
    outlined_img, prediction, scores, mask = oral_lesion_prediction(imgPath)

    outlined_img.save(os.path.join(tempDir, 'outlined_'+filename))
    mask.save(os.path.join(tempDir, 'mask_'+filename))

    #Create the thumbnail and saved to temp folder
    pil_img = Image.open(os.path.join(tempDir, 'outlined_'+filename)) 
    pil_img = create_thumbnail(pil_img)
    pil_img.save(os.path.join(current_app.config['IMAGE_DATA_DIR'], 'temp', 'thumb_outlined_' + filename)) 

    ai_predictions.append(prediction)
    ai_scores.append(str(scores))
        
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
    if os.path.isfile(os.path.join(tempDir, filename)):

        checked_filename = rename_if_duplicated(uploadDir, filename)

        shutil.copy2(os.path.join(tempDir, filename), os.path.join(uploadDir, checked_filename))
        shutil.copy2(os.path.join(tempDir, 'thumb_'+filename), os.path.join(thumbUploadDir, checked_filename))
        shutil.copy2(os.path.join(tempDir, 'outlined_'+filename), os.path.join(outlinedDir, checked_filename))
        shutil.copy2(os.path.join(tempDir, 'thumb_outlined_'+filename), os.path.join(thumbOutlinedDir, checked_filename))
        shutil.copy2(os.path.join(tempDir, 'mask_'+filename), os.path.join(maskDir, checked_filename))

        checked_filename_lst.append(checked_filename)

        # Try to clear temp folder if #files are more than CLEAR_TEMP_THRESHOLD
    if len(os.listdir(tempDir)) > current_app.config['CLEAR_TEMP_THRESHOLD']:
        for filename in os.listdir(tempDir):
            if os.path.isfile(os.path.join(tempDir, filename)):
                os.remove(os.path.join(tempDir, filename))

    # update database with the submission records
    # data are saved in session['imageNameList']
    # update_submission_record(ai_predictions, ai_scores)
    return  prediction, scores
        
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