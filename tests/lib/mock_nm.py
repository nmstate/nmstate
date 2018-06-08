#!/usr/bin/python3 -tt
# vim: fileencoding=utf8

UP = 1
DOWN = 0

NM_DEVICE_TYPE_GENERIC = 14


class MockNmConnection(object):
    def get_ip4_config(self):
        return None


class MockNmDevice(object):
    def __init__(self, devstate=DOWN, active_connection=MockNmConnection(),
                 iface="lo"):
        self._devstate = devstate
        self._active_connection = active_connection
        self._iface = iface

    def get_active_connection(self):
        return self._active_connection

    def get_device_type(self):
        return NM_DEVICE_TYPE_GENERIC

    def get_iface(self):
        return self._iface

    def get_state(self):
        return self._devstate

    def get_type_description(self):
        return 'Generic device'
