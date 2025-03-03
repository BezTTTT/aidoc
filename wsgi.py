from gevent import monkey
monkey.patch_all()

from gevent.pywsgi import WSGIServer
from aidoc import create_app
import logging
import socket

app = create_app()

# Forward App Logger to WSGI Logger
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

gevent_log_writer = LoggerWriter(app.logger, logging.DEBUG)

# Manually create and configure the server socket.
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind(("icohold.anamai.moph.go.th", 85))
server_socket.listen(5)  # 5 is a typical backlog value.

# Pass the preconfigured socket to the WSGIServer.
http_server = WSGIServer(
    server_socket,
    app,
    keyfile="D:/xampp_New_AI/apache/conf/cert/private.key",
    certfile="D:/xampp_New_AI/apache/conf/cert/star_anamai_moph_go_th.crt",
    ca_certs="D:/xampp_New_AI/apache/conf/cert/CARootCertificate-ca.crt",
    log=gevent_log_writer,
    error_log=gevent_log_writer
)

http_server.serve_forever()
