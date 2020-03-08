#!/usr/bin/env python3
import os, json, time, psutil
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.internet import reactor, task
from shared import Commands, Errors, TCP

class ClientSlaveConnection(TCP):
    def __init__(self):
        super(ClientSlaveConnection, self).__init__()
        self.system_information = {}  # type: dict
        self.timestamp = 0.0
        self.heart_beat_interval = 2.0

    def update(self):
        timestamp = time.mktime(time.localtime())
        if timestamp - self.timestamp >= self.heart_beat_interval:
            self.timestamp = timestamp
            self.send_heart_beat()

    def send_heart_beat(self):
        self.send(command=Commands.HEARTBEAT_REQ, data={'ts': time.mktime(time.localtime())})

    def connectionMade(self):
        self.send(command=Commands.SERVE_AS_SLAVE_REQ)
        self.send_slave_info(command=Commands.SYSTEM_INFORMATION_NOTIFY)
        self.send_heart_beat()

    def send_slave_info(self, command):
        data = {'ifconfig': os.popen('ifconfig').read(),
                'uname'   : os.popen('uname -a').read()[:-1],
                'whoami'  : os.popen('whoami').read()[:-1]}
        for name in 'SPHardwareDataType SPNetworkDataType SPStorageDataType SPDisplaysDataType SPUSBDataType'.split(' '):
            data[name] = os.popen('system_profiler {} 2>/dev/null'.format(name)).read() # type: str
        self.system_information = data
        self.send(command=command, data=self.system_information)

    def send_client_state(self):
        rsp = {'User': self.system_information.get('whoami')}
        uname = self.system_information.get('uname') # type: str
        beg = uname.find(' ')
        end = uname.find(' ', beg+1)
        rsp['Machine'] = uname[beg+1:end]
        rsp['CPU'] = psutil.cpu_percent()
        memory = rsp['MEM'] = psutil.virtual_memory()._asdict()
        for k, v in memory.items():
            if v < 1024: continue
            memory[k] = float(v) / (1 << 20)
        memory['unit'] = 'MB'
        hardware = self.decode_system_information(self.system_information.get('SPHardwareDataType'))
        rsp.update(hardware)
        storage = self.decode_system_information(self.system_information.get('SPStorageDataType'))
        rsp.update(storage)
        network = self.decode_system_information(self.system_information.get('SPNetworkDataType'))
        for k, v in network['Network'].items():
            if 'IPv4Addresses' in v:
                rsp['Network'] = v
                break
        self.send(command=Commands.SLAVE_STATE_RSP, data=rsp)

    def packReceived(self, data):
        msg = json.loads(data, encoding='utf-8')
        command = msg.get('command') # type: int
        payload = msg.get('data') # type: dict
        if command == Commands.SYSTEM_INFORMATION_REQ:
            self.send_slave_info(command=Commands.SYSTEM_INFORMATION_RSP)
        elif command == Commands.SLAVE_STATE_REQ:
            self.send_client_state()
        elif command == Commands.HEARTBEAT_RSP:
            return
        print(self.get_command_name(command), msg)

class ClientSlaveConnectionFactory(ReconnectingClientFactory):
    def __init__(self):
        self.connection = None # type: ClientSlaveConnection

    def buildProtocol(self, addr):
        self.resetDelay()
        ClientSlaveConnectionFactory.maxDelay = 300
        self.connection = ClientSlaveConnection()
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
    arguments.add_argument('--server', '-s', required=True, type=str, help='server address')
    arguments.add_argument('--port', '-p', required=True, type=int, help='server port')
    options = arguments.parse_args(sys.argv[1:])

    factory = ClientSlaveConnectionFactory()
    t = task.LoopingCall(factory.update)
    t.start(1.0/5)

    reactor.connectTCP(options.server, options.port, factory)
    reactor.run()

if __name__ == '__main__':
    main()