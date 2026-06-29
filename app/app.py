#!/usr/bin/env python3
import json, os, sqlite3, re, unicodedata, math, datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
BASE_DIR=os.path.dirname(os.path.abspath(__file__))
DB_PATH=os.path.join(BASE_DIR,'artyx.sqlite')
HOME_COORD=(47.2184,-1.5536)

def db():
    con=sqlite3.connect(DB_PATH); con.row_factory=sqlite3.Row; return con

def ensure_schema():
    con=db()
    con.execute("""CREATE TABLE IF NOT EXISTS notes_lieux(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        id_lieu TEXT,
        contenu TEXT NOT NULL,
        type_note TEXT DEFAULT 'note',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS notes_communes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code_insee TEXT,
        contenu TEXT NOT NULL,
        type_note TEXT DEFAULT 'note',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS profil_artiste(
        cle TEXT PRIMARY KEY,
        valeur TEXT
    )""")
    defaults={
      'nom':'Kenny Martineau',
      'baseline':'Humoriste • Comédien • Auteur • Réalisateur',
      'bio_courte':'Artiste de scène, auteur et comédien. Fiche à compléter.',
      'spectacle_actuel':'Je suis une princesse et je vous emmerde',
      'site':'https://www.kennymartineau.fr'
    }
    for k,v in defaults.items():
        con.execute('insert or ignore into profil_artiste(cle,valeur) values (?,?)',(k,v))
    con.commit(); con.close()

def strip_accents(s): return ''.join(c for c in unicodedata.normalize('NFD', s or '') if unicodedata.category(c) != 'Mn')
def norm(s):
    s=strip_accents((s or '').lower())
    return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9]+',' ',s)).strip()
def spectacle(summary):
    n=norm(summary)
    if 'princesse' in n: return 'Je suis une princesse'
    if '101' in n or 'trucs' in n: return '101 trucs à faire'
    if 'premiere partie' in n or '1ere partie' in n: return 'Premières parties'
    if 'plateau' in n or 'comedy club' in n or 'scene ouverte' in n: return 'Plateaux / comedy clubs'
    if 'festival' in n: return 'Festivals'
    return 'Autres scènes'
def parse_date(d):
    if not d: return None
    try: return datetime.datetime.fromisoformat(str(d).replace('Z','+00:00')).date()
    except Exception:
        try: return datetime.datetime.strptime(str(d)[:10],'%Y-%m-%d').date()
        except Exception: return None
def hav(a,b):
    lat1,lon1=a; lat2,lon2=b; R=6371
    dlat=math.radians(lat2-lat1); dlon=math.radians(lon2-lon1)
    x=math.sin(dlat/2)**2+math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return 2*R*math.asin(math.sqrt(x))
def country(summary, loc, city):
    n=norm(' '.join([summary or '',loc or '',city or '']))
    if any(x in n for x in ['suisse','geneve','lausanne','fribourg','neuchatel']): return 'Suisse'
    if any(x in n for x in ['belgique','bruxelles','brussels','liege']): return 'Belgique'
    return 'France'

def career_stats():
    con=db()
    rows=[dict(r) for r in con.execute('select date,summary,location,city_guess from historique_scene_memory order by date').fetchall()]
    coords={norm(r['nom_standard']):(float(r['latitude_mairie']),float(r['longitude_mairie'])) for r in con.execute('select nom_standard, latitude_mairie, longitude_mairie from communes_analyse where latitude_mairie is not null and longitude_mairie is not null')}
    con.close()
    specs={}; cities=set(); countries=set(); trips=[]; cur=None
    enriched=[]
    for r in rows:
        spec=spectacle(r['summary']); specs[spec]=specs.get(spec,0)+1
        city=(r.get('city_guess') or '').strip()
        if not city:
            for cname in list(coords.keys())[:]:
                pass
        if city: cities.add(city)
        ctry=country(r['summary'],r['location'],city); countries.add(ctry)
        dt=parse_date(r['date']); coord=coords.get(norm(city)) if city else None
        enriched.append({'date':dt,'spec':spec,'city':city,'coord':coord,'key':(spec,norm(city),norm(r['summary'])[:50])})
    for e in sorted([x for x in enriched if x['date']], key=lambda x:x['date']):
        if cur and cur['key']==e['key'] and (e['date']-cur['last']).days<=10:
            cur['last']=e['date']; cur['count']+=1
        else:
            if cur: trips.append(cur)
            cur={'key':e['key'],'last':e['date'],'count':1,'coord':e['coord'],'spec':e['spec']}
    if cur: trips.append(cur)
    km=0; known=0
    km_by={}
    for t in trips:
        if t['coord']:
            k=round(hav(HOME_COORD,t['coord'])*2*1.18)
            km+=k; known+=1; km_by[t['spec']]=km_by.get(t['spec'],0)+k
    return {
      'spectacles': sorted([{'spectacle':k,'count':v,'km':km_by.get(k,0)} for k,v in specs.items()], key=lambda x:x['count'], reverse=True),
      'villes_count': len(cities), 'pays': sorted(countries), 'km_estime': km, 'trajets_connus': known, 'evenements_scene': len(rows)
    }

