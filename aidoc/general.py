from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash

import functools
import datetime
import re

from aidoc.db import get_db

bp = Blueprint('general', __name__)

@bp.route('/general')
def general_index():
    if g.get('user') is None:
        session.clear() # logged out from everything

    if g.user: # already logged in
        if 'sender_mode' in session and session['sender_mode']=='general':
            return redirect('/general/upload')
    else:
        return render_template("general_login.html")

@bp.route('/general/login', methods=('Post',))
def general_login():
    session['sender_mode'] = 'general'
    email = request.form['email']
    error_msg = None
    db, cursor = get_db()
    cursor.execute('SELECT * FROM general_user WHERE email = %s', (email,))
    user = cursor.fetchone()
    if user is None:
        error_msg = "Please register a new user for the first time"
    if error_msg is None: # Logged in sucessfully
        session['user_id'] = user['id']
        return redirect('/general/upload')
    
    flash(error_msg)
    data = {'email': email}
    return render_template("general_register.html", data=data)

@bp.route('/general/register', methods=('GET', 'POST'))
def general_register():
    data = {}

    if request.method == 'POST':
        # This section extract the submitted form to 
        data["name"] = request.form["name"]
        data["surname"] = request.form["surname"]
        data["email"] = request.form["email"]
        data["job_position"] = request.form["job_position"]
        data["workplace"] = request.form["workplace"]
        data["city"] = request.form["city"]
        data["country"] = request.form["country"]

        data["valid_email"] = True

        email_pattern = r'([A-Za-z0-9]+[.-_])*[A-Za-z0-9]+@[A-Za-z0-9-]+(\.[A-Z|a-z]{2,})+'
        data["valid_email"] = re.fullmatch(email_pattern, data["email"]) is not None
        if not data["valid_email"]:
            return render_template("general_register.html", data=data)
        
        # Create new account if there is no duplicate account, else merge the accounts
        db, cursor = get_db()
        sql = "INSERT INTO general_user (name, surname, email, job_position, workplace, city, country) VALUES (%s,%s,%s,%s,%s,%s,%s)"
        val = (data["name"], data["surname"], data["email"], data["job_position"], data["workplace"], data["city"],data["country"])
        cursor.execute(sql, val)
            
        return redirect('/general/upload')
    else:
        return render_template("general_register.html", data=data)

@bp.route('/general/upload', methods=('GET', 'POST'))
def general_upload():
    data = {}
    session['sender_mode'] = 'general'
    submission = request.args.get('submission', default='false', type=str)
    if request.method == 'POST':
        if request.form.get('rotation_submitted'):
            imageName = request.form.get('uploadedImage')
            #rotate_temp_image(imageName)
            #data = {'uploadedImage': imageName}
        elif submission=='false': # Load and show the image, wait for the confirmation
            print()
    return render_template("general_upload.html", data=data)