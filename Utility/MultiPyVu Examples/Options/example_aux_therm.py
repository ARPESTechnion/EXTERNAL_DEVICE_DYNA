#!/usr/bin/env python3
"""
Simple script for reading the BRT module

@author: D. Jackson
"""

import time

import MultiPyVu as mpv


pause_time = 0.5


def save_values(client_obj: mpv.Client, mvu_dat: mpv.DataFile):
    mv_t, status_t = client_obj.get_temperature()
    mvu_dat.set_value('mv_temperature', mv_t)
    mvu_dat.set_value('t_status', status_t)
    print(f'{mv_t:^15}{status_t:^16}', end='')

    aux_t, status_aux = client_obj.get_aux_temperature()
    mvu_dat.set_value('aux_temperature', aux_t)
    mvu_dat.set_value('aux_temperature_err', status_aux)
    print(f'{aux_t:^15}{status_aux:^16}')

    mvu_dat.write_data()


def main():
    # configure the MultiVu columns
    data = mpv.DataFile()
    data.add_multiple_columns(
        ['mv_temperature', 't_status',
         'aux_temperature', 'aux_temperature_err',
         ])
    data.create_file_and_write_header(
        'AuxThermFile.dat',
        'Collecting Aux Therm Data'
    )

    with mpv.Server():
        with mpv.Client() as client:

            # print a header
            print('')
            hdr = f"{'___ T (K) ___':^15}{'__ Error Code __':^16}"
            hdr += f"{'___ Aux (K) ___':^15}{'__ Error Code __':^16}"
            print(hdr)

            points = 2
            for t in range(points):
                save_values(client, data)
                time.sleep(pause_time)


if __name__ == '__main__':
    main()
