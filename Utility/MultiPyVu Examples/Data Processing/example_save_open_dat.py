"""
example_Save-Open_dat.py - Demonstrates how to save data to a dat files
using the save_values  function and how to open and plot .dat files.
The script will run through a temperature ramp, saving the temperature
and field while the system is not stable. The script will then open and
plot this via matplotlib. This script should run on the MultiVu PC, as
it is configured for local operation.
"""


import time
import matplotlib.pyplot as plt

import MultiPyVu as mpv

# configure the MultiVu columns
data = mpv.DataFile()
# add a title for all data points being recorded
data.add_multiple_columns(['Temperature (K)', 'Field (Oe)'])
# create the file and its header before saving data
data.create_file_and_write_header('Temperature.dat', 'Collecting T Data')


# define a function to save values
def save_values(temperature: float, field: float):
    print(f'{temperature = :.2f}\t{field = :.1f}')
    # write temperature and field to associated columns
    data.set_value('Temperature (K)', temperature)
    data.set_value('Field (Oe)', field)
    data.write_data()


def save_while_ramping(client_obj: mpv.Client, delta_t: float = 0.5):
    """
    Save data every delta_t degrees
    """
    previous_t, _ = client_obj.get_temperature()
    while not client_obj.is_steady(client_obj.temperature.waitfor):
        # read temperature and field
        t, _ = client_obj.get_temperature()
        f, _ = client_obj.get_field()
        if abs(t - previous_t) > delta_t:
            save_values(t, f)
            previous_t, _ = client_obj.get_temperature()
        time.sleep(1)


def main():
    with mpv.Server():
        with mpv.Client() as client:
            print('Connected')

            print('Setting the temperature to 300 K')
            settle_mode = client.temperature.approach_mode.fast_settle
            client.set_temperature(300.0, 12.0, settle_mode)
            client.wait_for(bitmask=client.temperature.waitfor)

            # Get initial temperature, field, and chamber status and print them
            t, status_t = client.get_temperature()
            f, status_f = client.get_field()
            c = client.get_chamber()
            t_units = client.temperature.units
            f_units = client.field.units
            message = f'The Temperature is {t} {t_units}, '
            message += f'and the status is {status_t}.'
            message += f'\nThe Field is {f} {f_units}, '
            message += f'and the status is {status_f}.'
            message += f'\nThe Chamber is {c}.'
            print(message)

            print('Setting 295 K')
            client.set_temperature(295.0, 12.0, settle_mode)
            save_while_ramping(client)

            # Wait for 10 seconds after temperature and field are stable
            print('Pause for 10 seconds ')
            time.sleep(10)

            print('Setting 300 K')
            mode = client.temperature.approach_mode.fast_settle
            client.set_temperature(300.0, 12.0, mode)
            save_while_ramping(client)

    # open .dat file
    my_dataframe = data.parse_MVu_data_file('Temperature.dat')

    # set up plot
    fig, ax = plt.subplots(1, 1)
    fig.suptitle('Temperature Ramp Plot')
    ax.set_xlabel('Time Stamp (sec)')
    ax.set_ylabel('Temperature (K)')
    ax.scatter(x='Time Stamp (sec)',
               y='Temperature (K)',
               data=my_dataframe,
               )
    plt.show()


if __name__ == '__main__':
    main()
