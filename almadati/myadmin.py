from pathlib import Path
import almadati.auth as auth
import sqlite3
import hashlib, os
import pandas as pd
import os

p = Path(__file__).parent.resolve()
p = p / "dbfiles"

class CreateUser:
    def __init__(self, username: str, password: str, is_active: bool, tenant_id: str, is_admin: bool):
        self.username = username
        self.hashed_password =  auth.get_password_hash(password)
        self.is_active = is_active
        self.tenant_id = tenant_id
        self.is_admin = is_admin
        
    def create_user_db(self):
        with sqlite3.connect(p/'shared.db') as conn:
            conn.execute("INSERT INTO users (username, hashed_password, is_active, tenant_id, is_admin) \
                VALUES(?,?,?,?,?)", (self.username, self.hashed_password, self.is_active, self.tenant_id, self.is_admin))
    
    def init_tenant_db(self):
        db = hashlib.md5(f'{self.tenant_id}'.encode('utf-8')).hexdigest()
        # if os.path.isfile(p/f'{db}.db'):
        #     return None
        with sqlite3.connect(p/f'{db}.db') as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS msg (date TEXT, message TEXT, q INTEGER)")
            conn.execute("""CREATE TABLE IF NOT EXISTS adozioni_res (
                uni_cod TEXT, a_a TEXT, facolta TEXT, laurea_nome TEXT, 
                laurea_tipo TEXT, sede TEXT, laurea_classe_cod TEXT, curr_nome TEXT, 
                materia_nome TEXT, materia_ssd_cod TEXT, materia_cfu TEXT, curr_materia_anno TEXT,
                curr_materia_periodo TEXT, modulo_nome TEXT, sub_modulo_gruppo TEXT, sub_modulo_nome TEXT,
                modulo_cfu TEXT, modulo_periodo TEXT, insegnamento_prof TEXT, insegnamento_prof_www TEXT,
                isbn TEXT, autori TEXT, curatori TEXT, traduttori TEXT, titolo TEXT, editore TEXT,
                edizione TEXT, anno_pub TEXT, tipo_copertina TEXT, pagg TEXT, lingua TEXT, prezzo TEXT, 
                testo_obb TEXT, testo_uso TEXT, testo_freq TEXT, laurea_iscritti TEXT,
                laurea_matricole TEXT, prof_id TEXT, insegnamento_id TEXT)""")
            if os.path.isfile(p/'prof_alma_ssd.csv'):
                pd.read_csv(p/'prof_alma_ssd.csv').to_sql('tuttidocenti', conn, if_exists='replace', index=False)
            conn.execute("CREATE TABLE IF NOT EXISTS adozioni AS SELECT * FROM adozioni_res WHERE 0")
            conn.execute("CREATE INDEX ind_docenti_uni ON tuttidocenti (uni_cod);")
            conn.execute("CREATE INDEX ind_docenti_nome ON tuttidocenti (insegnamento_prof);")
            conn.execute("CREATE INDEX ind_docenti_ssd ON tuttidocenti (materia_ssd_cod);")
            conn.execute("CREATE INDEX ind_docenti_materia ON tuttidocenti (materia_nome);")
            conn.execute("""CREATE TABLE IF NOT EXISTS tuttidocenti_res(
                uni_cod TEXT, facolta TEXT, materia_ssd_cod TEXT, materia_nome TEXT, insegnamento_prof TEXT,
                insegnamento_prof_www TEXT, prof_id INTEGER,
                insegnamento_id INTEGER, email TEXT, indirizzo TEXT, citta TEXT, telefono TEXT, 
                note TEXT, isbn TEXT, titolo TEXT, data TEXT)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS docenti_router(
                uni_cod TEXT, facolta TEXT, materia_ssd_cod TEXT, materia_nome TEXT, insegnamento_prof TEXT, insegnamento_prof_www TEXT, prof_id INTEGER,
                insegnamento_id INTEGER, email TEXT, indirizzo TEXT, citta TEXT, telefono TEXT, 
                note TEXT, isbn TEXT, titolo TEXT, data TEXT)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS mailing(
                uni_cod TEXT, materia_ssd_cod TEXT, insegnamento_prof TEXT, prof_id INTEGER,
                insegnamento_id INTEGER, email TEXT, nome TEXT, note TEXT, data TEXT)""")
                        
               
        
        
# per popolare tuttidocenti:
# """\COPY (
#     WITH cte AS (
#         SELECT
#             work_prof_id.prof_id,
#             work_prof_id.uni_cod,
#             work_prof_id.prof_nome,
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
#    SELECT prof_id, uni_cod, prof_nome as insegnamento_prof, insegnamento_id, insegnamento_prof_www, materia_ssd_cod, materia_nome FROM cte WHERE rn = 1)
#    TO '/home/claudio/Dropbox/progetto_ecommerce/marketing/fastapi_docker/prof_alma_ssd.csv' DELIMITER ',' CSV HEADER;
# """
# def ini_db():
#     prof = pd.read_csv('/home/claudio/prof_alma_ssd.csv', sep=',')
#     with sqlite3.connect('sql_app.db') as conn:
#         prof.to_sql('tuttidocenti', conn, if_exists='replace', index=False)      