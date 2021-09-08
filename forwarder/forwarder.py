import asyncio
import logging

from core import queue_manager
from tcp import server


log = logging.getLogger(__name__)


class Forwarder(queue_manager.QueueManager):
    def __init__(self, host, port):
        super(Forwarder, self).__init__()
        self.tcp_server = server.Server(host, port, self.incoming_tcp_connections)
        self.coroutines_to_run.append(self.tcp_server.serve_forever())
