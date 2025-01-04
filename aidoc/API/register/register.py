from . import post_patient

def post_register_patient(data):
    output = post_patient.post_patient(data)
    return output