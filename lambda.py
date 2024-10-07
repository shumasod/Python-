import json
import boto3

def lambda_handler(event, context):
    client = boto3.client('elbv2')
    # 変更前のルールの優先順位を取得して保存
    original_rule_priorities = {}
    response = client.describe_rules(
        ListenerArn='ALBリスナーのARN',
    )
    for rule in response['Rules']:
        original_rule_priorities[rule['RuleArn']] = rule['Priority']

    # 作業が終了した後、優先順位をデフォルトに戻す
    def reset_rule_priorities(default_rule_priorities):
        response = client.set_rule_priorities(
            RulePriorities=default_rule_priorities
        )
        return response

    try:
        # リスナールールの自動切換えが行われるため、手動で優先順位を変更する必要はありません。

        # 作業が終了した後、優先順位をデフォルトに戻す
        reset_rule_priorities([
            {'RuleArn': rule_arn, 'Priority': priority} 
            for rule_arn, priority in original_rule_priorities.items()
        ])

        return {
            'statusCode': 200,
            'body': json.dumps('リスナールールの変更が完了し、優先順位がデフォルトに戻りました。')
        }
    except Exception as e:
        # エラーが発生した場合、優先順位をデフォルトに戻す
        reset_rule_priorities([
            {'RuleArn': rule_arn, 'Priority': priority} 
            for rule_arn, priority in original_rule_priorities.items()
        ])

        return {
            'statusCode': 500,
            'body': json.dumps(f'エラーが発生しました: {str(e)}')
        }
