#!/usr/bin/env python3

from twisted.internet import reactor
from twisted.internet.protocol import Factory, connectionDone
from twisted.internet.endpoints import IPv4Address
from shared import Commands, Errors, TCP
import json, time

class SlaveConnection(TCP):
    def __init__(self, factory, addr):
        super(SlaveConnection, self).__init__()
        self.factory = factory # type: SlaveConnectionFactory
        self.address = addr # type: IPv4Address
        self.address_string = '{}:{}'.format(self.address.host, self.address.port)
        self.uuid = -1
        self.ifconfig = ''

    def print(self, msg):
        ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        print('[{}] #{} \033[33m{} \033[36m{}\033[0m'.format(ts, self.uuid, self.address_string, msg))

    def connectionMade(self):
        self.factory.slaves[self.address] = self
        self.print('new slave #total={}'.format(len(self.factory.slaves)))

    def decode(self, info):
        print(json.dumps(self.decode_system_information(info), ensure_ascii=False))

    def packReceived(self, data):
        msg = json.loads(data, encoding='utf-8')
        command = msg.get('command')  # type: int
        payload = msg.get('data')  # type: dict
        if command in (Commands.SYSTEM_INFO_RSP, Commands.SYSTEM_INFO_NOTIFY):
            self.ifconfig = payload
            self.decode(payload.get('SPNetworkDataType'))
            self.decode(payload.get('SPAirPortDataType'))
            self.acknowledge(command)
        elif command == Commands.HEART_BEAT_REQ:
            self.send(command=Commands.HEART_BEAT_RSP, data=payload)
            return
        self.print(msg)

    def connectionLost(self, reason=connectionDone):
        del self.factory.slaves[self.address]
        self.print('connection lost #remain={}'.format(len(self.factory.slaves)))

class SlaveConnectionFactory(Factory):
    def __init__(self):
        self.slaves = {}
        self.sequence = 0

    def buildProtocol(self, addr):
        slave = SlaveConnection(factory=self, addr=addr)
        slave.uuid = self.sequence
        self.sequence += 1
        return slave

def main():
    import argparse, sys
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--port', '-p', required=True, type=int, help='server listen port number')
    options = arguments.parse_args(sys.argv[1:])
    reactor.listenTCP(options.port, SlaveConnectionFactory())
    reactor.run()

if __name__ == '__main__':
    main()