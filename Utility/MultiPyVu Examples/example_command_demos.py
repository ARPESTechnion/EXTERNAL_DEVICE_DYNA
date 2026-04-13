#!/usr/bin/env python3
"""
example_Command-Demos.py - Demonstrates the use of various commands to
set temp/field/chamber, read back their present value and status, and
wait for stability criteria to be met.  This script should run on the
MultiVu PC, as it is configured for local operation.
"""

import os
import time
import matplotlib.pyplot as plt

import MultiPyVu as mpv


def create_new_dat_file(file_path: str) -> bool:
    """
    Checks if the file exists.  If so, asks if this should
    be overwritten or appended.
    """
    create_file = True
    if os.path.exists(file_path):
        print(f"The file '{file_path}' already exists.")
        msg = 'overwrite (o), append (a), or cancel (c)? [o/a/c]:'
        while True:
            choice = input(msg).lower()
            if choice in ['o', 'a', 'c']:
                break
            else:
                msg = "Invalid choice. Please enter 'o' for overwrite "
                msg += ", 'a' for append, or 'c' to cancel. [o/a/c]"
        if choice == 'o':
            os.remove(file_path)
        elif choice == 'a':
            create_file = False
        else:
            raise ValueError('User cancelled')
    return create_file


def save_temp_field_chamber(client_obj: mpv.Client, datafile: mpv.DataFile):
    t, t_status = client_obj.get_temperature()
    f, f_status = client_obj.get_field()
    ch = client_obj.get_chamber()
    data_point = ['Temperature (K)', t,
                  'Field (Oe)', f,
                  'Chamber Status', ch]
    datafile.write_data_using_list(data_point)
    print(f'{t:{7}.{3}f} {t_status:{10}} {f:{7}} {f_status:{20}} {ch:{15}}')


