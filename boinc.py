import requests
import os
from os.path import join, dirname
from dotenv import load_dotenv
import json
from datetime import datetime
from sys import platform
import logging
retries = 0

def fetch():  # GET current tariff data from Octopus API
    url = "{url}/{prod_code}/electricity-tariffs/{tariff}/standard-unit-rates".format(url=os.getenv('BASE_URL'),
                                                                                      prod_code=os.getenv(
                                                                                          'PRODUCT_CODE'),
                                                                                      tariff=os.getenv('TARIFF'))
    logging.debug("GET URL " + url)
    key = os.getenv('KEY')
    response = requests.get(url, headers={
        "X-RapidAPI-Key": key
    })
    if response.status_code == 200:  # if success, continue. If not, die.
        return json.loads(response.text)
    else:
        logging.error("Unable to get rates. Response code {code}. Exiting".format(code=str(response.status_code)))
        exit(0)


def round_down(t):  # round time down to nearest half-hour
    if t.minute >= 30:
        return t.replace(second=0, microsecond=0, minute=30)
    else:
        return t.replace(second=0, microsecond=0, minute=0)


def round_up(t):  # round time up to nearest half-hour (almost to bodge around midnight +1 crashing)
    if t.minute >= 30:
        return t.replace(second=59, microsecond=0, minute=59)
    else:
        return t.replace(second=0, microsecond=0, minute=30)


def cur_price(data, time):
    result = 101.00  # default value always higher than possible on Agile so will not start BOINC if it cannot find data
    for a in data:
        if a['valid_from'] == time:
            logging.debug(
                "Located: {valid_from} at price {price}".format(valid_from=a['valid_from'], price=a['value_inc_vat']))
            result = a
            break

    return result


def boinc(price, runtime):
    threshold = float(os.getenv('PRICE_THRESHOLD'))
    boinc_path = "."

    if platform == "linux" or platform == "linux2":
        boinc_path = os.getenv('LINUX_BOINC')
    elif platform == "darwin":
        boinc_path = os.getenv('MAC_BOINC')
    elif platform == "win32":
        boinc_path = os.getenv('WIN_BOINC')
    else:
        logging.error("Unable to determine platform")

    if price <= threshold:
        logging.info("Price {price} less than threshold {th}".format(price=str(price), th=str(threshold)))
        os.system(boinc_path + " --set_run_mode auto {run_t}".format(run_t=str(runtime)))
    else:
        logging.info("Price {price} is greater than threshold {th}".format(price=str(price), th=str(threshold)))
        os.system(boinc_path + " --set_run_mode never")


def main():
    path = join(dirname(__file__), '.env')
    logging.basicConfig(filename='boinc{date}.log'.format(date=datetime.now().date()), format='%(asctime)s %(message)s',
                        level=logging.DEBUG)
    load_dotenv(path)
    now = datetime.utcnow()

    rd = round_down(t=now)
    ru = round_up(t=now)

    logging.debug("Rounded time " + str(rd))

    a = fetch()['results']

    price_now = cur_price(data=a, time=rd.isoformat() + "Z")  # Octopus adds "Z" to end of ISO Time, python doesn't
    logging.debug("Current price {cp}".format(cp=str(price_now['value_inc_vat'])))
    time_diff = (ru - now).seconds
    logging.debug("Time client will be run for: {time} ".format(time=str(time_diff)))
    boinc(price=price_now['value_inc_vat'], runtime=time_diff)


if __name__ == '__main__':
    main()
