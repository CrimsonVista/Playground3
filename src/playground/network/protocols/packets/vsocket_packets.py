from playground.network.packet import PacketType, FIELD_NOT_SET
from playground.network.packet.fieldtypes import UINT8, UINT16, UINT32, UINT64, \
                                                 STRING, BUFFER, \
                                                 ComplexFieldType, PacketFields
from playground.network.packet.fieldtypes.attributes import Optional                                                 


class VNICSocketOpenPacket(PacketType):
    DEFINITION_IDENTIFIER = "vsockets.VNICSocketOpenPacket"
    DEFINITION_VERSION    = "1.0"
    
    class SocketConnectData(PacketFields):
        FIELDS = [
            ("destination", STRING),
            ("destinationPort", UINT16)
        ]
        
    class SocketListenData(PacketFields):
        FIELDS = [
            ("sourcePort", UINT16)
        ]
    
    FIELDS = [
        ("callbackAddress", STRING),
        ("callbackPort", UINT16),
        
        ("connectData", ComplexFieldType(SocketConnectData, {Optional:True})),
        ("listenData", ComplexFieldType(SocketListenData, {Optional:True}))
    ]
    
    def isConnectType(self):
        return self.connectData != FIELD_NOT_SET and self.listenData == FIELD_NOT_SET
        
    def isListenType(self):
        return self.connectData == FIELD_NOT_SET and self.listenData != FIELD_NOT_SET

class VNICSocketOpenResponsePacket(PacketType):
    DEFINITION_IDENTIFIER = "vsockets.VNICSocketOpenResponsePacket"
    DEFINITION_VERSION    = "1.0"
    FIELDS = [
        ("port", UINT16),
        ("errorCode", UINT8({Optional:True})),
        ("errorMessage", STRING({Optional:True}))
    ]
    
    def isFailure(self):
        return (self.errorCode != FIELD_NOT_SET or self.errorMessage != FIELD_NOT_SET)
    
class VNICConnectionSpawnedPacket(PacketType):
    DEFINITION_IDENTIFIER = "vsockets.VNICConnectionSpawnedPacket"
    DEFINITION_VERSION    = "1.0"
    FIELDS = [
        ("spawnTcpPort", UINT16),
        ("source", STRING),
        ("sourcePort", UINT16),
        ("destination", STRING),
        ("destinationPort", UINT16)
    ]
    
        
def basicUnitTest():
    v1 = VNICSocketOpenPacket(callbackAddress="1.1.1.1", callbackPort=80)
    connectData = v1.SocketConnectData(destination="2.2.2.2",destinationPort=1000)
    v1.connectData = connectData
    
    assert v1.isConnectType()
    v1a = VNICSocketOpenPacket.Deserialize(v1.__serialize__())
    assert v1 == v1a
    
    v2 = VNICSocketOpenResponsePacket()
    v2.port = 666
    v2.errorCode = 1
    v2.errorMessage = "test failure"
    
    v2a = VNICSocketOpenResponsePacket.Deserialize(v2.__serialize__())
    assert v2 == v2a
    assert v2a.isFailure()
    
    v3 = VNICConnectionSpawnedPacket()
    v3.spawnTcpPort=555
    v3.source="0.0.0.0"
    v3.sourcePort=999
    v3.destination="1.2.3.4"
    v3.destinationPort=123
    
    v3a = VNICConnectionSpawnedPacket.Deserialize(v3.__serialize__())
    assert v3 == v3a
    
if __name__ == "__main__":
    basicUnitTest()
    print("Basic unit test completed successfully.")
    
    