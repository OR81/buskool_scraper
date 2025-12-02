import json
import logging
import os
import time
from datetime import datetime

import requests
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

LOG_FILE = 'response_log.jsonl'
PROCESSED_FILE = "processed_products.json"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

PROCESSED_PRODUCTS = set()


def create_chrome_driver(headless: bool = True):
    options = Options()
    if headless:
        #options.add_argument("--headless=new")
        options.add_argument("--use-gl=swiftshader")
        options.add_argument("--disable-software-rasterizer")

        options.add_argument("--disable-gpu-compositing")
        options.add_argument("--disable-accelerated-2d-canvas")
        options.add_argument("--disable-accelerated-video-decode")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--window-size=1280,1024")

    options.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver_instance = webdriver.Chrome(service=Service('chromedriver.exe'), options=options)
    return driver_instance


def write_log(entry: dict):
    logging.info(entry)
    entry["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = json.dumps(entry, ensure_ascii=False)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_cookies_from_file(driver, file_path="cookies.json"):
    if not os.path.exists(file_path):
        write_log({"action": "load_cookies", "status": "warning", "message": "Cookie file not found"})
        return False

    with open(file_path, "r", encoding="utf-8") as f:
        cookies = json.load(f)

    success_count = 0
    fail_count = 0

    for cookie in cookies:
        cookie.pop("sameSite", None)
        cookie.pop("hostOnly", None)
        cookie.pop("storeId", None)
        cookie.pop("expires", None)
        if "name" in cookie and "value" in cookie:
            try:
                driver.add_cookie(cookie)
                success_count += 1
            except Exception as e:
                fail_count += 1
                write_log({"action": "load_cookies", "status": "error", "cookie": cookie.get("name"), "error": str(e)})

    try:
        driver.refresh()
    except Exception as e:
        write_log({"action": "load_cookies", "status": "error", "message": "driver.refresh failed", "error": str(e)})
        return False

    write_log({"action": "load_cookies", "status": "success", "added": success_count, "failed": fail_count})
    return True


def check_forbidden_page(driver, url: str):
    page_source = driver.page_source.lower()
    if "error 403" in page_source or "forbidden" in page_source:
        write_log({"action": "check_forbidden", "status": "error", "url": url})
        driver.quit()
        raise SystemExit("Stopped due to 403 Forbidden error")
    else:
        write_log({"action": "check_forbidden", "status": "success", "url": url})


def start_browser(headless: bool = False):
    driver = create_chrome_driver(headless=headless)
    url = 'https://www.buskool.com/'
    driver.get(url)
    check_forbidden_page(driver, url)
    load_cookies_from_file(driver)
    write_log({"action": "start_browser", "status": "success"})
    return driver


def scroll_until_end(driver, pause=1.5):
    last_height = driver.execute_script("return document.body.scrollHeight")

    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause)

        new_height = driver.execute_script("return document.body.scrollHeight")

        # Scroll a little up and down to ensure elements are not overlapped
        driver.execute_script("window.scrollBy(0, -50);")
        time.sleep(0.2)
        driver.execute_script("window.scrollBy(0, 50);")
        time.sleep(0.2)

        if new_height == last_height:
            break
        last_height = new_height

    print("scroll completed")


