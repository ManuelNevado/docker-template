# Lambda for mark up files by mark. Each mark run diferent Lambda
from datetime import datetime
from fileinput import filename
import json
import time
import os
import uuid
import logging
import boto3
import botocore
from urllib.parse import unquote_plus
from collections import Counter
from statistics import mean
from shaadow_actions.insert import insert
from shaadow_actions.extract import extract
from functions.upload_to_s3 import upload_to_s3
from functions.clean_folder import clean_folder



# Environment variables
CWD = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(CWD, "configs")

# AWS clients
s3_client = boto3.client("s3")

## LOGGER
logger_format ="%(asctime)s %(levelname)s [%(lineno)s - %(funcName)s()] %(message)s"
logging.basicConfig(format=logger_format,filename="")
logger = logging.getLogger(__name__)
logger.setLevel(os.environ["LOGGER_LEVEL"])


# Lambda handler
def handler(event, context):
    print(json.dumps(event))
    print(context)

    if "source" in event:
        logger.info("SCHEDULED EVENT - Warm Up")
        return
    
    log_stream_name = context.log_stream_name
    print(log_stream_name)

    logger.info('CLEANING TMP FOLDER')
    clean_folder('/tmp')
    logger.info('TMP FOLDER IS CLEAN')

    # Select Digital mark
    logger.info("# SELECT DIGITAL MARK...")
    try:
        digital_mark = event["digitalMark"]
        logger.debug("Digital mark: %s", str(digital_mark))
        if digital_mark:
            logger.info("digital mark value: true")
            config_file="/config_shaadow.json"
        else:
            logger.info("digital mark value: false")
            config_file="/config_shaadow_no_digitalmark.json"
    except KeyError as kerr:
        logger.info("no digital mark provided. Default: true")
        config_file="/config_shaadow.json"

    # Origin bucket and key from event.
    logger.info("# GET EVENT PARAMETERS...")
    try:
        bucket_origin_name = event["bucketOriginName"]
        logger.debug("Origin bucket name: %s", bucket_origin_name)
        s3_file_origin_key = unquote_plus(event["s3FileOriginKey"])
        logger.debug("Origin file key: %s", s3_file_origin_key)
        lambda_file_origin_path = "/tmp/{}{}".format(uuid.uuid4(), s3_file_origin_key.replace("/", ""))
        logger.debug("Lambda download path: %s", lambda_file_origin_path)
    except KeyError as k_err:
        logger.error("Mandatory data is missing")
        raise k_err
    logger.info("Ok first mandatory data")

    logger.info("# DOWNLOADING FILE...")
    download_response = s3_client.download_file(bucket_origin_name, s3_file_origin_key, lambda_file_origin_path)
    logger.debug("Download response: %s", str(download_response))
    logger.info("File succesfully downloaded")

    # Manage shaadow action: MARK or READ:
    info = ""
    logger.info("# SHAADOW ACTION: %s", event["shaadowAction"])
    # handle event type

    logShadowLib = ""

    if event["shaadowAction"] in ["MARKUP", "MARK", "INSERT"]:
        logger.info("Get mark mandatory data")
        mark = event["shaadowMark"]
        logger.debug("insert mark: %s", mark)
        bucket_destination_name = event["bucketDestinationName"]
        logger.debug("bucket destination name: %s", bucket_destination_name)
        s3_file_destination_key = event["s3FileDestinationKey"]
        logger.debug("s3 file destination key: %s", s3_file_destination_key)
        lambda_file_marked_path = lambda_file_origin_path.replace(".pdf", "marked.pdf")
        logger.debug("Lambda file marked path: %s", lambda_file_marked_path)

        return_mark_info = insert(lambda_file_origin_path, lambda_file_marked_path, mark, config_file)
        logger.info(return_mark_info)
        
        if return_mark_info["error"]:

            time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            log_s3_destination_key_mark = f"""MARK/{time}_{mark}_error.log"""
            upload_to_s3("../tmp/shadow.log", os.environ["LOG_BUCKET"], log_s3_destination_key_mark)

            return {
                "statusCode": 200,
                "error": True,
                "mark": mark,
                "action": event["shaadowAction"],
                "result": return_mark_info["errorMessage"],
                "errorCode": return_mark_info["errorCode"],
                "logStreamName": log_stream_name,
                "logShadowLib": log_s3_destination_key_mark
            }
    
        upload_to_s3(lambda_file_marked_path, bucket_destination_name, s3_file_destination_key)
        info = return_mark_info
        info["insertPdfname"] = os.path.basename(s3_file_origin_key)

        time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_s3_destination_key_mark = f"MARK/{time}_{mark}_success.log"
        upload_to_s3("../tmp/shadow.log", os.environ["LOG_BUCKET"], log_s3_destination_key_mark)
        logShadowLib = log_s3_destination_key_mark


    elif event["shaadowAction"] in ["EXTRACT", "READ"]:

        return_read_info = extract(context, lambda_file_origin_path, config_file)
        mark = return_read_info["mark"]
        print("mark: ", mark)
        if return_read_info["error"]:

            time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            log_s3_destination_key = f"""EXTRACT_{time}_{mark}_error.log"""
            upload_to_s3("../tmp/shadow.log", os.environ["LOG_BUCKET"], log_s3_destination_key)

            return {
                "statusCode": 200,
                "error": True,
                "mark": mark,
                "action": event["shaadowAction"],
                "result": return_read_info["errorMessage"],
                "errorCode": return_read_info["errorCode"],
                "logStreamName": log_stream_name,
                "logShadowLib": log_s3_destination_key
            }

        if mark == "NO_USER_MARKS" and lambda_file_origin_path.rsplit('.')[1].lower() in ["jpeg", "png", "jpg"]:
            """response_check_file = check_file(lambda_file_origin_path, lambda_file_origin_path.rsplit('.')[1].lower())
            print(response_check_file)
            if response_check_file["error"] == False:
                return_read_info = extract(context, response_check_file["new_file_path"], config_file, True)
                mark = return_read_info["mark"]
                print("fin segunda iteración")"""
            print("No denoisser aplied version test")
        else:
            print("File is not image, no denoiser applied")

        logShadowLib = return_read_info["logShadowLib"]
        del return_read_info["logShadowLib"]

        info = return_read_info
        info["extractPdfname"] = os.path.basename(s3_file_origin_key)

        # time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        # log_s3_destination_key = f"EXTRACT/{time}_{mark}_success.log"

    elif event["shaadowAction"] in ["TRACE", "TRACEABILITY"]:
        mark = event["shaadowMark"]
        info = "traceability no implemented"

    # upload_to_s3("../tmp/shadow.log", os.environ["LOG_BUCKET"], log_s3_destination_key)
    os.remove("../tmp/shadow.log")
    try:
        os.remove(f"..{lambda_file_origin_path}")
    except:
        logger.info("Denoised applied, no file to remove")
        os.remove(response_check_file["new_file_path"])
    try:
        os.remove(f"..{lambda_file_marked_path}")
    except:
        logger.info('Not marked file')
    # Return to mark-and-read lambda

    return_info = {
        "statusCode": 200,
        "error": False,
        "mark": mark,
        "action": event["shaadowAction"],
        "result": "COMPLETED",
        "additionalInfo": info,
        "logStreamName": log_stream_name,
        "logShadowLib": logShadowLib
    }

    logger.debug("return info to lambda: %s", return_info)
    print('END OF SNIPPET')
    return return_info

class MarkupError(Exception):
    """Exception raised for errors when markup Action

    Attributes:
        code -- error code
        message -- explanation of the error
    """

    def __init__(self, mark, code=0, message="Unable to mark"):
        self.mark = mark
        self.message = message
        self.code = code
        super().__init__(self.code, self.message)

    def __str__(self):
        return json.dumps({
            "errorCode": self.code,
            "errorMessage": self.message,
            "mark": self.mark
        })

class ExtractionError(Exception):
    """Exception raised for errors when markup Action

    Attributes:
        code -- error code
        message -- explanation of the error
    """

    def __init__(self, code=0, message="Unable to extract any marks in document"):
        self.message = message
        self.code = code
        super().__init__(self.code, self.message)

    def __str__(self):
        return json.dumps({
            "errorCode": self.code,
            "errorMessage": self.message
        })