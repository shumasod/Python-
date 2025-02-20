#!/usr/bin/python
import requests
import sys
import os

# Disable warnings from SSL/TLS certificates
requests.packages.urllib3.disable_warnings()

# The IP address or hostname of the networking device
HOST = 'privateIP'

# Use environment variables to access the networking device credentials
USER = os.getenv('NETWORK_USER', 'default_user')
PASS = os.getenv('NETWORK_PASS', 'default_pass')
PORT = 443

def main():
    """Main method that retrieves the interface details from a networking device via RESTCONF."""

    # RESTCONF URL of the networking device
    url = f"https://{HOST}:{PORT}/restconf/data/Cisco-IOS-XE-native:native/ip/route/ip-route-interface-forwarding-list"

    # RESTCONF media types for REST API headers
    headers = {
        'Content-Type': 'application/yang-data+json',
        'Accept': 'application/yang-data+json'
    }

    try:
        # Perform a GET request on the specified URL
        response = requests.get(url, auth=(USER, PASS), headers=headers, verify=False)
        response.raise_for_status()  # Raise an exception for HTTP errors

        # Print the JSON that is returned
        print(response.text)
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    sys.exit(main())
