from string import Template
import json
import ipaddress
 
# jsonを読み込む
with open('./param.json', "r") as f:
    json_ary = json.load(f)
# テンプレートを読み込む
with open('./template.txt', "r") as f:
    tmpl = Template(f.read())
# 設定するVLANの数だけループ
for json_data in json_ary:
    # ipアドレス情報を扱うオブジェクトを設定
    ip_obj = ipaddress.ip_interface(json_data['ip'])
    # テンプレート内の変数を該当のパラメータに置換する
    config = tmpl.substitute(
        json_data,
        # IPアドレスとサブネットマスクを設定
        ip = ip_obj.with_netmask.replace('/', ' '),
        # VLANを設定
        vlan = json_data['vlan'],
        # PORTを設定
        port = json_data['port'],
        # パラメータにnoを設定することで設定削除が可能。(今回は追加のため空白)
        no = json_data['no']
    )
    # ホスト名でファイルを書き込む
    with open(json_data['host'] + '.txt', "a") as f:
        f.write(config)
