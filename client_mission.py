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

    def etime(self, data):
        data['etime'] = datetime.datetime.now().timestamp()


class NotImplementedMission(Mission):
    def schedule(self):
        self.etime(self.parameters)
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
        self.etime(self.parameters)
        respond.update(self.parameters)
        self.client.send(command=Commands.COLLABORATE_COMPLETE_REQ, data=respond)

class ReportSystemProfiler(Mission):
    def schedule(self):
        import os, serialization
        info = os.popen('system_profiler SPHardwareDataType SPStorageDataType SPNetworkDataType SPDisplaysDataType SPUSBDataType 2>/dev/null').read() # type: str
        respond = serialization.decode_system_information(info)
        self.etime(self.parameters)
        respond.update(self.parameters)
        self.client.send(command=Commands.COLLABORATE_COMPLETE_REQ, data=respond)
