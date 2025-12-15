import os
import pandas as pd
import re
import pypdf
from datetime import datetime, timedelta
from tqdm import tqdm
from io import BytesIO
from tabulate import tabulate
from utility_func import create_sql_engine, create_kafka_consumer
from kafka.errors import KafkaTimeoutError, RebalanceInProgressError
from sqlalchemy.exc import DataError, IntegrityError
# from psycopg2.errors import SyntaxError
from sqlalchemy.exc import DatabaseError


class NJRParser:

    def __init__(self):
        self.engine = self.engine = create_sql_engine('nj_realtor_data')
        self.consumer = create_kafka_consumer('njrdata_consumer', 'ncjar_data_consumer')
        self.raw_data = NJRParser.create_data_dict()

    @staticmethod
    def fake_consume_data():
        """
        Fake consumer
        :return:
        """

        base_path = 'C:\\Users\\jibreel.q.hameed.AC\\OneDrive - US Army\\PycharmProjects\\pythonProject\\NJR Scrapper'
        pdf_list = []
        key_list = []

        for idx, file in enumerate(os.listdir(base_path)):
            if os.path.isfile(os.path.join(base_path, file)):
                if file.endswith('.pdf'):
                    pdf_list.append(os.path.join(base_path, file))
                    key_list.append(file)

            if idx == 49:
                break

        return pdf_list, key_list

    def bytes2text(self, pdf_list, key_list):
        """
        Extracts the real estate data from that pdf bytes and stores as string text in list for later processing

        :param pdf_list:
        :param key_list:
        :return: None
        """
        new_pdf_list = []
        # base_path = 'C:\\Users\\Omar\\Desktop\\Python Temp Folder'

        # Modify once Kafka is implemented. Will loop through pdf_list instead of key_list
        # Also will not be using os. Will loop through list of byte objects
        for _, pdf, key in zip(tqdm(range(len(pdf_list)), desc='PDFs', colour='green', position=1), pdf_list, key_list):
            try:
                if isinstance(pdf, str):
                    if os.path.exists(pdf):
                        with open(pdf, 'rb') as reader:
                            pdfread = pypdf.PdfReader(reader)
                            page = pdfread.pages[0]
                            target = page.extract_text()
                            new_pdf_list.append(target)

                elif isinstance(pdf, bytes):
                    # Expects a file-like object which BytesIO creates
                    pdfread = pypdf.PdfReader(BytesIO(pdf))
                    page = pdfread.pages[0]
                    target = page.extract_text()
                    new_pdf_list.append(target)

                else:
                    new_pdf_list.append(None)

            except pypdf._reader.EmptyFileError:
                print(f'The file {key} does not have data. File possibly corrupted')
                new_pdf_list.append(None)

        print(f' ==== PDF LIST LEN: {len(new_pdf_list)}')
        return new_pdf_list

    def consume_data(self):

        pdf_list = []
        keys_list = []
        start_time = datetime.now()
        progress_bar = tqdm(range(len(pdf_list)), desc='New Data Found', colour='green', position=1)

        while True:

            try:
                new_data = self.consumer.poll(timeout_ms=4000)

                if new_data:
                    sub_list, key_list = NJRParser.extract_messages(new_data)

                    if isinstance(sub_list, list):
                        pdf_list.extend(sub_list)
                        keys_list.extend(key_list)
                        progress_bar.update(len(sub_list))
                    else:
                        pass

                elif ((datetime.now() - start_time) < timedelta(minutes=12)) and len(pdf_list) == 0:

                    print(' === WAITING FOR NEW DATA === ')
                    print(f' ==== CURRENT TIME LAPSE: {datetime.now() - start_time} ====')
                    continue

                elif ((datetime.now() - start_time) < timedelta(minutes=12)) and len(pdf_list) > 0:
                    # self.consumer.commit()
                    print(' ==== NEW DATA RETURNED ==== ')
                    print(f' ==== pdf list len: {len(pdf_list)} ==== ')
                    return pdf_list, keys_list

                else:
                    print(' === NO NEW DATA. KAFKA DATA CONSUMPTION COMPLETE === ')
                    return None, None

            except ValueError:
                pass

    @staticmethod
    def create_data_dict():

        data_dict = {
            'municipality': [],
            'county': [],
            'quarter': [],
            'month_': [],
            'year_': [],
            'new_listings': [],
            'new_listings_pcyoy': [],
            'closed_sales': [],
            'closed_sales_pcyoy': [],
            'dom': [],
            'dom_pcyoy': [],
            'median_sales_price': [],
            'median_sales_price_pcyoy': [],
            'polpr': [],
            'polpr_pcyoy': [],
            'inventory': [],
            'inventory_pcyoy': [],
            'months_of_supply': [],
            'mos_pcyoy': []
        }

        return data_dict

    def data_na(self, town, month, year):
        """
        UPDATE AND DELETE THE FY PORTION

        Staticmethod which assigns default values of 0, 0.0 and N/A to variables used in the extraction function
        for real estate pdfs which were found to have corrupted data
        :param town: str variable of the name of the town
        :param month: str variable of the month of the target data
        :param year: str variable of the year of the target data

        :return: None
        """

        self.raw_data['month_'].append(month)
        self.raw_data['quarter'].append(NJRParser.find_quarter(month))
        self.raw_data['year_'].append(year)
        self.raw_data['municipality'].append(town)
        self.raw_data['county'].append('N.A')

        for category in self.raw_data.keys():
            if category in ['municipality', 'county', 'year_', 'quarter', 'month_']:
                continue
            elif '_pcyoy' not in category:
                self.raw_data[category].append(0)
            else:
                self.raw_data[category].append(0.0)

    @staticmethod
    def extract_messages(new_messages):

        sub_list = []
        key_list = []

        for partition_obj, messages_list in new_messages.items():

            for record in messages_list:

                sub_list.append(record.value)
                if record.key != 'null':
                    key_list.append(record.key)
                else:
                    key_list.append(None)

        if len(sub_list) > 0:
            return sub_list, key_list

        else:
            return None, None

    @staticmethod
    def find_closed_sales(pdf_text):
        """
        :param pdf_text:
        :return:
        """

        closed_sales_pattern = re.compile(
            r'Closed\sSales\s(\d{0,3}?)\s(\d{0,3}?)\s(0.0%|--|[+-]\s\d{0,3}?.\d{0,1}?%)'
            r'\s(\d{0,3}?)\s(\d{0,3}?)\s(0.0%|--|[+-]\s\d{0,3}?.\d{0,1}?%)')
        closed_sales_search = list(closed_sales_pattern.findall(pdf_text))
        closed_sales_current = int(closed_sales_search[0][1])
        closed_sales_pc = closed_sales_search[0][2].split(' ')
        closed_sales_per_change = ''.join(closed_sales_pc).rstrip('%')
        if '+' in closed_sales_per_change:
            closed_sales_per_change.lstrip('+')
            closed_sales_per_change = round(float(closed_sales_per_change) / 100, 3)
        elif '--' in closed_sales_per_change:
            closed_sales_per_change = 0.0
        else:
            closed_sales_per_change = round(float(closed_sales_per_change) / 100, 3)

        return closed_sales_current, closed_sales_per_change

    @staticmethod
    def find_county(pdftext):
        """

        :return: county name
        """

        county_pattern = re.compile(r'(Atlantic|Bergen|Burlington|Camden|Cape May|Cumberland|Essex|'
                                    r'Gloucester|Hudson|Hunterdon|Mercer|Middlesex|Monmouth|Morris|Ocean|'
                                    r'Passaic|Salem|Somerset|Sussex|Union|Warren) County')

        found_county = county_pattern.search(pdftext).group()

        return found_county

    @staticmethod
    def find_dom(pdf_text):
        """
        :param pdf_text:
        :return:
        """

        dom_pattern = re.compile(
            r'Days\son\sMarket\sUntil\sSale\s(\d{0,3}?)\s(\d{0,3}?)\s'
            r'(0.0%|--|[+-]\s\d{0,3}?.\d{0,1}?%)\s(\d{0,3}?)\s(\d{0,3}?)\s(0.0%|--|[+-]\s\d{0,3}?.\d{0,1}?%)')
        dom_search = list(dom_pattern.findall(pdf_text))
        dom_current = int(dom_search[0][1])
        dom_pc = dom_search[0][2].split(' ')
        dom_per_change = ''.join(dom_pc).rstrip('%')
        if '+' in dom_per_change:
            dom_per_change.lstrip('+')
            dom_per_change = round(float(dom_per_change) / 100, 3)
        elif '--' in dom_per_change:
            dom_per_change = 0.0
        else:
            dom_per_change = round(float(dom_per_change) / 100, 3)

        return dom_current, dom_per_change

    @staticmethod
    def find_inventory(pdf_text):
        """
        :param pdf_text:
        :return:
        """

        inventory_pattern = re.compile(
            r'Inventory\sof\sHomes\sfor\sSale\s(--|\d{0,3}?)\s(--|\d{0,3}?)\s(0.0%|--|[+-]\s\d{1,3}?.\d{1}%)'
            r'\s(--|\d{0,3}?)\s(--|\d{0,3}?)\s(0.0%|--|[+-]\s\d{1,3}?.\d{1}%)')
        inventory_search = list(inventory_pattern.findall(pdf_text))
        inventory_current = inventory_search[0][1]
        if inventory_current != '--':
            inventory_current = int(inventory_current)
        inventory_pc = inventory_search[0][2].split(' ')
        inventory_per_change = ''.join(inventory_pc).rstrip('%')
        if '+' in inventory_per_change:
            inventory_per_change.lstrip('+')
            inventory_per_change = round(float(inventory_per_change) / 100, 3)
        elif '--' in inventory_per_change:
            inventory_per_change = 0.0
        else:
            inventory_per_change = round(float(inventory_per_change) / 100, 3)

        return inventory_current, inventory_per_change

    @staticmethod
    def find_key_metrics(pdf_text):
        """

        :param pdf_text:
        :return:
        """

        key_metrics_basic_pattern = re.compile(
            r'Key\sMetrics\s(\d{4})\s(\d{4})\sPercent\sChange\sThru'
            r'\s\d{1,2}?-\d{4}\sThru\s\d{1,2}?-\d{4}\sPercent\sChange')
        km_search = list(key_metrics_basic_pattern.findall(pdf_text))

        return km_search[0][1]

    @staticmethod
    def find_median_sales(pdf_text):
        """
        :param pdf_text:
        :return:
        """

        median_sales_pattern = re.compile(
            r'Median\sSales\sPrice\*\s(\$\d{1}|\$\d{0,3}?,?\d{0,3}?,\d{1,3})\s(\$\d{1}|\$\d{0,3}?,?\d{0,3}?,\d{1,3})'
            r'\s(0.0%|--|[+-]\s\d{1,3}?.\d{1}%)\s(\$\d{1}|\$\d{0,3}?,?\d{0,3}?,\d{1,3})'
            r'\s(\$\d{1}|\$\d{0,3}?,?\d{0,3}?,\d{1,3})\s(0.0%|--|[+-]\s\d{1,3}?.\d{1}%)')
        median_sales_search = list(median_sales_pattern.findall(pdf_text))
        median_sales_current = median_sales_search[0][1]
        median_sales_current = int("".join(median_sales_current.split(',')).lstrip('$'))
        median_sales_pc = median_sales_search[0][2].split(' ')
        median_sales_per_change = ''.join(median_sales_pc).rstrip('%')
        if '+' in median_sales_per_change:
            median_sales_per_change.lstrip('+')
            median_sales_per_change = round(float(median_sales_per_change) / 100, 3)
        elif '--' in median_sales_per_change:
            median_sales_per_change = 0.0
        else:
            median_sales_per_change = round(float(median_sales_per_change) / 100, 3)

        return median_sales_current, median_sales_per_change

    @staticmethod
    def find_month(pdf_text):
        """

        :param pdf_text:
        :return:
        """
        # print(pdf_text)
        month_pattern = re.compile(
            r'(January|February|March|April|May|June|July|August|September|October|November|December)'
            r'\s?Year\s?to\s?Date\s?Single\s?Family')

        return month_pattern.search(pdf_text).group(1)

    @staticmethod
    def find_new_listings(pdf_text):
        """
        :param pdf_text:
        :return:
        """

        new_listings_pattern = re.compile(
            r'New\sListings\s(\d{0,3}?)\s(\d{0,3}?)\s(0.0%|--|[+-]\s\d{0,3}?.\d{0,1}?%)'
            r'\s(\d{0,3}?)\s(\d{0,3}?)\s(0.0%|--|[+-]\s\d{0,3}?.\d{0,1}?%)')
        new_listing_search = list(new_listings_pattern.findall(pdf_text))
        new_listings_current = int(new_listing_search[0][1])
        new_listings_pc = str(new_listing_search[0][2]).split(' ')
        new_listings_per_change = ''.join(new_listings_pc).rstrip('%')
        if '+' in new_listings_per_change:
            new_listings_per_change.lstrip('+')
            new_listings_per_change = round(float(new_listings_per_change) / 100, 3)
        elif '--' in new_listings_per_change:
            new_listings_per_change = 0.0
        else:
            new_listings_per_change = round(float(new_listings_per_change) / 100, 3)

        return new_listings_current, new_listings_per_change

    @staticmethod
    def find_percent_lpr(pdf_text):
        """
        :param pdf_text:
        :return:
        """

        percent_lpr_pattern = re.compile(
            r'Percent\sof\sList\sPrice\sReceived\*\s(\d{1,3}?.\d{1}%)\s(\d{1,3}?.\d{1}%)\s(0.0%|--|[+-]'
            r'\s\d{1,3}?.\d{1}%)\s(\d{1,3}?.\d{1}%)\s(\d{1,3}?.\d{1}%)\s(0.0%|--|[+-]\s\d{1,3}?.\d{1}%)')
        percent_lpr_search = list(percent_lpr_pattern.findall(pdf_text))
        # Divide this by 100 and figure out how to format these to show the percent sign
        percent_lpr_current = float(percent_lpr_search[0][1].rstrip('%'))
        percent_lpr_pc = percent_lpr_search[0][2].split(' ')
        percent_lpr_per_change = ''.join(percent_lpr_pc).rstrip('%')
        if '+' in percent_lpr_per_change:
            percent_lpr_per_change.lstrip('+')
            percent_lpr_per_change = round(float(percent_lpr_per_change) / 100, 3)
        elif '--' in percent_lpr_per_change:
            percent_lpr_per_change = 0.0
        else:
            percent_lpr_per_change = round(float(percent_lpr_per_change) / 100, 3)

        return percent_lpr_current, percent_lpr_per_change

    @staticmethod
    def find_quarter(month):
        """

        :param month:
        :return:
        """
        if month in ['January', 'February', 'March']:
            return 1
        elif month in ['April', 'May', 'June']:
            return 2
        elif month in ['July', 'August', 'September']:
            return 3
        elif month in ['October', 'November', 'December']:
            return 4

    @staticmethod
    def find_supply(pdf_text):
        """
        :param pdf_text:
        :return:
        """

        supply_pattern = re.compile(
            r'Months\sSupply\sof\sInventory\s(--|\d{1,2}?.\d{1})\s(--|\d{1,2}?.\d{1})\s(0.0%|--|[+-]\s\d{1,3}?.\d{1}%)'
            r'\s(--|\d{1,2}?.\d{1})\s(--|\d{1,2}?.\d{1})\s(0.0%|--|[+-]\s\d{1,3}?.\d{1}%)')
        supply_search = list(supply_pattern.findall(pdf_text))
        supply_current = supply_search[0][1]
        if supply_current != '--':
            supply_current = float(supply_current)
        supply_pc = supply_search[0][2].split(' ')
        supply_per_change = ''.join(supply_pc).rstrip('%')
        if '+' in supply_per_change:
            supply_per_change.lstrip('+')
            supply_per_change = round(float(supply_per_change) / 100, 3)
        elif '--' in supply_per_change:
            supply_per_change = 0.0
        else:
            supply_per_change = round(float(supply_per_change) / 100, 3)

        return supply_current, supply_per_change

    def good_data(self, city, data, information):

        month = None
        data_dict = {
            'municipality': city,
            'county': NJRParser.find_county,
            'month_': NJRParser.find_month,
            'quarter': NJRParser.find_quarter,
            'year_': NJRParser.find_key_metrics,
            'new_listings': NJRParser.find_new_listings,
            'closed_sales': NJRParser.find_closed_sales,
            'dom': NJRParser.find_dom,
            'median_sales_price': NJRParser.find_median_sales,
            'polpr': NJRParser.find_percent_lpr,
            'inventory': NJRParser.find_inventory,
            'months_of_supply': NJRParser.find_supply,
        }

        for category, function in data_dict.items():
            if category == 'municipality':
                self.raw_data[category].append(function)
            elif category == 'month_':
                month = function(information)
                self.raw_data[category].append(month)
            elif category == 'quarter':
                self.raw_data[category].append(function(month))
            elif category == 'county':
                self.raw_data[category].append(function(information))
            elif category == 'year_':
                self.raw_data[category].append(function(data))
            else:
                current_data, yoy_data = function(data)
                self.raw_data[category].append(current_data)
                if category == 'months_of_supply':
                    self.raw_data[f'mos_pcyoy'].append(yoy_data)
                else:
                    self.raw_data[f'{category}_pcyoy'].append(yoy_data)

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

        return int(month_dict[month])

    def pandas2sql(self):
        """
        UPDATE

        :return:
        """

        table_name = 'nj_realtor_basic'
        true_data_len = len(self.raw_data['municipality'])

        try:
            for key in self.raw_data.keys():
                assert len(self.raw_data[key]) == true_data_len, f'==== INCORRECT DATA LENGTH: {key} ==== '

            db = pd.DataFrame(self.raw_data)
            db.drop_duplicates(subset=['municipality', 'month_', 'year_'], keep='first', inplace=True, ignore_index=True)
            db['month_'] = db['month_'].apply(NJRParser.month2num)
            db['year_'] = db['year_'].astype('int64')
            db['polpr'] = db['polpr'] / 100.0

            if not pd.read_sql_table(table_name, self.engine.raw_connection()).empty:
                db.to_sql(table_name, self.engine.raw_connection(), if_exists='append', chunksize=1000, index=False)
            # print(tabulate(db[list(db.columns)[0:11]], headers=list(db.columns)[0:11]))
            # print(tabulate(db[list(db.columns)[11:]], headers=list(db.columns)[11:]))

            print(f' ==== NJ REALTOR DATA HAS BEEN SAVED TO {table_name} IN POSTGRESQL ==== ')

        except AssertionError as e:
            print(f'{e}')
            raise AssertionError

    @staticmethod
    def parse_pdfname(pdf_name):
        """

        :param pdf_name:
        :return:
        """

        info = pdf_name.rstrip('.pdf').split(' ')
        town_directory = info[0:len(info) - 2]
        month = info[-2]
        year = info[-1]

        if len(town_directory) > 2:
            if 'County' in town_directory:
                # This means the city name is a duplicate and needs to have the county distinguished
                county = ' '.join(town_directory[-2:])
                town = ' '.join(town_directory[0:(town_directory.index('County') - 1)])
            else:
                town = ' '.join(town_directory)
                county = None
        else:
            town = ' '.join(town_directory)
            county = None

        return town.lstrip('"'), county, month, year

    def prepare_data(self, pdf_list, key_list):

        for _, pdf, key in zip(tqdm(range(len(pdf_list)), desc='PDFs', colour='green', position=1), pdf_list, key_list):

            town, county, month, year = NJRParser.parse_pdfname(key)

            if pdf is not None:
                lines = pdf.split('\n')
                data = '\n'.join(lines[:24])
                info = '\n'.join(lines[24:])

                self.good_data(town, data, info)

            else:
                print(f' ==== DATA FROM {key} POSSIBLY CORRUPTED ==== ')
                self.data_na(town, month, year)

    def main(self):

        print(' ==== EXTRACTING DATA FROM KAFKA ==== ')
        self.consumer.subscribe(['njrdata'])

        while True:
            # pdf_list, key_list = self.fake_consume_data()
            pdf_list, key_list = self.consume_data()

            if pdf_list is not None:
                print(' ==== TRANSFORMING KAFKA DATA INTO STRING TEXT ==== ')
                text_data_list = self.bytes2text(pdf_list, key_list)
                print(' ==== SCRAPPING TEXT DATA ==== ')
                self.prepare_data(text_data_list, key_list)
                # print(' ==== TEST CHECKPOINT: SAVING DATA ==== ')
                print(' ==== SAVING DATA ==== ')
                self.pandas2sql()
            else:
                break

        print(' ==== DATA EXTRACTION FROM KAFKA IS COMPLETE ==== ')
        self.consumer.close()


# if __name__ == '__main__':
#
#     obj = NJRParser()
#     obj.main()

