class YurtException(Exception):
    def __init__(self, message):
        self.message = message


class VMException(YurtException):
    pass


class VBoxManageException(YurtException):
    pass


class ConfigReadException(YurtException):
    pass


class ConfigWriteException(YurtException):
    pass
