"""
example_stabilize.py - Demonstrates the use of various commands 
to measure at stable temperature/field.  This script should run on the
MultiVu PC, as it is configured for local operation.
"""

import numpy as np

import MultiPyVu as mpv


# Set up data file with columns for temperature
filename = 'Measure_while_stabilizing.dat'
data = mpv.DataFile()
data.add_multiple_columns(['Temperature (K)',
                           'Field (Oe)'])
data.create_file_and_write_header(filename,
                                  'Collecting Temperature Data')


def save_values(temperature: float = -1,
                field: float = -1,
                comment: str = ''):
    """
    Save the temperature or field to the data MultiVu file
    """
    if temperature < 0 and field < 0:
        raise ValueError('Must provide a temperature or field')
    if temperature >= 0:
        data.set_value('Temperature (K)', temperature)
        print(f'Temperature = {temperature} K')
    if field >= 0:
        data.set_value('Field (Oe)', field)
        print(f'Field = {field} Oe')
    # Add an optional comment
    if comment != '':
        data.set_value('Comment', comment)
    data.write_data()


def main():
    with mpv.Server():
        with mpv.Client() as client:
            # Below shows how to measure while stabilizing at temperature
            msg = '<Set the temperature to 295 K while stabilizing every 1 K>'
            print(msg)

            initial_temp_k = 300
            final_temp_k = 295
            step_size_k = 2

            # Determines the temperature set points from
            # initial temperature, final temperature, and step size
            num_points = int(abs(initial_temp_k - final_temp_k) / step_size_k) + 1
            temperatures = np.linspace(initial_temp_k,
                                       final_temp_k,
                                       num_points)

            # Set approach mode
            appr = client.temperature.approach_mode.fast_settle

            stabilization_time_sec = 10
            for t in temperatures:
                # Sets each temperature in the range we are interested in
                # at a rate of 1K /min with a fast approach
                client.set_temperature(t, 1.0, appr)
                client.wait_for(stabilization_time_sec,
                                0,
                                client.temperature.waitfor)
                t, _ = client.get_temperature()
                save_values(temperature=t, comment='Measured while stable')

            # Below shows how to measure while stabilizing at field
            msg = '<Set the field to 1000 Oe while stabilizing every 100 Oe>'
            print(msg)

            init_field_oe = 0
            final_field_oe = 1000
            step_size_oe = 100

            # Determines the field set points from
            # initial field, final field, and step size
            num_points = abs(init_field_oe - final_field_oe) / step_size_oe
            num_points = int(num_points) + 1
            fields = np.linspace(init_field_oe, final_field_oe, num_points)

            # Set approach mode
            appr = client.field.approach_mode.linear

            stabilization_time_sec = 0
            for f in fields:
                # Sets each field in the range we are interested in at a rate of 50 Oe /sec 
                # with a linear approach
                client.set_field(f, 50.0, appr)
                client.wait_for(stabilization_time_sec,
                                0,
                                client.field.waitfor)
                save_values(field=f, comment='Measured while stable')


if __name__ == '__main__':
    main()
