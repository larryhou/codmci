#!/usr/bin/env python3
import os, json, time, psutil, datetime
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.internet import reactor, task
from twisted.internet.endpoints import IPv4Address
from shared import Commands, ProtocolExceptions, TCP, CollaborateMissions

class ClientSlaveConnection(TCP):
    def __init__(self, address, factory):
        super(ClientSlaveConnection, self).__init__(address)
        self.factory = factory # type: ClientSlaveConnectionFactory
        self.system_information = {}  # type: dict
        self.timestamp = 0.0
        self.heart_beat_interval = 10.0

    def update(self):
        timestamp = time.mktime(time.localtime())
        if timestamp - self.timestamp >= self.heart_beat_interval:
            self.timestamp = timestamp
            self.send_heartbeat()

    def send_heartbeat(self):
        self.send(command=Commands.HEARTBEAT_REQ, data={'ts': time.mktime(time.localtime())})

    def connectionMade(self):
        self.send(command=Commands.SERVE_AS_SLAVE_REQ)
        self.send_system_information(command=Commands.SYSTEM_INFORMATION_NOTIFY)
        self.send_heartbeat()

    def __run_system_profiler(self, name):
        text = os.popen('system_profiler {} 2>/dev/null'.format(name)).read()
        return self.decode_system_information(text) if text else {}

    def send_system_information(self, command):
        data = {'uname': os.popen('uname -a').read()[:-1],
                'whoami': os.popen('whoami').read()[:-1]}
        for name in 'SPHardwareDataType SPStorageDataType SPNetworkDataType SPDisplaysDataType SPUSBDataType'.split(' '):
            data[name] = self.__run_system_profiler(name)
        self.system_information = data
        self.send(command=command, data=self.system_information)

    def send_realtime_state(self, parameters):
        msg = {'User': self.system_information.get('whoami')}
        uname = self.system_information.get('uname')  # type: str
        beg = uname.find(' ')
        end = uname.find(' ', beg + 1)
        msg['Machine'] = uname[beg + 1:end]
        msg['CPU'] = psutil.cpu_percent()
        memory = msg['MEM'] = psutil.virtual_memory()._asdict()
        for k, v in memory.items():
            if v < 1024: continue
            memory[k] = float(v) / (1 << 20)
        memory['unit'] = 'MB'
        hardware = self.system_information.get('SPHardwareDataType')
        msg.update(hardware)
        storage = self.__run_system_profiler('SPStorageDataType')
        msg.update(storage)
        network = self.__run_system_profiler('SPNetworkDataType')
        for k, v in network['Network'].items():
            address = v.get('IPv4Addresses')
            if address:
                msg['Network'] = v
                msg['Address'] = address
                break
        msg.update(parameters)
        msg['etime'] = datetime.datetime.now().timestamp()
        self.send(command=Commands.COLLABORATE_COMPLETE_REQ, data=msg)

    def dispatch_collaborate_mission(self, parameters):
        import client_mission
        mission = CollaborateMissions.REPORT_SLAVE_STATE
        parameters['stime'] = datetime.datetime.now().timestamp()
        if 'mission' in parameters:
            mission = int(parameters['mission'])
        if mission == CollaborateMissions.REPORT_SLAVE_STATE:
            self.send_realtime_state(parameters)
        else:
            client_mission.NotImplementedMission(client=self, parameters=parameters).schedule()

    def packReceived(self, data):
        msg = json.loads(data, encoding='utf-8')
        command = msg.get('command') # type: int
        payload = msg.get('data') # type: dict
        if command not in self.factory.slient_commands:
            self.print('>>> {} {}'.format(self.get_command_name(command), data.decode('utf-8')))
        if command == Commands.SYSTEM_INFORMATION_REQ:
            self.send_system_information(command=Commands.SYSTEM_INFORMATION_RSP)
        elif command == Commands.COLLABORATE_MISSION_REQ:
            respond = {'accepted': True}
            respond.update(payload)
            self.send(command=Commands.COLLABORATE_MISSION_RSP, data=respond)
            self.dispatch_collaborate_mission(parameters=payload)
        elif command == Commands.BROADCAST_NOTIFY:
            pass

class ClientSlaveConnectionFactory(ReconnectingClientFactory):
    def __init__(self):
        self.connection = None # type: ClientSlaveConnection
        self.slient_commands = (
            Commands.HEARTBEAT_REQ,
            Commands.HEARTBEAT_RSP,
        )

    def buildProtocol(self, addr):
        self.resetDelay()
        ClientSlaveConnectionFactory.maxDelay = 300
        self.connection = ClientSlaveConnection(address=addr, factory=self)
        return self.connection

    def update(self):
        if self.connection: self.connection.update()

    def startedConnecting(self, connector):
        pass

    def clientConnectionFailed(self, connector, reason):
        print('connection fail {}'.format(reason))
        super(ClientSlaveConnectionFactory, self).clientConnectionFailed(connector, reason)
        self.connection = None

    def clientConnectionLost(self, connector, reason):
        print('connection lost {}'.format(reason))
        super(ClientSlaveConnectionFactory, self).clientConnectionLost(connector, reason)
        self.connection = None


def main():
    import argparse, sys
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--server', '-s', default='localhost', type=str, help='server address')
    arguments.add_argument('--port', '-p', required=True, type=int, help='server port')
    options = arguments.parse_args(sys.argv[1:])

    factory = ClientSlaveConnectionFactory()
    t = task.LoopingCall(factory.update)
    t.start(1.0/5)

    reactor.connectTCP(options.server, options.port, factory)
    reactor.run()

if __name__ == '__main__':
    main()