from bs4 import BeautifulSoup, Comment
import requests
from requests import ReadTimeout
import re
import json
import urllib3
import time
import functools
#ft.dk blocks all requests with verify=True, and we will thus get warning for each requests.get call unless we disable ssl verification
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class base_scraper:

    def __init__(self):
        self.base_url = 'https://ft.dk/'
    
    def _request_timeout(self, url, tries=1):
        if tries == 5:
            raise Exception('5 retries in a row')
        try:
            print(f'\nAttempting to request site\n - {url}')
            return requests.get(url, verify=False, timeout=(8,8))
        except ReadTimeout:
            print(f'\nRequest timeout (>8 sec). This is attempt number {tries}. Sleeping for {10*(tries)} and trying again on\n- {url}\n')
            # sleep for a bit in case that helps
            time.sleep(10*(tries))
            # try again
            tries += 1
        return self._request_timeout(url, tries)
    
    def has_comment(self, soup_object, comment: str):
        comments = soup_object.findAll(text=lambda text:isinstance(text, Comment))
        return bool(comment in comments)



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
            print(link) 
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
        self.content = self._request_timeout(self.url)
        self.soup = BeautifulSoup(self.content.content, 'html.parser')
        self.initial_block = self._get_initial_block()
        self.data = {}
        self.data['member_id'] = self.id
        self.data['member_url'] = self.url

        self.base_urls = {
            'questions': {
                'all': f'{self.url}/dokumenter/alle_spoergsmaal?mi={{{self.id}}}&pageSize=10000',
                'udvalgsspoergsmaal': f'{self.url}/dokumenter/udvalgsspoergsmaal?mi={{{self.id}}}&pageSize=10000',
                'samraadsspoergsmaal': f'{self.url}/dokumenter/samraadsspoergsmaal?mi={{{self.id}}}&pageSize=10000',
                'paragraf_20_spoergsmaal': f'{self.url}/dokumenter/paragraf_20_spoergsmaal?mi={{{self.id}}}&pageSize=10000'
            },
            'forslag': {
                'lovforslag': f'{self.url}/dokumenter/lovforslag?mi={{{self.id}}}&pageSize=10000',
                'beslutningsforslag': f'{self.url}/dokumenter/beslutningsforslag?mi={{{self.id}}}&pageSize=10000',
                'forespoergsler': f'{self.url}/dokumenter/forespoergsler?mi={{{self.id}}}&pageSize=10000',
                'redegoerelser': f'{self.url}/dokumenter/redegoerelser?mi={{{self.id}}}&pageSize=10000',
                'forslag_til_vedtagelse': f'{self.url}/dokumenter/forslag_til_vedtagelse?mi={{{self.id}}}&pageSize=10000',
                'alleforslag': f'{self.url}/dokumenter/alleforslag?mi={{{self.id}}}&pageSize=10000'
            },
            'taler_og_stemmer':{
                'ordfoerertaler': f'{self.url}/dokumenter/ordfoerertaler?mi={{{self.id}}}&pageSize=10000',
                'alletaler': f'{self.url}/dokumenter/alletaler?mi={{{self.id}}}&pageSize=10000',
                'afstemninger': f'{self.url}/dokumenter/afstemninger?mi={{{self.id}}}&pageSize=10000',
            }
        }
        # sessions can be either 20xx1 or 20xx2 (depending on how the year progressed, sometimes it will only have 1 session, however query will just return 0)
        self.periods= [f'{x}{i}' for x in range(2005,2023) for i in range(1,3)]

        
    
    def _get_initial_block(self):
        result = self.soup.findAll('div', attrs={'class': 'ftMember__accordion__container panel-group'})[0]
        return result

