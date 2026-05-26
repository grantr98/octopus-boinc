from prometheus_client import start_http_server, Summary, Gauge, Info
import random
import time

import requests
import os
from os.path import join, dirname
from dotenv import load_dotenv
import json
import datetime
from sys import platform, argv
import logging
from cachetools import cached, TTLCache
from pathlib import Path

from boinc import round_down,cur_price

@cached(cache=TTLCache(maxsize=2048, ttl=720))
def fetch_unit_rates():  # GET current tariff data from Octopus API
    url = "{url}/v1/products/{prod_code}/electricity-tariffs/{tariff}/standard-unit-rates".format(
        url=os.getenv("BASE_URL"),
        prod_code=os.getenv("PRODUCT_CODE"),
        tariff=os.getenv("TARIFF"),
    )
    logging.debug("GET URL " + url)

    response = requests.get(url)
    if response.status_code == 200:  # if success, continue. If not, die.
        return json.loads(response.text)
    else:
        logging.error(
            "Unable to get rates. Response code {code}. Exiting".format(
                code=str(response.status_code)
            )
        )
        exit(0)


@cached(cache=TTLCache(maxsize=2048, ttl=180))
def fetch_consumption():  # GET consumption data from Octopus API
    url = (
        "{url}/v1/electricity-meter-points/{mpan}/meters/{serial_number}/consumption/"
        "?group_by=day&page_size=2&order_by=-period".format(
            url=os.getenv("BASE_URL"),
            mpan=os.getenv("MPAN"),
            serial_number=os.getenv("ELEC_SERIAL_NUMBER"),
        )
    )
    logging.debug("GET URL " + url)
    key = os.getenv("KEY")
    response = requests.get(url=url, auth=(key, ""))
    if response.status_code == 200:  # if success, continue. If not, die.
        return json.loads(response.text)
    else:
        logging.error(
            "Unable to get rates. Response code {code}. Exiting".format(
                code=str(response.status_code)
            )
        )
        exit(0)


# Create a metric to track time spent and requests made.
CURRENT_PRICE_INC_VAT = Gauge(
    "current_electricity_price_inc_vat", "Current Electricity price including VAT"
)
CURRENT_PRICE_EXC_VAT = Gauge(
    "current_electricity_price_exc_vat", "Current Electricity price excluding VAT"
)
CONSUMPTION_YESTERDAY = Gauge(
    "electricity_consumption_yesterday", "Yesterdays Energy Use."
)


# Decorate function with metric.


def set_current_price(time, unit_rates):
    price = cur_price(
        data=unit_rates, time=time.isoformat()
    )  # Octopus adds "Z" to end of ISO Time, python doesn't
    CURRENT_PRICE_INC_VAT.set(price["value_inc_vat"])
    CURRENT_PRICE_EXC_VAT.set(price["value_exc_vat"])


def set_consumption(consumption):
    logging.debug(
        "Located: {valid_from} {data}".format(
            valid_from=consumption[0]["interval_start"], data=consumption[1]
        )
    )

    CONSUMPTION_YESTERDAY.set(consumption[1]["consumption"])


def fetch_rates_and_update(rd_utc):
    rates = fetch_unit_rates()["results"]
    consumption = fetch_consumption()["results"]
    set_current_price(rd_utc, rates)
    set_consumption(consumption)
    time.sleep(30)


if __name__ == "__main__":

    envfile_path = argv[1]
    path = Path(envfile_path)
    logging.basicConfig(
        handlers=[
            logging.FileHandler("boinc{date}.log".format(date=datetime.now().date())),
            logging.StreamHandler(),
        ],
        format="%(asctime)s %(message)s",
        level=logging.DEBUG,
    )

    load_dotenv(path)

    # Start up the server to expose the metrics.
    start_http_server(8000)
    now_utc = datetime.datetime.now(datetime.UTC)

    logging.debug(f"The time is {now_utc}, first boot:")
    rd_utc = round_down(timestamp=now_utc)  # Clamp time to nearest half hour.
    fetch_rates_and_update(rd_utc=rd_utc)

    while True:  # Now loop
        now_utc = datetime.datetime.now(datetime.UTC)

        if now_utc.minute == 30 or now_utc.minute == 0:  # If on the hour or half hour:
            logging.debug(f"The time is {now_utc}, updating:")
            rd_utc = round_down(timestamp=now_utc)  # Clamp time to nearest half hour.
            fetch_rates_and_update(rd_utc=rd_utc)

        time.sleep(60)
