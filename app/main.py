from fastapi import FastAPI, Request, Response, Form, Cookie, Query, File, Header, UploadFile, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, PlainTextResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from jinja2 import environment, pass_context
from fastapi.security import OAuth2, APIKeyCookie, OAuth2PasswordBearer, OAuth2PasswordRequestForm, HTTPBearer, OAuth2AuthorizationCodeBearer
from fastapi.openapi.models import OAuthFlows as OAuthFlowsModel
from fastapi.encoders import jsonable_encoder
#from jose import JWTError, jwt
#from passlib.context import CryptContext
#from passlib.handlers.sha2_crypt import sha512_crypt as crypto
from fastapi.staticfiles import StaticFiles
from typing import Callable, Iterator, Union, Optional, Annotated, List, Dict, Any, Literal
from enum import Enum
from fastapi.security.utils import get_authorization_scheme_param
from starlette.requests import Request
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN, HTTP_302_FOUND,HTTP_303_SEE_OTHER
from starlette.exceptions import HTTPException as StarletteHTTPException
from sse_starlette.sse import EventSourceResponse
import pandas as pd
import numpy as np
import itertools
from datetime import datetime, timedelta, timezone
import app.auth as auth
import aiosqlite, sqlite3
import httpx
#import aiofiles
import asyncio
import json, re, os, sys
from io import BytesIO, StringIO
from fastapi.middleware.wsgi import WSGIMiddleware
from pathlib import Path
import app.myalma as myalma
import app.myadmin as myadmin
from pydantic import BaseModel, EmailStr
from pydantic.dataclasses import dataclass
import hashlib
import datetime as dt
import logging
import logging.handlers
import app.mylangchain as mylangchain
from app.paginator.paginator import Paginator


handler = logging.handlers.RotatingFileHandler("logFile.log", maxBytes=10000)
logging.basicConfig(handlers=[handler], level=logging.WARNING)
logging.basicConfig(filename="logFile.log", 
                    format='%(asctime)s - %(levelname)s: %(message)s', 
                    datefmt='%d/%m/%Y %I:%M:%S %p')


MESSAGE_STREAM_DELAY = 4  # second
MESSAGE_STREAM_RETRY_TIMEOUT = 15000  # millisecond

def current_aa_year():
    if dt.datetime.now().month < 9:
        return dt.datetime.now().year-1
    return dt.datetime.now().year

app = FastAPI()


p = Path(__file__).parent.resolve()
st_abs_file_path = p/ "static/"
st_abs_templates = p/"templates/"
app.mount("/static", StaticFiles(directory=st_abs_file_path), name="static")
templates = Jinja2Templates(directory=st_abs_templates, autoescape=True)
p = p / "dbfiles"

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request, exc: HTTPException):
    return templates.TemplateResponse("/login.html", {"request": request})

@app.post("/token")
def login_for_access_token(
    response: Response, 
    form_data: OAuth2PasswordRequestForm = Depends()) -> Dict[str, str]:
    user = auth.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    access_token = auth.create_access_token(data={"username": user['username']}) # type: ignore
    
    # Set an HttpOnly cookie in the response. `httponly=True` prevents 
    # JavaScript from reading the cookie.
    response.set_cookie(
        key=auth.settings.COOKIE_NAME, 
        value=f"Bearer {access_token}", 
        httponly=True
    )  
    return {auth.settings.COOKIE_NAME: access_token, "token_type": "bearer"}


class LoginForm:
    def __init__(self, request: Request):
        self.request: Request = request
        self.errors: List = []
        self.username: Optional[str] = None
        self.password: Optional[str] = None

    async def load_data(self):
        form = await self.request.form()
        self.username = str(form.get("username"))
        self.password = str(form.get("password"))

    async def is_valid(self):
        if not self.username or not (self.username.__contains__("@")):
            self.errors.append("Email is required")
        if not self.password or not len(self.password) >= 4:
            self.errors.append("A valid password is required")
        if not self.errors:
            return True
        return False

@app.get("/login", response_class=HTMLResponse)
def login_get(request: Request):
    return templates.TemplateResponse("/login.html", {"request": request}) 

@app.post("/login", response_class=HTMLResponse)
async def login_post(request: Request):
    form = LoginForm(request)
    await form.load_data()
    if await form.is_valid():
        try:
            response = RedirectResponse("/", status.HTTP_302_FOUND)
            login_for_access_token(response=response, form_data=form) # type: ignore
            form.__dict__.update(msg="Login Successful!")
            return response
        except HTTPException:
            form.__dict__.update(msg="")
            if form.__dict__.get("errors") is None:
                form.__dict__["errors"] = []
            form.__dict__["errors"].append("Attenzione: Email o Password errate")
            return templates.TemplateResponse("/login.html", {"request": request, 'res': form.__dict__["errors"]})
    return templates.TemplateResponse("/login.html", form.__dict__)

@app.get("/logout", response_class=HTMLResponse)
def logout_get():
    #del os.environ[f'{db}MYVAR'] # delete the environment variable about LLM API key
    response = RedirectResponse(url="/")
    response.delete_cookie(auth.settings.COOKIE_NAME)
    return response



@app.get('/stream')
async def message_stream(request: Request, user: auth.User = Depends(auth.get_current_user_from_token),
                         db: str = Depends(auth.get_tenant_hash)):
    def new_messages():
        with sqlite3.connect(p/f'{db}.db') as conn:
            conn.row_factory = sqlite3.Row
            qres = conn.execute("SELECT * FROM msg ORDER BY date DESC")
            qres = qres.fetchall()
            return qres
    async def event_generator(request: Request):
        while True:
            if await request.is_disconnected():
                break
            try:
                res = new_messages()
                if res:
                    yield {
                            "event": "message",
                            "retry": MESSAGE_STREAM_RETRY_TIMEOUT,
                            "data": '<div></div>'.join([f"<p>Data: {x['date']}; Messaggio: {x['message']}; Step: q={x['q']}</p>"
                                                        for x in res])
                    }
                await asyncio.sleep(MESSAGE_STREAM_DELAY)
            except asyncio.CancelledError as e:
                raise e
            finally:
                pass
    return EventSourceResponse(event_generator(request))

############## CONFIG docenti #####################

@app.get("/base", response_class=HTMLResponse)
async def config_docenti(request: Request, user: auth.User = Depends(auth.get_current_user_from_token)):
    return templates.TemplateResponse("config.html", {"request": request, "user": user})

@app.post("/configfile", response_class=HTMLResponse)
async def fetch_file(request: Request,
    file: Annotated[UploadFile, File(description="A file read as UploadFile")], 
    user: auth.User = Depends(auth.get_current_user_from_token), 
    sep: str = Form(None), db: str = Depends(auth.get_tenant_hash)):
    contents = await file.read()
    buffer = BytesIO(contents)
    df = pd.read_csv(buffer, sep=sep, engine='python')
    buffer.close()
    await file.close()
    message = "Qualcosa non ha funzionato correttamente"
    with sqlite3.connect(p/f'{db}.db') as conn:
        df.to_sql('tuttidocenti', conn, if_exists='replace', index=False)
    message = "I dati sono stati caricati correttamente"
    return templates.TemplateResponse('partial_config.html', {"request": request, "user": user, "message": message})


###################################### I N I Z I O  #########################################



@app.get("/uploadfile", response_class=HTMLResponse)
async def upload_file(request: Request, user: auth.User = Depends(auth.get_current_user_from_token)):
    return templates.TemplateResponse("uploadfile.html", {"request": request, "user": user})

@app.post("/uploadfile", response_class=HTMLResponse)
async def create_upload_file(request: Request,
    file: Annotated[UploadFile, File(description="A file read as UploadFile")], 
    user: auth.User = Depends(auth.get_current_user_from_token), 
    inlineRadio: Literal['fail', 'replace', 'append'] = Form(...), sep: str = Form(None),
    db: str = Depends(auth.get_tenant_hash)):
    contents = await file.read()
    buffer = BytesIO(contents)
    df = pd.read_csv(buffer, sep=sep, engine='python')
    df = myalma.normalize_columns(df, 'adozioni')
    df['prof_id'] = df['prof_id'].fillna(0).astype(int)
    df['insegnamento_id'] = df['insegnamento_id'].fillna(0).astype(int)
    df['insegnamento_prof'] = df['insegnamento_prof'].fillna(' ')
    df['insegnamento_prof'] = df['insegnamento_prof'].apply(lambda x: myalma.clear_prof_name(x))
    df['materia_ssd_cod'] = df['materia_ssd_cod'].str.replace(';',' ')
    results = df[:5].to_dict(orient='records')
    buffer.close()
    await file.close()
    df_merged = myalma.get_prof_id_file(df, db)
    df_merged['prof_id'] = df_merged['prof_id'].fillna(0).astype(int)
    df_merged['insegnamento_id'] = df_merged['insegnamento_id'].fillna(0).astype(int)
    with sqlite3.connect(p/f'{db}.db') as conn:
        df_merged.to_sql('adozioni', conn, if_exists=inlineRadio, index=False)
        conn.row_factory = sqlite3.Row
        myalma.update_msg(conn, f"Caricato file con adozioni - {inlineRadio}")
    if request.headers.get('HX-Request'):
        return templates.TemplateResponse('partial_caricafile.html', {"request": request, "user": user, "adozioni": results})
    return templates.TemplateResponse("uploadfile.html", {"request": request, "user": user})

