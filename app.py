import datetime
import time
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
import requests
import xmltodict
from bs4 import BeautifulSoup
from io import BytesIO
from zipfile import ZipFile
import pandas as pd

user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.50 Safari/537.36'

options = webdriver.ChromeOptions()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('user-agent={0}'.format(user_agent))
browser = webdriver.Chrome(ChromeDriverManager().install(),options=options)

tables = []
units = []

def get_corp_code(name, match=True):
    res = requests.get('https://opendart.fss.or.kr/api/corpCode.xml', params={'crtfc_key':'a833e0e45d84a648428ad40598609e82f2bf226d'})
    zipfile_bytes = res.content
    zipfile_obj = ZipFile(BytesIO(zipfile_bytes))
    xmlfile_objs = {name: zipfile_obj.read(name) for name in zipfile_obj.namelist()}
    xml_str = xmlfile_objs['CORPCODE.xml'].decode('utf-8')
    data_dict = xmltodict.parse(xml_str).get('result', {}).get('list')
    result = []
    if match:
        for item in data_dict:
            if name == item['corp_name']:
                result.append(item)
    else:
        for item in data_dict:
            if name in item['corp_name']:
                result.append(item)
    return result

def get_dart_fss_data(name):
    global browser
    if browser is None:
        browser = webdriver.Chrome(ChromeDriverManager().install(), options=webdriver.ChromeOptions())
    now = datetime.datetime.now()
    ymd_from = str(now.year-1) + str(now.month).rjust(2,'0') + str(now.day).rjust(2,'0')
    ymd_to = str(now.year) + str(now.month).rjust(2,'0') + str(now.day).rjust(2,'0')
    corp_code =get_corp_code(name)[0]['corp_code']
    data = {
        "textCrpCik": corp_code,
        "startDate": ymd_from,
        "endDate": ymd_to,
        "publicType": "A001"
    }
    base_url = 'https://dart.fss.or.kr'
    res = requests.post(base_url + '/dsab007/detailSearch.ax', data)
    soup = BeautifulSoup(res.content, 'html.parser')
    url = base_url + soup.select('.tL > a')[0].attrs['href']
    browser.get(url)
    browser.execute_script("document.querySelectorAll('#listTree a').forEach(function(item){if(item.textContent.indexOf(' 재무제표 주석')>-1){item.click();}});")
    time.sleep(0.5)
    soup = BeautifulSoup(browser.page_source, 'html.parser')
    url = base_url + soup.select('#ifrm')[0].attrs['src']
    res = requests.get(url)
    soup = BeautifulSoup(res.content, 'html.parser')
    check_tags = soup.select('p, table')
    return check_tags

def get_unit(text):
    text = text.replace(' ','')
    find_text = '(단위:'
    start_index = text.find(find_text)
    end_index = text.find(')', start_index)
    return text[start_index+len(find_text):end_index]

def get_column_name(table, col_name=None):
    for col in table.columns.get_level_values(-1):
        if col_name == col.replace(' ',''):
            return col
    return False

def get_need_data(table):
    dvsn = '구분'
    begin = '기초'
    end = '기말'
    total = '계'
    result = []
    if get_column_name(table, begin):
        if get_column_name(table, dvsn):
            result.append({begin: []})
            for i, col in enumerate(table[get_column_name(table, dvsn)]):
                if total in col:
                    result[len(result)-1][begin].append({
                        col: table[get_column_name(table, begin)].iloc[i]
                    })
    if get_column_name(table, end):
        if get_column_name(table, dvsn):
            result.append({end: []})
            for i, col in enumerate(table[get_column_name(table, dvsn)]):
                if total in col:
                    result[len(result)-1][end].append({
                        col: table[get_column_name(table, end)].iloc[i]
                    })
    return result

def find_acquisition_amount(name):
    check_tags = get_dart_fss_data(name)
    target_idx = 0
    while target_idx < len(check_tags):
        if check_tags[target_idx].name == 'table':
            target_text = check_tags[target_idx].text
            if '취득' in target_text and '토지' in target_text and '건물' in target_text and '기초' in target_text and '기말' in target_text:
                dfs = pd.read_html(str(check_tags[target_idx]))
                df = dfs[0]
                tables.append(df)
                # summary = {k: v.iloc[0, 1].split('  ') for k, v in df.groupby('구 분')}
                if '단위' in target_text and '원' in target_text:
                    units.append(get_unit(target_text))
                else:
                    temp_idx = target_idx
                    while -1 < temp_idx:
                        temp_idx -= 1
                        target_text = check_tags[temp_idx].text
                        if '단위' in target_text and '원' in target_text:
                            units.append(get_unit(target_text))
                            break
                break
        target_idx += 1

def main():
    global tables, units
    find_acquisition_amount('한화생명')
    # find_acquisition_amount('삼성전자')
    # find_acquisition_amount('휴스틸')

    print(units)
    print(tables[0])
    for table in tables:
        print(get_need_data(table))

main()