def main():
    # configure the MultiVu .dat file
    data = mpv.DataFile()
    filename = 'example_command_demos_data.dat'
    try:
        create_new_dat_file(filename)
    except (ValueError, KeyboardInterrupt) as e:
        print(str(e))
        return
    data.add_multiple_columns(['Temperature (K)',
                               'Field (Oe)',
                               'Chamber Status'])
    data.create_file_and_write_header(filename,
                                      'example_command_demos.py')

    with mpv.Server():
        with mpv.Client() as client:
            temperature_mode = client.temperature.approach_mode.fast_settle

            print('Setting 300 K and 0 Oe')
            client.set_temperature(300.0,
                                   20.0,
                                   temperature_mode)
            client.set_field(0.0,
                             200.0,
                             client.field.approach_mode.linear,
                             client.field.driven_mode.driven)

            msg = 'Waiting for 10 seconds after temperature '
            msg += 'and field are stable'
            print(msg)
            client.wait_for(10,
                            timeout_sec=0,
                            bitmask=client.temperature.waitfor
                            | client.field.waitfor)

            print('Change the chamber state to Purge/Seal')
            client.set_chamber(client.chamber.mode.purge_seal)
            client.wait_for(10, timeout_sec=0, bitmask=client.chamber.waitfor)

            # print a header
            print('')
            hdr = '______ T ______     __________ H __________\t______ Chamber Status ______'
            print(hdr)

            # Polling temperature/field during a temperature ramp to 296 K
            current_temp, _ = client.get_temperature()
            set_point = 296.0
            rate = 20.0
            delta_t = 0.25
            message = f'Set the temperature {set_point} K and then '
            message += f'collect data every {delta_t} K while ramping'
            print(f'\n{message}\n')
            client.set_temperature(set_point,
                                   rate,
                                   temperature_mode)
            t_previous = current_temp
            while not client.is_steady(client.temperature.waitfor):
                t, _ = client.get_temperature()
                if abs(t - t_previous) > delta_t:
                    save_temp_field_chamber(client, data)
                    t_previous, _ = client.get_temperature()
                time.sleep(0.5)

            # Polling temperature/field during a field ramp to 1000 Oe
            current_field, _ = client.get_field()
            set_point = 1000.0
            rate = 10.0
            delta_f = 100.0
            message = f'Set the field to {set_point} Oe and then collect data '
            message += 'while ramping'
            print(f'\n{message}\n')
            client.set_field(set_point,
                             rate,
                             client.field.approach_mode.linear,
                             client.field.driven_mode.driven)
            f_previous = current_field
            while not client.is_steady(client.field.waitfor):
                f, _ = client.get_field()
                if abs(f - f_previous) > delta_f:
                    save_temp_field_chamber(client, data)
                    f_previous, _ = client.get_field()
                time.sleep(0.5)

            field, _ = client.get_field()
            field_units = client.field.units
            print(f'\nField = {field} {field_units}')
            new_field = field + 100.0
            rate = 250.0
            print(f'Raising the field to {new_field} {field_units}')
            client.set_field(new_field,
                             rate,
                             client.field.approach_mode.linear)

            # Without using the .wait_for command, the field will be
            # changing while we also set and then wait for the temperature
            # to reach its set point.

            temperature, _ = client.get_temperature()
            temp_units = client.temperature.units
            print(f'\nTemperature = {temperature} {temp_units}')
            delta_t = 2.0
            new_t = temperature + delta_t
            rate_t = 5.0
            msg = f'Raising the temperature by {delta_t} {temp_units}.'
            print(msg)
            client.set_temperature(new_t,
                                   rate_t,
                                   temperature_mode)
            save_temp_field_chamber(client, data)
            start = time.time()
            client.wait_for(0, 0, client.temperature.waitfor)
            end = time.time()
            save_temp_field_chamber(client, data)
            temperature, _ = client.get_temperature()
            print(f'Temperature = {temperature} {temp_units}')
            print(f'The ramp took {end - start:.3f} sec')

            field, _ = client.get_field()
            print(f'\nField = {field} {field_units}')
            delta_field = 500.0
            new_field = field + delta_field
            rate_field = 50.0
            pause_time = 10.0
            msg = f'Raising the field by {delta_field} {field_units}.  Once '
            msg += f'stable, adding another {pause_time} seconds before '
            msg += 'moving on.'
            print(msg)
            client.set_field(new_field,
                             rate_field,
                             client.field.approach_mode.linear)
            save_temp_field_chamber(client, data)
            start = time.time()
            client.wait_for(pause_time, 0, client.field.waitfor)
            end = time.time()
            save_temp_field_chamber(client, data)
            field, _ = client.get_field()
            print(f'Field = {field} {field_units}')
            print(f'The ramp took {end - start:.3f} sec')

            new_t = 300.0
            new_field = 0.0
            msg = f'\nWait for the temperature to reach {new_t} and '
            msg += f'the field to reach {new_field}'
            print(msg)
            client.set_temperature(new_t,
                                   rate_t,
                                   temperature_mode)
            client.set_field(new_field,
                             rate_field,
                             client.field.approach_mode.linear)
            save_temp_field_chamber(client, data)
            start = time.time()
            client.wait_for(0,
                            0,
                            client.temperature.waitfor | client.field.waitfor)
            end = time.time()
            save_temp_field_chamber(client, data)
            temperature, _ = client.get_temperature()
            field, _ = client.get_field()
            print(f'Temperature = {temperature} {temp_units}')
            print(f'Field = {field} {field_units}')
            print(f'The ramp took {end - start:.3f} sec')

            time.sleep(5)

            # For PPMS systems, the magnet can be put in persistent
            # mode.  For VersaLab/Dynacool/OptiCool/MPMS3, this will
            # throw an mpv.MultiPyVuError.
            print('\nTry to put the magnet in persistent mode:')
            print('This will only work for a PPMS')
            try:
                client.set_field(100,
                                 100,
                                 client.field.approach_mode.oscillate,
                                 client.field.driven_mode.persistent)
            except mpv.MultiPyVuError as e:
                print(str(e))
            client.wait_for(bitmask=client.field.waitfor)
            save_temp_field_chamber(client, data)
            print(f'Field = {field} {field_units}')

        # Open and plot the .dat file
        my_dataframe = data.parse_MVu_data_file(filename)

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
