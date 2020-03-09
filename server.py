#!/usr/bin/env python3

from twisted.internet import reactor, task
from twisted.internet.protocol import Factory, connectionDone
from twisted.internet.endpoints import IPv4Address
from shared import Commands, Errors, TCP
import json, time, datetime

class NetworkManager(object):
    def __init__(self, factory):
        self.factory = factory # type: ClientConnectionFactory
        self.__obserers = {}
        self.__waitings = {}
        self.__received = {}
        self.__timestamp = 0
        self.__running = False

    @property
    def running(self): return self.__running

    def update(self):
        if len(self.__waitings) > 0:
            timestamp = datetime.datetime.now().timestamp()
            if timestamp - self.__timestamp > 1.0:
                removing = []
                for addr, _ in self.__waitings.items():
                    if addr not in self.factory.clients: removing.append(addr)
                for addr in removing: del self.__waitings[addr]
            if timestamp - self.__timestamp > 10.0 or len(self.__waitings) == 0:
                self.__broadcast()

    def __clear(self):
        self.__init__(self.factory)

    def __broadcast(self):
        notify = []
        for addr, rsp in self.__received.items(): # type: IPv4Address, dict
            data = rsp.get('data')
            item = {'Port': addr.port}
            item.update(data)
            notify.append(item)
        for addr, _ in self.__obserers.items():
            client = self.factory.clients[addr] # type: ClientConnection
            client.send(command=Commands.NETWORK_SLAVES_NOTIFY, data=notify)
        self.__clear()

    def request(self, addr):
        self.__register(addr)
        if self.factory.slave_count == 0:
            self.__broadcast()
            return
        print('++ request slave states', addr)
        if self.__running: return
        self.__running = True
        self.__timestamp = datetime.datetime.now().timestamp()

        for _, client in self.factory.clients.items(): # type: IPv4Address, ClientConnection
            if not client.is_slave: continue
            client.send_network_state_request()
            print('## collect state #{}'.format(client.uuid), client.address)
            self.__waitings[client.address] = True

    def receive(self, addr, rsp): # type: (IPv4Address, dict)->None
        self.__received[addr] = rsp
        print('>> receive state', addr)
        del self.__waitings[addr]
        if len(self.__waitings) == 0:
            self.__broadcast()

    def __register(self, addr):
        self.__obserers[addr] = True

class ClientConnection(TCP):
    def __init__(self, factory, addr):
        super(ClientConnection, self).__init__(address=addr)
        self.factory = factory # type: ClientConnectionFactory
        self.uuid = -1
        self.ifconfig = ''
        self.is_slave = False

    def send_network_state_request(self):
        self.send(command=Commands.SLAVE_STATE_REQ, data={'index': self.uuid})

    def connectionMade(self):
        self.factory.clients[self.address] = self
        self.print('new client #total={} #slaves={}'.format(len(self.factory.clients), self.factory.slave_count))

    def decode(self, info):
        print(json.dumps(info, ensure_ascii=False, indent=4))

    def packReceived(self, data):
        msg = json.loads(data, encoding='utf-8')
        command = msg.get('command')  # type: int
        payload = msg.get('data')  # type: dict
        if command in (Commands.SYSTEM_INFORMATION_RSP, Commands.SYSTEM_INFORMATION_NOTIFY):
            self.ifconfig = payload
            self.decode(payload.get('SPHardwareDataType'))
            self.acknowledge(command)
        elif command == Commands.SERVE_AS_SLAVE_REQ:
            self.is_slave = True
            self.factory.slave_count += 1
            self.send(command=Commands.SERVE_AS_SLAVE_RSP)
        elif command == Commands.HEARTBEAT_REQ:
            self.send(command=Commands.HEARTBEAT_RSP, data=payload)
            return
        elif command == Commands.NETWORK_SLAVE_STATES_REQ:
            self.send(command=Commands.NETWORK_SLAVE_STATES_RSP, data={'msg': 'wait for asynchronous notify'})
            self.factory.network.request(addr=self.address)
        elif command == Commands.SLAVE_STATE_RSP:
            self.factory.network.receive(addr=self.address, rsp=msg)
        elif command == Commands.BROADCAST_REQ:
            self.send(command=Commands.BROADCAST_RSP)
            notify = {'sender': {'ip':self.address.host, 'port':self.address.port}}
            notify.update(payload)
            for _, client in self.factory.clients.items():
                if client != self: client.send(command=Commands.BROADCAST_NOTIFY, data=notify)
        elif command < 100:
            self.send(command=command+1, data={'msg': 'success with auto response'})
        self.print('{} {}'.format(self.get_command_name(command), data.decode('utf-8')))

    def connectionLost(self, reason=connectionDone):
        del self.factory.clients[self.address]
        if self.is_slave: self.factory.slave_count -= 1
        self.print('connection lost #total={} #slaves={}'.format(len(self.factory.clients), self.factory.slave_count))

class ClientConnectionFactory(Factory):
    def __init__(self):
        self.clients = {}  # type: dict[IPv4Address, ClientConnection]
        self.sequence = 0
        self.network = NetworkManager(self)
        self.slave_count = 0

    def update(self):
        self.network.update()

    def buildProtocol(self, addr):
        client = ClientConnection(factory=self, addr=addr)
        client.uuid = self.sequence
        self.sequence += 1
        return client

def main():
    import argparse, sys
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--port', '-p', required=True, type=int, help='server listen port number')
    options = arguments.parse_args(sys.argv[1:])
    factory = ClientConnectionFactory()
    t = task.LoopingCall(factory.update)
    t.start(1.0/5)
    reactor.listenTCP(options.port, factory)
    reactor.run()

if __name__ == '__main__':
    main()