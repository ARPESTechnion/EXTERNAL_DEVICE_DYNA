"""
example_sweep.py - Demonstrates the use of various commands to
save data while continuously sweeping the temperature/field. This
script should run on the MultiVu PC, as it is configured for local
operation.
"""

import time

import MultiPyVu as mpv

# Set up data file with columns for temperature
filename = 'Measure_while_sweeping.dat'
data = mpv.DataFile()
data.add_column('Temperature (K)')
data.create_file_and_write_header(filename,
                                  'Collecting Temperature Data')


def save_values(comment=''):
    """
    Create save command to save get the temperature while sleeping
    """
    t, _ = client.get_temperature()
    data.set_value('Temperature (K)', t)
    # Add an optional comment
    if comment != '':
        data.set_value('Comment', comment)
    data.write_data()


with mpv.Server() as server:
    with mpv.Client() as client:
        # Below shows how to measure while sweeping temperature
        # at uniform time gap
        pause_time = 0.5
        appr = client.temperature.approach_mode.fast_settle
        msg = '<Sweep the temperature to 295 K at 1 K/min>'
        print(msg)
        client.set_temperature(295.0, 1.0, appr)

        # Mask determines what the system is waiting for
        # can be replaced by client.field.waitfor.
        mask = client.temperature.waitfor
        while not client.is_steady(mask):
            # Measure and save
            save_values('uniform_time')
            # Wait
            time.sleep(pause_time)

        # Collect data at a uniform temperature spacing
        delta_t = 0.5
        msg = '<Sweep the temperature to 300 K at 1 K/min>'
        print(msg)
        client.set_temperature(300.0, 1.0, appr)
        t_previous, _ = client.get_temperature()
        while not client.is_steady(mask):
            t, _ = client.get_temperature()
            if abs(t - t_previous) > delta_t:
                save_values('uniform_temp')
                t_previous, _ = client.get_temperature()
            time.sleep(pause_time)
