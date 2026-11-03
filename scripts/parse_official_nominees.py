"""Extract Clerk's public-domain nominee list, stripping superscript footnote digits.

Requires pdfplumber only when refreshing this source. Forecast reproduction uses
the saved normalized CSV and does not need a PDF library.
"""
import csv
import re
from pathlib import Path
import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
NAMES = 'Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming'.split('|')
CODES = 'AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY'.split()
STATES = dict(zip(map(str.upper,NAMES),CODES))


def main():
    state, chamber, district = '', '', 1
    rows, clean = [], []
    with pdfplumber.open(ROOT/'data/bootstrap/120-nominations.pdf') as pdf:
        for page_no,page in enumerate(pdf.pages,1):
            page = page.filter(lambda obj: obj.get('object_type') != 'char' or obj.get('size',0) >= 8.9 or obj.get('text') in '*†‡')
            text = page.extract_text(layout=False) or ''
            clean.append(text)
            for line in text.splitlines():
                line = line.strip()
                header = line.replace('—Continued','').strip()
                if header in STATES:
                    if state != STATES[header]:
                        state, district = STATES[header], 1
                elif line.startswith('FOR UNITED STATES SENATOR') or line.startswith('F U S S'):
                    chamber, district = 'Senate',''
                elif line.startswith('FOR UNITED STATES REPRESENTATIVE') or line.startswith('F U S R'):
                    chamber = 'House'
                    if district == '':
                        district = 1
                elif 'FOR DELEGATE' in line or 'FOR RESIDENT COMMISSIONER' in line or line in ('F D','F R C'):
                    chamber = ''
                elif line == 'AT LARGE':
                    district = 1
                elif '...' in line and state and chamber:
                    prefix = re.split(r'\.{3,}',line)[0].strip()
                    number = re.match(r'^(\d+)\s+',prefix)
                    if number:
                        district = int(number[1])
                        prefix = prefix[number.end():]
                    if ',' not in prefix:
                        continue
                    primary = re.search(r',\s*[*†‡]*\s*(Republican|Democrat(?:ic-Farmer-Labor|ic-Nonpartisan League)?)(?:,|\s|$)',prefix)
                    if primary:
                        name,party = prefix[:primary.start()],prefix[primary.start()+1:]
                    else:
                        name,party = prefix.rsplit(',',1)
                    incumbent = '*' in name or '*' in party
                    name = re.sub('[*†‡]', '',name).strip().rstrip(',')
                    party = re.sub('[*†‡]', '',party).strip()
                    rows.append(dict(race_id=f'{state}-{int(district):02}' if chamber=='House' else f'{state}-SEN'+('-SPECIAL' if state in ('FL','OH') else ''),
                                     chamber=chamber,state=state,district=district if chamber=='House' else '',name=name,party_label=party,
                                     incumbent=str(incumbent).lower(),source_page=page_no,
                                     source_url='https://clerk.house.gov/member_info/electionInfo/2026/120-nominations.pdf',
                                     published_date='2026-10-08'))
    path = ROOT/'data/bootstrap/official_nominees.csv'
    with path.open('w',newline='',encoding='utf-8') as f:
        writer = csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader();writer.writerows(rows)
    (ROOT/'data/bootstrap/nominees_clean.txt').write_text('\n\f\n'.join(clean))
    print(len(rows),'candidate lines;',len(set(r['race_id'] for r in rows)),'races')
    print(sorted(set(r['party_label'] for r in rows)))


if __name__ == '__main__':
    main()
