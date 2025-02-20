import json

from . import get_image_list
from ... import db
from flask import jsonify, make_response, request
from decimal import Decimal
    
def get_image_manage_list(data):
    output = get_image_list.image_manage_list(data)
    return output