class FT_MemberID_CvScraper(FT_MemberID_Scraper_Base):

    def __init__(self, *args, **kwargs):
        FT_MemberID_Scraper_Base.__init__(self, *args, **kwargs) #init super class
        
        self.scrape_scope ={
            'medlemsperiode' : True,
            'parlamentarisk_karriere' : True,
            'uddannelse' : True,
            'beskaeftigelse' : True,
            'tillidshverv' : True,
            'publikationer' : True,
            'udmaerkelser' : True
        }

    def get_cv_block(self):
        return self.initial_block.findAll('div', attrs={'id': 'cv'})[0]
    
    def _has_section(self):
        return len(self.get_cv_block().findAll('section')) > 0
    
    def get_resume(self):
            #The first section on page is resume
            #replace just fixes weird unicode white space issue
            self.data['resume'] = self.cv.findAll('section')[0].text.strip().replace('\xa0', ' ')

    def filter_sections(self, filter_string, sections):
        to_return = []
        for section in sections:
            if section.findAll('strong') is not None:
                postprocessed = [y.text.lower().strip().replace(' ', '_') for y in section.findAll('strong')]
                if any([bool(y.replace('æ', 'ae').replace('ø', 'oe').replace('å', 'aa') == filter_string) for y in postprocessed]):
                    to_return.append(section)
        return to_return

    def meta_cv_scraper(self, type):
        """
        Filters through sections containing a <strong> tagged string matching type (roughly), and collects data from it.
        """
        sections = self.filter_sections(filter_string=type, sections=self.cv_sections)
        if len(sections) > 1:
            raise Exception(f'Multiple {type} sections found')
        self.data[type] = []
        if len(sections) == 1:
            section = sections[0]
            asides = section.findAll('aside')
            for item in asides:
                for rowline in item.text.strip().replace('\xa0', ' ').replace('\r\n', '\n').split('\n'):
                    if rowline.strip() != '':
                        self.data[type].append({'type': 'aside', 'data' : rowline.strip()})
            ps = section.findAll('p')
            for item in ps:
                for rowline in item.text.strip().replace('\xa0', ' ').replace('\r\n', '\n').split('\n'):
                    if rowline.strip() != '':
                        self.data[type].append({'type' : 'p', 'data': rowline.strip()})

            
    def run(self):
        if self._has_section():
            self.cv = self.get_cv_block()
            self.get_resume()
            self.cv_sections =self. cv.findAll('section')
            for scope, run_bool in self.scrape_scope.items():
                if run_bool:
                    self.meta_cv_scraper(scope)

class FT_MemberID_ForslagScraper(FT_MemberID_Scraper_Base):
    def __init__(self, *args, **kwargs):
        FT_MemberID_Scraper_Base.__init__(self, *args, **kwargs) #init super class
        self.scrape_scope = self.base_urls.get('forslag')
        self.data={}
        self.base_url = 'https://ft.dk/'
        

        self.tablerow_index_map = {
            'lovforslag': {0: 'Nr', 1: 'Titel', 2: 'Rolle', 3: 'Ministeromraade', 4: 'Samling'},
            'beslutningsforslag': {0: 'Nr', 1: 'Titel', 2: 'Rolle', 3: 'Ministeromraade', 4: 'Samling'},
            'forespoergsler': {0: 'Nr', 1: 'Titel', 2: 'Rolle', 3: 'Ministeromraade', 4: 'Samling'},
            'redegoerelser': {0: 'Nr', 1: 'Titel', 2: 'Afgivet af', 3: 'Rolle', 4: 'Samling'},
            'forslag_til_vedtagelse': {0: 'Nr', 1: 'Titel', 2: 'Samling'},
            'alleforslag': {0: 'Nr', 1: 'Titel', 2: 'Rolle', 3: 'Ministeromraade', 4: 'Samling'}
        }
        for key in self.tablerow_index_map.keys():
            self.data[key] = []

    def get_forslag_scope(self, scope, period):
            url = self.scrape_scope.get(scope)
            url = f'{url}&session={period}'
            response = self._request_timeout(url)
            soup = BeautifulSoup(response.content, 'html.parser')
            table_rows = soup.findAll('tr', attrs={'class': re.compile('^listespot'), 'data-url': re.compile('^/\S')})
            output = []
            if table_rows != []:
                # Helper function to parse output
                def _parse_row(row, index):
                    try:
                        return row.findAll('a')[index].text.strip(), row.findAll('a')[index].get('href')
                    except:
                        return None, None


                for row in table_rows:
                    to_append = {}
                    for i in range(len(self.tablerow_index_map[scope].keys())):
                        
                        text, url_end = _parse_row(row, i)
                        to_append[self.tablerow_index_map[scope][i]] = text
                        if url_end:
                            to_append['Url'] = f'{self.base_url}{url_end}'.replace('//','/')
                        to_append['Period'] =  period
                    if to_append.get('Url') is None:
                        to_append['Url'] = None
                    output.append(to_append)
            return output
    
    def run(self):
        for period in self.periods:
            for key in self.tablerow_index_map.keys():
                data = self.get_forslag_scope(scope=key, period=period)
                if data:
                    #Format data correctly -currently it is too nested.
                    self.data[key].append(data)
        for key in self.tablerow_index_map.keys():
            if len(self.data[key])>1:
                self.data[key] = functools.reduce(lambda x,y: x + y, self.data[key])
            if len(self.data[key]) == 1 & isinstance(self.data[key][0], list):
                self.data[key] = self.data[key][0]








            






    





    










    



