import asyncio
import itertools
import socket
import logging

import client_session
from exceptions import ClientClosedConnectionError


log = logging.getLogger(__name__)


class Server(object):
    def __init__(self, host: str, port: int, incoming_queue: asyncio.Queue):
        self.host = host
        self.port = port
        self.incoming_queue = incoming_queue
        self.clients = {}
        self._client_id = itertools.count()

    async def serve_forever(self):
        server = await asyncio.start_server(
            self.handle_new_tcp_connection,
            host=self.host,
            port=self.port,
            family=socket.AF_INET
        )
        log.info(f'listening on {self.host}:{self.port}')
        await server.serve_forever()

    async def handle_new_tcp_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        new_client_id = next(self._client_id)

        self.clients[new_client_id] = client_session.ClientSession(new_client_id, reader, writer, self.incoming_queue)
        asyncio.create_task(self.clients[new_client_id].run())

        log.debug(f'new client running: client_id={new_client_id}')

    async def write_to_client(self, data: bytes, client_id: int):
        try:
            await self.clients[client_id].write(data)
        except ClientClosedConnectionError:
            # TODO Decide what to do in this scenario,
            #  It means the client received a write from the ICMP part, and cannot forward it. Probably return a failure
            self.clients.pop(client_id)
