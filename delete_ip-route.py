#!/usr/bin/python
import requests
import sys
import json

# disable warnings from SSL/TLS certificates
requests.packages.urllib3.disable_warnings()

# the IP address or hostname of the networking device
HOST = 'IP'

# use your user credentials to access the networking device
USER = 'cisco'
PASS = 'cisco'
PORT = 443

# create a main() method
def main():
    """Main method that retrieves the interface details from a
    networking device via RESTCONF."""

    # RESTCONF url of the networking device
    url = "https://{h}:{p}/restconf/data/Cisco-IOS-XE-native:native/ip/route/ip-route-interface-forwarding-list=1.1.1.1,255.255.255.255".format(h=HOST, p=PORT)

    # RESTCONF media types for REST API headers
    headers = {'Content-Type': 'application/yang-data+json',
               'Accept': 'application/yang-data+json'}

    # this statement performs a PATCH on the specified url
    response = requests.delete(url, auth=(USER, PASS),
                            headers=headers, verify=False)

    # print the json that is returned
    print(response)

if __name__ == '__main__':
    sys.exit(main())
