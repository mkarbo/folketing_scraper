from bs4 import BeautifulSoup
import requests
import re
import json

class FT_scraper:
    """
    A simple webscraper for www.ft.dk, which gathers content from search function via party ID.
    """
    def __init__(self, party_id):
        self.url_template = 'https://www.ft.dk/searchResults.aspx?sortedDescending=false&party={{{party_id}}}&page=1&sortedBy=&pageSize=200'
        self.page = None # build by self.get_page
        self.soup = None # build by self.get_soup
        self.base_url = 'https://ft.dk/'
        self.party_id = party_id # required for self.get_page

    def get_page(self, party_id=None):
        url = self.url_template.format(party_id=(party_id if party_id else self.party_id))
        page = requests.get(url, verify=False)
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

    def run(self):
        self.get_page()
        self.setup_soup()
        self.find_table_rows()
        self.parse_table_rows()
        return self.output
    

class JSON_FT_scraper:
    def __init__(self, json_path, key='id'):
        with open(json_path, 'r') as jsonfile:
            data = json.loads(jsonfile.read())
        self.ids = [entry.get(key) for entry in data]

    def run(self):
        outputs = []
        for party_id in self.ids:
            ft = FT_scraper(party_id=party_id)
            outputs.extend(ft.run())
        return outputs

    def run_and_save(self, output_path=None):
        if output_path is None:
            output_path = 'output_scrape_ftdk.json'
        outputs = self.run()

        json_dump = json.dumps(outputs, ensure_ascii=False).replace('},', '},\n')
        with open(output_path, 'w') as file:
            file.write(json_dump)
        





    



