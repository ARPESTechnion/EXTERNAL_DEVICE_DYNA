
import MultiPyVu as mpv
import time
import matplotlib.pyplot as plt


# Set up data file with columns for the resistance in each
# channel, resistance error, and temperature
filename = 'Resistivity.dat'
data = mpv.DataFile()
data.add_multiple_columns(['r1', 'r1_err',
                           'r2', 'r2_err',
                           'r3', 'r3_err',
                           'Temperature (K)'])
data.create_file_and_write_header(filename,
                                  'Collecting resistivity Data')


def save_values(comment=''):
    """
    Create save command to save get the resistance for each
    bridge and temperature and then save them to the data file.
    """
    # For each bridge get the resistance (r) and status (s)
    for bridge in [1, 2, 3]:
        r, s = client.resistivity.get_resistance(bridge)
        # Set the value for resistance and status
        data.set_value(f'r{bridge}', r)
        data.set_value(f'r{bridge}_err', s)
        print(f'{r:^15}{s:^10}', end='')
    print()
    t, _ = client.get_temperature()
    data.set_value('Temperature (K)', t)
    # Add an optional comment
    if comment != '':
        data.set_value('Comment', comment)
    # Write the resistance and status
    data.write_data()


# Update the IP address to match the Server IP address
IP = '127.0.0.1'
# Connect as client
with mpv.Client(IP) as client:
    # Vent the chamber you can load your sample
    client.set_chamber(client.chamber.mode.vent_seal)
    # Waits for a user input confirming the sample has been loaded
    input("Please load your sample. When done press Enter to continue:")
    # Purge and seal the chamber
    client.set_chamber(client.chamber.mode.purge_seal)

    # Sets the temperature to 300K
    client.set_temperature(300,
                           20,
                           client.temperature.approach_mode.fast_settle)
    msg = '<Wait for the temperature to reach 300K with no time out or delay>'
    print(msg)
    client.wait_for(0, 0, client.temperature.waitfor)

    # Sets up the bridge limits for each bridge
    for bridge in [1, 2, 3]:
        client.resistivity.bridge_setup(bridge_number=bridge,
                                        channel_on=True,
                                        current_limit_uA=8000,
                                        power_limit_uW=500,
                                        voltage_limit_mV=1000)

    # Print a header
    hdr = f"{'___ r1 ___':^15}{'__ Error Code __':^10}"
    hdr += f"{'___ r2 ___':^15}{'__ Error Code __':^10}"
    hdr += f"{'___ r3 ___':^15}{'__ Error Code __':^10}"
    print(hdr)

    # Below shows how to measure while stabilizing at each
    # set point before measuring
    msg = '<Set the temperature to stabilize at from 300 K '
    msg += 'to 295 K with steps of 1 K>'
    print(msg)
    for temperature in range(300, 294, -1):
        # Sets the temperature to the index in Temperatures
        client.set_temperature(temperature,
                               1,
                               client.temperature.approach_mode.fast_settle)
        # Waits for the temperature to reach the
        # set point with one minute delay
        client.wait_for(60, 0, client.temperature.waitfor)
        save_values('stable')

    # # Below shows how to measure while sweeping a temperature
    # # Define a pause time between measurements
    pause_time = 0.5
    appr = client.temperature.approach_mode.fast_settle
    msg = '<Sweep the temperature up to 300 K at 1 K/min>'
    print(msg)
    client.set_temperature(300.0, 1.0, appr)

    mask = client.temperature.waitfor
    while not client.is_steady(mask):
        # Measure and save
        save_values('uniform_time')
        # Wait
        time.sleep(pause_time)

    # Collect data at a uniform temperature spacing
    delta_t = 0.5
    msg = '<Sweep the temperature to 295 K at 1 K/min>'
    print(msg)
    client.set_temperature(295.0, 1.0, appr)
    t_previous = 300.0
    while not client.is_steady(mask):
        t, _ = client.get_temperature()
        if abs(t - t_previous) > delta_t:
            save_values('uniform_temp')
            t_previous, _ = client.get_temperature()
        time.sleep(pause_time)

print('<Graphing data>')
# Open .dat file
my_dataframe = data.parse_MVu_data_file(filename)
# Selects channel 1 resistance and temperature
# Set up plot
fig, ax = plt.subplots(1, 1)
fig.suptitle('Resistance v Temperature')
ax.set_xlabel('Temperature (K)')
# note \u03A9 is the 'ohms' character
ax.set_ylabel('Resistance (\u03A9)')
# plot relevant points
ax.scatter(my_dataframe['Temperature (K)'],
           my_dataframe['r1']
           )
plt.show()
