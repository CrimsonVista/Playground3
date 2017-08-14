
class CustomConstant(object):
    """
    Simple class for custom constants such as NULL, NOT_FOUND, etc.
    Each object is obviously unique, so it is simple to do an equality
    check. Each object can be configured with string, int, float,
    and boolean values, as well as attributes.
    """
    def __init__(self, **config):
        self.__strValue = config.get("strValue", None)
        self.__intValue = config.get("intValue", None)
        self.__floatValue = config.get("floatValue", None)
        self.__boolValue = config.get("boolValue", None)
        for configKey in config:
            setattr(self, configKey, config[configKey])
            
    def __int__(self):
        if self.__intValue == None:
            if self.__floatValue == None:
                raise TypeError
            return int(self.__floatValue)
        return self.__intValue
        
    def __float__(self):
        if self.__floatValue == None:
            if self.__intValue == None:
                raise TypeError
            return float(self.__intValue)
        return self.__floatValue
        
    def __bool__(self):
        if self.__boolValue == None:
            if self.__intValue == None:
                if self.__floatValue == None:
                    raise TypeError
                return bool(self.__floatValue)
            return bool(self.__intValue)
        return self.__boolValue
        
    def __str__(self):
        if self.__strValue == None:
            sParts = []
            if self.__intValue: sParts.append(str(self.__intValue))
            if self.__floatValue: sParts.append(str(self.__floatValue))
            if self.__boolValue: sParts.append(str(self.__boolValue))
            return "/".join(sParts)
        return self.__strValue
        
    def __repr__(self):
        return "Constant(%s)" % str(self)