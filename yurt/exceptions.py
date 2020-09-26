class YurtException(Exception):
    def __init__(self, message):
        self.message = message


class YurtCalledProcessException(YurtException):
    pass


class YurtCalledProcessTimeout(YurtException):
    pass


class YurtSSHException(YurtException):
    pass


class LXCException(YurtException):
    pass


class VBoxException(YurtException):
    pass


class VMException(YurtException):
    pass


class ConfigReadException(YurtException):
    pass


class ConfigWriteException(YurtException):
    pass
