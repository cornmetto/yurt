class YurtException(Exception):
    def __init__(self, message):
        self.message = message


class CommandException(YurtException):
    pass


class CommandTimeout(YurtException):
    pass


class RemoteCommandException(YurtException):
    pass


class LXCException(YurtException):
    pass


class TermException(YurtException):
    pass


class VBoxException(YurtException):
    pass


class VMException(YurtException):
    pass


class ConfigReadException(YurtException):
    pass


class ConfigWriteException(YurtException):
    pass
