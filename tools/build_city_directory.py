import csv
import io
import json
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[1]
url = 'https://raw.githubusercontent.com/hflabs/city/master/city.csv'
rows = csv.DictReader(io.StringIO(urllib.request.urlopen(url).read().decode('utf-8-sig')))
cities = set()
for row in rows:
    name = row['city'] or row['settlement'] or row['region']
    region = row['region']
    kind = row['region_type']
    if region in {'Саха', 'Саха /Якутия/', 'Саха (Якутия)'}:
        region = 'Республика Саха (Якутия)'
    elif kind == 'Респ':
        region = 'Республика ' + region
    elif kind == 'обл':
        region += ' область'
    elif kind == 'край':
        region += ' край'
    elif kind == 'АО':
        region += ' автономный округ'
    elif kind == 'Аобл':
        region += ' автономная область'
    cities.add((name, region))
values = [{'name':n,'region':r} for n,r in sorted(cities)]
(root / 'frontend/src/cities.json').write_text(json.dumps(values,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
(root / 'frontend/public/assets/CITIES-LICENSE.txt').write_text('Города и регионы: hflabs/city, исходные данные DaData.\nhttps://github.com/hflabs/city\nCC BY-SA 4.0: https://creativecommons.org/licenses/by-sa/4.0/\nИзменения: оставлены город и регион, названия регионов приведены к читаемому виду. Снимок скачан 14.10.2026. Не является подключением к актуальному реестру ФИАС.\n',encoding='utf-8')
print('City directory:',len(values),'cities')
