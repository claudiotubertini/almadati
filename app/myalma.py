import requests
import json
import csv, re
import psycopg
from datetime import datetime
import pandas as pd
import numpy as np
import sqlite3, aiosqlite
from typing import Dict, List, Optional, Union, Text, Tuple, Literal
from app.threading_io import Alma_api
from pathlib import Path

p = Path(__file__).parent.resolve()
API_UNI = 'https://almalibri.it/api/lista_uni/'
API_ADOZIONI = 'https://almalibri.it/api/adozioni/?'
p = p / "dbfiles"

def normalize_columns(df, table):
    columns = df.columns.tolist()
    match table:
        case 'adozioni':
            required_columns = ["uni_cod", "a_a", "laurea_nome", "laurea_tipo",
                                "laurea_classe_cod", "sede", "facolta", "curr_nome", 
                                "materia_ssd_cod", "materia_cfu", "curr_materia_anno", 
                                "curr_materia_periodo", "materia_nome", "insegnamento_prof",
                                "insegnamento_prof_www", "isbn", "autori", "curatori",
                                "titolo", "editore", "testo_obb", "testo_uso", "testo_freq", 
                                "laurea_iscritti", "laurea_matricole", "prof_id", "insegnamento_id"]
        case 'docenti_router':
            required_columns = ["uni_cod", "facolta", "materia_ssd_cod", "materia_nome",
                                "insegnamento_prof", "insegnamento_prof_www", "prof_id", 
                                "insegnamento_id", "email", "indirizzo", "citta", "telefono", 
                                "note", "isbn", "titolo", "data"]
        case 'tuttidocenti':
            required_columns = ["prof_id", "uni_cod", "insegnamento_prof", "insegnamento_id",
                                "insegnamento_prof_www", "materia_ssd_cod", "materia_nome"]
        case 'universita':
            required_columns = ["uni_cod", "uni_nome", "max"]   
        case 'adozioni_res':
            required_columns = ["uni_cod", "a_a", "facolta", "laurea_nome", "laurea_tipo",
                                "sede", "laurea_classe_cod", "curr_nome", "materia_nome",
                                "materia_ssd_cod", "materia_cfu", "curr_materia_anno", 
                                "curr_materia_periodo",
                                 "insegnamento_prof", "insegnamento_prof_www",
                                "isbn", "autori", "curatori", "titolo", "editore", "testo_obb",
                                "testo_uso", "testo_freq", "laurea_iscritti", "laurea_matricole",
                                "prof_id", "insegnamento_id"]
        case 'tuttidocenti_res':
            required_columns = ["uni_cod", "facolta", "materia_ssd_cod", "materia_nome",
                                "insegnamento_prof", "insegnamento_prof_www", "prof_id", 
                                "insegnamento_id", "email", "indirizzo", "citta", "telefono",
                                "note", "isbn", "titolo", "data"]
        case _:
            required_columns = []
    # Check if the required columns are in the DataFrame
    #if not all(col in columns for col in required_columns):
    diff = set(required_columns) - set(columns)
    df = df.assign(**{col: np.nan for col in diff})
    return df[required_columns]

def set_query_update(filtered_params: List[Tuple[str, str]], table: str) -> str:
    if len(filtered_params) == 0:
        return ""
    else:
        query = f"UPDATE {table} SET "
        conditions = []
        for param, value in filtered_params:
            if param == 'rowid':
                where = f" WHERE rowid = {value}"
                continue
            set_cond = f"{param} = {value}"
            conditions.append(set_cond)
        query += ", ".join(conditions)
        query = query + where +';'
    return query


def set_query_where(filtered_params: List[Tuple[str, str]], table: str) -> str:
    if len(filtered_params) == 0:
        query = f"SELECT * FROM {table}"
        return query
    else:
        query = f"SELECT * FROM {table} WHERE "
        conditions = []
        for param, value in filtered_params:
            if param == 'materia_ssd_cod':
                #pams = value.split(',')
                if len(value) > 1:
                    or_conditions = " OR ".join([f"{param} = '{pam.strip()}'" for pam in value])
                    conditions.append(f"({or_conditions})")
                else:
                    conditions.append(f"{param} = '{value[0]}'")
            elif param in ['facolta', 'materia_nome', 'insegnamento_prof']:
                conditions.append(f"{param} LIKE '%{value}%'")
            elif param == 'isbn':
                pams = value.split(',')
                if len(pams) > 1:
                    or_conditions = " OR ".join([f"{param} = '{pam.strip()}'" for pam in pams])
                    conditions.append(f"({or_conditions})")
                else:
                    conditions.append(f"{param} = '{value}'")
            else:
                conditions.append(f"{param} = '{value}'")
        query += " AND ".join(conditions)
    return query

