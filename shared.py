from twisted.internet.protocol import Protocol
from twisted.internet.endpoints import IPv4Address
import json, struct, io, datetime

__author__ = 'larryhou'

TRANSPORT_MAGIC_NUMBER = 0x12345678

class Enum(object):
    __reverse_map = {}

    @classmethod
    def name(cls, x):
        if not cls.__reverse_map:
            for k, v in vars(cls).items():
                name = ''.join([x.title() for x in k.split('_')])
                if k.isupper(): cls.__reverse_map[v] = name
        return cls.__reverse_map.get(x)

class CollaborateMissions(Enum):
    REPORT_SLAVE_STATE = 20000

class Broadcasts(Enum):
    CHAT = 30000

class Commands(Enum):
    ACKNOWLEDGE = 0
    SYSTEM_INFORMATION_REQ = 1
    SYSTEM_INFORMATION_RSP = 2
    SYSTEM_INFORMATION_NOTIFY = 10002
    HEARTBEAT_REQ = 3
    HEARTBEAT_RSP = 4
    COLLABORATE_MISSION_REQ = 5
    COLLABORATE_MISSION_RSP = 6
    COLLABORATE_COMPLETE_REQ = 500
    COLLABORATE_COMPLETE_RSP = 600
    COLLABORATE_REQ = 7
    COLLABORATE_RSP = 8
    COLLABORATE_NOTIFY = 10008
    SERVE_AS_SLAVE_REQ = 9
    SERVE_AS_SLAVE_RSP = 10
    BROADCAST_REQ = 11
    BROADCAST_RSP = 12
    BROADCAST_NOTIFY = 10012

class ProtocolExceptions(Enum):
    ERROR_FORMAT = -1
    NOT_IMPLEMENTED = -2
    COLLABORATE_TIMEOUT = -3

class TCP(Protocol):
    def __init__(self, address):
        self.address = address # type: IPv4Address
        self.__pack = b''
        self.__size = 0
        self.__received = 0
        self.__stage = 0

    def print(self, msg):
        ts = datetime.datetime.now().isoformat()
        print('[{}] {}:{} {}'.format(ts, self.address.host, self.address.port, msg))

    def get_command_name(self, command):
        return Commands.name(command) or 'Unknown'

    @staticmethod
    def decode_system_information(text):
        string = io.StringIO(text)
        cursor = result = {}
        stack = []
        depth = {}
        indent = 0
        entity = None
        entity_name = ''
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
                    depth[padding] = len(stack)
                    if not isinstance(entity, dict):
                        entity = cursor[entity_name] = {}
                    cursor = entity  # type: dict[str, any]
                else:
                    shift = (len(stack) - depth[padding]) if padding in depth else 1
                    while shift > 0:
                        cursor = stack.pop()
                        shift -= 1
                indent = padding
            entity_name = line[padding:sep].replace(' ', '')  # type: str
            entity = line[sep + 1:].lstrip()
            if not entity: entity = {}
            cursor[entity_name] = entity
        return result

    def send(self, command, data=None, retcode=0, info=''):
        request = {'retcode': retcode, 'command': command}
        if data is not None: request['data'] = data
        request['ts'] = datetime.datetime.now().timestamp()
        if retcode != 0:
            data['error'] = {'info':info, 'code':retcode}
        if command not in (Commands.HEARTBEAT_RSP, Commands.HEARTBEAT_REQ):
            self.print('<<< {} {}'.format(self.get_command_name(command), json.dumps(request, ensure_ascii=False)))
        serialized_request = json.dumps(request, ensure_ascii=False).encode('utf-8')
        self.transport.write(struct.pack('>I', TRANSPORT_MAGIC_NUMBER))
        self.transport.write(struct.pack('>I', len(serialized_request) + 8))
        self.transport.write(serialized_request)

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
