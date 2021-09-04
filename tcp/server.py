import asyncio
import itertools
import socket
import logging


log = logging.getLogger(__name__)


class Server:
    def __init__(self, host: str, port: int, new_connections: asyncio.Queue):
        self.host = host
        self.port = port
        self.new_connections = new_connections
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
        await self.new_connections.put((next(self._client_id), reader, writer))