def get_prof_id_router(df, db):
    with sqlite3.connect(p/f'{db}.db') as conn:
        df2 = pd.read_sql('SELECT * FROM tuttidocenti', conn)
    df['normalized_names'] = df['insegnamento_prof'].apply(lambda x : sorted(x.split())).tolist()
    df2['normalized_names'] = df2['insegnamento_prof'].apply(lambda x : sorted(x.split())).tolist()
    df['normalized_names'] = df['normalized_names'].apply(lambda x : ' '.join(x))
    df2['normalized_names'] = df2['normalized_names'].apply(lambda x : ' '.join(x))
    df_merged = df.merge(df2, on='normalized_names', how='left')
    df_merged.rename(columns={'uni_cod_x': 'uni_cod', 'materia_ssd_cod_x': 'materia_ssd_cod', 'materia_nome_x': 'materia_nome',
                              'insegnamento_prof_x': 'insegnamento_prof', 'insegnamento_prof_www_x': 'insegnamento_prof_www', 
                              'prof_id_y': 'prof_id', 
                              'insegnamento_id_y': 'insegnamento_id'}, inplace=True)
    column_names = ['uni_cod', 'facolta', 'materia_ssd_cod', 'materia_nome', 'insegnamento_prof',
             'insegnamento_prof_www', 'prof_id', 'insegnamento_id', 'email', 'indirizzo', 'citta', 'telefono', 
             'note', 'isbn', 'titolo', 'data']
    df_merged = df_merged[column_names]
    return df_merged

def get_prof_id_file(df, db):
    with sqlite3.connect(p/f'{db}.db') as conn:
        df2 = pd.read_sql('SELECT * FROM tuttidocenti', conn)
    df['normalized_names'] = df['insegnamento_prof'].apply(lambda x : sorted(x.split())).tolist()
    df2['normalized_names'] = df2['insegnamento_prof'].apply(lambda x : sorted(x.split())).tolist()
    df['normalized_names'] = df['normalized_names'].apply(lambda x : ' '.join(x))
    df2['normalized_names'] = df2['normalized_names'].apply(lambda x : ' '.join(x))
    df_merged = df.merge(df2, on='normalized_names', how='left')
    df_merged.rename(columns={'uni_cod_x': 'uni_cod', 'materia_ssd_cod_x': 'materia_ssd_cod', 'materia_nome_x': 'materia_nome',
                              'insegnamento_prof_x': 'insegnamento_prof', 'insegnamento_prof_www_x': 'insegnamento_prof_www', 
                              'prof_id_y': 'prof_id', 
                              'insegnamento_id_y': 'insegnamento_id'}, inplace=True)
    column_names = ['uni_cod', 'a_a', 'laurea_nome', 'laurea_tipo', 'laurea_classe_cod', 'sede',
             'facolta', 'curr_nome', 'materia_ssd_cod', 'materia_cfu', 'curr_materia_anno',
             'curr_materia_periodo', 'materia_nome', 'insegnamento_prof', 'insegnamento_prof_www', 'isbn', 'autori',
             'curatori', 'titolo', 'editore', 'testo_obb', 'testo_uso', 'testo_freq', 'laurea_iscritti',
             'laurea_matricole', 'prof_id', 'insegnamento_id' ]
    df_merged = df_merged[column_names]
    return df_merged

def get_table_data(dfres):
    dfres['isbn'] = dfres['isbn'].astype(str)
    df = dfres[['uni_cod', 'isbn', 'materia_ssd_cod', 'insegnamento_prof']].describe()
    df = df.drop(['top','freq'])
    new_index = ['count', 'unique', 'val']
    df.reindex(new_index)
    df2 = df.copy()
    df2.loc['val', 'materia_ssd_cod'] = dfres['materia_ssd_cod'].unique().tolist()
    df2.loc['val', 'uni_cod'] = dfres['uni_cod'].unique().tolist()
    df2.fillna('-', inplace=True)
    return df2.to_dict(orient='records')


