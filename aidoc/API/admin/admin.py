import json
from . import delete_user_account, get_image_manage, get_user_account_list, get_user_edit_info, update_user_info
from ... import db
from flask import jsonify, make_response, request
from decimal import Decimal

def generate_admin_page():
    output = get_user_account_list.users_list()
    return output

def delete_user(id):
    output = delete_user_account.delete_user(id)
    return output

def generate_user_edit_info(id):
    output = get_user_edit_info.user_info(id)
    return output

def put_update_user_info(data):
    output = update_user_info.update_user_info(data)
    return output
    
def get_image_manage_list(data):
    output = get_image_manage.image_manage_list(data)
    return output










