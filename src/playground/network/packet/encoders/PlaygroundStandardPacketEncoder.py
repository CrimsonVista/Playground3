import struct, traceback
from io import SEEK_END

from playground.common.datastructures import Bijection
from playground.common.io import HighPerformanceStreamIO
from playground.common import Version as PacketDefinitionVersion
from playground.common import ReturnOrientedGenerator

from playground.network.packet.fieldtypes.attributes import StandardDescriptors 
from playground.network.packet.fieldtypes import ComplexFieldType, PacketFieldType, Uint, \
                                                    PacketFields, NamedPacketType

from .PacketEncoderBase import PacketEncoderBase
from .PacketEncodingError import PacketEncodingError

DECODE_WAITING_FOR_STREAM = PacketEncoderBase.DECODE_WAITING_FOR_STREAM
Size, Optional = StandardDescriptors.Size, StandardDescriptors.Optional
ExplicitTag    = StandardDescriptors.ExplicitTag

UNICODE_ENCODING = "utf-8" # used for converting strings to bytes and back.

class EncoderStreamAdapter(object):
    @classmethod
    def Adapt(cls, stream):
        if not isinstance(stream, cls):
            return cls(stream)
        return stream
        
    def __init__(self, stream):
        self._stream = stream
        
    def available(self):
        curPos = self._stream.tell()
        self._stream.seek(0, SEEK_END)
        endPos = self._stream.tell()
        self._stream.seek(curPos)
        return endPos-curPos
        
    def read(self, count):
        return self._stream.read(count)
        
    def write(self, data):
        return self._stream.write(data)
        
    def pack(self, packCode, *args):
        return self._stream.write(struct.pack(packCode, *args))
        
    def unpack(self, packCode):
        g = ReturnOrientedGenerator(self.unpackIterator(packCode))
        for waitingForStream in g: pass
        return g.result()
        
    def unpackIterator(self, packCode):
        unpackSize = struct.calcsize(packCode)
        while self.available() < unpackSize:
            yield DECODE_WAITING_FOR_STREAM
        unpackChunk = self.read(unpackSize)
        try:
            unpackedData = struct.unpack(packCode, unpackChunk)
        except Exception as unpackError:
            raise PacketEncodingError("Unpack of {} failed.".format(packCode)) from unpackError
        if len(unpackedData) == 1:
            return unpackedData[0]
        else:
            return unpackedData
                

class PlaygroundStandardPacketEncoder(PacketEncoderBase):
    __TypeEncoders = {}
    
    @classmethod
    def _GetTypeKey(self, encodingType):
        """
        Three scenarios:
        
        1. A Complex Type. We have to get the specific data type and generalizations
        2. An instance of PacketFieldType. Get the class and generalizations
        3. An actual class of PacketFieldType. Just return the class. No generalizations.
        """
        if isinstance(encodingType, ComplexFieldType):
            specificEncodingType = encodingType.dataType()
            specificComplexType  = encodingType.__class__
            
            if not isinstance(specificEncodingType, type):
                raise Exception("Playground Standard Packet Encoder only registers ComplexTypes with dataType classes.")
            
            for complexType in (specificComplexType,) + specificComplexType.__bases__:
                for dataType in (specificEncodingType,) + specificEncodingType.__bases__:
                    yield (complexType, dataType)
        elif isinstance(encodingType, PacketFieldType):
            yield encodingType.__class__
            for base in encodingType.__class__.__bases__:
                yield base
        elif isinstance(encodingType, type) and issubclass(encodingType, PacketFieldType):
            yield encodingType
        else:
            raise Exception("Playground Standard Packet Encoder only registers FieldType classes or instances.")
    
    @classmethod
    def RegisterTypeEncoder(cls, encodingType, encoder):
        # GetTypeKey is a generator. But the first key is the most specific. Use that to store.
        keyGenerator = cls._GetTypeKey(encodingType)
        cls.__TypeEncoders[next(keyGenerator)] = encoder
            
    @classmethod
    def GetTypeEncoder(cls, encodingType):
        for encodingKey in cls._GetTypeKey(encodingType):
            encoder = cls.__TypeEncoders.get(encodingKey, None)
            if encoder != None: return encoder
        return None
        
    def encode(self, stream, fieldType):
        typeEncoder = self.GetTypeEncoder(fieldType)
        if not typeEncoder:
            raise PacketEncodingError("Cannot encode fields of type {}".format(fieldType))
        typeEncoder().encode(EncoderStreamAdapter.Adapt(stream), fieldType, self)
        
    def decode(self, stream, fieldType):
        g = ReturnOrientedGenerator(self.decodeIterator(stream, fieldType))
        for waitingForStream in g: pass
        return g.result()
        
    def decodeIterator(self, stream, fieldType):
        typeDecoder = self.GetTypeEncoder(fieldType)
        if not typeDecoder:
            raise PacketEncodingError("Cannot decode fields of type {}".format(fieldType))
        yield from typeDecoder().decodeIterator(EncoderStreamAdapter.Adapt(stream), fieldType, self)

        
