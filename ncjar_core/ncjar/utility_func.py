import os
import logging
import json
import time
import shelve
import pendulum
import pandas as pd
from filelock import FileLock, Timeout
from pendulum import timezone
from docker.types import Mount
from kafka import KafkaProducer, KafkaConsumer
from dotenv import load_dotenv
from datetime import datetime
from tqdm import tqdm
from sqlalchemy import create_engine
from kafka.errors import NoBrokersAvailable

""" 
______________________________________________________________________________________________________________
                               Use this section to house the decorator functions
______________________________________________________________________________________________________________
"""


class TqdmLoggingHandler(logging.Handler):

    def emit(self, record):
        msg = self.format(record)
        tqdm.write(msg)


def check_pipeline_metadata(pipeline_, prop_type_: str | None, key_=None, status_=None):

    def create_pipeline_key(**kwargs):
        data_file = kwargs['data_file']
        key = kwargs['key']
        pipeline = kwargs['pipeline']
        prop_type = kwargs['prop_type']
        status = kwargs['status']

        if pipeline == 'gsmls_airflow_pipeline':
            if data_file.get(pipeline, None) is None:
                data_file.setdefault(pipeline, {})
            if data_file[pipeline].get(prop_type, None) is None:
                data_file[pipeline].setdefault(prop_type, {})
                data_file[pipeline][prop_type] = create_pipeline_metadata(pipeline)
                print(f" ==== INITIALIZING {key} STATUS OF {pipeline} TO {status} FOR {prop_type} ==== ")
        else:
            if data_file.get(pipeline, None) is None:
                data_file[pipeline] = create_pipeline_metadata(pipeline)
                print(f" ==== INITIALIZING {key} STATUS OF {pipeline} TO {status} ==== ")

    def update_pipeline_status(**kwargs):
        data_file = kwargs['data_file']
        key = kwargs['key']
        pipeline = kwargs['pipeline']
        prop_type = kwargs['prop_type']
        status = kwargs['status']

        if pipeline == 'gsmls_airflow_pipeline':
            if status is not None:
                data_file[pipeline][prop_type][key] = status
            else:
                data_file[pipeline][prop_type][key] = False
        else:
            data_file[pipeline][key] = status

    data_path = get_filepath("metadata")
    metadata_path = os.path.join(data_path, "metadata")
    filelock_path = f'{metadata_path}.lock'
    lock = FileLock(filelock_path, timeout=120)
    vars_ = {
        'data_file': None,
        'key': key_,
        'pipeline': pipeline_,
        'prop_type': prop_type_,
        'status': status_
    }

    try:
        # Lock the object and create/revise data
        with lock:
            with shelve.open(metadata_path, writeback=True) as data_file_:
                vars_['data_file'] = data_file_

                create_pipeline_key(**vars_)
                update_pipeline_status(**vars_)
                data_file_.sync()

    except Timeout:
        print(f" ==== FILELOCK TIMEOUT. STATUS OF {pipeline_} WAS NOT UPDATED ==== ")


def create_pipeline_metadata(pipeline):

    if pipeline == "ncjar_pipeline":
        return {"latest_data": None, "kafka_connection": False, "producer": False, "consumer": False}


def create_postgres_connection(con_type: str, db_name: str):

    port = 5432

    try:
        host = os.getenv("POSTGRES_AWS_HOST")
        username = os.getenv("POSTGRES_AWS_USER")
        pw = os.getenv("POSTGRES_AWS_PASSWORD")

        if host is None or username is None or pw is None:
            raise ValueError
    except ValueError:
        print(" ==== ENV ERROR: POSTGRES USER INFO NOT SUPPLIED TO DOCKER CONTAINER ==== ")
        print(" ==== LOADING INTERNAL ENVIRONMENT VARIABLES DOCUMENT ==== ")
        load_dotenv(get_filepath("env"))
        host = os.getenv("POSTGRES_AWS_HOST")
        username = os.getenv("POSTGRES_AWS_USER")
        pw = os.getenv("POSTGRES_AWS_PASSWORD")

    if con_type == 'jdbc':
        jdbc_url = f"jdbc:postgresql://{host}:{port}/{db_name}"
        properties = {
            'user': username,
            'password': pw,
            'driver': "org.postgresql.Driver"
        }

        return jdbc_url, properties

    elif con_type == 'psycopg2':

        return None, {'user': username, 'password': pw, 'dbname': db_name, 'host': host, 'port': port}


