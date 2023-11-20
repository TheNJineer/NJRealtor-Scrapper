import os
import winsound
import openpyxl
import PyPDF2
import shutil
import datetime
import enlighten
import logging
from os import strerror
import requests
from sys import path
import re
import time
import pandas as pd
from bs4 import BeautifulSoup
import pprint
import selenium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
# Allows us to interact with the Enter key and see search results
from selenium.webdriver.common.keys import Keys
# Allows Selenium to search for page elements By their attributes
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
# Next two imports set the program up for explicit waits so the document doesn't move to ther next step until the element is found
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
# Allows for Selenium to click a button
from selenium.webdriver.support.select import Select
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import ElementNotVisibleException
from selenium.common.exceptions import NoSuchElementException


class Scraper:

    current_data_avail = ''
    no_of_runs = 0
    event_log = {}

    def __init__(self):
        #Change the directory to store the temporary Selenium files to be processed
        os.chdir('C:\\Users\\Omar\\Desktop\\Selenium Temp Folder')
        #Regex patterns to find matches for the towns and counties in NJ. May not be needed anymore while using BeautifulSoup
        self.__counties_pattern = re.compile(r'<option value="(\w+)(\s\w+)?\sCounty">\w+(\s\w+)?\sCounty</option>')
        self.__towns_pattern = re.compile(r'<option value="(\w+\s\w+(\s\w+)?(\s\w+)?)">\w+\s\w+(\s\w+)?(\s\w+)?</option>')
        #Empty list to stored the found cities and counties
        self.__counties = []
        self.__towns = []
        #The years and months for the real estate data I'm looking for
        self.__years = ['2019', '2020', '2021', '2022', '2023']
        self.__months = {'01': 'January',
                         '02': 'February',
                         '03': 'March',
                         '04': 'April',
                         '05': 'May',
                         '06': 'June',
                         '07': 'July',
                         '08': 'August',
                         '09': 'September',
                         '10': 'October',
                         '11': 'November',
                         '12': 'December'
                         }
        #self.__last_run = '' This may not be needed anymore since the event_log class variable created to keep track of run times

    def get_us_pw(self, website):
        previous_wd = os.getcwd()
        os.chdir('F:\\Jibreel Hameed\\Kryptonite')
        wb = openpyxl.load_workbook('get_us_pw.xlsx')
        sheet = wb.active
        # website_col = list(sheet['A1' : 'A20'])
        # print(website_col)
        for i,n in enumerate(sheet['A0' : 'A20']):
            #print(i,n)
            for cell in n:
                if website == cell.value:
                    username = sheet['C' + str(i+1)].value
                    pw = sheet['D' + str(i+1)].value
                    #print(cell.value, username, pw)

        os.chdir(previous_wd)

        return username, pw


    def njr10k(self):

        logger = logging.getLogger("NJR10k")
        logger.setLevel(logging.DEBUG)
        # Create the FileHandler() and StreamHandler() loggers
        f_handler = logging.FileHandler('NJR10k.log')
        f_handler.setLevel(logging.DEBUG)
        c_handler = logging.StreamHandler()
        c_handler.setLevel(logging.INFO)
        # Create formatting for the loggers
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s',datefmt='%d-%b-%y %H:%M:%S')
        # Set the formatter for each handler
        f_handler.setFormatter(formatter)
        c_handler.setFormatter(formatter)
        logger.addHandler(f_handler)
        logger.addHandler(c_handler)

        possible_corrupted_files = []

        manager = enlighten.Manager()
        city_tracker = manager.counter(total = len(self.__towns), desc = f'City', unit = 'Cities')
        year_tracker = manager.counter(total = len(self.__years), desc = f'Year', unit = 'Years')


        base_url = 'http://njar.stats.10kresearch.com/docs/lmu/'

        with requests.Session() as session:
            # create a function/module which returns the njr10k inof
            username, pw = self.get_us_pw('NJRealtor')

            payload1 = {'rd': '10',
                        'passedURL': '/goto/10k/',
                        'case': '',
                        'LoginEmail': username,
                        'LoginPassword': pw,
                        'LoginButton': 'Login'}

            params = {'src': 'Page'}
            months = list(self.__months.keys())

            months_tracker = manager.counter(total=len(months), desc=f'Year:', unit='Months')

            url = 'https://www.njrealtor.com/login/?rd=10&passedURL=/goto/10k/'
            url2 = 'https://www.njrealtor.com/ramco-api/web-services/login_POST.php'

            response = session.get(url)
            r_post = session.post(url2, data=payload1)

            try:
                for i in range(len(self.__towns)):
                    time.sleep(0.1)
                    city_tracker.update()
                    city0 = i.split(' ')
                    city = ''.join(i.split(' '))
                    for y in self.__years:
                        time.sleep(0.1)
                        year_tracker.update()
                        if y == '2019':
                            months1 = months[8:13]
                            for m in months1:
                                time.sleep(0.1)
                                months_tracker.update()
                                url3 = base_url + y + '-' + m + '/x/' + city
                                new_filename = " ".join([city0[0], self.__months[m], y]) + ".pdf"
                                with session.get(url3, params=params, stream = True) as reader, open(new_filename, 'wb') as writer:
                                    for chunk in reader.iter_content(chunk_size=1000000):
                                        #check_pdf = chunk.content
                                        # print(check_pdf)
                                        # See the contents of the pdf to see if 'html' is metioned at all in it. If not, continue writing into new file
                                        # If not, add it to the possible_corrupted_files list
                                        #if 'DOCTYPE' not in check_pdf:
                                        writer.write(chunk)
                                        # elif 'DOCTYPE' in check_pdf:
                                        # possible_corrupted_files.append(new_filename)
                                        # Enter logger here

                        elif y != '2019':
                            for m in months:
                                time.sleep(0.1)
                                months_tracker.update()
                                url3 = base_url + y + '-' + m + '/x/' + city
                                new_filename = " ".join([city0[0], self.__months[m], y]) + ".pdf"
                                with session.get(url3, params=params, stream = True) as reader, open(new_filename, 'wb') as writer:
                                    for chunk in reader.iter_content(chunk_size=1000000):
                                        # check_pdf = chunk.content
                                        # print(check_pdf)
                                        # See the contents of the pdf to see if 'html' is metioned at all in it. If not, continue writing into new file
                                        # If not, add it to the possible_corrupted_files list
                                        # if 'DOCTYPE' not in check_pdf:
                                        writer.write(chunk)
                                        # elif 'DOCTYPE' in check_pdf:
                                        # possible_corrupted_files.append(new_filename)
                                        # Enter logger here
            except IOError as e:
                """An OS Error has occurred """
                logger.exception(f'IOError has Occurred: ', strerror(e.errno))

            except requests.exceptions.HTTPError as h:
                """An HTTP error occurred."""
                logger.exception(f'An HTTP has Occurred: {h}')

            except requests.exceptions.Timeout as t:
                """The request timed out.
    
                Catching this error will catch both
                :exc:`~requests.exceptions.ConnectTimeout` and
                :exc:`~requests.exceptions.ReadTimeout` errors.
                """
                logger.exception(f'The Request Has Timed Out: {t}')

            except requests.exceptions.InvalidURL as inv:
                """The URL provided was somehow invalid."""
                logger.exception(f'The URL Provided Was Invalid: {inv}')

            except requests.exceptions.RetryError as rte:
                    """Custom retries logic failed"""
                    logger.exception(f'Custom Retries Logic Failed: {rte}')

            except requests.exceptions.StreamConsumedError as sce:
                """The content for this response was already consumed."""
                logger.exception(f'The Content For This Response Was Already Consumed: {sce}')

            except requests.exceptions.ContentDecodingError as cde:
                """Failed to decode response content."""
                logger.exception(f'Failed to Decode Response Content: {cde}')

            except requests.exceptions.ChunkedEncodingError as cee:
                """The server declared chunked encoding but sent an invalid chunk."""
                logger.exception(f'Invalid Chunk Encoding: {cee}')

            else:
                #self.__last_run = datetime.datetime.now()
                if Scraper.no_of_runs == 0:
                    Scraper.event_log[Scraper.no_of_runs] = {'Latest Available Data' : self.current_data_avail,
                                                             'Run Date' : time.ctime(),
                                                             'Days Between Update' : 0 }
                elif Scraper.no_of_runs > 0:
                    Scraper.event_log[Scraper.no_of_runs] = {'Latest Available Data': self.current_data_avail,
                                                             'Run Date': time.ctime(),
                                                             'Days Between Update': self.daysuntilupdate(Scraper.no_of_runs)}
                Scraper.no_of_runs += 1
                #This is a very lengthy program so I'd like play a sound that signifies the process is done
                winsound.PlaySound('F:\\Python 2.0\\SoundFiles\\Victory.wav', 0)

        return possible_corrupted_files

    def daysuntilupdate(self, no_of_runs):
        current = Scraper.no_of_runs
        previous = current - 1
        current_date = datetime.datetime.now()
        previous_date = datetime.datetime.strptime(Scraper.event_log[previous]['Run Date'], "%a %b %d %H:%M:%S %Y")
        delta = current_date - previous_date

        return delta.days



    def area_results(self, soup):
        area = soup.find('select', id="lmuArea").children
        for obj in area:
            #see what form the area object comes in. If its a tuple, cast it into a list
            newobj = obj.get_text()
            if newobj in ['Select an area...', 'Entire State', '\n']:
                continue
            else:
                if 'County' in newobj:
                    #I believe there are multiple towns in different counties with the same name. Their county is attached
                    #and need to be seperated from the target values
                    if '/' in newobj:
                        newobj = newobj.split('/')
                        city = newobj[0]
                        self.__towns.append(city)
                    else:
                        #county = newobj.split('County')
                        #county[0].rstrip()
                        self.__counties.append(newobj)
                else:
                    self.__towns.append(newobj)

    def current_data_avail(self, soup):
        results = soup.find('select', id="lmuTime").children
        results = list(results)
        month_year = results[2].get_text()
        target = month_year.split(' ')
        year = target[1]
        month = target[0]
        if year not in self.__years:
            self.__years.append(year)
            main_dictionary[year] = {}

        Scraper.current_data_avail = month_year

    def create_dictionary(self, month, year):

        month = month[0:3]
        current_year = year
        previous_year = str(int(year) -1)
        main_dictionary[year] = {
            'City' : [],
            'County' : [],
            'New Listings ' + month + ' ' + previous_year : [],
            'New Listings ' + month + ' ' + current_year : [],
            'New Listings % Change ' + month + ' (YoY)': [],
            'Closed Sales ' + month + ' ' + previous_year: [],
            'Closed Sales ' + month + ' ' + current_year: [],
            'Closed Sales % Change ' + month + ' (YoY)': [],
            'Days on Market ' + month + ' ' + previous_year: [],
            'Days on Market ' + month + ' ' + current_year: [],
            'Days on Market % Change ' + month + ' (YoY)': [],
            'Median Sales Price ' + month + ' ' + previous_year: [],
            'Median Sales Price ' + month + ' ' + current_year: [],
            'Median Sales Price % Change ' + month + ' (YoY)': [],
            'Percent of Listing Price Received ' + month + ' ' + previous_year: [],
            'Percent of Listing Price Received ' + month + ' ' + current_year: [],
            'Percent of Listing Price Received % Change ' + month + ' (YoY)': [],
            'Inventory of Homes for Sale ' + month + ' ' + previous_year: [],
            'Inventory of Homes for Sale ' + month + ' ' + current_year: [],
            'Inventory of Homes for Sale % Change ' + month + ' (YoY)': [],
            'Months of Supply ' + month + ' ' + previous_year: [],
            'Months of Supply ' + month + ' ' + current_year: [],
            'Months of Supply % Change ' + month + ' (YoY)': []

        }

    def extract_re_data(self, pdfname):

        logger = logging.getLogger("Extract_Data")
        logger.setLevel(logging.DEBUG)
        # Create the FileHandler() and StreamHandler() loggers
        f_handler = logging.FileHandler('Extract_Data.log')
        f_handler.setLevel(logging.DEBUG)
        c_handler = logging.StreamHandler()
        c_handler.setLevel(logging.INFO)
        # Create formatting for the loggers
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s',datefmt='%d-%b-%y %H:%M:%S')
        # Set the formatter for each handler
        f_handler.setFormatter(formatter)
        c_handler.setFormatter(formatter)
        logger.addHandler(f_handler)
        logger.addHandler(c_handler)

        pdfread = PyPDF2.PdfReader(pdfname)
        page = pdfread.pages[0]
        target = page.extract_text()

        for i in self.__towns:
            if i in target:
                city = i
                break

        for c in self.__counties:
            if c in target:
                county = c
                break

        try:
            month_pattern = re.compile(r'(January|February|March|April|May|June|July|August|September|October|November|December)\sYear\sto\sDate\sSingle\sFamily')
            month = month_pattern.search(target)
            month = month.group()[0:3]
            key_metrics_pattern = re.compile(r'Key\sMetrics\s(\d{4})\s(\d{4})\sPercent\sChange\sThru\s\d{1,2}?-\d{4}')
            key_metrics_basic_pattern = re.compile(r'Key\sMetrics\s(\d{4})\s(\d{4})\sPercent\sChange')
            km_search = list(key_metrics_basic_pattern.findall(target))
            current_year = km_search[0][1]
            previous_year = str(int(current_year) - 1)
            new_listings_pattern = re.compile(r'New\sListings\s(-|\d{0,3}?)\s(-|\d{0,3}?)\s((\+|-)\s\d{1,3}?.\d{1}%)')
            new_listing_search = list(new_listings_pattern.findall(target))
            new_listings_current = int(new_listing_search[0][1])
            new_listings_previous = int(new_listing_search[0][0])
            new_listings_pc = str(new_listing_search[0][2]).split(' ')
            new_listings_per_change = ''.join([new_listings_pc[0], new_listings_pc[1]])
            closed_sales_pattern = re.compile(r'Closed\sSales\s(-|\d{0,3}?)\s(-|\d{0,3}?)\s((\+|-)\s\d{1,3}?.\d{1}%)')
            closed_sales_search = list(closed_sales_pattern.findall(target))
            closed_sales_current = int(closed_sales_search[0][1])
            closed_sales_previous = int(closed_sales_search[0][0])
            closed_sales_pc = closed_sales_search[0][2].split(' ')
            closed_sales_per_change = ''.join([closed_sales_pc[0], closed_sales_pc[1]])
            DOM_pattern = re.compile(r'Days\son\sMarket\sUntil\sSale\s(-|\d{0,3}?)\s(-|\d{0,3}?)\s((\+|-)\s\d{1,3}?.\d{1}%)')
            DOM_search = list(DOM_pattern.findall(target))
            DOM_current = int(DOM_search[0][1])
            DOM_previous = int(DOM_search[0][0])
            DOM_pc = DOM_search[0][2].split(' ')
            DOM_per_change = ''.join([DOM_pc[0], DOM_pc[1]])
            median_sales_pattern = re.compile(r'Median\sSales\sPrice\*\s(\$\d{1,3}?,\d{3})\s(\$\d{1,3}?,\d{3})\s((\+|-)\s\d{1,3}?.\d{1}%)')
            median_sales_search = list(median_sales_pattern.findall(target))
            median_sales_current = median_sales_search[0][1]
            median_sales_current = int("".join(median_sales_current.split(',')).lstrip('$'))
            median_sales_previous = median_sales_search[0][0]
            median_sales_previous = int("".join(median_sales_previous.split(',')).lstrip('$'))
            median_sales_pc = median_sales_search[0][2].split(' ')
            median_sales_per_change = ''.join([median_sales_pc[0], median_sales_pc[1]])
            percent_lpr_pattern = re.compile(r'Percent\sof\sList\sPrice\sReceived\*\s(\d{1,3}?.\d{1}%)\s(\d{1,3}?.\d{1}%)\s((\+|-)\s\d{1,3}?.\d{1}%)')
            percent_lpr_search = list(percent_lpr_pattern.findall(target))
            # Divide this by 100 and figure out how to format these to show the percent sign
            percent_lpr_current = float(percent_lpr_search[0][1].rstrip('%'))
            percent_lpr_previous = float(percent_lpr_search[0][0].rstrip('%'))
            percent_lpr_pc = percent_lpr_search[0][2].split(' ')
            percent_lpr_per_change = ''.join([percent_lpr_pc[0], percent_lpr_pc[1]])
            inventory_pattern = re.compile(r'Inventory\sof\sHomes\sfor\sSale\s(-|\d{0,3}?)\s(-|\d{0,3}?)\s((\+|-)\s\d{1,3}?.\d{1}%)')
            inventory_search = list(inventory_pattern.findall(target))
            inventory_current = int(inventory_search[0][1])
            inventory_previous = int(inventory_search[0][0])
            inventory_pc = inventory_search[0][2].split(' ')
            inventory_per_change = ''.join([inventory_pc[0], inventory_pc[1]])
            supply_pattern = re.compile(r'Months\sSupply\sof\sInventory\s(\d{1,2}?.\d{1})\s(\d{1,2}?.\d{1})\s((\+|-)\s\d{1,3}?.\d{1}%)')
            supply_search = list(supply_pattern.findall(target))
            supply_current = float(supply_search[0][1])
            supply_previous = float(supply_search[0][0])
            supply_pc = supply_search[0][2].split(' ')
            supply_per_change = ''.join([supply_pc[0], supply_pc[1]])

        except re.error as ree:
            logger.exception(f'A Regex Error Has Occurred: {ree}')

        else:

            if main_dictionary[current_year] == {}:
                self.create_dictionary(month, current_year)
                #Create key-value pairs for city and county
                main_dictionary[current_year]['City'].append(city)
                main_dictionary[current_year]['County'].append(county)
                main_dictionary[current_year]['New Listings ' + month + ' ' + previous_year].append(new_listings_previous)
                main_dictionary[current_year]['New Listings ' + month + ' ' + current_year].append(new_listings_current)
                main_dictionary[current_year]['New Listings % Change ' + month + ' (YoY)'].append(new_listings_per_change)
                main_dictionary[current_year]['Closed Sales ' + month + ' ' + previous_year].append(closed_sales_previous)
                main_dictionary[current_year]['Closed Sales ' + month + ' ' + current_year].append(closed_sales_current)
                main_dictionary[current_year]['Closed Sales % Change ' + month + ' (YoY)'].append(closed_sales_per_change)
                main_dictionary[current_year]['Days on Market ' + month + ' ' + previous_year].append(DOM_previous)
                main_dictionary[current_year]['Days on Market ' + month + ' ' + current_year].append(DOM_current)
                main_dictionary[current_year]['Days on Market % Change ' + month + ' (YoY)'].append(DOM_per_change)
                main_dictionary[current_year]['Median Sales Price ' + month + ' ' + previous_year].append(median_sales_previous)
                main_dictionary[current_year]['Median Sales Price ' + month + ' ' + current_year].append(median_sales_current)
                main_dictionary[current_year]['Median Sales Price % Change ' + month + ' (YoY)'].append(median_sales_per_change)
                main_dictionary[current_year]['Percent of Listing Price Received ' + month + ' ' + previous_year].append(percent_lpr_previous)
                main_dictionary[current_year]['Percent of Listing Price Received ' + month + ' ' + current_year].append(percent_lpr_current)
                main_dictionary[current_year]['Percent of Listing Price Received % Change ' + month + ' (YoY)'].append(percent_lpr_per_change)
                main_dictionary[current_year]['Inventory of Homes for Sale ' + month + ' ' + previous_year].append(inventory_previous)
                main_dictionary[current_year]['Inventory of Homes for Sale ' + month + ' ' + current_year].append(inventory_current)
                main_dictionary[current_year]['Inventory of Homes for Sale % Change ' + month + ' (YoY)'].append(inventory_per_change)
                main_dictionary[current_year]['Months of Supply ' + month + ' ' + previous_year].append(DOM_previous)
                main_dictionary[current_year]['Months of Supply ' + month + ' ' + current_year].append(DOM_current)
                main_dictionary[current_year]['Months of Supply % Change ' + month + ' (YoY)'].append(DOM_per_change)

            elif main_dictionary[current_year] != {} and city in main_dictionary[current_year]['City']:
                # Create key-value pairs for city and county
                main_dictionary[current_year].setdefault('New Listings ' + month + ' ' + previous_year, [])
                main_dictionary[current_year].setdefault('New Listings ' + month + ' ' + current_year, [])
                main_dictionary[current_year].setdefault('New Listings % Change ' + month + ' (YoY)', [])
                main_dictionary[current_year].setdefault('Closed Sales ' + month + ' ' + previous_year, [])
                main_dictionary[current_year].setdefault('Closed Sales ' + month + ' ' + current_year, [])
                main_dictionary[current_year].setdefault('Closed Sales % Change ' + month + ' (YoY)', [])
                main_dictionary[current_year].setdefault('Days on Market ' + month + ' ' + previous_year, [])
                main_dictionary[current_year].setdefault('Days on Market ' + month + ' ' + current_year, [])
                main_dictionary[current_year].setdefault('Days on Market % Change ' + month + ' (YoY)', [])
                main_dictionary[current_year].setdefault('Median Sales Price ' + month + ' ' + previous_year, [])
                main_dictionary[current_year].setdefault('Median Sales Price ' + month + ' ' + current_year, [])
                main_dictionary[current_year].setdefault('Median Sales Price % Change ' + month + ' (YoY)', [])
                main_dictionary[current_year].setdefault('Percent of Listing Price Received ' + month + ' ' + previous_year, [])
                main_dictionary[current_year].setdefault('Percent of Listing Price Received ' + month + ' ' + current_year, [])
                main_dictionary[current_year].setdefault('Percent of Listing Price Received % Change ' + month + ' (YoY)', [])
                main_dictionary[current_year].setdefault('Inventory of Homes for Sale ' + month + ' ' + previous_year, [])
                main_dictionary[current_year].setdefault('Inventory of Homes for Sale ' + month + ' ' + current_year, [])
                main_dictionary[current_year].setdefault('Inventory of Homes for Sale % Change ' + month + ' (YoY)', [])
                main_dictionary[current_year].setdefault('Months of Supply ' + month + ' ' + previous_year,[])
                main_dictionary[current_year].setdefault('Months of Supply ' + month + ' ' + current_year,[])
                main_dictionary[current_year].setdefault('Months of Supply % Change ' + month + ' (YoY)', [])
                main_dictionary[current_year]['New Listings ' + month + ' ' + previous_year].append(new_listings_previous)
                main_dictionary[current_year]['New Listings ' + month + ' ' + current_year].append(new_listings_current)
                main_dictionary[current_year]['New Listings % Change ' + month + ' (YoY)'].append(new_listings_per_change)
                main_dictionary[current_year]['Closed Sales ' + month + ' ' + previous_year].append(closed_sales_previous)
                main_dictionary[current_year]['Closed Sales ' + month + ' ' + current_year].append(closed_sales_current)
                main_dictionary[current_year]['Closed Sales % Change ' + month + ' (YoY)'].append(closed_sales_per_change)
                main_dictionary[current_year]['Days on Market ' + month + ' ' + previous_year].append(DOM_previous)
                main_dictionary[current_year]['Days on Market ' + month + ' ' + current_year].append(DOM_current)
                main_dictionary[current_year]['Days on Market % Change ' + month + ' (YoY)'].append(DOM_per_change)
                main_dictionary[current_year]['Median Sales Price ' + month + ' ' + previous_year].append(median_sales_previous)
                main_dictionary[current_year]['Median Sales Price ' + month + ' ' + current_year].append(median_sales_current)
                main_dictionary[current_year]['Median Sales Price % Change ' + month + ' (YoY)'].append(median_sales_per_change)
                main_dictionary[current_year]['Percent of Listing Price Received ' + month + ' ' + previous_year].append(percent_lpr_previous)
                main_dictionary[current_year]['Percent of Listing Price Received ' + month + ' ' + current_year].append(percent_lpr_current)
                main_dictionary[current_year]['Percent of Listing Price Received % Change ' + month + ' (YoY)'].append(percent_lpr_per_change)
                main_dictionary[current_year]['Inventory of Homes for Sale ' + month + ' ' + previous_year].append(inventory_previous)
                main_dictionary[current_year]['Inventory of Homes for Sale ' + month + ' ' + current_year].append(inventory_current)
                main_dictionary[current_year]['Inventory of Homes for Sale % Change ' + month + ' (YoY)'].append(inventory_per_change)
                main_dictionary[current_year]['Months of Supply ' + month + ' ' + previous_year].append(DOM_previous)
                main_dictionary[current_year]['Months of Supply ' + month + ' ' + current_year].append(DOM_current)
                main_dictionary[current_year]['Months of Supply % Change ' + month + ' (YoY)'].append(DOM_per_change)

            elif main_dictionary[current_year] != {} and city not in main_dictionary[current_year]['City']:
                main_dictionary[current_year].setdefault('New Listings ' + month + ' ' + previous_year, [])
                main_dictionary[current_year].setdefault('New Listings ' + month + ' ' + current_year, [])
                main_dictionary[current_year].setdefault('New Listings % Change ' + month + ' (YoY)', [])
                main_dictionary[current_year].setdefault('Closed Sales ' + month + ' ' + previous_year, [])
                main_dictionary[current_year].setdefault('Closed Sales ' + month + ' ' + current_year, [])
                main_dictionary[current_year].setdefault('Closed Sales % Change ' + month + ' (YoY)', [])
                main_dictionary[current_year].setdefault('Days on Market ' + month + ' ' + previous_year, [])
                main_dictionary[current_year].setdefault('Days on Market ' + month + ' ' + current_year, [])
                main_dictionary[current_year].setdefault('Days on Market % Change ' + month + ' (YoY)', [])
                main_dictionary[current_year].setdefault('Median Sales Price ' + month + ' ' + previous_year, [])
                main_dictionary[current_year].setdefault('Median Sales Price ' + month + ' ' + current_year, [])
                main_dictionary[current_year].setdefault('Median Sales Price % Change ' + month + ' (YoY)', [])
                main_dictionary[current_year].setdefault('Percent of Listing Price Received ' + month + ' ' + previous_year, [])
                main_dictionary[current_year].setdefault('Percent of Listing Price Received ' + month + ' ' + current_year, [])
                main_dictionary[current_year].setdefault('Percent of Listing Price Received % Change ' + month + ' (YoY)', [])
                main_dictionary[current_year].setdefault('Inventory of Homes for Sale ' + month + ' ' + previous_year,[])
                main_dictionary[current_year].setdefault('Inventory of Homes for Sale ' + month + ' ' + current_year,[])
                main_dictionary[current_year].setdefault('Inventory of Homes for Sale % Change ' + month + ' (YoY)', [])
                main_dictionary[current_year].setdefault('Months of Supply ' + month + ' ' + previous_year, [])
                main_dictionary[current_year].setdefault('Months of Supply ' + month + ' ' + current_year, [])
                main_dictionary[current_year].setdefault('Months of Supply % Change ' + month + ' (YoY)', [])
                main_dictionary[current_year]['City'].append(city)
                main_dictionary[current_year]['County'].append(county)
                main_dictionary[current_year]['New Listings ' + month + ' ' + previous_year].append(new_listings_previous)
                main_dictionary[current_year]['New Listings ' + month + ' ' + current_year].append(new_listings_current)
                main_dictionary[current_year]['New Listings % Change ' + month + ' (YoY)'].append(new_listings_per_change)
                main_dictionary[current_year]['Closed Sales ' + month + ' ' + previous_year].append(closed_sales_previous)
                main_dictionary[current_year]['Closed Sales ' + month + ' ' + current_year].append(closed_sales_current)
                main_dictionary[current_year]['Closed Sales % Change ' + month + ' (YoY)'].append(closed_sales_per_change)
                main_dictionary[current_year]['Days on Market ' + month + ' ' + previous_year].append(DOM_previous)
                main_dictionary[current_year]['Days on Market ' + month + ' ' + current_year].append(DOM_current)
                main_dictionary[current_year]['Days on Market % Change ' + month + ' (YoY)'].append(DOM_per_change)
                main_dictionary[current_year]['Median Sales Price ' + month + ' ' + previous_year].append(median_sales_previous)
                main_dictionary[current_year]['Median Sales Price ' + month + ' ' + current_year].append(median_sales_current)
                main_dictionary[current_year]['Median Sales Price % Change ' + month + ' (YoY)'].append(median_sales_per_change)
                main_dictionary[current_year]['Percent of Listing Price Received ' + month + ' ' + previous_year].append(percent_lpr_previous)
                main_dictionary[current_year]['Percent of Listing Price Received ' + month + ' ' + current_year].append(percent_lpr_current)
                main_dictionary[current_year]['Percent of Listing Price Received % Change ' + month + ' (YoY)'].append(percent_lpr_per_change)
                main_dictionary[current_year]['Inventory of Homes for Sale ' + month + ' ' + previous_year].append(inventory_previous)
                main_dictionary[current_year]['Inventory of Homes for Sale ' + month + ' ' + current_year].append(inventory_current)
                main_dictionary[current_year]['Inventory of Homes for Sale % Change ' + month + ' (YoY)'].append(inventory_per_change)
                main_dictionary[current_year]['Months of Supply ' + month + ' ' + previous_year].append(DOM_previous)
                main_dictionary[current_year]['Months of Supply ' + month + ' ' + current_year].append(DOM_current)
                main_dictionary[current_year]['Months of Supply % Change ' + month + ' (YoY)'].append(DOM_per_change)

        #return pprint.pprint(main_dictionary)

    def update_njr10k(self, current = current_data_avail):
        pass


    def njrdata(self):

        logger = logging.getLogger("NJRData")
        logger.setLevel(logging.DEBUG)
        # Create the FileHandler() and StreamHandler() loggers
        f_handler = logging.FileHandler('NJRData.log')
        f_handler.setLevel(logging.DEBUG)
        c_handler = logging.StreamHandler()
        c_handler.setLevel(logging.INFO)
        # Create formatting for the loggers
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s',datefmt='%d-%b-%y %H:%M:%S')
        # Set the formatter for each handler
        f_handler.setFormatter(formatter)
        c_handler.setFormatter(formatter)
        logger.addHandler(f_handler)
        logger.addHandler(c_handler)
        # Run Selenium to automate the download of all the monthly and full year real estate data of NJ
        options = Options()
        #Change this directory to the new one: ('C:\\Users\\Omar\\Desktop\\Python Temp Folder')
        s = {"savefile.default_directory": 'C:\\Users\\Omar\\Desktop\\Selenium Temp Folder'}
        #options.add_argument('window-postion=2000,0')
        #options.add_experimental_option("detach", True)
        options.add_experimental_option("prefs", s)
        options.add_argument("--headless=new")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        url = 'https://www.njrealtor.com/login.php?rd=10&passedURL=/goto.php?10kresearch=1&skipToken=1'
        driver.get(url)

        username, pw = self.get_us_pw('NJRealtor')

        try:
            # Login in using my email and password
            email = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//input[@id='LoginEmail']"))
                )
            email.send_keys(username)
            pw1 = driver.find_element(By.XPATH, "//input[@id='LoginPassword']")
            pw1.send_keys(pw)
            login = driver.find_element(By.XPATH, "//input[@id='LoginButton']")
            login.click()

            # Recognize the page element to know its time to webscrape all the cities and counties
            brand = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//img[@class='brand']"))
                )
            results = driver.page_source
            soup = BeautifulSoup(results, 'html.parser')
            self.area_results(soup)
            self.current_data_avail(soup)

        except TimeoutException as te:
            logger.exception(f'Timeout Error Occurred: {te}')

        except NoSuchElementException as nse:
            logger.exception(f'So Such Element Was Found: {nse}')

        except ElementNotVisibleException as env:
            logger.exception(f'The Element Is Not Visible: {env}')

        except:
            logger.exception(f'An Error Has Occured')

        else:
            logger.info(f'BeautifulSoup Has Run for NJ Realtor Successfully')

    def OrganizeFiles(self):

        base_path = 'C:\\Users\\Omar\\Desktop\\Python Temp Folder\\PDF Temp Files'
        years = {}
        for filenames in os.walk(base_path):
            for filename in filenames:
                target = filename.rstrip('.pdf').split(' ')
                year = target[-1]
                if year not in years:
                    years.add(year)
                for i in years:
                    target_path = base_path + '\\' + i
                    if os.path.exists(target_path):
                        shutil.move(filename, target_path)
                        #continue
                    elif os.path.exists(target_path) == False:
                        os.mkdir(i)
                        shutil.move(filename, target_path)
                        #continue

    def corrupted_files(self, list):
        dict = {}
        # Do I want to delete the corrupted files before redownloading them?
        for n, i in enumerate(list):
            info = i.rstrip('.pdf').split(' ')
            town = info[0:len(info) - 2]
            if len(town) > 1:
                town = ' '.join(town)
                month = info[-2]
                year = info[-1]

            for m, i in enumerate(self.__towns):
                if town in i:
                    town = self.__towns[m]
                    dict[n] = [town, month, year]

        base_url = 'http://njar.stats.10kresearch.com/docs/lmu/'

        with requests.Session() as session:
            username, pw = self.get_us_pw('NJRealtor')

            payload1 = {'rd': '10',
                        'passedURL': '/goto/10k/',
                        'case': '',
                        'LoginEmail': username,
                        'LoginPassword': pw,
                        'LoginButton': 'Login'}

            params = {'src': 'Page'}
            # months = list(self.__months.keys())

            # months_tracker = manager.counter(total=len(months), desc=f'Year:', unit='Months')

            url = 'https://www.njrealtor.com/login/?rd=10&passedURL=/goto/10k/'
            url2 = 'https://www.njrealtor.com/ramco-api/web-services/login_POST.php'

            response = session.get(url)
            r_post = session.post(url2, data=payload1)

            for k, v in dict.items():
                city0 = v[0].split(' ')
                city = ''.join(city0)
                y = v[2]
                for k, v in self.__months.items():
                    if month in v:
                        m = k

            try:
                url3 = base_url + y + '-' + m + '/x/' + city
                new_filename = " ".join([city0[0], self.__months[m], y]) + ".pdf"
                with session.get(url3, params=params, stream=True) as reader, open(new_filename, 'wb') as writer:
                    for chunk in reader.iter_content(chunk_size=1000000):
                        # target_pdf = reader.content
                        writer.write(chunk)
            except:
                #put correct loggers and exceptions here
                pass

    def CreateZip(self, folder):
        # This is the current python directory all files are being saved in
        # os.chdir('C:\\Users\\Omar\\Desktop\\Selenium Temp Folder')
        # Rename Selenium Temp Folder to Python Temp Folder and add a folder called PDF Temp Files as use that throughout the Scraper class
        # os.chdir('C:\\Users\\Omar\\Desktop\\Python Temp Folder\\PDF Temp Files')
        # import zipfile
        # folder = 'C:\\Users\\Omar\\Desktop\\Python Temp Folder\\PDF Temp Files'
        newZip = zipfile.Zipfile(str(datetime.datetime.now()) + '_NJRealtor.zip', 'w')
        for foldername, subfolders, filenames in os.walk(folder):
            # I need to look further into this os.walk to see how to properly add the folders and files to the zip
            newZip.write(foldername)
            for filename in filenames:
                # Figure out how to correctly write this code
                newZip.write
        newZip.close()
        # Create new PDF Temp Files folder at the end of the process





