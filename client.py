#!/usr/bin/env python3
import os, json, time, psutil, datetime
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.internet import reactor, task
from twisted.internet.endpoints import IPv4Address
from shared import Commands, Exceptions, TCP, CollaborateMissions
from client_mission import *

__author__ = 'larryhou'

class ClientSlaveConnection(TCP):
    def __init__(self, address, factory):
        super(ClientSlaveConnection, self).__init__(address)
        self.factory = factory # type: ClientSlaveConnectionFactory
        self.system_information = {}  # type: dict
        self.timestamp = 0.0
        self.heart_beat_interval = 10.0
        self.__missions = {} # type: dict[int, Mission]
        self.__mission_sequence = 0

    def register_mission(self, mission):
        self.__mission_sequence += 1
        self.__missions[self.__mission_sequence] = mission
        return self.__mission_sequence

    def unregister_mission(self, sequence):
        if sequence in self.__missions:
            del self.__missions[sequence]

    def update(self):
        timestamp = time.mktime(time.localtime())
        if timestamp - self.timestamp >= self.heart_beat_interval:
            self.timestamp = timestamp
            self.send_heartbeat()
        for mission in self.__missions:
            mission.update()

    def send_heartbeat(self):
        self.send(command=Commands.HEARTBEAT_REQ, data={'ts': time.mktime(time.localtime())})

    def connectionMade(self):
        self.send(command=Commands.SERVE_AS_SLAVE_REQ)
        self.send_system_information(command=Commands.SYSTEM_INFORMATION_NOTIFY)
        self.send_heartbeat()

    def run_system_profiler(self, name):
        text = os.popen('system_profiler {} 2>/dev/null'.format(name)).read()
        return self.decode_system_information(text) if text else {}

    def send_system_information(self, command):
        data = {'uname': os.popen('uname -a').read()[:-1],
                'whoami': os.popen('whoami').read()[:-1]}
        for name in 'SPHardwareDataType SPStorageDataType SPNetworkDataType SPDisplaysDataType SPUSBDataType'.split(' '):
            data[name] = self.run_system_profiler(name)
        self.system_information = data
        self.send(command=command, data=self.system_information)

    def dispatch_collaborate_mission(self, parameters):
        import client_mission
        mission = CollaborateMissions.REPORT_SYSTEM_STATS
        parameters['stime'] = datetime.datetime.now().timestamp()
        if 'mission' in parameters:
            mission = int(parameters['mission'])
        if mission == CollaborateMissions.REPORT_SYSTEM_STATS:
            client_mission.\
                ReportSystemStatsMission(client=self, parameters=parameters).schedule()
        elif mission == CollaborateMissions.REPORT_PERFORMANCE_STATS:
            client_mission.\
                ReportPerformanceStatsMission(client=self, parameters=parameters).schedule()
        elif mission == CollaborateMissions.REPORT_SYSTEM_PROFILER:
            client_mission.\
                ReportSystemProfilerMission(client=self, parameters=parameters).schedule()
        else:
            client_mission.\
                NotImplementedMission(client=self, parameters=parameters).schedule()

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