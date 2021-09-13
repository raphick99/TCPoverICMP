import asyncio
import logging
import collections

from tcp import client_session
import exceptions


log = logging.getLogger(__name__)


ClientInfo = collections.namedtuple('ClientInfo', ('session', 'task'))


class ClientManager:
    def __init__(
            self,
            stale_connections: asyncio.Queue,
            incoming_tcp_packets: asyncio.Queue
    ):
        self.clients = {}
        self.stale_connections = stale_connections
        self.incoming_tcp_packets = incoming_tcp_packets

    def client_exists(self, client_id: int):
        return client_id in self.clients.keys()

    def add_client(self, client_id: int, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        if self.client_exists(client_id):
            raise exceptions.ClientAlreadyExistsError()

        new_client_session = client_session.ClientSession(client_id, reader, writer)
        new_task = asyncio.create_task(self.read_from_client(client_id))
        self.clients[client_id] = ClientInfo(new_client_session, new_task)
        log.debug(f'adding client: (client_id={client_id})')

    async def remove_client(self, client_id: int):
        # Note: Dont call directly from client_manager, instead put client_id in stale_connections.
        if not self.client_exists(client_id):
            raise exceptions.RemovingClientThatDoesntExistError()

        log.debug(f'removing client: (client_id={client_id})')
        self.clients[client_id].task.cancel()
        await self.clients[client_id].task
        await self.clients[client_id].session.stop()
        self.clients.pop(client_id)

    async def write_to_client(self, data: bytes, client_id: int):
        if not self.client_exists(client_id):
            raise exceptions.WriteAttemptedToNonExistentClient()

        try:
            await self.clients[client_id].session.write(data)
        except exceptions.ClientClosedConnectionError:
            await self.stale_connections.put(client_id)

    async def read_from_client(self, client_id: int):
        if not self.client_exists(client_id):
            raise exceptions.ReadAttemptedFromNonExistentClient()

        client = self.clients[client_id].session

        try:
            while True:
                try:
                    data = await client.read()
                except exceptions.ClientClosedConnectionError:
                    await self.stale_connections.put(client_id)
                    return

                await self.incoming_tcp_packets.put((data, client.client_id, next(client.sequence_number)))
        except asyncio.CancelledError:
            pass
