from prometheus_client import start_http_server, Summary, Gauge, Info
import random
import time

import requests
import os
from os.path import join, dirname
from dotenv import load_dotenv
import json
from datetime import datetime
from sys import platform
import logging
from cachetools import cached, TTLCache

def cur_price(data, time):
    result = 101.00
    for a in data:
        if a['valid_from'] == time:
            logging.debug(
                "Located: {valid_from} {data}".format(valid_from=a['valid_from'], data=a))
            result = a
            break

    return result


@cached(cache=TTLCache(maxsize=2048, ttl=1800))
def fetch_unit_rates():  # GET current tariff data from Octopus API
    url = "{url}/v1/products/{prod_code}/electricity-tariffs/{tariff}/standard-unit-rates".format(
        url=os.getenv('BASE_URL'),
        prod_code=os.getenv(
            'PRODUCT_CODE'),
        tariff=os.getenv('TARIFF'))
    logging.debug("GET URL " + url)

    response = requests.get(url)
    if response.status_code == 200:  # if success, continue. If not, die.
        return json.loads(response.text)
    else:
        logging.error("Unable to get rates. Response code {code}. Exiting".format(code=str(response.status_code)))
        exit(0)


@cached(cache=TTLCache(maxsize=2048, ttl=32000))
def fetch_consumption():  # GET consumption data from Octopus API
    url = "{url}/v1/electricity-meter-points/{mpan}/meters/{serial_number}/consumption/" \
          "?group_by=day&page_size=2&order_by=-period".format(
        url=os.getenv('BASE_URL'), mpan=os.getenv('MPAN'), serial_number=os.getenv('ELEC_SERIAL_NUMBER'))
    logging.debug("GET URL " + url)
    key = os.getenv('KEY')
    response = requests.get(url=url, auth=(key, ''))
    if response.status_code == 200:  # if success, continue. If not, die.
        return json.loads(response.text)
    else:
        logging.error("Unable to get rates. Response code {code}. Exiting".format(code=str(response.status_code)))
        exit(0)


# Create a metric to track time spent and requests made.
CURRENT_PRICE_INC_VAT = Gauge('current_electricity_price_inc_vat', 'Current Electricity price including VAT')
CURRENT_PRICE_EXC_VAT = Gauge('current_electricity_price_exc_vat', 'Current Electricity price excluding VAT')
CONSUMPTION_YESTERDAY = Gauge('electricity_consumption_yesterday', 'Yesterdays Energy Use.')


# Decorate function with metric.


def set_current_price(time, unit_rates):
    price = cur_price(data=unit_rates,
                      time=time.isoformat() + "Z")  # Octopus adds "Z" to end of ISO Time, python doesn't
    CURRENT_PRICE_INC_VAT.set(price['value_inc_vat'])
    CURRENT_PRICE_EXC_VAT.set(price['value_exc_vat'])


def set_consumption(consumption):
    CONSUMPTION_YESTERDAY.set(consumption[1]['consumption'])  # Yesterdays value is second result on first page.


if __name__ == '__main__':
    path = join(dirname(__file__), '.env')
    logging.basicConfig(filename='boinc{date}.log'.format(date=datetime.now().date()), format='%(asctime)s %(message)s',
                        level=logging.DEBUG)
    load_dotenv(path)

    # Start up the server to expose the metrics.
    start_http_server(8000)

    while True:
        rates = fetch_unit_rates()['results']
        consumption = fetch_consumption()['results']
        now_utc = datetime.utcnow()

        if (30, 0) in now_utc.minute:
            set_current_price(rd_utc, rates)
            set_consumption(consumption)
            time.sleep(30)
