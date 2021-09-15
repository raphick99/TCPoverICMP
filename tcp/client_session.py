import asyncio
import logging
import itertools

from exceptions import ClientClosedConnectionError


log = logging.getLogger(__name__)


class ClientSession:
    INITIAL_SEQUENCE_NUMBER = 1
    RECV_BLOCK_SIZE = 1024

    def __init__(
            self,
            client_id: int,
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter,
    ):
        self.client_id = client_id
        self.reader = reader
        self.writer = writer
        self.sequence_number = itertools.count(self.INITIAL_SEQUENCE_NUMBER)
        self.last_written = self.INITIAL_SEQUENCE_NUMBER - 1
        self.packets = {}

    async def stop(self):
        log.debug(f'(client_id={self.client_id}): Shutting down..')
        self.writer.close()
        await self.writer.wait_closed()

    async def read(self):
        try:
            data = await self.reader.read(self.RECV_BLOCK_SIZE)
        except ConnectionResetError:
            raise ClientClosedConnectionError()

        if not data:
            raise ClientClosedConnectionError()

        return data

    async def write(self, sequence_number: int, data: bytes):
        if self.writer.is_closing():
            raise ClientClosedConnectionError()

        if sequence_number in self.packets.keys():
            log.debug(f'ignoring repeated packet: (seq_num={sequence_number})')
            return

        self.packets[sequence_number] = data
        while (self.last_written + 1) in self.packets.keys():
            self.last_written += 1

            self.writer.write(self.packets[self.last_written])
            await self.writer.drain()

            self.packets.pop(self.last_written)
