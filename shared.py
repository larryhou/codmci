from twisted.internet.protocol import Protocol
from twisted.internet.endpoints import IPv4Address
import json, struct, io, datetime
from serialization import decode_system_information

__author__ = 'larryhou'

TRANSPORT_MAGIC_NUMBER = 0x12345678

class Enum(object):
    __name_map = {}

    @classmethod
    def name(cls, value):
        if not cls.__name_map:
            for k, v in vars(cls).items():
                name = ''.join([x.title() for x in k.split('_')])
                if k.isupper():
                    assert v not in cls.__name_map
                    cls.__name_map[v] = name
        return cls.__name_map.get(value) or 'Unknown'

class CollaborateMissions(Enum):
    REPORT_SYSTEM_STATS = 20000
    REPORT_PERFORMANCE_STATS = 20001
    REPORT_SYSTEM_PROFILER = 20002

class Broadcasts(Enum):
    CHAT = 30000

class Commands(Enum):
    ACKNOWLEDGE = 0
    SYSTEM_INFORMATION_REQ = 1
    SYSTEM_INFORMATION_RSP = 2
    SYSTEM_INFORMATION_NOTIFY = 10002
    HEARTBEAT_REQ = 3
    HEARTBEAT_RSP = 4
    COLLABORATE_REQ = 5
    COLLABORATE_RSP = 6
    COLLABORATE_NOTIFY = 10006
    COLLABORATE_MISSION_REQ = 7
    COLLABORATE_MISSION_RSP = 8
    COLLABORATE_COMPLETE_REQ = 9
    COLLABORATE_COMPLETE_RSP = 10
    SERVE_AS_SLAVE_REQ = 11
    SERVE_AS_SLAVE_RSP = 12
    BROADCAST_REQ = 13
    BROADCAST_RSP = 14
    BROADCAST_NOTIFY = 10014

class Exceptions(Enum):
    ERROR_FORMAT = -1
    NOT_IMPLEMENTED = -2
    COLLABORATE_TIMEOUT = -3

class TCP(Protocol):
    def __init__(self, address, verbose=True):
        self.address = address # type: IPv4Address
        self.__pack = b''
        self.__size = 0
        self.__received = 0
        self.__stage = 0
        self.verbose = verbose

    def print(self, msg):
        if not self.verbose: return
        ts = datetime.datetime.now().isoformat()
        print('[{}] {}:{} {}'.format(ts, self.address.host, self.address.port, msg))

    def get_command_name(self, command):
        return Commands.name(command)

    @staticmethod
    def decode_system_information(text):
        return decode_system_information(text)

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
