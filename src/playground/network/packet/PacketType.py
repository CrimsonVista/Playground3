import io

from playground.common import Version as PacketDefinitionVersion
from playground.common.io import HighPerformanceStreamIO
from playground.network.packet.encoders import DefaultPacketEncoder
from playground.network.packet.fieldtypes import NamedPacketType, ComplexFieldType, PacketFields, Uint, \
                                                    ListFieldType, StringFieldType, PacketFieldType
from playground.network.packet.fieldtypes.attributes import MaxValue, Bits                                                  
from .PacketDefinitionRegistration import g_DefaultPacketDefinitions

FIELD_NOT_SET = PacketFieldType.UNSET

class PacketDefinitionLoader(type):
    """
    """
    
    
    IDENTIFIER_ATTRIBUTE = "DEFINITION_IDENTIFIER"
    VERSION_ATTRIBUTE    = "DEFINITION_VERSION"
    ENCODER_ATTRIBUTE    = "ENCODER"
    DEFINITIONS_STORE    = "DEFINITIONS_STORE"
    
    REQUIRED_ATTRIBUTES = ( IDENTIFIER_ATTRIBUTE, 
                            VERSION_ATTRIBUTE    )
    
    PermitDuplicateRegistrations = False
        
    
    def __new__(cls, name, parents, dict):
        for attr in cls.REQUIRED_ATTRIBUTES:
            if attr not in dict:
                raise AttributeError("Missing required attribute %s" % attr)
        if cls.ENCODER_ATTRIBUTE not in dict:
            dict[cls.ENCODER_ATTRIBUTE] = DefaultPacketEncoder
        if cls.DEFINITIONS_STORE not in dict:
            dict[cls.DEFINITIONS_STORE] = g_DefaultPacketDefinitions
        
        identifier = dict[cls.IDENTIFIER_ATTRIBUTE]        
        version    = PacketDefinitionVersion.FromString( dict[cls.VERSION_ATTRIBUTE] )    
        
        packetStore= dict[cls.DEFINITIONS_STORE]
        
        if not cls.PermitDuplicateRegistrations and packetStore.hasDefinition(identifier, version):
            raise ValueError("Duplicate registration {} v {}".format(identifier, version))
            
        definitionCls = super().__new__(cls, name, parents, dict)
        
        packetStore.registerDefinition(identifier, version, definitionCls)
        return definitionCls

######
# Python Import "feature." If you have a module that is part of a hierarchy,
# e.g., playground.network.packet.PacketType (i.e., this file), and then it
# also becomes the "__main__" module (e.g., "python -m playground.network.packet.PacketType",
# the module will be imported twice. So, to deal with this "feature", disable the
# duplicate packet checking.
if __name__=="__main__":
    PacketDefinitionLoader.PermitDuplicateRegistrations = True
##############################################################
    
