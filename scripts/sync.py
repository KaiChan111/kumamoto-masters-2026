"""Fetch BWF public daily match cards; never replace verified data on extraction failure."""
import json, os, re, sys, datetime, pathlib, hashlib
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
import requests
ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
DIAG=ROOT/'diagnostics'
BASE='https://bwfworldtour.bwfbadminton.com/tournament/5216/kumamoto-masters-japan-2026/results/'
TYPES={'MS','WS','MD','WD','XD'}
FLAGS={'TPE':'🇹🇼','JPN':'🇯🇵','CHN':'🇨🇳','KOR':'🇰🇷','MAS':'🇲🇾','INA':'🇮🇩','THA':'🇹🇭','IND':'🇮🇳','DEN':'🇩🇰','FRA':'🇫🇷','USA':'🇺🇸','HKG':'🇭🇰','CAN':'🇨🇦','BUL':'🇧🇬','UKR':'🇺🇦','IRL':'🇮🇪','ESP':'🇪🇸'}

def norm(s):return re.sub(r'[^a-z0-9]','',s.casefold())

def load_names():
 names={}
 for f in DATA.glob('*.json'):
  if not re.fullmatch(r'\d{4}-\d{2}-\d{2}\.json',f.name):continue
  try: matches=json.loads(f.read_text())
  except Exception:continue
  for m in matches:
   for side in ('a','b'):
    for p in m[side]:
     if p.get('zh') and p.get('en') and p['zh']!=p['en']:names[norm(p['en'])]=p['zh']
 return names

def extract(html,names):
 soup=BeautifulSoup(html,'html.parser'); out=[]
 for card in soup.select('.match-card-wrapper'):
  content=card.get_text(' ',strip=True)
  num=re.search(r'\bMatch\s*(\d+)\b',content,re.I)
  court=re.search(r'\bCourt\s*(\d+)\b',content,re.I)
  typ=re.search(r'\b(MS|WS|MD|WD|XD)\b',content)
  if not (num and court and typ):continue
  teams=[]
  for wrapper in card.select('.participant-wrapper')[:2]:
   ps=[]
   for a in wrapper.select('a.participant-name'):
    en=a.get_text(' ',strip=True);country=a.get('data-country-code','')
    ps.append(dict(en=en,zh=names.get(norm(en),en),country=country,flag=FLAGS.get(country,'🏳️')))
   if ps:teams.append(ps)
  if len(teams)!=2:continue
  status='Subject to Change' if 'Subject to Change' in content else 'Followed By' if 'Followed By' in content else 'Starts'
  time_match=re.search(r'\b(\d{1,2}):(\d{2})\s*(AM|PM)\b',content,re.I)
  time=''
  if time_match:
   h=int(time_match.group(1))%12+(12 if time_match.group(3).upper()=='PM' else 0)
   time=f'{h:02d}:{time_match.group(2)}'
  out.append(dict(id=int(num.group(1)),time=time,court=int(court.group(1)),type=typ.group(1),a=teams[0],b=teams[1],status=status,tw=any(p['country']=='TPE' for team in teams for p in team),star=False))
 return sorted(out,key=lambda m:(m['time'] or '99:99',m['court']))

def diagnose(date, url, response=None, error=None):
 """Write safe response metadata only; no full third-party page or credentials."""
 DIAG.mkdir(exist_ok=True)
 info={'date':date,'url':url,'error':str(error) if error else None}
 if response is not None:
  body=response.text
  soup=BeautifulSoup(body,'html.parser')
  info.update({'http_status':response.status_code,
   'content_type':response.headers.get('content-type',''),
   'response_bytes':len(response.content),
   'sha256':hashlib.sha256(response.content).hexdigest(),
   'match_card_count':len(soup.select('.match-card-wrapper')),
   'title':soup.title.get_text(' ',strip=True)[:150] if soup.title else '',
   'script_sources':[tag.get('src') for tag in soup.select('script[src]')][:20],
   'has_next_data':bool(soup.select_one('script#__NEXT_DATA__')),
   'has_nuxt':('__NUXT__' in body),
   'has_match_card_string':('match-card-wrapper' in body),
   'has_captcha_marker':any(x in body.lower() for x in ('captcha','cloudflare challenge','access denied'))})
 (DIAG/(date+'.json')).write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n')
 print('DIAGNOSTIC',json.dumps(info,ensure_ascii=False),flush=True)

def sync(date):
 url=BASE+date
 print('Checking',url)
 try:
  r=requests.get(url,timeout=25,headers={'User-Agent':'Mozilla/5.0 (compatible; KumamotoScheduleViewer/2.1)'})
 except requests.RequestException as e:
  diagnose(date,url,error=e)
  raise
 diagnose(date,url,response=r)
 r.raise_for_status()
 if 'match-card-wrapper' not in r.text:raise RuntimeError('BWF response has no match cards; likely JS rendering or access block')
 names=load_names();out=extract(r.text,names)
 oldpath=DATA/(date+'.json');old=[]
 if oldpath.exists():old=json.loads(oldpath.read_text())
 if len(out)<5:raise RuntimeError(f'Only {len(out)} cards; refusing overwrite')
 # preserve manually reviewed Chinese names and editorial recommendations by matching participants, not position
 oldmap={tuple(sorted(norm(p['en']) for side in ('a','b') for p in m[side])):m for m in old}
 for m in out:
  key=tuple(sorted(norm(p['en']) for side in ('a','b') for p in m[side]))
  prev=oldmap.get(key)
  if prev:
   m['star']=prev.get('star',False)
   zh={norm(p['en']):p['zh'] for side in ('a','b') for p in prev[side] if p.get('zh')}
   for side in ('a','b'):
    for p in m[side]:p['zh']=zh.get(norm(p['en']),p['zh'])
 # preserve baseline if partial fetch likely missed matches
 if old and len(out)<len(old)*0.75:raise RuntimeError(f'Partial schedule {len(out)} vs {len(old)}; refusing overwrite')
 oldpath.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 print(f'OK {date}: {len(out)} matches')
 return len(out)

if __name__=='__main__':
 now=datetime.datetime.now(ZoneInfo('Asia/Tokyo')).date()
 dates=sys.argv[1:] or [(now+datetime.timedelta(days=i)).isoformat() for i in (0,1)]
 failed=[];results={}
 for date in dates:
  if not ('2026-11-10'<=date<='2026-11-15'):continue
  try:results[date]=sync(date)
  except Exception as e:print(f'FAILED {date}: {e}',file=sys.stderr);failed.append(date)
 # status always updated for visibility; retain last successful schedule files
 status={'checked_at_jst':datetime.datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds'),'successful_dates':results,'failed_dates':failed}
 (DATA/'sync-status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n')
 if failed:sys.exit(1)
