import struct
import socket
import enum
from dataclasses import dataclass
from TCPoverICMP import exceptions


class ICMPType(enum.Enum):
    EchoReply = 0
    EchoRequest = 8


@dataclass
class ICMPPacket:
    type: ICMPType
    identifier: int
    sequence_number: int
    payload: bytes

    ICMP_STRUCT = struct.Struct('>BBHHH')
    CODE = 0

    @classmethod
    def deserialize(cls, packet: bytes):
        """
        classmethod for building ICMPPackets based on a stream of bytes
        :param packet: the packet that needs to be deserialized into ICMPPacket
        :return: the built ICMPPacket
        """
        raw_type, code, checksum, identifier, sequence_number = cls.ICMP_STRUCT.unpack(packet[:cls.ICMP_STRUCT.size])

        if code != cls.CODE:
            raise exceptions.InvalidICMPCode()

        computed_checksum = cls.compute_checksum(
            cls.ICMP_STRUCT.pack(raw_type, code, 0, identifier, sequence_number) + packet[cls.ICMP_STRUCT.size:]
        )

        if checksum != computed_checksum:
            raise exceptions.WrongChecksumOnICMPPacket()

        return cls(ICMPType(raw_type), identifier, sequence_number, packet[cls.ICMP_STRUCT.size:])

    def serialize(self):
        """
        serialize an instance of a ICMPPacket into a stream of bytes
        :return: the current ICMPPacket, serialized
        """
        packet_without_checksum = self.ICMP_STRUCT.pack(
            self.type.value,
            self.CODE,
            0,
            self.identifier,
            self.sequence_number
        ) + self.payload
        checksum = self.compute_checksum(data=packet_without_checksum)

        return self.ICMP_STRUCT.pack(
            self.type.value,
            self.CODE,
            checksum,
            self.identifier,
            self.sequence_number
        ) + self.payload

    # Taken from https://github.com/Akhavi/pyping/blob/master/pyping/core.py
    @staticmethod
    def compute_checksum(data: bytes):
        count_to = (int(len(data) / 2)) * 2
        total = 0
        count = 0

        while count < count_to:
            total += int.from_bytes(data[count:count+2], byteorder='little')
            count += 2

        # Handle last byte if applicable (odd-number of bytes)
        if count_to < len(data):  # Check for odd length
            total += data[-1]

        total &= 0xffffffff  # Truncate sum to 32 bits (a variance from ping.c, which
        # uses signed ints, but overflow is unlikely in ping)

        total = (total >> 16) + (total & 0xffff)    # Add high 16 bits to low 16 bits
        total += (total >> 16)					# Add carry from above (if any)
        result = ~total & 0xffff				# Invert and truncate to 16 bits
        result = socket.htons(result)

        return result
