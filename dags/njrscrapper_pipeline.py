import kafka.errors
from datetime import datetime
from datetime import timedelta
from airflow.sdk import task, dag, TaskGroup
from airflow.utils.email import send_email
from airflow.providers.standard.operators.python import PythonOperator, BranchPythonOperator
from airflow.providers.standard.sensors.python import PythonSensor
from airflow.exceptions import AirflowSkipException
from pendulum import timezone
from kafka.admin import NewTopic
from kafka.structs import TopicPartition
from kafka.admin.client import KafkaAdminClient
from plugins.utility_func import logger_decorator, create_kafka_producer, create_kafka_consumer
from plugins.NJRScrapper import Scraper
from plugins.NJRParser import NJRParser


def airflow_scrape_data(**kwargs):

    obj = Scraper()
    obj.main(**kwargs)


def airflow_consume_data():

    obj = NJRParser()
    obj.main()


def branching_decision(**kwargs):

    # starting_point returns True or False
    if kwargs['status'] is True:

        # Returns the task_id based on the internal logic
        return "etl_pipeline"

    else:
        return "skip_all_tasks"


def latest_data_available():

    obj = Scraper()
    return obj.airflow_status_check()


def new_msgs_available(logger_, topic='njrdata'):

    offset_dict = {}
    # KafkaConsumer not thread safe, so I need to create one specifically for this task
    cons = create_kafka_consumer("msg_check", "ncjar_data_consumer")

    # Check the partitions in the consumer. Returns a set of partition ids
    partitions = cons.partitions_for_topic(topic)
    print(f'{partitions}')

    try:
        if not partitions:
            logger_.warning(f"No partitions found for topic {topic}")

            raise AttributeError(f"No partitions created for {topic}")

        # Create list of TopicPartition objects to check end offsets
        topic_partitions = [TopicPartition(topic, p) for p in partitions]
        offset_dict.update({f"{tp}": False for tp in topic_partitions})

        # Returns a dict of partitions and their end offsets in key-value pairs
        end_offsets = cons.end_offsets(topic_partitions)

        for tp in topic_partitions:
            # tp is the topic partition object
            committed = cons.committed(tp)
            latest = end_offsets[tp]

            if committed is None:
                committed = 0
            lag = latest - committed
            logger_.info(
                f"Partition {tp.partition}: committed={committed}, latest={latest}, lag={lag}"
            )

            if lag > 0:
                offset_dict[tp] = True

        if True in list(offset_dict.values()):
            logger_.info(f"New data found for {topic}")

            return True
        else:
            return False

    except AttributeError:
        logger_.info(f"No partitions found for topic {topic}")

        return False


def skip_pipeline():
    raise AirflowSkipException("Time cutoff reached - skipping full pipeline")


def status_email(**kwargs):

    if kwargs['phase'] == 'starting':
        subject = f"NCJAR ETL Pipeline Starting - {datetime.now().date()}"
        message = f"""
                <b>NCJAR ETL Pipeline has been initiated</b><br>
                Scraping data from <b>{kwargs['previous_data']}</b> to
                <b>{kwargs['current_data']}</b>
            """
    else:
        subject = f"NCJAR ETL Pipeline Ending - {datetime.now().date()}"
        message = f"""
                <b>NCJAR ETL Pipeline has been completed</b><br>
            """

    send_email(to="nj.realestate.pybot@gmail.com", subject=subject, html_content=message)


# Task 1: Check the health of Apache Kafka #Connection
@task(task_id="check_kafka_connection")
def check_kafka_connection(logger_):

    # Check if broker connects
    test_producer = create_kafka_producer(client_id='test-connection')

    if test_producer.bootstrap_connected() is True:
        logger_.info('Test connection to Kafka brokers was successful')
        test_producer.close()
        return True

    else:
        return False


# Task 1a: Check if the correct topics have been created
@task(task_id="create_topics")
def create_kafka_topics(logger_, topic: str = 'njrdata', status: bool = True):

    if status is True:

        admin_client = KafkaAdminClient(
            bootstrap_servers=["broker-1:9092", "broker-2:9092", "broker-3:9092"],
            client_id="check_topic",
        )

        available_topics = admin_client.list_topics()
        logger_.info(f'Current existing topics: {available_topics}')

        try:
            if topic not in available_topics:
                topic_obj = NewTopic(
                    name=topic,
                    num_partitions=3,
                    replication_factor=2,
                    topic_configs={"cleanup.policy": "compact"},  # Look into what other configs I need
                )
                admin_client.create_topics(
                    new_topics=[topic_obj], validate_only=False, timeout_ms=1500
                )
        except kafka.errors.TopicAlreadyExistsError:
            logger_.info(f'Topic {topic} already exists')
        else:
            logger_.info(f'Topic {topic} created in Apache Kafka topic list')

        return admin_client.list_topics()


eastern = timezone("America/New_York")
default_args = {
    "owner": "Jibreel Hameed",
    "email": ['nj.realestate.pybot@gmail.com'],
    "email_on_failure": True,
    "email_on_retry": True,
    "start_date": datetime(2025, 12, 1, hour=9, minute=30, tzinfo=eastern),
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    }


# Define DAG as decorator over final pipeline function
@dag(
    "NCJAR_Scrape_And_Preprocessing",
    description="",
    default_args=default_args,
    schedule=timedelta(days=30),
)
@logger_decorator
def ncjar_pipeline(**kwargs):

    logger = kwargs['logger']
    f_handler = kwargs["f_handler"]
    c_handler = kwargs["c_handler"]

    kafka_status = check_kafka_connection()
    _ = create_kafka_topics(logger, status=kafka_status)

    latest_data_avail, current_data, previous_data = PythonSensor(
        task_id='latest_data_available',
        python_callable=latest_data_available,
        poke_interval=86400,
        timeout=90000,
        mode='reschedule'
    )

    branch_decision = BranchPythonOperator(
        task_id='branching_decision',
        python_callable=branching_decision,
        op_kwargs={'status': latest_data_avail},
        trigger_rule='none_failed'
    )

    skip_all_tasks = PythonOperator(
        task_id='skip_all_tasks',
        python_callable=skip_pipeline,
        trigger_rule='all_success'
    )

    with TaskGroup(group_id='etl_pipeline') as etl_pipeline:

        start_status = PythonOperator(
            task_id='start_email',
            python_callable=status_email,
            op_kwargs={'phase': 'starting', 'current_data': current_data,
                       'previous_data': previous_data}
        )

        scrape_data = PythonOperator(
            task_id='scrape_data',
            python_callable=airflow_scrape_data
        )

        kafka_msg_sensor = PythonSensor(
            task_id='check_for_messages',
            python_callable=new_msgs_available,
            op_kwargs={'logger_': logger}
        )

        consume_data = PythonOperator(
            task_id='consume_data',
            python_callable=airflow_consume_data
        )

        end_status = PythonOperator(
            task_id='start_email',
            python_callable=status_email,
            op_kwargs={'phase': 'ending'}
        )

        start_status >> scrape_data
        kafka_msg_sensor >> consume_data
        consume_data >> end_status

    latest_data_avail >> branch_decision
    branch_decision >> etl_pipeline
    branch_decision >> skip_all_tasks

