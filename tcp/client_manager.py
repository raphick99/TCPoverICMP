import asyncio
import logging

from tcp import client_session
from exceptions import ClientClosedConnectionError


log = logging.getLogger(__name__)


class ClientManager:
    def __init__(self, new_connections: asyncio.Queue, incoming_tcp_packets: asyncio.Queue):
        self.clients = {}
        self.new_connections = new_connections
        self.incoming_tcp_packet = incoming_tcp_packets

    async def wait_for_new_connections(self):
        while True:
            client_id, reader, writer = await self.new_connections.get()
            await self.add_client(client_id, reader, writer)

    async def add_client(self, client_id: int, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.clients[client_id] = client_session.ClientSession(client_id, reader, writer, self.incoming_tcp_packet)
        asyncio.create_task(self.clients[client_id].run())
        log.debug(f'new client running: client_id={client_id}')

    async def write_to_client(self, data: bytes, client_id: int):
        try:
            if client_id in self.clients.keys():
                await self.clients[client_id].write(data)
        except ClientClosedConnectionError:
            # TODO Decide what to do in this scenario,
            #  It means the client received a write from the ICMP part, and cannot forward it. Probably return a failure
            self.clients.pop(client_id)
