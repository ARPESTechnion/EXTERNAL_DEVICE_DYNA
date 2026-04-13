#!/usr/bin/env python3
"""
Simple script for interacting with the resistivity option

"""

import time

import MultiPyVu as mpv


def save_values(client_object: mpv.Client, mvu_dat: mpv.DataFile):
    # For each bridge get the resistance (r) and status (s)
    for bridge in [1, 2, 3]:
        r, s = client_object.resistivity.get_resistance(bridge)
        # Set the value for resistance and status
        mvu_dat.set_value(f'r{bridge}', r)
        mvu_dat.set_value(f'r{bridge}_err', s)
        print(f'{r:^15}{s:^10}', end='')
        # Write the resistance and status
        mvu_dat.write_data()
    print()


def main():
    # configure the MultiVu columns
    data = mpv.DataFile()
    data.add_multiple_columns(['r1', 'r1_err',
                               'r2', 'r2_err',
                               'r3', 'r3_err',])
    data.create_file_and_write_header('Resistivity.dat',
                                      'Collecting resistivity Data')

    with mpv.Server():
        with mpv.Client() as client:
            # print a header
            print('')
            hdr = f"{'___ r1 ___':^15}{'__ Error Code __':^10}"
            hdr += f"{'___ r2 ___':^15}{'__ Error Code __':^10}"
            hdr += f"{'___ r3 ___':^15}{'__ Error Code __':^10}"
            print(hdr)

            pause_time = 0.5
            # Sets up the bridge limits for each bridge
            for bridge in [1, 2, 3]:
                client.resistivity.bridge_setup(bridge_number=bridge,
                                                channel_on=True,
                                                current_limit_uA=8000,
                                                power_limit_uW=500,
                                                voltage_limit_mV=1000)
            # Add a delay to allow time for configuration.
            time.sleep(5)

            points = 8
            for t in range(points):
                save_values(client, data)
                time.sleep(pause_time)


if __name__ == '__main__':
    main()