@app.get("/universita")
async def universita(request: Request, db: str = Depends(auth.get_tenant_hash), 
                     user: auth.User = Depends(auth.get_current_user_from_token)):
    if user['is_active'] == 0: # type: ignore
        return templates.TemplateResponse("dummy_abbonamento_api.html", {"request": request, "user": user})
    msg=''
    txt_json = ''
    with httpx.Client() as client:
        try:
            r = client.get('https://almalibri.it/api/lista_uni/')
            txt_json = r.json()
        except Exception:
            return templates.TemplateResponse('universita.html', {"request": request, "user": user, "msg": Exception} )
    if txt_json['request_status'] != 'Operazione non consentita':
        df = pd.DataFrame(txt_json['data'])
        with sqlite3.connect(p/f'{db}.db') as conn:
            df.to_sql('universita', conn, if_exists='replace', index=False)
        return templates.TemplateResponse('universita.html', {"request": request, "unis": txt_json['data'], "user": user})
    else:
        return templates.TemplateResponse('universita.html', {"request": request, "msg": txt_json['request_status'], "user": user})
        
        
@app.post("/universita")
async def post_universita(request: Request, user: auth.User = Depends(auth.get_current_user_from_token),
                          db: str = Depends(auth.get_tenant_hash)):
    form = await request.form()
    data = jsonable_encoder(form)
    with sqlite3.connect(p/f'{db}.db') as conn:
        conn.row_factory = sqlite3.Row
        q = myalma.get_q(conn)
        count_res = conn.execute("SELECT COUNT(*) FROM adozioni_res").fetchone() #count = [lambda:0, lambda:N+1][count==N]()
        if count_res and count_res[0] == 0:
            res = conn.execute("SELECT * FROM adozioni WHERE uni_cod IN (SELECT key FROM json_each(?))", (json.dumps(data),))
        else:
            res = conn.execute("SELECT * FROM adozioni_res WHERE uni_cod IN (SELECT key FROM json_each(?))", (json.dumps(data),))
        names = [x[0] for x in res.description]
        txt = res.fetchall()
        dfres = pd.DataFrame(txt, columns=names)
        if len(dfres) == 0:
            message_tpl = True
        else:
            message_tpl = False
        dfres.to_sql('adozioni_res', conn, if_exists='replace', index=False)
        message = f"uni_cod: {' '.join(data)} selezionati"
        myalma.update_msg(conn, message)
    if request.headers.get('HX-Request'):
            return templates.TemplateResponse('partial_uni.html', {"request": request, "items": txt, 
                                                                   "message_tpl": message_tpl, "user":user})
    
@app.get("/adozioni") ## SSD  ############
async def get_adozioni(request: Request, page: int=1, user: auth.User = Depends(auth.get_current_user_from_token), 
                       db: str = Depends(auth.get_tenant_hash)):
    async with aiosqlite.connect(p/f'{db}.db') as conn:
        conn.row_factory = aiosqlite.Row
        q = await myalma.aget_q(conn)
        count_res = await conn.execute("SELECT COUNT(*) FROM adozioni_res")
        count_res = await count_res.fetchone()
        if count_res and count_res[0] == 0:
            cursor = await conn.execute("""
                SELECT DISTINCT uni_cod, laurea_nome, materia_nome, materia_ssd_cod, insegnamento_prof, 
                isbn, autori, curatori, titolo, editore, testo_obb FROM adozioni;
            """)
        else:
            cursor = await conn.execute("""
                SELECT DISTINCT uni_cod, laurea_nome, materia_nome, materia_ssd_cod, insegnamento_prof, 
                isbn, autori, curatori, titolo, editore, testo_obb FROM adozioni_res;
            """)
        results = await cursor.fetchall()
        await myalma.aupdate_msg(conn, f"Visualizzate le adozioni e i gli SSD.")
    paginator = Paginator(results, 100)
    page = paginator.get_page(page) # type: ignore
    return templates.TemplateResponse('adozioni.html',
                                      {"request": request, "paginator": paginator, "page": page, "user":user})

@app.post("/adozioni")  ## SSD ############
async def post_adozioni(request: Request,  user: auth.User = Depends(auth.get_current_user_from_token), 
                        db: str = Depends(auth.get_tenant_hash)):
    form = await request.form()
    data = jsonable_encoder(form)
    data = [x for x in data]
    message_tpl = f"La adozioni selezionate con SSD {' '.join(data)}."
    with sqlite3.connect(p/f'{db}.db') as conn:
        q = myalma.get_q(conn)
        count_res = conn.execute("SELECT COUNT(*) FROM adozioni_res").fetchone()
        if count_res[0] == 0:
            cursor = conn.execute("SELECT * FROM adozioni WHERE materia_ssd_cod IN (SELECT value FROM json_each(?))", (json.dumps(data),))
        else:
            cursor = conn.execute("SELECT * FROM adozioni_res WHERE materia_ssd_cod IN (SELECT value FROM json_each(?))", (json.dumps(data),))
        names = [x[0] for x in cursor.description]
        txt = cursor.fetchall()
        dfres = pd.DataFrame(txt, columns=names)
        dfres.to_sql('adozioni_res', conn, if_exists='replace', index=False)
        message = f"ssd: {data}"
        myalma.update_msg(conn, message)
    if request.headers.get('HX-Request'):
        return templates.TemplateResponse('partial_adozioni.html', {"request": request, "adozioni": txt, 
                                                                    "user":user, "message_tpl": message_tpl})

@app.post("/form")
async def post_form(request: Request, user: auth.User = Depends(auth.get_current_user_from_token), 
                db: str = Depends(auth.get_tenant_hash),
                uni_cod: str = Form(None),
                inlineRadio: Literal['fail', 'replace', 'append'] = Form(...),
                a_a: str = Form(...),
                laurea_nome: str = Form(None),
                laurea_tipo: str = Form(None),
                laurea_classe_cod: str = Form(None),
                curr_nome: str = Form(None),
                materia_nome: str = Form(None),
                materia_ssd_cod: List[str] = Form(None),
                curr_materia_anno: str = Form(None),
                curr_materia_periodo: str = Form(None),
                insegnamento_prof: str = Form(None),
                isbn: List[str] = Form(None),
                autori: str = Form(None),
                titolo: str = Form(None),
                editore: List[str] = Form(None),
                testo_obb: str = Form(None),
                page: str = Form(None),
                ult_agg: str = Form(None)):
    if user['is_active'] == 0: # type: ignore
        return templates.TemplateResponse("dummy_abbonamento_api.html", {"request": request, "user": user})
    params = [('uni_cod', uni_cod), ('a_a', a_a), ('laurea_nome', laurea_nome), ('laurea_tipo', laurea_tipo),
                ('laurea_classe_cod', laurea_classe_cod), ('curr_nome', curr_nome), ('materia_nome', materia_nome),
                ('materia_ssd_cod', materia_ssd_cod), ('curr_materia_anno', curr_materia_anno),
                ('curr_materia_periodo', curr_materia_periodo), ('insegnamento_prof', insegnamento_prof),
                ('isbn', isbn), ('autori', autori), ('titolo', titolo), ('editore', editore), ('testo_obb', testo_obb),
                ('page', page), ('ult_agg', ult_agg)]
    filtered_params = [(key,value) for key, value in params if (value != [''] and value != '' and value != None)]
    print(filtered_params)
    ado = myalma.get_alma_api_multiple(filtered_params)
    df = pd.DataFrame(itertools.chain.from_iterable(ado)) if ado else pd.DataFrame()
    msg = ''
    if not df.empty:
        df = myalma.normalize_columns(df, 'adozioni')
        df['laurea_iscritti'] = df['laurea_iscritti'].fillna(0).astype(int)
        df['laurea_matricole'] = df['laurea_matricole'].fillna(0).astype(int)
        df['prof_id'] = df['prof_id'].fillna(0).astype(int)
        df['insegnamento_id'] = df['insegnamento_id'].fillna(0).astype(int)
        df['insegnamento_prof'] = df['insegnamento_prof'].fillna(' ')
        df['insegnamento_prof'] = df['insegnamento_prof'].apply(lambda x: myalma.clear_prof_name(x))
        df['materia_ssd_cod'] = df['materia_ssd_cod'].str.replace(';',' ')
        df = df.drop_duplicates()
    else:
        adozioni = []
        msg = 'Non vi sono risultati'
        return templates.TemplateResponse('partial_adozioni.html', {"request": request, "adozioni": adozioni, "user":user, "message_tpl": msg})
    with sqlite3.connect(p/f'{db}.db') as conn:
        conn.row_factory = sqlite3.Row
        df.to_sql('adozioni', conn, if_exists=inlineRadio, index=False)
        df.to_csv(p/f'{db}adozioni_alma.csv', sep=',', index=False)
        myalma.update_msg(conn, f"Scaricati dati con parametri: {filtered_params}")
    df = df[['uni_cod', 'laurea_nome', 'materia_nome', 'materia_ssd_cod', 'insegnamento_prof', 'isbn', 'titolo', 'editore']]
    adozioni = df.to_dict(orient='records')
    if request.headers.get('HX-Request'):
        return templates.TemplateResponse('partial_adozioni.html', {"request": request, "user":user, 
                                                                    "adozioni": adozioni, "message_tpl": msg})
    return templates.TemplateResponse("form.html", {"request": request, "user": user})

