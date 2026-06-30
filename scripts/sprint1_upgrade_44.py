"""
Applauz - Sprint 1 : enrichissement local de la base 44.
A lancer depuis la racine du projet :
    python scripts/sprint1_upgrade_44.py
Ce script ne va pas sur Internet. Il structure et enrichit la base existante.
"""
import os, re, sqlite3, unicodedata, datetime, uuid

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB = os.path.join(ROOT, 'app', 'artyx.sqlite')
TODAY = datetime.date.today().isoformat()

def norm(s: str) -> str:
    s = s or ''
    s = ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[^a-z0-9]+', ' ', s).strip()
    return re.sub(r'\s+', ' ', s)

def q(con, sql, args=()):
    return con.execute(sql, args)

def table_exists(con, name):
    return con.execute("select 1 from sqlite_master where type='table' and name=?", (name,)).fetchone() is not None

def one(con, sql, args=(), default=0):
    r = con.execute(sql, args).fetchone()
    return r[0] if r else default

def main():
    if not os.path.exists(DB):
        raise SystemExit(f"Base introuvable : {DB}")
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    con.executescript('''
    CREATE TABLE IF NOT EXISTS lieux_canoniques(
        id_canonique TEXT PRIMARY KEY,
        nom_officiel TEXT NOT NULL,
        nom_normalise TEXT,
        ville TEXT,
        code_insee TEXT,
        dep_code TEXT DEFAULT '44',
        type_lieu TEXT DEFAULT 'a_qualifier',
        statut_validation TEXT DEFAULT 'a_valider',
        niveau_confiance TEXT DEFAULT 'proposition',
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS lieu_aliases(
        id_alias TEXT PRIMARY KEY,
        id_canonique TEXT,
        alias TEXT NOT NULL,
        alias_normalise TEXT,
        source TEXT,
        nb_occurrences INTEGER DEFAULT 0,
        statut_validation TEXT DEFAULT 'a_valider',
        FOREIGN KEY(id_canonique) REFERENCES lieux_canoniques(id_canonique)
    );
    CREATE TABLE IF NOT EXISTS representations_lieux_match(
        id_match TEXT PRIMARY KEY,
        source_event_id INTEGER,
        occurrence_no INTEGER,
        date TEXT,
        summary TEXT,
        city_guess TEXT,
        id_canonique TEXT,
        score_match INTEGER,
        statut_validation TEXT DEFAULT 'proposition',
        commentaire TEXT
    );
    CREATE TABLE IF NOT EXISTS communes_44_progress(
        code_insee TEXT PRIMARY KEY,
        commune TEXT,
        population INTEGER,
        epci_nom TEXT,
        nb_passages_kenny INTEGER DEFAULT 0,
        nb_lieux_identifies INTEGER DEFAULT 0,
        nb_alias_proposes INTEGER DEFAULT 0,
        statut_analyse TEXT DEFAULT 'a_faire',
        priorite TEXT DEFAULT 'normale',
        prochaine_action TEXT,
        derniere_maj TEXT
    );
    CREATE TABLE IF NOT EXISTS sprint_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date_action TEXT,
        sprint TEXT,
        action TEXT,
        details TEXT
    );
    ''')

    # communes 44
    if table_exists(con, 'communes_france'):
        rows = con.execute("""
            SELECT code_insee, nom_standard, population, epci_nom
            FROM communes_france
            WHERE dep_code='44'
        """).fetchall()
        for r in rows:
            con.execute('''INSERT OR IGNORE INTO communes_44_progress
                (code_insee, commune, population, epci_nom, derniere_maj)
                VALUES (?,?,?,?,?)''', (r['code_insee'], r['nom_standard'], r['population'], r['epci_nom'], TODAY))

    # priorité selon population + historique
    if table_exists(con, 'historique_scene_memory'):
        for r in con.execute("SELECT city_guess, count(*) as nb FROM historique_scene_memory WHERE city_guess IS NOT NULL AND city_guess<>'' GROUP BY city_guess"):
            cityn = norm(r['city_guess'])
            match = con.execute("SELECT code_insee, commune FROM communes_44_progress").fetchall()
            for m in match:
                if norm(m['commune']) == cityn:
                    con.execute("UPDATE communes_44_progress SET nb_passages_kenny=?, priorite='tres_haute', prochaine_action='Relier précisément les lieux déjà joués par Kenny', derniere_maj=? WHERE code_insee=?", (r['nb'], TODAY, m['code_insee']))

    con.execute("UPDATE communes_44_progress SET priorite='haute', prochaine_action='Chercher site officiel, agenda culturel et équipements' WHERE priorite='normale' AND population >= 10000")
    con.execute("UPDATE communes_44_progress SET prochaine_action=COALESCE(prochaine_action,'Recherche commune par commune') WHERE prochaine_action IS NULL")

    # lieux existants 44 -> canoniques
    if table_exists(con, 'lieux_culturels'):
        for r in con.execute("SELECT * FROM lieux_culturels WHERE dep_code='44'"):
            nom = r['nom_lieu']
            ville = r['ville'] or ''
            ident = 'LC-' + norm(ville + '-' + nom).replace(' ', '-')[:80]
            con.execute('''INSERT OR IGNORE INTO lieux_canoniques
                (id_canonique, nom_officiel, nom_normalise, ville, code_insee, dep_code, type_lieu, statut_validation, niveau_confiance, notes)
                VALUES (?,?,?,?,?,?,?,?,?,?)''',
                (ident, nom, norm(nom), ville, r['code_insee'], '44', r['type_lieu'] or 'a_qualifier', 'a_valider', r['niveau_confiance'] or 'proposition', r['notes']))
            con.execute('''INSERT OR IGNORE INTO lieu_aliases
                (id_alias, id_canonique, alias, alias_normalise, source, nb_occurrences, statut_validation)
                VALUES (?,?,?,?,?,?,?)''',
                ('AL-' + norm(ville + '-' + nom).replace(' ', '-')[:80], ident, nom, norm(nom), 'lieux_culturels', 1, 'valide_source'))

    # propositions d'alias depuis l'agenda : on prend le summary comme indice de lieu
    if table_exists(con, 'historique_scene_memory'):
        patterns = [
            ('Théâtre 100 Noms', ['100 noms','theatre 100 noms','spectacle fete des meres au 100 noms'], 'Nantes', 'theatre'),
            ('Le Grand T', ['grand t'], 'Nantes', 'theatre'),
            ('La Compagnie du Café-Théâtre', ['compagnie du cafe theatre','cafe theatre nantes'], 'Nantes', 'cafe_theatre'),
            ('Le Bacchus', ['bacchus','le bacchus'], 'Rennes', 'cafe_theatre'),
            ('Théâtre de Jeanne', ['theatre de jeanne','jeanne'], 'Nantes', 'theatre'),
            ('Cité des Congrès', ['cite des congres','cité des congrès'], 'Nantes', 'salle_spectacle'),
            ('TNT - Terrain Neutre Théâtre', ['tnt'], 'Nantes', 'theatre'),
        ]
        for officiel, aliases, ville, typ in patterns:
            canon_id = 'LC-' + norm(ville + '-' + officiel).replace(' ', '-')[:80]
            con.execute('''INSERT OR IGNORE INTO lieux_canoniques
                (id_canonique, nom_officiel, nom_normalise, ville, dep_code, type_lieu, statut_validation, niveau_confiance, notes)
                VALUES (?,?,?,?,?,?,?,?,?)''',
                (canon_id, officiel, norm(officiel), ville, '44' if ville in ['Nantes'] else '', typ, 'a_valider', 'proposition', 'Créé par moteur de normalisation Sprint 1'))
            for al in aliases:
                nb = 0
                for h in con.execute('SELECT source_event_id, occurrence_no, date, summary, city_guess FROM historique_scene_memory'):
                    if al in norm(h['summary']):
                        nb += 1
                        match_id = str(uuid.uuid4())
                        con.execute('''INSERT OR IGNORE INTO representations_lieux_match
                            (id_match, source_event_id, occurrence_no, date, summary, city_guess, id_canonique, score_match, commentaire)
                            VALUES (?,?,?,?,?,?,?,?,?)''',
                            (match_id, h['source_event_id'], h['occurrence_no'], h['date'], h['summary'], h['city_guess'], canon_id, 85, f"Alias détecté : {al}"))
                con.execute('''INSERT OR IGNORE INTO lieu_aliases
                    (id_alias, id_canonique, alias, alias_normalise, source, nb_occurrences, statut_validation)
                    VALUES (?,?,?,?,?,?,?)''',
                    ('AL-' + norm(ville + '-' + officiel + '-' + al).replace(' ', '-')[:100], canon_id, al, norm(al), 'historique_scene_memory', nb, 'a_valider'))

    # Update counts
    for r in con.execute("SELECT commune, code_insee FROM communes_44_progress").fetchall():
        lieux = one(con, "SELECT count(*) FROM lieux_canoniques WHERE ville=? OR code_insee=?", (r['commune'], r['code_insee']))
        aliases = one(con, "SELECT count(*) FROM lieu_aliases la JOIN lieux_canoniques lc ON lc.id_canonique=la.id_canonique WHERE lc.ville=?", (r['commune'],))
        con.execute("UPDATE communes_44_progress SET nb_lieux_identifies=?, nb_alias_proposes=?, derniere_maj=? WHERE code_insee=?", (lieux, aliases, TODAY, r['code_insee']))

    # Qualité : lieux sans type, communes prioritaires sans lieu
    con.execute("DELETE FROM qualite_donnees WHERE table_nom IN ('lieux_canoniques','communes_44_progress')")
    for r in con.execute("SELECT id_canonique, nom_officiel FROM lieux_canoniques WHERE dep_code='44' AND (type_lieu IS NULL OR type_lieu='a_qualifier')"):
        con.execute("INSERT INTO qualite_donnees(table_nom, objet_id, champ, probleme, gravite, statut) VALUES (?,?,?,?,?,?)",
                    ('lieux_canoniques', r['id_canonique'], 'type_lieu', 'Type de lieu à qualifier', 'moyenne', 'ouvert'))
    for r in con.execute("SELECT code_insee, commune, priorite FROM communes_44_progress WHERE priorite IN ('tres_haute','haute') AND nb_lieux_identifies=0"):
        con.execute("INSERT INTO qualite_donnees(table_nom, objet_id, champ, probleme, gravite, statut) VALUES (?,?,?,?,?,?)",
                    ('communes_44_progress', r['code_insee'], 'lieux', f"Commune prioritaire sans lieu identifié : {r['commune']}", 'haute', 'ouvert'))

    con.execute("INSERT INTO sprint_log(date_action,sprint,action,details) VALUES (?,?,?,?)",
                (TODAY, 'Sprint 1 - Base 44', 'migration', 'Création tables lieux_canoniques, aliases, matches, communes_44_progress'))
    con.commit()
    # Summary
    summary = {
        'communes_44': one(con, 'SELECT count(*) FROM communes_44_progress'),
        'lieux_canoniques': one(con, 'SELECT count(*) FROM lieux_canoniques'),
        'aliases': one(con, 'SELECT count(*) FROM lieu_aliases'),
        'matches_agenda': one(con, 'SELECT count(*) FROM representations_lieux_match'),
        'points_qualite': one(con, "SELECT count(*) FROM qualite_donnees WHERE statut='ouvert'")
    }
    con.close()
    print('Applauz Sprint 1 terminé.')
    for k,v in summary.items():
        print(f'- {k}: {v}')

if __name__ == '__main__':
    main()