if __name__ == '__main__':
    #l1 = ['Aberdeen September 2019.pdf', 'Aberdeen October 2019.pdf']
    main_dictionary = {
        '2018': {},
        '2019': {},
        '2020': {},
        '2021': {},
        '2022': {},
        '2023': {}
    }

    obj = Scraper()
    #load the shelf file for the saved data
    #If this code has never been run before, the full NJR10k will need to be run all the way back from 2018
    if obj.no_of_runs == 0:
        obj.njrdata()
        results = obj.njr10k()
        #The NJR10k function will return a list if there and pdfs found to be possibly corrupted
        #If length of the list is created than 0, the program will trigger the next function to download corrupted data
        if len(results) > 0:
            obj.corrupted_files(results)
        #Organize all the files into their respective folders according to the year of the data
        obj.OrganizeFiles()
        #If todays date is the last day of the year run zip functino. If not, stay sleep
        if datetime.datetime.now(): #>= last day of the year
            obj.CreateZip()

        #Run the function that turns the main_dictionary into a Pandas dataframe
        #Create seperate dataframes for the year 2018 to 2023 (this holds columns for all 12 individual months)
        #Create seperate dataframes for Q1 - Q4 for every year
        #Create a full year dataframe for 2018 to 2023 (this hold columns for the full year data pulled from December pdfs)
        #Run Pandas2Excel which will put all dataframes in a single file in their own respective tabs

    # If this code has been run before, the Updated NJR10k will need to be run from last pulled data
    elif obj.no_of_runs > 0:
        obj.njrdata()
        results = obj.update_njr10k()
        if len(results) > 0:
            obj.corrupted_files(results)

        obj.OrganizeFiles()
        if datetime.datetime.now():  # >= last day of the year
            obj.CreateZip()

        # Run the function that uplaods the main file, create Pandas dataframes from the new data and append them to respective dictionaries
        # Update seperate dataframes for the current year (this holds columns for all 12 individual months)
        # Update seperate dataframes for Q1 - Q4 for the current year
        # Create a full year dataframe for the current year (this hold columns for the full year data pulled from December pdfs)
        # Run Pandas2Excel which will put all dataframes in a single file in their own respective tabs









    # for i in l1:
    #     obj.extract_re_data(i)

    pprint.pprint(main_dictionary)

    # username, pw = obj.get_us_pw('NJRealtor')
    # print(type(username))
    # print(type(pw))