def get_adozioni_cerca(conn, skey):
    q = get_count(conn, 'adozioni_res')
    if q > 0:
        df = pd.read_sql('SELECT * FROM adozioni_res', conn)
    else:
        df = pd.read_sql('SELECT * FROM adozioni', conn)
    def search_string(s, skey):
        return skey.lower() in str(s).lower()
    mask = df.apply(lambda x: x.map(lambda s: search_string(s, skey)))
    filtered_df = df.loc[mask.any(axis=1)]
    return filtered_df


def get_last_query(conn, skey):
    df = pd.read_sql('SELECT * FROM last_query', conn) 
    def search_string(s, skey):
        return skey in str(s).lower()
    mask = df.apply(lambda x: x.map(lambda s: search_string(s, skey)))
    filtered_df = df.loc[mask.any(axis=1)]
    return filtered_df.to_dict(orient='records')

def create_last_query(conn, cursor, data):
    #results = cursor.fetchall()
    names = [x[0] for x in cursor.description]
    df = pd.DataFrame(data, columns=names)
    df.to_sql('last_query', conn, if_exists='replace', index=False)
    

def ISBNgenerator(mystr):
    """ return a 13 digit isbn code without dash (-) from 10 digit isbn code
     9×1 + 7×3 + 8×1 + 0×3 + 3×1 + 0×3 + 6×1 + 4×3 + 0×1 + 6×3 + 1×1 + 5×3 = 93.
 93 / 10 = 9 remainder 3.
 Check digit is the value needed to add to the sum to make it dividable 
 by 10. So the check digit is 7. The valid ISBN is 9780306406157.
"""
    mysum = 0
    ckd: Optional[int] = None
    if mystr and (mystr.find('-') != -1):
        if len(mystr) == 13:
            mystr = '978' + ''.join(mystr.split('-'))
            mystr = mystr[:-1]
            for i in range(len(mystr)):
                if (i+1) % 2 == 0:
                    mysum = mysum + int(mystr[i])*3
                else:
                    mysum = mysum + int(mystr[i])
                ckd = (10 - mysum % 10) % 10
            return mystr + str(ckd)
        elif len(mystr) == 17:
            return ''.join(mystr.split('-'))
    elif len(mystr) == 10 and (mystr.find('-') == -1):
        mystr = str('978') + mystr
        mystr = mystr[:-1]
        for i in range(len(mystr)):
            if (i+1) % 2 == 0:
                mysum = mysum + int(mystr[i])*3
            else:
                mysum = mysum + int(mystr[i])
            ckd = (10 - mysum % 10) % 10
        return str(mystr) + str(ckd)
    else:
        return mystr

def get_count(conn, table):
    count = conn.execute(f"SELECT COUNT(*) FROM '{table}'")
    count = count.fetchone()
    return count[0]


async def aget_count(conn, table):
    count = await conn.execute(f"SELECT COUNT(*) FROM {table}")
    count = await count.fetchone()
    return count[0]


def get_q(conn):
    conn.row_factory = sqlite3.Row
    qres = conn.execute("SELECT q FROM msg ORDER BY date DESC LIMIT 1")
    qres = qres.fetchone()
    if qres:
        q = qres['q']
        q = q + 1
    else:
        q = 0
    return q

async def aget_q(conn):
    conn.row_factory = aiosqlite.Row
    qres = await conn.execute("SELECT q FROM msg ORDER BY date DESC LIMIT 1")
    qres = await qres.fetchone()
    if qres:
        q = qres['q']
        q = q + 1
    else:
        q = 0
    return q

def update_msg(conn, message):
    q = get_q(conn)
    date = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("INSERT INTO msg (date,message,q) VALUES(?,?,?)", (date, message, q))
    conn.commit()
    
async def aupdate_msg(conn, message):
    q = await aget_q(conn)
    date = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    await conn.execute("INSERT INTO msg (date,message,q) VALUES(?,?,?)", (date, message, q))
    await conn.commit()

    
def clear_prof_name(prof_name):
    prof_name = re.sub(r'\(.+\)\Z', '', prof_name).strip(' -')
    if prof_name.lower().startswith(('docente', 'docenti','assegnazione','000000 00000', 'not assigned')):
        prof_name = ''
    if re.search(r'\bnon\s(.)*(assegnato|definito|assegnati|definiti|Not Assigned)', prof_name, re.IGNORECASE):
        prof_name = ''
    if re.search(r'^da definire|^da nominare|Assegnazione|^[0\s]+', prof_name, re.IGNORECASE):
        prof_name = ''
    return prof_name.replace(', ', ' ').replace(',', ' ').strip().title()
    
