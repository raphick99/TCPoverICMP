import asyncio
import logging
import itertools

from exceptions import ClientClosedConnectionError


log = logging.getLogger(__name__)


class ClientSession:
    def __init__(
            self,
            client_id: int,
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter,
    ):
        self.client_id = client_id
        self.reader = reader
        self.writer = writer
        self.sequence_number = itertools.count(1)

    async def stop(self):
        log.debug(f'(client_id={self.client_id}): Shutting down..')
        self.writer.close()
        await self.writer.wait_closed()

    async def read(self):
        try:
            data = await self.reader.read(1024)
        except ConnectionResetError:
            raise ClientClosedConnectionError()

        if data.decode() == '':
            raise ClientClosedConnectionError()

        return data

    async def write(self, data: bytes):
        if self.writer.is_closing():
            raise ClientClosedConnectionError()

        self.writer.write(data)
        await self.writer.drain()
