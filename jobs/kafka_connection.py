import sys
from ncjar_core.ncjar.utility_func import create_kafka_producer, check_pipeline_metadata


def check_kafka_connection():

    # Check if broker connects
    test_producer = create_kafka_producer(client_id='test-connection')

    if test_producer.bootstrap_connected() is True:
        print(' ==== KAFKA TEST CONNECTION WAS SUCCESSFUL ====  ')
        test_producer.close()
        return "true"  # Boolean values cannot be passed through argparse so use str values

    else:
        return "false"


if __name__ == '__main__':

    status = check_kafka_connection()
    check_pipeline_metadata("ncjar_pipeline", prop_type_=None,
                            key_="kafka_connection", status_=status)
    sys.exit(0)

