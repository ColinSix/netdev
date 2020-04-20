"""
Copyright (c) 2019 Sergey Yakovlev <selfuryon@gmail.com>.

This module provides different closures for working with cisco-like devices

"""
from enum import IntEnum
from re import match
from typing import List

from netdev.connections import IOConnection
from netdev.core import (DeviceManager, DeviceStream, Layer, LayerManager,
                         enter_closure, exit_closure)


class CiscoTerminalModes(IntEnum):
    """ Configuration modes for Cisco-Like devices """

    UNPRIVILEGE_EXEC = 0
    PRIVILEGE_EXEC = 1
    CONFIG_MODE = 2


def cisco_check_closure(unprivilege_pattern, privilege_pattern, config_pattern):
    """ Generates cisco_like checker """

    async def cisco_checker(prompt: str) -> IntEnum:
        result = None  # type: CiscoTerminalMode
        if config_pattern in prompt:
            result = CiscoTerminalModes.CONFIG_MODE
        elif privilege_pattern in prompt:
            result = CiscoTerminalModes.PRIVILEGE_EXEC
        elif unprivilege_pattern in prompt:
            result = CiscoTerminalModes.UNPRIVILEGE_EXEC
        else:
            raise ValueError("Can't find the terminal mode")

        return result

    return cisco_checker


def cisco_set_prompt_closure(delimeter_list: List[str]):
    """ Generates cisco-like set_prompt function """

    def cisco_set_prompt(buf: str) -> str:
        delimeters = r"|".join(delimeter_list)
        delimeters = rf"[{delimeters}]"
        config_mode = r"(\(.*?\))?"
        buf = buf.strip().split('\n')[-1]
        pattern = rf"([\w\d\-\_]+)\s?{delimeters}"
        prompt = match(pattern, buf).group(1)
        prompt_pattern = prompt + config_mode + delimeters
        return prompt_pattern

    return cisco_set_prompt


def create_cisco_like_dmanager(conn: IOConnection, delimeter_list: List[str], terminal_modes: IntEnum):
    # Create Cisco Like Device Manager
    set_prompt_func = cisco_set_prompt_closure(delimeter_list)
    dstream = DeviceStream(conn, delimeter_list, set_prompt_func, "term len 0")
    # Create Layers
    unprivilege_layer = Layer(terminal_modes(
        0).name, dstream, enter_func=None, exit_func=None, transactional=False, commit_func=None)
    privilege_layer = Layer(terminal_modes(1).name, dstream, enter_func=enter_closure(
        "enable"), exit_func=exit_closure("exit"), transactional=False, commit_func=None)
    config_layer = Layer(terminal_modes(2).name, dstream, enter_func=enter_closure(
        "conf t"), exit_func=exit_closure("exit"), transactional=False, commit_func=None)
    # Create Layer Manager
    layer_manager = LayerManager(
        dstream, terminal_modes, cisco_check_closure(r">", r"#", r")#"))
    layer_manager.add_layer(terminal_modes(0), unprivilege_layer)
    layer_manager.add_layer(terminal_modes(1), privilege_layer)
    layer_manager.add_layer(terminal_modes(2), config_layer)
    # Create Device Manager
    device_manager = DeviceManager(dstream, layer_manager)
    return device_manager
