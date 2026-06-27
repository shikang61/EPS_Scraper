// Classify an affiliation into a type for grouping the cards:
//   uni = University, inst = Research institute, company = Company, org = Organisation, other
// Heuristic on the name + an overrides map for acronyms the keywords can't catch.
// Curated overrides win; then ordered keyword rules; else 'other'.
window.TYPE_LABELS = {uni:'Universities', inst:'Research institutes', company:'Companies', org:'Organisations', other:'Other'};
window.TYPE_ORDER  = ['uni','inst','company','org','other'];
window.affType = (function(){
  const norm = s => s.replace(/\s+/g,' ').trim().toLowerCase().replace(/^[ .,;:]+|[ .,;:]+$/g,'');

  // normKey(affiliation) -> type, for names the rules miss or misclassify
  const OVR = {
    "cea":"inst","ciemat":"inst","enea":"inst","vtt":"inst","cnrs":"inst","cpht":"inst",
    "celia":"inst","asipp":"inst","differ":"inst","dieti":"inst","arcnl":"inst","inflpr":"inst",
    "ibs korea":"inst","lpp-erm":"inst","european xfel gmbh":"inst",
    "epfl":"uni","epfl, swiss plasma center":"uni","kaist":"uni","ens de lyon":"uni",
    "instituto superior técnico":"uni","instituto superior de engenharia de lisboa":"uni",
    "ntt":"company","demcon":"company","pasteur labs":"company","alpha ring":"company",
    "novatron fusion":"company","next step fusion":"company","general atomics":"company",
    "tokamak energy":"company","cambridge multiphysics":"company","meranti research laboratories":"company",
    "vdi technologiezentrum":"company",
    "step fusion":"org","eurofusion":"org",
    "ku leuven":"uni","tu wien":"uni","uct prague":"uni","ipp garching":"inst",
    "indian institute of science":"uni","royal military academy belgium":"uni",
    "a*star":"inst","onera":"inst","extreme light infrastructure eric":"inst",
  };

  // checked in order, first match wins
  const RULES = [
    [/universi|\bcollege\b|polytechnic|politecnico|\bécole\b|\becole\b|institute of technology|h(ö|o)gskola|\bhochschule\b/i, 'uni'],
    [/\bltd\b|\bgmbh\b|\binc\b|\bllc\b|\bplc\b|\bco\b|\bcorp|\bsystems\b|\bsolutions\b/i, 'company'],
    [/authority|agency|organi[sz]ation|consortium|consorzio|\bcouncil\b|association|commission|eurofusion|\biter\b/i, 'org'],
    [/institut|laborato|\bcentre\b|\bcenter\b|\bcentro\b|zentrum|observ|fraunhofer|max[ -]planck|forschung|\bfacility\b|academy of sciences|\bresearch\b/i, 'inst'],
  ];

  return function(name){
    if(!name) return 'other';
    const k = norm(name);
    if(OVR[k]) return OVR[k];
    for(const [r,t] of RULES) if(r.test(name)) return t;
    return 'other';
  };
})();
