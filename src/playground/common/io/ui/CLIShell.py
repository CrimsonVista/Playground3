'''
Created on Feb 16, 2016

@author: sethjn
'''

import os, threading, sys, textwrap, traceback, shlex, time
import asyncio
# TODO: it would be nice to get rid of this some day
from .AsyncIODeferred import Deferred
from playground.network.common.Protocol import StackingProtocol

class AdvancedStdio(object):
    """
    We need AdvancedStdio to do things like tab completion, etc.
    Otherwise, we could just use asyncio's addreader

    AdvancedStdio will run in a loop. When data is available, it
    will it send it to the main thread asyncio loop. It also
    functions as a transport allowing writes
    """

    ReadlineModule = None

    def __init__(self, protocol):
        # don't import readline unless we're instantiating. Help with 
        # platform handling
        if not AdvancedStdio.ReadlineModule:
            try:
                import readline
                AdvancedStdio.ReadlineModule = readline
            except ImportError as e:
                print("Could not find module readline. If you're on Windows, make sure you pip install pyreadline")
                debugPrint(e)
                sys.exit(1)
        self.__protocol = protocol
        self.__getLine = False
        self.__getLineLock = threading.Lock()
        self.__getLineCV = threading.Condition(self.__getLineLock)
        self.__quit = False
        self.__quitLock = threading.Lock()
        self.__inputLock = threading.Lock()
        self.__asyncLoop = asyncio.get_event_loop()
        self.__asyncLoop.run_in_executor(None, self.loop)

    def write(self, buf):
        if self.__inputLock.locked():
            sys.stdout.write("\n")
        sys.stdout.write(buf)
        if not buf[-1] == "\n":
            sys.stdout.flush()
        #else:
        #    if not self.shouldQuit() and self.__inputLock.locked():
        #        sys.stdout.write(self.__protocol.prompt + self.ReadlineModule.get_line_buffer())
        #        sys.stdout.flush()

    def refreshDisplay(self):
        if not self.shouldQuit() and self.__inputLock.locked():
            sys.stdout.write(self.__protocol.prompt + self.ReadlineModule.get_line_buffer())
            sys.stdout.flush()

    def getNextInput(self):
        with self.__getLineLock:
            self.__getLine = True
            self.__getLineCV.notify()

    def close(self):
        self.lose_connection()

    def lose_connection(self):
        #self.__asyncLoop.call_later(0,self.__asyncLoop.stop)
        with self.__quitLock:
            self.__quit = True

    def incompleteShutdown(self):
        with self.__getLineLock:
            if (self.__getLine and not self.__quit) or self.__inputLock.locked():
                print("\nIncomplete shutdown (probably ctrl-c). Press enter (ctrl-d exits immediately)")

    def shouldQuit(self):
        if not self.__asyncLoop.is_running(): return True
        with self.__quitLock:
            return self.__quit

    def __waitUntilReadyForInput(self):
        with self.__getLineCV:
            while not self.__getLine and not self.shouldQuit():
                self.__getLineCV.wait(1.0)

    def __protocolProcessLine(self, line):
        try:
            result, d = self.__protocol.line_received(line)
            if d:
                d.addCallback(lambda res: self.getNextInput())
                d.addErrback(lambda res: self.getNextInput())
            else:
                self.getNextInput()
        except:
            print(traceback.format_exc())

    def loop(self):
        readline = self.ReadlineModule
        # If the loop is no longer running, call self.incompleteShutdown()
        # This currently never gets called in the test
        #def monitorAsyncLoop():
        #    if not self.__asyncLoop.is_running():
        #        self.__asyncLoop.call_soon_threadsafe(self.incompleteShutdown)
        #self.__asyncLoop.call_soon(monitorAsyncLoop)
        readline.set_completer_delims("")
        if isinstance(self.__protocol, CompleterInterface):
            readline.set_completer(self.__protocol.complete)
        readline.parse_and_bind("tab: complete")
        self.__asyncLoop.call_soon_threadsafe(self.__protocol.make_connection, self)
        with self.__getLineLock:
            self.__getLine = True
        while not self.shouldQuit():
            try:
                with self.__inputLock:
                    line = input(self.__protocol.prompt)
            except Exception as e:
                print("[CLIShell:error]", e)
                break
                #self.__asyncLoop.call_soon_threadsafe(self.__asyncLoop.stop)
                #self.__protocol.lose_connection()
                #return
            with self.__getLineLock:
                self.__getLine = False
            self.__asyncLoop.call_soon_threadsafe(self.__protocolProcessLine, line)
            self.__waitUntilReadyForInput()
        self.__asyncLoop.call_soon_threadsafe(self.__protocol.connection_lost)


