import os
from dotenv import load_dotenv
from utility_func import create_sql_engine, create_kafka_producer, logger_decorator
from itertools import product
from tqdm.auto import trange
import datetime
from datetime import datetime, date, timedelta
import logging
import requests
import re
import time
import pandas as pd
from bs4 import BeautifulSoup
from sqlalchemy.exc import ProgrammingError
from requests.exceptions import RequestException


class Scraper:

    def __init__(self, testing=False):
        self.counties = []
        self.towns = []
        self.testing = testing
        self.session = None
        self.producer = create_kafka_producer('njrscrapper_producer')
        self.engine = create_sql_engine('nj_realtor_data')
        self.event_log = Scraper.create_event_log()
        self.timeframe = {}
        self.run_number = None
        self.last_ran_month = None
        self.last_ran_year = None
        self.last_run_date = None
        self.last_municipality = None
        self.last_muni_year = None
        self.current_month = None
        self.current_year = None
        self.latest_nj_data()  # Observe what's the latest data available in the portal
        self.latest_event_data()  # Observe what's the latest scraping event to occur

    """ 
    ______________________________________________________________________________________________________________
                            Use this section to house the instance, class and static functions
    ______________________________________________________________________________________________________________
    """

    def airflow_status_check(self):

        current_data = self.current_month + ' ' + str(self.current_year)
        last_data = self.last_ran_month + ' ' + str(self.last_ran_year)

        try:
            assert current_data != last_data
            print(f' ==== LATEST DATA ACQUIRED: {last_data} ====')
            print(f' ==== LATEST DATA AVAILABLE: {current_data} ====')

            return True, current_data, last_data

        except AssertionError:

            return False, None, None

    # Function which scrapes the cities and counties from the njrealtor 10k state page
    def area_results(self, soup):
        """
        Function which accepts a BeautifulSoup object to then parse and find the cities
        and counties located in New Jersey
        :param soup: BeautifulSoup object
        :return: None
        """

        area_list = Scraper.city_cleaner(soup)

        for municipality in area_list:

            if municipality in ['Select an area...', 'Entire State', '\n']:
                continue
            else:
                if 'County' in municipality:
                    # There are multiple towns in different counties with the same name. Their county is attached
                    # and need to be separated from the target values
                    if '/' in municipality:
                        # Do not split the city name if it has '/' in it. It signifies that there is more than 1 city
                        # with that name and shows the county it belongs to
                        # newobj = newobj.split('/')
                        self.towns.append(municipality)
                    else:
                        self.counties.append(municipality)
                else:
                    self.towns.append(municipality)

    @staticmethod
    def city_cleaner(soup):

        municipality_pattern = re.compile(r'AreaList\["lmu"] = \[(.*)];')
        area = soup.find_all('script', {'type': 'text/javascript'})
        area_list = []

        for item in area:
            target_str = item.get_text()
            if 'var AreaList = {};' in target_str:
                municipality_list = municipality_pattern.search(target_str).group(1)

        municipality_list = municipality_list.split(',')

        for city in municipality_list:
            cleaned_city = ''.join([i for i in city if i != '"'])
            area_list.append(cleaned_city)

        return area_list

    @staticmethod
    def create_date_object(filename):

        date_pattern1 = re.compile(r'\d{4}-\d{2}-\d{2}')
        date_pattern2 = re.compile(r'(\w+\s\w+\s\d{2})\s.*')

        # Creates date object from date found in logger file
        if filename.endswith('.log'):
            metadata = os.stat(filename)
            target = time.strptime(time.ctime(metadata.st_mtime))

            year = target.tm_year
            month = target.tm_mon
            day = target.tm_mday

            return date(year, month, day)

        else:
            # Not an actual filename
            # This will create a datetime object based on a date string from the event log
            if date_pattern1.match(filename):
                return datetime.strptime(filename, '%Y-%m-%d')
            elif date_pattern2.match(filename):
                _, month, day = date_pattern2.search(filename).group(1).split(' ')
                return datetime(2024, int(Scraper.month2num(month)), int(day))

    @staticmethod
    def create_event_log():

        clean_log = {'number_of_runs': [],
                     'run_type': [],
                     'latest_available_data': [],
                     'run_time': [],
                     'run_date': [],
                     'days_between_update': [],
                     'expected_data': [0],
                     'data_produced': [0]}

        return clean_log

    def create_timeframe(self):

        months = {
            '01': 'January', '02': 'February',
            '03': 'March', '04': 'April',
            '05': 'May', '06': 'June',
            '07': 'July', '08': 'August',
            '09': 'September', '10': 'October',
            '11': 'November', '12': 'December'
            }

        current_month = Scraper.get_key(self.current_month, months)
        last_month = Scraper.get_key(self.last_ran_month, months)

        for year in range(self.last_ran_year, self.current_year + 1):
            self.timeframe.setdefault(year, {})

            for num, month in months.items():
                # Create a block for if the year equals the last ran year
                # Allows user not to create duplicate data for that year
                if year == self.last_ran_year and year == self.current_year:
                    if (int(num) <= int(last_month)) or (int(num) > int(current_month)):
                        continue
                    self.timeframe[year][num] = month
                elif year == self.last_ran_year:
                    if int(num) <= int(last_month):
                        continue
                    self.timeframe[year][num] = month
                elif self.last_ran_year < year < self.current_year:
                    self.timeframe[year][num] = month
                elif year == self.current_year:
                    if int(num) <= int(current_month):
                        self.timeframe[year][num] = month

    @staticmethod
    def create_session_object(s):

        load_dotenv("/opt/airflow/.env")
        pw = os.getenv("NJREALTOR_PASSWORD")
        user = os.getenv("NJREALTOR_USERNAME")
        login_page = 'https://www.njrealtor.com/login/?rd=10&passedURL=/goto/10k/'
        data_portal = 'https://www.njrealtor.com/ramco-api/web-services/login_POST.php'

        # payload sent during the HTTP POST
        payload1 = {'rd': '10',
                    'passedURL': '/goto/10k/',
                    'case': '',
                    'LoginEmail': user,
                    'LoginPassword': pw,
                    'LoginButton': 'Login'}

        s.get(login_page)  # Request to arrive at the log-in page
        s.post(data_portal, data=payload1)

        return s

    @staticmethod
    def create_url_and_key(**kwargs):
        """

        :return:
        """
        base_url = kwargs['base_url']
        month_var = kwargs['data'][3]
        month_num = kwargs['data'][2]
        year_var = kwargs['data'][1]
        city_list = kwargs['data'][0].split(' ')
        merged_city_name = ''.join(city_list)

        if '/' in city_list:
            merged_city_name = '%2F'.join(merged_city_name.split('/'))

        new_url = base_url + str(year_var) + '-' + month_num + '/x/' + merged_city_name
        key = " ".join([' '.join(city_list), month_var, str(year_var)])

        return new_url, key

    # Function which scrapes the current month of data available
    def current_data_avail(self, soup):
        """
        Function which accepts a BeautifulSoup object and scrapes the most recent data available to download
        and assigns the value to the current_data class variable
        :param soup: BeautifulSoup object
        :return: None
        """
        current_results = soup.find('select', id="lmuTime").children
        current_results = list(current_results)
        self.event_log['latest_available_data'].append(current_results[2].get_text())
        target = current_results[2].get_text().split(' ')

        return target[0], int(target[1])

    # Function which calculates the difference between the current download date and previous date
    # Use this to calculate the average amount of time it takes between new update periods
    def daysuntilupdate(self):
        """
        Method which returns a timedelta object that depicts the amount of days between
        the program's last run and current update

        :return: delta (timedelta object)
        """
        current = self.run_number
        previous = current - 1
        current_date = datetime.now()
        try:
            previous_date = datetime.strptime(str(self.last_run_date), "%Y-%m-%d %H:%M:%S+00:00")

        except ValueError:
            previous_date = Scraper.create_date_object(self.last_run_date)

        delta = current_date - previous_date

        return delta.days

    def download_pdf(self, **kwargs):
        """

        :return:
        """

        with self.session.get(kwargs['url'], params=kwargs['params'], stream=True) as reader:
            try:
                reader.raise_for_status()
                # Casting the bytes into a str type and slicing the first 20 characters to check if 'PDF' is in
                check_pdf = str(reader.content)[:20]

                if 'PDF' in check_pdf:
                    # print(f' ==== {kwargs['key']} PRODUCED TO KAFKA ==== ')
                    self.producer.send('njrdata', key=kwargs['key'], value=reader.content)
                    self.event_log['data_produced'][-1] += 1
                else:
                    kwargs['logger'].warning(f' ==== WARNING! {kwargs['key']} IS POSSIBLY A CORRUPTED FILE ==== ')

            except RequestException as e:
                kwargs['logger'].error(f' ==== REQUESTS ERROR: {kwargs['key']}\n{e}')

    # This is an instance method because I'm using a static method inside the function which may not be able
    def event_log_update(self, logger):
        """

        Instance method which updates the event log with runtime data of the most recent NJR10k download.
        Stores the type of downlaod/update which was run, the length of the download runtime, current date and
        length in time between the previous and current program runs
        :param logger: logger function which will return event log to the logger file
        :return: None
        """

        self.event_log['run_type'].append('NJR10k')
        self.event_log['number_of_runs'].append(self.run_number)
        self.event_log['run_date'].append(datetime.now())
        self.event_log['days_between_update'].append(self.daysuntilupdate())
        table_name = 'event_log'

        db = pd.DataFrame(self.event_log)
        db['run_date'] = pd.to_datetime(db['run_date'])
        db['run_time'] = pd.to_timedelta(db['run_time'])
        db['run_time'] = db['run_time'].astype('str')

        if not pd.read_sql_table(table_name, self.engine.raw_connection()).empty:
            db.to_sql(table_name, self.engine.raw_connection(), if_exists='append', index=False)

        # print(f'==== RUN NUMBER {self.run_number} HAS BEEN SAVED TO {table_name} in POSTGRESQL')
        logger.info(f'==== RUN NUMBER {self.run_number} HAS BEEN SAVED TO {table_name} in POSTGRESQL')

    @staticmethod
    def get_key(val, my_dict):
        for key, value in my_dict.items():
            if val == value:
                return key

        return "key doesn't exist"

    def latest_event_data(self):
        """
        - Accept the self.db_engine as a var since the classmethod cant directly access it
        - latest_event = pd.read_sql_table('event_log', engine=db_engine).loc[-1]
        - last_run_num = latest_event['Run Num']
        - last_date = latest_event['Latest Available Data'].split(' ')
        - Also have a try-except block that says if there's no data:
        return 1, 09, 2019
        :return:
        """

        event_query = """SELECT * FROM event_log
                        WHERE number_of_runs = (
                        SELECT MAX(number_of_runs) FROM event_log
                        )
                    """
        data_query = """SELECT * FROM nj_realtor_basic
                        ORDER BY year_ DESC, month_ DESC, county DESC, municipality DESC
                        LIMIT 1;
                    """

        try:
            latest_event = pd.read_sql_query(event_query, self.engine).iloc[-1]  # Use engine.raw_connection() with Airflow
            latest_data = pd.read_sql_query(data_query, self.engine).iloc[-1]  # Use engine.raw_connection() with Airflow
            last_ran_data = latest_event['latest_available_data'].split(' ')
            self.last_ran_month = last_ran_data[0]
            self.last_ran_year = int(last_ran_data[1])
            print(f' ==== LATEST NJ DATA SCRAPED: {self.last_ran_month} {self.last_ran_year} ==== ')
            self.last_run_date = latest_event['run_date']
            self.run_number = latest_event['number_of_runs'] + 1
            self.last_municipality = latest_data['municipality']
            self.last_muni_year = latest_data['year_']

            if self.last_municipality == 'White Twp' and self.last_muni_year == self.last_ran_year:
                print(f' ==== ALL DATA ACQUIRED DURING PREVIOUS RUN. RESETTING INSTANCE VARIABLES ==== ')
                self.last_municipality = None
                self.last_muni_year = None

        except (IndexError, ProgrammingError):
            # The table doesn't exist or exists but there's no data in it yet
            self.run_number = 1
            self.last_ran_month = 'September'
            self.last_ran_year = 2019
            self.last_run_date = None

    def latest_nj_data(self):
        """

        :return:
        """

        base_url = 'https://njar.stats.10kresearch.com/reports'

        with requests.Session() as session:
            print(' ==== CREATING TEMP SESSION TO SCRAPE LATEST NJ DATA ==== ')
            true_session = Scraper.create_session_object(session)
            response = true_session.get(base_url)

        if response.status_code == 200:
            print(' ==== LOGIN SUCCESSFUL === ')
            page_source = response.text
            soup = BeautifulSoup(page_source, 'html.parser')
            self.area_results(soup)

            self.current_month, self.current_year = self.current_data_avail(soup)
            print(' ==== CURRENT NJ DATA ACQUIRED ==== ')

        else:
            response.raise_for_status()

    @staticmethod
    def month2num(month):
        # Return the name of the month if digits are given or digits if the name is given
        month_dict = {
            'January': '01', 'February': '02',
            'March': '03', 'April': '04',
            'May': '05', 'June': '06',
            'July': '07', 'August': '08',
            'September': '09', 'October': '10',
            'November': '11', 'December': '12'
        }
        if month.isalpha():
            for name, value in month_dict.items():
                if month in name:
                    return value

        elif month.isdigit():

            for name, value in month_dict.items():
                if value == month:
                    return name

    def njr10k(self, **kwargs):
        """
        UPDATE
        Function which automatically downloads the pdfs from each city to get ready to scrape

        :return:
        """

        start_time = datetime.now()

        kwargs['base_url'] = 'http://njar.stats.10kresearch.com/docs/lmu/'
        kwargs['params'] = {'src': 'Page'}
        logger = kwargs['logger']
        first_year = list(self.timeframe.keys())[0]

        for year, months_dict in self.timeframe.items():
            kwargs['year'] = year
            kwargs['month_dict'] = months_dict

            # Script interruption and is continuing from where it stopped
            if year == first_year and year == self.last_muni_year and self.last_municipality is not None:
                town_index = self.towns.index(self.last_municipality)
                kwargs['municipalities'] = towns = self.towns[town_index + 1:]
            else:
                kwargs['municipalities'] = towns = self.towns

            data_len = len(list(product(towns, [year], months_dict.values())))
            self.event_log['expected_data'][-1] += data_len

            for idx, data in zip(trange(data_len, desc='Downloaded PDFs'), Scraper.value_generator(**kwargs)):
                kwargs['data'] = data
                kwargs['url'], kwargs['key'] = Scraper.create_url_and_key(**kwargs)
                self.download_pdf(**kwargs)

                if self.testing is True:
                    if idx == 30:
                        break

        logger.info('==== DOWNLOAD FOR TARGETED DATA HAS BEEN COMPLETED ====')

        end_time = datetime.now()
        self.event_log['run_time'].append(str(end_time - start_time))

    @staticmethod
    def value_generator(**kwargs):

        for num, month in kwargs['month_dict'].items():
            for m in kwargs['municipalities']:
                yield m, kwargs['year'], num, month

    @logger_decorator
    def main(self, **kwargs):

        logger = kwargs['logger']
        f_handler = kwargs['f_handler']
        c_handler = kwargs['c_handler']

        try:
            # Step 1a: Check if new data is available
            assert self.current_month != self.last_ran_month, ' ==== NO NEW REAL ESTATE DATA AVAILABLE ==== '
            logger.info(f' ==== NEW DATA AVAILABLE FOR {self.current_month + " " + str(self.current_year)} ==== ')

            with requests.Session() as session:
                # Enrich the session object with target website and user persistence
                self.session = Scraper.create_session_object(session)
                logger.info(' ==== CREATING THE TIMEFRAME FOR THE TARGETED DATA ==== ')
                self.create_timeframe()
                logger.info(' ==== STARTING THE DOWNLOAD FOR TARGETED DATA ==== ')
                self.njr10k(**kwargs)
                self.event_log_update(logger)

        except KeyboardInterrupt:
            print()
            print(' ==== KEYBOARD INTERRUPT ==== ')
        except AssertionError as ae:
            # Send message that says no new data is available
            # Tell airflow to try again tomorrow
            pass
        finally:
            logger.removeHandler(f_handler)
            logger.removeHandler(c_handler)
            logging.shutdown()
            self.producer.close()


# if __name__ == '__main__':
#
#     obj = Scraper()
#     obj.main()
#
#     print('Done')

