import tensorflow as tf
import numpy as np
import os
from PIL import Image

class ImageQualityChecker:
    classes = [
        'Misorientation',
        'Non Standard',
        'No Mouth',
        'Standard'
    ]
    
    def __init__(self, model_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "imageQualityChecker.tflite")):
        # Load the TFLite model and allocate tensors
        self.model = tf.lite.Interpreter(model_path=model_path)
        self.model.allocate_tensors()
        
        # Get input and output tensor details
        self.input_details = self.model.get_input_details()
        self.output_details = self.model.get_output_details()
        
    def predict(self, image):
        
        # check the transparency channel and convert to RGB
        if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
            image.load()
            alpha = Image.new("RGB", image.size, (255, 255, 255))
            alpha.paste(image, mask=image.split()[3]) # 3 is the alpha channel
            image = alpha

        # pre-process the image
        resized_image = image.resize((256, 256))
        input_data = np.array(resized_image).astype(np.float32) / 255.0 # for narm image
        input_data = np.expand_dims(input_data, axis=0)  
        
        # attach the input
        self.model.set_tensor(self.input_details[0]['index'], input_data)
        # forward
        self.model.invoke()
        # get the output
        output_data = self.model.get_tensor(self.output_details[0]['index'])
        
        class_id = int(np.argmax(output_data[0]))
        class_name = ImageQualityChecker.classes[class_id]
        confident = float(output_data[0][class_id])
        
        return {
            'Class_ID': class_id,
            'Class_Name': class_name,
            'Confident': confident
        }