def FileArgCompleter(s, state):
    pathParts = os.path.split(s)
    pathFirstPart = os.sep.join(pathParts[:-1])
    pathFirstPart = os.path.expanduser(pathFirstPart)
    pathIncomplete = pathParts[-1]
    if os.path.exists(pathFirstPart):
        fIndex = 0
        for fileName in os.listdir(pathFirstPart):
            if fileName.startswith(pathIncomplete):
                if fIndex == state:
                    return os.path.join(pathFirstPart, fileName)
                fIndex += 1
    return None


class CompleterInterface(object):
    def complete(self, s, state):
        return None


def completeKeys(d, s, state, recursive=True):
    keyIndex = 0
    for k in d.keys():
        if recursive and s.startswith(k+" ") and isinstance(d[k], CompleterInterface):
            # in this case, the command is already fully formed.
            # allow the command's completer to take over
            remainderOfS = s[len(k)+1:]
            return k+" "+d[k].complete(remainderOfS, state)
        elif k.startswith(s):
            if keyIndex == state:
                return k
            keyIndex += 1
    return None


def formatText(line, width=120):
    return textwrap.TextWrapper(replace_whitespace=False, drop_whitespace=False, width=width).fill(line)


class TwistedStdioReplacement(object):
    StandardIO = AdvancedStdio
    formatText = formatText

class ArgPod(object):
    def __init__(self):
        self.argHandler = lambda writer, *args: args
        self.cmdHandler = None
        self.help = None
        self.usage = None

