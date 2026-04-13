#!/usr/bin/env python3
"""
Simple script for interacting with the horizontal rotator option

"""

import time

import MultiPyVu as mpv


def save_values(client_object: mpv.Client, mvu_dat: mpv.DataFile) -> str:
    # Get the position
    p, s = client_object.get_position()
    # Set the value for resistance and status
    mvu_dat.set_value('position', p)
    mvu_dat.set_value('position_status', s)
    print(f'{p:^15.4f}{s:^10}', end='')
    # Write the resistance and status
    mvu_dat.write_data()
    print()
    return s


def main():
    # configure the MultiVu columns
    data = mpv.DataFile()
    data.add_column('position')
    data.add_column('position_status')
    data.create_file_and_write_header('Rotator.dat',
                                      'Using the horizontal rotator')

    with mpv.Server():
        with mpv.Client() as client:
            # print a header
            print('')
            hdr = f"{'___ pos ___':^15}{'__ status __':^10}"
            print(hdr)

            pos, status = client.get_position()
            new_pos = 360.0 if pos < 180.0 else 7.0
            client.set_position(new_pos,
                                100.0,
                                )
            pause_time = 0.5
            pos, status = client.get_position()
            while status != 'Transport stopped at set point':
                status = save_values(client, data)
                time.sleep(pause_time)


if __name__ == '__main__':
    main()
