#!/usr/bin/env python3

import json

from twisted.internet import reactor
from twisted.internet.protocol import ClientFactory

from shared import Commands, TCP


class CheckProtocol(TCP):
    def __init__(self, options):
        super(CheckProtocol, self).__init__()
        self.options = options

    def connectionMade(self):
        self.send(command=Commands.NETWORK_SLAVE_STATES_REQ, data={})

    def packReceived(self, data):
        msg = json.loads(data, encoding='utf-8') # type: dict
        command = msg.get('command') # type: int
        payload = msg.get('data')
        if command == Commands.NETWORK_SLAVES_NOTIFY:
            self.transport.loseConnection()
            for it in payload:
                if not self.options.hardware: del it['Hardware']
                if not self.options.storage: del it['Storage']
                if not self.options.wifi: del it['Wi-Fi']
            print(json.dumps(payload, ensure_ascii=False, indent=4))

class CheckFactory(ClientFactory):
    def __init__(self, options):
        self.options = options

    def buildProtocol(self, addr):
        return CheckProtocol(options=self.options)

    def clientConnectionLost(self, connector, reason):
        reactor.stop()

def main():
    import argparse, sys
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--server', '-s', required=True, type=str, help='server address')
    arguments.add_argument('--port', '-p', required=True, type=int, help='server port')
    arguments.add_argument('--hardware', '-hw', action='store_true')
    arguments.add_argument('--storage', '-sg', action='store_true')
    arguments.add_argument('--wifi', '-wf', action='store_true')
    options = arguments.parse_args(sys.argv[1:])
    reactor.connectTCP(options.server, options.port, CheckFactory(options))
    reactor.run()

if __name__ == '__main__':
    main()