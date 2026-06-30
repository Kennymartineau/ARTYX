let currentDep='44';
const $=s=>document.querySelector(s); const $$=s=>document.querySelectorAll(s);
async function api(u,opt){
  const response=await fetch(u,opt);
  const text=await response.text();
  if(!response.ok){
    throw new Error(`API error ${response.status}: ${text||'no response'}`);
  }
  if(!text){return {};}
  try{return JSON.parse(text);}catch{return {};}
}
function showTab(id){
  $$('.tab').forEach(t=>t.classList.remove('visible'));
  $('#'+id).classList.add('visible');
  $$('.nav').forEach(b=>b.classList.toggle('active',b.dataset.tab===id));
  if(id==='territoires') loadDeps();
  if(id==='historique') loadHistory();
  if(id==='prospection') loadProspection();
  if(id==='lieux') loadLieux();
  if(id==='veille') loadVeille();
  if(id==='database') loadDatabase();
  if(id==='chantier44') loadChantier44();
  if(id==='profil') loadProfil();
}
$$('.nav').forEach(b=>b.onclick=()=>showTab(b.dataset.tab));
function card(n,l){return `<div class="card"><b>${n}</b><span>${l}</span></div>`}
async function loadOverview(){
  try{
    let d=await api('/api/overview');
    let pays=Array.isArray(d.pays)?d.pays:[];
    let spectacles=Array.isArray(d.spectacles)?d.spectacles:[];
    $('#homeCards').innerHTML=card(d.evenements_scene||0,'événements scène')+card(d.villes_count||0,'villes différentes')+card(pays.length,'pays détectés')+card((d.km_estime||0).toLocaleString('fr-FR')+' km','estimés');
    $('#spectacleStats').innerHTML=spectacles.map(s=>`<div class="bar"><div class="grow"><b>${s.spectacle||'—'}</b><br><small>${s.km? s.km.toLocaleString('fr-FR')+' km estimés' : 'km à préciser'}</small></div><span class="pill">${s.count||0} fois</span></div>`).join('');
  }catch(err){
    $('#homeCards').innerHTML=card('—','données indisponibles');
    $('#spectacleStats').innerHTML='<p class="muted">Le chargement du tableau de bord a échoué.</p>';
  }
}
async function loadHistory(){let q=$('#histSearch').value||''; let rows=await api('/api/history?q='+encodeURIComponent(q)); $('#histList').innerHTML=rows.map(r=>`<div class="item"><h3>${r.summary}</h3><small>${r.date||''} • ${r.city_guess||''} ${r.location||''}</small></div>`).join('')}
$('#histSearch').oninput=()=>loadHistory();
async function loadLieux(){let q=$('#lieuxSearch').value||'', t=$('#lieuxType').value||''; let rows=await api(`/api/lieux?q=${encodeURIComponent(q)}&type=${encodeURIComponent(t)}`); $('#lieuxList').innerHTML=rows.map(r=>`<div class="item" onclick="detailLieu('${r.id_lieu}')"><h3>${r.nom_lieu}</h3><small>${r.ville||''} • ${r.dep_code||''} • ${r.type_lieu||'type à préciser'}</small></div>`).join('')}
$('#lieuxSearch').oninput=()=>loadLieux(); $('#lieuxType').onchange=()=>loadLieux();
async function detailLieu(id){let d=await api('/api/lieux/'+id); let r=d.lieu; if(!r)return; $('#lieuDetail').innerHTML=`<h2>${r.nom_lieu}</h2><p>${r.ville||''} • ${r.dep_nom||''}</p><div class="kv"><b>Type</b><span>${r.type_lieu||''}</span><b>Catégorie</b><span>${r.categorie||''}</span><b>Source</b><span>${r.source||'à compléter'}</span><b>Confiance</b><span>${r.niveau_confiance||'à vérifier'}</span><b>Notes</b><span>${r.notes||''}</span></div><textarea id="noteLieu" placeholder="Ajouter ton ressenti ou une info terrain..."></textarea><button class="btn" onclick="saveNoteLieu('${id}')">Ajouter la note</button><h3>Notes</h3>${(d.notes||[]).map(n=>`<div class="bar"><div>${n.contenu}</div></div>`).join('')}`}
async function saveNoteLieu(id){let txt=$('#noteLieu').value; await api('/api/lieux/'+id+'/note',{method:'POST',body:JSON.stringify({contenu:txt})}); detailLieu(id)}
async function loadDeps(){let rows=await api('/api/departements'); $('#depList').innerHTML=rows.map(r=>`<div class="item" onclick="currentDep='${r.dep_code}';loadCommunes();"><h3>${r.dep_code} - ${r.dep_nom}</h3><small>${r.reg_nom} • ${r.nb_communes} communes • ${r.statut_analyse||'à analyser'}</small></div>`).join(''); loadCommunes()}
async function loadCommunes(){
  let q=$('#communeSearch').value||'';
  let sort=$('#communeSort')?.value||'population';
  let rows=await api(`/api/communes?dep=${currentDep}&q=${encodeURIComponent(q)}&sort=${encodeURIComponent(sort)}`);
  $('#communeList').innerHTML=
    `<h2>Communes du ${currentDep}</h2>`+
    `<div class="row"><select id="communeSort" onchange="loadCommunes()"><option value="population" ${sort==='population'?'selected':''}>Trier par population</option><option value="alpha" ${sort==='alpha'?'selected':''}>Trier par ordre alphabétique</option></select></div>`+
    `<div class="split"><div class="list compact">`+
    rows.map(r=>`
      <div class="item" onclick="detailCommune('${r.code_insee}')">
        <h3>${r.nom_standard}</h3>
        <small>${(r.population||0).toLocaleString('fr-FR')} hab. • ${r.statut_analyse||'jamais analysée'} • priorité ${r.priorite_analyse||''}</small>
      </div>
    `).join('')+
    `</div><div id="communeDetail" class="detail">Sélectionne une commune.</div></div>`;
}
$('#communeSearch').oninput=()=>loadCommunes();
async function detailCommune(code){
  let d=await api('/api/communes/'+code);
  if(d.error){ $('#communeDetail').innerHTML='<p class="muted">Commune introuvable.</p>'; return; }
  let c=d.commune || {};
  let ch=d.chantier || {};
  $('#communeDetail').innerHTML=`
    <h2>${c.nom_standard || ''}</h2>
    <p>${c.dep_code || '44'} • ${(c.population||0).toLocaleString('fr-FR')} habitants</p>
    <div class="kv">
      <b>Statut analyse</b><span>${c.statut_analyse||'à analyser'}</span>
      <b>Priorité</b><span>${c.priorite_analyse||ch.priorite||'normale'}</span>
      <b>Historique Kenny</b><span>${ch.nb_passages_kenny||d.historique.length} passage(s)</span>
      <b>Lieux identifiés</b><span>${d.lieux.length}</span>
      <b>Prochaine action</b><span>${ch.prochaine_action||'à définir'}</span>
      <b>Pourquoi</b><span>${ch.raison_priorite||'à compléter'}</span>
    </div>
    <button class="btn" onclick="editCommune('${code}')">Modifier</button>
    <h3>Lieux culturels</h3>
    ${d.lieux.length ? d.lieux.map(l=>`
      <div class="bar">
        <div class="grow"><b>${l.nom_lieu}</b><br><small>${l.type_lieu||'type à préciser'} • ${l.niveau_confiance||'à vérifier'}</small></div>
      </div>
    `).join('') : '<p class="muted">Aucun lieu identifié pour le moment.</p>'}
    <h3>Historique Kenny</h3>
    ${d.historique.length ? d.historique.map(h=>`
      <div class="bar">
        <div class="grow"><b>${h.summary}</b><br><small>${h.date||''} • ${h.location||''}</small></div>
      </div>
    `).join('') : '<p class="muted">Aucun passage détecté.</p>'}
    <h3>Notes commune</h3>
    <textarea id="noteCommune" placeholder="Note terrain, idée de prospection, ressenti..."></textarea>
    <button class="btn" onclick="saveNoteCommune('${code}')">Ajouter la note</button>
    ${(d.notes||[]).map(n=>`<div class="bar"><div>${n.contenu}</div></div>`).join('')}
  `;
}
async function editCommune(code){
  let d=await api('/api/communes/'+code);
  let c=d.commune || {};
  $('#communeDetail').innerHTML=`
    <h2>${c.nom_standard || ''}</h2>
    <div class="kv">
      <b>Population</b><span><input id="editPopulation" value="${c.population||''}"></span>
      <b>Statut analyse</b><span><input id="editStatut" value="${c.statut_analyse||''}"></span>
      <b>Priorité analyse</b><span><input id="editPriorite" value="${c.priorite_analyse||''}"></span>
      <b>Dernière analyse</b><span><input id="editDerniereAnalyse" value="${c.derniere_analyse||''}"></span>
    </div>
    <button class="btn" onclick="saveCommune('${code}')">Enregistrer</button>
    <button class="btn" onclick="detailCommune('${code}')">Annuler</button>
  `;
}
async function saveCommune(code){
  let payload={
    population: $('#editPopulation').value,
    statut_analyse: $('#editStatut').value,
    priorite_analyse: $('#editPriorite').value,
    derniere_analyse: $('#editDerniereAnalyse').value
  };
  await api('/api/communes/'+code+'/update',{method:'POST',body:JSON.stringify(payload)});
  detailCommune(code);
}
async function saveNoteCommune(code){
  let txt=$('#noteCommune').value;
  await api('/api/communes/'+code+'/note',{method:'POST',body:JSON.stringify({contenu:txt})});
  detailCommune(code);
}
async function loadProspection(){let q=$('#prospectSearch').value||'', dep=$('#prospectDep').value||'44'; let rows=await api(`/api/lieux?dep=${dep}&q=${encodeURIComponent(q)}`); $('#prospectList').innerHTML=rows.map(r=>`<div class="item"><h3>${r.nom_lieu}</h3><small>${r.ville||''} • ${r.type_lieu||''} • ${r.niveau_confiance||'à vérifier'}</small></div>`).join('')}
$('#prospectSearch').oninput=()=>loadProspection(); $('#prospectDep').onchange=()=>loadProspection();
async function loadVeille(){let d=await api('/api/veille'); $('#veilleCards').innerHTML=d.departements.map(x=>card(x.dep_code,x.dep_nom+' • '+(x.statut_analyse||'à analyser'))).join('') + card(d.statuts.reduce((a,b)=>a+b.nb,0),'communes dans la veille')}
async function loadDatabase(){
  let d=await api('/api/database_status');
  $('#dbCards').innerHTML=
    card(d.communes_total.toLocaleString('fr-FR'),'communes France')+
    card(d.communes_44_queue,'communes 44 en file')+
    card(d.communes_44_haute,'priorité haute 44')+
    card(d.lieux_queue,'lieux à vérifier')+
    card(d.alias_proposes,'regroupements proposés')+
    card(d.qualite_ouverte,'points qualité ouverts');
  let communes=await api('/api/database_communes_queue?dep=44');
  $('#queueCommunes').innerHTML=communes.map(r=>`<div class="item"><h3>${r.commune}</h3><small>${(r.population||0).toLocaleString('fr-FR')} hab. • ${r.priorite} • ${r.raison_priorite}</small></div>`).join('');
  let aliases=await api('/api/database_aliases');
  $('#aliasList').innerHTML=aliases.map(r=>`<div class="item"><h3>${r.nom_canonique_propose}</h3><small>${r.ville_proposee||''} • ${r.nb_occurrences} occurrence(s) • ${r.statut_validation}</small><p>${r.nom_source||''}</p></div>`).join('');
  let q=await api('/api/database_quality');
  $('#qualityList').innerHTML=q.map(r=>`<div class="bar"><div class="grow"><b>${r.table_nom}</b> • ${r.objet_id}<br><small>${r.champ} : ${r.probleme}</small></div><span class="pill">${r.gravite}</span></div>`).join('');
}
async function loadProfil(){let p=await api('/api/profil'); $('#profilBox').innerHTML=`<div class="card"><b>${p.nom}</b><span>${p.baseline}</span></div><div class="bar"><div class="grow"><b>Spectacle actuel</b><br>${p.spectacle_actuel}</div></div><p>${p.bio_courte}</p><p><b>Site :</b> ${p.site}</p><button class="btn">Préparer un mail avec ma fiche</button>`}
$('#globalSearch').onkeydown=e=>{if(e.key==='Enter'){showTab('lieux'); $('#lieuxSearch').value=e.target.value; loadLieux();}}
loadOverview();
async function loadChantier44(){
  let s=await api('/api/chantier44_status');
  $('#chantier44Cards').innerHTML=
    card(s.communes_44,'communes du 44')+
    card(s.priorite_tres_haute,'priorité très haute')+
    card(s.priorite_haute,'priorité haute')+
    card(s.avec_historique,'avec historique Kenny')+
    card(s.avec_lieux,'avec lieux identifiés');
  await loadChantier44Communes();
  let m=await api('/api/chantier44_method');
  $('#method44List').innerHTML=m.map(x=>`<div class="item"><h3>${x.ordre}. ${x.action}</h3><small>${x.niveau}</small><p>${x.objectif}</p></div>`).join('');
  let h=await api('/api/chantier44_hypotheses');
  $('#hypotheses44List').innerHTML=h.map(x=>`<div class="item"><h3>${x.commune}</h3><small>${x.statut} • ${x.source||''}</small><p>${x.hypothese}</p></div>`).join('');
}
async function loadChantier44Communes(){
  let q=$('#chantier44Search')?.value||'', pr=$('#chantier44Priority')?.value||'';
  let rows=await api(`/api/chantier44_communes?q=${encodeURIComponent(q)}&priorite=${encodeURIComponent(pr)}`);
  $('#chantier44List').innerHTML=rows.map(r=>`<div class="item"><h3>${r.commune}</h3><small>${(r.population||0).toLocaleString('fr-FR')} hab. • ${r.priorite} • ${r.nb_passages_kenny} passage(s) Kenny • ${r.nb_lieux_identifies} lieu(x)</small><p><b>Pourquoi :</b> ${r.raison_priorite||''}</p><p><b>Prochaine action :</b> ${r.prochaine_action||''}</p></div>`).join('');
}
setTimeout(()=>{let a=$('#chantier44Search'), b=$('#chantier44Priority'); if(a)a.oninput=()=>loadChantier44Communes(); if(b)b.onchange=()=>loadChantier44Communes();},500);
