import asyncio
import socket
import logging

from . import icmp_packet


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


# I only need an incoming packet queue, because since the server manages the tcp-incoming messages, it can just call
#  the appropriate send function. Therefore, I can have a while-true on recv, and on write, just expose an API.


class ICMPSocket(object):
    IP_HEADER_LENGTH = 20

    def __init__(self, incoming_queue: asyncio.Queue, endpoint_address):
        self.incoming_queue = incoming_queue
        self.endpoint_address = endpoint_address

        self._icmp_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        self._icmp_socket.setblocking(False)
        self._icmp_socket.sendto(b'AAAA', (self.endpoint_address, 0))  # need to send one packet, because didnt bind.

    async def recv(self, buffersize: int = 4096):
        data = await asyncio.get_event_loop().sock_recv(self._icmp_socket, buffersize)
        if data == '':
            pass
            # TODO This shouldnt happen. What if it does?
        log.debug(f'received packet over ICMP: {data.hex()}')
        return icmp_packet.ICMPPacket.deserialize(data[self.IP_HEADER_LENGTH:])

    async def wait_for_incoming_packet(self):
        while True:
            packet = await self.recv()
            await self.incoming_queue.put(packet)

    def sendto(self, packet: icmp_packet.ICMPPacket, destination: str = None):
        destination = destination or self.endpoint_address
        log.debug(f'sending {packet.payload} to {destination}')
        self._icmp_socket.sendto(packet.serialize(), (destination, 1))