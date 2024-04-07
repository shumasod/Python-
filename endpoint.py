import subprocess
import boto3

get_rds_endpoints = lambda region, db_instance_identifier: boto3.client('rds', region_name=region).describe_db_instances(DBInstanceIdentifier=db_instance_identifier)['DBInstances'][0]['Endpoint']['Address']

def switch_rds_endpoint(profile, region, db_instance_identifier):
    """
    RDSエンドポイントを表示し、AWS CLIで設定を切り替える関数
    """
    # RDSエンドポイントの取得
    endpoint = get_rds_endpoints(region, db_instance_identifier)

    if endpoint:
        # エンドポイントを表示
        print(f"RDS Endpoint: {endpoint}")

        # AWS CLIでプロファイルごとのデフォルトリージョンを設定
        subprocess.run(['aws', 'configure', 'set', 'default.region', region, '--profile', profile])

        # AWS CLIでRDSエンドポイントを設定
        subprocess.run(['aws', 'configure', 'set', f'aws_rds_endpoint={endpoint}', '--profile', profile])

        print(f"Switched to RDS Endpoint: {endpoint}")
    else:
        print(f"Error: Unable to retrieve RDS Endpoint for {db_instance_identifier}")

if __name__ == "__main__":
    # 以下の変数を適切な値に変更してください
    aws_profile = "your_aws_profile"
    aws_region = "your_aws_region"
    rds_instance_identifier = "your_rds_instance_identifier"

    switch_rds_endpoint(aws_profile, aws_region, rds_instance_identifier)
