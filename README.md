# Guida ad AlmaDati

## Guida rapida

### Introduzione

![Diagramma del sito AlmaDati](https://almalibri-staticfiles.fra1.digitaloceanspaces.com/static/images/mermaid_flowchart.jpg)

0. Per accedere all'applicazione è necessario scrivere a <info@almalibri.it>, che provvederà alla creazione dell'account.

1. Almalibri, l'applicazione "genitore" su cui si appoggia AlmaDati (l'app di cui state leggendo la documentazione), consente di estrarre sia le adozioni che l'offerta formativa attraverso un apposito [web form](https://www.almalibri.it/guida/adozioni). AlmaDati è una piccola applicazione che consente di selezionare o visualizzare, più o meno facilmente, le principali informazioni contenute in Almalibri.  
AlmaDati è divisa in due menu principali: uno per l'analisi delle "adozioni", l'altro per la gestione dei docenti, denominato "promozione".
L'applicazione è pensata per effettuare query sulle adozioni universitarie che seguono lo schema di [Almalibri](https://www.almalibri.it/guida/adozioni). I file con le adozioni possono provenire tanto dalla consultazione via API ad Almalibri, tanto dal download di file csv dallo stesso sito web, quanto da una rielaborazione personale di dati ottenuti in altro modo. L'importante è che il file segua il tracciato record [qui indicato](https://www.almalibri.it/guida/adozioni).  

2. Il menù "adozioni" consente di gestire i dati adozionali individuando i docenti, i libri di testo, gli insegnamenti e il numero di studenti presunto per ogni titolo adottato. Il menù "promozione" gestisce i docenti, tiene memoria delle copie saggio inviate, è utile alla gestione degli indirizzari. In entrambi i menù si parte dai dati selezionati da Almalibri (o in altro modo come indicato al punto 1), si procede per selezioni successive o per inserimento di altre informazioni, per arrivare alla dashboard che ricapitola i dati gestiti.

3. Nella colonna di sinistra, nel menù Funzioni, sotto ai diversi link, si trova la tabella "Selezioni effettuate" che consente di tenere sotto controllo le diverse query e i parametri utilizzati (ad esempio prof_id, università, ssd). È sempre possibile scaricare i dati elaborati oppure eliminarli ed eventualmente ricominciare da capo il processo di selezione.

4. Gli utenti che hanno accesso all'applicazione devono essere collegati al nome di un'azienda (un *tenant*). Per ogni azienda possono esserci molti utenti ma un utente non può appartenere a più aziende. I dati sono condivisi per singola azienda. Cioè se un utente scarica dei dati e decide di cancellarne una parte, cancella i dati anche per gli altri utenti che appartengono alla stessa azienda. In altre parole ogni azienda (*tenant*) individua un gruppo di lavoro che condivide gli stessi dati.

### Le adozioni

I dati caricati dalla pagina [Carica dati](https://almadati.it/form) provengono direttamente dalle API di Almalibri. Se invece si possiede già un file, scaricato in precedenza, eventualmente corretto o modificato, andrà inserito nella pagina [Carica file](https://almadati.it/uploadfile). Il processo da tenere a mente è che i dati, dopo essere stati caricati, vengono sottoposti a una serie di selezioni il cui risultato compare infine nella pagina [Dashboard](https://almadati.it).  

La pagina [Università](https://almadati.it/universita) accede ad Almalibri e scarica l'elenco delle università disponibili. Selezionando una o più università, si selezionano le adozioni tra quelle precedentemente scaricate da [Carica dati](https://almadati.it/form), appartenenti appunte alle università scelte.

La pagina [Libri](https://almadati.it/libri) mostra l'elenco dei libri adottati contenuti nella selezione già effettuata e consente di selezionare uno o più ISBN, se si fosse interessati solo ad alcuni titoli invece che ad altri. Il dato selezionato è l'"ISBN".

La pagina [Docenti](https://almadati.it/docenti) mostra anch'essa il semplice elenco dei docenti contenuti nella precedente selezione, mostrando alcuni dati rilevanti per l'individuazione del nome. Si può procedere a un'ulteriore selezione. Il dato selezionato è il "prof_id".

La pagina [SSD](https://almadati.it/adozioni) mostra l'elenco delle adozioni (ovvero l'associazione insegnamento - ISBN) e compie una selezione solo sull'SSD. È sufficiente selezionare anche una sola adozione appartenente all'SSD che si vuole analizzare.

La pagina [Nuove adozioni](https://almadati.it/nuove_adozioni) mette a confronto le adozioni dei singoli docenti, per ogni corso di laurea (a cui fanno riferimento il numero degli studenti iscritti) e mostra l'elenco delle nuove adozioni, ovvero quelle che per quel docente, in quel corso di laurea, non erano presenti l'anno precedente.

La pagina [Insegnamenti](https://almadati.it/insegnamenti) mostra l'elenco degli insegnamenti e procede alla selezione sulla base del prof_id, cioè del docente.  

Infine la pagina [Dashboard](https://almadati.it) riassume i dati ottenuti riportando l'elenco dei docenti, il numero di studenti che potrebbero acquistare il volume e l'elenco delle adozioni. I dati sono tutti scaricabili in formato csv.

### Il menù Funzioni

A sinistra, in ogni pagina, si trova il menù "Funzioni". È suddiviso in tre parti: le funzioni di gestione dati, la gestione del database del gruppo di lavoro a cui appartiene l'utente, le "Selezioni effettuate", ovvero una serie di messaggi che costituiscono un promemoria delle selezioni effettuate.  
Si è già detto delle funzioni nel paragrafo precedente.  

1. "Cancella le adozioni selezionate" cancella le tabelle con i messaggi (le "Selezioni effettuate") e quella con le selezioni delle adozioni;  
2. "Cancella i dati del menù adozioni" cancella, oltre alle tabelle precedenti, anche quella che riporta i dati scaricati da Almalibri;  
3. "Cancella tutti i dati e crea backup" crea prima una copia del database e cancella, oltre a tutte le precedenti, anche la tabella con le selezioni dei docenti ("Tutti i docenti"). Scarica sempre un backup per ragioni di sicurezza.  
4. Infine con "Scarica backup" si può creare un backup in qualsiasi momento e continuare il lavoro in un altro ambiente di sviluppo.  
Uno strumento semplice per consultare il database così creato è [DB Browser for SQLite](https://sqlitebrowser.org/). Questo *client* consente di aprire il database, visualizzare le tabelle, eseguire query, modificare i dati e infine esportarli in csv.  

### Il menù Ricerca

Questa pagina consente di cercare ed estrarre dati mediante richieste in linguaggio naturale inserite nell'input denominato `Cerca`. La ricerca verrà effettuata all'interno dei dati caricati e modificati in questa applicazione, facendo uso di un modello della serie ChatGPT. L'applicazione restituisce una query in linguaggio SQL che verrà eseguita solo se accettata (o modificata) dall'operatore. Il risultato comparirà nella stessa pagina. Eventualmente si potranno scaricare i dati in formato csv.

### Il menù Promozione

Il menù "promozione" è pensato per gestire i dati relativi ai docenti, alle copie saggio e agli indirizzari.  

[Selezione docenti](https://almadati.it/router_cerca_docenti) In questa pagina è possibile estrarre i docenti di tutti gli anni accademici, ciascuno con l'url personale, quando pubblicamente disponibile, esportare i dati in formato csv e procedere a eventuali analisi e modifiche delle anagrafiche.  

[Gestione docenti](https://almadati.it/gestione_docenti) In questa pagina si possono modificare o inserire i dati relativi ai docenti, agli indirizzari e alle copie saggio inviate. I records sono editabili e cancellabili. Si può sempre scaricare il risultato del lavoro in formato csv.

[Dashboard docenti](https://almadati.it/dashboard_docenti) Questa pagina riassume i dati relativi ai docenti, alle copie saggio e agli indirizzari. Si possono scaricare i dati in formato csv. Consente di accedere direttamente su Almalibri alle adozioni del docente e alle adozioni di libro adottato.

## Esempi

### Cercare i docenti

1. Selezionare i docenti da almalibri con l'ssd desiderato (da "Scarica da almalibri")
2. Nella pagina "Docenti" compariranno i docenti con l'ssd desiderato ma ripetuti se hanno più insegnamenti
3. Se si desidera un file csv con i nomi dei docenti e con la pagina url personale, per le successive ricerche di dati promozionali, conviene andare su "Dashboard" e scaricare il file csv dal pannello docenti
4. In alternativa si può cliccare su "Tutti i docenti" ed effettuare la selezione come indicato nella figuta 1 ![Selezione docenti](https://almalibri-staticfiles.fra1.digitaloceanspaces.com/static/images/selezione_docenti.png)

### Selezionare gli insegnamenti

Un elemento utile alla promozione è conoscere quali insegnamenti sono tenuti da un docente. Nella pagina "Insegnamenti" si possono selezionare gli insegnamenti di un docente. Nella "Dashboard" compaiono, e si possono scaricare i corrispondenti file csv, i dati relativi al numero di studenti che potrebbero acquistare il libro adottato, l'elenco delle adozioni di quel docente e dove trovare sul web le informazioni personali del docente.  

### Selezionare i libri adottati

Continuando lo stesso esempio, si può selezionare un libro adottato da un docente. Nella pagina "Libri" si seleziona l'ISBN del libro adottato. Nella "Dashboard" compaiono, e si possono scaricare i corrispondenti file csv, i dati relativi al numero di studenti che potrebbero acquistare il libro adottato, l'elenco delle adozioni di quel docente e dove trovare sul web le informazioni personali del docente.  

### Elenco dei corsi  

Per ottenere l'elenco dei corsi dove è adottato un volume, occorre selezionarlo nella pagina "Libri". Nella "Dashboard" si troveranno così l'elenco dei docenti che lo adottano, il numero (vedi le considerazioni sulla correttezza di questo dato) di studenti complessivo che potrebbe acquistarlo ogni anno e l'elenco delle adozioni.

### Iniziare una nuova selezione

Per iniziare una nuova ricerca/selezione, si può cliccare su "Cancella le adozioni selezionate" e ricominciare da capo. Si possono anche cancellare i dati del menù adozioni, oppure cancellare tutti i dati e creare un backup. In alternativa si può proseguire la ricerca conservando i dati già selezionati e aggiungere ad essi nuovi dati sia con "Scarica da almalibri" sia con "Carica file".  

### Individuare i docenti con nome e prof_id

Il prof_id è un identificativo che viene assegnato da Almalibri a ciascun docente sulla base del nome e cognome e dell'università. Non è un identificativo univoco. Lo stesso docente può insegnare in più università e avere più prof_id. Se un docente nel corso degli anni cambia università, il prof_id cambierà. Per questo motivo l'individuazione dei docenti e dei corsi è sempre basata su un insieme di dati.  
L'unico momento in cui si fa uso del prof_id come identificativo univoco è quando viene caricato, nel menu "promozione", un file con i dati "personali" dei docenti a cui si sono inviati saggi. In questo caso l'identità dei docenti sarà stata probabilmente controllata dall'utente.  

## Aggiornamento docenti

Nel menu "promozione" è disponibile la funzione "Aggiornamento docenti". Questa funzione consente di aggiornare i dati dei docenti consultabili su "Selezione docenti" con quelli presenti su [AlmaLibri](https://almalibri.it).  

Elenco dei link contenenti l'aggiornamento semestrale dei docenti presenti su [AlmaLibri](https://almalibri.it)  
I Semestre A.A 2024/25  
[docenti_2024_I_sem.csv](https://almalibri-backup.fra1.digitaloceanspaces.com/public/docenti/docenti_2024_I_sem.csv)  
II Semestre A.A 2024/25  
[docenti_2024_II_sem.csv](https://almalibri-backup.fra1.digitaloceanspaces.com/public/docenti/docenti_2024_II_sem.csv)  

I Semestre A.A 2025/26
In preparazione  
