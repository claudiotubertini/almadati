from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts import HumanMessagePromptTemplate, AIMessagePromptTemplate
from langchain_core.prompts.few_shot import FewShotChatMessagePromptTemplate
#from langchain_community.utilities import SQLDatabase
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_core.runnables import RunnablePassthrough
from environs import Env
from pathlib import Path
from pydantic import BaseModel

p = Path(__file__).parent.resolve()
p = p / "dbfiles"

env = Env()
env.read_env()


def get_sql_from_ai(input, db):
    db = SQLDatabase.from_uri(f"sqlite:///{p}/{db}.db")

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key= env("OPENAI_API_KEY_api_key")
    )
    # oppure si può usare deepseek-chat
    # llm = ChatOpenAI(
    #     model="deepseek-chat",
    #     openai_api_key='<your api key>', 
    #     openai_api_base='https://api.deepseek.com',
    #     max_tokens=1024
    # )

    examples = [
        {"input": "Quanti sono gli studenti che hanno in adozione il libro con ISBN 9783406656019?",
        "output": "SELECT SUM(laurea_matricole) AS totale_studenti FROM (SELECT DISTINCT laurea_nome, laurea_matricole FROM adozioni WHERE isbn = 9783406656019) AS subquery"},
        {"input": "Quanti sono gli studenti che hanno in adozione il libro con ISBN 9783406656019?",
        "output": "WITH cts AS (SELECT DISTINCT uni_cod, laurea_nome, isbn, laurea_matricole AS studenti FROM adozioni) SELECT tbl1.isbn, tbl2.titolo, tbl2.autore, tbl2.editore, tbl1.studenti FROM  (SELECT n1.isbn, sum( CAST(n1.studenti as integer)) as studenti from cts n1 GROUP BY isbn) AS tbl1 INNER JOIN (SELECT DISTINCT isbn, titolo, autori ||' '||curatori AS autore, editore from adozioni) AS tbl2 ON tbl1.isbn = tbl2.isbn WHERE tbl1.isbn = 9783406656019;"},
        {"input": "Quali sono le adozioni di un insegnamento (materia_nome) o di una laurea (laurea_nome) o di un docente (insegnamento_prof)\
            o di un ssd (materia_ssd_cod) o di un isbn", 
        "output": "SELECT DISTINCT uni_cod, laurea_nome, materia_nome, materia_ssd_cod, insegnamento_prof, isbn, \
                        titolo, editore, testo_obb, laurea_matricole FROM adozioni;"},
        {"input": "Quanti sono gli studenti (laurea_matricole) dei diversi corsi di laurea (laurea_nome) che hanno in adozione un isbn",
        "output": "WITH cts AS (SELECT DISTINCT uni_cod, laurea_nome, isbn, laurea_matricole AS studenti FROM adozioni) \
                    SELECT tbl1.isbn, tbl2.titolo, tbl2.autore, tbl2.editore, tbl1.studenti FROM \
                    (SELECT n1.isbn, sum( CAST(n1.studenti as integer)) as studenti from cts n1 GROUP BY isbn) AS tbl1 \
                    INNER JOIN \
                    (SELECT DISTINCT isbn, titolo, autori ||' '||curatori AS autore, editore from adozioni) AS tbl2 \
                    ON tbl1.isbn = tbl2.isbn;"},
        {"input": "Quali sono i docenti con insegnamenti con ssd M-GGR/02?",
        "output": "SELECT DISTINCT insegnamento_prof FROM adozioni WHERE materia_ssd_cod = 'M-GGR/02';"},
        {"input": "Quali sono i docenti (insegnamento_prof) di una università (uni_cod) o di una sede o di un ssd (materia_ssd_cod)\
            o di una facoltà",
        "output": "SELECT DISTINCT prof_id, materia_ssd_cod, insegnamento_prof, insegnamento_prof_www, uni_cod, sede,facolta \
                        FROM adozioni;"},
        {"input": "Quali sono gli insegnamenti del docente Alessandro Iannucci?",
         "output": "SELECT uni_cod, materia_nome FROM adozioni WHERE insegnamento_prof = 'Alessandro Iannucci' \
         UNION SELECT uni_cod, materia_nome from tuttidocenti WHERE insegnamento_prof = 'Alessandro Iannucci';"},
        {"input": "Quali sono i libri inviati come saggio al docente Alessandro Iannucci?",
         "output": "SELECT DISTINCT isbn, titolo FROM tuttidocenti_res WHERE insegnamento_prof = 'Alessandro Iannucci';"}]

    example_prompt = (
        HumanMessagePromptTemplate.from_template("{input}")
        + AIMessagePromptTemplate.from_template("{output}")
    )

    few_shot_prompt = FewShotChatMessagePromptTemplate(
        examples=examples,
        example_prompt=example_prompt,
    )

    # Create prompt templates
    template1 = """Given an input question, convert it to a SQL query. No pre-amble.
    Based on the table schema below, write a SQL query that would answer the user's question
    {table_schema}
    Question: {question}
    SQL Query:"""

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "Given an input question, convert it to a SQL query. No pre-amble."),
            few_shot_prompt,
            ("human", template1),
        ]
    )

    def get_info(_):
        context = db.get_context()
        return context["table_info"]

    sql_response = (
        RunnablePassthrough.assign(table_schema=get_info)
        | prompt
        | llm.bind(stop=["\nSQLResult:"])
        | StrOutputParser()
    )
    try:
        response = sql_response.invoke({"question": input})
    except Exception as e:
        return f"L'esecuzione della domanda:\n\n{input}\n\nha causato il seguente errore:\n\n{type(e)}: {e}"
    return response