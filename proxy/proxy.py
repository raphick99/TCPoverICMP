import asyncio
import logging

from core import tunnel_endpoint
from proto import Tunnel


log = logging.getLogger(__name__)


class Proxy(tunnel_endpoint.TunnelEndpoint):
    def __init__(self):
        super(Proxy, self).__init__()
        self.coroutines_to_run.append(self.handle_incoming_from_icmp_channel())
        self.coroutines_to_run.append(self.handle_incoming_from_tcp_channel())

    @property
    def other_endpoint(self):
        return '192.168.23.152'

    @property
    def direction(self):
        return Tunnel.Direction.to_forwarder

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
