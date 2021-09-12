import asyncio
import logging

from core import queue_manager
from icmp import icmp_packet
from proto import Tunnel


log = logging.getLogger(__name__)


class Proxy(queue_manager.QueueManager):
    def __init__(self):
        super(Proxy, self).__init__()
        self.coroutines_to_run.append(self.handle_incoming_from_icmp_channel())
        self.coroutines_to_run.append(self.handle_incoming_from_tcp_channel())
        self.coroutines_to_run.append(self.wait_for_stale_connection())

    @property
    def other_endpoint(self):
        return '192.168.23.152'

    async def handle_incoming_from_icmp_channel(self):
        while True:
            new_icmp_packet = await self.incoming_from_icmp_channel.get()
            tunnel_packet = Tunnel()
            tunnel_packet.ParseFromString(new_icmp_packet.payload)
            log.debug(f'received {tunnel_packet}')

            if tunnel_packet.direction == Tunnel.Direction.to_forwarder:
                log.debug('ignoring packet headed in the wrong direction')
                continue

            if tunnel_packet.state == Tunnel.State.start:
                reader, writer = await asyncio.open_connection(tunnel_packet.ip, tunnel_packet.port)
                # log.debug(f'received start command. (client_id={new_icmp_packet.identifier}'
                #           f') connecting to {tunnel_packet.ip}:{tunnel_packet.port}')
                self.client_manager.add_client(
                    client_id=new_icmp_packet.identifier,
                    reader=reader,
                    writer=writer,
                )
            elif tunnel_packet.state == Tunnel.State.end:
                # log.debug(f'received end command. (client_id={new_icmp_packet.identifier})')
                self.client_manager.remove_client(new_icmp_packet.identifier)
            elif tunnel_packet.state == Tunnel.State.data:
                await self.client_manager.write_to_client(tunnel_packet.payload, new_icmp_packet.identifier)
            elif tunnel_packet.state == Tunnel.State.ack:
                # currently not doing anything with acks
                pass

    async def handle_incoming_from_tcp_channel(self):
        while True:
            data, client_id, seq_num = await self.incoming_from_tcp_channel.get()

            new_tunnel_packet = Tunnel(
                ip='',
                port=0,
                state=Tunnel.State.data,
                direction=Tunnel.Direction.to_forwarder,
                payload=data,
            )
            new_icmp_packet = icmp_packet.ICMPPacket(
                type=icmp_packet.ICMPType.EchoRequest,
                identifier=client_id,
                sequence_number=seq_num,
                payload=new_tunnel_packet.SerializeToString(),
            )
            self.icmp_socket.sendto(new_icmp_packet)

    async def wait_for_stale_connection(self):
        while True:
            client_id = await self.stale_tcp_connections.get()

            new_tunnel_packet = Tunnel(
                ip='',
                port=0,
                state=Tunnel.State.end,
                direction=Tunnel.Direction.to_forwarder,
                payload=b'',
            )

            new_icmp_packet = icmp_packet.ICMPPacket(
                type=icmp_packet.ICMPType.EchoRequest,
                identifier=client_id,
                sequence_number=0,
                payload=new_tunnel_packet.SerializeToString(),
            )
            self.icmp_socket.sendto(new_icmp_packet)

            self.client_manager.remove_client(client_id)
