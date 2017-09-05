
from .PacketFieldType import PacketFieldType

class ComplexFieldType(PacketFieldType):
    @classmethod
    def _CreateInstance(cls):
        """
        Default is ComplexFieldType(PacketFieldType)
        """
        return cls(PacketFieldType)
        
    def __init__(self, dataType, attributes=None):
        super().__init__(attributes)
        self._dataType = dataType
        
    def dataType(self):
        return self._dataType
        
    def initializeData(self):
        if not self._data:
            self._data = self._dataType()
        # TODO: Warnings, Errors, etc?
        
    def _setTypedData(self, data):
        if not isinstance(data, self._dataType):
            raise ValueError("Invalid data for ComplexFieldType. Must be of type {}.".format(self._dataType))
        super()._setTypedData(data)
        
    def __call__(self, newAttributes=None):
        cls = self.__class__
        cloneAttributes = {}
        cloneAttributes.update(self._attributes)
        if newAttributes: cloneAttributes.update(newAttributes)
        instance = cls(self._dataType, cloneAttributes)
        return instance
        
    def __repr__(self):
        return "{}({})".format(self.__class__.__name__, self._dataType)

