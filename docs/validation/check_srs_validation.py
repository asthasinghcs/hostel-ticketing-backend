"""Disposable API boundary checks for the academic SRS. Never uses a live DB."""
import os,sys,tempfile,json
from pathlib import Path
from contextlib import closing
BACKEND=Path(os.environ.get('HOSTEL_BACKEND_ROOT',str(Path(__file__).resolve().parents[2])))
sys.path.insert(0,str(BACKEND))
os.environ['DATABASE_URL']='';os.environ['DATABASE_URL_UNPOOLED']=''
folder=tempfile.TemporaryDirectory(dir=os.environ.get('HOSTEL_TEST_TMP'))
os.environ['DATABASE_PATH']=str(Path(folder.name)/'validation.db')
from app import app,get_db
from werkzeug.security import generate_password_hash
app.config['TESTING']=True
client=app.test_client();results=[];counter=24058000

def record(case,expected,response,parameter):
 actual=response.status_code;results.append(dict(id=case,parameter=parameter,expected=expected,actual=actual,passed=actual==expected))
 if actual!=expected:raise AssertionError((case,expected,actual,response.json))
 return response

def signup(case,expected,**changes):
 global counter
 counter+=1
 data=dict(name='Validation resident',email=f'{counter}@kiit.ac.in',password='Validation!123',hostel_block='KP-1')
 data.update(changes);return record(case,expected,client.post('/api/signup',json=data),str({k:('length '+str(len(v)) if k in ('password','name') else v) for k,v in changes.items()}))

try:
 s=signup('BV01',201,email='24054001@kiit.ac.in').json
 signup('BV02',400,email='student@gmail.com')
 signup('BV03',400,email='student@kiit.ac.in')
 signup('BV04',400,email='24054001@kiit.ac.in.evil.com')
 signup('BV05',400,email='24054001@other.ac.in')
 signup('BV06',400,email='12345@kiit.ac.in')
 signup('BV07',201,email='123456@kiit.ac.in')
 signup('BV08',201,email='123456789012@kiit.ac.in')
 signup('BV09',400,email='1234567890123@kiit.ac.in')
 signup('BV10',201,email='24054002@KIIT.AC.IN')
 signup('BV11',400,password='x'*7)
 signup('BV12',201,password='x'*8)
 signup('BV13',201,password='x'*128)
 signup('BV14',400,password='x'*129)
 signup('BV15',400,name='')
 signup('BV16',201,name='N'*100)
 signup('BV17',400,name='N'*101)
 signup('BV18',409,email='24054001@kiit.ac.in')
 signup('BV19',403,role='admin')
 signup('BV20',400,hostel_block='KP-99')
 auth={'Authorization':'Bearer '+s['token']}
 def ticket(case,expected,**updates):
  data=dict(category='Wi-Fi',description='Boundary check',hostel_block='KP-1');data.update(updates)
  return record(case,expected,client.post('/api/tickets',json=data,headers=auth),str({k:(len(v) if k in ('description','floor','room_no') else v) for k,v in updates.items()}))
 t=ticket('BV21',201).json
 ticket('BV22',400,description='')
 ticket('BV23',201,description='D'*4000)
 ticket('BV24',400,description='D'*4001)
 ticket('BV25',400,category='Unsupported')
 ticket('BV26',201,floor='F'*30,room_no='R'*30)
 ticket('BV27',400,floor='F'*31)
 ticket('BV28',400,room_no='R'*31)
 ticket('BV29',403,hostel_block='KP-2')
 record('BV30',403,client.get('/api/tickets?hostel_block=KP-2',headers=auth),'Other hostel filter')
 record('BV31',401,client.get('/api/overview'),'Missing bearer token')
 tid=t['id']
 record('BV32',201,client.post(f'/api/tickets/{tid}/vote',json={},headers=auth),'First own-hostel vote')
 record('BV33',409,client.post(f'/api/tickets/{tid}/vote',json={},headers=auth),'Duplicate vote')
 record('BV34',403,client.patch(f'/api/tickets/{tid}/status',json={'status':'Resolved'},headers=auth),'Student status update')
 record('BV35',400,client.post(f'/api/tickets/{tid}/comments',json={'text':''},headers=auth),'Comment length 0')
 record('BV36',201,client.post(f'/api/tickets/{tid}/comments',json={'text':'C'*2000},headers=auth),'Comment length 2000')
 record('BV37',400,client.post(f'/api/tickets/{tid}/comments',json={'text':'C'*2001},headers=auth),'Comment length 2001')
 record('BV38',400,client.get('/api/overview?date_from=2026-10-27&date_to=2026-10-21',headers=auth),'Reversed dates')
 record('BV39',400,client.get('/api/overview?date_from=2026-02-30',headers=auth),'Impossible date')
 record('BV40',200,client.get('/api/overview?date_from=2026-10-21&date_to=2026-10-27',headers=auth),'Valid inclusive date range')
 report={'date':'2026-10-27','database':'isolated temporary SQLite','passed':sum(r['passed'] for r in results),'total':len(results),'checks':results}
 Path(os.environ.get('SRS_REPORT_PATH',str(Path(__file__).with_name('SRS_Validation_Results.json')))).write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(f'Boundary and validation checks: {report["passed"]}/{report["total"]} passed; live database not used.')
finally:
 folder.cleanup()
