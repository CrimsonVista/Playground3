
from .PacketFieldType import PacketFieldType
from .ComplexFieldType import ComplexFieldType
from .Uint import Uint
from .PacketFields import PacketFields
from .NamedPacketType import NamedPacketType
from .ListFieldType import ListFieldType
from .StringFieldType import StringFieldType
from .BufferFieldType import BufferFieldType

from .attributes import Bits

STRING = StringFieldType
BUFFER = BufferFieldType

UINT = Uint
UINT8 = Uint({Bits:8})
UINT16 = Uint({Bits:16})
UINT32 = Uint({Bits:32})
UINT64 = Uint({Bits:64})