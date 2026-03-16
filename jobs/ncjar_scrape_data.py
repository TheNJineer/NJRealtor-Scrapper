import sys
import argparse
from ncjar_core.ncjar.NJRScrapper import Scraper


def parse_args():

    parser = argparse.ArgumentParser(description="Create necessary Kafka topics if they aren't available")
    parser.add_argument("--testing", required=True)

    # return parser.parse_args(["--testing", "false"])
    # return parser.parse_args(["--testing", "true"])
    return parser.parse_args()


if __name__ == '__main__':

    bool_conversion = {
        'true': True,
        'false': False
    }

    args = parse_args()
    obj = Scraper(testing=bool_conversion[args.testing])
    results = obj.main()

    print(f' ==== NCJAR SCRAPING HAS BEEN COMPLETED ==== ')
    sys.exit(0)
