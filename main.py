from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pypdf import PdfReader
from docx import Document
from io import BytesIO
from pydantic import BaseModel
from pathlib import Path
import re, sqlite3, hashlib, secrets, json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = FastAPI(title="SkillGap AI API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
DB = Path(__file__).with_name("skillgap.db")

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
with db() as c:
    c.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    c.execute("CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id INTEGER NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id))")
    c.execute("CREATE TABLE IF NOT EXISTS analyses(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,filename TEXT,role TEXT,score INTEGER,matched TEXT,weak TEXT,missing TEXT,candidate_skills TEXT,roadmap TEXT,total_learning_hours INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(user_id) REFERENCES users(id))")

def pw(x): return hashlib.sha256(x.encode()).hexdigest()
def user_from(token):
    if not token: raise HTTPException(401,"Please log in first")
    with db() as c:
        r=c.execute("SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=?",(token,)).fetchone()
    if not r: raise HTTPException(401,"Session expired. Please log in again")
    return r
class Auth(BaseModel): email:str; password:str

SKILLS = {
    "Machine Learning Engineer": ["Python","Machine Learning","Scikit-learn","Pandas","NumPy","SQL","Git","Docker","FastAPI","Deep Learning","Cloud Deployment","TensorFlow","PyTorch"],
    "AI / ML Developer": ["Python","Machine Learning","Deep Learning","TensorFlow","PyTorch","NLP","BERT","Scikit-learn","Pandas","Git","Docker","FastAPI","SQL"],
    "Data Scientist": ["Python","SQL","Pandas","NumPy","Scikit-learn","Statistics","Machine Learning","Data Visualization","Power BI","Tableau","Git","Deep Learning"],
    "Frontend Developer": ["HTML","CSS","JavaScript","React","TypeScript","Git","REST API","Responsive Design","Tailwind CSS","Testing"],
    "Backend Developer": ["Python","Java","Node.js","REST API","FastAPI","SQL","PostgreSQL","MongoDB","Docker","Git","Authentication","Testing"],
    "Full Stack Developer": ["HTML","CSS","JavaScript","React","Node.js","REST API","SQL","MongoDB","Git","Docker","Authentication","Testing"]}
ALIASES={"python":"Python","py":"Python","scikit learn":"Scikit-learn","sklearn":"Scikit-learn","ml":"Machine Learning","machine learning":"Machine Learning","deep learning":"Deep Learning","dl":"Deep Learning","pandas":"Pandas","numpy":"NumPy","sql":"SQL","postgresql":"PostgreSQL","postgres":"PostgreSQL","mongo":"MongoDB","mongodb":"MongoDB","node":"Node.js","nodejs":"Node.js","javascript":"JavaScript","js":"JavaScript","typescript":"TypeScript","ts":"TypeScript","react":"React","reactjs":"React","html":"HTML","css":"CSS","tailwind":"Tailwind CSS","tailwind css":"Tailwind CSS","git":"Git","github":"Git","docker":"Docker","fastapi":"FastAPI","flask":"FastAPI","tensorflow":"TensorFlow","pytorch":"PyTorch","bert":"BERT","nlp":"NLP","rest api":"REST API","restful api":"REST API","api":"REST API","power bi":"Power BI","tableau":"Tableau","statistics":"Statistics","data visualization":"Data Visualization","responsive design":"Responsive Design","authentication":"Authentication","testing":"Testing","cloud deployment":"Cloud Deployment"}
LEARNING={
"Docker":{"hours":10,"level":"Beginner → Working","where":"Docker Get Started","url":"https://docs.docker.com/get-started/","type":"Guides + hands-on container project"},"FastAPI":{"hours":8,"level":"Beginner → Working","where":"FastAPI Tutorial","url":"https://fastapi.tiangolo.com/tutorial/","type":"Build a REST API"},"Cloud Deployment":{"hours":12,"level":"Beginner → Working","where":"AWS Skill Builder","url":"https://skillbuilder.aws/","type":"Deploy one full-stack application"},"Deep Learning":{"hours":18,"level":"Foundation → Working","where":"DeepLearning.AI","url":"https://www.deeplearning.ai/courses/","type":"Course + classification project"},"SQL":{"hours":8,"level":"Foundation → Working","where":"SQLBolt","url":"https://sqlbolt.com/","type":"Interactive SQL practice"},"Scikit-learn":{"hours":8,"level":"Foundation → Working","where":"scikit-learn User Guide","url":"https://scikit-learn.org/stable/user_guide.html","type":"Train and evaluate ML models"},"React":{"hours":12,"level":"Foundation → Working","where":"React Learn","url":"https://react.dev/learn","type":"Build a dashboard"},"JavaScript":{"hours":12,"level":"Foundation → Working","where":"MDN JavaScript Guide","url":"https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide","type":"Practice + browser projects"},"Node.js":{"hours":10,"level":"Beginner → Working","where":"Node.js Learn","url":"https://nodejs.org/en/learn","type":"Build a REST service"},"REST API":{"hours":6,"level":"Foundation → Working","where":"MDN HTTP / APIs","url":"https://developer.mozilla.org/en-US/docs/Learn_web_development/Extensions/Server-side","type":"Design and test an API"},"PostgreSQL":{"hours":8,"level":"Foundation → Working","where":"PostgreSQL Tutorial","url":"https://www.postgresql.org/docs/current/tutorial.html","type":"Schema + query practice"},"MongoDB":{"hours":8,"level":"Foundation → Working","where":"MongoDB University","url":"https://learn.mongodb.com/","type":"CRUD + data modeling"},"NLP":{"hours":14,"level":"Foundation → Working","where":"Hugging Face Course","url":"https://huggingface.co/learn/nlp-course/chapter1/1","type":"Text extraction project"},"BERT":{"hours":12,"level":"Foundation → Working","where":"Hugging Face Course","url":"https://huggingface.co/learn/nlp-course/chapter1/1","type":"Transformer project"},"TensorFlow":{"hours":12,"level":"Foundation → Working","where":"TensorFlow Tutorials","url":"https://www.tensorflow.org/tutorials","type":"Neural network project"},"PyTorch":{"hours":12,"level":"Foundation → Working","where":"PyTorch Tutorials","url":"https://pytorch.org/tutorials/","type":"Neural network project"},"Git":{"hours":5,"level":"Foundation → Working","where":"GitHub Skills","url":"https://skills.github.com/","type":"Branching + pull requests"},"HTML":{"hours":5,"level":"Foundation → Working","where":"MDN HTML","url":"https://developer.mozilla.org/en-US/docs/Web/HTML","type":"Build semantic pages"},"CSS":{"hours":6,"level":"Foundation → Working","where":"MDN CSS","url":"https://developer.mozilla.org/en-US/docs/Web/CSS","type":"Responsive layout project"},"TypeScript":{"hours":10,"level":"Foundation → Working","where":"TypeScript Handbook","url":"https://www.typescriptlang.org/docs/handbook/intro.html","type":"Convert a JS app"},"Testing":{"hours":6,"level":"Foundation → Working","where":"MDN Testing","url":"https://developer.mozilla.org/en-US/docs/Learn/Tools_and_testing","type":"Unit + integration tests"},"Power BI":{"hours":10,"level":"Foundation → Working","where":"Microsoft Learn","url":"https://learn.microsoft.com/training/powerplatform/power-bi/","type":"Build an interactive dashboard"},"Tableau":{"hours":10,"level":"Foundation → Working","where":"Tableau Learning","url":"https://www.tableau.com/learn/training","type":"Build a dashboard"},"Data Visualization":{"hours":8,"level":"Foundation → Working","where":"Matplotlib Tutorials","url":"https://matplotlib.org/stable/tutorials/","type":"Create an analytical dashboard"},"Statistics":{"hours":12,"level":"Foundation → Working","where":"Khan Academy Statistics","url":"https://www.khanacademy.org/math/statistics-probability","type":"Probability + inference practice"},"NumPy":{"hours":5,"level":"Foundation → Working","where":"NumPy Learn","url":"https://numpy.org/learn/","type":"Numerical computing practice"},"Pandas":{"hours":6,"level":"Foundation → Working","where":"Pandas Tutorials","url":"https://pandas.pydata.org/docs/getting_started/intro_tutorials/","type":"Data cleaning + analysis"}}

def extract_text(data, filename):
    try:
        n=(filename or '').lower()
        if n.endswith('.pdf'):
            return '\n'.join((p.extract_text() or '') for p in PdfReader(BytesIO(data)).pages)
        if n.endswith('.docx'): return '\n'.join(p.text for p in Document(BytesIO(data)).paragraphs)
        if n.endswith('.doc'): raise ValueError('Legacy .doc is not supported. Save it as .docx or PDF.')
        return data.decode('utf-8',errors='ignore')
    except Exception as e: raise ValueError(f'Could not parse resume: {e}')
def canonicalize(text):
    low=re.sub(r'[^a-z0-9+#.\- ]+',' ',text.lower()); found=[]
    for a,c in sorted(ALIASES.items(),key=lambda x:len(x[0]),reverse=True):
        if re.search(r'(?<![a-z0-9])'+re.escape(a)+r'(?![a-z0-9])',low) and c not in found: found.append(c)
    return found
def semantic_score(text, skills):
    try:
        v=TfidfVectorizer(ngram_range=(1,2),stop_words='english'); m=v.fit_transform([text,' '.join(skills)])
        return float(cosine_similarity(m[0:1],m[1:2])[0][0])
    except Exception:return 0.0

def save_analysis(user_id, result):
    with db() as c:
        c.execute("INSERT INTO analyses(user_id,filename,role,score,matched,weak,missing,candidate_skills,roadmap,total_learning_hours) VALUES(?,?,?,?,?,?,?,?,?,?)",(user_id,result['filename'],result['role'],result['score'],json.dumps(result['matched']),json.dumps(result['weak']),json.dumps(result['missing']),json.dumps(result['candidate_skills']),json.dumps(result['roadmap']),result['total_learning_hours']))

def row_result(r):
    return {'id':r['id'],'filename':r['filename'],'role':r['role'],'score':r['score'],'matched':json.loads(r['matched']), 'weak':json.loads(r['weak']),'missing':json.loads(r['missing']),'candidate_skills':json.loads(r['candidate_skills']),'roadmap':json.loads(r['roadmap']),'total_learning_hours':r['total_learning_hours'],'date':r['created_at'],'analyzed':True}

@app.get('/')
def root(): return {'name':'SkillGap AI API','status':'running','docs':'/docs'}
@app.get('/health')
def health(): return {'status':'ok'}
@app.post('/auth/register')
def register(a:Auth):
    email=a.email.strip().lower()
    if len(a.password)<6: raise HTTPException(400,'Password must be at least 6 characters')
    try:
        with db() as c:
            cur=c.execute('INSERT INTO users(email,password_hash) VALUES(?,?)',(email,pw(a.password))); uid=cur.lastrowid
            token=secrets.token_urlsafe(32); c.execute('INSERT INTO sessions(token,user_id) VALUES(?,?)',(token,uid))
        return {'token':token,'email':email}
    except sqlite3.IntegrityError: raise HTTPException(409,'An account with this email already exists')
@app.post('/auth/login')
def login(a:Auth):
    with db() as c:r=c.execute('SELECT * FROM users WHERE email=? AND password_hash=?',(a.email.strip().lower(),pw(a.password))).fetchone()
    if not r: raise HTTPException(401,'Invalid email or password')
    token=secrets.token_urlsafe(32)
    with db() as c:c.execute('INSERT INTO sessions(token,user_id) VALUES(?,?)',(token,r['id']))
    return {'token':token,'email':r['email']}
@app.get('/auth/me')
def me(token:str):
    u=user_from(token); return {'email':u['email']}
@app.get('/history')
def history(token:str):
    u=user_from(token)
    with db() as c: rows=c.execute('SELECT * FROM analyses WHERE user_id=? ORDER BY id DESC',(u['id'],)).fetchall()
    return [row_result(r) for r in rows]
@app.get('/history/{analysis_id}')
def history_one(analysis_id:int,token:str):
    u=user_from(token)
    with db() as c:r=c.execute('SELECT * FROM analyses WHERE id=? AND user_id=?',(analysis_id,u['id'])).fetchone()
    if not r: raise HTTPException(404,'Analysis not found')
    return row_result(r)
@app.post('/analyze')
async def analyze(token:str,resume:UploadFile=File(...),role:str=Form(...)):
    u=user_from(token)
    if role not in SKILLS: raise HTTPException(400,'Unknown target role')
    data=await resume.read()
    if len(data)>10*1024*1024: raise HTTPException(413,'Resume must be 10 MB or smaller')
    if not data: raise HTTPException(400,'Empty resume')
    try:text=extract_text(data,resume.filename or 'resume')
    except ValueError as e:raise HTTPException(400,str(e))
    if len(text.strip())<40:raise HTTPException(400,'Very little readable text was found. Try a text-based PDF or DOCX.')
    candidate=canonicalize(text); required=SKILLS[role]; matched=[s for s in required if s in candidate]; missing=[s for s in required if s not in candidate]
    semantic=semantic_score(text,required); coverage=len(matched)/len(required); score=round(min(100,(coverage*90)+(semantic*10)))
    weak=[]
    if semantic>0.35 and missing: weak=missing[:min(2,len(missing))]; missing=missing[len(weak):]
    roadmap=[]
    for skill in weak+missing: roadmap.append({'skill':skill,**LEARNING.get(skill,{'hours':8,'level':'Foundation → Working','where':'Curated learning resources','url':'https://developer.mozilla.org/','type':'Course + practice project'})})
    result={'filename':resume.filename,'role':role,'score':score,'matched':matched,'weak':weak,'missing':missing,'candidate_skills':candidate,'semantic_similarity':round(semantic,3),'roadmap':roadmap,'total_learning_hours':sum(x['hours'] for x in roadmap),'analyzed':True}
    save_analysis(u['id'],result); return result
