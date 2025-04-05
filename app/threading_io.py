import concurrent.futures
import time
import json
import threading
import httpx
import csv
import itertools
import logging


class Alma_api:
    def __init__(self):
        self.API_UNI = 'https://almalibri.it/api/lista_uni/'
        self.API_ADOZIONI = 'https://almalibri.it/api/adozioni/?'
        self.API_PROGRAMMI = 'https://almalibri.it/api/biblio_request/?'
        self.thread_local = threading.local()
        self.session = httpx.Client()

    def get_session(self):
        if not hasattr(self.thread_local, "session"):
            self.thread_local.session = httpx.Client()
        return self.thread_local.session

    def download_uni(self, a_a):
        session = self.get_session()
        r = session.get(self.API_UNI)
        unicontent = json.loads(r.content)
        unis = [j['uni_cod'] for j in [x for x in unicontent['data'] if x['max']>=int(a_a)]]
        #unis = [j['uni_cod'] for j in [x for x in unicontent['data']]]
        return unis

    def download_deep_site(self, s, txt):
        while s != '':
            r = httpx.get(s)
            r.raise_for_status()
            res = json.loads(r.content)
            txt = txt + res['data']
            s = res['next_page_url']
        return txt

    def download_site(self, site):
        session = self.get_session()
        params = ['uni_cod='+site[0]]
        for k in site[1]:
            params.append(f"{k}")
        txt = []
        r = session.get(self.API_ADOZIONI + '&'.join(params))
        if r.content:
            res = json.loads(r.content)
            txt = res['data']
            s = res['next_page_url']
            if s != '':
                txt = self.download_deep_site(s, txt)
        else:
            logging.error(f"Error in download_site: {r.url}")
        return txt

    def download_all_sites(self, unis, params):
        if type(unis) == str:
            unis = [unis]
        sites = [(uni, params) for uni in unis]
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_site = {executor.submit(self.download_site, site): site for site in sites}
            data = []
            for future in concurrent.futures.as_completed(future_to_site):
                data.append(future.result())
        return data
    
    def write_csv(self, data, filename='output.csv'):
        data_out = itertools.chain.from_iterable(data)
        f = csv.writer(open(filename, "w+"))
        f.writerow(['uni_cod', 'a_a', 'facolta', 'laurea_nome', 
                    'laurea_tipo', 'sede',
                    'laurea_classe_cod',
                    'curr_nome',
                    'materia_nome',
                    'materia_ssd_cod',
                    'materia_cfu',
                    'curr_materia_anno',
                    'curr_materia_periodo',
                    'modulo_nome',
                    'sub_modulo_gruppo',
                    'sub_modulo_nome',
                    'modulo_cfu',
                    'modulo_periodo',
                    'insegnamento_prof',
                    'insegnamento_prof_www',
                    'isbn',
                    'autori',
                    'curatori',
                    'traduttori',
                    'titolo',
                    'editore',
                    'edizione',
                    'anno_pub',
                    'tipo_copertina',
                    'pagg',
                    'lingua',
                    'prezzo',
                    'testo_obb',
                    'testo_uso',
                    'testo_freq',
                    'laurea_iscritti',
                    'laurea_matricole',
                    'prof_id',
                    'insegnamento_id'])
        for x in data_out:
            f.writerow([x['uni_cod'], x['a_a'], x['facolta'], 
                        x['laurea_nome'], x['laurea_tipo'], x['sede'],
                        x['laurea_classe_cod'],
                        x['curr_nome'],
                        x['materia_nome'],
                        x['materia_ssd_cod'],
                        x['materia_cfu'],
                        x['curr_materia_anno'],
                        x['curr_materia_periodo'],
                        x['modulo_nome'],
                        x['sub_modulo_gruppo'],
                        x['sub_modulo_nome'],
                        x['modulo_cfu'],
                        x['modulo_periodo'],
                        x['insegnamento_prof'],
                        x['insegnamento_prof_www'],
                        x['isbn'],
                        x['autori'],
                        x['curatori'],
                        x['traduttori'],
                        x['titolo'],
                        x['editore'],
                        x['edizione'],
                        x['anno_pub'],
                        x['tipo_copertina'],
                        x['pagg'],
                        x['lingua'],                    
                        x['prezzo'],
                        x['testo_obb'],
                        x['testo_uso'],
                        x['testo_freq'],
                        x['laurea_iscritti'],
                        x['laurea_matricole'],
                        x['prof_id'],
                        x['insegnamento_id']])


    
    