1. Git clone patiwet/aidoc/main to WSL aidoc folder
2. Copy the oralLesionNet folder to aidoc\ (rename to oralLesionNet)
3. Add the following line to aidoc\oralLesionNet\__init__.py, after import os

# ---------------------------------------------------------------------------
__version__ = "2.2"
__package__ = "aidoc/" + __package__
# ---------------------------------------------------------------------------

4. Add the following line to aidoc\oralLesionNet\model.py after from tensorflow.keras import layers

# ---------------------------------------------------------------------------

gpus = tf.config.list_physical_devices('GPU')
if gpus:
    try:
        # Currently, memory growth needs to be the same across GPUs
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)
            #tf.config.set_logical_device_configuration(gpu, [tf.config.LogicalDeviceConfiguration(memory_limit=3072)])
        logical_gpus = tf.config.list_logical_devices('GPU')
        print("This server has", len(gpus), "Physical GPUs,", len(logical_gpus), "Logical GPUs")
    except RuntimeError as e:
        # Memory growth must be set before GPUs have been initialized
        print(e)

# ---------------------------------------------------------------------------

5. cd aidoc
6. pip install -e .
7. copy config.py (OneDrive - Personal) to aidoc\instance folder
8. flask --app aidoc init-db
9. flask --app aidoc run