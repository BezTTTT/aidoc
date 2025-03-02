import io
import base64
import numpy as np
import tensorflow as tf
import cv2
import os
import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from PIL import Image, ImageFilter
from contextlib import asynccontextmanager
import logging
from logging.handlers import RotatingFileHandler

# Logging configuration
os.makedirs('aidoc_logs/ai', exist_ok=True)
current_time_str = datetime.datetime.now().strftime("%d-%b-%Y_%H-%M")
log_file = os.path.join('aidoc_logs', 'ai', f'aidoc_ai_{current_time_str}.log')
file_handler = RotatingFileHandler(log_file, maxBytes=10*2**20, backupCount=10)
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%d/%b/%Y %H:%M:%S")
file_handler.setFormatter(formatter)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

# Configure the root logger.
root_logger = logging.getLogger()
root_logger.handlers.clear()  # Clear any existing handlers.
root_logger.setLevel(logging.INFO)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

# Also, configure uvicorn's loggers so that they use the same handlers.
uvicorn_error_logger = logging.getLogger("uvicorn.error")
uvicorn_error_logger.handlers.clear()
uvicorn_error_logger.setLevel(logging.INFO)
uvicorn_error_logger.addHandler(file_handler)
uvicorn_error_logger.addHandler(console_handler)

uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.handlers.clear()
uvicorn_access_logger.setLevel(logging.INFO)
uvicorn_access_logger.addHandler(file_handler)
uvicorn_access_logger.addHandler(console_handler)

# Request model that contains the image file path.
class PredictRequest(BaseModel):
    imgPath: str

# Global variables for our models
model = None           # For oral lesion prediction
quality_checker = None # For image quality checking

# Lifespan event: load both models at startup.
@asynccontextmanager
async def lifespan(app: FastAPI):
    global model, quality_checker
    try:
        # Load oral lesion prediction model.
        import oralLesionNet
        model = oralLesionNet.load_model()
        logging.info("Oral lesion prediction model loaded successfully.")

        # Load image quality checker.
        import imageQualityChecker
        quality_checker = imageQualityChecker.ImageQualityChecker()
        logging.info("Image quality checker loaded successfully.")
    except Exception as e:
        logging.critical(f"Error loading models: {e}")
        raise e
    yield
    # Optional: add any cleanup code here.

app = FastAPI(lifespan=lifespan)

def pil_to_base64(img: Image.Image) -> str:
    """Convert a PIL image to a base64-encoded PNG."""
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

