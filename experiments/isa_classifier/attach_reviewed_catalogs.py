"""Apply the same reviewed image policy to both frozen model predictions."""
import argparse
import json
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--folder',type=Path,required=True)
    p.add_argument('--policy',type=Path,required=True)
    args=p.parse_args()
    file=args.folder/'comparison.json'
    data=json.loads(file.read_text(encoding='utf8'))
    data['reviewedCatalogs']={}
    for language in ('es','en'):
        catalog=json.loads((args.policy/f'catalog-{language}.json').read_text(encoding='utf8'))
        catalog.pop('reviewedLoop',None)
        data['reviewedCatalogs'][language]=catalog
    file.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')

if __name__=='__main__':main()
