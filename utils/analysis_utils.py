"""Utility functions for analyzing stream gauge data, and slide data.
"""

import math, datetime

from xml.etree import ElementTree as ET

import requests, pytz

# Assume this file will be imported in a directory outside of utils.
from utils.ir_reading import IRReading


# Critical values.
# Critical rise in feet. Critical slope, in ft/hr.
RISE_CRITICAL = 2.5
M_CRITICAL = 0.5


def fetch_current_data(fresh=True, filename='ir_data_other/current_data.txt'):
    """Fetches current data from the river gauge.

    If fresh is False, looks for cached data.
      Cached data is really just for development purposes, to avoid hitting
      the server unnecessarily.

    Returns the current data as text.
    """
    print("  Fetching data...")
    if fresh:
        print("    Fetching fresh gauge data...")

        gauge_url = "https://water.weather.gov/ahps2/hydrograph_to_xml.php?gage=irva2&output=tabular"
        gauge_url_xml = "https://water.weather.gov/ahps2/hydrograph_to_xml.php?gage=irva2&output=xml"
        r = requests.get(gauge_url_xml)
        print(f"    Response status: {r.status_code}")
        # return r

        with open(filename, 'w') as f:
            f.write(r.text)
        print(f"    Wrote data to {filename}.")

        return r.text

    else:
        # Try to use cached data.
        try:
            with open(filename) as f:
                current_data = f.read()
        except:
            # Can't read from file, so fetch fresh data.
            print("    Couldn't read from file, fetching fresh data...")
            return fetch_current_data(fresh=True)
        else:
            print("    Read gauge data from file.")
            return current_data


def process_xml_data(data):
    """Processes xml data from text file.
    Returns a list of readings.
    """
    print("  Processing raw data...")
    # Parse xml tree from file.
    root = ET.fromstring(data)
    tree = ET.ElementTree(root)

    # 6th element is the set of observed readings.
    # 1st and 2nd elements of each reading are datetime, height.
    readings = []
    for reading in root[5]:
        dt_reading_str = reading[0].text
        dt_reading = datetime.datetime.strptime(dt_reading_str,
                 "%Y-%m-%dT%H:%M:%S-00:00")
        dt_reading_utc = dt_reading.replace(tzinfo=pytz.utc)
        height = float(reading[1].text)

        reading = IRReading(dt_reading_utc, height)
        readings.append(reading)

    # Readings need to be in chronological order.
    # DEV: This should be an absolute ordering, not just relying on 
    #      input file format.
    readings.reverse()

    print(f"    Found {len(readings)} readings.")
    return readings


def get_critical_points(readings):
    """Return critical points.
    A critical point is the first point where the slope has been critical
    over a minimum rise. Once a point is considered critical, there are no
    more critical points for the next 6 hours.
    """
    print("  Looking for critical points...")

    # What's the longest it could take to reach critical?
    #   RISE_CRITICAL / M_CRITICAL
    #  If it rises faster than that, we want to know.
    #    Multiplied by 4, because there are 4 readings/hr.
    readings_per_hr = get_reading_rate(readings)
    max_lookback = math.ceil(RISE_CRITICAL / M_CRITICAL) * readings_per_hr

    critical_points = []
    # Start with 10th reading, so can look back.
    for reading_index, reading in enumerate(readings[max_lookback:]):
        # print(f"  Examining reading: {reading.get_formatted_reading()}")
        # Get prev max_lookback readings.
        prev_readings = [reading for reading in readings[reading_index-max_lookback:reading_index]]
        for prev_reading in prev_readings:
            rise = reading.get_rise(prev_reading)
            m = reading.get_slope(prev_reading)
            # print(f"    Rise: {rise} Slope: {m}")
            if rise >= RISE_CRITICAL and m > M_CRITICAL:
                # print(f"Critical point: {reading.get_formatted_reading()}")
                critical_points.append(reading)
                break

    print(f"    Found {len(critical_points)} critical points.")
    return critical_points


def get_reading_rate(readings):
    """Return readings/hr.
    Should be 1 or 4, for hourly or 15-min readings.
    """
    reading_interval = (
        (readings[1].dt_reading - readings[0].dt_reading).total_seconds() // 60)
    reading_rate = int(60 / reading_interval)
    # print(f"Reading rate for this set of readings: {reading_rate}")

    return reading_rate


def get_recent_readings(readings, hours_lookback):
    """From a set of readings, return only the most recent x hours
    of readings.
    """
    print(f"  Getting most recent {hours_lookback} hours of readings...")
    last_reading = readings[-1]
    td_lookback = datetime.timedelta(hours=hours_lookback)
    dt_first_reading = last_reading.dt_reading - td_lookback
    recent_readings = [r for r in readings
                            if r.dt_reading >= dt_first_reading]

    print(f"    Found {len(recent_readings)} recent readings.")
    return recent_readings