@app.get("/api_alma", response_class=PlainTextResponse)
def get_csv_api_alma(user: auth.User = Depends(auth.get_current_user_from_token), db: str = Depends(auth.get_tenant_hash)):
    if os.path.isfile(p/f'{db}adozioni_alma.csv'):
        return FileResponse(
            p/f'{db}adozioni_alma.csv',
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment"})

@app.get("/form", response_class=HTMLResponse)
async def getform(request: Request, user: auth.User = Depends(auth.get_current_user_from_token)):
    if user['is_active'] == 0: # type: ignore
        return templates.TemplateResponse("dummy_abbonamento_api.html", {"request": request, "user": user})
    return templates.TemplateResponse("form.html", {"request": request, "user": user})


@app.get("/insegnamenti")
async def get_insegnamenti(request: Request, page: int=1, user: auth.User = Depends(auth.get_current_user_from_token), 
                           db: str = Depends(auth.get_tenant_hash)):
    with sqlite3.connect(p/f'{db}.db') as conn:
        conn.row_factory = sqlite3.Row
        q = myalma.get_q(conn)
        count_res = conn.execute("SELECT COUNT(*) FROM adozioni_res")
        count_res = count_res.fetchone()
        if count_res[0] == 0:
            cursor = conn.execute("""
                    SELECT DISTINCT uni_cod, laurea_nome, materia_nome, materia_ssd_cod, insegnamento_prof, insegnamento_id, prof_id FROM adozioni
                    ORDER BY uni_cod, laurea_nome, materia_nome;""")
        else:
            cursor = conn.execute("""
                    SELECT DISTINCT uni_cod, laurea_nome, materia_nome, materia_ssd_cod, insegnamento_prof, insegnamento_id, prof_id FROM adozioni_res
                    ORDER BY uni_cod, laurea_nome, materia_nome;""")
        results = cursor.fetchall()
        myalma.update_msg(conn, f"Visualizzati gli insegnamenti")
    paginator = Paginator(results, 100)
    page = paginator.get_page(page) # type: ignore
    return templates.TemplateResponse('insegnamenti.html',
                                      {"request": request, "paginator": paginator, "page": page, "user": user})

    
    
@app.post("/insegnamenti")
async def post_insegnamenti(request: Request, user: auth.User = Depends(auth.get_current_user_from_token), 
                            db: str = Depends(auth.get_tenant_hash)):
    form = await request.form()
    data = jsonable_encoder(form)
    data = [x for x in data]
    message_tpl = f"Gli insegnamenti selezionati con i docenti che hanno prof_id {' '.join(data)}."
    with sqlite3.connect(p/f'{db}.db') as conn:
        conn.row_factory = sqlite3.Row
        q = myalma.get_q(conn)
        count_res = conn.execute("SELECT COUNT(*) FROM adozioni_res").fetchone()
        if count_res[0] == 0:
            cursor = conn.execute("SELECT * FROM adozioni WHERE prof_id IN (SELECT value FROM json_each(?))", (json.dumps(data),))
        else:
            cursor = conn.execute("SELECT * FROM adozioni_res WHERE prof_id IN (SELECT value FROM json_each(?))", (json.dumps(data),))
        names = [x[0] for x in cursor.description]
        results = cursor.fetchall()
        dfres = pd.DataFrame(results, columns=names)
        dfres.to_sql('adozioni_res', conn, if_exists='replace', index=False)
        message = f"prof_id (insegnamenti): {data} selezionati"
        myalma.update_msg(conn, message)
    if request.headers.get('HX-Request'):
        return templates.TemplateResponse('partial_insegnamenti.html', {"request": request, 
                                                                        "user": user, "items": results, "message_tpl": message_tpl})
    
@app.get("/docenti")
async def get_docenti(request: Request, page: int=1,  user: auth.User = Depends(auth.get_current_user_from_token), 
                      db: str = Depends(auth.get_tenant_hash)):
    async with aiosqlite.connect(p/f'{db}.db') as conn:
        conn.row_factory = aiosqlite.Row
        q = await myalma.aget_q(conn)
        count_res = await conn.execute("SELECT COUNT(*) FROM adozioni_res")
        count_res = await count_res.fetchone()
        if count_res and count_res[0] == 0:
            cursor = await conn.execute("""
                    SELECT DISTINCT prof_id, materia_ssd_cod, insegnamento_prof, uni_cod, sede,facolta FROM adozioni;
                """)
        else:
            cursor = await conn.execute("""
                    SELECT DISTINCT prof_id, materia_ssd_cod, insegnamento_prof, uni_cod, sede, facolta FROM adozioni_res;
                """)
        results = await cursor.fetchall()
        message = "Visualizzati i docenti"
        await myalma.aupdate_msg(conn, message)
    paginator = Paginator(results, 100)
    page = paginator.get_page(page) # type: ignore
    return templates.TemplateResponse('docenti.html',
                                      {"request": request, "paginator": paginator, "page": page, "user": user})
    
@app.post("/docenti")
async def post_docenti(request: Request, user: auth.User = Depends(auth.get_current_user_from_token), 
                       db: str = Depends(auth.get_tenant_hash)):
    form = await request.form()
    data = jsonable_encoder(form)
    data = [x for x in data]
    message_tpl = f"I docenti selezionati che hanno prof_id {' '.join(data)}."
    with sqlite3.connect(p/f'{db}.db') as conn:
        conn.row_factory = sqlite3.Row
        q = myalma.get_q(conn)
        count_res = conn.execute("SELECT COUNT(*) FROM adozioni_res").fetchone()
        if count_res[0] == 0:
            cursor = conn.execute("SELECT * FROM adozioni WHERE prof_id IN (SELECT value FROM json_each(?))", (json.dumps(data),))
        else:
            cursor = conn.execute("SELECT * FROM adozioni_res WHERE prof_id IN (SELECT value FROM json_each(?))", (json.dumps(data),))
        names = [x[0] for x in cursor.description]
        results = cursor.fetchall()
        dfres = pd.DataFrame(results, columns=names)
        dfres.to_sql('adozioni_res', conn, if_exists='replace', index=False)
        message = f"prof_id (docenti): {data} selezionati"
        myalma.update_msg(conn, message)
    if request.headers.get('HX-Request'):
        return templates.TemplateResponse('partial_docenti.html', {"request": request, "items": results, "user":user, "message_tpl": message_tpl})

############################### CERCA E CARICA DOCENTI COMPLETI DA ALMALIBRI ##############################


@app.get("/router_cerca_docenti", response_class=HTMLResponse)
async def router_getform(request: Request, user: auth.User = Depends(auth.get_current_user_from_token)):
    if user:
        return templates.TemplateResponse("router_form.html", {"request": request, "user": user})

@app.post("/router_cerca_docenti", response_class=HTMLResponse)
async def form_docenti(request: Request, db: str = Depends(auth.get_tenant_hash),
                    user: auth.User = Depends(auth.get_current_user_from_token),
                    inlineRadio: Literal['fail', 'replace', 'append'] = Form(...),
                    inlineCheck: str = Form(None),
                    uni_cod: str = Form(None),
                    materia_ssd_cod: List[str] = Form(None),
                    insegnamento_prof: str = Form(None),
                    materia_nome: str = Form(None),
                    prof_id: str = Form(None),
                    insegnamento_id: str = Form(None)):
    params = [('uni_cod', uni_cod), ('materia_ssd_cod', materia_ssd_cod), ('insegnamento_prof', insegnamento_prof),
             ('materia_nome', materia_nome), ('prof_id', prof_id), ('insegnamento_id', insegnamento_id)]
    filtered_params = [(key,value) for key, value in params if value != '' and value != ['']]
    form = await request.form()
    data = jsonable_encoder(form)
    query = myalma.set_query_where(filtered_params, 'tuttidocenti')
    with sqlite3.connect(p/f'{db}.db') as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(query)
        names = [x[0] for x in cur.description]
        res = cur.fetchall()
        names_2 = ['uni_cod', 'facolta', 'materia_ssd_cod', 'materia_nome', 'insegnamento_prof',
            'insegnamento_prof_www', 'prof_id', 'insegnamento_id', 'email', 'indirizzo', 'citta', 'telefono', 
            'note', 'isbn', 'titolo','data']
        df = pd.DataFrame(res, columns=names)
        df['prof_id'] = df['prof_id'].fillna(0).astype(int)
        df['insegnamento_id'] = df['insegnamento_id'].fillna(0).astype(int)
        df = df.assign(facolta='', email='', indirizzo='', citta='', telefono='', note='', isbn='', titolo='', data='')
        df = df[names_2]
        if myalma.get_count(conn, 'adozioni_res') > 0:
            cur2 = conn.execute("SELECT * FROM adozioni_res")
        else:
            cur2 = conn.execute("SELECT * FROM adozioni")
        names_3 = [x[0] for x in cur2.description]
        res2 = cur2.fetchall()
        df2 = pd.DataFrame(res2, columns=names_3)
        df2 = df2[['uni_cod', 'facolta', 'materia_ssd_cod', 'materia_nome', 'insegnamento_prof',
        'insegnamento_prof_www', 'prof_id', 'insegnamento_id']]
        df2['prof_id'] = df2['prof_id'].fillna(0).astype(int)
        df2['insegnamento_id'] = df2['prof_id'].fillna(0).astype(int)
        df2 = df2.assign(materia_nome='', email='', indirizzo='', citta='', telefono='', note='', isbn='', titolo='', data='')
        if inlineCheck == '1':
            df = pd.concat([df, df2])
            df = df.drop_duplicates(subset=['prof_id', 'insegnamento_id'])
            df.to_sql('tuttidocenti_res', conn, if_exists=inlineRadio, index=False)
            message = f"Selezionati i docenti con {filtered_params} e aggiunti i docenti con adozioni"
        elif inlineCheck == '0':
            df = df2.drop_duplicates(subset=['prof_id', 'insegnamento_id'])
            df.to_sql('tuttidocenti_res', conn, if_exists=inlineRadio, index=False)
            message = f"Selezionati solo i docenti con adozioni"
        else:
            df.to_sql('tuttidocenti_res', conn, if_exists=inlineRadio, index=False)
            message = f"Selezionati i docenti con {filtered_params}"
        myalma.update_msg(conn, message)
        df.to_csv(os.path.join(p, f'{db}tuttidocenti_res.csv'), sep=',', index=False)
        docenti = df.to_dict(orient='records')
        count_df = len(docenti)
        if count_df == 0:
            note = "Nessun docente trovato con i parametri selezionati"
        else:
            note=''
    if request.headers.get('HX-Request'):
        return templates.TemplateResponse('partial_router_cerca_docenti.html', 
                                      {"request": request, "user":user, "docenti": docenti, "note": note})
    
@app.get("/csv_docenti_router", response_class=PlainTextResponse)
def get_csv_docenti_router(user: auth.User = Depends(auth.get_current_user_from_token), 
                           db: str = Depends(auth.get_tenant_hash)):
    if os.path.isfile(f'{db}tuttidocenti_res.csv'):
        return FileResponse(
            p/f'{db}tuttidocenti_res.csv',
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment"})

###################################### FINE CERCA TUTTIDOCENTI
    
@app.get("/libri")
async def get_libri(request: Request, page: int=1, user: auth.User = Depends(auth.get_current_user_from_token), 
                    db: str = Depends(auth.get_tenant_hash)):
    async with aiosqlite.connect(p/f'{db}.db') as conn:
        conn.row_factory = aiosqlite.Row
        q = await myalma.aget_q(conn)
        count_res = await conn.execute("SELECT COUNT(*) FROM adozioni_res")
        count_res = await count_res.fetchone()
        if count_res and count_res[0] == 0:
            cursor = await conn.execute("""
                    SELECT DISTINCT isbn, autori, curatori, titolo, editore FROM adozioni;
                """)
        else:
            cursor = await conn.execute("""
                    SELECT DISTINCT isbn, autori, curatori, titolo, editore FROM adozioni_res;
                """)
        results = await cursor.fetchall()
        await myalma.aupdate_msg(conn, f"Visualizzati i libri")
    paginator = Paginator(results, 100)
    page = paginator.get_page(page) # type: ignore
    return templates.TemplateResponse('libri.html',
                                      {"request": request, "paginator": paginator, "page": page, "user": user})

    
@app.post("/libri")
async def post_libri(request: Request, user: auth.User = Depends(auth.get_current_user_from_token),
                     db: str = Depends(auth.get_tenant_hash)):
    form = await request.form()
    data = jsonable_encoder(form)
    data = [x for x in data]
    message_tpl = f"I libri selezionati che hanno isbn {' '.join(data)}."
    with sqlite3.connect(p/f'{db}.db') as conn:
        conn.row_factory = sqlite3.Row
        q = myalma.get_q(conn)
        count_res = conn.execute("SELECT COUNT(*) FROM adozioni_res").fetchone()
        if count_res[0] == 0:
            cursor = conn.execute("SELECT * FROM adozioni WHERE isbn IN (SELECT value FROM json_each(?))", (json.dumps(data),))
        else:
            cursor = conn.execute("SELECT * FROM adozioni_res WHERE isbn IN (SELECT value FROM json_each(?))", (json.dumps(data),))
        names = [x[0] for x in cursor.description]
        results = cursor.fetchall()
        dfres = pd.DataFrame(results, columns=names)
        dfres.to_sql('adozioni_res', conn, if_exists='replace', index=False)
        message = f"isbn (libri): {data} selezionati"
        myalma.update_msg(conn, message)
    if request.headers.get('HX-Request'):
        return templates.TemplateResponse('partial_libri.html', {"request": request, "items": results, "user":user, "message_tpl": message_tpl})

##################################################### NUOVE ADOZIONI ########################################


@app.get("/nuove_adozioni", response_class=PlainTextResponse)
async def get_nuove_adozioni(request: Request, user: auth.User = Depends(auth.get_current_user_from_token), db: str = Depends(auth.get_tenant_hash)):
    return templates.TemplateResponse("nuove_adozioni_form.html", {"request": request, "user": user})

@app.post("/nuove_adozioni", response_class=PlainTextResponse)
async def post_nuove_adozioni(request: Request, user: auth.User = Depends(auth.get_current_user_from_token), 
                            db: str = Depends(auth.get_tenant_hash),
                            a_a: int = Form(...),
                            uni_cod: str = Form(None),
                            laurea_nome: str = Form(None),
                            laurea_tipo: str = Form(None),
                            laurea_classe_cod: str = Form(None),
                            insegnamento_prof: str = Form(None),
                            isbn: str = Form(None),
                            titolo: str = Form(None),
                            editore: str = Form(None)):
    params = [('a_a', a_a), ('uni_cod', uni_cod), ('laurea_nome', laurea_nome), ('laurea_tipo', laurea_tipo), 
              ('laurea_classe_cod', laurea_classe_cod),
              ('insegnamento_prof', insegnamento_prof), ('isbn', isbn), ('titolo', titolo), ('editore', editore)]
    filtered_params = [(key,value) for key, value in params if value != '' and value != ['']]
    async with aiosqlite.connect(p/f'{db}.db') as conn:
        conn.row_factory = aiosqlite.Row
        count_res = await myalma.aget_count(conn, 'adozioni_res')
        if count_res == 0:
            query = "SELECT DISTINCT a_a, uni_cod, laurea_nome, laurea_tipo, laurea_classe_cod, insegnamento_prof, isbn, titolo, editore, laurea_matricole FROM adozioni WHERE"
        else:
            query = "SELECT DISTINCT a_a, uni_cod, laurea_nome, laurea_tipo, laurea_classe_cod, insegnamento_prof, isbn, titolo, editore, laurea_matricole FROM adozioni_res WHERE"
        for i in range(len(filtered_params)): 
            if filtered_params[i][0] == 'laurea_nome':
                query += f" {filtered_params[i][0]} LIKE '%{filtered_params[i][1]}%' AND "
                continue
            if filtered_params[i][0] == 'insegnamento_prof':
                query += f" {filtered_params[i][0]} LIKE '%{filtered_params[i][1]}%' AND "
                continue
            if filtered_params[i][0] == 'titolo':
                query += f" {filtered_params[i][0]} LIKE '%{filtered_params[i][1]}%' AND "
                continue
            if filtered_params[i][0] == 'a_a':
                query += f" ({filtered_params[i][0]} = {filtered_params[i][1]} OR a_a = {filtered_params[i][1]-1}) AND "
                continue
            query += f" {filtered_params[i][0]} = '{filtered_params[i][1]}' AND "
        query = query[:-5]
        cur = await conn.execute(query)
        adozioni = await cur.fetchall()
    names = ['a_a', 'uni_cod', 'laurea_nome', 'laurea_tipo', 'laurea_classe_cod', 'insegnamento_prof', 'isbn', 
                    'titolo', 'editore', 'laurea_matricole']
    df = pd.DataFrame(adozioni, columns=names)
    df_def = df[['a_a', 'uni_cod', 'laurea_nome', 'laurea_tipo', 'laurea_classe_cod', 'insegnamento_prof', 'isbn', 'laurea_matricole']]
    #df_def = df_def.sort_values(['insegnamento_prof', 'isbn', 'a_a', 'laurea_nome']).reset_index(drop=True)
    df_2 = df_def[df_def['a_a'] == int(a_a)-1]
    df_1 = df_def[df_def['a_a'] == a_a]
    df_2 = df_2[['uni_cod', 'laurea_nome','insegnamento_prof', 'isbn','laurea_matricole']]
    df_1 = df_1[['uni_cod', 'laurea_nome','insegnamento_prof', 'isbn', 'laurea_matricole']]
    ds2 = set(map(tuple, df_2.values))
    ds1 = set(map(tuple, df_1.values))
    ds = ds1.difference(ds2)
    ds_df = pd.DataFrame(list(ds), columns=['uni_cod', 'laurea_nome', 'insegnamento_prof', 'isbn', 'laurea_matricole'])
    if ds_df.empty:
        msg_tpl = "Nessuna nuova adozione"
    else:
        msg_tpl = ""
    ds_df.to_csv(p/f'{db}nuove_adozioni.csv', sep=',', index=False)
    adozioni = ds_df.to_dict(orient='records')
    message = "Visualizzate le nuova adozioni"
    async with aiosqlite.connect(p/f'{db}.db') as conn:
        await myalma.aupdate_msg(conn, message)
    if request.headers.get('HX-Request'):
        return templates.TemplateResponse("partial_nuove_adozioni.html", {"request": request, "adozioni": adozioni, 
                                                                          "msg_tpl": msg_tpl, "user": user})
    return templates.TemplateResponse("nuove_adozioni.html", {"request": request, "user": user})
    
    
@app.get("/csv_nuove_adozioni", response_class=PlainTextResponse)
def get_csv_nuove_adozioni(user: auth.User = Depends(auth.get_current_user_from_token), db: str = Depends(auth.get_tenant_hash)):
    if os.path.isfile(p/f'{db}nuove_adozioni.csv'):
        return FileResponse(
            p/f"{db}nuove_adozioni.csv",
            media_type="text/csv",
            headers={"Content-Disposition": "attachment"}
    )

############## FINE NUOVE ADOZIONI ################

############## DASHBOARD ##########################

@app.post("/cerca_adozioni")
async def get_cerca_adozioni(request: Request, search: str = Form(...), user: auth.User = Depends(auth.get_current_user_from_token), 
                           db: str = Depends(auth.get_tenant_hash)):
    message_tpl = ""
    with sqlite3.connect(p/f'{db}.db') as conn:
        res = myalma.get_adozioni_cerca(conn, search)
        results = res.to_dict(orient='records')
    if results:
        res.to_csv(p/f'{db}cerca_adozioni.csv', sep=',', index=False)
        return templates.TemplateResponse("partial_cerca_adozioni.html", {"request": request, "results": results, "user": user})
    else:
        message_tpl = "Nessun risultato trovato"
        return templates.TemplateResponse("partial_cerca_adozioni.html", {"request": request, "message_tpl": message_tpl, "user": user})
        
@app.get("/csv_cerca_adozioni")
def get_csv_tuttidocenti(user: auth.User = Depends(auth.get_current_user_from_token), db: str = Depends(auth.get_tenant_hash)):
    if os.path.isfile(p/f'{db}cerca_adozioni.csv'):
        return FileResponse(
            p/f"{db}cerca_adozioni.csv",
            media_type="text/csv",
            headers={"Content-Disposition": "attachment"})
        
        
@app.get("/", name="dashboard")
async def get_dashboard(request: Request, db: str = Depends(auth.get_tenant_hash)):
    user = auth.get_current_user_from_cookie(request)
    if user is None:
        user['username'] = "Utente non riconosciuto"
        return templates.TemplateResponse("login.html", {"request": request, "user": user})
    async with aiosqlite.connect(p/f'{db}.db') as conn:
        conn.row_factory = aiosqlite.Row
        q = await myalma.aget_q(conn)
        count_res = await myalma.aget_count(conn, 'adozioni_res')
        if count_res == 0:
            adozioni0 = await conn.execute("""
                    SELECT DISTINCT a_a, uni_cod, laurea_nome, materia_nome, materia_ssd_cod, insegnamento_prof, isbn, 
                    titolo, editore, testo_obb, laurea_matricole FROM adozioni;
                """)
            names = [x[0] for x in adozioni0.description]
            adozioni = await adozioni0.fetchall()
            items = pd.DataFrame(adozioni, columns=names)
            items.to_csv(p/f'{db}adozioni.csv', sep=',', index=False)
            studenti0 = await conn.execute("""
                WITH cts AS (SELECT DISTINCT uni_cod, laurea_nome, isbn, laurea_matricole AS studenti FROM adozioni) 
                SELECT tbl1.isbn, tbl2.titolo, tbl2.autore, tbl2.editore, tbl1.studenti FROM 
                (SELECT n1.isbn, sum( CAST(n1.studenti as integer)) as studenti from cts n1 GROUP BY isbn) AS tbl1 
                INNER JOIN 
                (SELECT DISTINCT isbn, titolo, autori ||' '||curatori AS autore, editore from adozioni) AS tbl2 
                ON tbl1.isbn = tbl2.isbn;
            """)
            names = [x[0] for x in studenti0.description]
            studenti = await studenti0.fetchall()
            pd.DataFrame(studenti, columns=names).to_csv(p/f'{db}studenti.csv', sep=',', index=False)
            docenti0 = await conn.execute("""
                    SELECT DISTINCT prof_id, materia_ssd_cod, insegnamento_prof, insegnamento_prof_www, uni_cod, sede,facolta 
                    FROM adozioni;
                """)
            names = [x[0] for x in docenti0.description]
            docenti = await docenti0.fetchall()
            pd.DataFrame(docenti, columns=names).to_csv(p/f'{db}docenti.csv', sep=',', index=False)
        else:
            adozioni = await conn.execute("""
                    SELECT DISTINCT a_a, uni_cod, laurea_nome, materia_nome, materia_ssd_cod, insegnamento_prof, isbn, 
                    titolo, editore, testo_obb, laurea_matricole FROM adozioni_res;
                """)
            names = [x[0] for x in adozioni.description]
            adozioni = await adozioni.fetchall()
            items = pd.DataFrame(adozioni, columns=names)
            items.to_csv(p/f'{db}adozioni.csv', sep=',', index=False)
            studenti = await conn.execute("""
                WITH cts AS (SELECT DISTINCT uni_cod, laurea_nome, isbn, laurea_matricole AS studenti FROM adozioni_res) 
                SELECT tbl1.isbn, tbl2.titolo, tbl2.autore, tbl2.editore, tbl1.studenti FROM 
                (SELECT n1.isbn, sum( CAST(n1.studenti as integer)) as studenti from cts n1 GROUP BY isbn) AS tbl1 
                INNER JOIN 
                (SELECT DISTINCT isbn, titolo, autori ||' '||curatori AS autore, editore from adozioni_res) AS tbl2 
                ON tbl1.isbn = tbl2.isbn;
            """)
            names = [x[0] for x in studenti.description]
            studenti = await studenti.fetchall()
            pd.DataFrame(studenti, columns=names).to_csv(p/f'{db}studenti.csv', sep=',', index=False)
            docenti = await conn.execute("""
                    SELECT DISTINCT prof_id, materia_ssd_cod, insegnamento_prof, insegnamento_prof_www, uni_cod, sede,facolta 
                    FROM adozioni_res;
                """)
            names = [x[0] for x in docenti.description]
            docenti = await docenti.fetchall()
            pd.DataFrame(docenti).to_csv(p/f'{db}docenti.csv', sep=',', index=False)
        message = "Visualizzata la dashboard"
        await myalma.aupdate_msg(conn, message)
        data = myalma.get_table_data(items)
    return templates.TemplateResponse("dashboard.html", {"request": request, 
                                    "adozioni": adozioni, "studenti": studenti,
                                    "user": user, "docenti": docenti, "data": data})

@app.get("/csv_tuttidocenti", response_class=PlainTextResponse)
def csv_tuttidocenti(user: auth.User = Depends(auth.get_current_user_from_token), db: str = Depends(auth.get_tenant_hash)):
    if os.path.isfile(p/f'{db}tuttidocenti.csv'):
        return FileResponse(
            p/f"{db}tuttidocenti.csv",
            media_type="text/csv",
            headers={"Content-Disposition": "attachment"}
    )
    
@app.get("/csv_docenti", response_class=PlainTextResponse)
def get_csv_docenti(user: auth.User = Depends(auth.get_current_user_from_token), db: str = Depends(auth.get_tenant_hash)):
    if os.path.isfile(p/f'{db}docenti.csv'):
        return FileResponse(
            p/f"{db}docenti.csv",
            media_type="text/csv",
            headers={"Content-Disposition": "attachment"}
    )
    
    
@app.get("/csv_studenti", response_class=PlainTextResponse)
def get_csv_studenti(user: auth.User = Depends(auth.get_current_user_from_token), db: str = Depends(auth.get_tenant_hash)):
    if os.path.isfile(p/f'{db}studenti.csv'):
        return FileResponse(
            p/f"{db}studenti.csv",
            media_type="text/csv",
            headers={"Content-Disposition": "attachment"})
    
    
@app.get("/csv_adozioni" , response_class=PlainTextResponse)
def get_csv_adozioni(user: auth.User = Depends(auth.get_current_user_from_token), db: str = Depends(auth.get_tenant_hash)):
    if os.path.isfile(p/f'{db}adozioni.csv'):
        return FileResponse(
            p/f"{db}adozioni.csv",
            media_type="text/csv",
            headers={"Content-Disposition": "attachment"})
    

@app.get("/settings", response_class=PlainTextResponse)
async def get_settings(request: Request, user: auth.User = Depends(auth.get_current_user_from_token), 
                       db: str = Depends(auth.get_tenant_hash)):
    date = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    df = pd.DataFrame({'date': [date], 'message': ["Parametri cancellati"], 'q':[0]})
    with sqlite3.connect(p/f'{db}.db') as conn:
        conn.execute("DELETE FROM msg")
        conn.execute("DELETE FROM adozioni_res")
        conn.commit()
        df.to_sql('msg', conn, if_exists='replace', index=False)
    return "Parametri cancellati"

@app.get("/settings/delete", response_class=PlainTextResponse)
async def get_delete(request: Request, user: auth.User = Depends(auth.get_current_user_from_token), 
                       deleteall: str | None = None, db: str = Depends(auth.get_tenant_hash)):
    
    with sqlite3.connect(p/f'{db}.db') as conn:
        conn.execute("DELETE FROM msg")
        conn.execute("DELETE FROM adozioni_res")
        conn.execute("DELETE FROM adozioni")
        conn.commit()
        myalma.update_msg(conn, "Le adozioni sono state cancellate")
    return "Tutte le adozioni sono state cancellate."

@app.get("/settings/deleteall", response_class=FileResponse)
async def get_deleteall(request: Request, user: auth.User = Depends(auth.get_current_user_from_token), 
                       deleteall: str | None = None, db: str = Depends(auth.get_tenant_hash)):
    src = await aiosqlite.connect(p/f'{db}.db')
    dst = await aiosqlite.connect(p/f'{db}.backup')
    await src.backup(dst)
    await dst.close()
    await src.close()
    async with aiosqlite.connect(p/f'{db}.db') as conn:
        await conn.execute("DELETE FROM msg")
        await conn.execute("DELETE FROM adozioni_res")
        await conn.execute("DELETE FROM adozioni")
        await conn.execute("DELETE FROM tuttidocenti_res")
        await conn.commit()
        message = 'Tutte le adozioni sono state cancellate'
        await myalma.aupdate_msg(conn, message)
    return FileResponse(
            p/f'{db}.backup',
            media_type="application/vnd.sqlite3",
            headers={"Content-Disposition": "attachment"})


@app.get("/scarica_backup", response_class=FileResponse)
async def get_backup(user: auth.User = Depends(auth.get_current_user_from_token), db: str = Depends(auth.get_tenant_hash)):
    src = await aiosqlite.connect(p/f'{db}.db')
    dst = await aiosqlite.connect(p/f'{db}.backup')
    await src.backup(dst)
    await dst.close()
    await src.close()
    return FileResponse(
        p/f'{db}.backup',
        media_type="application/vnd.sqlite3",
        headers={"Content-Disposition": "attachment"})

############### RICERCA IN LINGUAGGIO NATURALE #############################

@app.get("/search", response_class=HTMLResponse)
async def get_search(request: Request, user: auth.User = Depends(auth.get_current_user_from_token),
                        db: str = Depends(auth.get_tenant_hash)):
    if user:
        return templates.TemplateResponse("search.html", {"request": request, "user": user})

@app.post("/search", response_class=PlainTextResponse)
async def post_search(request: Request, user: auth.User = Depends(auth.get_current_user_from_token),
                        db: str = Depends(auth.get_tenant_hash),
                        input: str = Form(...)):
    res = mylangchain.get_sql_from_ai(input, db)
    return res
    

@app.post("/search_data", response_class=HTMLResponse)
async def post_search_data(request: Request, user: auth.User = Depends(auth.get_current_user_from_token),
                        db: str = Depends(auth.get_tenant_hash),
                        query_dati: str = Form(...)):
    with sqlite3.connect(p/f'{db}.db') as conn:
        conn.row_factory = sqlite3.Row
        n_columns = 0
        df = pd.DataFrame()
        msg = ''
        try:
            cursor = conn.execute(query_dati)
            names = [x[0] for x in cursor.description]
            res = cursor.fetchall()
            df = pd.DataFrame(res, columns=names)
            results = df.to_dict(orient='records')
            if results==[]:
                msg = "Nessun dato trovato"
            n_columns = df.shape[1]
            df.to_csv(p/f'{db}search.csv', sep=',', index=False)
        except Exception as e:
            msg = "Nessun dato trovato o errore nella query"
            results = []
    return templates.TemplateResponse("partial_search.html", {
        "request": request,
        "user": user, 
        "results": results, 
        "msg": msg,
        "n_columns": n_columns,
        "names": df.columns.to_list()})

@app.get("/csv_search_data", response_class=PlainTextResponse)
def get_csv_search_data(user: auth.User = Depends(auth.get_current_user_from_token), db: str = Depends(auth.get_tenant_hash)):
    if os.path.isfile(p/f'{db}search.csv'):
        return FileResponse(
            p/f"{db}search.csv",
            media_type="text/csv",
            headers={"Content-Disposition": "attachment"})

############################# END RICERCA IN LINGUAGGIO NATURALE #############################

#========================================================================

############## PROMOZIONE ##############################################



################ PROMOZIONE CERCA DOCENTI ###############################

@app.get("/promozione_docenti", response_class=HTMLResponse)
async def get_promozione_docenti(request: Request, db: str = Depends(auth.get_tenant_hash),
                                 user: auth.User = Depends(auth.get_current_user_from_token)):
    if user:
        return templates.TemplateResponse("promozione_scelta_docenti.html", {"request": request, "user": user, "msg": ""})


@app.post("/promozione_docenti", response_class=HTMLResponse)
async def post_promozione_docenti(request: Request, db: str = Depends(auth.get_tenant_hash),
                    user: auth.User = Depends(auth.get_current_user_from_token),
                    uni_cod: str = Form(None),
                    facolta: str = Form(None),
                    materia_ssd_cod: List[str] = Form(None),
                    materia_nome: str = Form(None),
                    insegnamento_prof: str = Form(None),
                    prof_id: str = Form(None),
                    insegnamento_id: str = Form(None),
                    citta: str = Form(None),
                    isbn: str = Form(None),
                    data: str = Form(None),
                    audience_name: str = Form(...),
                    download: str = Form(None)):
    params = [('uni_cod', uni_cod), ('facolta', facolta), ('materia_ssd_cod', materia_ssd_cod), ('insegnamento_prof', insegnamento_prof),
             ('materia_nome', materia_nome), ('prof_id', prof_id), ('insegnamento_id', insegnamento_id), ('citta', citta),
             ('isbn', isbn), ('data', data)]
    filtered_params = [(key,value) for key, value in params if value != '' and value != None and value != ['']]
    query = myalma.set_query_where(filtered_params, 'docenti_router')
    with sqlite3.connect(os.path.join(p, f'{db}.db')) as conn: # type: ignore
        conn.row_factory = sqlite3.Row
        cur = conn.execute(query)
        names = [x[0] for x in cur.description]
        res = cur.fetchall()
    df = pd.DataFrame(res, columns=names)
    if audience_name:
        df['nome'] = audience_name
        df['data'] = pd.Timestamp.now().strftime("%Y-%m-%d")
        df[['uni_cod', 'materia_ssd_cod', 'insegnamento_prof', 'prof_id',\
                'insegnamento_id', 'email', 'nome', 'data']].to_sql('mailing', conn, if_exists='append', index=False)
        msg = 'Creata audience'
    if download:
        df.to_csv(os.path.join(p, f'{db}_docenti_router.csv'), sep=',', index=False) # type: ignore
    msg = ''
    docenti = []
    if df.empty:
        msg = "Nessun docente trovato con i parametri selezionati"
    else:
        docenti = df.to_dict(orient='records')
    if request.headers.get('HX-Request'):
        return templates.TemplateResponse('partial_promozione_docenti.html', 
                                      {"request": request, "user":user, "items": docenti, "msg": msg})
    
@app.get("/csv_promozione_docenti", response_class=PlainTextResponse)
def get_csv_promozione_docenti(user: auth.User = Depends(auth.get_current_user_from_token), 
                             db: str = Depends(auth.get_tenant_hash)):
    if os.path.isfile(p/f'{db}_docenti_router.csv'):
        return FileResponse(
            p/f"{db}_docenti_router.csv",
            media_type="text/csv",
            headers={"Content-Disposition": "attachment"})   
    
######################### ROUTER DASHBOARD ##################

@app.get("/copiesaggio", response_class=HTMLResponse)
async def read_dashboard(request: Request, page: int=1, db: str = Depends(auth.get_tenant_hash)):
    user = auth.get_current_user_from_cookie(request)
    if user is None:
        user['username'] = "Utente non riconosciuto"
        return templates.TemplateResponse("login.html", {"request": request, "user": user})
    query = """SELECT uni_cod,
    facolta,
    materia_ssd_cod,
    materia_nome,
    insegnamento_prof,
    insegnamento_prof_www,
    prof_id,
    insegnamento_id,
    email,
    indirizzo,
    citta,
    telefono,
    note,
    coalesce(isbn,'Nessun saggio') isbn, titolo, data
    FROM docenti_router GROUP BY insegnamento_prof, isbn
    ORDER BY insegnamento_prof"""
    query_1 = """SELECT uni_cod,
    facolta,
    materia_ssd_cod,
    materia_nome,
    insegnamento_prof,
    insegnamento_prof_www,
    prof_id,
    insegnamento_id,
    email,
    indirizzo,
    citta,
    telefono,
    note,
    coalesce(isbn,'Nessun saggio') isbn, titolo, data
     FROM tuttidocenti_res GROUP BY insegnamento_prof, isbn ORDER BY insegnamento_prof"""
    with sqlite3.connect(p/f'{db}.db') as conn:
        conn.row_factory = sqlite3.Row
        cx = conn.execute("select (select count(*) from docenti_router) > 0;").fetchone()[0]
        if cx == 1:
            cursor = conn.execute(query)
        else:
            cursor = conn.execute(query_1)
        names = [x[0] for x in cursor.description]
        results = cursor.fetchall()
        dfres = pd.DataFrame(results, columns=names)
    items = myalma.get_table_data(dfres)
    dfres.to_csv(p/f'{db}docenti_router_corretti.csv', sep=',', index=False)
    paginator = Paginator(results, 20)
    page = paginator.get_page(page) # type: ignore
    return templates.TemplateResponse("router_dashboard.html", {"request": request, 
                                    "paginator": paginator,
                                    "page": page, 
                                    "user": user,
                                    "data": items})

@app.post("/copiesaggio", response_class=HTMLResponse)
async def post_dashboard(request: Request, db: str = Depends(auth.get_tenant_hash),
                            user: auth.User = Depends(auth.get_current_user_from_token)):
    form = await request.form()
    data = jsonable_encoder(form)
    data = [x for x in data]
    with sqlite3.connect(p/f'{db}.db') as conn:
        conn.row_factory = sqlite3.Row
        cx = conn.execute("select (select count(*) from docenti_router) > 0;").fetchone()[0]
        if cx == 1:
            cursor = conn.execute("SELECT * FROM docenti_router WHERE insegnamento_prof IN (SELECT value FROM json_each(?))",
                                  (json.dumps(data),))
        else:
            cursor = conn.execute("SELECT * FROM tuttidocenti_res WHERE insegnamento_prof IN (SELECT value FROM json_each(?))",
                                  (json.dumps(data),))
        names = [x[0] for x in cursor.description]
        results = cursor.fetchall()
        dfres = pd.DataFrame(results, columns=names)
        dfres.to_sql('docenti_router', conn, if_exists='append', index=False)
        dfres.to_csv(p/f'{db}docenti_router_selezionati.csv', sep=',', index=False)
        message = f"prof_id (docenti): {data} selezionati"
        myalma.update_msg(conn, message)
    return templates.TemplateResponse('partial_router_dashboard.html', 
                                          {"request": request, "user": user, "items": results})
    
@app.get("/copiesaggio/prof/adozioni/{insegnamento_prof}", response_class=HTMLResponse)
def get_prof_adozioni(request: Request, insegnamento_prof: str, a_a: str = Depends(current_aa_year), db: str = Depends(auth.get_tenant_hash),
                 user: auth.User = Depends(auth.get_current_user_from_token)):
    msg = ""
    # DA CONTROLLARE
    adozioni = myalma.get_alma_api(**dict([('insegnamento_prof', insegnamento_prof), ('a_a', a_a)]))
    res = [x for x in adozioni if len(x) > 0] # type: ignore
    if len(res) == 0:
        msg = f"Non ci sono adozioni per il docente {insegnamento_prof}"
        adozioni = []
    else:
        adozioni = res[0]
    if request.headers.get('HX-Request'):
        return templates.TemplateResponse('partial_copiesaggio_prof_adozioni.html', 
                                      {"request": request, "adozioni": adozioni, "nome": insegnamento_prof, "msg": msg})
                              
@app.get("/copiesaggio/isbn/adozioni/{isbn}", response_class=HTMLResponse)
def get_isbn_adozioni(request: Request, isbn: str, a_a: str = Depends(current_aa_year), db: str = Depends(auth.get_tenant_hash),
                 user: auth.User = Depends(auth.get_current_user_from_token)):
    msg = ""
    adozioni = []
    adozioni = myalma.get_alma_api(**dict([('isbn', isbn), ('a_a', a_a)]))
    res = [x for x in adozioni if len(x)>0] # type: ignore
    if len(res) == 0:
        msg = f"Non ci sono adozioni per l'isbn {isbn}"
        adozioni = []
    else:
        adozioni = res[0]
    if request.headers.get('HX-Request'):
        return templates.TemplateResponse('partial_isbn_adozioni.html', 
                                      {"request": request, "adozioni": adozioni, "isbn":isbn, "msg": msg})
        
@app.get("/csv_docenti_router/corretti")
def get_csv_docenti_corretti(user: auth.User = Depends(auth.get_current_user_from_token), 
                             db: str = Depends(auth.get_tenant_hash)):
    if os.path.isfile(p/f'{db}docenti_router_corretti.csv'):
        return FileResponse(
            p/f"{db}docenti_router_corretti.csv",
            media_type="text/csv",
            headers={"Content-Disposition": "attachment"})
        
        
@app.get("/csv_docenti_router/selezionati")
def get_csv_docenti_selezionati(user: auth.User = Depends(auth.get_current_user_from_token), 
                             db: str = Depends(auth.get_tenant_hash)):
    if os.path.isfile(p/f'{db}docenti_router_selezionati.csv'):
        return FileResponse(
            p/f"{db}docenti_router_selezionati.csv",
            media_type="text/csv",
            headers={"Content-Disposition": "attachment"})



######## ROUTER UPLOAD FILE ###############################


@app.get("/router_uploadfile", response_class=HTMLResponse)
async def router_file(request: Request, db: str = Depends(auth.get_tenant_hash),
                       user: auth.User = Depends(auth.get_current_user_from_token)):
    return templates.TemplateResponse('router_uploadfile.html', {"request": request, "user": user})
    
@app.post("/router_uploadfile", response_class=HTMLResponse)
async def upload_router_file(request: Request, 
                        file: Annotated[UploadFile, File(description="A file read as UploadFile")], 
                        user: auth.User = Depends(auth.get_current_user_from_token), db: str = Depends(auth.get_tenant_hash),
                        inlineRadio: Literal['update', 'replace', 'append'] = Form(...), sep: str = Form(None) ):
    msg = ''
    contents = await file.read()
    buffer = BytesIO(contents)
    df = pd.read_csv(buffer, sep=sep)
    names = ['uni_cod', 'facolta', 'materia_ssd_cod', 'materia_nome', 'insegnamento_prof',
             'insegnamento_prof_www', 'prof_id', 'insegnamento_id', 'email', 'indirizzo', 'citta', 'telefono', 
             'note', 'isbn', 'titolo', 'data']
    try:
        if (set(df.columns) == set(names)):
            df = df[names]
    except:
        msg = "Il file non ha le colonne corrette. Controllare il file e aggiungere o eliminare \
        le colonne che non corrispondono alle indicazioni fornite."
        return templates.TemplateResponse('partial_router_uploadfile.html', {"request": request, "user": user, 'msg': msg})
    df['isbn'] = df['isbn'].replace("", 0)
    df['isbn'] = df['isbn'].replace(r"[!-\/:-[-`{-~]", '', regex=True)
    df['isbn'] = df['isbn'].fillna(0).astype(int)
    df['insegnamento_prof'] = df['insegnamento_prof'].astype(str).apply(lambda x: myalma.clear_prof_name(x))
    buffer.close()
    await file.close()
    df_prof_id = myalma.get_prof_id_router(df, db)
    with sqlite3.connect(p/f'{db}.db') as conn:
        conn.row_factory = sqlite3.Row
        if inlineRadio == 'append':
            df2 = pd.read_sql("SELECT * FROM tuttidocenti_res", conn)
            df3 = pd.concat([df_prof_id, df2])
            df3['isbn'] = df3['isbn'].replace("", 0)
            df3['isbn'] = df3['isbn'].fillna(0)
            df3['isbn'] = df3['isbn'].astype(int)
            df3.fillna('', inplace=True)
            df3.to_sql('docenti_router', conn, if_exists='append', index=False)
            results = df3.to_dict(orient='records')
        elif inlineRadio == 'replace':
            df_prof_id['isbn'] = df_prof_id['isbn'].astype(int)
            df_prof_id.fillna('', inplace=True)
            df_prof_id.to_sql('docenti_router', conn, if_exists='replace', index=False)
            results = df_prof_id.to_dict(orient='records')
        else:
            #df = df.dropna(subset=['uni_cod', 'prof_id']) # Se questi campi sono vuoti non si può fare l'update
            df4 = pd.read_sql("SELECT * FROM docenti_router", conn)
            try:
                df5 = pd.concat([df_prof_id, df4]).sort_values(by=['uni_cod', 'prof_id', 'insegnamento_prof'], ascending=[True, True, False], na_position="first")
                df5 = df5.drop_duplicates(subset=['uni_cod','prof_id'], keep='last')
                results = df5.to_dict(orient='records')
            except:
                results = []
                msg = "Errore nell'aggiornamento"
        myalma.update_msg(conn, f"Caricato file con email, indirizzi, saggi.")
    if request.headers.get('HX-Request'):
        return templates.TemplateResponse('partial_router_uploadfile.html',
                                      {"request": request, "user": user, "items": results, "msg": msg})
    
    
######### DOCUMENTAZIONE ===================
    
@app.get("/documentazione", response_class=HTMLResponse)
def get_documentazione(request: Request, user: auth.User = Depends(auth.get_current_user_from_token)):
    return templates.TemplateResponse('documentazione.html', {"request": request, "user": user})
    
    
    
############### ADMIN ##################

@app.get("/admin", response_class=HTMLResponse)
def login_get_admin(request: Request, user: auth.User = Depends(auth.get_current_user_from_token)):
    return templates.TemplateResponse("/admin_login.html", {"request": request}) 


@app.post('/admin/login', response_class=HTMLResponse)
async def post_user_admin(request: Request, db: str = Depends(auth.get_tenant_hash), 
                          user: auth.User = Depends(auth.get_current_user_from_token)):
    if user['is_admin'] == 1: # type: ignore
        with sqlite3.connect(p/'shared.db') as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("SELECT rowid, username, hashed_password, is_active, tenant_id, is_admin FROM users")
            res = cur.fetchall()
        return templates.TemplateResponse("admin_login_list.html", {"request": request, "items":res, "user": user})
    else:
        return RedirectResponse("/login", status.HTTP_302_FOUND)
        

@app.post('/admin/update_user',  response_class=HTMLResponse)
async def admin_update_user(request: Request, db: str = Depends(auth.get_tenant_hash),
                    user: auth.User = Depends(auth.get_current_user_from_token),
                    rowid: int = Form(None),
                    username: str = Form(...),
                    password: str = Form(...),
                    tenant_id: str = Form(...),
                    is_active: int = Form(None),
                    is_admin: int = Form(None)):
    if rowid:
        hashed_password = auth.get_password_hash(password)
        params = [('rowid', rowid), ('username', username), ('hashed_password', hashed_password), 
                  ('is_active', is_active), ('tenant_id', tenant_id), ('is_admin', is_admin)]
        filtered_params = [(key,value) for key, value in params if value != '' and value != None and value != ['']]
        query = myalma.set_query_update(filtered_params, 'users')
        try:
            with sqlite3.connect(p/'shared.db') as conn:
                conn.row_factory = sqlite3.Row
                conn.execute(query)
                cur = conn.execute("SELECT rowid, username, hashed_password, is_active, tenant_id, is_admin FROM users")
                res = cur.fetchall()
                e = "Utente aggiornato"
        except Exception as e:
            print(e)
        return templates.TemplateResponse("partial_admin_login_list.html", {"request": request, "items":res, "user": user, "message_tpl": e})
    else:
        try:
            c_user = myadmin.CreateUser(username, password, is_active, tenant_id, is_admin)
            c_user.create_user_db()
            c_user.init_tenant_db()
            e = "Utente creato"
        except Exception as e:
            print(e)
    return templates.TemplateResponse("partial_admin_login_list.html", {"request": request, "items":res, "user": user, "message_tpl": e})


############# DATATABLES #################################

@app.get("/gestione_docenti", response_class=HTMLResponse)
async def gestione_docenti(request: Request, 
                    db: str = Depends(auth.get_tenant_hash)):
    user = auth.get_current_user_from_cookie(request)
    if user is None:
        user['username'] = "Utente non riconosciuto"
        return templates.TemplateResponse("login.html", {"request": request, "user": user})
    #return FileResponse("app/templates/templates_datatables/index.html")
    return templates.TemplateResponse("templates_datatables/index.html", {"request": request, "user": user})

@app.get("/gestione_docenti/data")
async def get_gestione_docenti_data(request: Request, user: auth.User = Depends(auth.get_current_user_from_token), 
                    db: str = Depends(auth.get_tenant_hash)):
    with sqlite3.connect(p/f'{db}.db') as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("INSERT INTO docenti_router SELECT * FROM tuttidocenti_res")
        cur = conn.execute("SELECT rowid, * FROM docenti_router")
        res = cur.fetchall()
    return jsonable_encoder({"data": [dict(x) for x in res]})

@app.put("/gestione_docenti/{rowid}")
async def put_gestione_docenti(request: Request, rowid: int, item: auth.CopiaSaggio, user: auth.User = Depends(auth.get_current_user_from_token), 
                    db: str = Depends(auth.get_tenant_hash)):
    with sqlite3.connect(p/f'{db}.db') as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("UPDATE docenti_router SET uni_cod = ?, facolta = ?, materia_ssd_cod = ?, materia_nome = ?, \
                     insegnamento_prof = ?, insegnamento_prof_www = ?, prof_id = ?, insegnamento_id = ?, email = ?, \
                     indirizzo = ?, citta = ?, telefono = ?, note = ?, isbn = ?, titolo = ?, data = ? WHERE rowid = ?", 
                     (item.uni_cod, item.facolta, item.materia_ssd_cod, item.materia_nome, item.insegnamento_prof,
                      item.insegnamento_prof_www, item.prof_id, item.insegnamento_id, item.email, item.indirizzo, 
                      item.citta, item.telefono, item.note, item.isbn, item.titolo, item.data, rowid))
    #return RedirectResponse(url="/gestione_docenti", status_code=status.HTTP_303_SEE_OTHER)
    return {"message": "Record aggiornato"}

@app.delete("/gestione_docenti/{rowid}")
async def delete_gestione_docenti(request: Request, rowid: int, user: auth.User = Depends(auth.get_current_user_from_token), 
                    db: str = Depends(auth.get_tenant_hash)):
    with sqlite3.connect(p/f'{db}.db') as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("DELETE FROM docenti_router WHERE rowid = ?", (rowid,))
    return {"message": "Record eliminato"}

@app.post("/gestione_docenti/row")
async def post_gestione_docenti(request: Request, user: auth.User = Depends(auth.get_current_user_from_token),
                    db: str = Depends(auth.get_tenant_hash),
                    uni_cod: str = Form(None),
                    facolta: str = Form(None),
                    materia_ssd_cod: str = Form(None),
                    materia_nome: str = Form(None),
                    insegnamento_prof: str = Form(...),
                    insegnamento_prof_www: str = Form(None),
                    prof_id: int = Form(None),
                    insegnamento_id: int = Form(None),
                    email: str = Form(None),
                    indirizzo: str = Form(None),
                    citta: str = Form(None),
                    telefono: str = Form(None),
                    note: str = Form(None),
                    isbn: str = Form(None),
                    titolo: str = Form(None),
                    data: str = Form(None)):
    with sqlite3.connect(p/f'{db}.db') as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("INSERT INTO docenti_router (uni_cod, facolta, materia_ssd_cod, materia_nome, insegnamento_prof, \
                     insegnamento_prof_www, prof_id, insegnamento_id, email, indirizzo, citta, telefono, note, isbn, titolo, data) \
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", 
                     (uni_cod, facolta, materia_ssd_cod, materia_nome, insegnamento_prof,
                      insegnamento_prof_www, prof_id, insegnamento_id, email, indirizzo, 
                      citta, telefono, note, isbn, titolo, data))
    return RedirectResponse("/gestione_docenti", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/csv_gestione_docenti", response_class=PlainTextResponse)
def get_csv_gestione_docenti(user: auth.User = Depends(auth.get_current_user_from_token), 
                             db: str = Depends(auth.get_tenant_hash)):
    with sqlite3.connect(p/f'{db}.db') as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM docenti_router")
        names = [x[0] for x in cur.description]
        res = cur.fetchall()
        df = pd.DataFrame(res, columns=names)
        df.to_csv(p/f'{db}_gestione_docenti.csv', sep=',', index=False)
    if os.path.isfile(p/f'{db}_gestione_docenti.csv'):
        return FileResponse(
            p/f"{db}_gestione_docenti.csv",
            media_type="text/csv",
            headers={"Content-Disposition": "attachment"})
                                
                                