from twisted.internet.protocol import Protocol
from twisted.internet.endpoints import IPv4Address
import json, struct, io, datetime

TRANSPORT_MAGIC_NUMBER = 0x12345678
__commands__ = {}

class Commands(object):
    ACKNOWLEDGE = 0
    SYSTEM_INFORMATION_REQ = 1
    SYSTEM_INFORMATION_RSP = 2
    SYSTEM_INFORMATION_NOTIFY = 1002
    HEARTBEAT_REQ = 3
    HEARTBEAT_RSP = 4
    SLAVE_STATE_REQ = 5
    SLAVE_STATE_RSP = 6
    NETWORK_SLAVE_STATES_REQ = 7
    NETWORK_SLAVE_STATES_RSP = 8
    NETWORK_SLAVES_NOTIFY = 1008
    SERVE_AS_SLAVE_REQ = 9
    SERVE_AS_SLAVE_RSP = 10

class Errors(object):
    ERROR_FORMAT = -1

class TCP(Protocol):

    def __init__(self, address):
        self.address = address # type: IPv4Address
        self.__pack = b''
        self.__size = 0
        self.__received = 0
        self.__stage = 0
        self.__commands = __commands__
        if not self.__commands:
            for k, v in vars(Commands).items():
                if not k.isupper(): continue
                name = ''.join([x.title() for x in k.split('_')])
                self.__commands[v] = name

    def print(self, msg):
        ts = datetime.datetime.now().isoformat()
        print('[{}] {}:{} {}'.format(ts, self.address.host, self.address.port, msg))

    def get_command_name(self, command):
        return self.__commands.get(command) or 'Unknown'

    @staticmethod
    def decode_system_information(text):
        string = io.StringIO(text)
        cursor = result = {}
        stack = []
        depth = {}
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
                    depth[padding] = len(stack)
                    cursor = entity  # type: dict[str, any]
                else:
                    shift = (len(stack) - depth[padding]) if padding in depth else 1
                    while shift > 0:
                        cursor = stack.pop()
                        shift -= 1
                indent = padding
            name = line[padding:sep].replace(' ', '')  # type: str
            entity = line[sep + 1:].lstrip()
            if not entity: entity = {}
            cursor[name] = entity
        return result

    def send(self, command, data=None, retcode=0):  # type: (int, any, int)->None
        msg = {'ret': retcode, 'command': command}
        if data is not None: msg['data'] = data
        msg['ts'] = datetime.datetime.now().timestamp()
        if command not in (Commands.HEARTBEAT_RSP, Commands.HEARTBEAT_REQ):
            self.print('{} {}'.format(self.get_command_name(command), json.dumps(msg, ensure_ascii=False)))
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
