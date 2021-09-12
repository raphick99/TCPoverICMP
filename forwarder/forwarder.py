import asyncio
import logging

from core import queue_manager
from tcp import server
from icmp import icmp_packet
from proto import Tunnel


log = logging.getLogger(__name__)


class Forwarder(queue_manager.TunnelEndpoint):
    def __init__(self, host, port, destination_host, destination_port):
        super(Forwarder, self).__init__()
        log.info(f'forwarding to {destination_host}:{destination_port}')
        self.destination_host = destination_host
        self.destination_port = destination_port
        self.incoming_tcp_connections = asyncio.Queue(maxsize=1000)
        self.tcp_server = server.Server(host, port, self.incoming_tcp_connections)
        self.coroutines_to_run.append(self.tcp_server.serve_forever())
        self.coroutines_to_run.append(self.handle_incoming_from_icmp_channel())
        self.coroutines_to_run.append(self.handle_incoming_from_tcp_channel())
        self.coroutines_to_run.append(self.wait_for_new_connection())

    @property
    def other_endpoint(self):
        return '192.168.23.153'

    async def handle_incoming_from_icmp_channel(self):
        while True:
            new_icmp_packet = await self.incoming_from_icmp_channel.get()
            if not self.client_manager.client_exists(new_icmp_packet.identifier):
                log.debug('received icmp packet that isnt meant for me.')
                continue
            tunnel_packet = Tunnel()
            tunnel_packet.ParseFromString(new_icmp_packet.payload)
            log.debug(f'received {tunnel_packet}')

            if tunnel_packet.direction == Tunnel.Direction.to_proxy:
                log.debug('ignoring packet headed in the wrong direction')
                continue

            if tunnel_packet.state == Tunnel.State.start:
                log.debug('invalid start command. ignoring')
                continue
            elif tunnel_packet.state == Tunnel.State.end:
                log.debug(f'received end command. ending {new_icmp_packet.identifier}')
                self.client_manager.remove_client(new_icmp_packet.identifier)
            elif tunnel_packet.state == Tunnel.State.data:
                await self.client_manager.write_to_client(tunnel_packet.payload, new_icmp_packet.identifier)
            elif tunnel_packet.state == Tunnel.State.ack:
                # currently not doing anything with acks
                pass

    async def wait_for_new_connection(self):
        while True:
            client_id, reader, writer = await self.incoming_tcp_connections.get()

            new_tunnel_packet = Tunnel(
                ip=self.destination_host,
                port=self.destination_port,
                state=Tunnel.State.start,
                direction=Tunnel.Direction.to_proxy,
                payload=b'',
            )
            new_icmp_packet = icmp_packet.ICMPPacket(
                type=icmp_packet.ICMPType.EchoRequest,
                identifier=client_id,
                sequence_number=0,
                payload=new_tunnel_packet.SerializeToString(),
            )
            self.icmp_socket.sendto(new_icmp_packet)

            self.client_manager.add_client(client_id, reader, writer)

    async def handle_incoming_from_tcp_channel(self):
        while True:
            data, client_id, seq_num = await self.incoming_from_tcp_channel.get()

            new_tunnel_packet = Tunnel(
                ip='',
                port=0,
                state=Tunnel.State.data,
                direction=Tunnel.Direction.to_proxy,
                payload=data,
            )
            new_icmp_packet = icmp_packet.ICMPPacket(
                type=icmp_packet.ICMPType.EchoRequest,
                identifier=client_id,
                sequence_number=seq_num,
                payload=new_tunnel_packet.SerializeToString(),
            )
            self.icmp_socket.sendto(new_icmp_packet)
