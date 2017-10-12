'''
Created on Aug 20, 2013

@author: sethjn
'''

from playground.network.packet import PacketType, FIELD_NOT_SET
from playground.network.packet.fieldtypes import UINT16, STRING, BUFFER, LIST
from playground.network.packet.fieldtypes.attributes import Optional
from playground.network.protocols.packets.switching_packets import FramedPacketType

import random

class SPMPPacket(PacketType):
    DEFINITION_IDENTIFIER = "devices.management.SPMPPacket"
    DEFINITION_VERSION = "1.0"
    
    MAX_ID = (2**16)-1
    
    FIELDS = [  ("requestId", UINT16),
                ("request",   STRING),
                ("args",      LIST(STRING)),
                ("result",    STRING),
                ("error",     STRING({Optional:True})),
                
                # The security fields are generic on purpose. Different
                # security mechanisms have an arbitrary number of fields
                # For example, a security buffer could be a signature,
                # encrypted data, password data, etc.
                ("securityType", STRING({Optional:True})),
                ("security",  LIST(BUFFER, {Optional:True}))
                ]
                
    def generateRequestId(self):
        self.requestId = random.randint(0, self.MAX_ID)
        
    def failed(self):
        return self.error != FIELD_NOT_SET
    
class FramedSPMPWrapper(FramedPacketType):
    """
    This class is solely for wrapping the SPMP packet in a framed
    encoder
    """
    
    DEFINITION_IDENTIFIER = "devices.management.FramedSPMPWrapper"
    DEFINITION_VERSION = "1.0"
    
    FIELDS = [ ("spmpPacket", BUFFER) ]
    

    