class UintEncoder:
    SIZE_TO_PACKCODE =  {
                        1:"!B",
                        2:"!H",
                        4:"!I",
                        8:"!Q"
                        }
                        
    def encode(self, stream, uint, topEncoder):
        size = uint.getAttribute(Size, Uint.DEFAULT_SIZE)
        if not size in self.SIZE_TO_PACKCODE:
            raise PacketEncodingError("Playground Standard Encoder does not support uint of size {}.".format(size))
        packCode = self.SIZE_TO_PACKCODE[size]
        stream.pack(packCode, uint.data())
        
    def decodeIterator(self, stream, uint, topDecoder):
        size = uint.getAttribute(Size, Uint.DEFAULT_SIZE)
        if not size in self.SIZE_TO_PACKCODE:
            raise PacketEncodingError("Playground Standard Encoder does not support uint of size {}.".format(size))
        packCode = self.SIZE_TO_PACKCODE[size]
        uintData = yield from stream.unpackIterator(packCode)
        uint.setData(uintData)
PlaygroundStandardPacketEncoder.RegisterTypeEncoder(Uint, UintEncoder)

class PacketFieldsEncoder:
    FIELD_TAG_PACK_CODE = "!H"
    FIELD_COUNT_PACK_CODE = "!H"
    
    def _processFields(self, fields):
        autoTag      = 0
        fieldToTag   = Bijection()

        for fieldName, fieldType in fields:
            if fieldName in fieldToTag:
                raise Exception("Duplicate Field")
            tag = fieldType.getAttribute(ExplicitTag, None)
            if tag != None and tag in fieldToTag.inverse():
                raise Exception("Duplicate Explicit Tag")
            if tag == None:
                while autoTag in fieldToTag.inverse():
                    autoTag += 1
                tag = autoTag
            fieldToTag[fieldName] = tag
        return fieldToTag
    
    def encode(self, stream, complexType, topEncoder):
        packetFields = complexType.data()
        fieldToTag = self._processFields(packetFields.FIELDS)
        
        # Get all the fields that have data.
        encodeFields = []
        for fieldName, fieldType in packetFields.FIELDS:
            rawField = packetFields.__getrawfield__(fieldName)
            if rawField.data() == PacketFieldType.UNSET:
                if rawField.getAttribute(Optional, False) == True:
                    continue
                else:
                    raise PacketEncodingError("Field '{}' is unset and not marked as optional.".format(fieldName))   
            encodeFields.append((fieldName, rawField))
            
        # Write the number of encoding fields into the stream
        stream.pack(self.FIELD_COUNT_PACK_CODE, len(encodeFields))
        
        # Write the actual fields into the stream
        for fieldName, rawField in encodeFields:
            try:
                tag = fieldToTag[fieldName]
                stream.pack(self.FIELD_TAG_PACK_CODE, tag)
                topEncoder.encode(stream, rawField)
            except Exception as encodingException:
                raise PacketEncodingError("Error encoding field {}.".format(fieldName)) from encodingException
    
    def decodeIterator(self, stream, complexType, topDecoder):
        packetFields = complexType.data()
        fieldToTag = self._processFields(packetFields.FIELDS)
        fieldCount = yield from stream.unpackIterator(self.FIELD_COUNT_PACK_CODE)
        
        for i in range(fieldCount):
            fieldID = yield from stream.unpackIterator(self.FIELD_TAG_PACK_CODE)
            fieldName = fieldToTag.inverse()[fieldID]
            rawField  = packetFields.__getrawfield__(fieldName)
            if isinstance(rawField, ComplexFieldType):
                # complex types must be initialized prior to decoding
                rawField.initializeData()
            try:
                yield from topDecoder.decodeIterator(stream, rawField)
            except Exception as encodingException:
                raise PacketEncodingError("Error decoding field {}.".format(fieldName)) from encodingException
