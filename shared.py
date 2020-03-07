from twisted.internet.protocol import Protocol
import json, struct

TRANSPORT_MAGIC_NUMBER = 0x12345678

class Commands(object):
    ACKNOWLEDGE = 0
    SLAVE_INFO_REQ = 1
    SLAVE_INFO_RSP = 2
    SLAVE_INFO_NOTIFY = 1001
    HEART_BEAT_REQ = 3
    HEART_BEAT_RSP = 4

class Errors(object):
    ERROR_FORMAT = -1

class TCP(Protocol):

    def __init__(self):
        self.__pack = b''
        self.__size = 0
        self.__received = 0
        self.__stage = 0

    def send(self, command, data, retcode=0):  # type: (int, any, int)->None
        msg = {'ret': retcode, 'command': command, 'data': data}
        raw = json.dumps(msg, ensure_ascii=False).encode('utf-8')
        self.transport.write(struct.pack('>I', TRANSPORT_MAGIC_NUMBER))
        self.transport.write(struct.pack('>I', len(raw) + 8))
        self.transport.write(raw)

    def packReceived(self, data): # type: (bytes)->None
        pass

    def dataReceived(self, data):
        if self.__stage == 0:
            self.__pack = b''
            self.__received = 0
            number, = struct.unpack('>I', data[:4])
            if number != TRANSPORT_MAGIC_NUMBER: return
            self.__size, = struct.unpack('>I', data[4:8])
            self.__stage = 1
        self.__received += len(data)
        self.__pack += data
        if self.__stage == 1:
            if self.__received >= self.__size:
                self.__stage = 2
        if self.__stage == 2:
            self.packReceived(self.__pack[8:self.__size])
            self.__stage = 0
            if self.__received > self.__size:
                self.dataReceived(data=self.__pack[self.__size:])


    def acknowledge(self, command, data='success'):
        self.send(command=Commands.ACKNOWLEDGE, data=':{} {}'.format(command, data))
