from playground.network.packet import PacketType, FIELD_NOT_SET
from playground.network.packet.fieldtypes import UINT16, UINT32, UINT64, \
                                                 STRING, BUFFER, \
                                                 ComplexFieldType, PacketFields
from playground.network.packet.fieldtypes.attributes import Optional                                                 


class AnnounceLinkPacket(PacketType):
    DEFINITION_IDENTIFIER = "switching.AnnounceLinkPacket"
    DEFINITION_VERSION    = "1.0"
    
    FIELDS = [
        ("address", STRING)
    ]

class WirePacket(PacketType):
    DEFINITION_IDENTIFIER = "switching.WirePacket"
    DEFINITION_VERSION    = "1.0"
    
    class FragmentData(PacketFields):
        FIELDS = [
            ("fragId",    UINT32),
            ("totalSize", UINT64),
            ("offset",    UINT64)
        ]
    
    FIELDS = [
        ("source",         STRING),
        ("sourcePort",     UINT16),
        ("destination",    STRING),
        ("destinationPort",UINT16),
        
        ("fragData",       ComplexFieldType(FragmentData, {Optional:True})),
        
        ("data",           BUFFER)
    ]
    
    def isFragment(self):
        return self.fragData != FIELD_NOT_SET
        
def basicUnitTest():
    from playground.network.packet import FIELD_NOT_SET
    
    announce1 = AnnounceLinkPacket(address="1.2.3.4")
    assert announce1.address == "1.2.3.4"
    
    announce2 = AnnounceLinkPacket()
    print(announce2.address)
    assert announce2.address == FIELD_NOT_SET
    
    announce2.address = announce1.address
    assert announce1.address == announce2.address
    
    deserializer = AnnounceLinkPacket.Deserializer()
    deserializer.update(announce1.__serialize__())
    deserializer.update(announce2.__serialize__())
    
    packets = list(deserializer.nextPackets())
    assert packets[0] == announce1
    assert packets[1] == announce2
    
    wirepacket1 = WirePacket(   source="1.2.3.4",
                                sourcePort=80,
                                destination="4.3.2.1",
                                destinationPort=2000,
                                
                                fragData=WirePacket.FragmentData(   fragId=1,
                                                                    totalSize=1000,
                                                                    offset=100),
                                data=b"this is a small buffer"
                                )
    assert wirepacket1.source=="1.2.3.4"
    assert wirepacket1.fragData.fragId==1
    assert wirepacket1.fragData.totalSize==1000
    assert wirepacket1.isFragment()
    
    serializedData = wirepacket1.__serialize__()
    
    wirepacket2 = WirePacket()
    wirepacket2.source="4.3.2.1"
    wirepacket2.sourcePort=1000
    wirepacket2.destination="1.2.3.4"
    wirepacket2.destinationPort=80
    wirepacket2.data = b"response"
    
    assert not wirepacket2.isFragment()
    
    serializedData += wirepacket2.__serialize__()
    
    packets = []
    
    deserializer = wirepacket1.Deserializer()
    while serializedData:
        chunk, serializedData = serializedData[:10], serializedData[10:]
        deserializer.update(chunk)
        for packet in deserializer.nextPackets():
            packets.append(packet)
    
    assert packets[0] == wirepacket1
    assert packets[1] == wirepacket2
    
if __name__ == "__main__":
    basicUnitTest()
    print("Basic unit test completed successfully.")
    
    