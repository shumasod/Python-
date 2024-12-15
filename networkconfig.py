import PySimpleGUI as sg
from ncclient import manager
import xml.dom.minidom

def apply_config(values):
    payload = f"""
    <config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
      <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
        <ip>
          <route>
            <ip-route-interface-forwarding-list>
              <prefix>{values['prefix']}</prefix>
              <mask>{values['mask']}</mask>
              <fwd-list>
                <fwd>{values['forward']}</fwd>
              </fwd-list>
            </ip-route-interface-forwarding-list>
          </route>
        </ip>
      </native>
    </config>
    """
    
    try:
        with manager.connect(host=values['host'], port=830, username=values['username'], 
                             password=values['password'], hostkey_verify=False, 
                             device_params={'name': 'iosxe'}) as m:
            response = m.edit_config(target='running', config=payload)
            return "設定が正常に適用されました。"
    except Exception as e:
        return f"エラーが発生しました: {str(e)}"

layout = [
    [sg.Text('ホスト:'), sg.Input(key='host')],
    [sg.Text('ユーザー名:'), sg.Input(key='username')],
    [sg.Text('パスワード:'), sg.Input(key='password', password_char='*')],
    [sg.Text('プレフィックス:'), sg.Input(key='prefix')],
    [sg.Text('マスク:'), sg.Input(key='mask')],
    [sg.Text('転送先:'), sg.Input(key='forward')],
    [sg.Button('設定適用'), sg.Button('終了')],
    [sg.Output(size=(60,10))]
]

window = sg.Window('ネットワーク設定ツール', layout)

while True:
    event, values = window.read()
    if event == sg.WINDOW_CLOSED or event == '終了':
        break
    if event == '設定適用':
        result = apply_config(values)
        print(result)

window.close()