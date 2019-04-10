import playground, asyncio

def create_compare_data(data1, data2):
    max_len = max(len(data1), len(data2))
    if max_len < 60:
        s = b"\t" + data1 + b"\n"
        s+= b"\t" + data2 + b"\n"
        s+= b"\t"
        for i in range(max_len):
            if i > len(data1) or i > len(data2) or data1[i] != data2[i]:
                s+=b"^"
            else:
                s+=b" "
        s += b"\n"
    else:
        error_bytes = []
        for i in range(max_len):
            if i >= len(data1) or i >= len(data2):
                break
            if data1[i] != data2[i]:
                error_bytes.append(i)

        if error_bytes:
            line1 = b"\t"
            line2 = b"\t"
            line3 = b"\t"
            last_offset = 0
            while error_bytes:
                next_offset = error_bytes.pop(0)
                offset_string = "({} bytes)...".format(next_offset-last_offset).encode()
                line3 += offset_string + b"^"
                line1 += b"."*len(offset_string)+data1[next_offset:next_offset+1]
                line2 += b"."*len(offset_string)+data2[next_offset:next_offset+1]
                last_offset = next_offset
            s = b"\n".join([line1, line2, line3])
        else:
            s = "\t{}...({} bytes)...{}\n".format(data1[:5], len(data1), data1[-5:]).encode()
            s+= "\t{}...({} bytes)...{}\n".format(data2[:5], len(data2), data2[-5:]).encode()
            s+= b"\n"
    return s
        

class RawEchoClient(asyncio.Protocol):
    def __init__(self, data_to_send):
        self.sent_data = data_to_send
        self.received_data = None
        
    def connection_made(self, transport):
        self.transport = transport
        self.transport.write(self.sent_data)
        asyncio.get_event_loop().call_later(30, self._abort)
        
    def data_received(self, data):
        if self.received_data == None:
            self.received_data = data
        else:
            self.received_data += data
        if len(self.received_data)>=len(self.sent_data):
            print("close")
            self.transport.close()
        
    def _abort(self):
        print("aborting")
        #if self.received_data == None:
        #    self.transport.close()
            
    def connection_lost(self, exc):
        print("connection lost",exc)
        asyncio.get_event_loop().call_later(1,asyncio.get_event_loop().stop)
        
class RawEchoServer(asyncio.Protocol):
    def connection_made(self, transport):
        self.transport = transport
        
    def data_received(self, data):
        self.transport.write(data)
        
if __name__=="__main__":
    import sys, os, argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("mode")
    parser.add_argument("--port", default=201)
    parser.add_argument("--msg", default=None)
    parser.add_argument("--count",default=None)
    parser.add_argument("--stack",default="default")
    parser.add_argument("--debug",action="store_true", default=False)
    
    args = parser.parse_args(sys.argv[1:])
    
    if args.debug:
        from playground.common.logging import EnablePresetLogging, PRESET_DEBUG
        EnablePresetLogging(PRESET_DEBUG)
    
    if args.mode == "server":
        if args.msg != None or args.count != None:
            print("Can't specify a message or a count for a server")
            sys.exit(-1)
        coro = playground.create_server(RawEchoServer, port=201, family=args.stack)
        asyncio.get_event_loop().run_until_complete(coro)
        asyncio.get_event_loop().run_forever()
    else:
        if args.msg != None and args.count != None:
            print("Can specify an explicity message or a byte count, but not both")
            sys.exit(-1)
        if args.msg != None:
            data_to_send = args.msg.encode()
        elif args.count != None:
            data_to_send = os.urandom(int(int(args.count)/2)).hex().encode()
        else:
            data_to_send = b"This is a test message from an echo client!"
        print("raw echo test connecting to {}://{}:{}".format(args.stack, args.mode, args.port))
        coro = playground.create_connection(lambda: RawEchoClient(data_to_send), host=args.mode, port=args.port, family=args.stack)
        transport, protocol = asyncio.get_event_loop().run_until_complete(coro)
        print("Connected. Transmitted {} bytes. Wait for response".format(len(protocol.sent_data)))
        asyncio.get_event_loop().run_forever()
        if protocol.received_data == None:
            print("Echo client transmission failed. Data was never received from the server.")
        elif protocol.sent_data == protocol.received_data:
            print("Echo client round-trip transmission completed with no errors:")
            print(create_compare_data(protocol.sent_data, protocol.received_data).decode())
        else:
            print("Echo client round-trip transmission completed but there were errors.")
            
            correct_bytes = 0
            for i in range(len(protocol.received_data)):
                if i < len(protocol.sent_data) and protocol.sent_data[i] == protocol.received_data[i]:
                    correct_bytes += 1
            
            print("\tData Transmitted: {} bytes".format(len(protocol.sent_data)))
            print("\tcorrect Bytes Received: {} bytes".format(correct_bytes))
            print("\n")
            print(create_compare_data(protocol.sent_data, protocol.received_data).decode(errors="replace"))
        