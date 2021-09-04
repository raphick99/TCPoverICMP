import asyncio
import logging
import itertools

from exceptions import ClientClosedConnectionError


log = logging.getLogger(__name__)


class ClientSession(object):
    def __init__(
            self,
            client_id: int,
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter,
            incoming_from_tcp_channel: asyncio.Queue
    ):
        self.client_id = client_id
        self.reader = reader
        self.writer = writer
        self.incoming_from_tcp_channel = incoming_from_tcp_channel
        self.sequence_number = itertools.count()

    async def run(self):
        while True:
            try:
                data = await self.reader.read(1024)
            except ConnectionResetError:
                log.debug(f'(client_id={self.client_id}): client disconnected. Shutting down..')
                return

            if data.decode() == '':
                log.debug(f'(client_id={self.client_id}): client disconnected. Shutting down..')
                self.writer.close()
                await self.writer.wait_closed()
                return

            log.debug(f'(client_id={self.client_id}): recv(\'{data.decode()}\')')
            await self.incoming_from_tcp_channel.put((data, self.client_id, next(self.sequence_number)))

    async def write(self, data: bytes):
        if self.writer.is_closing():
            raise ClientClosedConnectionError()

        log.debug(f'(client_id={self.client_id}): send(\'{data.decode()}\')')
        self.writer.write(data)
        await self.writer.drain()
