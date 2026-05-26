import requests
import os
from pathlib import Path
from os.path import join, dirname
from dotenv import load_dotenv
import json
import datetime
from sys import platform, argv
import logging

retries = 0


def fetch():
    """GET current tariff data from Octopus API"""
    url = "{url}/v1/products/{prod_code}/electricity-tariffs/{tariff}/standard-unit-rates".format(
        url=os.getenv("BASE_URL"),
        prod_code=os.getenv("PRODUCT_CODE"),
        tariff=os.getenv("TARIFF"),
    )
    logging.info("GET URL " + url)
    key = os.getenv("KEY")
    response = requests.get(url, headers={"X-RapidAPI-Key": key})
    if response.status_code == 200:  # if success, continue. If not, die.
        return json.loads(response.text)
    else:
        logging.error(
            "Unable to get rates. Response code {code}. Exiting".format(
                code=str(response.status_code)
            )
        )
        exit(0)


def round_down(timestamp):  
    """Round time down to nearest half-hour"""
    if timestamp.minute >= 30:
        return timestamp.replace(second=0, microsecond=0, minute=30)
    else:
        return timestamp.replace(second=0, microsecond=0, minute=0)


def round_up(timestamp):  
    """ Round time up to nearest half-hour (almost to bodge around midnight +1 crashing) """
    if timestamp.minute >= 30:
        return timestamp.replace(second=59, microsecond=0, minute=59)
    else:
        return timestamp.replace(second=0, microsecond=0, minute=30)


def cur_price(data, time):
    """Fetch current price from data and return applicable_values."""
    result = {"value_exc_vat":101.00,"value_inc_vat":101.00,"valid_from":"2020-01-01T00:00:00Z","valid_to":"2020-01-01T00:00:30Z","payment_method":None} # default value always higher than possible on Agile so will not start BOINC if it cannot find data
    for entry in data:
        print(entry)
        timestamp = datetime.datetime.fromisoformat(entry["valid_from"])
        if timestamp == time:
            logging.info(
                "Located: {valid_from} at price {price}".format(
                    valid_from=timestamp, price=entry
                )
            )
            result = entry
            break
    print("Selected result", result)
    return result


def boinc(price, runtime):
    """
    Launches BOINC with the given runtime in automatic mode if the price is leq the threshold.
    Stops BOINC by setting runmode to never if price is greater than threshold.
    """
    threshold = float(os.getenv("PRICE_THRESHOLD"))
    boinc_path = "."

    if platform == "linux" or platform == "linux2":
        boinc_path = os.getenv("LINUX_BOINC")
    elif platform == "darwin":
        boinc_path = os.getenv("MAC_BOINC")
    elif platform == "win32":
        boinc_path = os.getenv("WIN_BOINC")
    else:
        logging.error("Unable to determine platform")

    if price <= threshold:
        logging.info(
            "Price {price} leq than threshold {th}".format(
                price=str(price), th=str(threshold)
            )
        )
        os.system(
            boinc_path + " --set_run_mode auto {run_t}".format(run_t=str(runtime))
        )
    else:
        logging.info(
            "Price {price} is greater than threshold {th}".format(
                price=str(price), th=str(threshold)
            )
        )
        os.system(boinc_path + " --set_run_mode never")


def main():
    envfile_path = argv[1]
    path = Path(envfile_path)
    logging.basicConfig(
        filename="boinc{date}.log".format(
            date=datetime.datetime.now(tz=datetime.UTC).date()
        ),
        format="%(asctime)s %(message)s",
        level=logging.DEBUG,
    )
    load_dotenv(path)
    now = datetime.datetime.now(tz=datetime.UTC)

    round_down_time = round_down(timestamp=now)
    round_up_time = round_up(timestamp=now)

    logging.info("Rounded time " + str(round_down_time))

    price_data = fetch()["results"]

    price_now = cur_price(data=price_data, time=round_down_time)
    logging.info("Current price {cp}".format(cp=str(price_now)))
    time_diff = (round_up_time - now).seconds
    logging.info("Time client will be run for: {time} ".format(time=str(time_diff)))
    boinc(price=price_now["value_inc_vat"], runtime=time_diff)


if __name__ == "__main__":
    main()