INDEX_HTML='''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>ARTYX</title><meta name="theme-color" content="#8BCDBD"><link rel="manifest" href="/manifest.json"><link rel="stylesheet" href="/static/style.css"></head><body>
<div class="bg"></div><aside><div class="brand">ARTYX</div><div class="mini">Copilote artiste</div><nav>
<button class="nav active" data-tab="accueil">Accueil</button><button class="nav" data-tab="historique">Historique</button><button class="nav" data-tab="lieux">Salles & entités</button><button class="nav" data-tab="territoires">Territoires</button><button class="nav" data-tab="prospection">Base de prospection</button><button class="nav" data-tab="veille">Veille</button><button class="nav" data-tab="database">Base données</button><button class="nav" data-tab="chantier44">Chantier 44</button><button class="nav" data-tab="profil">Mon profil</button><button class="nav" data-tab="parametres">Paramètres</button>
</nav></aside><main><header><div><h1>Bonjour Kenny 👋</h1><p>Une seule interface ARTYX : carrière, territoires, prospection et veille.</p></div><input id="globalSearch" placeholder="Rechercher une ville, une salle, un spectacle..."></header>
<section class="tab visible" id="accueil"><div class="grid cards" id="homeCards"></div><div class="panel"><h2>Spectacles joués</h2><div id="spectacleStats"></div></div></section>
<section class="tab" id="historique"><div class="panel"><h2>Historique de scène</h2><input id="histSearch" placeholder="Filtrer : Princesse, Bacchus, Rennes..."><div id="histList" class="list"></div></div></section>
<section class="tab" id="lieux"><div class="panel"><h2>Salles & entités</h2><div class="row"><input id="lieuxSearch" placeholder="Rechercher dans les lieux"><select id="lieuxType"><option value="">Tous types</option><option>theatre</option><option>salle_municipale</option><option>salle_spectacle</option><option>casino</option></select></div><div class="split"><div id="lieuxList" class="list"></div><div id="lieuDetail" class="detail">Sélectionne un lieu.</div></div></div></section>
<section class="tab" id="territoires"><div class="panel"><h2>Territoires</h2><p class="muted">Base nationale issue du fichier communes : départements, communes, population et statut d'analyse.</p><div class="split"><div id="depList" class="list"></div><div><input id="communeSearch" placeholder="Chercher une commune"><div id="communeList" class="list"></div></div></div></div></section>
<section class="tab" id="prospection"><div class="panel"><h2>Base de prospection</h2><p class="muted">Lieux culturels identifiés et à enrichir, département par département.</p><div class="row"><input id="prospectSearch" placeholder="Rechercher lieu / ville"><select id="prospectDep"><option value="44">44 Loire-Atlantique</option><option value="85">85 Vendée</option><option value="49">49 Maine-et-Loire</option></select></div><div id="prospectList" class="list"></div></div></section>
<section class="tab" id="veille"><div class="panel"><h2>Veille</h2><div class="grid cards" id="veilleCards"></div><p class="muted">Objectif : programmer des réanalyses mensuelles par département. Pour l'instant, ARTYX structure les données à vérifier.</p></div></section>

<section class="tab" id="database"><div class="panel"><h2>Base de données en construction</h2><p class="muted">Suivi concret du nettoyage, des communes à analyser, des lieux à vérifier et des regroupements proposés.</p><div class="grid cards" id="dbCards"></div><div class="split"><div><h2>Communes 44 à analyser</h2><div id="queueCommunes" class="list"></div></div><div><h2>Regroupements proposés</h2><div id="aliasList" class="list"></div></div></div><div class="panel inner"><h2>Problèmes de qualité à corriger</h2><div id="qualityList" class="list"></div></div></div></section>

<section class="tab" id="chantier44"><div class="panel"><h2>Chantier 44 — Loire-Atlantique</h2><p class="muted">Travail concentré sur ton territoire principal : communes, historique Kenny, lieux identifiés et priorités d’analyse.</p><div class="grid cards" id="chantier44Cards"></div><div class="row"><input id="chantier44Search" placeholder="Chercher une commune du 44"><select id="chantier44Priority"><option value="">Toutes priorités</option><option value="tres_haute">Très haute</option><option value="haute">Haute</option><option value="normale">Normale</option></select></div><div class="split"><div><h2>Communes à traiter</h2><div id="chantier44List" class="list"></div></div><div><h2>Méthode de recherche</h2><div id="method44List" class="list"></div><h2>Hypothèses terrain</h2><div id="hypotheses44List" class="list"></div></div></div></div></section>
<section class="tab" id="profil"><div class="panel"><h2>Mon profil artiste</h2><div id="profilBox"></div></div></section>
<section class="tab" id="parametres"><div class="panel"><h2>Paramètres</h2><p>Palette actuelle : blanc majoritaire + vert d'eau.</p><p>Application locale unifiée. Les prochaines mises à jour s’ajouteront dans cette interface.</p></div></section>
</main><script src="/static/app.js"></script></body></html>'''
MANIFEST={'name':'ARTYX','short_name':'ARTYX','start_url':'/','display':'standalone','background_color':'#ffffff','theme_color':'#8BCDBD'}
class Handler(BaseHTTPRequestHandler):
    def _send(self,status=200,body=b'',ctype='application/json'):
        self.send_response(status); self.send_header('Content-Type',ctype); self.send_header('Cache-Control','no-store'); self.end_headers()
        if isinstance(body,str): body=body.encode('utf-8')
        self.wfile.write(body)
    def _json(self,obj,status=200): self._send(status,json.dumps(obj,ensure_ascii=False), 'application/json; charset=utf-8')
    def do_GET(self):
        p=urlparse(self.path); qs=parse_qs(p.query)
        if p.path=='/': return self._send(200,INDEX_HTML,'text/html; charset=utf-8')
        if p.path=='/manifest.json': return self._json(MANIFEST)
        if p.path.startswith('/static/'):
            fp=os.path.join(BASE_DIR,p.path.lstrip('/'))
            if not os.path.exists(fp): return self._json({'error':'not found'},404)
            ext=os.path.splitext(fp)[1].lower(); c='application/octet-stream'
            if ext=='.css': c='text/css; charset=utf-8'
            if ext=='.js': c='text/javascript; charset=utf-8'
            if ext in ['.jpg','.jpeg']: c='image/jpeg'
            if ext=='.png': c='image/png'
            return self._send(200,open(fp,'rb').read(),c)
        con=db()
        if p.path=='/api/overview':
            data=career_stats()
            data.update({
              'communes': con.execute('select count(*) from communes_france').fetchone()[0],
              'departements': con.execute('select count(*) from departements').fetchone()[0],
              'lieux': con.execute('select count(*) from lieux_culturels').fetchone()[0],
              'communes_44': con.execute("select count(*) from communes_analyse where dep_code='44'").fetchone()[0]
            }); con.close(); return self._json(data)
        if p.path=='/api/history':
            q=qs.get('q',[''])[0]
            args=[]; where='1=1'
            if q:
                where='summary like ? or coalesce(location,\'\') like ? or coalesce(city_guess,\'\') like ?'; args=[f'%{q}%']*3
            rows=[dict(r) for r in con.execute('select date,summary,location,city_guess,status from historique_scene_memory where '+where+' order by date desc limit 200',args)]
            con.close(); return self._json(rows)
        if p.path=='/api/departements':
            rows=[dict(r) for r in con.execute('select dep_code,dep_nom,reg_nom,nb_communes,population_totale,statut_analyse,priorite from departements order by dep_code')]
            con.close(); return self._json(rows)
        if p.path=='/api/communes':
            dep=qs.get('dep',['44'])[0]; q=qs.get('q',[''])[0]
            args=[dep]; where='dep_code=?'
            if q: where+=' and nom_standard like ?'; args.append(f'%{q}%')
            rows=[dict(r) for r in con.execute('select code_insee,nom_standard,population,statut_analyse,priorite_analyse,derniere_analyse from communes_analyse where '+where+' order by population desc limit 300',args)]
            con.close(); return self._json(rows)
        if p.path=='/api/lieux':
            q=qs.get('q',[''])[0]; typ=qs.get('type',[''])[0]; dep=qs.get('dep',[''])[0]
            args=[]; where='1=1'
            if q: where+=' and (nom_lieu like ? or ville like ? or coalesce(notes,\'\') like ?)'; args += [f'%{q}%']*3
            if typ: where+=' and type_lieu=?'; args.append(typ)
            if dep: where+=' and dep_code=?'; args.append(dep)
            rows=[dict(r) for r in con.execute('select * from lieux_culturels where '+where+' order by dep_code, ville, nom_lieu limit 250',args)]
            con.close(); return self._json(rows)
        if p.path.startswith('/api/lieux/'):
            id_lieu=p.path.split('/')[-1]
            r=con.execute('select * from lieux_culturels where id_lieu=?',(id_lieu,)).fetchone()
            notes=[dict(n) for n in con.execute('select * from notes_lieux where id_lieu=? order by created_at desc',(id_lieu,))]
            con.close(); return self._json({'lieu':dict(r) if r else None,'notes':notes})
        if p.path=='/api/profil':
            rows={r['cle']:r['valeur'] for r in con.execute('select * from profil_artiste')}
            con.close(); return self._json(rows)

        if p.path=='/api/database_status':
            status={
              'communes_total': con.execute('select count(*) from communes_france').fetchone()[0],
              'communes_44_queue': con.execute("select count(*) from commune_research_queue where dep_code='44'").fetchone()[0],
              'communes_44_haute': con.execute("select count(*) from commune_research_queue where dep_code='44' and priorite='haute'").fetchone()[0],
              'lieux_queue': con.execute('select count(*) from lieu_research_queue').fetchone()[0],
              'alias_proposes': con.execute('select count(*) from alias_lieux_proposes').fetchone()[0],
              'qualite_ouverte': con.execute("select count(*) from qualite_donnees where statut='ouvert'").fetchone()[0]
            }
            con.close(); return self._json(status)
        if p.path=='/api/database_communes_queue':
            dep=qs.get('dep',['44'])[0]; pr=qs.get('priorite',[''])[0]
            args=[dep]; where='dep_code=?'
            if pr: where+=' and priorite=?'; args.append(pr)
            rows=[dict(r) for r in con.execute('select * from commune_research_queue where '+where+' order by case priorite when \'haute\' then 1 when \'moyenne\' then 2 else 3 end, population desc limit 120',args)]
            con.close(); return self._json(rows)
        if p.path=='/api/database_aliases':
            rows=[dict(r) for r in con.execute('select * from alias_lieux_proposes order by nb_occurrences desc, nom_canonique_propose limit 120')]
            con.close(); return self._json(rows)
        if p.path=='/api/database_quality':
            rows=[dict(r) for r in con.execute('select * from qualite_donnees where statut=\'ouvert\' order by case gravite when \'haute\' then 1 when \'moyenne\' then 2 else 3 end limit 120')]
            con.close(); return self._json(rows)

        if p.path=='/api/chantier44_status':
            status={
              'communes_44': con.execute("select count(*) from chantier_44_communes").fetchone()[0],
              'priorite_tres_haute': con.execute("select count(*) from chantier_44_communes where priorite='tres_haute'").fetchone()[0],
              'priorite_haute': con.execute("select count(*) from chantier_44_communes where priorite='haute'").fetchone()[0],
              'avec_historique': con.execute("select count(*) from chantier_44_communes where nb_passages_kenny>0").fetchone()[0],
              'avec_lieux': con.execute("select count(*) from chantier_44_communes where nb_lieux_identifies>0").fetchone()[0]
            }
            con.close(); return self._json(status)
        if p.path=='/api/chantier44_communes':
            q=qs.get('q',[''])[0]; pr=qs.get('priorite',[''])[0]
            args=[]; where='1=1'
            if q:
                where+=' and commune like ?'; args.append(f'%{q}%')
            if pr:
                where+=' and priorite=?'; args.append(pr)
            rows=[dict(r) for r in con.execute('select * from chantier_44_communes where '+where+' order by case priorite when \'tres_haute\' then 1 when \'haute\' then 2 else 3 end, nb_passages_kenny desc, population desc limit 200',args)]
            con.close(); return self._json(rows)
        if p.path=='/api/chantier44_method':
            rows=[dict(r) for r in con.execute('select * from methodologie_recherche order by ordre')]
            con.close(); return self._json(rows)
        if p.path=='/api/chantier44_hypotheses':
            rows=[dict(r) for r in con.execute("select * from prospection_hypotheses where dep_code='44' order by created_at desc limit 50")]
            con.close(); return self._json(rows)

        if p.path=='/api/veille':
            rows=[dict(r) for r in con.execute("select statut_analyse, count(*) as nb from communes_analyse group by statut_analyse")]
            deps=[dict(r) for r in con.execute("select dep_code, dep_nom, statut_analyse, priorite, nb_communes from departements where dep_code in ('44','85','49','56','35') order by dep_code")]
            con.close(); return self._json({'statuts':rows,'departements':deps})
        con.close(); return self._json({'error':'not found'},404)
    def do_POST(self):
        p=urlparse(self.path); length=int(self.headers.get('Content-Length','0')); data=json.loads(self.rfile.read(length).decode('utf-8') or '{}')
        con=db()
        if p.path.startswith('/api/lieux/') and p.path.endswith('/note'):
            id_lieu=p.path.split('/')[-2]; txt=(data.get('contenu') or '').strip()
            if txt: con.execute('insert into notes_lieux(id_lieu,contenu,type_note) values (?,?,?)',(id_lieu,txt,data.get('type_note','note'))); con.commit()
            con.close(); return self._json({'ok':True})
        con.close(); return self._json({'error':'not found'},404)

def run():
    ensure_schema(); print('ARTYX unifié lancé : http://localhost:8787'); HTTPServer(('127.0.0.1',8787),Handler).serve_forever()
if __name__=='__main__': run()