class CLICommand(CompleterInterface):
    SINGLETON_MODE = "Singletone Mode: Single callback no matter the args"
    STANDARD_MODE = "Standard Mode: Arguments Only"
    SUBCMD_MODE = "SubCommand Mode: Requires a sub command"

    def __init__(self, cmdTxt, helpTxt, defaultCb = None, defaultArgHandler = None, mode=SINGLETON_MODE):
        self.cmdTxt = cmdTxt
        self.cb = {}
        self.argCompleters = {"f://":FileArgCompleter}
        self.helpTxt = helpTxt
        self.defaultIndent = "  " # two spaces
        self.__mode = mode
        self.__defaultCb = defaultCb
        if defaultArgHandler:
            self.__defaultArgHandler = defaultArgHandler
        else:
            self.__defaultArgHandler = lambda writer, *args: args
        if self.__mode == CLICommand.SINGLETON_MODE and not defaultCb:
            raise Exception("Singleton mode requires a one and only default callback")

    def usageHelp(self):
        usageStrings = []
        if self.__defaultCb:
            if self.__mode ==CLICommand.SINGLETON_MODE:
                usageStrings.append("%s/*"% self.cmdTxt)
            else: usageStrings.append("%s/0"%self.cmdTxt)
        if self.__mode == CLICommand.STANDARD_MODE:
            for argCount, argPod in self.cb.items():
                if argPod.usage:
                    usageStrings.append("%s %s" % (self.cmdTxt, argPod.usage))
                else:
                    usageStrings.append("%s/%d" % (self.cmdTxt, argCount))
        elif self.__mode == CLICommand.SUBCMD_MODE:
            for subCmdObj in self.cb.values():
                for subUsage in subCmdObj.usageHelp():
                    usageStrings.append("%s %s" % (self.cmdTxt, subUsage))
        return usageStrings

    def help(self):
        helpStrings = []
        if self.__defaultCb:
            if self.__mode==CLICommand.SINGLETON_MODE:
                helpStrings.append("%s/*\n  %s" % (self.cmdTxt, self.helpTxt))
            else:
                helpStrings.append("%s/0\n  %s" % (self.cmdTxt, self.helpTxt))
        if self.__mode == CLICommand.STANDARD_MODE:
            for argCount, argPod in self.cb.items():
                if argPod.usage:
                    helpStrings.append("%s %s\n  %s" % (self.cmdTxt, argPod.usage, formatText(argPod.helpTxt)))
                else:
                    helpStrings.append("%s/%d\n  %s" % (self.cmdTxt, argCount, formatText(argPod.helpTxt)))
        elif self.__mode == CLICommand.SUBCMD_MODE:
            for subCmdObj in self.cb.values():
                for helpLine in subCmdObj.help():
                    helpStrings.append("%s %s" % (self.cmdTxt, helpLine))
        return helpStrings

    def stripCompleterKeys(self, arg):
        for key in self.argCompleters.keys():
            if arg.startswith(key):
                return arg[len(key):]
        return arg

    def configureSubcommand(self, subCmd):
        if self.__mode != CLICommand.SUBCMD_MODE:
            raise Exception("Cannot configure sub commands except in sub command mode")
        if subCmd.cmdTxt in self.cb:
            raise Exception("Cannot add duplicate subcommand for %s" % subCmd.cmdTxt)
        self.cb[subCmd.cmdTxt] = subCmd

    def configure(self, numArgs, cmdHandler, helpTxt, argHandler = None, usage=None):
        if self.__mode != CLICommand.STANDARD_MODE:
            raise Exception("Cannot configure standard arguments except in standard mode")
        if numArgs in self.cb:
            raise Exception("CLI command %s already configured for %d args" % (self.cmdTxt, numArgs))
        if numArgs < 1:
            raise Exception("CLI command cannot take a negative number of arguments")
        try:
            self.cb[numArgs] = ArgPod()
            self.cb[numArgs].cmdHandler = cmdHandler
            self.cb[numArgs].helpTxt = helpTxt
            self.cb[numArgs].usage = usage
        except:
            print(traceback.format_exc())
        if argHandler: self.cb[numArgs].argHandler = argHandler

    def process(self, args, writer):
        try:
            if self.__mode == CLICommand.SINGLETON_MODE:
                args = map(self.stripCompleterKeys, args)
                args = self.__defaultArgHandler(writer, *args)
                if args is None:
                    writer("Command failed.\n")
                    return (False, None)
                else:
                    debugPrint("CLICmd process 1")
                    d = self.__defaultCb(writer, *args)
                    return (True, d)
            if len(args)==0:
                if not self.__defaultCb:
                    writer("Command requires arguments\n")
                else:
                    args = self.__defaultArgHandler(writer, *args)
                    if args is None:
                        writer("Command failed.\n")
                        return (False, None)
                    else:
                        debugPrint("CLICmd process 2")
                        d = self.__defaultCb(writer, *args)
                        return (True, d)
            if self.__mode == CLICommand.SUBCMD_MODE:
                subCmd = args[0]
                subCmdArgs = args[1:]
                subCmdHandler = self.cb.get(subCmd, None)
                if not subCmdHandler:
                    writer("No such command %s\n" % subCmd)
                    return (False, None)

                debugPrint("CLICmd process calling subCmdHandler.process")
                return subCmdHandler.process(subCmdArgs, writer)
            else:
                args = list(map(self.stripCompleterKeys, args))
                argsPod = self.cb.get(len(args), None)
                debugPrint("CLICmd process self.cb:", self.cb)
                if not argsPod:
                    writer("Wrong number of arguments\n")
                    return (False, None)
                args = argsPod.argHandler(writer, *args)
                debugPrint("CLICmd process self.cb args:", args)
                if args is None:
                    writer("Command failed\n")
                    return (False, None)
                else:
                    debugPrint("CLICmd process 3 argsPod:", argsPod)
                    debugPrint("argspod.cmdHandler", argsPod.cmdHandler)
                    d = argsPod.cmdHandler(writer, *args)
                    debugPrint("CLICmd process 3 DONE!")
                    return (True, d)
        except:
            print(traceback.format_exc())

    def complete(self, s, state):
        if self.__mode == CLICommand.SUBCMD_MODE:
            return completeKeys(self.cb, s, state)
        elif self.__mode in [CLICommand.STANDARD_MODE, CLICommand.SINGLETON_MODE]:
            args = s.split(" ")
            tabArg = args[-1]
            finishedArgs = args[:-1]
            for key in self.argCompleters.keys():
                if tabArg.startswith(key):
                    tabArgWithoutKey=tabArg[len(key):]
                    completeString = ""
                    if finishedArgs: completeString += " ".join(finishedArgs) + " "
                    completeString += key + self.argCompleters[key](tabArgWithoutKey, state)
                    return completeString
        return None