def create_kafka_consumer(client_id, group_id):

    return KafkaConsumer(
        client_id=client_id,
        group_id=group_id,
        bootstrap_servers=["broker-1-ncjar:9092", "broker-2-ncjar:9092", "broker-3-ncjar:9092"],
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        key_deserializer=lambda k: k.decode("utf-8"),
        heartbeat_interval_ms=5000,  # Send heartbeats in 5s intervals
        session_timeout_ms=45000,  # How long the consumer waits for heartbeats before considered dead: 45 secondds
        max_poll_interval_ms=3000000,  # How long the consumer goes in between successful polls before considered "stuck": 50 minutes
        max_poll_records=100,  # Max number of records pulled per poll request
    )


def create_kafka_producer(client_id, logger=None, remote=True):
    retries = 0

    if remote is not True:
        bootstrap_servers = ["localhost:9092"]
    else:
        bootstrap_servers = ["broker-1-ncjar:9092", "broker-2-ncjar:9092", "broker-3-ncjar:9092"]

    while retries <= 4:
        for attempt in range(1):
            try:
                producer = KafkaProducer(
                    bootstrap_servers=bootstrap_servers,
                    key_serializer=lambda v: json.dumps(v).encode("utf-8"),
                    retries=3,
                    acks="all",
                    client_id=client_id,
                )

                return producer

            except NoBrokersAvailable as nba:
                retries += 1

                if logger is not None:
                    logger.warning(f"{nba}")
                    logger.warning(
                        f"KafkaProducer couldn't be established on this attempt. This will be retry #{retries}"
                    )
                time.sleep(3)

                if retries > 4:
                    break

    raise NoBrokersAvailable


def create_sql_engine(database: str, remote=True):

    if remote is True:

        try:
            connection_str = os.getenv("POSTGRES_AWS_CONN")

            if connection_str is None:
                raise ValueError
        except ValueError:
            print(" ==== ENV ERROR: POSTGRESS AWS INFO NOT SUPPLIED TO DOCKER CONTAINER ==== ")
            print(" ==== LOADING INTERNAL ENVIRONMENT VARIABLES DOCUMENT ==== ")
            load_dotenv(get_filepath("env"))
            connection_str = os.getenv("POSTGRES_AWS_CONN")

        engine = create_engine(f"postgresql+psycopg2://{connection_str}:5432/{database}", echo=False)

    else:
        base, user, pw = get_us_pw("PostgreSQL")
        engine = create_engine(f"postgresql://{user}:{pw}@{base}:5432/{database}", echo=False)

    return engine


def create_volume_mounts(job: str):

    mount_list = []
    source_base = '/root/home/projects/GSMLS-Analysis'
    container_base = '/app'
    jobs_dict = {
        'minor_job': {'source': ['pipeline_metadata'],
                      'target': ['pipeline_metadata']},
        'producer': {'source': ['pipeline_metadata', 'data/stage_one/downloads'],
                     'target': ['pipeline_metadata', 'downloads']},
        'consumer': {'source': ['pipeline_metadata', 'consumer_backup_data'],
                     'target': ['pipeline_metadata', 'consumer_backup_data']},
        'image_consumer': {'source': ['pipeline_metadata'],
                           'target': ['pipeline_metadata']},
        'cleaning': {'source': ['pipeline_metadata', 'data/stage_one/parquet_files', 'logs/pyspark_logs'],
                     'target': ['pipeline_metadata', 'parquet_files', 'logs']},
    }

    source_list = jobs_dict[job]['source']
    target_list = jobs_dict[job]['target']

    for source, target in zip(source_list, target_list):
        mount_obj = Mount(
            source=os.path.join(source_base, source),
            target=os.path.join(container_base, target),
            type='bind'
        )
        mount_list.append(mount_obj)

    return mount_list


