from ncclient import manager

payload = """
<config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
    <ip>
      <route>
        <ip-route-interface-forwarding-list>
          <prefix>1.1.1.1</prefix>
          <mask>255.255.255.255</mask>
          <fwd-list>
            <fwd>Null0</fwd>
          </fwd-list>
        </ip-route-interface-forwarding-list>
        <ip-route-interface-forwarding-list>
          <prefix>1.1.1.2</prefix>
          <mask>255.255.255.255</mask>
          <fwd-list>
            <fwd>Null0</fwd>
          </fwd-list>
        </ip-route-interface-forwarding-list>
        <ip-route-interface-forwarding-list>
          <prefix>1.1.1.3</prefix>
          <mask>255.255.255.255</mask>
          <fwd-list>
            <fwd>Null0</fwd>
          </fwd-list>
        </ip-route-interface-forwarding-list>
      </route>
    </ip>
</native>
</config>
"""

# Connect to NETCONF agent on the router
with manager.connect(
    host='172.16.62.151',
    port=830,
    username='cisco',
    password='cisco',
    hostkey_verify=False,
    device_params={'name': 'iosxe'}
) as m:
    print('###########################################################################')
    print('### XML')
    print('###########################################################################')
    # Edit configuration
    response = m.edit_config(target='running', config=payload).xml
    print(response)

    print('###########################################################################')
    print('### XML Formatstring')
    print('###########################################################################')
    # Print formatted XML
    data = m.get_config(source='running').data_xml
    print(data)
