1. Git clone patiwet/aidoc/main to WSL home folder (aidoc folder will be automatically created)
2. Copy the oralLesionNet folder to aidoc\ (rename to oralLesionNet)
3. Double check path variable in the file __init__.py
5. cd aidoc
6. pip install -e .
7. flask --app aidoc init-db
8. copy \instance folder (having config.py) in the 'OneDrive - Personal' to aidoc\aidoc\instance folder
9. flask --app aidoc run