def process_all_products(driver):
    global PROCESSED_PRODUCTS
    PROCESSED_PRODUCTS = load_processed()

    # دسته‌بندی‌ها
    WebDriverWait(driver, 15).until(EC.presence_of_all_elements_located(
        (By.XPATH, "//div[contains(@class,'categories-container')]/div[contains(@class,'category-card')]")))
    categories = driver.find_elements(By.XPATH,
                                      "//div[contains(@class,'categories-container')]/div[contains(@class,'category-card')]")
    total_categories = len(categories)

    for c_index in range(total_categories):
        # دوباره دسته‌بندی‌ها رو پیدا کن
        categories = driver.find_elements(By.XPATH,
                                          "//div[contains(@class,'categories-container')]/div[contains(@class,'category-card')]")
        category = categories[c_index]
        category_name = category.find_element(By.TAG_NAME, "p").text
        print(f"Processing category: {category_name}")

        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", category)
        time.sleep(0.3)
        try:
            category.click()
        except StaleElementReferenceException:
            categories = driver.find_elements(By.XPATH,
                                              "//div[contains(@class,'categories-container')]/div[contains(@class,'category-card')]")
            category = categories[c_index]
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", category)
            category.click()
        time.sleep(2)

        old_count = 0
        
        try:
         new_product_button  = WebDriverWait(driver,10).until(EC.element_to_be_clickable((By.XPATH ,'//*[@id="main"]/div/div/section/div[1]/ul/li[3]/button')))
         new_product_button.click()
         time.sleep(3)
         write_log({'action':"click_new_product_button" , 'status':'success'})
        except Exception as e:
            write_log({'action':"click_new_product_button" , 'status':'faild' , "message":str(e)})
            
        while True:
            time.sleep(5)
            products = WebDriverWait(driver, 15).until(EC.presence_of_all_elements_located(
                (By.XPATH, "//div[contains(@class,'items-wrapper')]//div[contains(@class,'product-row-wrapper')]")))
            if not products:
                print("No products found on page.")
                break
            if len(products) <= old_count:
                break
            else:
                old_count = len(products)

            for p_index, product in enumerate(products):

                try:
                    driver.execute_script("arguments[0].scrollIntoView({behavior:'smooth', block:'center'});", product)
                    time.sleep(0.5)

                    image_src = driver.find_element(By.XPATH,
                        f"//*[@id='article-list']/div/div[{p_index + 1}]/div/div/div[1]/div[1]/img").get_attribute(
                        "src")

                    write_log({"image": image_src})

                    if image_src in PROCESSED_PRODUCTS:
                        write_log({"action": "skip_duplicate", "status": "skipped", "product_name": image_src})
                        continue

                    if image_src:
                        PROCESSED_PRODUCTS.add(image_src)
                        save_processed()

                    current_tabs = driver.window_handles
                    product.click()
                    time.sleep(1)

                    new_tabs = driver.window_handles
                    if len(new_tabs) > len(current_tabs):
                        driver.switch_to.window(new_tabs[-1])
                        write_log({"action": "switch_to_new_tab", "status": "success", "tab_index": len(new_tabs) - 1})
                    else:
                        write_log({"action": "switch_to_new_tab", "status": "no_new_tab"})

                except StaleElementReferenceException:
                    products = driver.find_elements(By.XPATH,
                                                    "//div[contains(@class,'items-wrapper')]//div[contains(@class,'product-row-wrapper')]")
                    product = products[p_index]
                    driver.execute_script("arguments[0].scrollIntoView({behavior:'smooth', block:'center'});", product)
                    current_tabs = driver.window_handles
                    
                    product.click()
                    time.sleep(1)
                    new_tabs = driver.window_handles
                    if len(new_tabs) > len(current_tabs):
                        driver.switch_to.window(new_tabs[-1])
                        write_log({"action": "switch_to_new_tab", "status": "success", "tab_index": len(new_tabs) - 1})
                    else:
                        write_log({"action": "switch_to_new_tab", "status": "no_new_tab"})

                scrape_single_product(driver)

                if len(new_tabs) > len(current_tabs):
                    driver.close()
                    driver.switch_to.window(current_tabs[0])
                    write_log({"action": "close_product_tab", "status": "success"})

            # بررسی می‌کنیم آیا محصول جدید بعد اسکرول لود شده
            new_products = WebDriverWait(driver, 15).until(EC.presence_of_all_elements_located(
                (By.XPATH, "//div[contains(@class,'items-wrapper')]//div[contains(@class,'product-row-wrapper')]")))
            if len(new_products) <= len(products):
                break
            driver.execute_script("window.scrollBy(0, 300);")
            time.sleep(1)

        driver.back()
        time.sleep(1)


def send_message_text(chat_box, text):
    lines = text.split("\n")
    for i, line in enumerate(lines):
        chat_box.send_keys(line)
        if i < len(lines) - 1:
            chat_box.send_keys(Keys.SHIFT, Keys.ENTER)
    chat_box.send_keys(Keys.ENTER)


API_URL = "https://pinosite.omidrajabee.ir/webhook/94209ce1-0e9b-43ca-997b-826a3af69c79"

LAST_API_CALL = 0
API_INTERVAL = 1


def send_to_api(data, retries=1):
    global LAST_API_CALL
    now = time.time()
    elapsed = now - LAST_API_CALL

    if elapsed < API_INTERVAL:
        wait_time = API_INTERVAL - elapsed
        write_log({"action": "rate_limit", "status": "waiting", "wait_time": wait_time})
        time.sleep(wait_time)

    attempt = 0

    while attempt <= retries:
        try:
            response = requests.post(API_URL, json=data)

            if response.status_code != 200:
                write_log({"action": "send_to_api", "status": "fail", "attempt": attempt + 1,
                    "http_status": response.status_code})
                return None

            try:
                result = response.json()
                output_text = result.get("output", "")
            except:
                output_text = ""

            # اگر خروجی خالی بود → retry
            if not output_text:
                write_log({"action": "send_to_api", "status": "empty_output", "attempt": attempt + 1})
                attempt += 1
                if attempt <= retries:
                    write_log({"action": "send_to_api", "status": "retrying_due_to_empty_output", "attempt": attempt})
                    continue
                else:
                    # خالی بود و retry هم تموم شد → برو آیتم بعدی
                    return None

            LAST_API_CALL = time.time()
            write_log({"action": "send_to_api", "status": "success"})
            return output_text

        except Exception as e:
            write_log({"action": "send_to_api", "status": "exception", "attempt": attempt + 1, "error": str(e)})

        attempt += 1
        if attempt <= retries:
            write_log({"action": "send_to_api", "status": "retrying_after_exception", "attempt": attempt})

    # اگر همه چی شکست → برو آیتم بعدی
    return None


