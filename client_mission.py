from client import ClientSlaveConnection
from shared import *
import datetime, psutil

__author__ = 'larryhou'


class Mission(object):
    def __init__(self, client, parameters):
        self.client = client  # type: ClientSlaveConnection
        self.parameters = parameters  # type: dict

    def schedule(self):
        pass

    def finish(self, respond):
        respond['etime'] = datetime.datetime.now().timestamp()


class NotImplementedMission(Mission):
    def schedule(self):
        self.finish(respond=self.parameters)
        self.client.send(command=Commands.COLLABORATE_COMPLETE_REQ,
                         retcode=ProtocolExceptions.NOT_IMPLEMENTED,
                         data=self.__parameters,
                         info='not implemented mission')


class ReportPerformanceMission(Mission):
    def schedule(self):
        respond = {'CPU':psutil.cpu_percent()}
        memory = respond['MEM'] = psutil.virtual_memory()._asdict()
        for k, v in memory.items():
            if v < 1024: continue
            memory[k] = float(v) / (1 << 20)
        respond.update(self.parameters)
        self.finish(respond)
        self.client.send(command=Commands.COLLABORATE_COMPLETE_REQ, data=respond)