def get_alma_api_multiple(filtered_params):
    alma = Alma_api()
    user_vars = dict(filtered_params)
    if user_vars.get('materia_ssd_cod'):
        user_vars['materia_ssd_cod'] = ','.join(user_vars['materia_ssd_cod'])
    if user_vars.get('isbn'):
        user_vars['isbn'] = ','.join(user_vars['isbn'])
    if user_vars.get('editore'):
        user_vars['editore'] = ','.join(user_vars['editore'])
    data = None
    if 'uni_cod' not in user_vars:
        unis = alma.download_uni(user_vars['a_a'])
        params = []
        for k in user_vars:
            params.append(f"{k}={user_vars[k]}")
        data = alma.download_all_sites(unis, params)
    elif 'uni_cod' in user_vars:
        unis = user_vars['uni_cod']
        del user_vars['uni_cod']
        params = []
        for k in user_vars:
            params.append(f"{k}={user_vars[k]}")
        data = alma.download_all_sites(unis, params)
    return data

def get_alma_api(**kwargs):
    alma = Alma_api()
    user_vars = kwargs
    data = None
    if 'uni_cod' not in user_vars:
        unis = alma.download_uni(user_vars['a_a'])
        params = []
        for k in user_vars:
            params.append(f"{k}={user_vars[k]}")
        data = alma.download_all_sites(unis, params)
    elif 'uni_cod' in user_vars:
        unis = user_vars['uni_cod']
        del user_vars['uni_cod']
        params = []
        for k in user_vars:
            params.append(f"{k}={user_vars[k]}")
        data = alma.download_all_sites(unis, params)
    return data
    
# solo con requests
def get_alma_api_2(**kwargs):
    user_vars = kwargs
    adozioni = pd.DataFrame()
    if 'uni_cod' not in user_vars:
        r = requests.get(API_UNI, stream=True)
        r.raise_for_status()
        unicontent = json.loads(r.content)
        unis = [j['uni_cod'] for j in unicontent['data']]
    else:
        unis = user_vars['uni_cod']
    for uni in unis:
        params = ['uni_cod='+uni]
        for k in user_vars:
            params.append(f"{k}={user_vars[k]}")
        r = requests.get(API_ADOZIONI + '&'.join(params), stream=True)                  
        r.raise_for_status()
        txt = json.loads(r.content)
        df = pd.json_normalize(txt['data'])
        adozioni = pd.concat([adozioni, df], ignore_index=True)
        # I dati arrivano paginati a 1000 record alla volta
        # content['next_page_url'] contiene url per andare alla pagina successiva
        while txt.get('next_page_url', '') != '':
            r = requests.get(txt['next_page_url'])
            r.raise_for_status()
            txt = json.loads(r.content)
        df = pd.json_normalize(txt['data'])
        adozioni = pd.concat([adozioni, df], ignore_index=True)
        adozioni = adozioni.drop_duplicates()
    return adozioni

def ini_db(prof_df, db):
    with sqlite3.connect(p/f'dbfiles/{db}.db') as conn:
        prof_df.to_sql('tuttidocenti', conn, if_exists='replace', index=False)
        
# solo per operatori almalibri
def init_file():
    host='produzione.almalibri.it'
    dbname='work_unicoursebooks'
    user='claudio'
    password='Matilde1995?'
    port=5433
    query = """
             WITH cte AS (
        SELECT
            work_prof_id.prof_id,
            work_prof_id.uni_cod,
            work_prof_id.prof_nome,
            work_prof_id.prof_array,
            insegnamenti.insegnamento_id,
            insegnamenti.insegnamento_prof_www,
            materia_ssd.materia_ssd_cod,
            materie.materia_nome,
            ROW_NUMBER() OVER (PARTITION BY work_prof_id.prof_id ORDER BY insegnamenti.insegnamento_id DESC) AS rn
        FROM
            work_prof_id
        JOIN insegnamento_prof_id ON work_prof_id.prof_id = insegnamento_prof_id.prof_id
        JOIN insegnamenti ON insegnamento_prof_id.insegnamento_id = insegnamenti.insegnamento_id
        JOIN materia_ssd ON insegnamenti.materia_id = materia_ssd.materia_id
        JOIN materie ON materia_ssd.materia_id = materie.materia_id
    )
   SELECT prof_id, uni_cod, prof_nome as insegnamento_prof, prof_array, insegnamento_id, insegnamento_prof_www, 
          materia_ssd_cod, materia_nome FROM cte WHERE rn = 1;
        """
    connections_string = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
    with psycopg.connect(connections_string) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(query)
                data = cur.fetchall()
                df = pd.DataFrame(data, columns=[desc[0] for desc in cur.description])
                df.to_csv('prof_alma_ssd.csv', sep=',', index=False)
        except (Exception, psycopg.Error) as error:
            raise error
            
    #return data 