def scrape_single_product(driver):
    data = {"phone": "", "seller_name": "", "product_name": "", "city": "", "state": "","price":"", "description": "",
        "category": "", "sub_category": "", "link": "", }

    time.sleep(2)
    try:
        data["product_name"] = driver.find_element(By.XPATH, "//*[@class='main-contents']//h1").text
        write_log({"action": "get_product_name", "status": "success", "product_name": data["product_name"]})
    except Exception as e:
        write_log({"action": "get_product_name", "status": "skipped", "message": str(e)})

    try:
        data["seller_name"] = WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.XPATH,
                                                                                                '//*[@id="main"]/div[1]/div/div[2]/section/div/div/div[1]/div[2]/div/div/ul/li[1]/span[2]'))).text
        write_log({"action": "get_seller_name", "status": "success", "seller_name": data["seller_name"]})
    except Exception as e:
        write_log({"action": "get_seller_name", "status": "skipped", "message": "seller name not found"})
    try:
        location_text = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH,
                                                                                        '//*[@id="main"]/div[1]/div/div[2]/section/div/div/div[1]/div[2]/div/div/ul/li[2]/span[2]'))).text

        if "-" in location_text:
            state, city = location_text.split("-")
            data["state"] = state.replace("استان", "").strip()
            data["city"] = city.replace("شهر", "").strip()
            write_log({"action": "get_location", "status": "success", "state": data["state"], "city": data["city"]})
    except Exception as e:
        write_log({"action": "get_location", "status": "skipped", "message": "location not found"})
        
        
    try:
        data["price"] = WebDriverWait(driver,5).until(EC.presence_of_element_located((By.XPATH , '//*[@id="main"]/div[1]/div/div[2]/section/div/div/div[1]/div[2]/div/div/div/div/div[2]/p[2]'))).text    
        write_log({"action": "get_price", "status": "success", "price": data["price"]})
    except Exception as e:
         write_log({"action": "get_price", "status": "faild", "message": str(e)})

    try:
        data["link"]= driver.current_url
        write_log({"action": "get_link", "status": "success", "price": data["link"]})
    except Exception as e:
        write_log({"action": "get_link", "status": "faild", "message": str(e)})


    try:

        #phone_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable(
            #(By.XPATH, "//button[contains(@class, 'main-button') and contains(text(), 'شماره تماس')]")))
        
        #phone_button.click()
        #time.sleep(2)
        #write_log({"action": "click_phone_button", "status": "success", })

        #phone_number = WebDriverWait(driver, 10).until(
            #EC.presence_of_element_located((By.XPATH, "//a[@class='phone-number']/p")))
        data["phone"] = "090000000000"
                #data["phone"] = phone_number.text

        #time.sleep(0.5)
        #write_log({"action": "get_phone_number", "status": "success", "phone_number": data["phone"]})
    except:
        write_log({"action": "click_phone_button", "status": "fail", "message": "cant click phone_button"})

    try:
        description = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'product-description')]//p")))
        driver.execute_script("arguments[0].scrollIntoView({behavior:'smooth', block:'center'});", description)
        data["description"] = description.text
        write_log({"action": "get_description", "status": "success", "description": data["description"]})
    except:
        write_log({"action": "get_description", "status": "fail", "message": "description not found"})

    try:
        breadcrumbs = driver.find_elements(By.XPATH, "//a[contains(@href,'/product-list/category/')]//span")
        if len(breadcrumbs) >= 2:
            data["category"] = breadcrumbs[0].text
            data["sub_category"] = breadcrumbs[1].text
            write_log({"action": "get_category_and_sub_category", "status": "success", "category": data['category'],
                       'sub_category': data["sub_category"]})
    except:
        write_log({"action": "get_category_and_sub_category", "status": "fail",
                   "message": "category and subcategory not found"})

    api_response = None

    try:
        api_response = send_to_api(data)
        write_log({"action": "send_to_api", "status": "success", "api_response": api_response})
    except Exception as e:
        write_log({"action": "send_to_api", "status": "fail", "message": str(e)})

    if api_response:
        try:
            chat_buuton = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'چت با فروشنده')]")))
            driver.execute_script("arguments[0].scrollIntoView({behavior:'smooth', block:'center'});", chat_buuton)
            driver.execute_script("arguments[0].click();", chat_buuton)
            time.sleep(2)
            write_log({"action": "click_chat_button", "status": "success"})
            chat_box = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//textarea[@id='msg_text']")))
            chat_box.click()
            write_log({"action": "click_chat_box", "status": "success"})
            send_message_text(chat_box, api_response)
            time.sleep(1)
        except Exception as e:
            write_log({"action": "send_message_text", "status": "success"})

       
    print("Sending product:", data["product_name"])


def load_processed():
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_processed():
    # مرحله ۱: خواندن فایل موجود
    old_data = set()
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
            try:
                old_data = set(json.load(f))
            except json.JSONDecodeError:
                old_data = set()

    # مرحله ۲: ترکیب با داده‌های جدید
    combined = list(old_data.union(PROCESSED_PRODUCTS))

    # مرحله ۳: ذخیره کردن بدون پاک کردن داده‌های قبلی
    with open(PROCESSED_FILE, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    try:
        driver = start_browser(headless=False)
        process_all_products(driver)
    except Exception as e:
        print("Error:", e)
    finally:
        try:
            driver.quit()
        except:
            pass
