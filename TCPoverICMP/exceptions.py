class ClientClosedConnectionError(Exception):
    pass


class WriteAttemptedToNonExistentClient(Exception):
    pass


class ReadAttemptedFromNonExistentClient(Exception):
    pass


class ClientAlreadyExistsError(Exception):
    pass


class RemovingClientThatDoesntExistError(Exception):
    pass


class WrongChecksumOnICMPPacket(Exception):
    pass


class InvalidICMPCode(Exception):
    pass


class RecvReturnedEmptyString(Exception):
    pass
