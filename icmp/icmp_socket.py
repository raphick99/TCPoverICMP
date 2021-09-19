import asyncio
import socket
import logging
import contextlib

from . import icmp_packet, exceptions


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class ICMPSocket(object):
    IP_HEADER_LENGTH = 20
    MINIMAL_PACKET = b'\x00\x00'
    DEFAULT_DESTINATION_PORT = 0
    DEFAULT_DESTINATION = ('', DEFAULT_DESTINATION_PORT)
    DEFAULT_BUFFERSIZE = 4096

    def __init__(self, incoming_queue: asyncio.Queue):
        self.incoming_queue = incoming_queue

        self._icmp_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        self._icmp_socket.setblocking(False)
        self._icmp_socket.sendto(self.MINIMAL_PACKET, self.DEFAULT_DESTINATION)  # need to send one packet, because didnt bind. otherwise exception is raised when using on first packet.

    async def recv(self, buffersize: int = DEFAULT_BUFFERSIZE):
        """
        receive a single ICMP packet.
        :param buffersize:  maximal length of data to receive.
        :return: an instance of ICMPPacket, representing a sniffed ICMP packet.
        """
        data = await asyncio.get_event_loop().sock_recv(self._icmp_socket, buffersize)
        if not data:
            raise exceptions.RecvReturnedEmptyString()
        return icmp_packet.ICMPPacket.deserialize(data[self.IP_HEADER_LENGTH:])  # packet includes IP header, so remove it.

    async def wait_for_incoming_packet(self):
        """
        "listen" on the socket, pretty much sniff raw for ICMP packets, and put them in the incoming ICMP queue.
        :return:
        """
        while True:
            with contextlib.suppress(exceptions.InvalidICMPCode):
                packet = await self.recv()
                await self.incoming_queue.put(packet)

    def sendto(self, packet: icmp_packet.ICMPPacket, destination: str):
        """
        receive an icmp packet, and sent it to the destination.
        :param packet: an instance if ICMPPacket that is to be sent.
        :param destination: the IP of the destination.
        """
        log.debug(f'sending {packet.payload} to {destination}')
        self._icmp_socket.sendto(packet.serialize(), (destination, self.DEFAULT_DESTINATION_PORT))
