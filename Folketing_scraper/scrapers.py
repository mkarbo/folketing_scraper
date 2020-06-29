from bs4 import BeautifulSoup
import requests
from requests import ReadTimeout
import re
import json
import urllib3
import time
#ft.dk blocks all requests with verify=True, and we will thus get warning for each requests.get call
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class base_scraper:

    def __init__(self):
        pass
    
    def _request_timeout(self, url, tries=1):
        if tries == 5:
            raise Exception('5 retries in a row')
        try:
            return requests.get(url, verify=False, timeout=(8,8))
        except ReadTimeout:
            print(f'\nRequest timeout (>8 sec). This is attempt number {tries}. Sleeping for {10*(tries)} and trying again on\n- {url}\n')
            # sleep for a bit in case that helps
            time.sleep(10*(tries))
            # try again
            tries += 1
        return self._request_timeout(url, tries)

class FT_PartyID_Scraper(base_scraper):
    """
    A simple webscraper for www.ft.dk, which gathers content from search function via party ID.

    This will scrape a list of members, their current party including party ID and member ID from ft.dk.
    """
    def __init__(self, party_id, sleep_timer = 0.1):
        self.url_template = 'https://www.ft.dk/searchResults.aspx?sortedDescending=false&party={{{party_id}}}&page=1&sortedBy=&pageSize=200'
        self.page = None # build by self.get_page
        self.soup = None # build by self.get_soup
        self.base_url = 'https://ft.dk/'
        self.party_id = party_id # required for self.get_page

    def get_page(self, party_id=None):
        url = self.url_template.format(party_id=(party_id if party_id else self.party_id))
        print(f'Requestion page: {url}')
        page = self._request_timeout(url)
        self.page = page
        return page
    
    def setup_soup(self):
        if self.page is None:
            raise Exception('Page not downloaded yet - can not setup BS4 Soup')
        else:
            self.soup = BeautifulSoup(self.page.content, 'html.parser')

    def find_table_rows(self):
        if self.soup is None:
            raise Exception('Soup not found - please initiate soup before looking for tables')
        else:
            table_rows = self.soup.findAll(attrs={'data-item-url': re.compile('^https://www.ft.dk/medlemmer/')})
            self.table_rows = table_rows
            return table_rows

    def parse_table_rows(self):
        def _parse_row(row):
            output = {}
            attrs = row.attrs
            page_url = attrs.get('onclick').split('(')[-1].strip(')').strip('\'')
            output['page_url'] = page_url
            link = attrs.get('data-item-url')
            children = [a for a in row.children if a != '\n']
            img_attr = children[0].find_all('img')[0].attrs
            output['img_alt'] = img_attr.get('alt')
            
            img_url = '{base_url}{img_src}'.format(
                base_url=self.base_url,
                img_src=img_attr.get('src')
            )
            output['img_url'] = img_url
            

            output['first_name'] = children[1].text
            output['last_name'] = children[2].text
            output['party'] = children[3].text
            output['party_id'] = self.party_id
            output['role'] = children[4].text
            try:
                output['contact'] = ' '.join(
                    list(children[5].children)[1].text.split()
                )
            except Exception:
                pass
            return output
        if self.table_rows is None:
                raise Exception('Table rows not found - please run .find_table_rows first')
        else:
            outputs = []
            trs = self.table_rows
            for trow in trs:
                outputs.append(_parse_row(trow))
            self.output = outputs
            return outputs

    def get_member_id(self, member_url):
        print(f'Requesting page: {member_url}')
        result = self._request_timeout(member_url)
        soup = BeautifulSoup(result.content, 'html.parser')
        #Should only be one such match as of date 29-06-2020
        member_content = soup.findAll(attrs={'class': 'ftMember__accordion__container panel-group'})[0]
        minister_id_http = member_content.find_all('a', attrs={'href': re.compile('\?mi={\S{1,}?')})[0].get('href')
        #Searches for something of the form '^*mi={ID}$'
        minister_id = re.search('(mi={)(.*)}$', minister_id_http).group(2)
        return minister_id

    def iter_member_ids(self, rows):
        """
        To be used on parse_table_rows output.
        This method will iterate over output and apply .get_member_id to retrieve member ID.
        """
        new_rows = []
        for row in rows:
            url = row.get('page_url')
            row['member_id'] = self.get_member_id(member_url=url)
            new_rows.append(row)
        return new_rows



    def run(self):
        self.get_page()
        self.setup_soup()
        self.find_table_rows()
        output = self.parse_table_rows()
        output = self.iter_member_ids(output)
        return output
    

