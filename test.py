import tensorflow as tf
from PIL import Image, ImageFilter

import oralLesionNet
# Load the oralLesionNet model to the global variable
model = oralLesionNet.load_model()

def create_mask(pred_mask):
  pred_mask = tf.math.argmax(pred_mask, axis=-1)
  pred_mask = pred_mask[..., tf.newaxis]
  return pred_mask[0]

def oral_lesion_prediction(imgPath):
    img = tf.keras.utils.load_img(imgPath, target_size=(342, 512, 3))
    img = tf.expand_dims(img, axis=0)

    global model
    pred_mask = model.predict(img)
    output_mask = create_mask(pred_mask)

    predictionMask = tf.math.not_equal(output_mask, 0)

    pred_mask = tf.squeeze(pred_mask, axis=0)  # Remove batch dimension
    backgroundChannel = pred_mask[:,:,0]
    opmdChannel = pred_mask[:,:,1]
    osccChannel = pred_mask[:,:,2]
    
    predictionMaskSum = tf.reduce_sum(tf.cast(predictionMask,  tf.int64)) # Count number of pixels in prediction mask
    predictionIndexer = tf.squeeze(predictionMask, axis=-1) # Remove singleton dimension (last index)
    print(predictionMaskSum)
    if predictionMaskSum>200: # Threshold to cut noises are 200 pixels
        opmdScore = tf.reduce_mean(opmdChannel[predictionIndexer])
        osccScore = tf.reduce_mean(osccChannel[predictionIndexer])
        backgroundScore = tf.reduce_mean(backgroundChannel[predictionIndexer])
        if opmdScore>osccScore:
            predictClass = 'OPMD'
        else:
            predictClass = 'OSCC'
    else:
        backgroundIndexer = tf.math.logical_not(predictionIndexer)
        opmdScore = tf.reduce_mean(opmdChannel[backgroundIndexer])
        osccScore = tf.reduce_mean(osccChannel[backgroundIndexer])
        backgroundScore = tf.reduce_mean(backgroundChannel[backgroundIndexer])
        predictClass = 'NORMAL'
    
    output = tf.keras.utils.array_to_img(predictionMask)
    edge_img = output.filter(ImageFilter.FIND_EDGES)
    dilation_img = edge_img.filter(ImageFilter.MaxFilter(3))

    yellow_edge = Image.merge("RGB", (dilation_img, dilation_img, Image.new(mode="L", size=dilation_img.size)))
    img = tf.squeeze(img, axis=0)
    input_img = tf.keras.utils.array_to_img(img)    
    outlined_img = input_img.copy()
    outlined_img.paste(yellow_edge, dilation_img)
    
    scoreList = [backgroundScore, opmdScore, osccScore]
    scoreList = [x.numpy() for x in scoreList]
    return outlined_img, predictClass, scoreList

outlined_img, pred_class, scores = oral_lesion_prediction('/home/patiwet/aidoc/imageData/temp/561000006469902.jpg')
print(pred_class)
print(scores)
outlined_img.save('output.png')