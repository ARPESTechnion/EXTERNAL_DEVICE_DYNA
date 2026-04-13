#!/usr/bin/env python3
"""
Created on Mon Jun 7 23:47:19 2021

run_mv_server.py is a module for use on a computer running
MultiVu.  It can be used with MultiPyVu.Client to control
a Quantum Design cryostat.

"""

import sys
from time import sleep

import MultiPyVu as mpv


def server(flags: str = ''):
    """
    This method deciphers the command line text, and then starts the
    MultiVuServer.

    Parameters
    ----------
    flags : str
        For a list of flags, use the help flag, '--help'.
        The default is '', which will look for command-line
        arguments.
    """

    user_flags = []
    if flags == '':
        user_flags = sys.argv[1:]
    else:
        user_flags = flags.split(' ')

    s = mpv.Server(user_flags)
    try:
        s.open()

        connections = s.number_of_clients()
        print(f'{connections = }')
        while True:
            n = s.number_of_clients()
            if connections != n:
                connections = n
                print(f'{connections = }')
            if s.server_status() == 'closed':
                print('exiting script')
                break
            sleep(0.3)
        s.close()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    # Open the server with default options
    server()

    # Use the following for running as a PPMS
    # in scaffolding mode:
    # server('-s ppms')
