
class FieldTypeAttribute:
    def __init__(self, baseAttributes=None):
        self._bases = baseAttributes != None and baseAttributes or []
        
    def baseAttributes(self):
        return self._bases[:]
        
    def translateAttributeValue(self, baseAttribute, attrValue):
        """
        Attributes are associated with an attribute value in a Field type.
        Base Attributes may need a converted value. The default conversion
        is the null conversion (i.e., f(x)=x). Subclasses can implement
        their own conversions
        """
        return attrValue