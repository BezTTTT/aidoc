from gevent.pywsgi import WSGIServer
from aidoc import create_app

app = create_app()
http_server = WSGIServer(
		("icohold.anamai.moph.go.th", 85), 
		app,
		keyfile = "D:\\xampp_New_AI\\apache\\conf\\cert\\private.key",
        certfile = "D:\\xampp_New_AI\\apache\\conf\\cert\\star_anamai_moph_go_th.crt",
)
http_server.serve_forever()