class JSON_FT_scraper:
    def __init__(self, json_path, key='id'):
        with open(json_path, 'r') as jsonfile:
            data = json.loads(jsonfile.read())
        self.ids = [entry.get(key) for entry in data]

    def run(self):
        outputs = []
        for party_id in self.ids:
            ft = FT_PartyID_Scraper(party_id=party_id)
            outputs.extend(ft.run())
        return outputs

    def run_and_save(self, output_path=None):
        if output_path is None:
            output_path = 'output_scrape_ftdk.json'
        outputs = self.run()

        json_dump = json.dumps(outputs, ensure_ascii=False).replace('},', '},\n')
        with open(output_path, 'w') as file:
            file.write(json_dump)
        
class FT_MemberID_Scraper_Base(base_scraper):

    def __init__(self, member_URL, member_ID):
        self.url = member_URL
        self.id = member_ID
        self.content = self._request_timeout(member_url)
        self.soup = BeautifulSoup(content.content, 'html.parser')
        self.initial_block = self._get_initial_block

        self.base_urls = {
            'questions': {
                'all': f'{self.url.rstrip('/')}/dokumenter/alle_spoergsmaal?mi={{{self.id}}}&pageSize=10000',
                'udvalgsspoergsmaal': f'{self.url.rstrip('/')}/dokumenter/udvalgsspoergsmaal?mi={{{self.id}}}&pageSize=10000',
                'samraadsspoergsmaal': f'{self.url.rstrip('/')}/dokumenter/samraadsspoergsmaal?mi={{{self.id}}}&pageSize=10000',
                'paragraf_20_spoergsmaal': f'{self.url.rstrip('/')}/dokumenter/paragraf_20_spoergsmaal?mi={{{self.id}}}&pageSize=10000'
            },
            'forslag': {
                'lovforslag': f'{self.url.rstrip('/')}/dokumenter/lovforslag?mi={{{self.id}}}&pageSize=10000',
                'beslutningsforslag': f'{self.url.rstrip('/')}/dokumenter/beslutningsforslag?mi={{{self.id}}}&pageSize=10000',
                'forespoergsler': f'{self.url.rstrip('/')}/dokumenter/forespoergsler?mi={{{self.id}}}&pageSize=10000',
                'forespoergsler': f'{self.url.rstrip('/')}/dokumenter/forespoergsler?mi={{{self.id}}}&pageSize=10000',
                'redegoerelser': f'{self.url.rstrip('/')}/dokumenter/redegoerelser?mi={{{self.id}}}&pageSize=10000',
                'forslag_til_vedtagelse': f'{self.url.rstrip('/')}/dokumenter/forslag_til_vedtagelse?mi={{{self.id}}}&pageSize=10000',
                'alleforslag': f'{self.url.rstrip('/')}/dokumenter/alleforslag?mi={{{self.id}}}&pageSize=10000'
            },
            'taler_og_stemmer':{
                'ordfoerertaler': f'{self.url.rstrip('/')}/dokumenter/ordfoerertaler?mi={{{self.id}}}&pageSize=10000',
                'alletaler': f'{self.url.rstrip('/')}/dokumenter/alletaler?mi={{{self.id}}}&pageSize=10000',
                'afstemninger': f'{self.url.rstrip('/')}/dokumenter/afstemninger?mi={{{self.id}}}&pageSize=10000',
            }
        }
        # sessions can be either 20xx1 or 20xx2 (depending on how the year progressed, sometimes it will only have 1 session, however query will just return 0)
        self.periods= [f'{x}{i}' for x in range(2005,2022) for i in range(1,3)]

        
    
    def _get_initial_block(self):
        result = self.soup.findAll('div', attrs={'class': 'ftMember__accordion__container panel-group'})
        return result

class FT_MemberID_QuestionScraper(FT_MemberID_Scraper_Base):

    def __init__(self, *args, **kwargs):
        FT_MemberID_Scraper_Base.__init__(*args, **kwargs) #init super class

    def lovforslag_scraper


    










    



