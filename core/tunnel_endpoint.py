import asyncio
import logging

from tcp import client_manager
from icmp import icmp_socket, icmp_packet
from proto import Tunnel


log = logging.getLogger(__name__)


def consume_queue(queue_to_consume):
    def wrap_function(f):
        async def wrapper(*_, **__):
            while True:
                args = await queue_to_consume.get()
                await f(*args)
        return wrapper
    return wrap_function


class TunnelEndpoint:
    def __init__(self):
        self.stale_tcp_connections = asyncio.Queue(maxsize=1000)
        self.incoming_from_icmp_channel = asyncio.Queue(maxsize=1000)
        self.incoming_from_tcp_channel = asyncio.Queue(maxsize=1000)
        self.icmp_socket = icmp_socket.ICMPSocket(
            self.incoming_from_icmp_channel, self.other_endpoint  # TODO have the endpoint be configurable
        )

        self.client_manager = client_manager.ClientManager(
            self.stale_tcp_connections,
            self.incoming_from_tcp_channel
        )

        self.coroutines_to_run = []

    @property
    def other_endpoint(self):
        raise NotImplementedError()

    @property
    def direction(self):
        raise NotImplementedError()

    async def handle_start_request(self, tunnel_packet):
        raise NotImplementedError()

    async def handle_end_request(self, tunnel_packet):
        raise NotImplementedError()

    async def handle_data_request(self, tunnel_packet):
        raise NotImplementedError()

    async def handle_ack_request(self, tunnel_packet):
        raise NotImplementedError()

    async def run(self):
        constant_coroutines = [
            self.handle_incoming_from_tcp_channel(),
            self.handle_incoming_from_icmp_channel(),
            self.wait_for_stale_connection(),
            self.icmp_socket.wait_for_incoming_packet(),
        ]
        running_tasks = [asyncio.create_task(coroutine) for coroutine in self.coroutines_to_run + constant_coroutines]

        await asyncio.gather(*running_tasks)

    async def handle_incoming_from_icmp_channel(self):
        while True:
            new_icmp_packet = await self.incoming_from_icmp_channel.get()
            if new_icmp_packet.identifier != 0xcafe or new_icmp_packet.sequence_number != 0xbabe:
                log.debug(f'wrong magic (identifier={new_icmp_packet.identifer})'
                          f'(seq_num={new_icmp_packet.sequence_number}), ignoring')
                continue

            tunnel_packet = Tunnel()
            tunnel_packet.ParseFromString(new_icmp_packet.payload)
            if tunnel_packet.action != Tunnel.Action.ack:
                self.send_ack(tunnel_packet)
            log.debug(f'received {tunnel_packet}')

            if tunnel_packet.direction == self.direction:
                log.debug('ignoring packet headed in the wrong direction')
                continue

            actions = {
                Tunnel.Action.start: self.handle_start_request,
                Tunnel.Action.end: self.handle_end_request,
                Tunnel.Action.data: self.handle_data_request,
                Tunnel.Action.ack: self.handle_ack_request,

            }
            await actions[tunnel_packet.action](tunnel_packet)

    async def handle_incoming_from_tcp_channel(self):
        while True:
            data, client_id, sequence_number = await self.incoming_from_tcp_channel.get()

            new_tunnel_packet = Tunnel(
                client_id=client_id,
                sequence_number=sequence_number,
                action=Tunnel.Action.data,
                direction=self.direction,
                ip='',
                port=0,
                payload=data,
            )
            self.send_icmp_packet(icmp_packet.ICMPType.EchoRequest, new_tunnel_packet.SerializeToString())

    async def wait_for_stale_connection(self):
        while True:
            client_id = await self.stale_tcp_connections.get()

            new_tunnel_packet = Tunnel(
                client_id=client_id,
                action=Tunnel.Action.end,
                direction=self.direction,
                ip='',
                port=0,
                payload=b'',
            )

            self.send_icmp_packet(icmp_packet.ICMPType.EchoRequest, new_tunnel_packet.SerializeToString())
            self.client_manager.remove_client(client_id)

    def send_ack(self, tunnel_packet):
        new_tunnel_packet = Tunnel(
            client_id=tunnel_packet.client_id,
            sequence_number=tunnel_packet.sequence_number,
            action=Tunnel.Action.ack,
            direction=self.direction,
            ip='',
            port=0,
            payload=b'',
        )
        self.send_icmp_packet(
            icmp_packet.ICMPType.EchoReply,
            new_tunnel_packet.SerializeToString(),
        )

    def send_icmp_packet(
            self,
            type: icmp_packet.ICMPType,
            payload: bytes
    ):
        new_icmp_packet = icmp_packet.ICMPPacket(
            type=type,
            identifier=0xcafe,
            sequence_number=0xbabe,
            payload=payload
        )
        self.icmp_socket.sendto(new_icmp_packet, self.other_endpoint)