class PacketType(NamedPacketType, metaclass=PacketDefinitionLoader):
    """
    The base class of all Packet Type classes. PacketType
    classes enable rapid development and maintenance of typable 
    serializable packets.
    
    An instance of a given PacketType has built-in methods for
    serializing and de-serializing data. These routines are based on
    the encoder of the PacketDefinitionLoader, which is the PacketType's
    MetaClass. The Encoder uses fields defined in the BODY attribute
    to encode and decode data. BODY is a list of fields, where every 
    field has the following definition:
      (NAME, TYPE(<with optional attributes>))
    
    Every PacketType has a DEFINITION_IDENTIFIER and a DEFINITION_VERSION.
    These fields can be used by the encoder, and are used by the default
    encoder, to transmit packets that automatically can be reconstructed
    on the other end of the connection. That is, the identifier and version
    are transmitted as part of the serialized packet and used by the receiver
    to load the correct packet type.

    Every Message Definition needs to define its own PLAYGROUND_IDENTIFIER
    and MESSAGE_VERSION field. Any fields must be defined in a class variable
    called BODY. 
    
    TODO: Examples.
    """

    @classmethod
    def Deserialize(cls, buffer):
        encoder = cls.ENCODER()
        
        # The encoders work on field types. The packet itself, isn't one.
        # We create a ComplexFieldType(NamedPacketType) and pass it to decoder.
        # The type's data will be set to the decoded stream.
        fieldWrapper = ComplexFieldType(cls)
        encoder.decode(io.BytesIO(buffer), fieldWrapper)
        return fieldWrapper.data()

    @classmethod
    def DeserializeStream(cls, stream):
        encoder = cls.ENCODER()
        
        # The encoders work on field types. The packet itself, isn't one.
        # We create a ComplexFieldType(PacketType) and pass it to decoder.
        # The type's data will be set to the decoded stream.
        fieldWrapper = ComplexFieldType(cls)
        yield from encoder.decodeIterator(stream, fieldWrapper)
        packet = fieldWrapper.data()
        if not isinstance(packet, cls):
            raise Exception("Deserialized packet of class {} but expected class {}.".format(packet.__class__, cls))
        return packet
        
    @classmethod
    def Deserializer(cls, stream=None, errHandler=None):
        class ConcreteDeserializer:
            def __init__(self, underlyingStream, errHandler):
                """
                Underlying stream must support "update"
                """
                self._stream = (underlyingStream == None and HighPerformanceStreamIO() or underlyingStream)
                self._iterator = cls.DeserializeStream(self._stream)
                self._errHandler = errHandler
                
            def update(self, buffer):
                self._stream.update(buffer)
            def nextPackets(self):
                """
                The packet DeserializeStream iterator yields not ready until
                it finally has the packet, which it returns (via StopIteration)
                """
                exhausted = False
                while not exhausted:
                    try:
                        notReady = next(self._iterator)
                        # No more messages until more data. We're done.
                        exhausted = True
                    except StopIteration as result:
                        # we got a message!
                        yield result.value
                        # get new iterator
                        self._iterator = cls.DeserializeStream(self._stream)
                    except Exception as error:
                        if self._errHandler: self._errhandler.handleException(error)
                        # if no error handler, simply drop errors.
        return ConcreteDeserializer(stream, errHandler)

    DEFINITION_IDENTIFIER = "__abstract__.PacketType"
    DEFINITION_VERSION = "0.0"
    FIELDS = []

    def __init__(self, **fieldInitialization):
        super().__init__(**fieldInitialization)

    def __serialize__(self):
        encoder = self.ENCODER()
        writeStream = io.BytesIO()
        fieldWrapper = ComplexFieldType(PacketType)
        fieldWrapper.setData(self)
        encoder.encode(writeStream, fieldWrapper)
        return writeStream.getvalue()

    def __repr__(self):
        return "%s v%s (%x)" % (self.DEFINITION_IDENTIFIER, self.DEFINITION_VERSION, id(self))
        
def basicUnitTest():
    p = PacketType()
    class TestPacket1(PacketType):
        DEFINITION_IDENTIFIER = "packettype.basicunittest.TestPacket1"
        DEFINITION_VERSION    = "1.0"
        
        class SubFields(PacketFields):
            FIELDS = [("subfield1",Uint({Bits:16})), ("subfield2",Uint({Bits:16}))]
        SubFieldsType = ComplexFieldType(SubFields)
        
        FIELDS = [  ("header", ComplexFieldType(SubFields)), 
                    ("field1", Uint({MaxValue:1000})), 
                    ("field2", StringFieldType),
                    ("listField", ListFieldType(Uint)),
                    ("complexListField", ListFieldType(SubFieldsType)),
                    ("trailer", SubFieldsType)]
    
    packet = TestPacket1()
    packet.header = TestPacket1.SubFields()
    packet.trailer = TestPacket1.SubFields()
    
    packet.header.subfield1 = 1
    packet.header.subfield2 = 100
    packet.field1 = 50
    packet.field2 = "test packet field 2"
    packet.listField = [1,2,3]
    packet.complexListField = [TestPacket1.SubFields()]
    packet.complexListField[0].subfield1 = 0
    packet.complexListField[0].subfield2 = 1
    packet.trailer.subfield1 = 5
    packet.trailer.subfield2 = 500
    
    serializedData = packet.__serialize__()
    restoredPacket = PacketType.Deserialize(serializedData)
    
    assert packet.header.subfield1 == restoredPacket.header.subfield1 
    assert packet.field2 == restoredPacket.field2
    assert packet == restoredPacket

if __name__=="__main__":
    basicUnitTest()