import asyncio
import logging

from tcp import client_session
from exceptions import ClientClosedConnectionError


log = logging.getLogger(__name__)


class ClientManager:
    def __init__(
            self,
            new_connections: asyncio.Queue,
            stale_connections: asyncio.Queue,
            incoming_tcp_packets: asyncio.Queue
    ):
        self.clients = {}
        self.new_connections = new_connections
        self.stale_connections = stale_connections
        self.incoming_tcp_packet = incoming_tcp_packets

    def client_exists(self, client_id: int):
        return client_id in self.clients.keys()

    async def wait_for_new_connection(self):
        while True:
            client_id, reader, writer = await self.new_connections.get()
            self.add_client(client_id, reader, writer)

    async def wait_for_stale_connection(self):
        while True:
            client_id = await self.stale_connections.get()
            self.remove_client(client_id)

    def add_client(self, client_id: int, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        new_client_session = client_session.ClientSession(client_id, reader, writer, self.incoming_tcp_packet)
        # self.clients[client_id] = client_session.ClientSession(client_id, reader, writer, self.incoming_tcp_packet)
        new_task = asyncio.create_task(new_client_session.run())
        self.clients[client_id] = new_client_session, new_task
        log.debug(f'new client running: client_id={client_id}')

    def remove_client(self, client_id: int):
        log.debug(f'new client running: client_id={client_id}')

        if self.client_exists(client_id):
            # todo (RI): make nicer, maybe collections.namedtuple
            self.clients[client_id][0].stop()
            self.clients[client_id][1].cancel()

    async def write_to_client(self, data: bytes, client_id: int):
        try:
            if self.client_exists(client_id):
                await self.clients[client_id][0].write(data)
        except ClientClosedConnectionError:
            # TODO Decide what to do in this scenario,
            #  It means the client received a write from the ICMP part, and cannot forward it. Probably return a failure
            self.clients.pop(client_id)