@app.post("/predict")
async def predict(request: PredictRequest):
    """
    Oral lesion prediction endpoint.
    Accepts a JSON payload with key 'imgPath'.
    Returns an outlined image (base64-encoded), predicted class,
    scores, and a mask (base64-encoded).
    """
    imgPath = request.imgPath
    try:
        # Load and preprocess image for lesion prediction.
        img = tf.keras.utils.load_img(imgPath, target_size=(342, 512, 3))
        img = tf.keras.preprocessing.image.img_to_array(img)
        img = tf.expand_dims(img, axis=0)  # Add batch dimension

        global model
        pred_mask = model.predict(img)

        # Perform prediction (remains a Tensor)
        try:
            # Ensure eager execution is enabled
            tf.config.run_functions_eagerly(True)
            pred_mask = model.predict(img)  # Standard prediction
        except RuntimeError as e: ### 🔹 Handle `model.predict(img)` RuntimeError 🔹 ###
            error_msg = f"⚠️ RuntimeError in model.predict(): {e}"
            print(error_msg)
            logging.error(error_msg)
            print("🔄 Attempting to enable eager execution and retry...")
            try:
                import oralLesionNet
                tf.config.run_functions_eagerly(True)
                model = oralLesionNet.load_model()
                pred_mask = model.predict(img)
            except Exception as e:
                error_msg = f"❌ Critical Error: Fallback prediction also failed! Error: {e}"
                print(error_msg)
                logging.critical(error_msg)
                restart_fastapi_app()

        try:
            # Process prediction mask.
            output_mask = tf.math.argmax(pred_mask, axis=-1, output_type=tf.int32)
            output_mask = tf.expand_dims(output_mask[0], axis=-1)  # Remove batch dimension
            predictionMask = tf.math.not_equal(output_mask, 0)
            predictionMask_np = tf.cast(predictionMask, tf.uint8).numpy()  # Convert Tensor to NumPy
        except AttributeError as e:
            error_msg = f"⚠️ AttributeError: Failed to convert predictionMask to NumPy. Error: {e}"
            logging.error(error_msg)
            print("🔄 Attempting to evaluate using tf.keras.backend.eval() as fallback...")
            try:
                tf.config.run_functions_eagerly(True)
                model = oralLesionNet.load_model() # Reload model
                pred_mask = model.predict(img) # Re-predict
                output_mask = tf.math.argmax(pred_mask, axis=-1, output_type=tf.int32)
                output_mask = tf.expand_dims(output_mask[0], axis=-1)
                predictionMask = tf.math.not_equal(output_mask, 0)
                predictionMask_np = tf.keras.backend.eval(tf.cast(predictionMask, tf.uint8))  # Alternative conversion
            except Exception as e:
                error_msg = f"❌ Critical Error: Fallback conversion also failed! Error: {e}"
                print(error_msg)
                logging.critical(error_msg)
                restart_fastapi_app()

        # Connected Component Analysis with OpenCV.
        analysis = cv2.connectedComponentsWithStats(predictionMask_np, 4, cv2.CV_32S)
        (numLabels, labels, stats, centroids) = analysis
        output = np.zeros((342, 512), dtype="uint8")
        maxArea = 0

        for i in range(1, numLabels):
            area = stats[i, cv2.CC_STAT_AREA]
            maxArea = max(maxArea, area)
            if area > 500:
                componentMask = (labels == i).astype("uint8") * 255
                output = cv2.bitwise_or(output, componentMask)

        # Convert OpenCV output back to TensorFlow tensor.
        predictionMask = tf.convert_to_tensor(output, dtype=tf.uint8)
        predictionMask = tf.math.equal(predictionMask, 255)
        predictionMask = tf.expand_dims(predictionMask, axis=-1)

        # Process channels from the original prediction.
        pred_mask = tf.squeeze(pred_mask, axis=0)
        backgroundChannel, opmdChannel, osccChannel = tf.unstack(pred_mask, axis=-1)

        predictionIndexer = tf.squeeze(predictionMask, axis=-1)
        if maxArea > 500:
            opmdScore = tf.reduce_mean(tf.boolean_mask(opmdChannel, predictionIndexer))
            osccScore = tf.reduce_mean(tf.boolean_mask(osccChannel, predictionIndexer))
            backgroundScore = tf.reduce_mean(tf.boolean_mask(backgroundChannel, predictionIndexer))
            predictClass = tf.cond(opmdScore > osccScore, lambda: 1, lambda: 2)
        else:
            backgroundIndexer = tf.math.logical_not(predictionIndexer)
            opmdScore = tf.reduce_mean(tf.boolean_mask(opmdChannel, backgroundIndexer))
            osccScore = tf.reduce_mean(tf.boolean_mask(osccChannel, backgroundIndexer))
            backgroundScore = tf.reduce_mean(tf.boolean_mask(backgroundChannel, backgroundIndexer))
            predictClass = 0

        # Generate edge image for visualization.
        output_img = tf.keras.utils.array_to_img(predictionMask)
        edge_img = output_img.filter(ImageFilter.FIND_EDGES)
        dilation_img = edge_img.filter(ImageFilter.MaxFilter(3))

        # Load full-size original image.
        full_img = Image.open(imgPath)
        full_dilation_img = dilation_img.resize(full_img.size, resample=Image.NEAREST)
        mask_img = output_img.resize(full_img.size, resample=Image.NEAREST)

        yellow_edge = Image.merge("RGB", (
            full_dilation_img,
            full_dilation_img,
            Image.new(mode="L", size=full_dilation_img.size)
        ))
        outlined_img = full_img.copy()
        outlined_img.paste(yellow_edge, full_dilation_img)

        scores = [
            backgroundScore.numpy().item(),
            opmdScore.numpy().item(),
            osccScore.numpy().item()
        ]
        if isinstance(predictClass, tf.Tensor):
            predictClass = int(predictClass.numpy())
        else:
            predictClass = int(predictClass)

        return {
            "outlined_img": pil_to_base64(outlined_img),
            "predictClass": predictClass,
            "scores": scores,
            "mask": pil_to_base64(mask_img)
        }
    except Exception as e:
        logging.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/predict_quality")
async def predict_quality(request: PredictRequest):
    """
    Image quality prediction endpoint.
    Accepts a JSON payload with key 'imgPath'.
    Loads the image, runs quality prediction using the ImageQualityChecker,
    and returns the result as JSON.
    """
    imgPath = request.imgPath
    try:
        image = Image.open(imgPath).convert('RGB')
    except Exception as e:
        error_msg = f"Error opening image from path {imgPath}: {e}"
        logging.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
    
    try:
        global quality_checker
        result = quality_checker.predict(image)
        return result
    except Exception as e:
        error_msg = f"Error during quality prediction: {e}"
        logging.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

def restart_fastapi_app(imgPath):
    logging.critical("Critical error occurred. Restarting FastAPI app in 3 seconds...")
    logging.critical(f"The last image before crashing is {imgPath} ...")
    # os.execl() replaces the current process with a new one.
    import sys, time
    time.sleep(3)
    os.execl(sys.executable, sys.executable, *sys.argv)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("artificial_intelligence_api:app", host="0.0.0.0", port=8501, reload=True)
