import boto3
import json
import logging

s3 = boto3.resource('s3')
s3_client = boto3.client('s3')
rek = boto3.client('rekognition', region_name='us-east-1')
topic_ARN = '<ARN>'
role_ARN = '<ARN>'
sqs = boto3.client('sqs')
sqs_res = ''
celebs = ''

logger = logging.getLogger('mainlog')

def initialize_video(filenamearg):
    res = rek.start_celebrity_recognition(
        Video={
            'S3Object':{
                'Bucket':'pennapps-retro',
                'Name':filenamearg
        }
    },
    ClientRequestToken= filenamearg[0:-5],
    NotificationChannel={
        'SNSTopicArn':topic_ARN,
        'RoleArn':role_ARN
        },
    JobTag='Krakatoa'
    )
    logger.debug(res)
    global job_ID
    job_ID = res['JobId']
    return job_ID


def celeb_img(filename):
    global img_resp
    img_resp = rek.recognize_celebrities(
        Image={
            'S3Object':{
                'Bucket':'pennapps-retro',
                'Name':filename
                }
            }
    )

    return img_resp


def call_sqs():
    global sqs_res
    sqs_res = sqs.receive_message(
        QueueUrl='<url>',
        MaxNumberOfMessages=1,
        WaitTimeSeconds = 20,
        )


def celeb_vid(job_ID):
    global celebs
    celebs = rek.get_celebrity_recognition(
        JobId=job_ID,
        MaxResults = 1000
    )

    stat = celebs['JobStatus']
    for x in celebs['Celebrities']:
        logger.debug(x)

    return [celebs, stat]
