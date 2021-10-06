import asyncio
import logging
from TCPoverICMP import client_manager, icmp_socket, icmp_packet
from TCPoverICMP.proto import Tunnel


log = logging.getLogger(__name__)


class TunnelEndpoint:
    MAGIC_IDENTIFIER = 0xcafe
    MAGIC_SEQUENCE_NUMBER = 0xbabe
    ACK_WAITING_TIME = 0.7

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
        """
        generic handle for end request. remove client and send ack
        :param tunnel_packet: packet containing the client_id to remove.
        :return:
        """
        await self.client_manager.remove_client(tunnel_packet.client_id)
        self.send_ack(tunnel_packet)

    async def handle_data_request(self, tunnel_packet: Tunnel):
        """
        generic handle for data request. forwards to the proper client and sends an ack.
        :param tunnel_packet: the packet to send.
        """
        await self.client_manager.write_to_client(
            tunnel_packet.client_id,
            tunnel_packet.sequence_number,
            tunnel_packet.payload
        )
        self.send_ack(tunnel_packet)

    async def handle_ack_request(self, tunnel_packet: Tunnel):
        """
        generic handle for an ack request.
        packet can be recognized singularly by combining client_id and sequence_number
        :param tunnel_packet: the packet to ack.
        """
        packet_id = (tunnel_packet.client_id, tunnel_packet.sequence_number)
        if packet_id in self.packets_requiring_ack:
            self.packets_requiring_ack[packet_id].set()

    async def run(self):
        """
        run the whole tunnel endpoint, which pretty much means run all the basic tasks and gather them.
        """
        constant_coroutines = [
            self.handle_incoming_from_tcp_channel(),
            self.handle_incoming_from_icmp_channel(),
            self.wait_for_stale_connection(),
            self.icmp_socket.wait_for_incoming_packet(),
        ]
        running_tasks = [asyncio.create_task(coroutine) for coroutine in self.coroutines_to_run + constant_coroutines]

        await asyncio.gather(*running_tasks)

    async def handle_incoming_from_icmp_channel(self):
        """
        listen for new tunnel packets from the icmp channel. parse and execute them.
        """
        while True:
            new_icmp_packet = await self.incoming_from_icmp_channel.get()
            if new_icmp_packet.identifier != self.MAGIC_IDENTIFIER or new_icmp_packet.sequence_number != self.MAGIC_SEQUENCE_NUMBER:
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
            await actions[tunnel_packet.action](tunnel_packet)

    async def handle_incoming_from_tcp_channel(self):
        """
        await on the incoming_from_tcp_channel queue for new data packets to send on the icmp channel.
        """
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
        """
        await on the stale_tcp_connections queue for a stale client
        """
        while True:
            client_id = await self.stale_tcp_connections.get()

            new_tunnel_packet = Tunnel(client_id=client_id, action=Tunnel.Action.end, direction=self.direction)

            await self.send_icmp_packet_and_wait_for_ack(new_tunnel_packet)
            await self.client_manager.remove_client(client_id)  # remove client, doesnt matter if the packet was acked.

    def send_ack(self, tunnel_packet: Tunnel):
        """
        send an ack for a given packet using echoReply
        :param tunnel_packet: the packet to ack
        """
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
                    self.ACK_WAITING_TIME
                )
                self.packets_requiring_ack.pop((tunnel_packet.client_id, tunnel_packet.sequence_number))  # if i reached here, means that ack was received. can remove event.
                return True
            except asyncio.TimeoutError:
                log.debug(f'failed to send, resending:\n{tunnel_packet}')
        log.info(f'message failed to send:\n{tunnel_packet}\nremoving client.')
        await self.stale_tcp_connections.put(tunnel_packet.client_id)  # remove client, cannot send his messages.

    def send_icmp_packet(
            self,
            type: icmp_packet.ICMPType,
            payload: bytes
    ):
        """
        build and send an icmp packet on the icmp socket.
        :param type: wether to send an echoRequest or an echoReply
        :param payload: the payload to push into the icmp
        """
        new_icmp_packet = icmp_packet.ICMPPacket(
            type=type,
            identifier=self.MAGIC_IDENTIFIER,
            sequence_number=self.MAGIC_SEQUENCE_NUMBER,
            payload=payload
        )
        self.icmp_socket.sendto(new_icmp_packet, self.other_endpoint)
