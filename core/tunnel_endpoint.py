import asyncio
import logging

from tcp import client_manager
from icmp import icmp_socket, icmp_packet
from proto import Tunnel


log = logging.getLogger(__name__)


class TunnelEndpoint:
    def __init__(self, other_endpoint):
        self.other_endpoint = other_endpoint
        log.info(f'other tunnel endpoint: {self.other_endpoint}')

        self.stale_tcp_connections = asyncio.Queue()
        self.incoming_from_icmp_channel = asyncio.Queue()
        self.incoming_from_tcp_channel = asyncio.Queue()

        self.icmp_socket = icmp_socket.ICMPSocket(self.incoming_from_icmp_channel)
        self.client_manager = client_manager.ClientManager(self.stale_tcp_connections, self.incoming_from_tcp_channel)

        self.packets_requiring_ack = {}
        self.coroutines_to_run = []

    @property
    def direction(self):
        raise NotImplementedError()

    async def handle_start_request(self, tunnel_packet: Tunnel):
        raise NotImplementedError()

    async def handle_end_request(self, tunnel_packet: Tunnel):
        await self.client_manager.remove_client(tunnel_packet.client_id)
        self.send_ack(tunnel_packet)

    async def handle_data_request(self, tunnel_packet: Tunnel):
        await self.client_manager.write_to_client(
            tunnel_packet.client_id,
            tunnel_packet.sequence_number,
            tunnel_packet.payload
        )
        self.send_ack(tunnel_packet)

    async def handle_ack_request(self, tunnel_packet: Tunnel):
        self.packets_requiring_ack[(tunnel_packet.client_id, tunnel_packet.sequence_number)].set()

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
                log.debug(f'wrong magic (identifier={new_icmp_packet.identifier})'
                          f'(seq_num={new_icmp_packet.sequence_number}), ignoring')
                continue

            tunnel_packet = Tunnel()
            tunnel_packet.ParseFromString(new_icmp_packet.payload)
            log.debug(f'received:\n{tunnel_packet}')

            if tunnel_packet.direction == self.direction:
                log.debug('ignoring packet headed in the wrong direction')
                continue

            actions = {
                Tunnel.Action.start: self.handle_start_request,
                Tunnel.Action.end: self.handle_end_request,
                Tunnel.Action.data: self.handle_data_request,
                Tunnel.Action.ack: self.handle_ack_request,

            }
            try:
                await actions[tunnel_packet.action](tunnel_packet)
            except Exception as e:
                print(e)

    async def handle_incoming_from_tcp_channel(self):
        while True:
            data, client_id, sequence_number = await self.incoming_from_tcp_channel.get()

            new_tunnel_packet = Tunnel(
                client_id=client_id,
                sequence_number=sequence_number,
                action=Tunnel.Action.data,
                direction=self.direction,
                payload=data,
            )
            asyncio.create_task(self.send_icmp_packet_and_wait_for_ack(new_tunnel_packet))

    async def wait_for_stale_connection(self):
        while True:
            client_id = await self.stale_tcp_connections.get()

            new_tunnel_packet = Tunnel(
                client_id=client_id,
                action=Tunnel.Action.end,
                direction=self.direction,
            )

            await self.send_icmp_packet_and_wait_for_ack(new_tunnel_packet)
            await self.client_manager.remove_client(client_id)  # remove client, doesnt matter if the packet was acked.

    def send_ack(self, tunnel_packet: Tunnel):
        new_tunnel_packet = Tunnel(
            client_id=tunnel_packet.client_id,
            sequence_number=tunnel_packet.sequence_number,
            action=Tunnel.Action.ack,
            direction=self.direction,
        )
        self.send_icmp_packet(
            icmp_packet.ICMPType.EchoReply,
            new_tunnel_packet.SerializeToString(),
        )

    async def send_icmp_packet_and_wait_for_ack(self, tunnel_packet: Tunnel):
        """
        coroutine that tries to send a icmp packet and assert that an ack was received. if an ack wasnt received, send again, up to 3 times.
        :param tunnel_packet: the packet to send on the icmp socket.
        :return: boolean representing wether the packet was successfully acked.
        """
        self.packets_requiring_ack[(tunnel_packet.client_id, tunnel_packet.sequence_number)] = asyncio.Event()

        for _ in range(3):
            self.send_icmp_packet(
                icmp_packet.ICMPType.EchoRequest,
                tunnel_packet.SerializeToString(),
            )
            try:
                await asyncio.wait_for(
                    self.packets_requiring_ack[(tunnel_packet.client_id, tunnel_packet.sequence_number)].wait(),
                    0.3
                )
                return
            except asyncio.TimeoutError:
                log.debug(f'failed to send, resending:\n{tunnel_packet}')
        log.info(f'message failed to send:\n{tunnel_packet}')

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
