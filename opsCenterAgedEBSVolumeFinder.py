import json
import itertools
from datetime import datetime, timedelta 
import os, os.path, sys
import boto3
import botocore
from botocore.exceptions import ClientError

## Usage Notes: 
### environment variables:
#### IGNORE_WINDOW -- volumes with activity in this window will be ignored even if they are available; e.g. for a 30 day IGNORE_WINDOW, a volume detached 29 days ago will not be flagged, but a volume detached 31 days ago will. Value must be between 1 and 90
#### SNS_ARN -- Full ARN for SNS topic to send notifications to, e.g. arn:aws:sns:us-west-1:123456789012:mySNStopic; this topic is also used to send detailed notifications when enabled
#### SSM_AUTOMATION_ID -- SSM automation ID for actions to take on volumes which are non-compliant
#### BATCH_SIZE -- size of batches of volumes to attach to a single Ops Item; this number can be between 1 and 100, inclusive; this value is also used if you are sending detailed notifications
#### DETAILED_NOTIFICATIONS -- TRUE/FALSE, determines if detailed notifications are sent to SNS_ARN with the list of volumes found



def getCloudTrailEvents(startDateTime, rgn):
    # gets CloudTrail events from startDateTime until "now"
    cloudTrail = boto3.client('cloudtrail', region_name=rgn)
    attrList = [{'AttributeKey': 'ResourceType', 'AttributeValue': 'AWS::EC2::Volume'}]
    eventList = []
    response = cloudTrail.lookup_events(LookupAttributes=attrList, StartTime=startDateTime, MaxResults=50)
    eventList += response['Events']
    while('NextToken' in response):
        response = cloudTrail.lookup_events(LookupAttributes=attrList, StartTime=startDateTime, MaxResults=50, NextToken=response['NextToken'])
        eventList += response['Events']
    return eventList

def getAvailableVolumes(rgn):
    # returns list of volumes in 'available' state
    ec2 = boto3.client('ec2', region_name=rgn)
    availableVolList = []
    filterList = [{'Name': 'status', 'Values': ['available']}]
    response = ec2.describe_volumes(Filters=filterList, MaxResults=500)
    for v in response['Volumes']:
        availableVolList.append(v['VolumeId'])
    while('NextToken' in response):
        response = ec2.describe_volumes(Filters=filterList, MaxResults=500, NextToken=response['NextToken'])
        for v in response['Volumes']:
            availableVolList.append(v['VolumeId'])
    return availableVolList

def getRecentActiveVolumes(events):
    # parses volumes from list of events from CloudTrail
    recentActiveVolumeList = []
    for e in events:
        for i in e['Resources']:
            if i['ResourceType'] == 'AWS::EC2::Volume':
                recentActiveVolumeList.append(i['ResourceName'])
    recentActiveVolumeSet = set(recentActiveVolumeList) # remove duplicates
    return recentActiveVolumeSet

def identifyAgedVolumes(availableVolList, activeVolList):
    # remove and return EBS volumes which are recently active from the list of available volumes
    if len(availableVolList) == 0:
        return None
    else:
        agedVolumes = list(set(availableVolList) - set(activeVolList))
        return agedVolumes

def buildOpsEntries(vols, rgn, acctID):
    # construct the entry for the OpsItem resource list, using full ARNs for each EBS volume
    resourceList = []
    for v in vols:
        volArn = "\"arn:aws:ec2:" + rgn + ":" + acctID + ":volume/" + v + "\""
        resourceList.append({"\"arn\"": volArn})
    return str(resourceList).translate(str.maketrans({"'":None}))

def splitter(volList, splitSize = 100):
    # splits a list into groups of splitSize, 100 by default; min splitSize is 1 and max splitSize is 100
    if(splitSize < 1 or splitSize > 100):
        splitSize = 100
    iters = [iter(volList)]*splitSize
    return list(itertools.zip_longest(*iters))

