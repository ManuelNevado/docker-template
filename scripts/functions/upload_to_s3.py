import logging
import boto3
import os

# AWS clients
s3_client = boto3.client("s3")
## LOGGER
logger_format ="%(asctime)s %(levelname)s [%(lineno)s - %(funcName)s()] %(message)s"
logging.basicConfig(format=logger_format,filename="")
logger = logging.getLogger(__name__)
logger.setLevel(os.environ["LOGGER_LEVEL"])

def upload_to_s3(origin_path, bucket_name, dest_path):
    #Upload file to S3
    print("------------------------")
    logger.info("Uploading file to S3 bucket...")
    logger.info("Upoad key: %s", dest_path)

    if origin_path.endswith('log'):
        s3_client.upload_file(
            Filename=origin_path,
            Bucket=bucket_name,
            Key=dest_path)
    else:
        s3_client.upload_file(
            Filename=origin_path,
            Bucket=bucket_name,
            Key=dest_path,
            ExtraArgs={
                "ContentType": "application/pdf"
                }
            )
    logger.info("File uploaded to S3 bucket successfully")
    print("---------------------------------")