import asyncio
import logging
import collections
from TCPoverICMP import client_session, exceptions


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
        """
        check if client exists
        """
        return client_id in self.clients.keys()

    def add_client(self, client_id: int, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """
        add a client to be managed. create a task that constantly reads from the client.
        """
        if self.client_exists(client_id):
            raise exceptions.ClientAlreadyExistsError()

        new_client_session = client_session.ClientSession(client_id, reader, writer)
        new_task = asyncio.create_task(self.read_from_client(client_id))
        self.clients[client_id] = ClientInfo(new_client_session, new_task)
        log.debug(f'adding client: (client_id={client_id})')

    async def remove_client(self, client_id: int):
        """
        remove a managed client. cancel the task and stop the client session.
        Dont call directly from client_manager, instead put client_id in stale_connections.
        :param client_id: the client_id to remove
        """
        if not self.client_exists(client_id):
            raise exceptions.RemovingClientThatDoesntExistError(client_id, self.clients.keys())

        log.debug(f'removing client: (client_id={client_id})')
        self.clients[client_id].task.cancel()
        await self.clients[client_id].task
        await self.clients[client_id].session.stop()
        self.clients.pop(client_id)

    async def write_to_client(self, client_id: int, sequence_number: int, data: bytes):
        """
        function for writing to a managed client.
        :param client_id: the client_id of the client to write to.
        :param sequence_number: the sequence number of the write. used for validation and ordering of packets.
        :param data: the data to write.
        """
        if not self.client_exists(client_id):
            raise exceptions.WriteAttemptedToNonExistentClient()

        try:
            await self.clients[client_id].session.write(sequence_number, data)
        except exceptions.ClientClosedConnectionError:
            await self.stale_connections.put(client_id)

    async def read_from_client(self, client_id: int):
        """
        constantly read from a client, and put in incoming_tcp_packets queue.
        :param client_id: the client to read from.
        """
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