class LineReceiver(StackingProtocol):
    """
    Shamelessly copied and slightly modified from Twisted's
    protocol.protocols.basic.LineReceiver and Protocol

    A protocol that receives lines and/or raw data, depending on mode.
    In line mode, each line that's received becomes a callback to
    L{lineReceived}.  In raw data mode, each chunk of raw data becomes a
    callback to L{LineReceiver.rawDataReceived}.
    The L{setLineMode} and L{setRawMode} methods switch between the two modes.
    This is useful for line-oriented protocols such as IRC, HTTP, POP, etc.
    @cvar delimiter: The line-ending delimiter to use. By default this is
                     C{b'\\r\\n'}.
    @cvar MAX_LENGTH: The maximum length of a line to allow (If a
                      sent line is longer than this, the connection is dropped).
                      Default is 16384.
    """
    line_mode = 1
    _buffer = b''
    _busyReceiving = False
    delimiter = b'\r\n'
    MAX_LENGTH = 16384

    def clearLineBuffer(self):
        """
        Clear buffered data.
        @return: All of the cleared buffered data.
        @rtype: C{bytes}
        """
        b, self._buffer = self._buffer, b""
        return b

    def data_received(self, data):
        """
        Protocol.dataReceived.
        Translates bytes into lines, and calls lineReceived (or
        rawDataReceived, depending on mode.)
        """
        if self._busyReceiving:
            self._buffer += data
            return

        try:
            self._busyReceiving = True
            self._buffer += data
            while self._buffer:  # and not self.paused
                if self.line_mode:
                    try:
                        line, self._buffer = self._buffer.split(
                            self.delimiter, 1)
                    except ValueError:
                        if len(self._buffer) > self.MAX_LENGTH:
                            line, self._buffer = self._buffer, b''
                            return self.lineLengthExceeded(line)
                        return
                    else:
                        lineLength = len(line)
                        if lineLength > self.MAX_LENGTH:
                            exceeded = line + self.delimiter + self._buffer
                            self._buffer = b''
                            return self.lineLengthExceeded(exceeded)
                        why = self.line_received(line)
                        debugPrint("LR data_received why:", why)
                        if (why or self.transport and
                            self.transport.disconnecting):
                            return why
                else:
                    data = self._buffer
                    self._buffer = b''
                    why = self.rawDataReceived(data)
                    if why:
                        return why
        finally:
            self._busyReceiving = False

    def setLineMode(self, extra=b''):
        """
        Sets the line-mode of this receiver.
        If you are calling this from a rawDataReceived callback,
        you can pass in extra unhandled data, and that data will
        be parsed for lines.  Further data received will be sent
        to lineReceived rather than rawDataReceived.
        Do not pass extra data if calling this function from
        within a lineReceived callback.
        """
        self.line_mode = 1
        if extra:
            return self.data_received(extra)

    def setRawMode(self):
        """
        Sets the raw mode of this receiver.
        Further data received will be sent to rawDataReceived rather
        than lineReceived.
        """
        self.line_mode = 0

    def rawDataReceived(self, data):
        """
        Override this for when raw data is received.
        """
        raise NotImplementedError

    def line_received(self, line):
        """
        Override this for when each line is received.
        @param line: The line which was received with the delimiter removed.
        @type line: C{bytes}
        """
        raise NotImplementedError

    def sendLine(self, line):
        """
        Sends a line to the other end of the connection.
        @param line: The line to send, not including the delimiter.
        @type line: C{bytes}
        """
        return self.transport.write(line + self.delimiter)

    def lineLengthExceeded(self, line):
        """
        Called when the maximum line length has been reached.
        Override if it needs to be dealt with in some special way.
        The argument 'line' contains the remainder of the buffer, starting
        with (at least some part) of the line which is too long. This may
        be more than one line, or may be only the initial portion of the
        line.
        """
        return self.transport.lose_connection()

    def make_connection(self, transport):
        """
        Make a connection to a transport and a server.
        This sets the 'transport' attribute of this Protocol, and calls
        connection_made().
        """
        self.connected = 1
        self.transport = transport
        self.connection_made(transport)


