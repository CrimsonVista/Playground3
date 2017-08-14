
from playground.common import CustomConstant as Constant
from playground.common import Version as PacketDefinitionVersion
from playground.packet.encoders import DefaultPacketEncoder
from PacketDefinitionRegistration import g_DefaultPacketDefinitions



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
            raise DuplicatePacketDefinition(identifier, version)
            
        definitionCls = super(MessageDefinitionMetaClass, cls).__new__(cls, name, parents, dict
            
        packetStore.registerDefinition(identifier, version, definitionCls)
    
class PacketDefinition(__metaclass__ = PacketDefinitionLoader):
    """
    The base class of all Packet Definition classes. PacketDefinition
    classes enable rapid development and maintenance of typable 
    serializable packets.
    
    An instance of a given PacketDefinition has built-in methods for
    serializing and de-serializing data. These routines are based on
    the encoder of the PacketDefinitionLoader, which is the PacketDefinition's
    MetaClass. The Encoder uses fields defined in the BODY attribute
    to encode and decode data. BODY is a list of fields, where every 
    field has the following definition:
      (NAME, TYPE, *ATTRIBUTES)
    
    Every PacketDefinition has a DEFINITION_IDENTIFIER and a DEFINITION_VERSION.
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
    def Deserialize(cls, buf):
        emptyPacketObject = cls()
        obj, bytesUsed = emptyPacketObject.__encoder__.decode(cls, buf)# StructuredData.Deserialize(buf)
        return obj, bytesUsed

    @classmethod
    def DeserializeStream(cls, bufs):
        emptyPacketObject = cls()
        for obj in emptyPacketObject.__encoder__.decodeStream(bufs):
            yield obj
            
    UNSET = Constant(strValue="Unset Packet Field", boolValue=False)

    DEFINITION_IDENTIFIER = "base.definition"
    DEFINITION_VERSION = "0.0"
    FIELDS = []
    # FIELDS = [("blah",LIST(UINT), {FixedSize=4,Optional=True}]

    def __init__(self, **fieldInitialization):
        self.__encoder__ = self._CreateEncoder()
        self.__encoder__.init()
        self.__fieldNames = set([])
        for fieldSpec in self.FIELDS:
            fieldName = fieldSpec[0]
            self.__fieldNames.add(fieldName)
            if fieldInitialization.has_key(fieldName):
                self.__encoder__[fieldName].setData(fieldInitialization[fieldName])

    def __getattribute__(self, field):
        if not field.startswith("_") and field in self.__fieldNames:
            return self.__encoder__[field].data()
        return object.__getattribute__(self, field)

    def __setattr__(self, field, value):
        if not field.startswith("_") and field in self.__fieldNames:
            self.__encoder__[field].setData(value)
        else: object.__setattr__(self, field, value)

    def __serialize__(self):
        return self.__encoder__.encode()

    def __repr__(self):
        return "%s v%s (%x)" % (self.DEFINITION_IDENTIFIER, self.DEFINITION_VERSION, id(self))
