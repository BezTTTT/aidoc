----- On Development -----
0. Install WSL LAMP (Linux, Apache, MySQL Server, and phpmyadmin)
1. Git clone patiwet/aidoc/main to WSL home folder (aidoc folder will be automatically created)
2. Copy all files from 'OneDrive\aidoc\New AIDOC dependency' to 'aidoc\aidoc\' folder
    (Including, imageQualityChecker, instance\config.py, legal\templates\*, oralLesionNet)
3. Install the python environment and the related packages (see below)
4. Create a database name 'aidoc_development' (For production, 'aidoc_production') on MySQL server
5. Intialize the database   on the terminal using:      flask --app aidoc init-db
6. Run the WebApp (Flask)   on the terminal using:      flask --app aidoc run
7. Run the AI API (FaskAPI) on the terminal using:      python artificial_intelligence_api.py
8. Keep the requirements.txt and this file updated.
9. Try to minimize the dependencies (Or try to reduce the unneccessary ones)
10. Update version numbers on config.py accordingly

----- On production -----
*** Installation Phase ***
1. Ask Mr. Thawatchai to setup xampp on the server, setup the reverse proxy, and ask for the URL
2. Git clone patiwet/aidoc/main to xampp\htdocs\aidoc
3. Install the python environment and the related packages (you may use the requirements.txt)
4. Install the gevent WSGI server package (For WebApp):  pip install gevent
5. Edit wsgi.py file to correct the url and port number, and point the keyfile and certfile to the correct locations

*** Maintainance Phase ***
6. Launch the server using:     python wsgi.py
7. Keep updating the web app using 'git pull'
8. Occasionally update the environment based on the current requirements.txt

Note that the images files are in the folder: aidoc\imageData
The user and submission database can be accessed through the phpmyadmin

----- Python Package Dependency Installation -----
1. install conda or miniconda
2. create a conda environment using: conda create --name aidoc python
3. Activate the environment and pip install the following packages

(you may also check the requirements.txt)
pip install Flask
pip install mysql-connector-python
pip install pillow
pip install opencv-python
pip install python-dateutil
pip install pypdf
pip install reportlab
pip install line-bot-sdk
pip install bcrypt
pip install pandas
pip install openpyxl
pip install uvicorn[standard]
pip install fastapi[standard]
pip install tensorflow (or pip install tensorflow[and-cuda] if you want to use a GPU)
pip install cachetools

(you may upgrade the package using this line)
pip install --upgrade Flask, mysql-connector-python tensorflow pillow opencv-python python-dateutil pypdf reportlab line-bot-sdk bcrypt pandas openpyxl
pip install --upgrade tensorflow (or tensorflow[and-cuda])
pip install --upgrade uvicorn[standard] fastapi[standard]

Updated: Mar 4, 2025