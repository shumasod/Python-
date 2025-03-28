import subprocess
import boto3

def get_rds_endpoint(region, db_instance_identifier):
    rds_client = boto3.client('rds', region_name=region)
    response = rds_client.describe_db_instances(DBInstanceIdentifier=db_instance_identifier)
    if response['DBInstances']:
        return response['DBInstances'][0]['Endpoint']['Address']
    return None

def switch_rds_endpoint(profile, region, db_instance_identifier):
    """ Display RDS endpoint and switch configuration using AWS CLI """
    # Get RDS endpoint
    endpoint = get_rds_endpoint(region, db_instance_identifier)
    if endpoint:
        # Display endpoint
        print(f"RDS Endpoint: {endpoint}")
        # Set default region for the profile using AWS CLI
        subprocess.run(['aws', 'configure', 'set', 'region', region, '--profile', profile])
        # Set RDS endpoint for the profile using AWS CLI
        subprocess.run(['aws', 'configure', 'set', f'aws_rds_endpoint={endpoint}', '--profile', profile])
        print(f"Switched to RDS Endpoint: {endpoint}")
    else:
        print(f"Error: Unable to retrieve RDS Endpoint for {db_instance_identifier}")

if __name__ == "__main__":
    # Replace with appropriate values
    aws_profile = "your_aws_profile"
    aws_region = "your_aws_region"
    rds_instance_identifier = "your_rds_instance_identifier"
    switch_rds_endpoint(aws_profile, aws_region, rds_instance_identifier)