from .PacketFields import PacketFields

class NamedPacketType(PacketFields):
    """
    This class largely exists for breaking circular importation, etc.
    TODO: Explain more
    """
    DEFINITION_IDENTIFIER = "base.definition"
    DEFINITION_VERSION = "0.0"