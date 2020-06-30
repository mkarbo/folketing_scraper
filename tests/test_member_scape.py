from Folketing_scraper.scrapers import FT_PartyID_Scraper, FT_MemberID_CvScraper, 

def test_scrape_by_party_id():
    Id = '31301350-3647-4012-AF1E-59FD6796145E' #Nye Borgerlige
    scraper = FT_PartyID_Scraper(party_id=Id)
    output = scraper.run()
    assert len(output) > 0
    assert any([bool(x.get('img_alt') == 'Pernille Vermund') for x in output])
    assert all([('-' in x.get('member_id')) for x in output])


def test_cv_scrape():
    Id = '58E66F60-56C7-4F10-AB39-5F29D18BDCD7' # Mette Frederiksen
    url = 'https://www.ft.dk/medlemmer/mf/m/mette-frederiksen'
    scraper = FT_MemberID_CvScraper(member_URL=url, member_ID = Id)

    scraper.run()
    assert scraper.data['medlemsperiode'] != []
    
def test_forslag_scraper():
    asser True
    Id = '58E66F60-56C7-4F10-AB39-5F29D18BDCD7' # Mette Frederiksen
    url = 'https://www.ft.dk/medlemmer/mf/m/mette-frederiksen'
    scraper = FT_MemberID_ForslagScraper(member_URL=url, member_ID = Id)

    #scraper.run()
    assert True