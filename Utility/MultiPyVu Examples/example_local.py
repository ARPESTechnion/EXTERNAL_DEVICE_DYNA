#!/usr/bin/env python3
'''
example_Local.py - This example tests local operation on the MultiVu PC.
'''

import time

import MultiPyVu as mpv


# Start the server.
with mpv.Server():
    # Start the client
    with mpv.Client() as client:

        # A basic loop that demonstrates communication between
        # client/server
        for t in range(5):
            # Polls MultiVu for the temperature, field, and their
            # respective states
            t, t_status = client.get_temperature()
            f, f_status = client.get_field()

            # Relay the information from MultiVu
            message = f'The temperature is {t}, status is {t_status}; '
            message += f'the field is {f}, status is {f_status}. '
            print(message)

            # collect data at roughly 2s intervals
            time.sleep(2)