# per popolare tuttidocenti:
# """\COPY (
#     WITH cte AS (
#         SELECT
#             work_prof_id.prof_id,
#             work_prof_id.uni_cod,
#             work_prof_id.prof_nome,
#             work_prof_id.prof_array,
#             insegnamenti.insegnamento_id,
#             insegnamenti.insegnamento_prof_www,
#             materia_ssd.materia_ssd_cod,
#             materie.materia_nome,
#             ROW_NUMBER() OVER (PARTITION BY work_prof_id.prof_id ORDER BY insegnamenti.insegnamento_id DESC) AS rn
#         FROM
#             work_prof_id
#         JOIN insegnamento_prof_id ON work_prof_id.prof_id = insegnamento_prof_id.prof_id
#         JOIN insegnamenti ON insegnamento_prof_id.insegnamento_id = insegnamenti.insegnamento_id
#         JOIN materia_ssd ON insegnamenti.materia_id = materia_ssd.materia_id
#         JOIN materie ON materia_ssd.materia_id = materie.materia_id
#     )
#    SELECT prof_id, uni_cod, prof_nome as insegnamento_prof, prof_array, insegnamento_id, insegnamento_prof_www, 
#           materia_ssd_cod, materia_nome FROM cte WHERE rn = 1)
#    TO '/home/claudio/Dropbox/progetto_ecommerce/marketing/fastapi-docker-2/prof_alma_ssd.csv' DELIMITER ',' CSV HEADER;
# """


# campi: prof_id, uni_cod, prof_nome, insegnamento_prof, insegnamento_id, insegnamento_prof_www, materia_ssd_cod, materia_nome
# query nuova:
# \COPY (WITH cte AS (SELECT work_prof_id.prof_id, work_prof_id.prof_nome, work_prof_id.prof_array, 
# work_prof_id_ssd.prof_ssd FROM work_prof_id
#   LEFT JOIN work_prof_id_ssd ON work_prof_id.prof_id = work_prof_id_ssd.prof_id ),
# cte2 AS (SELECT insegnamento_prof_id.insegnamento_id, insegnamento_prof_id.prof_id, 
# insegnamenti.insegnamento_prof_www FROM insegnamento_prof_id 
# 	LEFT JOIN insegnamenti ON insegnamento_prof_id.insegnamento_id=insegnamenti.insegnamento_id
# 	LEFT JOIN curr_materie_insegnamenti ON insegnamento_prof_id.insegnamento_id=curr_materie_insegnamenti.insegnamento_id
# 	LEFT JOIN curricula_materie ON curricula_materie.curr_materia_id=curr_materie_insegnamenti.curr_materia_id
# 	LEFT JOIN curricula ON curricula.curr_id = curricula_materie.curr_id
# 	LEFT JOIN lauree ON curricula.laurea_id=lauree.laurea_id WHERE laurea_aa = 2024),
# cte3 AS (SELECT insegnamento_prof_www, prof_id, ROW_NUMBER() OVER (PARTITION BY cte2.prof_id ORDER BY cte2.insegnamento_id DESC) AS rn FROM cte2)
# SELECT cte.prof_id, cte.prof_nome, cte.prof_array, cte.prof_ssd, cte3.insegnamento_prof_www FROM cte JOIN cte3 ON cte.prof_id = cte3.prof_id WHERE cte3.rn=1)
# TO '/home/claudio/Dropbox/progetto_ecommerce/marketing/fastapi-docker-2/insegnamento_id.csv' DELIMITER ',' CSV HEADER;
# def ini_db():
#     prof = pd.read_csv('/home/claudio/prof_alma_ssd.csv', sep=',')
#     with sqlite3.connect('sql_app.db') as conn:
#         prof.to_sql('tuttidocenti', conn, if_exists='replace', index=False)
        

