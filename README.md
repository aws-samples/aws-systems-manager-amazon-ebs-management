# AWS Systems Manager Amazon EBS Volume Management

Example Lambda function to help control your AWS costs by identifying unused Amazon Elastic Block Store (EBS) volumes. 

## Getting Started

These instructions will help you set up a Lambda function to identify available and unused EBS volumes. Please review [Controlling Your AWS Costs by Deleting Unused Amazon EBS Volumes](https://aws.amazon.com/blogs/mt/controlling-your-aws-costs-by-deleting-unused-amazon-ebs-volumes/) on the [AWS Blog](https://aws.amazon.com/blogs/) for a detailed walkthrough of the solution.

### Prerequisites

Before getting started, please make sure you've completed the following:

* Install [Python 3](https://www.python.org/downloads/)
* Install the [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html)

### Creating the Lambda Function

1. Create the IAM Role
    * Navigate to IAM and create a role for Lambda function execution with the [JSON policy](executionrole.json). This policy grants the Lambda function the basic execution role, the ability to read CloudTrail logs, and the ability to access EC2 resources such as EBS volume and Systems Manager. For more information, see Create and Attach Your First Customer Managed Policy.

1. Navigate to the Lambda console and create a function with following basic details as shown in the following screenshot:
    1. For Function name, enter opsCenterAgedEBSVolumeFinder.
    1. For Runtime, from the dropdown list, select Python 3.6 or Python 3.7.
    1. Under Permissions:
    1. For Execution role, from the dropdown list, select Use an existing role.
        * For Existing role, select the role created in the previous step for the Lambda function.
    1. Choose Create Function.
1. Next, in the Lambda console of the newly created function, scroll down to the Environment variables section and enter the following four key-value parameters:
    * For BATCH_SIZE, enter 20. This parameter refers to the number of EBS volumes batched together by the Lambda function into one OpsItems event published to Systems Manager OpsCenter. The maximum Batch Size is 100.
    * For DETAILED_NOTIFICATIONS, enter True to send a detailed notification to the SNS topic. Alternatively, you can send a brief notification by entering False.
    * For IGNORE_WINDOW, enter 15. This parameter specifies how far back the Lambda function should look into the CloudTrail logs. Choose between 0 to 90 days. CloudTrail logs are retained for a maximum of 90 days.
    * For SNS_ARN, provide the ARN of the SNS topic you created in step 1.
    * For SSM_AUTOMATION_ID, enter AWS-CreateSnapshot. Provide the default Automation document you want to associate with the OpsItems that the Lambda function writes to the OpsCenter. In this blog post, we use a preexisting automation document to create a snapshot of the EBS volume. Using the Systems Manager Automation Documents Reference, you can create custom document, upload it to Systems Manager, and associate that with your OpsItems as the default Automation action.
1. In the Lambda console, scroll down to the Function Code section, and under Handler, update to opsCenterAgedEBSVolumeFinder.lambda_handler, as shown in the following diagram.
1. In the Lambda console, under Basic settings, update Memory to 256 MB and Timeout to 3 Choose Save to update the function.
1. In a new directory/folder in your laptop or EC2 instance, download the script for the Lambda function to examine your CloudTrail logs to identify the unused EBS volumes, and follow the steps: 
    * Navigate to the folder where you saved the Python file and create a requirements.txt file with the following botocore, boto3, and awscli versions to run the function:
      ```
      boto3==1.9.170
      botocore==1.12.171
      awscli==1.16.181
      ```
    * Save this file in the same directory as the Lambda function. The requirements.txt file is necessary to ensure that the Lambda execution environment has the necessary versions of the libraries packaged together for the function to execute correctly. For a quick rundown on packaging boto3 and botocore, see [Automate your DynamoDB backups with Serverless in less than 5 minutes](https://serverless.com/blog/automatic-dynamodb-backups-serverless/).
      * Note - As long as you use a version equal to or later than the ones specified here for boto3, botocore, and awscli, you can use that to package the Lambda function.
    * From the directory where you placed the Lambda function and the requirements.txt file, run the following command to create local copies of the boto3, botocore, and awscli packages (include the “.” at the end):

      **MacOS/Linux:** `pip install --upgrade -r requirements.txt -t .`
      **Windows:** `pip install -r requirements.txt -t .`

    * Recursively zip the contents of the directory where the Lambda function resides to create a deployment package using the following command, which is run from the Lambda function’s directory (include the “.” at the end):
    
      **MacOS/Linux:** `zip -r9 ../opsCenterAgedEBSVolumeFinder.zip .`
      **Windows:**  `7z.exe a -r c:\code\opsCenterAgedEBSVolumeFinder.zip .`

    * Upload the package to Lambda by updating the existing function (replace your function name, Region, and zip file name if needed), running this command from where the zip file exists:

      ```
      aws lambda update-function-code --region us-west-2 --function-name opsCenterAgedEBSVolumeFinder —zip-file fileb://opsCenterAgedEBSVolumeFinder.zip
      ```
      
1. After the package successfully uploads, navigate to the console and test the Lambda function.
   * To manually invoke your Lambda function, choose Test
   * Choose Create a new test event and leave the default template in place.
   * Enter an Event name, then choose Create.
   * Choose Test to invoke the Lambda function.

## Credit

Ballu Singh, Principal Solutions Architect, AWS

Sona Rajamani, Senior Solutions Architect, AWS

Joshua Zeiser, Senior Technical Account Manager, AWS

## License

This sample code is made available under the MIT-0 license. See the [LICENSE](LICENSE.md) file for details
