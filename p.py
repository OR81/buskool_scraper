import requests

API_URL = "https://pinosite.omidrajabee.ir/webhook/94209ce1-0e9b-43ca-997b-826a3af69c79"

data = {
    "phone":"09301445322",
    "seller_name":"امیدرجبی",
    "product_name":"دو راس حسین و فاطیما",
    "city":"کازرون",
    "state":"فارس",
    "description":"با سلام یک راس گاو ماده سالم در حد نو و یک راس کره اسب تازه نفس به شرط کارشناسی شاسی پلمپ تحویل در محل",
    "category":"فروش دام و طیور",
    "sub_category":"فروش چهار پا"
}

response = requests.post(API_URL, json=data)
print(response.status_code, response.text)
