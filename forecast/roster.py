"""Independent apportionment and Senate-class checks."""
APPORTIONMENT = dict(AL=7,AK=1,AZ=9,AR=4,CA=52,CO=8,CT=5,DE=1,FL=28,GA=14,HI=2,
                    ID=2,IL=17,IN=9,IA=4,KS=4,KY=6,LA=6,ME=2,MD=8,MA=9,MI=13,
                    MN=8,MS=4,MO=8,MT=2,NE=3,NV=4,NH=2,NJ=12,NM=3,NY=26,NC=14,
                    ND=1,OH=15,OK=5,OR=6,PA=17,RI=2,SC=7,SD=1,TN=9,TX=38,UT=4,
                    VT=1,VA=11,WA=10,WV=2,WI=8,WY=1)
CLASS_2 = set('AL AK AR CO DE GA ID IL IA KS KY LA ME MA MI MN MS MT NE NH NJ NM NC OK OR RI SC SD TN TX VA WV WY'.split())


def validate_roster(rows, holdovers):
    house = [r for r in rows if r['chamber'] == 'House']
    senate = [r for r in rows if r['chamber'] == 'Senate']
    if len({r['race_id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate race identifiers')
    expected = {(st, district) for st, n in APPORTIONMENT.items() for district in range(1, n+1)}
    actual = {(r['state'], int(r['district']) or 1) for r in house}
    if len(house) != 435 or actual != expected:
        raise ValueError(f'House roster mismatch: missing={expected-actual}, extra={actual-expected}')
    regular = {r['state'] for r in senate if str(r.get('special', '')).lower() not in ('true','1','yes')}
    special = {r['state'] for r in senate if str(r.get('special', '')).lower() in ('true','1','yes')}
    if len(senate) != 35 or regular != CLASS_2 or special != {'FL','OH'}:
        raise ValueError('Senate roster must contain 33 Class II races plus FL/OH specials')
    if len(holdovers) != 65:
        raise ValueError('Expected 65 Senate holdovers')
    keys = {(r['state'], int(r['seat_class'])) for r in senate}
    old = {(r['state'], int(r['seat_class'])) for r in holdovers}
    if len(old) != 65 or keys & old or len(keys | old) != 100:
        raise ValueError('Contested and holdover Senate seats overlap or are incomplete')
