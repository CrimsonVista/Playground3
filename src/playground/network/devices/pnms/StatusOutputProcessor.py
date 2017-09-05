from .SwitchDevice import SwitchDevice
from .VnicDevice import VnicDevice


class PNMSDeviceStatusOutputProcessor:
    def __init__(self, deviceType):
        self._deviceType = deviceType
        self._outputTemplate = "{deviceType} {deviceName}:\n"
        self._outputTemplate += "\tStatus: {status} {pid}\n"
        self._outputTemplate += "\tAuto-Enable: {auto_enable}\n"
        
    def process(self, device):
        pid = device.getPid()
        if pid:
            pidStr = "(PID: {})".format(pid)
        else:
            pidStr = ""
        return self._outputTemplate.format(deviceType = self._deviceType,
                                            deviceName = device.name(),
                                            status = device.enabled(),
                                            pid = pidStr,
                                            auto_enable = device.isAutoEnabled())
                                            
class SwitchDeviceStatusOutputProcessor(PNMSDeviceStatusOutputProcessor):
    def __init__(self):
        super().__init__(SwitchDevice.REGISTER_DEVICE_TYPE_NAME)
        self._switchTemplate = "\tPNMS Managed: {managed}\n"
        self._switchTemplate += "\tTCP Location: {tcp_location}\n"
        
    def process(self, switch):
        deviceTemplate = super().process(switch)
        tcpLocation = switch.tcpLocation()
        tcpLocation = "{}:{}".format(tcpLocation[0], tcpLocation[1])
        switchString = self._switchTemplate.format(managed=switch.isManaged(),
                                                    tcp_location=tcpLocation)
        return deviceTemplate + switchString
        
class VnicDeviceStatusOutputProcessor(PNMSDeviceStatusOutputProcessor):
    def __init__(self):
        super().__init__(VnicDevice.REGISTER_DEVICE_TYPE_NAME)
        self._vnicTemplate = "\tPlayground Address: {playground_address}\n"
        self._vnicTemplate += "\tConnected To: {access_point}\n"
        self._vnicTemplate += "\tRoutes:\n"
        
    def process(self, vnic):
        deviceTemplate = super().process(vnic)
        connectedToDeviceName = vnic.connectedTo()
        connectedToDevice = None
        if connectedToDeviceName:
            connectedToDevice = vnic.networkManager().getDevice(connectedToDeviceName)
        if connectedToDevice:
            tcpLocation = connectedToDevice.tcpLocation()
            connectedToDeviceName += " ({}:{})".format(tcpLocation[0], tcpLocation[1])
        
        outputString = deviceTemplate
        outputString += self._vnicTemplate.format(playground_address=vnic.address(),
                                                   access_point=connectedToDeviceName)
        for route in vnic.routes():
            outputString += "\t\t{}\n".format(route)
        return outputString

class DeviceStatusOutputProcessor: 
    @classmethod
    def DeviceProcessorFactory(cls, networkManager, deviceName):
        deviceView,_ = networkManager.getSectionAPI(networkManager.DEVICES_SECTION_NAME)
        deviceType = deviceView.lookupDeviceType(deviceName)
        if deviceType == SwitchDevice.REGISTER_DEVICE_TYPE_NAME:
            deviceProcessor = SwitchDeviceStatusOutputProcessor()
        elif deviceType == VnicDevice.REGISTER_DEVICE_TYPE_NAME:
            deviceProcessor = VnicDeviceStatusOutputProcessor()
        else:
            deviceProcessor = PNMSDeviceStatusOutputProcessor(deviceType)
        return deviceProcessor
        
    def process(self, networkManager):
        output = "\nPlayground Networking Configuration:\n"
        output += "-------------------------------------\n\n"
        
        deviceView,_ = networkManager.getSectionAPI(networkManager.DEVICES_SECTION_NAME)
        rawDeviceSection = deviceView.rawView()

        for deviceName in rawDeviceSection:
            deviceType = deviceView.lookupDeviceType(deviceName)
            deviceManager = networkManager.getDevice(deviceName)
            deviceProcessor = self.DeviceProcessorFactory(networkManager, deviceName)
            output += deviceProcessor.process(deviceManager)
            output += "\n"
           
        return output
        
class RoutesStatusOutputProcessor:
    def process(self, networkManager):
        output = "\nPlayground Routing:\n"
        output += "-------------------------------------\n\n"
        
        routesView,_ = networkManager.getSectionAPI(networkManager.ROUTES_SECTION_NAME)
        for route in routesView.rawView():
            deviceName = routesView.lookupDeviceForRoute(route)
            output += "\t{} -> {}\n".format(route, deviceName)
        output += "\n"
        return output