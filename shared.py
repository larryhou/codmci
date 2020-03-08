from twisted.internet.protocol import Protocol
import json, struct, io

TRANSPORT_MAGIC_NUMBER = 0x12345678

class Commands(object):
    ACKNOWLEDGE = 0
    SYSTEM_INFO_REQ = 1
    SYSTEM_INFO_RSP = 2
    SYSTEM_INFO_NOTIFY = 1001
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

    @staticmethod
    def decode_system_information(text):
        string = io.StringIO(text)
        cursor = result = {}
        stack = []
        indent = 0
        entity = None
        for line in string.readlines():
            line = line[:-1].rstrip()
            if not line: continue
            padding = 0
            for n in range(len(line)):
                if line[n] != ' ':
                    padding = n
                    break
            sep = line.find(':')
            if indent != padding:
                if indent < padding:
                    stack.append(cursor)
                    cursor = entity  # type: dict[str, any]
                else:
                    cursor = stack.pop()
                indent = padding
            name = line[padding:sep]  # type: str
            entity = line[sep + 1:].lstrip()
            if not entity: entity = {}
            cursor[name] = entity
        return result

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
