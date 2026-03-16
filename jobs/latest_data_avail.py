import sys
from ncjar.utility_func import check_pipeline_metadata
from ncjar.NJRScrapper import Scraper


if __name__ == '__main__':

    obj = Scraper()
    results = obj.airflow_status_check()

    print(f' ==== NCJAR Latest Results: {results} ==== ')
    # This current arg syntax doesn't support the current function. Update before using
    check_pipeline_metadata('ncjar_pipeline', None, "latest_data", results)
    sys.exit(0)