def current_status(pipeline: str, prop_type: str, key=None):

    data_path = get_filepath('metadata')
    metadata_path = os.path.join(data_path, "metadata")

    with shelve.open(metadata_path) as reader:
        if key is None:
            result = reader[pipeline][prop_type]
        else:
            result = reader[pipeline][prop_type][key]

    print(f'Pipeline: {pipeline} Key: {key}, Result: {result}')
    return result


def cutoff_time(
    days: int = 0,
    hours: int = None,
    minutes: int = None,
    seconds: int = None,
    tz: str = None,
):

    start = pendulum.now(tz=timezone(tz))
    day = start.day
    day_delta = day + days
    finish = start.set(
        day=day_delta, hour=hours, minute=minutes, second=seconds, microsecond=0
    )

    assert finish > start, f" ==== CUTOFF TIME IS LESS THAN THE CURRENT DATETIME ==== "
    print(f" ==== THE CUTOFF TIME IS : {finish} ==== ")

    return finish


def get_filepath(usecase: str):

    filepaths = {
        'backups': ['/root/home/projects/NJRScrapper/consumer_backup_data',
                    '/workspace/consumer_backup_data', '/app/consumer_backup_data'],
        'base': ['/root/home/projects/NJRScrapper', '/workspace', '/app'],
        'downloads': ['/root/home/projects/NJRScrapper/data/stage_one/downloads',
                      '/workspace/data/stage_one/downloads', '/app/downloads'],
        'env': ['/root/home/projects/NJRScrapper/.env', '/workspace/.env', '/app/.env', '/opt/airflow/.env'],
        'jobs_major': ['/workspace/jobs/major_jobs', '/app/major_jobs'],
        'jobs_minor': ['/workspace/jobs/minor_jobs', '/app/minor_jobs'],
        'logger': ['/workspace/logs/logger_decorator', '/app/logs'],
        'metadata': ['/root/home/projects/NJRScrapper/pipeline_metadata',
                     '/workspace/pipeline_metadata', '/app/pipeline_metadata']
    }

    for path in filepaths[usecase]:
        if os.path.exists(path):
            return path

    raise ValueError(f" ==== CURRENT FILEPATHS FOR {usecase} DO NOT EXIST IN THIS ENVIRONMENT ==== ")


def get_us_pw(website):
    """

    :param website:
    :return:
    """
    # Saves the current directory in a variable in order to switch back to it once the program ends
    previous_wd = os.getcwd()
    os.chdir("F:\\Add\\Folder\\Path")

    db = pd.read_excel("document_name.xlsx", index_col=0)
    username = db.loc[website, "Username"]
    pw = db.loc[website, "Password"]
    base_url = db.loc[website, "Base URL"]

    os.chdir(previous_wd)

    return username, base_url, pw


def logger_decorator(original_function):
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(original_function.__name__)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        if not logger.handlers:
            # Create the FileHandler() and StreamHandler() loggers
            filepath = get_filepath("logger")
            log_filepath = os.path.join(
                filepath,
                original_function.__name__
                + " "
                + str(datetime.today().date())
                + ".log",
            )
            f_handler = logging.FileHandler(log_filepath)
            f_handler.setLevel(logging.DEBUG)
            c_handler = TqdmLoggingHandler()
            c_handler.setLevel(logging.INFO)
            # Create formatting for the loggers
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%d-%b-%y %H:%M:%S",
            )
            # Set the formatter for each handler
            f_handler.setFormatter(formatter)
            c_handler.setFormatter(formatter)
            logger.addHandler(f_handler)
            logger.addHandler(c_handler)

            kwargs["logger"] = logger
            kwargs["f_handler"] = f_handler
            kwargs["c_handler"] = c_handler

        result = original_function(*args, **kwargs)

        if result is None:
            pass
        else:
            return result

    return wrapper