def detailedNotifier(volList):
    # sends a list of volumes to the SNS topic for review outside of OpsCenter
    sns = boto3.client('sns')
    message = "The following volumes are flagged as non-compliant: " + ', '.join(volList)
    try:
        response = sns.publish(
            TopicArn=os.environ["SNS_ARN"],
            Message=message,
        )
        return response
    except ClientError as err:
        print(err)

def validateEnvironmentVariables():
    if(int(os.environ["IGNORE_WINDOW"]) < 1 or int(os.environ["IGNORE_WINDOW"]) > 90):
        print("Invalid value provided for IGNORE_WINDOW. Please choose a value between 1 day and 90 days.")
        raise ValueError('Bad IGNORE_WINDOW value provided')
    if(int(os.environ["BATCH_SIZE"]) < 1 or int(os.environ["BATCH_SIZE"]) > 100):
        print("Invalid value provided for BATCH_SIZE. Please choose a value between 1 and 100.")
        raise ValueError('Bad BATCH_SIZE value provided')
    if(os.environ["DETAILED_NOTIFICATIONS"].upper() not in ["TRUE", "FALSE"]):
        print("Invalid value provided for DETAILED_NOTIFICATIONS. Please choose TRUE or FALSE.")
        raise ValueError('Bad DETAILED_NOTIFICATIONS value provided')
        
def lambda_handler(event, context):
    # gather data to build OpsItem request
    print("boto3 version:"+boto3.__version__)
    print("botocore version:"+botocore.__version__)
    acctID = context.invoked_function_arn.split(":")[4]
    rgn = os.environ["AWS_REGION"] # used with Lambda to get the current region
    opscenter = boto3.client('ssm', region_name=rgn) # boto3.client('opscenter', region_name=rgn)
    snsArn = [{"Arn": os.environ["SNS_ARN"]}] # used with Lambda to get desired SNS topic ARN
    opsItemTemplate = {}
    opsItemTemplate["/aws/automations"] = {"Value": "[{\"automationType\": \"AWS:SSM:Automation\", \"automationId\": \"" + os.environ["SSM_AUTOMATION_ID"] + "\"}]"}
    opsItemTemplate["VolumeDetails"] = {"Value": "[{\"NON-COMPLIANT\"}]"}
    opsItemTemplate["/aws/dedup"] = {"Type": "SearchableString", "Value": "{\"dedupString\": \"EBS-Aged-Volume-Finder-Non-Compliant-Volumes\"}"}
    # validate environment variables
    try:
        validateEnvironmentVariables()
    except ValueError as vErr:
        print(vErr)
        sys.exit(1)
    # collect available EBS volumes and attachment history
    startDateTime = datetime.today() - timedelta(int(os.environ["IGNORE_WINDOW"])) # IGNORE_WINDOW defined in environment variables
    eventList = getCloudTrailEvents(startDateTime, rgn)
    activeVols = getRecentActiveVolumes(eventList)
    availableVols = getAvailableVolumes(rgn)
    flaggedVols = identifyAgedVolumes(availableVols, activeVols)
    flaggedVols.sort()
    
    # process EBS volumes and create OpsItems
    splitList = splitter(flaggedVols, int(os.environ["BATCH_SIZE"]))
    for i in splitList:
        opsData = {}
        processedVols = list(filter(None, i))
        opsData["Value"] = buildOpsEntries(processedVols, rgn, acctID) 
        opsItemData = opsItemTemplate
        opsItemData["/aws/resources"] = opsData
        description = "Unused EBS volume identifier" 
        title = "EBS Volumes older than " + os.environ["IGNORE_WINDOW"] + " days."
        try:
            print(opscenter.create_ops_item(Description=description, Title=title, Priority=2, Notifications=snsArn, Source="EBS", OperationalData=opsItemData))
        except ClientError as err:
            if err.response['Error']['Code'] == "OpsItemAlreadyExistsException":
                print("OpsItem already exists, skipping this batch.")
            else:
                print(err)
        if(os.environ["DETAILED_NOTIFICATIONS"].upper() == "TRUE"):
            try:
                print(detailedNotifier(processedVols))
            except ClientError as err:
                print(err)