PlaygroundStandardPacketEncoder.RegisterTypeEncoder(ComplexFieldType(PacketFields), PacketFieldsEncoder)
        
class PacketEncoder:
    PacketIdentifierTemplate = "!B{}sB{}s" # Length followed by length-string
                                           # For packet type identifier and version
                                           
    def encode(self, stream, complexType, topEncoder):
        packet = complexType.data()
        packetDefEncoded = packet.DEFINITION_IDENTIFIER.encode(UNICODE_ENCODING)
        packetVerEncoded = packet.DEFINITION_VERSION.encode(   UNICODE_ENCODING)
        packCode = self.PacketIdentifierTemplate.format(len(packetDefEncoded), len(packetVerEncoded))
        stream.pack(packCode, len(packetDefEncoded), packetDefEncoded, 
                              len(packetVerEncoded), packetVerEncoded) 
                              
        PacketFieldsEncoder().encode(stream, complexType, topEncoder)
        
    def decodeIterator(self, stream, complexType, topEncoder):
        nameLen = yield from stream.unpackIterator("!B")
        name    = yield from stream.unpackIterator("!{}s".format(nameLen))
        name    = name.decode(UNICODE_ENCODING)
        
        versionLen = yield from stream.unpackIterator("!B")
        version    = yield from stream.unpackIterator("!{}s".format(versionLen))
        version    = version.decode(UNICODE_ENCODING)
        
        version = PacketDefinitionVersion.FromString(version)

        basePacketType    = complexType.dataType()
        packetDefinitions = basePacketType.DEFINITIONS_STORE
        packetType = packetDefinitions.getDefinition(name, version)
        packet = packetType()
        complexType.setData(packet)
        yield from PacketFieldsEncoder().decodeIterator(stream, complexType, topEncoder)
PlaygroundStandardPacketEncoder.RegisterTypeEncoder(ComplexFieldType(NamedPacketType), PacketEncoder)
        
def basicUnitTest():
    import io
    
    uint1, uint2 = Uint(), Uint()
    stream = io.BytesIO()
    encoder = PlaygroundStandardPacketEncoder()
    
    uint1.setData(10)
    encoder.encode(stream, uint1)
    stream.seek(0)
    encoder.decode(stream, uint2)
    assert uint2.data() == uint1.data()
    
    class SomeFields(PacketFields):
        FIELDS = [  ("field1", Uint(Size=2)),
                    ("field2", Uint(Size=4))
                    ]
    
    fields1Field = ComplexFieldType(SomeFields)
    fields2Field = ComplexFieldType(SomeFields)
    
    fields1 = SomeFields()
    fields1.field1 = 50
    fields1.field2 = 500
    
    fields1Field.setData(fields1)
    fields2Field.setData(SomeFields())
    
    stream = io.BytesIO()
    encoder.encode(stream, fields1Field)
    stream.seek(0)
    encoder.decode(stream, fields2Field)
    
    fields2 = fields2Field.data()
    
    assert fields1.field1 == fields2.field1
    assert fields1.field2 == fields2.field2
    
    # Packet not tested in this file. See basicUnitTest in PacketType.py
    
if __name__=="__main__":
    basicUnitTest()