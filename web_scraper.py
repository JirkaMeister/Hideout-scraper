#	File name:	product_scraper.py
#	Author:     Jiří Charamza
#   Brief:      Web scraper for getting hideout zones requirments

import httpx
from bs4 import BeautifulSoup
from bs4 import element
import sys
import time
import json

def create_id(name: str):
    # Create a unique ID for the zone based on its name
    return name.lower().replace(' ', '_').replace('\"', '')

class HideoutZone:
    def __init__(self, name):
        self.id = create_id(name)
        self.name = name
        self.requirements = []
    
    def add_zone_level(self):
        self.requirements.append([])

    def add_requirement(self, requirement_li, level):
        try:
            # Adjust level to match the index in requirements list
            level -= 1 
            new_requirement = ZoneRequirement(
                ZoneRequirement.get_name(requirement_li),
                ZoneRequirement.get_level_or_quantity(requirement_li),
                ZoneRequirement.get_type(requirement_li),
                ZoneRequirement.get_link(requirement_li)
            )
            self.requirements[level].append(new_requirement)
        except:
            print(f"Error processing requirement: {requirement_li}", file=sys.stderr)

    def print_zone_info(self):
        print(f"Zone ID: {self.id}")
        print(f"Zone Name: {self.name}")
        print("Requirements:")
        if len(self.requirements) > 0:
            for level, reqs in enumerate(self.requirements):
                print(f"  Level {level + 1}:")
                for req in reqs:
                    print(f"    - {req}")

    def to_dict(self):
        requirements_dict = []
        for level, reqs in enumerate(self.requirements):
            level_reqs = {
                'level': level + 1,
                'requirements': [req.to_dict() for req in reqs]
            }
            requirements_dict.append(level_reqs)
        
        return {
            'id': self.id,
            'name': self.name,
            'level_requirements': requirements_dict
        }

class ZoneRequirement:
    def __init__(self, name, number, req_type, link=None):
        self.id = create_id(name)
        self.name = name
        self.number = number
        if req_type == None:
            raise Exception("Invalid requirement type")
        self.type = req_type
        self.link = link
        if req_type == 'item':
            self.img = self.get_img()
        else:
            self.img = None
    
    def get_name(list_item: element.Tag):
        # Name of the requirement is the text of the <a> tag
        return list_item.find('a').text.strip() if list_item.find('a') else 'N/A'

    def get_level_or_quantity(list_item: element.Tag):
        # If the first element is a string - quantity of the item  
        if type(list_item.contents[0]) == element.NavigableString:
            return list_item.contents[0] if list_item.contents else 'N/A'
        # Otherwise the last element is the level of trader/skill/zone
        else:
            return list_item.contents[-1] if list_item.contents else 'N/A'
    
    def get_type(list_item: element.Tag):
        if list_item :
            # Traders and skills start with <a> tag
            if type(list_item.contents[0]) == element.Tag:
                if 'LL' in list_item.contents[-1]:
                    return 'trader'
                elif 'Level' in list_item.contents[-1]:
                    return 'skill'
            # Items start with a number
            elif list_item.contents[0][0].isnumeric():
                return 'item'
            # Zones start with 'Level'
            elif 'Level' in list_item.contents[0]:
                return 'zone'
            else:
                return None
            
    def get_link(list_item: element.Tag):
        for content in list_item.contents:
            if type(content) == element.Tag and content.name == 'a':
                return content['href'] if 'href' in content.attrs else None
        return None
    
    def get_img(self):
        if self.link:
            url = 'https://escapefromtarkov.fandom.com' + self.link
            response = httpx.get(url)
            soup = BeautifulSoup(response.content, 'html.parser')
            img = soup.select('td.va-infobox-icon a img')
            if img:
                return img[0]['src'] if 'src' in img[0].attrs else None
        return None

    
    def __repr__(self):
        if self.type == 'items':
            return f"{self.number}x {self.name}"
        return f"{self.name} {self.number}"
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'number': self.number,
            'type': self.type,
            'img': self.img
        }


def get_zone_tables(url: str):
    response = httpx.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    parent_div = soup.find('div', class_='wds-tabber dealer-tabber')
    zone_divs = parent_div.find_all('div', class_='wds-tab__content')
    zone_tables = [zone_div.find('table', class_='wikitable') for zone_div in zone_divs]
    return zone_tables

def extract_zone_info(zone_table):
    zones = []
    for table in zone_table:
        # Name of the zone is the first row of the table
        header_row = table.select('tr:first-child th')
        zone_name = header_row[0].contents[0].strip()

        zone = HideoutZone(zone_name)

        # First table of requirements are in the third row of the table
        requirements_levels = []
        i = 0
        while True:
            requirement_list = table.select(f'tr:nth-child({i + 3}) td:first-of-type ul li')
            if not requirement_list:
                break
            requirements_levels.append(requirement_list)
            zone.add_zone_level()
            i += 1

        for level, requirements_list in enumerate(requirements_levels, start=1):
            for requirement in requirements_list:
                zone.add_requirement(requirement, level)

        zone.print_zone_info()
        zones.append(zone)

    return zones


if __name__ == '__main__':
    url = 'https://escapefromtarkov.fandom.com/wiki/Hideout'
    retries = 0
    zones = []

    # Retry up to 3 times in case of an error
    while retries < 3:
        try:
            zone_tables = get_zone_tables(url)
            zones = extract_zone_info(zone_tables)
            break
        except Exception as e:
            retries += 1
            print(f'Error scraping: {e}', file=sys.stderr)
            time.sleep(1)

    with open('hideout_zones.json', 'w') as f:
        json.dump([zone.to_dict() for zone in zones], f, indent=2, ensure_ascii=False)