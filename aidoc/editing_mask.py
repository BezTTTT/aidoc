import json
from flask import (
    render_template,
    request,
    session,
    Blueprint
)

import cv2 # type: ignore
from scipy.ndimage import zoom # type: ignore
from PIL import Image
import datetime

# aidoc model
# from api.AI_model.constants import *

import ast
import traceback
from utils.import_model import *
from utils.helper import *
from utils.connect_db import mydb,mycursor

import numpy as np

editing_mask_blueprint = Blueprint('editing_mask_blueprint', __name__)


@editing_mask_blueprint.route("/editing_mask", methods=["POST"])
def editing_mask_page():
    mydb.reconnect(attempts=1, delay=0) #reconnect to database if timeout
    # Get Cookies
    data = request.form.get("all_data")
    data = ast.literal_eval(data)
    imagePathSplite = data['image'].split("/", 3)
    data['input_image'] = imagePathSplite[0] + '/' + imagePathSplite[1] + '/inputs/' + imagePathSplite[3]
    data['output_image'] = imagePathSplite[0] + '/' + imagePathSplite[1] + '/outputs/' + imagePathSplite[3]
    outputImage = Image.open(data['output_image'])
    inputImage = Image.open(data['input_image'])
    externalCoordinates, holesCoordinates, outputOriginalShape = generateMark(inputImage, outputImage)
    data['external_masking_path'] = externalCoordinates
    data['internal_masking_path'] = holesCoordinates
    data['output_original_shape'] = outputOriginalShape

    try:
        return (
            render_template(
                "dentists/editing_mask.html",
                data=data,
            ),
            200,
        )
    except Exception as e:
        traceback.print_exc()
        print(e)
        push_log(e)
        return (
            render_template(
                "login.html",
                data=data,
            ),
            200,
        ) 

def generateMark(inputImage, outputImage) :
    # convert to numpy
    inputArr = np.array(inputImage)
    outputArr = np.array(outputImage)
    originalShape = inputArr.shape
    outputOriginalShape = outputArr.shape

    # resize to original
    result = zoom(outputArr, (originalShape[0] / outputArr.shape[0], originalShape[1] / outputArr.shape[1], 1))

    # Convert the image to grayscale
    gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)

    # Threshold the image to create a binary image
    _, thresholded = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY)

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

    return externalCoordinates, holesCoordinates, outputOriginalShape

@editing_mask_blueprint.route("/add_mask", methods=["POST"])
def add_mask():
    mydb.reconnect(attempts=1, delay=0) #reconnect to database if timeout

    outputImage = request.files['mask_file']
    data = request.form.get('all_data')
    
    if data:
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            return jsonify({"error": "Invalid JSON data"}), 400
    else:
        return jsonify({"error": "No data provided"}), 400
    
    outputOriginalShape = data['output_original_shape']
    filename = outputImage.filename 
    originalSize = (outputOriginalShape[1], outputOriginalShape[0])
    img = Image.open(io.BytesIO(outputImage.read()))
    outputImage = img.resize(originalSize)
    file_upload(filename, outputImage, output_image_path)
    inputImage = Image.open(input_image_path + filename)
    outputImage = Image.open(output_image_path + filename)

    result = np.zeros((outputOriginalShape[0], outputOriginalShape[1], 3))
    resultOneHot = tf.one_hot(tf.argmax(result, axis=-1), depth=4)
    resultClass = convert_oh_to_class(resultOneHot) # we can cut this out with tensor.numpy
    outputClass = remove_small_object_3class(resultClass)

    outputBordering = make_bordering_edited_image(outputImage, outputClass)
    outputOverlap = make_overlap_edited_image(inputImage, outputBordering)

    file_upload(filename, outputOverlap, bordering_overlap_image_path)

    sql = "SELECT * FROM patients_history WHERE id = %s"
    val = (data["caseid"],)
    mycursor.execute(sql, val)
    patientHistories = mycursor.fetchall()

    # get patient data
    if patientHistories[0]['userid'] != None:
        #get patient by userId
        sql = "SELECT * FROM patients WHERE id = %s"
        val = (patientHistories[0]['userid'],)
        mycursor.execute(sql, val)
        patient = mycursor.fetchone()

        birthdate = patient['birth_date']
        current_date = datetime.datetime.now()
        age_timedelta = current_date - birthdate
        age_years = age_timedelta.days // 365
        patient['birth_date'] = str(age_years)
        del patient['created_at']
    else:
        patient = None

    return (
        render_template(
            "dentists/checking.html",
            data=data,
            patient=patient,
        ),
        200,
    )

def file_upload(filename, img, path):
    fname = filename 
    image_path = path + str(fname)

    # img = Image.open(io.BytesIO(file.read()))

    lst_of_bad_type = ['tiff','tif','jfif']
    if image_path.rsplit('.', 1)[-1].lower() in lst_of_bad_type:
        filename = image_path.split("/")[-1].rsplit('.', 1)[0] + ".png"
        image_path = "/".join(image_path.split("/")[:-1]) + "/" + filename
        img.save(image_path, format="PNG")
    else:
        if image_path.lower().endswith(".jpg") or image_path.lower().endswith(".jpeg"):
            img = img.convert("RGB")
        img.save(image_path)