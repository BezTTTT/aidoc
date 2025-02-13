from gevent.pywsgi import WSGIServer
from aidoc import create_app

app = create_app()
import logging
class LoggerWriter:
    def __init__(self, logger, level):
        self.logger = logger
        self.level = level

    def write(self, message):
        message = message.strip()
        if message:  # avoid empty messages
            self.logger.log(self.level, message)

    def flush(self):
        pass

# Create a writer that sends gevent logs to your app.logger:
gevent_log_writer = LoggerWriter(app.logger, logging.DEBUG)

http_server = WSGIServer(
		("icohold.anamai.moph.go.th", 85), 
		app,
        keyfile="D:/xampp_New_AI/apache/conf/cert/private.key",
        certfile="D:/xampp_New_AI/apache/conf/cert/star_anamai_moph_go_th.crt",
	    ca_certs="D:/xampp_New_AI/apache/conf/cert/CARootCertificate-ca.crt",
        log=gevent_log_writer,      # for general request logs
        error_log=gevent_log_writer # for error logs
    )
http_server.serve_forever()