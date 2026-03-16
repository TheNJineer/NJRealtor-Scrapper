import sys
import argparse
from ncjar_core.ncjar.NJRParser import NJRParser


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
    obj = NJRParser(testing=bool_conversion[args.testing])
    results = obj.main()

    print(' ==== DATA EXTRACTION FROM KAFKA IS COMPLETE ==== ')
    sys.exit(0)
