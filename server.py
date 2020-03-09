#!/usr/bin/env python3

from twisted.internet import reactor, task
from twisted.internet.protocol import Factory, connectionDone
from twisted.internet.endpoints import IPv4Address
from shared import Commands, Errors, TCP, CollaborateMissions
import json, time, datetime

class CollaborateManager(object):
    def __init__(self, factory):
        self.factory = factory # type: ClientConnectionFactory
        self.__obserers = {}
        self.__waitings = {}
        self.__received = {}
        self.__timestamp = 0
        self.__running = False
        self.mission_timeout = 10.0
        self.failure_allowed = True

    @property
    def running(self): return self.__running

    def update(self):
        if len(self.__waitings) > 0:
            timestamp = datetime.datetime.now().timestamp()
            if len(self.__waitings) == 0:
                self.__broadcast()
            elif 0 < self.mission_timeout <= (timestamp - self.__timestamp):
                self.__broadcast() if self.failure_allowed else self.__abort()

    def __abort(self):
        for addr, _ in self.__obserers.items():
            client = self.factory.clients.get(addr)  # type: ClientConnection
            if client: client.send(command=Commands.COLLABORATE_NOTIFY, retcode=-1)
        self.__reset()

    def __reset(self):
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
            client.send(command=Commands.COLLABORATE_NOTIFY, data=notify)
        self.__reset()

    def dispatch_missions(self, sender, parameters):
        if not parameters: parameters = {}
        if 'mission_timeout' in parameters:
            self.mission_timeout = max(10.0, parameters['mission_timeout'])
        if 'failure_allowed' in parameters:
            self.failure_allowed = parameters['failure_allowed']
        self.__register_observer(sender)
        if self.factory.slave_count == 0:
            self.__broadcast()
            return
        print('++ dispatch missions', sender)
        if self.__running: return
        self.__running = True
        self.__timestamp = datetime.datetime.now().timestamp()
        for _, client in self.factory.clients.items(): # type: IPv4Address, ClientConnection
            if not client.is_slave: continue
            client.dispatch_collaborate_mission(parameters)
            print('## dispatch mission #{}'.format(client.uuid), client.address)
            self.__waitings[client.address] = True

    def finish(self, addr):
        del self.__waitings[addr]
        if len(self.__waitings) == 0:
            self.__broadcast()

    def receive(self, addr, rsp): # type: (IPv4Address, dict)->None
        self.__received[addr] = rsp
        print('>> receive mission artifact', addr)
        self.finish(addr)

    def __register_observer(self, addr):
        self.__obserers[addr] = True

class ClientConnection(TCP):
    def __init__(self, factory, addr):
        super(ClientConnection, self).__init__(address=addr)
        self.factory = factory # type: ClientConnectionFactory
        self.uuid = -1
        self.ifconfig = ''
        self.is_slave = False

    def dispatch_collaborate_mission(self, parameters):
        mission = {'id': self.uuid}
        mission.update(parameters)
        self.send(command=Commands.COLLABORATE_MISSION_REQ, data=mission)

    def connectionMade(self):
        self.factory.clients[self.address] = self
        self.print('new client #total={} #slaves={}'.format(len(self.factory.clients), self.factory.slave_count))

    def decode(self, info):
        print(json.dumps(info, ensure_ascii=False, indent=4))

    def packReceived(self, data):
        msg = json.loads(data, encoding='utf-8')
        command = msg.get('command')  # type: int
        payload = msg.get('data')  # type: dict
        if command not in self.factory.silent_commands:
            self.print('>>> {} {}'.format(self.get_command_name(command), data.decode('utf-8')))
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
        elif command == Commands.COLLABORATE_REQ:
            self.send(command=Commands.COLLABORATE_RSP, data={'msg': 'wait for asynchronous notify'})
            self.factory.collaborate.dispatch_missions(sender=self.address, parameters=payload)
        elif command == Commands.COLLABORATE_MISSION_RSP: # accept mission
            if payload and not payload.get('accepted'):
                self.factory.collaborate.finish(addr=self.address)
        elif command == Commands.COLLABORATE_COMPLETE_REQ:
            self.send(command=Commands.COLLABORATE_COMPLETE_RSP)
            self.factory.collaborate.receive(addr=self.address, rsp=msg)
        elif command == Commands.BROADCAST_REQ:
            self.send(command=Commands.BROADCAST_RSP)
            notify = {'sender': {'ip': self.address.host, 'port': self.address.port}}
            notify.update(payload)
            for _, client in self.factory.clients.items():
                if client != self: client.send(command=Commands.BROADCAST_NOTIFY, data=notify)
        elif command < 100:
            self.send(command=command+1, data={'msg': 'success with auto response'})

    def connectionLost(self, reason=connectionDone):
        del self.factory.clients[self.address]
        if self.is_slave: self.factory.slave_count -= 1
        self.print('connection lost #total={} #slaves={}'.format(len(self.factory.clients), self.factory.slave_count))

class ClientConnectionFactory(Factory):
    def __init__(self):
        self.clients = {}  # type: dict[IPv4Address, ClientConnection]
        self.sequence = 0
        self.collaborate = CollaborateManager(self)
        self.slave_count = 0
        self.silent_commands = (
            Commands.HEARTBEAT_REQ,
            Commands.HEARTBEAT_RSP,
        )

    def update(self):
        self.collaborate.update()

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