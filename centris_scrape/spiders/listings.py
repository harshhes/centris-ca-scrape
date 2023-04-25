import scrapy, json
from scrapy.selector import Selector
from scrapy_splash import SplashRequest
from w3lib.http import basic_auth_header



class ListingsSpider(scrapy.Spider):
    name = 'listings'
    allowed_domains = ['www.centris.ca']

    cookies = {'cookie':'AnonymousId=146d581251d04eb2a3dbf65239048e26; ll-search-selection=; .AspNetCore.Session=CfDJ8AOd167IDotPki3NIkn%2FxZ%2FGtV7q934sjxAlTCOAtZzzA4yiGjgYZCMHzezrvY2jgImh6Ns0LHxEtw9nC%2F9zZ3MoBymzgTAwH9C%2ByIlW9k5G5z%2FTsaM8MBt%2Fo3dSn4YEguw%2FcRbiG3NlxL%2BTLR5rpBa9vImCVTVqd5fQRBBYJl3l; ll-visitor-id=36fde0d6-2a70-4c62-9a58-149384ad0c99'}
    
    position = {
        "startPosition": 0
    }

    script = """
        function main(splash, args)
        splash:on_request(function(request)
            if request.url:find('css') then
                request.abort()
            end
        end)
        splash.images_enabled = false
        splash.js_enabled = false
        assert(splash:go(args.url))
        assert(splash:wait(0.5))
        return splash:html()
        end
        """

    def start_requests(self):
        yield scrapy.Request(
            url = 'https://www.centris.ca/en',
            # cookies=self.cookies,
            headers={
                'accept-language': 'en-GB,en;q=0.6',
                'Content-Type': 'application/json; charset=utf-8'
                },
            callback=self.new_start_requests
        )
    def new_start_requests(self, response):
        query = {
            "query":{
                "UseGeographyShapes":0,
                "Filters":[
                    {
                        "MatchType":"GeographicArea",
                        "Text":"Montréal (Island)",
                        "Id":"GSGS4621"
                    }
                ],
                "FieldsValues":[
                    {
                        "fieldId":"GeographicArea",
                        "value":"GSGS4621",
                        "fieldConditionId":"",
                        "valueConditionId":""
                    },
                    {
                        "fieldId":"Category",
                        "value":"Residential",
                        "fieldConditionId":"",
                        "valueConditionId":""
                    },
                    {
                        "fieldId":"SellingType",
                        "value":"Rent",
                        "fieldConditionId":"",
                        "valueConditionId":""
                    },
                    {
                        "fieldId":"LandArea",
                        "value":"SquareFeet",
                        "fieldConditionId":"IsLandArea",
                        "valueConditionId":""
                    },
                    {
                        "fieldId":"RentPrice",
                        "value":0,
                        "fieldConditionId":"ForRent",
                        "valueConditionId":""
                    },
                    {
                        "fieldId":"RentPrice",
                        "value":1000,
                        "fieldConditionId":"ForRent",
                        "valueConditionId":""
                    }
                ]
            },
            "isHomePage":True
            }

        yield scrapy.Request(
            url='https://www.centris.ca/property/UpdateQuery',
            method='POST',
            # cookies=self.cookies, 
            body = json.dumps(query),
            headers={
                'accept-language': 'en-GB,en;q=0.6',
                'Content-Type': 'application/json; charset=utf-8'
                },
            callback=self.update_query)

    def update_query(self, response):

        yield scrapy.Request(
            url = 'https://www.centris.ca/Property/GetInscriptions',
            method = 'POST',
            # cookies=self.cookies, 
            body = json.dumps(self.position),
            headers={
                'accept-language': 'en-GB,en;q=0.6',
                'Content-Type': 'application/json; charset=UTF-8'
                },
            callback=self.parse)

    def parse(self, response):
        auth = basic_auth_header('user', 'userpass')
        new_response = json.loads(response.body)
        html = new_response['d']['Result']['html']
        resp = Selector(text=html)
        
        listings = resp.xpath("//div[@class='shell']")

        for listing in listings:
            category = listing.xpath("normalize-space(.//div[@class='description']//span[@class='category']/div/text())").get()
            price = listing.xpath(".//div[@class='description']//span/text()").get()
            address = listing.xpath("normalize-space(.//div[@class='description']//span[@class='address']/div/text())").get()
            url = listing.xpath(".//a[@class='property-thumbnail-summary-link']/@href").get()
            abs_url = f'https://www.centris.ca{url}'

            yield SplashRequest(
                url=abs_url,
                endpoint='execute',
                splash_headers={'Authorization': auth},
                callback=self.parse_summary,
                args={
                    'lua_source': self.script
                },
                meta= {
                    'cat': category,
                    'pri': price,
                    "add": address,
                    "url": abs_url
                }
            )

        count = new_response['d']['Result']['count']
        position = new_response['d']['Result']['inscNumberPerPage']

        if self.position['startPosition'] <= count:
            self.position['startPosition'] += position

            yield scrapy.Request(
            url = 'https://www.centris.ca/Property/GetInscriptions',
            method = 'POST',
            body = json.dumps(self.position),
            headers={
                'accept-language': 'en-GB,en;q=0.6',
                'Content-Type': 'application/json; charset=UTF-8'
                },
            callback=self.parse)

        
    def parse_summary(self, response):
        
        address_summary = response.xpath("//h2[@itemprop='address'][@class='pt-1']/text()").get()
        description = response.xpath("normalize-space(//div[@itemprop='description']/text())").get()
        category = response.request.meta['cat']
        price = response.request.meta['pri']
        # address = response.request.meta['add']
        lifestyle = response.xpath("normalize-space(//div[@class='col-lg-3 col-sm-6 lifestyle']/span/text())").get()
        rooms = response.xpath("normalize-space(//div[@class='col-lg-3 col-sm-6 piece']/text())").get()
        beds = response.xpath("normalize-space(//div[@class='col-lg-3 col-sm-6 cac']/text())").get()
        bathrooms = response.xpath("normalize-space(//div[@class='col-lg-3 col-sm-6 sdb']/text())").get()
        additional_features = response.xpath("//div[@class='carac-value']/span/text()").getall()
        url = response.request.meta['url']

        yield {
            "category": category, 
            "description": description,
            "address": address_summary,
            "price": f"{price} /month",
            # "address": address,
            'features': f"{lifestyle} {rooms} {beds} {bathrooms}",
            'addtional_features': additional_features,
            "url_of_property": url

        }