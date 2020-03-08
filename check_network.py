#!/usr/bin/env python3

import json

from twisted.internet import reactor
from twisted.internet.protocol import ClientFactory

from shared import Commands, TCP


class CheckProtocol(TCP):
    def connectionMade(self):
        self.send(command=Commands.NETWORK_SLAVE_STATES_REQ, data={})

    def packReceived(self, data):
        msg = json.loads(data, encoding='utf-8') # type: dict
        command = msg.get('command') # type: int
        if command == Commands.NETWORK_SLAVES_NOTIFY:
            self.transport.loseConnection()
            print(json.dumps(msg, ensure_ascii=False, indent=4))

class CheckFactory(ClientFactory):
    def buildProtocol(self, addr):
        return CheckProtocol()

    def clientConnectionLost(self, connector, reason):
        reactor.stop()

def main():
    import argparse, sys
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--server', '-s', required=True, type=str, help='server address')
    arguments.add_argument('--port', '-p', required=True, type=int, help='server port')
    options = arguments.parse_args(sys.argv[1:])
    reactor.connectTCP(options.server, options.port, CheckFactory())
    reactor.run()

if __name__ == '__main__':
    main()