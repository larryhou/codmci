from client import ClientSlaveConnection
from shared import *

__author__ = 'larryhou'

class NotImplementedMission(object):
    def __init__(self, client, parameters):
        self.__client = client # type: ClientSlaveConnection
        self.__parameters = parameters # type: dict

    def schedule(self):
        self.__client.send(command=Commands.COLLABORATE_COMPLETE_REQ,
                           retcode=ProtocolExceptions.NOT_IMPLEMENTED,
                           data=self.__parameters,
                           info='not implemented mission')
