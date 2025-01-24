----- On Development -----
0. Install WSL LAMP (Linux, Apache, MySQL Server, and phpmyadmin)
1. Git clone patiwet/aidoc/main to WSL home folder (aidoc folder will be automatically created)
2. Copy the oralLesionNet files from 'OneDrive\aidoc\oralLesionNet' to 'aidoc\aidoc\oralLesionNet' folder
3. Copy config.py file from 'OneDrive\aidoc\instance' to 'aidoc\aidoc\instance' folder
4. Copy the imageQualityChecker files from 'OneDrive\aidoc\imageQualityChecker' to 'aidoc\aidoc\imageQualityChecker' folder
5. Copy the legal files from 'OneDrive\aidoc\legal' to 'aidoc\aidoc\legal' folder
6. Install the python environment and the related packages (see below)
7. In the folder aidoc\, install the aidoc package on the pip list using:   pip install -e .
8. Intialize the database using:            flask --app aidoc init-db
9. Run the package on the terminal using:   flask --app aidoc run
10. Keep the requirements.txt and this file updated.
11. Try to minimize the dependencies (Or try to reduce the unneccessary ones)
12. Update version numbers on config.py accordingly

----- On production -----
*** Installation Phase ***
1. Ask Mr. Thawatchai to setup xampp on the server, setup the reverse proxy, and ask for the URL
2. Git clone patiwet/aidoc/main to xampp\htdocs\aidoc
3. Install the python environment and the related packages (you may use the requirements.txt)
4. Install the gevent WSGI server package:  pip install gevent
5. In the folder aidoc\, install the aidoc package on the pip list using:   pip install -e .
6. Edit wsgi.py file to correct the url and port number, and point the keyfile and certfile to the correct locations

*** Maintainance Phase ***
7. Launch the server using:     python wsgi.py
8. Keep updating the web app using 'git pull'
9. Occasionally update the environment based on the current requirements.txt

Note that the images files are in the folder: aidoc\imageData
The user and submission database can be accessed through the phpmyadmin

----- Python Package Dependency Installation -----
1. install conda or miniconda
2. create a conda environment using: conda create --name aidoc python
3. Activate the environment and pip install the following packages

(you may also check the requirements.txt)
pip install Flask
pip install mysql-connector-python
pip install tensorflow (or pip install tensorflow[and-cuda] if you want to use a GPU)
pip install pillow
pip install opencv-python
pip install python-dateutil
pip install PyPDF2
pip install reportlab

Updated: Jan 17, 2024