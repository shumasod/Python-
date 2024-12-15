import time
import requests
from bs4 import BeautifulSoup

url = "https://example.com"
class_name = 'div.newUserPageProfile_info_body.newUserPageProfile_description'
file = "elems_text.txt"

def is_changed(old_elem, new_elem):
    return old_elem != new_elem

def set_old_elems():
    try:
        with open(file) as f:
            old_elems = f.read()
            print(f'{"old_elem":10} : {old_elems}')
    except FileNotFoundError:
        old_elems = ''
    return old_elems

def set_new_elems():
    response = requests.get(url)
    response.encoding = response.apparent_encoding
    bs = BeautifulSoup(response.text, 'html.parser')
    new_elems = str(bs.select(class_name))
    print('{"new_elem":10} : {}'.format(new_elems))
    return new_elems

def display_result(old_elem, new_elem):
    if is_changed(old_elem, new_elem):
        with open(file, 'w') as f:
            f.write(new_elem)
        print("Change is detected!!")
    else:
        print("not changed...")

if __name__ == '__main__':
    try:
        while True:
            print("=" * 100)
            new_elems = set_new_elems()
            old_elems = set_old_elems()
            display_result(old_elems, new_elems)
            time.sleep(20)
    except (KeyboardInterrupt, Exception) as e:
        print(f"Error: {e}")
