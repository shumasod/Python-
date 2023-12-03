[ NETCONF ]
NETCONFのPythonコード
下記がNETCONFのスクリプト本体です。


#!/usr/bin/env python

from ncclient import manager
from xml.dom import minidom
import lxml.etree as ET
import xmltodict

payload = """
<config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <ip>
        <route>
          <ip-route-interface-forwarding-list xc:operation="delete">
          <prefix>1.1.1.1</prefix>
            <mask>255.255.255.255</mask>
          </ip-route-interface-forwarding-list>
          <ip-route-interface-forwarding-list xc:operation="delete">
          <prefix>1.1.1.2</prefix>
            <mask>255.255.255.255</mask>
          </ip-route-interface-forwarding-list>
          <ip-route-interface-forwarding-list xc:operation="delete">
          <prefix>1.1.1.3</prefix>
            <mask>255.255.255.255</mask>
          </ip-route-interface-forwarding-list>
        </route>
      </ip>
</native>
</config>
"""

# connect to netconf agent
m = manager.connect(host='172.16.62.151', port=830, username='cisco', password='cisco', hostkey_verify=False, device_params={'name': 'iosxe'})

#response = m.get_config(source='running', filter=payload)
print '###########################################################################'
print '### XML'
print '###########################################################################'
response = m.edit_config(target='running', config=payload).xml
print response

print '###########################################################################'
print '### XML Formatstring'
print '###########################################################################'
data = ET.fromstring(response)
print(ET.tostring(data, pretty_print=True))

