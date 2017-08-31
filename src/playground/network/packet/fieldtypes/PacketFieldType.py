from playground.common import CustomConstant as Constant
from playground.network.packet.fieldtypes.attributes import Validator

class PacketFieldType:
    UNSET = Constant(strValue="Unset Packet Field", boolValue=False)
    
    @classmethod
    def GetAttribute(cls, field, attr, default=None):
        """
        This class method is designed to get the attribute from a field,
        whether the field is an instance of the class itself. If the class
        itself, there are not attributes, and it returns none (or the default)
        """
        if isinstance(field, PacketFieldType):
            return field._getAttribute(attr, default)
        else: return default
    
    @classmethod
    def CreateInstance(cls, field):
        """
        This class method is designed to create an instance of the field,
        whether the field is an instance or the class itself. If the class
        itself, call the class method _CreateInstance, which can be overridden
        by subclasses. If the instance, return the instance's clone method()
        """
        if isinstance(field, PacketFieldType):
            return field.clone()
        else: return field._CreateInstance()
        
    @classmethod
    def _CreateInstance(cls):
        return cls()

    def __init__(self, attributes=None):
        self._attributes = {}
        self._validators = set([])
        if attributes != None: 
            self._attributes.update(attributes)
        
            for attr in attributes:
                # Every attribute can have "base attributes" that are analogous to "base classes"
                # When an attribute is registered, it also registers for base attributes that are
                # unset. In this way, when client code can query for a base attribute that was
                # set by a more specific attribute.
                baseAttributes = attr.baseAttributes()
                while baseAttributes:
                    baseAttr = baseAttributes.pop(0)
                    if baseAttr not in self._attributes:
                        self._attributes[baseAttr] = attr.translateAttributeValue(baseAttr, self._attributes[attr])
                        baseAttributes += baseAttr.baseAttributes()
                if isinstance(attr, Validator):
                    self._validators.add(attr)
        self._data = self.UNSET
        
    def setData(self, data):
        if data == self.UNSET:
            self._data = data
            return
        self._setTypedData(data)
        for validator in self._validators:
            attrValue = self._attributes[validator]
            if not validator.validate(self._data, attrValue):
                raise ValueError("Cannot set field to {} for type with attribute {}={}".format(data, validator, attrValue))
        
    def _setTypedData(self, data):
        """
        This function is to be generally overridden by subclasses
        that need to check the data for typing.
        """
        self._data = data
        
    def data(self):
        return self._data
        
    def _getAttribute(self, attr, default=None):
        return self._attributes.get(attr, default)
        
    def __call__(self, newAttributes=None):
        cloneAttributes = {}
        cloneAttributes.update(self._attributes)
        if newAttributes:
            cloneAttributes.update(newAttributes)
        cls = self.__class__
        instance = cls(cloneAttributes)
        return instance
        
    #def __repr__(self):
    #    return 