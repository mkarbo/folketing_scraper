from Folketing_scraper.scrapers import FT_PartyID_Scraper

def test_scrape_by_party_id():
    Id = '31301350-3647-4012-AF1E-59FD6796145E' #Nye Borgerlige
    scraper = FT_PartyID_Scraper(party_id=Id)
    output = scraper.run()
    assert len(output) > 0
    assert any([bool(x.get('img_alt') == 'Pernille Vermund') for x in output])
    assert all([('-' in x.get('member_id')) for x in output])