class CLIShell(LineReceiver, CompleterInterface):
    delimiter = os.linesep

    CommandHandler = CLICommand

    def __init__(self, prompt=">>> ", banner=None, higherProtocol=None):
        LineReceiver.__init__(self, higherProtocol=higherProtocol)
        self.prompt = prompt
        self.banner = banner
        self.__helpCmdHandler = CLICommand("help", "Get information on commands", self.help,
                                           mode = CLICommand.SUBCMD_MODE)
        self.__batchCmdHandler = CLICommand("batch", "Execute a file with a batch of instructions",
                                            mode = CLICommand.STANDARD_MODE)
        self.__batchCmdHandler.configure(1, self.__batch, "Launch [batch_file]",
                                         usage = "[batch_file]")
        self.__commands = {}
        self.__registerCommand(self.__helpCmdHandler)
        self.__registerCommand(self.__batchCmdHandler)
        self.__registerCommand(CLICommand("quit", "Terminate the shell", self.quit,
                                          mode=CLICommand.STANDARD_MODE))
        self.__exitListeners = set([])

    def registerExitListener(self, l):
        self.__exitListeners.add(l)

    def removeExitListener(self, l):
        if l in self.__exitListeners:
            self.__exitListeners.remove(l)

    def help(self, writer, cmd=None):
        if cmd:
            if not cmd in self.__commands:
                writer("No such command %s\n" % cmd)
            else:
                writer("\n\n".join(self.__commands[cmd].help()))
                writer("\n")
            return
        for cmdObj in self.__commands.values():
            if cmdObj == self.__helpCmdHandler:
                writer("  help [cmd]\n")
                continue
            for cmdUsageString in cmdObj.usageHelp():
                writer("  "+cmdUsageString+"\n")

    def __runBatchLines(self, writer, batchLines, batchDeferred):
        while batchLines:
            line = batchLines.pop(0)
            writer("[Batch] > %s\n" % line)
            result, d = self.line_received(line)
            debugPrint(result, d)
            if not result:
                writer("  Batch failed\n")
                # even though this failed, we have a successful callback
                # to the I/O system
                batchDeferred.callback(True)
                return
            if d:
                writer("  Batch cmd returned a deferred. Waiting to execute next line\n")
                d.addCallback(lambda res: self.__runBatchLines(writer, batchLines, batchDeferred))
                d.addErrback(lambda res: self.__runBatchLines(writer, batchLines, batchDeferred))
                # we need to wait. So return the batch deferred for the
                # i/o system to wait on.
                return batchDeferred
        writer("Batch Complete\n")
        batchDeferred.callback(True)
        # all done. No batch deferred required (return none)

    def __batch(self, writer, batchFile):
        if not os.path.exists(batchFile):
            writer("No such file %s\n" % batchFile)
            return
        d = Deferred()
        with open(batchFile) as f:
            batchLines = f.readlines()
            d = self.__runBatchLines(writer, batchLines, d)
        # d is either the same d as above, or None
        # if it's d, the I/O system will wait until batch is complete
        # otherwise, will return immediately
        return d

    def quit(self, writer, *args):
        self.transport.lose_connection()

    def registerCommand(self, cmdHandler):
        if cmdHandler.cmdTxt.startswith("_"):
            raise Exception("Cannot register commands with leading underscores")
        self.__registerCommand(cmdHandler)

    def __registerCommand(self, cmdHandler):
        if cmdHandler.cmdTxt in self.__commands:
            raise Exception("Duplicate command handler")
        self.__commands[cmdHandler.cmdTxt] = cmdHandler
        subCommandHelp = CLICommand(cmdHandler.cmdTxt, "Get information about %s" % cmdHandler.cmdTxt,
                                    lambda writer, *args: self.help(writer, cmdHandler.cmdTxt))
        self.__helpCmdHandler.configureSubcommand(subCommandHelp)

    def complete(self, s, state):
        return completeKeys(self.__commands, s, state)

    def connection_made(self, transport):
        StackingProtocol.connection_made(self, transport)
        self.transport = transport
        if self.banner:
            self.transport.write(formatText(self.banner)+"\n")

    def line_received(self, line):
        try:
            return self.lineReceivedImpl(line)
        except Exception:
            errMsg = traceback.format_exc()
            self.transport.write(errMsg+"\n")
            return False, None
        #self.transport.write("\n"+self.prompt)

    def lineReceivedImpl(self, line):
        line = line.strip()
        if not line:
            return (False, None)
        args = shlex.split(line)
        while '' in args: args.remove('')
        cmd = args[0]
        cmdArgs = args[1:]
        callbackHandler = self.__commands.get(cmd, None)
        if callbackHandler is None:
            self.transport.write("Unknown command %s\n" % cmd)
            return (False, None)
        return callbackHandler.process(cmdArgs, self.transport.write)

    def connection_lost(self, reason=None):
        super().connection_lost(reason)
        for exitListener in self.__exitListeners:
            asyncio.get_event_loop().call_soon(exitListener, reason)

DEBUG = False
def debugPrint(*s):
    if DEBUG: print("[%s]" % round(time.time() % 1e4, 4), *s)


if __name__=="__main__":
    loop = asyncio.get_event_loop()
    #loop.set_debug(True)
    printFilename = lambda writer, fname: writer("Got filename: %s\n" % fname)
    fnameCommand = CLICommand("print_file", "Print a filename", mode=CLICommand.STANDARD_MODE)
    fnameCommand.configure(1, printFilename, usage="[filename]",
                           helpTxt="Print out 'filename' to the screen.")

    def initShell(fnameCmd):
        shell = CLIShell()
        shell.registerCommand(fnameCmd)
        a = AdvancedStdio(shell)

    loop.call_soon(initShell,fnameCommand)
    loop.run_forever()
