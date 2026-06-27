// Heuristic affiliation -> ISO2 country guess, for institutions not in the
// curated AFFIL_COUNTRY map. Best-effort: scans the name for a city, then a
// country name, then a demonym (that precedence). Limited to the 29 countries
// the map supports. Curated map always takes priority (see affIso in dashboard).
//
// Whole-word matching (\b) avoids false hits like "uk" inside "Fukuoka".
window.guessCountry = (function(){
  // ordered [token, ISO2] — first match wins, so list disambiguators first
  const TABLE = [
    // --- cities / institutions (US disambiguators before GB "york"/"cambridge") ---
    ["new york","US"],["massachusetts","US"],["boston","US"],["princeton","US"],
    ["berkeley","US"],["stanford","US"],["san diego","US"],["los angeles","US"],
    ["los alamos","US"],["oak ridge","US"],["livermore","US"],["wisconsin","US"],
    ["tennessee","US"],["knoxville","US"],["rochester","US"],["seattle","US"],
    ["washington","US"],["chicago","US"],["austin","US"],["columbia","US"],
    ["maryland","US"],["california","US"],
    ["london","GB"],["oxford","GB"],["cambridge","GB"],["edinburgh","GB"],
    ["york","GB"],["manchester","GB"],["glasgow","GB"],["liverpool","GB"],
    ["strathclyde","GB"],["belfast","GB"],["coventry","GB"],["lancaster","GB"],
    ["st andrews","GB"],["culham","GB"],["durham","GB"],["imperial","GB"],
    ["paris","FR"],["lyon","FR"],["marseille","FR"],["grenoble","FR"],
    ["bordeaux","FR"],["toulouse","FR"],["saclay","FR"],["cadarache","FR"],
    ["nancy","FR"],["lorraine","FR"],["strasbourg","FR"],
    ["munich","DE"],["münchen","DE"],["munchen","DE"],["berlin","DE"],
    ["garching","DE"],["greifswald","DE"],["jülich","DE"],["julich","DE"],
    ["stuttgart","DE"],["karlsruhe","DE"],["aachen","DE"],["hamburg","DE"],
    ["kiel","DE"],["dresden","DE"],["bayreuth","DE"],["heidelberg","DE"],
    ["madrid","ES"],["barcelona","ES"],["seville","ES"],["sevilla","ES"],
    ["valencia","ES"],["oviedo","ES"],["cantabria","ES"],["valladolid","ES"],
    ["córdoba","ES"],["cordoba","ES"],
    ["rome","IT"],["roma","IT"],["milan","IT"],["milano","IT"],["padova","IT"],
    ["padua","IT"],["naples","IT"],["napoli","IT"],["turin","IT"],["torino","IT"],
    ["trieste","IT"],["frascati","IT"],["bologna","IT"],["bicocca","IT"],
    ["lausanne","CH"],["geneva","CH"],["zurich","CH"],["zürich","CH"],
    ["tokyo","JP"],["osaka","JP"],["kyoto","JP"],["nagoya","JP"],["kyushu","JP"],
    ["tottori","JP"],["hyogo","JP"],["komazawa","JP"],
    ["stockholm","SE"],["gothenburg","SE"],["göteborg","SE"],["goteborg","SE"],
    ["chalmers","SE"],["uppsala","SE"],
    ["prague","CZ"],["praha","CZ"],["brno","CZ"],
    ["seoul","KR"],["daejeon","KR"],["busan","KR"],
    ["beijing","CN"],["shanghai","CN"],["hefei","CN"],["wuhan","CN"],
    ["harbin","CN"],["chengdu","CN"],["xi'an","CN"],["xian","CN"],
    ["tsinghua","CN"],["peking","CN"],["jiao tong","CN"],["beihang","CN"],
    ["huazhong","CN"],
    ["helsinki","FI"],["espoo","FI"],["aalto","FI"],["tampere","FI"],
    ["lisbon","PT"],["lisboa","PT"],["porto","PT"],["coimbra","PT"],
    ["brussels","BE"],["ghent","BE"],["gent","BE"],["leuven","BE"],
    ["liège","BE"],["liege","BE"],["louvain","BE"],
    ["vienna","AT"],["wien","AT"],["graz","AT"],["innsbruck","AT"],
    ["warsaw","PL"],["warszawa","PL"],["krakow","PL"],["kraków","PL"],["wroclaw","PL"],
    ["amsterdam","NL"],["eindhoven","NL"],["delft","NL"],["utrecht","NL"],
    ["nijmegen","NL"],["groningen","NL"],
    ["bucharest","RO"],["cluj","RO"],["iasi","RO"],
    ["toronto","CA"],["montreal","CA"],["vancouver","CA"],["edmonton","CA"],
    ["alberta","CA"],["quebec","CA"],["ottawa","CA"],["waterloo","CA"],
    ["kharkiv","UA"],["kyiv","UA"],["kiev","UA"],["lviv","UA"],
    ["jerusalem","IL"],["tel aviv","IL"],["haifa","IL"],["technion","IL"],["weizmann","IL"],
    ["athens","GR"],["thessaloniki","GR"],["ioannina","GR"],["patras","GR"],
    ["ljubljana","SI"],["maribor","SI"],
    ["budapest","HU"],["debrecen","HU"],["pecs","HU"],["pécs","HU"],
    ["oslo","NO"],["tromsø","NO"],["tromso","NO"],["bergen","NO"],["trondheim","NO"],
    ["delhi","IN"],["mumbai","IN"],["bangalore","IN"],["bengaluru","IN"],
    ["gandhinagar","IN"],["chennai","IN"],["kanpur","IN"],["sikkim","IN"],
    ["taipei","TW"],["hsinchu","TW"],["taiwan","TW"],
    ["singapore","SG"],["nanyang","SG"],["a*star","SG"],
    ["sydney","AU"],["melbourne","AU"],["canberra","AU"],["brisbane","AU"],
    ["perth","AU"],["adelaide","AU"],["queensland","AU"],
    ["brunel","GB"],["sorbonne","FR"],["onera","FR"],["mitsubishi","JP"],
    ["hun-ren","HU"],["tor vergata","IT"],["southwestern institute of physics","CN"],
    ["extreme light infrastructure eric","CZ"],
    // --- country names ---
    ["united kingdom","GB"],["u.k.","GB"],["england","GB"],["scotland","GB"],
    ["wales","GB"],["britain","GB"],["uk","GB"],
    ["united states","US"],["u.s.a","US"],["usa","US"],["america","US"],
    ["germany","DE"],["deutschland","DE"],["france","FR"],
    ["switzerland","CH"],["spain","ES"],["españa","ES"],["espana","ES"],
    ["italy","IT"],["italia","IT"],["japan","JP"],["nippon","JP"],
    ["sweden","SE"],["sverige","SE"],["czechia","CZ"],["korea","KR"],
    ["china","CN"],["finland","FI"],["portugal","PT"],["belgium","BE"],
    ["austria","AT"],["poland","PL"],["polska","PL"],["netherlands","NL"],
    ["holland","NL"],["romania","RO"],["canada","CA"],["ukraine","UA"],
    ["israel","IL"],["greece","GR"],["hellenic","GR"],["slovenia","SI"],
    ["hungary","HU"],["norway","NO"],["norge","NO"],["india","IN"],["australia","AU"],
    // --- demonyms (lowest priority) ---
    ["swiss","CH"],["chinese","CN"],["czech","CZ"],["german","DE"],["french","FR"],
    ["british","GB"],["american","US"],["spanish","ES"],["italian","IT"],
    ["swedish","SE"],["korean","KR"],["japanese","JP"],["finnish","FI"],
    ["portuguese","PT"],["belgian","BE"],["austrian","AT"],["polish","PL"],
    ["dutch","NL"],["romanian","RO"],["canadian","CA"],["ukrainian","UA"],
    ["israeli","IL"],["greek","GR"],["slovenian","SI"],["hungarian","HU"],
    ["norwegian","NO"],["indian","IN"],["taiwanese","TW"],["singaporean","SG"],["australian","AU"],
  ];
  const RX = TABLE.map(([t,iso]) =>
    [new RegExp('\\b'+t.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'\\b','i'), iso]);
  return function(name){
    if(!name) return null;
    for(const [r,iso] of RX) if(r.test(name)) return iso;
    return null;
  };
})();
